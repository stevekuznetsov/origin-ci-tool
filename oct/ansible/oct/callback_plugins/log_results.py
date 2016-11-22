# coding=utf-8
from __future__ import absolute_import, division, print_function, unicode_literals

from codecs import open
from datetime import datetime
from os import environ, makedirs
from os.path import exists, join, sep
from shutil import rmtree
from tempfile import mkdtemp
from traceback import format_exc

from ansible.plugins.callback import CallbackBase
from yaml import dump


def log_exceptions(func):
    """
    Instead of allowing exceptions from the method
    this decorates, log the exception to disk and
    instead fail silently. I know this is insane.
    We want to:
        a) get the full exception output
        b) not pollute std{out,err}
    Ansible does not allow us these simple things.
    So we work around it in a crazy way.

    :param func: function to decorate
    :return: decorated function
    """

    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception:
            with open(join(args[0].log_root_dir, 'internal.log'), 'a', encoding='utf-8') as log_file:
                log_file.write(
                    '{} | Exception on func {} with args self, {} and kwargs {}:\n{}\n'.
                    format(datetime.now(), func.__name__, args[1:], kwargs, format_exc())
                )

    return wrapper


def log_exceptions_v2_playbook_on_start(func):
    """
    The Ansible TaskQueueManager inspects the
    declared argument names, but only for the
    `v2_playbook_on_start` method, and if the
    method does not explicitly list `playbook`
    as an argument, it mangles the call. This
    wrapper, therefore, exposes `playbook` as
    an argument.

    :param func: wrapped v2_playbook_on_start
    :return: better wrapper
    """

    def wrapper(self, playbook):
        return func(self, playbook)

    return wrapper


class CallbackModule(CallbackBase):
    """
    Logs results from tasks, per playbook, per host.
    Logfiles are aggregates of YAML snippets that
    describe actions, their results, and where full
    log messages can be found. Full log messages are
    aggregates of YAML snippets that were given to
    the callback, like the result, whether errors are
    to be ignored, etc.
    """
    CALLBACK_VERSION = 2.0
    CALLBACK_TYPE = 'notification'
    CALLBACK_NAME = 'log_results'
    CALLBACK_NEEDS_WHITELIST = True

    def __init__(self):
        super(CallbackModule, self).__init__()

        self.log_root_dir = environ.get('ANSIBLE_LOG_ROOT_PATH', mkdtemp(prefix='ansible_log'))
        if not exists(self.log_root_dir):
            makedirs(self.log_root_dir)

        # we will update the current playbook log path
        # once we know we are executing a playbook
        self.current_playbook_log_path = None

    def write_log(self, message, logfile=None, data=None):
        """
        Write a message to the current playbook log and
        optionally dump verbose data to a separate log-
        file, linking the two with another message in
        the playbook log.

        :param message: message for the playbook log
        :param logfile: path to extra log file
        :param data: data for extra log file
        """
        with open(self.current_playbook_log_path, 'a', encoding='utf-8') as playbook_log:
            playbook_log.write('{} | {}\n'.format(datetime.now(), message))
            if logfile and data:
                playbook_log.write('\tFull output at:{}\n'.format(logfile))
                # sanitize the data to remove Ansible
                # internal fields that the user doesn't
                # need in their output files
                for key in data.keys():
                    if key.startswith('_ansible'):
                        del data[key]

                # remove `stdout_lines` if `stdout` is
                # present -- we can let people load the
                # data and format it however they want,
                # but we don't want to store it twice
                if 'results' in data:
                    for result in data['results']:
                        if 'stdout' in result and 'stdout_lines' in result:
                            del result['stdout_lines']

                with open(logfile, 'wb', encoding='utf-8') as log_file:
                    log_file.write(dump(data, default_flow_style=False, explicit_start=True))

    def log_task_result(self, status, result):
        """
        Log the result of a task.

        :param status: exit status of the task
        :param result: result data from the task
        """
        host = result._host.get_name()
        message = 'Task finished with status "{}" on host "{}"'.format(status, host)
        logfile = join(self.log_dir_for_task(result._task), '{}_{}.yml'.format(host, status))
        data = result._result
        self.write_log(message, logfile, data)

    def log_dir_for_task(self, task):
        """
        Determine the directory in which logs
        for the given task should be placed.

        :param task: task to inspect
        :return: absolute path to the task log directory
        """
        return join(self.log_dir_for_play(task._parent._play), 'task_{}'.format(task._uuid))

    def log_dir_for_play(self, play):
        """
        Determine the directory in which logs
        for the given play should be placed.

        :param play: play to inspect
        :return: absolute path to the play log directory
        """
        # the location of the play must be in the playbook
        playbook_file, _ = self.determine_location_for_workload(play)
        return join(self.log_dir_for_playbook(playbook_file), 'play_{}'.format(play._uuid))

    def log_dir_for_playbook(self, playbook_source):
        """
        Determine the directory in which logs
        for the given playbook should be placed.

        :param playbook_source: playbook location on disk
        :return: absolute path to the playbook log directory
        """
        return join(self.log_root_dir, 'playbook_{}'.format(playbook_source.replace(sep, '_')))

    def log_message_for_task(self, task, message_prefix):
        """
        Log a message for a task. The message will
        be prepended to a generic stanza identifying
        the task.

        :param task: task to log for
        :param message_prefix: message prefix to write
        """
        task_file, task_line = self.determine_location_for_workload(task)
        self.write_log(
            '{} task "{}" with UUID "task_{}" from "{}:{}".'.format(
                message_prefix,
                task.get_name(),
                task._uuid,
                task_file,
                task_line,
            )
        )

    def determine_location_for_workload(self, workload):
        """
        Determine the file location and line number where
        the Ansible workload is defined. Not every workload
        has a consistent set of entries in `_attributes`, so
        we need to take a more dynamic approach to find one
        that we can (ab)use for this information.

        :param workload: Ansible workload to inspect
        :return: file path, line number
        """
        if not hasattr(workload, '_attributes'):
            return 'unknown', 'unknown'

        for attribute in workload._attributes.values():
            if hasattr(attribute, '_data_source'):
                return attribute._data_source, attribute._line_number

        return 'unknown', 'unknown'

    @log_exceptions_v2_playbook_on_start
    @log_exceptions
    def v2_playbook_on_start(self, playbook):
        """
        Implementation of the callback endpoint to be
        fired when execution of a new playbook begins.
        We are only interested in recording the results
        for the last run of any particular playbook, so
        if the log directory already exists for this
        playbook, we will over-write it. Otherwise, we
        make sure to set up the directory for future
        writes from other callback handlers.

        :param playbook: playbook which began execution
        """
        playbook_log_dir = self.log_dir_for_playbook(playbook._file_name)
        if exists(playbook_log_dir):
            rmtree(playbook_log_dir)

        makedirs(playbook_log_dir)
        self.current_playbook_log_path = join(playbook_log_dir, 'log')
        self.write_log('Starting execution for playbook at {}'.format(playbook._file_name))

    @log_exceptions
    def v2_playbook_on_import_for_host(self, result, imported_file):
        """
        Implementation of the callback endpoint to be
        fired when an import occurs on a host.

        :param result: result of the import action
        :param imported_file: which file was imported by the host
        """
        # TODO: determine what this result looks like and place it in the right log dir
        host = result._host.get_name()
        self.write_log('Imported file at "{}" on host "{}"'.format(imported_file, host))
        self.write_log(dump(result, default_flow_style=False, explicit_start=True))

    @log_exceptions
    def v2_playbook_on_not_import_for_host(self, result, missing_file):
        """
        Implementation of the callback endpoint to be
        fired when an import fails on a host.

        :param result: result of the import action
        :param missing_file: which file was not found on the host
        """
        # TODO: determine what this result looks like and place it in the right log dir
        host = result._host.get_name()
        self.write_log('Failed to import file at "{}" on host "{}"'.format(missing_file, host))
        self.write_log(dump(result, default_flow_style=False, explicit_start=True))

    @log_exceptions
    def v2_playbook_on_include(self, included_file):
        """
        Implementation of the callback endpoint to be
        fired when an include statement is executed.

        :param included_file: which file was imported by the host
        """
        self.write_log('Included file at "{}"'.format(included_file))

    @log_exceptions
    def v2_playbook_on_setup(self):
        """
        Implementation of the callback endpoint to be
        fired when a setup task is executed. We want
        to handle this case separately from the generic
        task case as setup "tasks" do not contain much
        of the metadata we expect to see on all tasks.
        """
        self.write_log('Running setup for playbook.')

    @log_exceptions
    def v2_playbook_on_play_start(self, play):
        """
        Implementation of the callback endpoint to be
        fired when execution of a new play begins.

        :param play: play which began execution
        """
        makedirs(self.log_dir_for_play(play))
        play_file, play_line = self.determine_location_for_workload(play)
        self.write_log(
            'Starting execution for play "{}" with name "play_{}" from "{}:{}".'.format(
                play.get_name(),
                play._uuid,
                play_file,
                play_line,
            )
        )

    @log_exceptions
    def v2_playbook_on_task_start(self, task, is_conditional):
        """
        Implementation of the callback endpoint to be
        fired when execution of a new task begins.

        :param task:task which began execution
        :param is_conditional: whether or not this task is conditional
        """
        makedirs(self.log_dir_for_task(task))
        self.log_message_for_task(task, 'Starting')

    @log_exceptions
    def v2_runner_on_failed(self, result, ignore_errors=False):
        """
        Implementation of the callback endpoint to be
        fired when a task fails to execute successfully.

        :param result: result of the task execution
        :param ignore_errors: if we should consider this a failure
        """
        self.log_task_result('failed', result)

    @log_exceptions
    def v2_runner_on_ok(self, result):
        """
        Implementation of the callback endpoint to be
        fired when a task executes successfully.

        :param result: result of the task execution
        """
        self.log_task_result('ok', result)

    @log_exceptions
    def v2_runner_on_skipped(self, result):
        """
        Implementation of the callback endpoint to be
        fired when task execution is skipped.

        :param result: result of the task execution
        """
        self.log_task_result('skipped', result)

    @log_exceptions
    def v2_runner_on_unreachable(self, result):
        """
        Implementation of the callback endpoint to be
        fired when a task fails to reach a target host.

        :param result: result of the task execution
        """
        self.log_task_result('unreachable', result)

    @log_exceptions
    def v2_runner_on_no_hosts(self, task):
        """
        Implementation of the callback endpoint to be
        fired when a task finds no hosts to execute on.

        :param task: task which did not execute
        """
        self.log_message_for_task(task, 'No hosts found for')

    @log_exceptions
    def v2_runner_on_async_ok(self, result):
        """
        Implementation of the callback endpoint to be
        fired when a task asynchronously executes
        successfully.

        :param result: result of the task execution
        """
        self.log_task_result('async ok', result)

    @log_exceptions
    def v2_runner_on_async_failed(self, result):
        """
        Implementation of the callback endpoint to be
        fired when a task fails to execute asynchronously
        successfully.

        :param result: result of the task execution
        """
        self.log_task_result('async failed', result)

    @log_exceptions
    def v2_playbook_on_no_hosts_matched(self):
        """
        Implementation of the callback endpoint to be
        fired when a playbook finds no hosts to execute on.
        """
        self.write_log('No hosts matched.')

    @log_exceptions
    def v2_playbook_on_no_hosts_remaining(self):
        """
        Implementation of the callback endpoint to be
        fired when a playbook has no hosts remaining
        to execute on.
        """
        self.write_log('No hosts remaining.')

        # TODO: unimplemented methods follow - do we need them?
        # def v2_runner_item_on_ok(self, result):
        # def v2_runner_item_on_failed(self, result):
        # def v2_runner_item_on_skipped(self, result):
        # def v2_runner_retry(self, result):
        # def v2_runner_on_file_diff(self, result, diff):
        # def v2_playbook_on_notify(self, result, handler):
        # def v2_playbook_on_cleanup_task_start(self, task):
        # def v2_playbook_on_handler_task_start(self, task):
        # def v2_playbook_on_vars_prompt(self, varname, private=True, prompt=None, encrypt=None,
        #                                confirm=False, salt_size=None, salt=None, default=None):
        # def v2_on_file_diff(self, result):
        # def v2_playbook_on_stats(self, stats):


from structlog import get_logger

logger = get_logger()

def callback_generic_event(func):
    def wrapper(*args, **kwargs):
        logger.bind(callback=func.__name__)
        func(*args, **kwargs)
        logger.unbind('callback')

    return wrapper


def callback_result_event(func):
    def wrapper(callback_module, raw_result, *args, **kwargs):
        host = raw_result._host.get_name()
        result = santitize_result(raw_result._result)
        ansible_workload_reference = {
            'uuid': raw_result._task._uuid,
            'type': 'task'
        }
        logger.bind(host=host, result=result, ansible_workload_reference=ansible_workload_reference)
        callback_generic_event(func)(callback_module, raw_result, *args, **kwargs)
        logger.unbind('host', 'result', 'ansible_workload_reference')

    return wrapper


def callback_start_event(func):
    def wrapper(callback_module, ansible_workload, *args, **kwargs):
        ansible_workload_reference = {
            'uuid': ansible_workload._uuid,
            'type': type(ansible_workload).__name__.lower()
        }
        logger.bind(ansible_workload_reference=ansible_workload_reference)
        callback_generic_event(func)(callback_module, ansible_workload, *args, **kwargs)
        logger.unbind('ansible_workload_reference')

    return wrapper
