# coding=utf-8
"""
update_vagrant_metadata is an Ansible module that allows for
updates to a single provider section of a Vagrant metadata.json
file describing a box.
"""
from __future__ import absolute_import, division, print_function, unicode_literals

from ansible.module_utils.basic import AnsibleModule
from github import Github

DOCUMENTATION = '''
---
module: fetch_github_repos
short_description: Fetch the list of repositories for an organization
author: Steve Kuznetsov
options:
  org:
    description:
      - The organization for which to fetch repositories.
    required: true
requirements:
 - pygithub
'''

EXAMPLES = '''
# Fetch the list of repositories for the OpenShift organization
- fetch_github_repos:
    org: 'openshift'
  register: data

- debug:
    var: data.repositories
'''


def main():
    """
    Fetch the list of GitHub repositories for an organization.
    """
    module = AnsibleModule(
        supports_check_mode=False,
        argument_spec=dict(
            org=dict(
                required=True,
                default=None,
                type='str',
            ),
        ),
    )

    org = module.params['org']

    module.exit_json(
        changed=True,
        failed=False,
        repositories=[ repo.name for repo in Github().get_organization(org).get_repos() ],
    )