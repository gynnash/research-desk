"""Process-scoped Git authentication; no network or member requests."""

from pathlib import Path
import subprocess
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import writing_member as writing


class WritingRemoteRefresh(unittest.TestCase):
    def test_actions_uses_ephemeral_read_token_and_never_stores_it_in_arguments(self):
        environment = {'GITHUB_ACTIONS': 'true', 'GH_TOKEN': 'isolated-test-token'}
        with mock.patch.dict('os.environ', environment, clear=True), mock.patch.object(
                writing.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, stderr=b'')) as run:
            self.assertTrue(writing.refresh_origin(Path('/workbench')))
        command = run.call_args.args[0]
        self.assertIn('credential.helper=', command)
        self.assertIn('credential.helper=!gh auth git-credential', command)
        self.assertIn('url.https://github.com/.insteadOf=git@github.com:', command)
        self.assertNotIn(environment['GH_TOKEN'], ' '.join(command))
        self.assertEqual(run.call_args.kwargs['env']['GH_TOKEN'], environment['GH_TOKEN'])
        self.assertEqual(run.call_args.kwargs['env']['GIT_TERMINAL_PROMPT'], '0')
        self.assertEqual(command[-4:], ['fetch', '--quiet', 'origin', 'main'])

    def test_actions_missing_read_token_stops_without_falling_back_to_keychain(self):
        with mock.patch.dict('os.environ', {'GITHUB_ACTIONS': 'true'}, clear=True), mock.patch.object(
                writing.subprocess, 'run') as run:
            with self.assertRaises(writing.WritingRefreshError) as caught:
                writing.refresh_origin(Path('/workbench'))
            self.assertEqual(caught.exception.code, 'writing_remote_read_token_missing')
            run.assert_not_called()

    def test_failure_categories_never_include_git_provider_text(self):
        for detail, expected in ((b'Authentication failed for private-token-url', 'writing_remote_auth_failed'),
                                 (b'SSL connection failed private-proxy-value', 'writing_remote_network_failed')):
            with self.subTest(expected=expected), mock.patch.dict('os.environ', {}, clear=True), mock.patch.object(
                    writing.subprocess, 'run', return_value=subprocess.CompletedProcess([], 128, stderr=detail)):
                with self.assertRaises(writing.WritingRefreshError) as caught:
                    writing.refresh_origin(Path('/workbench'))
                self.assertEqual(str(caught.exception), expected)


if __name__ == '__main__':
    unittest.main()
