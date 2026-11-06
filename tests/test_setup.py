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
        origin = mock.patch.object(setup.runner, '_repository', return_value='fixture/workbench')
        origin.start()
        self.addCleanup(origin.stop)

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
            self.wizard.github.prepare.assert_called_once_with(
                expected_repository='fixture/workbench', require_private=True)
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

    def test_saving_topics_updates_all_stages_and_keeps_previous_work(self):
        workbench.initialize(self.root)
        old_note = self.root / 'summary/agent_memory/previous.md'
        old_note.write_text('已有研究', encoding='utf-8')
        original = workbench.load_effective(self.root)
        self.wizard.update_setup()
        self.assertEqual(self.wizard.snapshot()['setup']['topics'], [{'id': 'agent_memory', 'name': 'Agent Memory'}])

        topics = setup.topic_choices([{'name': '向量数据库'}, {'name': 'C++'}, {'name': 'C#'}])
        self.wizard.perform('save_topics', topics)
        snapshot = self.wizard.snapshot()
        self.assertEqual(snapshot['notice']['state'], 'ready', snapshot)
        saved = snapshot['setup']['topics']
        self.assertEqual([topic['name'] for topic in saved], ['向量数据库', 'C++', 'C#'])
        ids = [topic['id'] for topic in saved]
        self.assertEqual(len(set(ids)), 3)
        effective = workbench.load_effective(self.root)
        for stage in ('automation', 'admission', 'confirmation', 'writing_admission'):
            self.assertEqual(effective[stage]['topics'], ids)
        self.assertEqual(effective['research']['topic'], ids[0])
        self.assertEqual(effective['insight']['topic'], ids[0])
        self.assertEqual(effective['research']['discovery'], original['research']['discovery'])
        self.assertFalse(effective['research_topics']['topics']['agent_memory']['enabled'])
        self.assertEqual(effective['research_topics']['topics'][ids[0]]['keywords'], ['向量数据库'])

        self.wizard.perform('save_topics', setup.topic_choices([{'name': 'agent memory'}] + saved))
        effective = workbench.load_effective(self.root)
        self.assertEqual(effective['automation']['topics'], ['agent_memory'] + ids)
        self.assertEqual(effective['research_topics']['topics']['agent_memory'],
                         original['research_topics']['topics']['agent_memory'])
        self.assertEqual(old_note.read_text(encoding='utf-8'), '已有研究')
        self.start_runner.assert_not_called()


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

                connection.request('POST', '/api/action',
                                   '{"action":"save_topics","topics":[{"name":"RAG"},{"name":"rag"}]}', headers)
                response = connection.getresponse()
                self.assertEqual(response.status, 400)
                self.assertIn('重复', json.loads(response.read())['error'])
                wizard.submit.assert_called_once()

                connection.request('POST', '/api/action',
                                   '{"action":"save_topics","topics":[{"name":"向量数据库"}]}'.encode(), headers)
                response = connection.getresponse()
                self.assertEqual(response.status, 202)
                response.read()
                wizard.submit.assert_called_with('save_topics', [(None, '向量数据库')])
                connection.close()
            finally:
                server.shutdown()
                thread.join(timeout=5)


if __name__ == '__main__':
    unittest.main()
