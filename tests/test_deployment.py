"""Reload current settings while preserving the registered workbench and notes."""

from copy import deepcopy
from datetime import datetime
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import deployment
import automatic
import membership
import publish
import workbench


class ConfigurationReload(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='researchdesk-deployment-test-')
        self.addCleanup(temporary.cleanup)
        base = Path(temporary.name).resolve()
        self.root, self.source = base / 'workbench', base / 'checkout'
        self.system = yaml.safe_load((workbench.REPOSITORY / workbench.SYSTEM_CONFIG).read_text())
        for root in (self.root, self.source):
            self.write(root / workbench.SYSTEM_CONFIG, self.system)
            self.git(root, 'init', '-b', 'main')
            self.git(root, 'config', 'user.name', 'Offline test')
            self.git(root, 'config', 'user.email', 'test@example.invalid')
            self.git(root, 'remote', 'add', 'origin', 'https://github.com/example/workbench.git')
            self.git(root, 'add', 'config/system.yaml')
            self.git(root, 'commit', '-m', 'Shared defaults')
        workbench.initialize(self.root)
        self.local = yaml.safe_load((self.root / workbench.LOCAL_CONFIG).read_text())
        self.local['runtime'] = {'python': {'venv': sys.prefix}}
        self.write(self.root / workbench.LOCAL_CONFIG, self.local)
        self.commit = self.git(self.source, 'rev-parse', 'HEAD').strip()
        self.env = {'GITHUB_ACTIONS': 'true', 'GITHUB_REF': 'refs/heads/main',
                    'GITHUB_EVENT_NAME': 'schedule', 'GITHUB_REPOSITORY': 'example/workbench',
                    'RESEARCHDESK_WORKBENCH_ROOT': str(self.root)}
        patcher = mock.patch.object(membership, 'MembershipClient',
                                    side_effect=AssertionError('Disabled schedule must not read credentials'))
        patcher.start()
        self.addCleanup(patcher.stop)

    def git(self, root, *args):
        return subprocess.run(['git', '-C', str(root), *args], check=True,
                              capture_output=True, text=True).stdout

    def write(self, path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(value, allow_unicode=True, sort_keys=False))

    def update_upstream(self, days):
        value = deepcopy(self.system)
        value['research']['window']['days'] = days
        self.write(self.source / workbench.SYSTEM_CONFIG, value)
        self.git(self.source, 'add', 'config/system.yaml')
        self.git(self.source, 'commit', '-m', 'Update defaults')
        self.commit = self.git(self.source, 'rev-parse', 'HEAD').strip()

    def dispatch(self):
        return deployment.dispatch(self.source, self.commit, self.source / 'artifact',
                                   environment=self.env)

    def test_each_dispatch_reloads_system_and_user_settings_without_login_or_inference(self):
        # Omit the template's explicit 60-day override to inherit system changes.
        self.local['research'].pop('window')
        self.write(self.root / workbench.LOCAL_CONFIG, self.local)
        user_bytes = (self.root / workbench.LOCAL_CONFIG).read_bytes()
        self.update_upstream(45)
        result = self.dispatch()
        self.assertEqual(result['status'], 'skipped')
        self.assertFalse(result['exported'])
        self.assertEqual(workbench.load_effective(self.root)['research']['window']['days'], 45)
        self.local['research']['window'] = {'days': 30}
        self.write(self.root / workbench.LOCAL_CONFIG, self.local)
        changed_user = (self.root / workbench.LOCAL_CONFIG).read_bytes()
        self.update_upstream(20)
        self.dispatch()
        self.assertEqual(workbench.load_effective(self.root)['research']['window']['days'], 30)
        self.assertEqual((self.root / workbench.LOCAL_CONFIG).read_bytes(), changed_user)
        self.assertNotEqual(changed_user, user_bytes)
        state = json.loads((self.root / deployment.SYSTEM_SYNC).read_text())
        self.assertEqual(state['source_commit'], self.commit)
        self.assertFalse((self.root / 'reports').exists())

    def test_local_system_edits_and_reverts_are_not_overwritten(self):
        self.update_upstream(45)
        deployment.sync_system(self.root, self.source, self.commit)
        manual = deepcopy(self.system)
        manual['research']['window']['days'] = 30
        self.write(self.root / workbench.SYSTEM_CONFIG, manual)
        note = self.root / 'summary/agent_memory/my-note.md'
        note.parent.mkdir(parents=True, exist_ok=True)
        note.write_text('Keep my manual note.\n')
        self.update_upstream(20)
        self.assertEqual(deployment.sync_system(self.root, self.source, self.commit),
                         'local_system_preserved')
        self.assertEqual(yaml.safe_load((self.root / workbench.SYSTEM_CONFIG).read_text()), manual)
        # Reverting to this clone's old HEAD is still an intentional local edit.
        self.write(self.root / workbench.SYSTEM_CONFIG, self.system)
        deployment.sync_system(self.root, self.source, self.commit)
        self.assertEqual(yaml.safe_load((self.root / workbench.SYSTEM_CONFIG).read_text()), self.system)
        self.assertEqual(note.read_text(), 'Keep my manual note.\n')

    def test_other_repository_and_pull_request_cannot_access_the_workbench(self):
        for changes in ({'GITHUB_REPOSITORY': 'other/project'}, {'GITHUB_EVENT_NAME': 'pull_request'},
                        {'GITHUB_REF': 'refs/heads/untrusted'}, {'GITHUB_ACTIONS': 'false'}):
            with self.subTest(changes=changes), self.assertRaises(deployment.DeploymentError):
                deployment.dispatch(self.source, self.commit, self.source / 'artifact',
                                      environment={**self.env, **changes})

    def test_interpreter_move_requires_start_before_any_models_or_collection(self):
        self.local['runtime']['python']['venv'] = str(self.root.parent / 'new-runtime')
        self.write(self.root / workbench.LOCAL_CONFIG, self.local)
        with self.assertRaisesRegex(deployment.DeploymentError, 'run_workbench_start'):
            self.dispatch()
        self.assertFalse((self.root / 'reports').exists())

    def test_scheduled_trigger_with_stale_cron_or_zone_skips_before_collection(self):
        self.local['automation'] = {'enabled': True, 'weekly': {
            'weekdays': [5], 'time': '03:25', 'timezone': 'Asia/Shanghai'}}
        self.write(self.root / workbench.LOCAL_CONFIG, self.local)
        workflow = self.source / '.github/workflows/researchdesk-manual.yml'
        # Same cron in a different timezone must also skip when the remote
        # workflow has changed but the operator's local settings have not.
        self.write(workflow, {'on': {'schedule': [{'cron': '25 3 * * 5', 'timezone': 'America/New_York'}]}})
        self.git(self.source, 'add', str(workflow))
        self.git(self.source, 'commit', '-m', 'Change remote timezone')
        self.commit = self.git(self.source, 'rev-parse', 'HEAD').strip()

        def pipeline(root, **kwargs):
            collector = mock.Mock(side_effect=AssertionError('Stale events must not collect'))
            result = automatic.run(root, collector=collector,
                                   now=datetime.fromisoformat('2026-11-06T23:00:00+08:00'), **kwargs)
            collector.assert_not_called()
            return result

        for expression in ('0 19 * * 1,4', '25 3 * * 5'):
            with self.subTest(expression=expression):
                result = deployment.dispatch(self.source, self.commit, self.source / 'artifact',
                    environment={**self.env, 'RESEARCHDESK_TRIGGER_CRON': expression}, pipeline=pipeline)
                self.assertEqual((result['status'], result['reason']), ('skipped', 'schedule_trigger_mismatch'))
                self.assertFalse(result['exported'])
        self.assertFalse((self.root / 'reports').exists())

    def test_scheduled_topic_packages_keep_successful_exports_and_saves_when_another_fails(self):
        topics = ['agent_memory', 'fixture-retrieval']
        self.local['automation'] = {'enabled': True, 'topics': topics}
        self.local['research_topics'] = {'topics': {'fixture-retrieval': {
            'name': 'Retrieval', 'enabled': True, 'description': 'Offline fixture.',
            'scope': ['Retrieval'], 'keywords': ['retrieval']}}}
        self.write(self.root / workbench.LOCAL_CONFIG, self.local)

        def collect(root, path, identity):
            if identity.startswith('agent_memory-'):
                raise RuntimeError('Fixture source failure')
            return {'status': 'empty', 'discovery_status': 'complete'}

        def pipeline(root, **kwargs):
            return automatic.run(root, collector=collect,
                                 now=datetime.fromisoformat('2026-11-06T09:00:00+08:00'), **kwargs)

        artifact, outputs = self.source.parent / 'artifact', self.source.parent / 'outputs'
        result = deployment.dispatch(self.source, self.commit, artifact,
                                     environment=self.env, github_output=outputs, pipeline=pipeline)
        self.assertEqual(result['status'], 'partial')
        self.assertTrue(result['exported'])
        self.assertIn('artifact_path=' + str(artifact), outputs.read_text())
        identities = [(run['topic'], run['cycle_id']) for run in result['runs']]
        self.assertEqual([run['status'] for run in result['runs']], ['failed', 'no_new'])

        first, second = [automatic._base(topic, cycle) + '/context.yaml' for topic, cycle in identities]
        conflict = self.source / first
        conflict.parent.mkdir(parents=True)
        conflict.write_text('keep this existing file\n')
        remote = self.source.parent / 'remote.git'
        remote.mkdir()
        self.git(remote, 'init', '--bare')
        self.git(self.source, 'remote', 'set-url', 'origin', str(remote))
        self.git(self.source, 'push', 'origin', 'main')
        saved = publish.apply(self.source, artifact, push=True)
        self.assertEqual(saved['status'], 'partial')
        self.assertEqual([item['status'] for item in saved['results']], ['failed', 'complete'])
        self.assertEqual(conflict.read_text(), 'keep this existing file\n')
        self.assertTrue((self.source / second).is_file())
        self.assertTrue(saved['pushed'])
        self.assertEqual(self.git(remote, 'show', 'refs/heads/main:' + second), (self.source / second).read_text())
        self.assertNotIn(first, self.git(remote, 'ls-tree', '-r', '--name-only', 'refs/heads/main'))
        self.assertEqual(publish.apply(self.source, artifact, push=True)['saved_files'], 0)

        (self.root / first).write_text('invalid local proof\n')
        second_artifact = self.source.parent / 'second-artifact'
        partial_export = publish.export_many(self.root, second_artifact, identities, self.commit)
        self.assertEqual(partial_export['exported_cycles'], 1)
        self.assertEqual(partial_export['failures'][0]['topic'], 'agent_memory')
        self.assertEqual(publish.apply(self.source, second_artifact)['status'], 'complete')


if __name__ == '__main__':
    unittest.main()
