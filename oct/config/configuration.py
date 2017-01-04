# coding=utf-8
from __future__ import absolute_import, division, print_function

from atexit import register

from os import getenv, listdir, makedirs, mkdir
from os.path import abspath, exists, expanduser, isdir, join
from yaml import dump, load

from ..config.ansible_client import AnsibleCoreClient
from ..config.aws_client import AWSClientConfiguration
from ..config.aws_variables import AWSVariables
from ..config.vagrant import VagrantVMMetadata
from ..config.variables import PlaybookExtraVariables
from ..util.playbook import playbook_path

DEFAULT_HOSTNAME = 'openshiftdevel'

_ANSIBLE_CLIENT_CONFIGURATION_FILE = 'ansible_client_configuration.yml'
_ANSIBLE_VARIABLES_FILE = 'ansible_variables.yml'
_ANSIBLE_INVENTORY_DIRECTORY = 'inventory'
_VAGRANT_ROOT_DIRECTORY = 'vagrant'
_VAGRANT_BOX_DIRECTORY = 'boxes'
_LOG_DIRECTORY = 'logs'
_AWS_CLIENT_CONFIGURATION_FILE = 'aws_client_configuration.yml'
_AWS_VARIABLES_FILE = 'aws_variables.yml'


def load_configuration(class_type, path, *init_args, **init_kwargs):
    """
    Load a configuration object, first attempting to do so from
    a path and falling back to creating a default instance. This
    function will furthermore register a serialization of the
    object on process exit, ensuring we always leave the file-
    system with the most up-to-date version of the data.

    :param class_type: class of the object to load
    :param path: path to attempt to load from
    :param init_args: optional arguments to __init__()
    :param init_kwargs: optional arguments to __init__()
    :return: the loaded or defaulted instance of the class
    """
    if not exists(path):
        loaded_object = class_type(*init_args, **init_kwargs)
    else:
        with open(path) as configuration_file:
            loaded_object = load(configuration_file)

    # ensure that the object is saved on process exit
    register(
        save_configuration,
        loaded_object,
        path
    )

    return loaded_object


def save_configuration(data, path):
    """
    Save a configuration object to disk.

    :param data: configuration object to save
    :param path: where to save the object
    """
    makedirs(path, exist_ok=True)
    with open(path, 'w+') as configuration_file:
        dump(
            data,
            configuration_file,
            default_flow_style=False,
            explicit_start=True
        )


class Configuration(object):
    """
    This container holds all of the state that this tool needs
    to persist between CLI invocations. Default values allow
    for playbooks to be run with a minimal amount of specification.
    `run_playbook()` acts as a minimal client for the Ansible API.
    """

    def __init__(self):
        # Configuration will be placed in the user-based conf-
        # iguration path, preferring an explicit directory and
        # otherwise using $HOME.
        base_dir = getenv('OCT_CONFIG_HOME', abspath(join(expanduser('~'), '.config')))

        # path to the local configuration directory
        self._path = abspath(join(base_dir, 'origin-ci-tool'))

        # configuration options for Ansible core
        self.ansible_client_configuration = load_configuration(
            AnsibleCoreClient,
            self.ansible_client_configuration_path,
            inventory_dir=self.ansible_inventory_path,
            log_directory=self.ansible_log_path
        )

        # extra variables we want to send to Ansible playbooks
        self.ansible_variables = load_configuration(
            PlaybookExtraVariables,
            self.variables_path
        )

        # metadata about active Vagrant local VMs
        self._vagrant_metadata = self.load_vagrant_metadata()

        # configuration options for AWS client
        self.aws_client_configuration = load_configuration(
            AWSClientConfiguration,
            self.aws_client_configuration_path
        )

        # extra variables we want to send to Ansible playbooks
        # that touch the AWS API
        self.aws_variables = load_configuration(
            AWSVariables,
            self.aws_variables_path
        )

    def run_playbook(self, playbook_relative_path, playbook_variables=None, option_overrides=None):
        """
        Run a playbook from file with the variables provided. The
        playbook file should be specified as a relative path from
        the root of the internal Ansible playbook directory, with
        the YAML suffix omitted, e.g. `prepare/main`

        :param playbook_relative_path: the location of the playbook
        :param playbook_variables: extra variables for the playbook
        """
        playbook_variables = self.ansible_variables.default(
            self.aws_variables.default(playbook_variables)
        )

        self.ansible_client_configuration.run_playbook(
            playbook_file=playbook_path(playbook_relative_path),
            playbook_variables=playbook_variables,
            option_overrides=option_overrides
        )

    @property
    def ansible_inventory_path(self):
        """
        Yield the path to the Ansible core inventory directory.
        :return: absolute path to the Ansible core inventory directory
        """
        return join(self._path, _ANSIBLE_INVENTORY_DIRECTORY)

    @property
    def ansible_client_configuration_path(self):
        """
        Yield the path to the Ansible core configuration file.
        :return: absolute path to the Ansible core configuration
        """
        return join(self._path, _ANSIBLE_CLIENT_CONFIGURATION_FILE)

    @property
    def variables_path(self):
        """
        Yield the path to the Ansible playbook extra variables file.
        :return: absolute path to the Ansible playbook extra variables
        """
        return join(self._path, _ANSIBLE_VARIABLES_FILE)

    @property
    def vagrant_directory_root(self):
        """
        Yield the root path for Vagrant VM locations.
        :return: absolute path to Vagrant VM containers directory
        """
        return join(self._path, _VAGRANT_ROOT_DIRECTORY)

    @property
    def vagrant_box_directory(self):
        """
        Yield the path for Vagrant box files and metadata.
        :return: absolute path to Vagrant VM boxes directory
        """
        return join(self.vagrant_directory_root, _VAGRANT_BOX_DIRECTORY)

    def vagrant_home_directory(self, name):
        """
        Yield the path to the specific storage directory
        for the VM `boxname'.

        :param name: name of the VM
        :return: absolute path to the Vagrant VM directory
        """
        return join(self.vagrant_directory_root, name)

    @property
    def next_available_vagrant_name(self):
        """
        Yield the next available hostname for a local Vagrant
        VM.

        :return: the next hostname
        """
        if not self._vagrant_hostname_taken(DEFAULT_HOSTNAME):
            return DEFAULT_HOSTNAME

        for i in range(len(listdir(self.vagrant_directory_root)) + 1):
            possible_hostname = DEFAULT_HOSTNAME + str(i)
            if not self._vagrant_hostname_taken(possible_hostname):
                return possible_hostname

    def _vagrant_hostname_taken(self, name):
        """
        Determine if a Vagrant VM with the given hostname exists.

        :param name: hostname of the VM
        :return: whether or not the VM exists
        """
        # we know all of our Vagrant VMs must reside in top-
        # level subdirectories of the Vagrant directory root,
        # so we can do this simple exists check
        return isdir(join(self.vagrant_directory_root, name))

    def load_vagrant_metadata(self):
        """
        Load metadata for the Vagrant virtual machines
        that we have provisioned with this tool.
        """
        metadata = []
        if not exists(self.vagrant_directory_root):
            mkdir(self.vagrant_directory_root)
        else:
            for content in listdir(self.vagrant_directory_root):
                variables_file = join(self.vagrant_directory_root, content, 'variables.yml')
                groups_file = join(self.vagrant_directory_root, content, 'groups.yml')
                if exists(variables_file):
                    metadata.append(VagrantVMMetadata(variable_file=variables_file, group_file=groups_file))

        return metadata

    def registered_vagrant_machines(self):
        """
        Yield the list of Vagrant machine metadata.
        :return: the Vagrant metadata
        """
        return self._vagrant_metadata

    @property
    def ansible_log_path(self):
        """
        Yield the root path for Ansible log files.
        :return: absolute path to Ansible logging directory
        """
        return join(self._path, _LOG_DIRECTORY)

    @property
    def aws_client_configuration_path(self):
        """
        Yield the path to the AWS client configuration file.
        :return: absolute path to the AWS client configuration
        """
        return join(self._path, _AWS_CLIENT_CONFIGURATION_FILE)

    @property
    def aws_variables_path(self):
        """
        Yield the path to the AWS client configuration file.
        :return: absolute path to the AWS client configuration
        """
        return join(self._path, _AWS_VARIABLES_FILE)
