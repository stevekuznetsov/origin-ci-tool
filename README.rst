##############
origin-ci-tool
##############

A CLI tool for building, testing and composing OpenShift repositories.

********
Overview
********

The ``origin-ci-tool`` allows for developers to provision virtual machine environments locally using a hypervisor on the
development host and remotely in a cloud computing environment. These environments contain all of the major source code
repositories for the OpenShift ecosystem and can be configured to check out these repositories in whatever state necessary.
Release artifacts can be built from all of these repositories in concert and used to start an OpenShift cluster.

This tool is a successor to `the OpenShift Vagrant plugin <https://github.com/openshift/vagrant-openshift>`_ and is intended to
support a superset of use-cases. Consult the `Sample Use-Cases`_ section to see some examples of specific workflows that are
supported.

Prospective contributors should read the `Contributing`_ section to determine the best way to extend the functionality of this
tool for their needs.

.. contents:: Table of Contents
    :backlinks: entry

************
Installation
************

Prerequisites
=============

This project requires Python 2.7 and the ``pip`` package manager for installation. On RHEL, CentOS and Fedora, install them with:

.. code-block:: shell

    $ sudo yum install python2 python-pip

On Mac OS, the preferred method uses `Homebrew <http://brew.sh/>`_. Installation instructions for Homebrew are on `their
website <https://github.com/Homebrew/brew/blob/master/docs/Installation.md#installation>`_. Using Homebrew, install Python (
``brew`` will automatically install ``pip``) with:

.. code-block:: shell

    $ brew install python

Core Installation
=================

Today, full functionality of this tool requires a development version of Ansible to benefit from the following patches:

1. `New ec2_group_facts module to be able to get facts from EC2 security groups <https://github.com/ansible/ansible-modules-extras/pull/2591>`_
2. `Factored polling std{out,err} reads into a function <https://github.com/ansible/ansible/pull/19298>`_
3. `Add support to the make module for targets with options <https://github.com/ansible/ansible/pull/18848>`_
4. `ec2_group_facts: Fail correctly when boto3 is not installed  <https://github.com/ansible/ansible/pull/18842>`_
5. `Only read EC2 regions_exclude list if necessary <https://github.com/ansible/ansible/pull/18720>`_

Due to this requirement, it is highly suggested that you install this tool inside of a virtual environment for Python as the
installation requires source checkouts of Ansible and this tool. To create the virtual environment, the ``virtualenv`` package
will be necessary. Install it with:

.. code-block:: shell

    $ sudo pip install virtualenv

Now, create a virtual environment. In the following examples, the environment is named and created in a directory ``venv``. On
Linux systems, you will want to allow the virtual environment to access system site packages, as running Ansible against the
local host requires Python bindings for ``yum`` and ``dnf``, which cannot be installed in the virtual environment:

.. code-block:: shell

    $ virtualenv venv --system-site-packages

On Mac OS, the virtual environment can be created without this option:

.. code-block:: shell

    $ virtualenv venv

Activate the virtual environment:

.. code-block:: shell

    $ source ./venv/bin/activate

Install Ansible and the ``origin-ci-tool`` in the virtual environment:

.. code-block:: shell

    $ pip install git+https://github.com/openshift/origin-ci-tool.git --process-dependency-links

You are now ready to use the ``oct`` CLI tool. If you want to use this virtual environment and get access to ``oct`` every time
you open a shell, add the activate line to your ``~/.bashrc``:

.. code-block:: shell

    $ echo "source '$( pwd )/venv/bin/activate'" >> ~/.bashrc

If you want to exit the virtual environment in a shell, use the ``deactivate`` function:

.. code-block:: shell

    $ deactivate

On Mac OS, the Python bindings for the AWS API are also necessary:

.. code-block:: shell

    $ pip install boto boto3

On Linux, some system dependencies are furthermore necessary. Install them using:

.. code-block:: shell

    $ oct bootstrap self

.. _image_prerequisites:

If you wish to develop and package VM images, further dependencies are required and can be installed with:

.. code-block:: shell

    $ oct bootstrap self --for-images

*************
Configuration
*************

The ``origin-ci-tool`` will place a directory of configuration files and runtime metadata to persist state between CLI
invocations. By default, this will be placed under ``~/.config`` but can be configured to be under a custom directory by setting
the ``${OCT_CONFIG_HOME}`` environment variable. Remember to add the ``${OCT_CONFIG_HOME}`` environment variable to your
``~/.bashrc`` if you are using a custom setting.

In general, configuration options for the ``origin-ci-tool`` can be accessed and changed with the following invocation, where
``COMPONENT`` is a semantic grouping of configuration options like ``aws-client`` or ``ansible-defaults`` and ``KEY`` and
``VALUE`` are the key-value pair to configure:

.. code-block:: shell

    $ oct configure COMPONENT KEY VALUE

Configuration for a component can be reviewed with:

.. code-block:: shell

    $ oct configure COMPONENT --view

AWS Credentials and Configuration
=================================

Communicating with the AWS API to provision virtual machines in EC2 requires a set of credentials. The ``origin-ci-tool`` uses
the same credential store as the AWS CLI. Detailed instructions for configuring the credential file are at the `AWS User Guide
<http://docs.aws.amazon.com/cli/latest/userguide/cli-chap-getting-started.html>`_, but the general flow is simple. If you have
the AWS CLI installed, simply run:

.. code-block:: shell

    $ aws configure

If not, you'll want to place a file at ``~/.aws/credentials`` with the following content:

.. code-block:: cfg

    [default]                  #<1>
    aws_access_key_id=XXXXXXXX #<2>
    aws_secret_access_key=XXXX #<3>

1. The name of the AWS credential profile. If this is not set to ``default``, ``${AWS_PROFILE}`` will need to be set to choose the
   correct profile to use.
2. The AWS secret access key ID. Consult the `AWS documentation <http://docs.aws.amazon.com/general/latest/gr/aws-sec-cred-types.html#access-keys-and-secret-access-keys>`_
   for more details.
3. The AWS secret access key. Consult the `AWS documentation <http://docs.aws.amazon.com/general/latest/gr/aws-sec-cred-types.html#access-keys-and-secret-access-keys>`_
   for more details.

When setting up the SSH configuration for virtual machines provisioned in AWS EC2, the name and location of the private key used
to reach the instance need to be known by the ``origin-ci-tool``. Configure them with:

.. code-block:: shell

    $ oct configure aws-client keypair_name KEY_NAME
    $ oct configure aws-client private_key_path /path/to/KEY_NAME.pem

Complex AWS Configuration
-------------------------

The region in which to provision the cluster can be configured with:

.. code-block:: shell

    $ oct configure aws-defaults region REGION_NAME

The instance type to use for a master can be configured with:

.. code-block:: shell

    $ oct configure aws-defaults master_instance_type TYPE

When provisioning in AWS EC2, a number of high-level objects like virtual private clouds, subnets, security groups and elastic
load-balancers are necessary. By default, the ``origin-ci-tool`` does not create these objects when provisioning instances in EC2
to reduce the minimum permission level necessary to provision a cluster. Instead, objects of the correct type that are visible
are used if they have the correct tag. By default, the ``origin_ci_aws_cluster_component`` tag is used, but this can be changed
with:

.. code-block:: shell

    $ oct configure aws-defaults identifying_tag_key KEY_NAME

The acceptable value for this identifying tag for each component can also be configured. For instance, the default value for a
subnet that can be used as a master subnet is ``master_subnet``. This configuration can be changed with:

.. code-block:: shell

    $ oct configure aws-defaults master_subnet_tag_value KEY_VALUE

Instead of determining the correct cluster component by searching through tags, it is possible to provide a comma-delimited list
of literal identifiers to use:

.. code-block:: shell

    $ oct configure aws-defaults master_subnet_ids subnet-XXXXXXXX,subnet-XXXXXXXX,subnet-XXXXXXXX

****************
Sample Use-Cases
****************

Provisioning an OpenShift Origin All-in-One Locally
===================================================

When provisioning a local All-in-One VM, make sure that your local environment has the storage, CPU and memory required to
support the VM, then run:

.. code-block:: shell

    $ oct provision local all-in-one --os OS         \ #<1>
                                     --provider NAME \ #<2>
                                     --stage STAGE     #<3>

1. Select the operating system you would like to use with ``--os``. Fedora and CentOS are supported.
2. Choose the virtualization provider to use. LibVirt, VirtualBox and VMWare Fusion are supported.
3. Determine the image stage to base the virtual machine on. Valid image stages are ``bare``, ``base`` and ``install``. Only the
   bare OS stage is supported for VMWare Fusion.

By default, about five gigabytes of storage are necessary to start the machine; six gigabytes of RAM and two CPUs are
made available to the virtual machine. Fewer resources can be provided to the machine by providing the ``--memory`` and/or
``--cpus`` flags to ``oct provision local all-in-one``, but this is not recommended for workflows that compile the Origin
repository.

+---------+----------------------------------------------------------------------------------------------------------------+
| Warning | The implementation of user-configured virtual machine memory and CPU limits is not complete. The above section |
|         | will be relevant once issue `#31 <https://github.com/stevekuznetsov/origin-ci-tool/issues/31>`_ is finished.   |
+---------+----------------------------------------------------------------------------------------------------------------+

To access the machine, use SSH:

.. code-block:: shell

    $ ssh openshiftdevel

To remove the VM, use:

.. code-block:: shell

    $ oct deprovision

Provisioning an OpenShift Origin All-in-One in the Cloud
========================================================

+------+---------------------------------------------------------------------------------------+
| Note | Configure your `AWS Credentials and Configuration` before trying the following steps. |
+------+---------------------------------------------------------------------------------------+

To provision an All-in-One VM in the cloud, run:

.. code-block:: shell

    $ oct provision remote all-in-one --os OS         \ #<1>
                                      --provider NAME \ #<2>
                                      --stage STAGE   \ #<3>
                                      --name VM-NAME    #<4>

1. Select the operating system you would like to use with ``--os``. Fedora, CentOS and RHEL are supported.
2. Choose the cloud provider to use. Only AWS is supported.
3. Determine the image stage to base the virtual machine on. Valid image stages are ``bare``, ``base`` and ``install``.
4. Provide the identifier to use when naming the virtual machine on the cloud platform.

To access the machine, use SSH:

.. code-block:: shell

    $ ssh openshiftdevel

To remove the VM, use:

.. code-block:: shell

    $ oct deprovision

Provisioning an OpenShift Origin Cluster
========================================

+------+---------------------------------------------------------------------------------------+
| Note | Configure your `AWS Credentials and Configuration` before trying the following steps. |
+------+---------------------------------------------------------------------------------------+

Only certain configurations of clusters are available for provisioning using the ``origin-ci-tool``. If a more fine-tuned setup
is necessary, direct interfacing with the OpenShift Ansible AWS `reference architecture
<https://github.com/openshift/openshift-ansible-contrib/tree/master/reference-architecture/aws-ansible>`_ and/or `provisioner
<https://github.com/openshift/openshift-ansible-contrib/tree/master/playbooks/provisioning/aws>`_ is necessary.

To provision an OpenShift cluster, use:

.. code-block:: shell

    $ oct provision remote cluster

+---------+----------------------------------------------------------------------------------------------------------+
| Warning | The implementation of the full cluster provisioning logic is not complete. The above section will be     |
|         | relevant once issue `#41 <https://github.com/openshift/openshift-ansible-contrib/pull/41>`_ is finished. |
+---------+----------------------------------------------------------------------------------------------------------+

Running Tests On Updated Code
=============================

First, follow the steps in `Provisioning an OpenShift Origin All-in-One Locally` or `Provisioning an OpenShift Origin
All-in-One in the Cloud`. Then, make changes to a local checkout of a repository supported in the VM. For this example, we will
use the ``origin`` repository.

.. code-block:: shell

    $ cd "${GOPATH}"/src/github.com/openshift/origin
    # make some changes, optionally stage and/or commit them
    $ oct sync local origin --branch BRANCH                 #<1>
    $ oct make origin test-unit --env WHAT=pkg/changed/path #<2>

1. Sync the state of the repository on the local host to the remote host. Changes will be synced regardless of whether they are
   staged or committed. On the remote, a branch will be made with the same name and state as your local checkout.
2. Interact with the repository on the remote host in some way.

Rebuilding The Ecosystem From Updated Code
==========================================

First, set up a virtual machine and make some changes as described in `Running Tests on Updated Code`. Then, run:

.. code-block:: shell

    $ oct build origin --follow-dependencies #<1>
    $ oct install origin                     #<2>

1. Re-build the ``origin`` repository and use the build artifacts (RPMs, binaries, container images) to re-build any other
   repositories that are downstream consumers of those artifacts.
2. Use the new artifacts to re-install the OpenShift Origin instance. If you need to re-install other downstream projects, use
   separate ``oct install`` directives.

Creating a VM Image
===================

Packaging Local Images
----------------------

+------+-----------------------------------------------------------------------+
| Note | If packaging local virtual machine images, `install the required      |
|      | dependencies image_prerequisites_` before trying the following steps. |
+------+-----------------------------------------------------------------------+

To package a local virtual machine into a re-useable image, use:

.. code-block:: shell

    $ oct package vagrant --update            \ #<1>
                          --bump-version TYPE \ #<2>
                          --serve-local         #<3>

1. Update the current image stage, or ``--upgrade`` to create an image for the next stage.
2. Strategy for updating the Vagrant box semantic version, can be ``major``, ``minor``, ``patch`` or ``none``.
3. Configure the Vagrant box to pull the new image from it's location on disk, or ``--serve-remote`` to write the URL under
   the `OpenShift mirror <https://mirror.openshift.com/pub/vagrant/boxes/openshift3/>`_.

+---------+-----------------------------------------------------------------------------------------------------------+
| Warning | The implementation of provisioning from a local image source file is not complete. The above section will |
|         | be relevant once issue `#30 <https://github.com/stevekuznetsov/origin-ci-tool/issues/30>`_ is finished.   |
+---------+-----------------------------------------------------------------------------------------------------------+

Packaging Cloud Images
----------------------

+------+---------------------------------------------------------------------------------------+
| Note | Configure your `AWS Credentials and Configuration` before trying the following steps. |
+------+---------------------------------------------------------------------------------------+

+------+---------------------------------------------------------------+
| Note | Packaging images from virtual machines in the cloud is only   |
|      | supported when there is only one virtual machine provisioned. |
+------+---------------------------------------------------------------+

To package a remote virtual machine into a re-useable image, use:


.. code-block:: shell

    $ oct package ami --update #<1>

1. Update the current image stage, or ``--upgrade`` to create an image for the next stage.

When a new image is created for the ``bare`` or ``base`` image stages, it is not known if the image will support the full
OpenShift build and install. Therefore, it is possible to execute whatever build, installation or test actions are necessary on
the virtual machine, then use the following command to mark the image previously created from the virtual machine as ready for
consumption:

.. code-block:: shell

    $ oct package ami --mark-ready

This action will change the ``ready`` tag value from ``no`` to ``yes`` on the remote image.

************
Contributing
************

Design Principles
=================

The core design principle behind the ``origin-ci-tool`` is that it should contain the smallest amount of logic possible. The
largest lesson learned from the `Vagrant plugin for OpenShift <https://github.com/openshift/vagrant-openshift>`_ was that
internalizing repository-specific logic led to a bloated code-base that could neither support all of the use-cases that the
repositories wanted nor could be update quickly when repositories needed changes in behavior. For this reason, *all* of the
interaction that the ``origin-ci-tool`` has with repositories is through ``make`` targets. This allows the ``origin-ci-tool``
to provide a low-level ``oct make REPO TARGET`` command that can be utilized to support whatever custom workflow any repository
needs.

A second but nonetheless critical design principle is `dog-food <https://en.wikipedia.org/wiki/Eating_your_own_dog_food>`_. In
the past, a large proliferation of provisioning, installation and configuration solutions was created by members of the
OpenShift community because no simple central utilities existed. The `OpenShift Productization team
<https://trello.com/b/wJYDst6C/productization>`_ now supports a full-featured installation and configuration path using Ansible
in their `OpenShift Ansible <https://github.com/openshift/openshift-ansible>`_ repository. Reference architectures and
implementations of provisioning solutions exist in the `OpenShift Ansible contributions
<https://github.com/openshift/openshift-ansible-contrib>`_ repository. The ``origin-ci-tool`` utilizes these tools to ensure that we
eat our own dog-food.

When adding to this project, therefore, it is necessary to ask:
 - is this change adding repository-specific business logic to the ``origin-ci-tool``?
 - should this change instead be contributed to an upstream solution for the OpenShift community to share?


Integration With New Repositories
=================================

It is not certain that the ``origin-ci-tool`` can support any repository generically, so integrating with a new repository
requires changes to the codebase. New repositories need to be added to the ``Repository`` enumeration in
``cli/util/repository_options.py``:

.. code-block:: python

    class Repository(object):
        """
        An enumeration of repository names that are currently
        supported as a part of the OpenShift ecosystem.
        """

As the ``origin-ci-tool`` interacts with repositories using ``make``, your repository will need a ``Makefile`` in the repository
root with whatever targets are necessary. If you wish for the ``origin-ci-tool`` to support helpful commands like ``oct
build``, ``oct install``, ``oct test``, and/or ``oct download``, you will need to place a ``.oct-config.yml`` file in your
repository root. The file as described below contains four lists in normal `YAML syntax <http://www.yaml.org/start.html>`_. The
``build``, ``install``, and ``test`` entries list ``make`` targets. The ``download`` list contains directories or files that the
``origin-ci-tool`` will download from a remote host.

.. code-block:: yml

    ---
    build: <1>
      - build-release <2>
          ENVAR: value <3>
    install: <4>
      - install-onto-cluster
    test: <5>
      - test -o build-release <6>
    download: <7>
      - /tmp/myrepo

1. If present, this list of ``make`` targets will be called when a user invokes ``oct build REPO``.
2. A ``make`` target can be presented in-line.
3. Options for the ``make`` target are provided as key-value pairs, descendant from the target entry.
4. If present, this list of ``make`` targets will be called when a user invokes ``oct install REPO``.
5. If present, this list of ``make`` targets will be called when a user invokes ``oct test REPO``.
6. Complicated ``make`` invocations can be provided for the target.
7. If present, this list of absolute paths will be downloaded from the remote host when a user invokes ``oct download
   REPO-artifacts``

+---------+----------------------------------------------------------------------------------------------------------+
| Warning | The implementation of the ``.oct-config.yml`` configuration file is not complete. The above section will |
|         | be relevant once issue `#29 <https://github.com/stevekuznetsov/origin-ci-tool/issues/29>`_ is finished.  |
+---------+----------------------------------------------------------------------------------------------------------+

Running Tests
=============

The main means by which automated tests verify that the ``origin-ci-tool`` functions is by ensuring that a specific CLI
invocation results in the correct Ansible playbook being called with the correct variables. In order to run the unit tests,
install the test-specific dependencies first. To get the dependencies and a version of ``oct`` that tracks the source, run the
following command from the ``origin-ci-tool`` source directory:

.. code-block:: shell

    $ pip install --editable .[development] --process-dependency-links

All of the unit tests can be run with:

.. code-block:: shell

    $ coverage run -m unittest discover --verbose

The code coverage report can be seen with:

.. code-block:: shell

    $ coverage report -m
    $ open htmlcov/index.html