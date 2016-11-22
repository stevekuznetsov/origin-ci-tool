# coding=utf-8
from __future__ import absolute_import, division, print_function

from click import ClickException, command, pass_context

from ..util.common_options import ansible_output_options
from ..util.repository_options import Repository, repository_argument


@command(
    short_help='Install and configure systems from binaries and artifacts.'
)
@repository_argument
@ansible_output_options
@pass_context
def install(context, repository):
    """
    Install the binaries or other artifacts necessary for
    the given repository on the remote host.

    :param context: Click context
    :param repository: name of the repository to use
    """
    ansible_client = context.obj
    if repository == Repository.origin:
        install_origin(ansible_client)
    elif repository == Repository.enterprise:
        install_enterprise(ansible_client)
    elif repository == Repository.logging:
        install_logging(ansible_client)
    elif repository == Repository.metrics:
        install_metrics(ansible_client)
    elif repository == Repository.source_to_image:
        install_source_to_image(ansible_client)
    elif repository == Repository.web_console:
        install_web_console(ansible_client)


def install_origin(ansible_client):
    """
    Install OpenShift Origin from RPMs.

    :param ansible_client: Ansible client
    """
    install_openshift(ansible_client, 'origin')


def install_enterprise(ansible_client):
    """
    Install OpenShift Container Platform from RPMs.

    :param ansible_client: Ansible client
    """
    install_openshift(ansible_client, 'enterprise')


def install_openshift(ansible_client, deployment_type):
    """
    Install OpenShift from RPMs.

    :param ansible_client: Ansible client
    """
    ansible_client.run_playbook(
        playbook_relative_path='byo/openshift-node/network_manager',
        playbook_variables={
            'ansible_become_user': 'root'
        },
        option_overrides={
            'become': True
        }
    )
    ansible_client.run_playbook(
        playbook_relative_path='byo/config',
        playbook_variables={
            'ansible_become_user': 'root',
            'deployment_type': deployment_type
        },
        option_overrides={
            'become': True
        }
    )


def install_logging(ansible_client):
    """
    Install OpenShift Aggregated Logging onto a cluster.
    Today, we don't install logging as part of the BYO
    playbook for OpenShift. In the future, we will be able
    to do this as a discrete step on top of that.

    :param ansible_client: Ansible client
    """
    domain = '{}.xip.io'.format(get_master_ip(ansible_client.registered_vagrant_machines()))
    ansible_client.run_playbook(
        playbook_relative_path='byo/config',
        playbook_variables={
            'ansible_become_user': 'root',
            'deployment_type': 'origin',
            'openshift_master_default_subdomain': domain,
            'openshift_hosted_logging_deploy': True,
        },
        option_overrides={
            'become': True
        }
    )


def install_metrics(ansible_client):
    """
    Install OpenShift Metrics onto a cluster. Today, we
    don't install logging as part of the BYO playbook for
    OpenShift. In the future, we will be able to do this
    as a discrete step on top of that.

    :param ansible_client: Ansible client
    """
    domain = '{}.xip.io'.format(get_master_ip(ansible_client.registered_vagrant_machines()))
    ansible_client.run_playbook(
        playbook_relative_path='byo/config',
        playbook_variables={
            'ansible_become_user': 'root',
            'deployment_type': 'origin',
            'openshift_master_default_subdomain': domain,
            'openshift_hosted_metrics_deploy': True,
        },
        option_overrides={
            'become': True
        }
    )


def get_master_ip(hosts):
    for host in hosts:
        if 'masters' in host.groups:
            return host.host

    raise ClickException('No master host found, could not determine cluster domain!')


def install_source_to_image(ansible_client):
    """
    Install the Source-to-Image tools. These tools do not
    need to be installed on the OpenShift cluster, as the
    OpenShift repository vendors s2i. There is therefore
    no install process for s2i.

    :param ansible_client: Ansible client
    """
    pass


def install_web_console(ansible_client):
    """
    Install the Web Console onto a cluster. Today, the
    console is vendored into the OpenShift repository,
    so there is no need to install the console onto a
    cluster.

    :param ansible_client:
    """
    # TODO: When the console is broken out into a pod,
    #       install the infra pod onto the cluster
    pass
