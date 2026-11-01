"""Reload current settings while preserving the registered workbench and notes."""

from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import researchdesk_deployment as deployment
import researchdesk_membership as membership
import researchdesk_workbench as workbench


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


if __name__ == '__main__':
    unittest.main()
