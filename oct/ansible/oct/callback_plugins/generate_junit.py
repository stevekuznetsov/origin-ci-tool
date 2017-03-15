# coding=utf-8
"""
A callback module that outputs jUnit XML for plays.
"""
from __future__ import absolute_import, division, print_function, unicode_literals

from random import choice
from string import ascii_letters
from timeit import default_timer as timer

import os
from ansible.plugins.callback import CallbackBase
from junit_xml import TestCase, TestSuite
from os import getenv, makedirs
from os.path import abspath, exists, expanduser, join, normpath, realpath, sep, splitext


class CallbackModule(CallbackBase):
    """
    This module allows for CLI-based Ansible invocations
    to have nicely formatted output that cleanly indicates
    to the users what their CLI call is doing and how far
    along it is in the process.
    """
    CALLBACK_VERSION = 2.0
    CALLBACK_TYPE = 'notification'
    CALLBACK_NAME = 'generate_junit'
    CALLBACK_NEEDS_WHITELIST = True

    def __init__(self, *args, **kwargs):
        # track the currently executing task
        self.current_task = None
        self.current_task_start = None

        # we track the entirety of our actions as a
        # suite, which we can create at the end. For
        # that, we need to keep track of test suites
        # during execution and the name of the play-
        # book we are running
        self.test_suites = {}
        self.playbook_name = ''

        super(CallbackModule, self).__init__(*args, **kwargs)

    def append_test_case(self, test_case):
        play_name = self.current_task._parent._play.get_name()
        if play_name in self.test_suites:
            self.test_suites[play_name].append(test_case)
        else:
            self.test_suites[play_name] = [test_case]

    def test_case_for_result(self, result):
        return TestCase(
            name='[{}] {}'.format(result._host, self.current_task.get_name()),
            elapsed_sec=timer() - self.current_task_start,
        )

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
        # We want the playbook names to be short but
        # ultimately unique identifiers. If we notice
        # that we're running a playbook from a known
        # repo, we strip the leading path for brevity.
        # We do not need the file extension, and it is
        # interpreted weirdly by jUnit viewers, so we
        # get rid of it
        playbook_path = splitext(normpath(realpath(playbook._file_name)))[0].split(sep)
        project_prefixes = [
            ['oct', 'ansible', 'oct', 'playbooks'],
            ['openshift-ansible', 'playbooks'],
            ['openshift-ansible-gce', 'playbooks'],
        ]
        for i in range(len(playbook_path)):
            for prefix in project_prefixes:
                if i + len(prefix) >= len(playbook_path):
                    continue

                if playbook_path[i:i + len(prefix)] == prefix:
                    self.playbook_name = sep.join(playbook_path[i + len(prefix):])
                    return

        self.playbook_name = playbook._file_name

    def v2_playbook_on_task_start(self, task, is_conditional):
        """
        Implementation of the callback endpoint to be
        fired when execution of a new task begins. We
        keep track of the last running task, so here
        we update that record.

        :param task: task that just started
        :param is_conditional: if the task is conditional
        """
        self.current_task = task
        self.current_task_start = timer()

    def v2_runner_on_ok(self, result):
        """
        Implementation of the callback endpoint to be
        fired when a task finishes executing successfully.
        We assume that the last workload is the last task.

        :param result: result of the last task
        """
        self.append_test_case(self.test_case_for_result(result))

    def v2_runner_on_failed(self, result, ignore_errors=False):
        """
        Implementation of the callback endpoint to be
        fired when a task fails to execute successfully.
        If we are not ignoring errors, we will not only
        show the task as failed, but also add the error
        information to the output stream.

        :param result: result of the last task
        :param ignore_errors: if we should consider this a failure
        """
        test_case = self.test_case_for_result(result)
        if not ignore_errors:
            test_case.add_failure_info(format_result(result._result))
        self.append_test_case(test_case)

    def v2_runner_on_unreachable(self, result):
        """
        Implementation of the callback endpoint to be
        fired when a task can't reach it's target host.
        We will show the task as errored and append the
        error information to the output stream.

        :param result: result of the last task
        """
        test_case = self.test_case_for_result(result)
        test_case.add_error_info(format_result(result._result))
        self.append_test_case(test_case)

    def v2_runner_on_skipped(self, result):
        """
        Implementation of the callback endpoint to be
        fired when task execution is skipped.

        :param result: result of the last task
        """
        test_case = self.test_case_for_result(result)
        test_case.add_skipped_info(format_result(result._result))
        self.append_test_case(test_case)

    def v2_playbook_on_stats(self, stats):
        """
        Implementation of the callback endpoint to be
        fired when a playbook is finished. As we are
        only running one playbook at a time, we know
        we are done logging and can aggregate the jUnit
        test suite and serialize it.

        :param stats: statistics about the run
        """
        suites = []
        for play_name in self.test_suites:
            suites.append(TestSuite(play_name, self.test_suites[play_name]))

        if 'ANSIBLE_JUNIT_DIR' in os.environ:
            log_dir = abspath(getenv('ANSIBLE_JUNIT_DIR'))
        else:
            if 'OCT_CONFIG_HOME' in os.environ:
                base_dir = getenv('OCT_CONFIG_HOME')
            else:
                base_dir = abspath(join(expanduser('~'), '.config'))
            log_dir = abspath(join(base_dir, 'origin-ci-tool', 'logs', 'junit'))

        if not exists(log_dir):
            makedirs(log_dir)

        log_filename = ''
        for _ in range(10):
            log_basename = '{}.xml'.format(''.join(choice(ascii_letters) for _ in range(10)))
            log_filename = join(log_dir, log_basename)
            if not exists(log_filename):
                # TODO: determine a better way to do this
                break

        with open(log_filename, 'w') as result_file:
            TestSuite.to_file(result_file, suites)


def format_result(result):
    """
    Attempt to extract and format information
    about an Ansible workload result.

    :param result: result to inspect
    :return: message
    """
    full_message = format_failure_message(result)
    full_message += format_item_failures(result)
    full_message += format_terminal_output(result)
    # detect internal module failures
    full_message += format_terminal_output(result, stdout_key='module_stdout', stderr_key='module_stderr')
    # detect internal stacktrace crashes
    full_message += format_internal_exception_output(result)
    full_message += format_parsing_error(result)

    # filter out empty lines and lines of only whitespace
    full_message = [line for line in full_message.splitlines() if line and line.strip()]
    return "\n".join(full_message)


def format_failure_message(result):
    """
    Output a formatted version of the failure
    message, if the result contains one.

    :param result: result to inspect
    :return: message
    """
    if 'msg' in result:
        # this is most likely a module failure
        if isinstance(result['msg'], list):
            error_message = '\n'.join(result['msg'])
        else:
            error_message = result['msg']

        return '{}\n'.format(error_message)

    return ''


def format_item_failures(result):
    """
    Output a formatted version of the item
    failures, if the result contains any.

    :param result: result to inspect
    :return: message
    """
    if 'results' in result:
        # this is most likely a failure from with_items
        item_preamble = 'The following error messages came from items:'
        item_messages = []
        for item_result in result['results']:
            # the item could possibly contain any
            # valid result output, as any Ansible
            # workload can be looped over
            item_messages.append(format_result(item_result))

        item_messages = [message for message in item_messages if len(message) > 0]
        if len(item_messages) > 0:
            return '{}\n{}'.format(item_preamble, '\n'.join(item_messages))

    return ''


def format_terminal_output(result, stdout_key='stdout', stderr_key='stderr'):
    """
    Output a formatted version of the terminal
    output (std{out,err}), if the result contains
    either.

    :param stdout_key: where stdout is recorded
    :param stderr_key: where stderr is recorded
    :param result: result to inspect
    :return: formatted output message
    """
    output_message = ''
    if stdout_key in result:
        # this is most likely a shell/command/raw failure
        if len(result[stdout_key]) > 0:
            output_message += '{}\n{}\n'.format('Output to stdout:', result[stdout_key])

    if stderr_key in result:
        if len(result[stderr_key]) > 0:
            output_message += '{}\n{}\n'.format('Output to stderr:', result[stderr_key])

    if stdout_key in result and len(result[stdout_key]) == 0 and stderr_key in result and len(result[stderr_key]) == 0:
        output_message = 'No output was written to stdout or stderr!'

    return output_message


def format_internal_exception_output(result):
    """
    Output a formatted version of any internal
    errors that Ansible runs into when executing,
    if any are present.

    :param result: result to inspect
    :return: formatted output message
    """
    if 'exception' in result:
        return 'An internal exception occurred:\n{}'.format(result['exception'])

    return ''


def format_parsing_error(result):
    """
    Output a formatted version of any parsing
    errors that Ansible runs into when looking
    at a playbook, if any are present.

    :param result: result to inspect
    :return: formatted output message
    """
    if 'reason' in result:
        return 'Parsing the playbook failed:\n{}'.format(result['reason'])

    return ''
