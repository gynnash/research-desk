"""Verify activation ordering and local-only wizard actions without live services."""

import base64
from datetime import datetime, timedelta, timezone
import http.client
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import setup
import setup_github as github_setup
import setup_obsidian as obsidian_setup
import workbench


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
            'state': 'ready', 'repository': 'fixture/workbench', 'private': True, 'workflow_scope': True,
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

    def test_startup_overlaps_independent_checks_and_shows_the_schedule_before_the_vault(self):
        self.wizard.perform('check')
        self.wizard.perform('create_schedule', WEEKLY)
        self.wizard.update('deployment', setup.section('idle', '正在检查日程。'))
        self.wizard.github.status.return_value['research_workflow_state'] = 'active'
        catalog_started = threading.Event()
        vault_started = threading.Event()
        model_write_started = threading.Event()
        schedule_started = threading.Event()
        schedule_published = threading.Event()
        release_vault = threading.Event()

        def catalog():
            catalog_started.set()
            return self.chatgpt.models.return_value

        def github_status():
            self.assertTrue(catalog_started.wait(3))
            self.assertTrue(vault_started.wait(3))
            self.assertFalse(model_write_started.is_set())
            return self.wizard.github.status.return_value

        def vault_status():
            vault_started.set()
            self.assertTrue(release_vault.wait(5))
            return self.wizard.obsidian.status.return_value

        def check_schedule(*args, **kwargs):
            schedule_started.set()
            return True

        original_configure = setup.configure_models
        original_update = self.wizard.update

        def configure(*args):
            model_write_started.set()
            self.assertTrue(schedule_started.wait(3))
            original_configure(*args)

        def update(name, value):
            original_update(name, value)
            if name == 'deployment' and value['state'] == 'ready':
                schedule_published.set()

        self.chatgpt.models.side_effect = catalog
        self.wizard.github.status.side_effect = github_status
        self.wizard.github.schedule_matches.side_effect = check_schedule
        self.wizard.obsidian.status.side_effect = vault_status
        self.wizard.update = update
        with mock.patch.object(setup, 'configure_models', side_effect=configure):
            worker = threading.Thread(target=self.wizard.perform, args=('check',), daemon=True)
            worker.start()
            try:
                self.assertTrue(schedule_published.wait(4))
                self.assertTrue(worker.is_alive())
                self.wizard.github.schedule_matches.assert_called_once_with(
                    '35 9 * * 1,4', WEEKLY['timezone'], expected_repository='fixture/workbench',
                    observed_workflow_state='active')
            finally:
                release_vault.set()
                worker.join(6)
        self.assertFalse(worker.is_alive())

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
            'state': 'ready', 'repository': 'fixture/workbench', 'private': True, 'workflow_scope': True,
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

    def test_workflow_scope_is_authorized_separately_before_deployment(self):
        github = self.wizard.github
        github.status.return_value.update(workflow_scope=False, can_create=True)
        self.wizard.perform('check')
        self.wizard.perform('github_create')
        self.wizard.perform('create_schedule', WEEKLY)
        github.create_repository.assert_not_called()
        github.prepare.assert_not_called()
        github.health.assert_not_called()
        github.authorize_workflow.assert_not_called()
        self.start_runner.assert_not_called()

        github.authorize_workflow.side_effect = setup.GitHubSetupError('等待 GitHub 授权超时。')
        self.wizard.perform('github_workflow_auth')
        snapshot = self.wizard.snapshot()
        self.assertEqual(snapshot['github']['state'], 'ready')
        self.assertFalse(snapshot['github']['workflow_scope'])
        self.assertEqual(snapshot['notice']['message'], '等待 GitHub 授权超时。')

        def grant_workflow_scope(_notify):
            github.status.return_value['workflow_scope'] = True

        github.authorize_workflow.side_effect = grant_workflow_scope
        self.wizard.perform('github_workflow_auth')
        self.assertTrue(self.wizard.snapshot()['github']['workflow_scope'])
        self.start_runner.assert_not_called()

        self.wizard.perform('create_schedule', WEEKLY)
        github.require_workflow_scope.assert_called_once()
        github.configure_schedule.assert_called_once_with(
            '35 9 * * 1,4', WEEKLY['timezone'], expected_repository='fixture/workbench', require_private=True)
        self.assertEqual(self.wizard.snapshot()['deployment']['state'], 'ready')

    def test_chatgpt_authorization_url_is_handed_to_the_existing_wizard(self):
        url = 'https://auth.openai.com/authorize'
        self.wizard.perform('check')

        def login(*, open_authorization):
            open_authorization(url)
            self.assertEqual(self.wizard.snapshot()['operation']['url'], url)

        self.chatgpt.login.side_effect = login
        self.wizard.update('operation', {'action': 'chatgpt_login'})
        with mock.patch.object(setup.webbrowser, 'open') as browser:
            self.wizard.perform('chatgpt_login')
        browser.assert_not_called()
        self.assertEqual(self.wizard.snapshot()['chatgpt']['state'], 'ready')
        self.assertIsNone(self.wizard.snapshot()['operation'])

    def test_github_authorization_reports_the_completed_attempt_without_opening_a_wizard(self):
        with mock.patch.object(setup.webbrowser, 'open') as browser:
            for action in ('github_login', 'github_workflow_auth'):
                with self.subTest(action=action):
                    self.wizard.update('operation', {'action': action, 'attempt': action + '-attempt'})
                    self.wizard.perform(action)
                    snapshot = self.wizard.snapshot()
                    self.assertEqual(snapshot['github']['state'], 'ready')
                    self.assertTrue(snapshot['github']['workflow_scope'])
                    self.assertIsNone(snapshot['operation'])
                    self.assertEqual(snapshot['notice']['state'], 'ready')
                    self.assertEqual(snapshot['notice']['attempt'], action + '-attempt')
            browser.assert_not_called()

    def test_failed_github_authorization_keeps_wizard_in_place(self):
        self.wizard.update('operation', {'action': 'github_login', 'attempt': 'failed-attempt'})
        self.wizard.github.login.side_effect = setup.GitHubSetupError('授权超时。')
        with mock.patch.object(setup.webbrowser, 'open') as browser:
            self.wizard.perform('github_login')
        browser.assert_not_called()
        snapshot = self.wizard.snapshot()
        self.assertEqual(snapshot['github']['state'], 'needs_login')
        self.assertIsNone(snapshot['operation'])
        self.assertNotIn('attempt', snapshot.get('notice', {}))

    def test_revoked_workflow_scope_preserves_the_existing_schedule(self):
        github = self.wizard.github
        self.wizard.perform('check')
        self.wizard.perform('create_schedule', WEEKLY)
        github.require_workflow_scope.side_effect = setup.GitHubSetupError(
            setup.GITHUB_WORKFLOW_REQUIRED, code='github_workflow_scope_required')

        self.wizard.perform('create_schedule', {**WEEKLY, 'time': '10:00'})
        snapshot = self.wizard.snapshot()
        self.assertFalse(snapshot['github']['workflow_scope'])
        self.assertEqual(snapshot['notice']['message'], setup.GITHUB_WORKFLOW_REQUIRED)
        self.assertEqual(snapshot['deployment']['state'], 'ready')
        self.assertEqual(snapshot['setup']['weekly'], WEEKLY)
        github.prepare.assert_called_once()
        github.configure_schedule.assert_called_once()
        github.authorize_workflow.assert_not_called()

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


class ObsidianNetworkTest(unittest.TestCase):
    def test_github_fetch_uses_system_proxy_with_isolated_git_configuration(self):
        vault = obsidian_setup.ObsidianSetup(workbench.REPOSITORY)
        proxy = 'http://proxy.fixture:3128'
        origin = 'https://github.com/fixture/workbench.git'
        inherited = {'GIT_DIR': '/ignored', 'GIT_CONFIG_COUNT': '1', 'GIT_CONFIG_KEY_0': 'http.proxy',
                     'GIT_CONFIG_VALUE_0': 'http://ignored', 'GIT_TRACE': '1', 'GH_TOKEN': 'fixture-token'}
        with (mock.patch.dict(os.environ, inherited, clear=True),
              mock.patch.object(github_setup, 'getproxies', return_value={'https': proxy}),
              mock.patch.object(github_setup, 'proxy_bypass', return_value=False),
              mock.patch.object(obsidian_setup.subprocess, 'run',
                                return_value=subprocess.CompletedProcess([], 0, stdout=b'')) as run):
            vault._git(vault.root, 'fetch', '--', origin, network=True, github_auth=True)
        command, = run.call_args.args
        environment = run.call_args.kwargs['env']
        self.assertEqual(environment['HTTPS_PROXY'], proxy)
        self.assertEqual(environment['GH_TOKEN'], inherited['GH_TOKEN'])
        self.assertEqual(environment['GIT_CONFIG_GLOBAL'], os.devnull)
        self.assertEqual(environment['GIT_CONFIG_NOSYSTEM'], '1')
        self.assertEqual(environment['GIT_TERMINAL_PROMPT'], '0')
        self.assertFalse((inherited.keys() - {'GH_TOKEN'}) & environment.keys())
        self.assertIn('core.hooksPath=/dev/null', command)
        self.assertIn('protocol.allow=never', command)
        self.assertIn('credential.https://github.com.helper=!gh auth git-credential', command)
        self.assertEqual(command[-3:], ['fetch', '--', origin])


class ObsidianReadingVaultTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='researchdesk-reading-vault-')
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name).resolve()
        self.source = root / 'source'
        workbench_root = root / 'workbench'
        for directory in (self.source, workbench_root):
            directory.mkdir()
            self.git(directory, 'init', '-b', 'main')
        self.git(workbench_root, 'remote', 'add', 'origin', str(self.source))
        self.vault = obsidian_setup.ObsidianSetup(workbench_root, root / 'vaults')
        self.reading = {
            'README.md': '阅读指南',
            '研究首页.md': '研究目录',
            'collection/agents/week/items/paper/original.md': '论文原文',
            'summary/agents/week/paper.md': '逐篇总结',
            'insights/agents/week/report.md': '综合洞察',
            'articles/agents/week-topic-1.md': '待确认选题',
            'sources/originals/agents/paper.md': '历史原文',
            'reports/agents/week-research-paper.md': '历史总结',
            'reports/agents/解读/week/paper.md': '历史解读',
        }
        other = {
            '.gitignore': '/.obsidian/\n',
            'scripts/tool.py': '# code',
            'config/README.md': '配置说明',
            'reports/proof.md': '运行证明',
            'reports/agents/admissions/week/proof.md': '准入证明',
            'summary/agents/week/data.yaml': 'private: false',
            'summary/agents/week/.draft.md': '隐藏草稿',
            'collection/agents/.hidden/notes.md': '隐藏目录',
            'insights/test/fixture/report.md': '测试洞察',
            'articles/agents/test/fixture.md': '测试稿件',
        }
        for path, content in {**self.reading, **other}.items():
            self.write(self.source, path, content)
        self.commit()

    @staticmethod
    def git(root, *args):
        result = subprocess.run(
            ['git', '-C', str(root), '-c', 'core.hooksPath=/dev/null', '-c', 'commit.gpgsign=false',
             '-c', 'user.name=ResearchDesk Test', '-c', 'user.email=test@example.invalid', *args],
            capture_output=True, text=True, check=True,
        )
        return result.stdout.strip()

    @staticmethod
    def write(root, relative, content):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding='utf-8')

    def commit(self):
        self.git(self.source, 'add', '--all')
        self.git(self.source, 'commit', '-m', 'Update reading fixture')

    def visible_files(self):
        return {path.relative_to(self.vault.path).as_posix() for path in self.vault.path.rglob('*')
                if path.is_file() and '.git' not in path.relative_to(self.vault.path).parts}

    def test_initial_copy_and_automatic_refresh_only_show_reading_files(self):
        self.vault.sync()
        self.assertEqual(self.visible_files(), self.reading.keys())
        summary = 'summary/agents/week/paper.md'
        removed = 'collection/agents/week/items/paper/original.md'
        added = 'articles/agents/week-draft.md'
        named_notes = {
            'summary/agents/长期记忆~next/核对事实~paper.md': '新命名总结',
            'insights/agents/检索需要核实~next/长期记忆为何失效.md': '新命名洞察',
        }
        self.write(self.vault.path, '.obsidian/app.json', '{}')
        self.write(self.source, summary, '更新后的总结')
        self.write(self.source, added, '新稿件')
        for path, content in named_notes.items():
            self.write(self.source, path, content)
        self.write(self.source, 'scripts/new.py', '# new code')
        (self.source / removed).unlink()
        self.commit()

        with (mock.patch.object(obsidian_setup, '_github_repo', return_value='fixture/workbench'),
              mock.patch.object(obsidian_setup, '_reading_remote', side_effect=lambda remote: (remote, False))):
            self.assertTrue(self.vault.refresh_existing('fixture/workbench'))

        self.assertEqual(self.visible_files(),
                         (self.reading.keys() - {removed}) | named_notes.keys() | {added, '.obsidian/app.json'})
        for path, content in named_notes.items():
            self.assertEqual((self.vault.path / path).read_text(encoding='utf-8'), content)
        self.assertEqual((self.vault.path / summary).read_text(encoding='utf-8'), '更新后的总结')
        self.assertEqual((self.vault.path / '.obsidian/app.json').read_text(encoding='utf-8'), '{}')
        self.assertEqual(self.vault.status()['state'], 'ready')

    def test_selected_empty_path_is_saved_and_used_for_automatic_refresh(self):
        self.vault.sync()
        previous = self.vault.path
        selected = self.source.parent / '自选 阅读库 '
        selected.mkdir()
        with mock.patch.object(self.vault, '_pick_folder', return_value=selected):
            self.assertTrue(self.vault.choose_path())
        self.assertEqual(list(selected.iterdir()), [])

        reopened = obsidian_setup.ObsidianSetup(self.vault.root)
        status = reopened.status()
        self.assertEqual(status['path'], str(selected))
        self.assertEqual(status['state'], 'not_ready')
        reopened.sync()
        self.assertEqual(reopened.status()['state'], 'ready')
        self.assertEqual((selected / 'README.md').read_text(encoding='utf-8'), self.reading['README.md'])
        self.assertFalse((selected / 'scripts/tool.py').exists())

        self.write(self.source, 'README.md', '更新后的阅读指南')
        self.commit()
        with (mock.patch.object(obsidian_setup, '_github_repo', return_value='fixture/workbench'),
              mock.patch.object(obsidian_setup, '_reading_remote', side_effect=lambda remote: (remote, False))):
            runner_vault = obsidian_setup.ObsidianSetup(self.vault.root)
            self.assertTrue(runner_vault.refresh_existing('fixture/workbench'))

        self.assertEqual((selected / 'README.md').read_text(encoding='utf-8'), '更新后的阅读指南')
        self.assertEqual((previous / 'README.md').read_text(encoding='utf-8'), self.reading['README.md'])

    def test_cancel_and_invalid_folder_leave_the_existing_selection_intact(self):
        selected = self.source.parent / '已有阅读库'
        selected.mkdir()
        with mock.patch.object(self.vault, '_pick_folder', return_value=selected):
            self.assertTrue(self.vault.choose_path())
        self.vault.sync()
        self.write(selected, '.obsidian/app.json', '{"theme":"local"}')

        with mock.patch.object(self.vault, '_pick_folder', return_value=None):
            self.assertFalse(self.vault.choose_path())
        unrelated = self.source.parent / '个人笔记'
        self.write(unrelated, '笔记.md', '保留笔记')
        inside_workbench = self.vault.root / '阅读库'
        inside_workbench.mkdir()
        for invalid in (unrelated, inside_workbench):
            with (self.subTest(folder=invalid), mock.patch.object(self.vault, '_pick_folder', return_value=invalid),
                  self.assertRaises(obsidian_setup.ObsidianSetupError)):
                self.vault.choose_path()

        reopened = obsidian_setup.ObsidianSetup(self.vault.root)
        status = reopened.status()
        self.assertEqual(status['path'], str(selected))
        self.assertEqual(status['state'], 'ready')
        self.assertEqual((selected / '.obsidian/app.json').read_text(encoding='utf-8'), '{"theme":"local"}')
        self.assertEqual((unrelated / '笔记.md').read_text(encoding='utf-8'), '保留笔记')

    def test_legacy_copy_migrates_in_place_and_protects_local_edits(self):
        self.vault.path.parent.mkdir()
        self.git(self.source, 'clone', '--no-local', '--single-branch', '--branch', 'main',
                 str(self.source), str(self.vault.path))
        self.write(self.vault.path, '.git/researchdesk-obsidian', self.vault._identity + '\n')
        self.write(self.vault.path, '.obsidian/app.json', '{"theme":"local"}')
        old_code = 'scripts/tool.py'
        self.write(self.vault.path, old_code, '本地修改')
        with self.assertRaisesRegex(obsidian_setup.ObsidianSetupError, '本地改动'):
            self.vault.sync()
        self.assertEqual((self.vault.path / old_code).read_text(encoding='utf-8'), '本地修改')

        self.git(self.vault.path, 'restore', '--', old_code)
        self.vault.sync()
        self.assertEqual(self.visible_files(), self.reading.keys() | {'.obsidian/app.json'})
        self.assertEqual((self.vault.path / '.obsidian/app.json').read_text(encoding='utf-8'), '{"theme":"local"}')
        self.assertEqual(self.vault.status()['state'], 'ready')

    def test_new_remote_note_cannot_overwrite_an_ignored_local_file(self):
        self.vault.sync()
        relative = 'summary/agents/week/local.md'
        with (self.vault.path / '.git/info/exclude').open('a', encoding='utf-8') as exclude:
            exclude.write('/' + relative + '\n')
        self.write(self.vault.path, relative, '本地笔记')
        self.assertEqual(self.git(self.vault.path, 'status', '--porcelain'), '')
        self.write(self.source, relative, '远端新笔记')
        self.commit()

        with self.assertRaisesRegex(obsidian_setup.ObsidianSetupError, '本地'):
            self.vault.sync()

        self.assertEqual((self.vault.path / relative).read_text(encoding='utf-8'), '本地笔记')


class GitHubScheduleTest(unittest.TestCase):
    def test_github_environment_uses_system_proxy_and_preserves_bypass(self):
        proxies = {'http': 'http://proxy.fixture:3128', 'https': 'http://proxy.fixture:3129'}
        with (mock.patch.dict(os.environ, {'CLICOLOR_FORCE': '1'}, clear=True),
              mock.patch.object(github_setup, 'getproxies', return_value=proxies),
              mock.patch.object(github_setup, 'proxy_bypass', side_effect=lambda host: host == 'api.github.com')):
            environment = github_setup._environment()
        self.assertEqual(environment['HTTP_PROXY'], proxies['http'])
        self.assertEqual(environment['HTTPS_PROXY'], proxies['https'])
        self.assertIn('api.github.com', environment['NO_PROXY'].split(','))
        self.assertNotIn('github.com', environment['NO_PROXY'].split(','))
        self.assertEqual(environment['NO_COLOR'], '1')
        self.assertIn(environment.get('CLICOLOR_FORCE'), (None, '0'))

    def test_github_environment_preserves_explicit_proxy_configuration(self):
        for explicit in ({'https_proxy': 'http://proxy.fixture:3128', 'NO_PROXY': 'github.com'},
                         {'HTTPS_PROXY': ''}, {'no_proxy': 'github.com'}):
            with (self.subTest(explicit=explicit), mock.patch.dict(os.environ, explicit, clear=True),
                  mock.patch.object(github_setup, 'getproxies') as system):
                environment = github_setup._environment()
                system.assert_not_called()
                self.assertEqual({name: environment[name] for name in setup.runner.PROXY_NAMES
                                  if name in environment}, explicit)

    def test_login_fails_distinctly_when_no_device_code_arrives(self):
        github = setup.GitHubSetup(workbench.REPOSITORY)
        with (mock.patch.object(github_setup.subprocess, 'Popen') as spawn,
              mock.patch.object(github_setup.selectors, 'DefaultSelector') as selectors,
              mock.patch.object(github_setup.os, 'read') as read,
              mock.patch.object(github_setup.time, 'monotonic', return_value=100)):
            process = spawn.return_value
            selector = selectors.return_value.__enter__.return_value
            process.wait.side_effect = [subprocess.TimeoutExpired('gh', 25), 0]
            process.poll.return_value = None
            selector.select.return_value = []
            with self.assertRaises(setup.GitHubSetupError) as timed_out:
                github._authorize_in_browser(['login'], mock.Mock(), 'fixture')
            self.assertEqual(timed_out.exception.code, 'github_device_code_timeout')
            selector.select.assert_called_once_with(25)
            process.terminate.assert_called_once()

            process.wait.side_effect = None
            process.wait.return_value = 1
            process.poll.return_value = 1
            selector.select.return_value = [mock.sentinel.ready]
            read.side_effect = [b'network error with private diagnostics', b'']
            with self.assertRaises(setup.GitHubSetupError) as unavailable:
                github._authorize_in_browser(['login'], mock.Mock(), 'fixture')
            self.assertEqual(unavailable.exception.code, 'github_device_code_unavailable')
            self.assertNotIn('private diagnostics', str(unavailable.exception))

    def test_login_resets_deadline_after_device_code(self):
        github = setup.GitHubSetup(workbench.REPOSITORY)
        notify = mock.Mock()
        with (mock.patch.object(github_setup.subprocess, 'Popen') as spawn,
              mock.patch.object(github_setup.selectors, 'DefaultSelector') as selectors,
              mock.patch.object(github_setup.os, 'read', side_effect=[
                  b'! First copy your one-time code: ABCD-1234\n', b'',
              ]),
              mock.patch.object(github_setup.time, 'monotonic', return_value=100)):
            spawn.return_value.wait.return_value = 0
            spawn.return_value.poll.return_value = 0
            selector = selectors.return_value.__enter__.return_value
            selector.select.return_value = [mock.sentinel.ready]
            github._authorize_in_browser(['login'], notify, 'fixture')
        self.assertEqual(selector.select.call_args_list, [mock.call(25), mock.call(300)])
        self.assertEqual([call.kwargs['code'] for call in notify.call_args_list if 'code' in call.kwargs],
                         ['ABCD-1234'])

    def test_first_login_requests_workflow_permission(self):
        github = setup.GitHubSetup(workbench.REPOSITORY)
        missing = setup.GitHubSetupError('需要登录', code='github_login_required')
        notify = mock.Mock()
        with (mock.patch('setup_github.shutil.which', return_value='gh'),
              mock.patch.object(github, '_check_auth', side_effect=[missing, None]) as check,
              mock.patch.object(github, '_authorize_in_browser') as browser):
            github.login(notify)
        self.assertEqual(check.call_count, 2)
        browser.assert_called_once_with(['login', '--hostname', 'github.com', '--web', '--scopes', 'workflow'],
                                        notify, mock.ANY)

    def test_permission_status_is_independent_of_repository_connection(self):
        github = setup.GitHubSetup(workbench.REPOSITORY)
        missing_repository = setup.GitHubSetupError('需要连接仓库', code='github_repository_required')
        with (mock.patch('setup_github.shutil.which', return_value='gh'),
              mock.patch.dict(os.environ, {'GH_TOKEN': '', 'GITHUB_TOKEN': ''}),
              mock.patch.object(github, '_check_auth'),
              mock.patch.object(github, '_repository', side_effect=missing_repository),
              mock.patch.object(github, '_workflow_scope', return_value=False) as scope):
            status = github.status()
            self.assertEqual(status['state'], 'needs_repository')
            self.assertFalse(status['workflow_scope'])
            self.assertTrue(status['can_authorize_workflow'])
            with mock.patch.dict(os.environ, {'GITHUB_TOKEN': 'fixture-token'}):
                status = github.status()
                self.assertFalse(status['workflow_scope'])
                self.assertFalse(status['can_authorize_workflow'])
                self.assertIn('GITHUB_TOKEN', status['workflow_scope_message'])
            scope.return_value = True
            self.assertTrue(github.status()['workflow_scope'])
            scope.side_effect = setup.GitHubSetupError('GitHub 查询超时', code='github_timeout')
            status = github.status()
            self.assertEqual(status['state'], 'needs_repository')
            self.assertNotIn('workflow_scope', status)
            self.assertEqual(status['workflow_scope_message'], 'GitHub 查询超时')

    def test_workflow_browser_refresh_requires_explicit_action_and_local_credential(self):
        github = setup.GitHubSetup(workbench.REPOSITORY)
        notify = mock.Mock()
        with (mock.patch.dict(os.environ, {'GH_TOKEN': '', 'GITHUB_TOKEN': ''}),
              mock.patch.object(github, '_check_auth'),
              mock.patch.object(github, '_workflow_scope', return_value=False) as scope,
              mock.patch.object(github, '_authorize_in_browser') as browser):
            with self.assertRaises(setup.GitHubSetupError) as check:
                github.require_workflow_scope()
            self.assertEqual(check.exception.code, 'github_workflow_scope_required')
            browser.assert_not_called()
            with mock.patch.dict(os.environ, {'GH_TOKEN': 'fixture-token'}):
                with self.assertRaisesRegex(setup.GitHubSetupError, 'GH_TOKEN'):
                    github.authorize_workflow(notify)
                browser.assert_not_called()
            scope.side_effect = [False, True]
            github.authorize_workflow(notify)
            browser.assert_called_once_with(['refresh', '--hostname', 'github.com', '--scopes', 'workflow'],
                                            notify, mock.ANY)

    def test_prepare_uses_authenticated_main_content_without_git_https(self):
        github = setup.GitHubSetup(workbench.REPOSITORY)
        workflow = workbench.REPOSITORY / '.github/workflows/researchdesk-manual.yml'
        source = workflow.read_text(encoding='utf-8')
        target = ('fixture/workbench', {'researchdesk-manual.yml': 'active', 'researchdesk-writing.yml': 'active'})
        with (mock.patch.object(github, '_deployment_target', return_value=target),
              mock.patch.object(github, '_git', side_effect=AssertionError('unexpected Git transport')),
              mock.patch.object(github, '_api', side_effect=[
                  {'type': 'file', 'encoding': 'base64', 'sha': 'a' * 40,
                   'content': base64.b64encode(source.encode()).decode()},
                  {'type': 'file'},
              ]) as api):
            github.prepare(expected_repository='fixture/workbench', require_private=True, require_schedule=True)
            self.assertEqual([call.args[0] for call in api.call_args_list], [
                'repos/fixture/workbench/contents/.github/workflows/researchdesk-manual.yml?ref=main',
                'repos/fixture/workbench/contents/scripts/setup_obsidian.py?ref=main',
            ])

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
              mock.patch.object(github, 'require_workflow_scope') as scope,
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


class GitHubStartupTest(unittest.TestCase):
    def test_workflow_checks_overlap_after_policy_validation(self):
        github = setup.GitHubSetup(workbench.REPOSITORY)
        repository = 'fixture/workbench'
        policy_checked = threading.Event()
        both_started = threading.Barrier(2, timeout=2)

        def check_workflow(repo, name):
            self.assertEqual(repo, repository)
            self.assertTrue(policy_checked.is_set())
            both_started.wait()
            return 'active' if name == github_setup.RESEARCH_WORKFLOW else 'disabled_manually'

        with (mock.patch.object(github_setup.shutil, 'which', return_value='/mock/tool'),
              mock.patch.object(github, '_check_auth'),
              mock.patch.object(github, '_workflow_scope', return_value=True),
              mock.patch.object(github, '_repository', return_value=repository),
              mock.patch.object(github, '_api', return_value={
                  'permissions': {'admin': True}, 'default_branch': 'main', 'private': True,
              }),
              mock.patch.object(github, '_check_actions', side_effect=lambda _: policy_checked.set()),
              mock.patch.object(github, '_workflow_state', side_effect=check_workflow)):
            result = github.status()
        self.assertEqual(result['state'], 'ready')
        self.assertEqual(result['research_workflow_state'], 'active')
        self.assertIn('将启用', result['message'])

    def test_schedule_match_reuses_workflow_state_but_still_checks_origin_and_file(self):
        github = setup.GitHubSetup(workbench.REPOSITORY)
        repository = 'fixture/workbench'
        cron, timezone = '35 9 * * 1,4', WEEKLY['timezone']
        source = (f"on:\n  schedule:\n{github_setup.SCHEDULE_MARKER}\n"
                  f"    - cron: '{cron}'\n      timezone: '{timezone}'\n")
        with (mock.patch.object(github, '_repository', return_value=repository) as origin,
              mock.patch.object(github, '_workflow_content', return_value=(source, 'a' * 40)) as content,
              mock.patch.object(github, '_workflow_state', return_value='disabled_manually') as state):
            self.assertTrue(github.schedule_matches(cron, timezone, expected_repository=repository,
                                                   observed_workflow_state='active'))
            self.assertFalse(github.schedule_matches(cron, timezone, expected_repository=repository,
                                                    observed_workflow_state='disabled_manually'))
            state.assert_not_called()
            self.assertFalse(github.schedule_matches(cron, timezone, expected_repository=repository))
            state.assert_called_once_with(repository, github_setup.RESEARCH_WORKFLOW)
            self.assertEqual(origin.call_count, 3)
            self.assertEqual(content.call_args_list, [mock.call(repository)] * 3)


if __name__ == '__main__':
    unittest.main()
