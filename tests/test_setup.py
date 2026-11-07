"""Verify activation ordering and local-only wizard actions without live services."""

import base64
from datetime import datetime, timedelta, timezone
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


WEEKLY = {'weekdays': [1, 4], 'time': '09:35', 'timezone': 'America/New_York'}
WORKFLOW_URL = 'https://github.com/fixture/workbench/actions/workflows/researchdesk-manual.yml'


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
        self.wizard.github.configure_schedule.return_value = WORKFLOW_URL
        self.wizard.github.schedule_matches.return_value = True
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

    def test_creation_is_explicit_and_local_activation_follows_github(self):
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
        self.wizard.perform('github_login')
        self.start_runner.assert_not_called()
        self.wizard.github.configure_schedule.assert_not_called()
        self.assertEqual(self.wizard.snapshot()['deployment']['state'], 'needs_setup')
        before = datetime.now(timezone.utc)

        def check_remote_health():
            self.start_runner.assert_called_once_with(self.root)
            self.wizard.github.prepare.assert_called_once_with(
                expected_repository='fixture/workbench', require_private=True, require_schedule=True)
            current = workbench.load_effective(self.root)
            self.assertFalse(current['automation']['enabled'])
            self.assertFalse(current['admission']['enabled'])
            self.assertNotEqual(current['research']['models']['research'], current['research']['models']['review'])
            self.wizard.github.configure_schedule.assert_not_called()

        def update_remote(cron, zone, **kwargs):
            self.wizard.github.health.assert_called_once()
            self.assertEqual((cron, zone), ('35 9 * * 1,4', WEEKLY['timezone']))
            self.assertFalse(workbench.load_effective(self.root)['automation']['enabled'])
            return WORKFLOW_URL

        self.wizard.github.health.side_effect = check_remote_health
        self.wizard.github.configure_schedule.side_effect = update_remote
        self.wizard.perform('create_schedule', WEEKLY)
        current = workbench.load_effective(self.root)
        self.assertEqual(self.wizard.snapshot()['deployment']['state'], 'ready')
        self.assertEqual(self.wizard.snapshot()['deployment']['url'], WORKFLOW_URL)
        self.assertEqual(self.wizard.snapshot()['setup']['weekly'], WEEKLY)
        self.assertEqual(current['automation']['weekly'], WEEKLY)
        self.assertTrue(current['automation']['enabled'])
        self.assertTrue(current['admission']['enabled'])
        self.assertGreaterEqual(setup.schedule.instant(current['automation']['activated_at']), before)
        self.wizard.obsidian.sync.assert_called_once()
        self.chatgpt.infer.assert_not_called()
        self.assertFalse((self.root / 'reports').exists())

        self.wizard.perform('check')
        self.start_runner.assert_called_once_with(self.root)
        self.wizard.github.configure_schedule.assert_called_once()
        self.wizard.github.schedule_matches.assert_called_once_with(
            '35 9 * * 1,4', WEEKLY['timezone'], expected_repository='fixture/workbench')
        self.assertEqual(self.wizard.snapshot()['deployment']['url'], WORKFLOW_URL)

    def test_failed_health_or_workflow_update_can_retry_without_activation(self):
        self.wizard.github.health.side_effect = setup.GitHubSetupError('检查失败')
        self.wizard.perform('check')
        self.wizard.perform('create_schedule', WEEKLY)
        self.assertEqual(self.wizard.snapshot()['deployment']['state'], 'blocked')
        self.assertFalse(workbench.load_effective(self.root)['automation']['enabled'])
        self.wizard.obsidian.sync.assert_not_called()
        self.wizard.github.configure_schedule.assert_not_called()

        self.wizard.github.health.side_effect = None
        self.wizard.github.configure_schedule.side_effect = setup.GitHubSetupError('无法保存工作流')
        self.wizard.perform('create_schedule', WEEKLY)
        self.assertFalse(workbench.load_effective(self.root)['automation']['enabled'])
        self.assertEqual(self.wizard.snapshot()['deployment']['state'], 'blocked')

        self.wizard.github.configure_schedule.side_effect = None
        self.wizard.obsidian.sync.side_effect = setup.ObsidianSetupError('阅读库有本地改动')
        self.wizard.perform('create_schedule', WEEKLY)

        self.assertEqual(self.wizard.snapshot()['deployment']['state'], 'ready')
        self.assertEqual(self.wizard.snapshot()['obsidian']['state'], 'blocked')
        self.assertTrue(workbench.load_effective(self.root)['automation']['enabled'])

    def test_public_repository_requires_explicit_creation(self):
        self.wizard.github.status.return_value['private'] = False
        self.wizard.perform('check')
        self.start_runner.assert_not_called()
        self.assertEqual(self.wizard.snapshot()['deployment']['state'], 'needs_setup')

        self.wizard.perform('create_schedule', WEEKLY)

        self.start_runner.assert_called_once_with(self.root)
        self.wizard.github.prepare.assert_called_once_with(
            expected_repository='fixture/workbench', require_private=False, require_schedule=True)
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
                body = json.dumps({'action': 'create_schedule', 'schedule': WEEKLY})
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
                wizard.submit.assert_called_once_with('create_schedule', WEEKLY)

                connection.request('POST', '/api/action', json.dumps({
                    'action': 'create_schedule', 'schedule': {**WEEKLY, 'time': '24:15'},
                }), headers)
                response = connection.getresponse()
                self.assertEqual(response.status, 400)
                response.read()
                wizard.submit.assert_called_once()

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


class SetupSchedulePreviewTest(unittest.TestCase):
    def request(self, wizard, query, headers=None):
        with mock.patch.object(setup, 'ThreadingHTTPServer', side_effect=lambda _, handler: handler):
            handler = object.__new__(setup.create_server(wizard))
        handler.server = mock.Mock(server_port=8765)
        handler.headers = {'Host': '127.0.0.1:8765', **(headers or {})}
        handler.path = '/api/schedule-preview?' + query
        handler.reply = mock.Mock()
        handler.do_GET()
        handler.reply.assert_called_once()
        return handler.reply.call_args.args

    def test_preview_uses_local_guard_and_rejects_invalid_or_ambiguous_parameters(self):
        wizard = mock.Mock(spec=['submit'])
        query = 'weekdays=5,2&time=03%3A00&timezone=Asia%2FShanghai'
        before = datetime.now(timezone.utc)
        status, payload = self.request(wizard, query)
        self.assertEqual(status, 200)
        actual = datetime.fromisoformat(payload['next_run'])
        self.assertGreater(actual, before)
        self.assertEqual(actual.utcoffset(), timedelta(0))
        shanghai = actual + timedelta(hours=8)
        self.assertIn(shanghai.isoweekday(), {2, 5})
        self.assertEqual((shanghai.hour, shanghai.minute), (3, 0))

        for invalid in ('', query + '&timezone=UTC', query.replace('5,2', '2,2'),
                        query.replace('03%3A00', '24%3A00'), query.replace('Shanghai', 'Unknown')):
            with self.subTest(query=invalid):
                status, payload = self.request(wizard, invalid)
                self.assertEqual(status, 400)
                self.assertEqual(set(payload), {'error'})
        self.assertEqual(self.request(wizard, query, {'Sec-Fetch-Site': 'cross-site'})[0], 403)
        self.assertEqual(self.request(wizard, query, {'Host': 'example.invalid:8765'})[0], 403)
        wizard.submit.assert_not_called()

    def test_preview_preserves_future_activation_without_writing_configuration(self):
        with tempfile.TemporaryDirectory(prefix='researchdesk-preview-') as temporary:
            root = Path(temporary).resolve()
            workbench.initialize(root)
            path = root / workbench.LOCAL_CONFIG
            user = workbench._read(path)
            user['automation']['activated_at'] = '2099-01-02T03:00:00+00:00'
            workbench._write(path, workbench._yaml(user))
            existing = path.read_bytes()
            wizard = mock.Mock(root=root)
            query = 'weekdays=1,2,3,4,5,6,7&time=03%3A00&timezone=UTC'
            with mock.patch.object(workbench, '_write', side_effect=AssertionError('Read-only preview')):
                status, payload = self.request(wizard, query)
            self.assertEqual((status, payload), (200, {'next_run': user['automation']['activated_at']}))
            self.assertEqual(path.read_bytes(), existing)
            wizard.submit.assert_not_called()


class GitHubScheduleTest(unittest.TestCase):
    def test_workflow_update_preserves_other_lines_and_same_schedule_needs_no_commit(self):
        github = setup.GitHubSetup(workbench.REPOSITORY)
        workflow = workbench.REPOSITORY / '.github/workflows/researchdesk-manual.yml'
        source = workflow.read_text(encoding='utf-8')
        updated = source.replace("cron: '0 19 * * 1,4'", "cron: '35 9 * * 1,4'").replace(
            "timezone: 'UTC'", "timezone: 'America/New_York'")
        target = ('fixture/workbench', {'researchdesk-manual.yml': 'active'})
        sha = 'a' * 40
        with (mock.patch.object(github, '_deployment_target', return_value=target),
              mock.patch.object(github, '_workflow_content', return_value=(source, sha)) as content,
              mock.patch.object(github, '_ensure_workflow_scope') as scope,
              mock.patch.object(github, '_api') as api):
            result = github.configure_schedule('35 9 * * 1,4', WEEKLY['timezone'],
                                               expected_repository='fixture/workbench')
            self.assertEqual(result, WORKFLOW_URL)
            self.assertEqual(api.call_args.kwargs['method'], 'PUT')
            data = api.call_args.kwargs['data']
            self.assertEqual((data['branch'], data['sha']), ('main', sha))
            self.assertEqual(base64.b64decode(data['content']).decode('utf-8'), updated)
            content.return_value = updated, 'b' * 40
            self.assertEqual(github.configure_schedule('35 9 * * 1,4', WEEKLY['timezone'],
                                                       expected_repository='fixture/workbench'), WORKFLOW_URL)
            scope.assert_called_once()
            api.assert_called_once()


if __name__ == '__main__':
    unittest.main()
