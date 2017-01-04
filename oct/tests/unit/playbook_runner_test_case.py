# coding=utf-8
from __future__ import absolute_import, division, print_function

from traceback import format_exception
from unittest import TestCase

from click.testing import CliRunner
from mock import patch
from os import environ

import oct.config.configuration as configuration_module
from oct.config.configuration import Configuration
from oct.oct import oct_command
from oct.tests.unit.formatting_util import format_assertion_failure, format_expectation

# Allow for run-time triggering of stack trace output
show_stack_trace = 'SHOW_STACK_TRACE' in environ
if not show_stack_trace:
    __unittest = True

# Click does not expose these exit codes, so we need to define them
CLICK_RC_OK = 0
CLICK_RC_EXCEPTION = 1
CLICK_RC_USAGE = 2

DUMMY_INVENTORY_DIR = 'dummy-inventory-dir'


class TestCaseParameters(object):
    def __init__(self, args, expected_result=CLICK_RC_OK, expected_calls=None, expected_output=None):
        """
        Parameterize a Click playbook test case.

        :param args: command-line arguments to Click
        :param expected_result: expected exit code of the command-line invocation
        :param expected_calls: expected calls to PlaybookRunner.run()
        :param expected_output: phrase expected to be in the command line output
        """
        self.args = args
        self.expected_result = expected_result
        self.expected_output = expected_output
        self.expected_calls = expected_calls


class PlaybookRunnerTestCase(TestCase):
    """
    Set up a common test case that validates correct
    interaction with the Ansible playbook API.
    """

    def setUp(self):
        """
        Mock out the `run_playbook()` method on the Config
        so that we can validate that it is called correctly.

        Mock out the filesystem methods on Configuration
        so we don't touch disk in our tests.
        """
        self._call_metadata = []
        patches = [
            patch.object(
                target=Configuration,
                attribute='run_playbook',
                new=lambda _, playbook_relative_path, playbook_variables=None:
                self._call_metadata.append({
                    'playbook_relative_path': playbook_relative_path,
                    'playbook_variables': playbook_variables
                })
            ),
            patch.object(
                target=Configuration,
                attribute='load_vagrant_metadata',
                new=lambda _: []
            ),
            patch.object(
                target=configuration_module,
                attribute='load_configuration',
                new=lambda class_type, _, *init_args, **init_kwargs: class_type(*init_args, **init_kwargs)
            )
        ]
        for patcher in patches:
            patcher.start()
            self.addCleanup(patcher.stop)

    def run_test(self, parameters):
        """
        Run a Click PlaybookRunner test case.

        :param parameters: a TestCaseParameters instance
        """
        result = CliRunner().invoke(cli=oct_command, args=parameters.args)
        extra = 'Full output:\n{}'.format(result.output)
        if result.exception is not None:
            extra = ''.join(format_exception(*result.exc_info))
        self.assertEqual(
            parameters.expected_result,
            result.exit_code,
            format_assertion_failure(
                message='Command did not exit with correct code.',
                expectation=(parameters.expected_result, result.exit_code),
                extra=extra
            )
        )
        self.validate_call_metadata(parameters.expected_calls)
        if parameters.expected_output is not None:
            self.assertIn(
                parameters.expected_output,
                result.output,
                msg=format_assertion_failure(
                    message='Phrase `{}` not found in output.'.format(parameters.expected_output),
                    extra=extra
                )
            )

    def validate_call_metadata(self, expected_calls):
        """
        Validate that the metadata recorded by our mock
        matches what was expected for the test. If the
        expected data contains an `ansible_options` key,
        we will helpfully only check that the metadata
        we collected previously contains the options that
        the user specified, and ignore any they did not,
        to allow users to specify only the ones that they
        care about.

        :param expected_calls: expected call metadata
        """
        if expected_calls is None:
            expected_calls = []

        self._expected_calls = expected_calls

        self.make_equality_assertion(
            actual=len(self._call_metadata),
            expected=len(expected_calls),
            message='Invalid number of playbook calls.'
        )

        for i, (actual, expected) in enumerate(zip(self._call_metadata, expected_calls)):
            prefix = '[playbook {}]'.format(i)

            self.make_equality_assertion(
                actual=actual['playbook_relative_path'],
                expected=expected['playbook_relative_path'],
                message='{}: Invalid source.'.format(prefix)
            )

            self.make_equality_assertion(
                actual=actual['playbook_variables'],
                expected=expected['playbook_variables'],
                message='{}: Invalid variables.'.format(prefix)
            )

    def make_equality_assertion(self, actual, expected, message):
        """
        Make an assertion about equality, with a nice
        error message that is consistent between tests
        and gives full context to what is being tested.

        :param actual: object
        :param expected: object
        :param message: failure message
        """
        self.assertEqual(
            actual,
            expected,
            msg=format_assertion_failure(
                message=message,
                expectation=(actual, expected),
                extra='Full Call Metadata Context:\n{}'.format(
                    format_expectation(
                        self._call_metadata,
                        self._expected_calls
                    )
                )
            )
        )
