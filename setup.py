# coding=utf-8
from setuptools import find_packages, setup

base_requires = [
    'Click',
    'ansible==3.0.0',
    'backports.shutil_get_terminal_size',
    'semver',
    'junit_xml',
    'structlog'
]

test_requires = base_requires + [
    'mock',
    'coverage',
    'pep8',
    'yapf==0.14.0'
]

setup(
    name='origin-ci-tool',
    version='0.1.0',
    url='https://www.github.com/openshift/origin-ci-tool',
    maintainer='Steve Kuznetsov',
    maintainer_email='skuznets@redhat.com',
    packages=find_packages(exclude=['tests']),
    include_package_data=True,
    dependency_links=[
        'git+https://github.com/stevekuznetsov/ansible.git@skuznets/oct-release#egg=ansible-3.0.0'
    ],
    install_requires=base_requires,
    tests_require=test_requires,
    extras_require={
        'development': test_requires
    },
    entry_points='''
        [console_scripts]
        oct=oct.oct:oct_command
    ''',
)
