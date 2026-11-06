"""Verify activation ordering and local-only wizard actions without live services."""

from datetime import datetime, timezone
import http.client
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import researchdesk_setup as setup
import researchdesk_workbench as workbench


class SetupWizardTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='researchdesk-setup-test-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.wizard = setup.SetupWizard(self.root)
        self.chatgpt = mock.Mock()
        self.chatgpt.status.return_value = {'authenticated': True, 'plan_permission': True}
        self.chatgpt.models.return_value = [{'slug': 'available-generation'}, {'slug': 'available-review'}]
        self.wizard.client = mock.Mock(return_value=self.chatgpt)
        self.wizard.github = mock.Mock()
        self.wizard.github.status.return_value = {
            'state': 'ready', 'repository': 'fixture/workbench', 'private': True,
        }
        self.wizard.obsidian = mock.Mock()
        self.wizard.obsidian.status.return_value = {'state': 'ready'}
        self.start = mock.patch.object(workbench, 'start', return_value={'status': 'started'})
        self.start_runner = self.start.start()
        self.addCleanup(self.start.stop)
        platform = mock.patch.object(setup.platform, 'system', return_value='Darwin')
        platform.start()
        self.addCleanup(platform.stop)

    def test_activation_follows_both_authorizations_and_health(self):
        self.chatgpt.status.return_value['plan_permission'] = False
        self.wizard.github.status.return_value = {'state': 'needs_login'}
        self.wizard.perform('check')
        self.assertEqual(self.wizard.snapshot()['chatgpt']['state'], 'needs_login')
        self.start_runner.assert_not_called()

        self.chatgpt.status.return_value['plan_permission'] = True
        self.wizard.perform('chatgpt_login')
        self.start_runner.assert_not_called()
        self.wizard.github.status.return_value = {
            'state': 'ready', 'repository': 'fixture/workbench', 'private': True,
        }
        before = datetime.now(timezone.utc)

        def check_remote_health():
            self.start_runner.assert_called_once_with(self.root)
            self.wizard.github.prepare.assert_called_once()
            current = workbench.load_effective(self.root)
            self.assertFalse(current['automation']['enabled'])
            self.assertFalse(current['admission']['enabled'])
            self.assertNotEqual(current['research']['models']['research'], current['research']['models']['review'])

        self.wizard.github.health.side_effect = check_remote_health
        self.wizard.perform('github_login')

        current = workbench.load_effective(self.root)
        self.assertEqual(self.wizard.snapshot()['deployment']['state'], 'ready')
        self.assertTrue(current['automation']['enabled'])
        self.assertTrue(current['admission']['enabled'])
        self.assertGreaterEqual(setup.schedule.instant(current['automation']['activated_at']), before)
        self.wizard.obsidian.sync.assert_called_once()
        self.chatgpt.infer.assert_not_called()
        self.assertFalse((self.root / 'reports').exists())

    def test_failed_health_can_retry_without_enabling_schedule(self):
        self.wizard.github.health.side_effect = setup.GitHubSetupError('检查失败')
        self.wizard.perform('check')
        self.assertEqual(self.wizard.snapshot()['deployment']['state'], 'blocked')
        self.assertFalse(workbench.load_effective(self.root)['automation']['enabled'])
        self.wizard.obsidian.sync.assert_not_called()
        self.wizard.github.health.side_effect = None
        self.wizard.obsidian.sync.side_effect = setup.ObsidianSetupError('阅读库有本地改动')

        self.wizard.perform('deploy')

        self.assertEqual(self.wizard.snapshot()['deployment']['state'], 'ready')
        self.assertEqual(self.wizard.snapshot()['obsidian']['state'], 'blocked')
        self.assertTrue(workbench.load_effective(self.root)['automation']['enabled'])

    def test_public_repository_waits_for_explicit_deploy(self):
        self.wizard.github.status.return_value['private'] = False
        self.wizard.perform('check')
        self.start_runner.assert_not_called()
        self.assertEqual(self.wizard.snapshot()['deployment']['state'], 'needs_setup')

        self.wizard.perform('deploy')

        self.start_runner.assert_called_once_with(self.root)
        self.assertEqual(self.wizard.snapshot()['deployment']['state'], 'ready')


class SetupHttpTest(unittest.TestCase):
    def test_mutations_require_the_same_local_origin_and_session(self):
        wizard = mock.Mock()
        wizard.snapshot.return_value = {'operation': None}
        wizard.submit.return_value = True
        with setup.create_server(wizard) as server:
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=5)
                connection.request('GET', '/api/status')
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                csrf = json.loads(response.read())['csrf']
                body = '{"action":"deploy"}'
                headers = {'Content-Type': 'application/json', 'X-ResearchDesk-CSRF': csrf}

                connection.request('POST', '/api/action', body, {**headers, 'Origin': 'https://example.org'})
                response = connection.getresponse()
                self.assertEqual(response.status, 403)
                response.read()
                wizard.submit.assert_not_called()

                headers['Origin'] = f'http://127.0.0.1:{server.server_port}'
                connection.request('POST', '/api/action', body, headers)
                response = connection.getresponse()
                self.assertEqual(response.status, 202)
                response.read()
                wizard.submit.assert_called_once_with('deploy')
                connection.close()
            finally:
                server.shutdown()
                thread.join(timeout=5)


if __name__ == '__main__':
    unittest.main()
