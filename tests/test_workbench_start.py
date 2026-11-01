"""One-command deployment without any network, inference or service mutation."""

from copy import deepcopy
import json
import os
from pathlib import Path
import socket
import stat
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import researchdesk_membership as membership
import researchdesk_offline as store
import researchdesk_runner as runner
import researchdesk_workbench as workbench


class OneCommandStart(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='researchdesk-start-tests-')
        self.addCleanup(temporary.cleanup)
        self.parent = Path(temporary.name).resolve()
        self.root = self.parent / 'workbench'
        self.root.mkdir()
        workbench.initialize(self.root)
        self.local = self.root / workbench.LOCAL_CONFIG
        config = yaml.safe_load(self.local.read_text())
        config['runtime'] = {
            'runner': {'directory': str(self.parent / 'runner'), 'name': 'fixture-runner'},
            'python': {'venv': str(self.parent / 'runtime')},
            'membership': {'profile': str(self.parent / 'own-profile')},
        }
        self.local.write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False))
        self.expected_runner = {'registered': True, 'service': 'running', 'name': 'fixture-runner'}
        self.client = mock.Mock()
        self.client.status.return_value = {'authenticated': True, 'plan_permission': True}
        self.client.models.return_value = [{'slug': name} for name in (
            'gpt-6.1-sol', 'gpt-6-astra', 'gpt-6-luna', 'fixture-new-review')]
        self.sdk_ready = True
        self.calls = []
        for target, name in ((socket, 'create_connection'), (socket.socket, 'connect'),
                             (subprocess, 'run')):
            patcher = mock.patch.object(target, name, side_effect=AssertionError('No external operation'))
            patcher.start()
            self.addCleanup(patcher.stop)
        self.patch(membership, 'MembershipClient', return_value=self.client)
        self.patch(workbench.platform, 'system', return_value='Darwin')
        self.patch(runner, '_repository', return_value='fixture-owner/researchdesk')
        self.api = self.patch(runner, '_api', return_value={'permissions': {'admin': True}})
        self.run_process = self.patch(runner, '_run', side_effect=self.process)
        self.setup_runner = self.patch(runner, 'setup', side_effect=self.setup)

    def patch(self, target, name, **kwargs):
        patcher = mock.patch.object(target, name, **kwargs)
        result = patcher.start()
        self.addCleanup(patcher.stop)
        return result

    def process(self, command, *args, **kwargs):
        self.calls.append(command)
        if 'preflight' in command:
            return SimpleNamespace(returncode=0, stdout=yaml.safe_dump({'live_ready': self.sdk_ready}))
        return SimpleNamespace(returncode=0, stdout='')

    def setup(self, root, config, pre_start=None):
        self.assertEqual(root, self.root)
        self.assertEqual(config['_profile'], self.parent / 'own-profile')
        self.assertIsNotNone(pre_start)
        pre_start()
        self.calls.append(['service-start'])
        return {'runner': deepcopy(self.expected_runner)}

    def test_start_applies_config_checks_both_authorizations_and_does_not_enable_research(self):
        config = yaml.safe_load(self.local.read_text())
        config['models']['review'] = 'fixture-new-review'
        self.local.write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False))
        state = self.root / workbench.STATE
        state.write_text('schema_version: 1\nusage_months: {2026-10: 86}\nselected_identity_keys: [fixture]\n')
        before = state.read_bytes(), self.local.read_bytes()
        result = workbench.start(self.root)
        self.assertEqual(result['status'], 'started')
        self.assertFalse(result['research_enabled'])
        self.assertEqual(result['model_calls'], 0)
        self.assertEqual((state.read_bytes(), self.local.read_bytes()), before)
        generated = yaml.safe_load((self.root / 'config/cycles/default.yaml').read_text())
        self.assertEqual(generated['models']['review'], 'fixture-new-review')
        self.client.infer.assert_not_called()
        self.assertIn(['gh', 'auth', 'status', '--hostname', 'github.com'], self.calls)
        self.api.assert_called_once_with(self.root, 'repos/fixture-owner/researchdesk')
        preflight = next(command for command in self.calls if 'preflight' in command)
        self.assertEqual(preflight[0], str(self.parent / 'runtime/bin/python'))
        self.assertLess(self.calls.index(preflight), self.calls.index(['service-start']))
        gate = ['gh', 'variable', 'set', 'RESEARCHDESK_DEPLOYED', '--repo',
                'fixture-owner/researchdesk', '--body', 'true']
        self.assertIn(gate, self.calls)
        self.assertLess(self.calls.index(['service-start']), self.calls.index(gate))
        self.assertTrue(result['github_deployment_gate'])
        marker = self.root / 'config/local/deployment-started-at.json'
        self.assertIn('+00:00', json.loads(marker.read_text())['started_at'])
        self.assertEqual(stat.S_IMODE(marker.stat().st_mode), 0o600)
        first = marker.read_bytes()
        workbench.start(self.root)
        self.assertEqual(marker.read_bytes(), first, 'restarting must not reset the activation/catchup horizon')

    def test_authorization_and_missing_models_stop_before_registration(self):
        self.client.status.return_value['plan_permission'] = False
        with self.assertRaisesRegex(store.OfflineError, 'chatgpt_login'):
            workbench.start(self.root)
        self.client.models.assert_not_called()
        self.setup_runner.assert_not_called()
        self.client.status.return_value['plan_permission'] = True
        self.client.models.return_value = [{'slug': 'gpt-6.1-sol'}]
        with self.assertRaisesRegex(store.OfflineError, 'models_unavailable'):
            workbench.start(self.root)
        self.setup_runner.assert_not_called()

    def test_github_permission_and_blocked_sdk_do_not_start_service(self):
        self.api.return_value = {'permissions': {'admin': False}}
        with self.assertRaisesRegex(store.OfflineError, 'runner_admin'):
            workbench.start(self.root)
        self.setup_runner.assert_not_called()
        self.api.return_value = {'permissions': {'admin': True}}
        self.sdk_ready = False
        with self.assertRaisesRegex(runner.RunnerError, 'runtime_not_ready'):
            workbench.start(self.root)
        self.assertNotIn(['service-start'], self.calls)
        self.assertFalse((self.root / 'config/local/deployment-started-at.json').exists())
        self.assertFalse(any('RESEARCHDESK_DEPLOYED' in command for command in self.calls))

    def test_deployment_gate_failure_is_not_reported_as_success_or_initialized(self):
        def fail_gate(command, *args, **kwargs):
            if 'RESEARCHDESK_DEPLOYED' in command:
                self.assertIn(['service-start'], self.calls)
                raise runner.RunnerError('github_deployment_gate_activation_failed')
            return self.process(command, *args, **kwargs)
        self.run_process.side_effect = fail_gate
        with self.assertRaisesRegex(runner.RunnerError, 'deployment_gate_activation_failed'):
            workbench.start(self.root)
        self.assertFalse((self.root / 'config/local/deployment-started-at.json').exists())
        self.client.infer.assert_not_called()


class DeploymentEnvironment(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='researchdesk-runner-env-tests-')
        self.addCleanup(temporary.cleanup)
        self.parent = Path(temporary.name).resolve()
        self.root, self.directory = self.parent / 'workbench', self.parent / 'runner'
        self.root.mkdir()
        self.directory.mkdir()
        self.config = {'_directory': self.directory, '_venv': self.parent / 'runtime'}

    def test_binding_is_owner_only_persistent_and_preserves_other_runner_settings(self):
        environment = self.directory / '.env'
        environment.write_text('KEEP_THIS=unchanged\nhttps_proxy=http://fixture.invalid:7890\n')
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertTrue(runner._sync_deployment_environment(self.root, self.config))
            first = environment.read_bytes()
            self.assertFalse(runner._sync_deployment_environment(self.root, self.config))
        self.assertEqual(environment.read_bytes(), first)
        text = environment.read_text()
        self.assertIn('KEEP_THIS=unchanged\n', text)
        self.assertIn('https_proxy=http://fixture.invalid:7890\n', text)
        self.assertIn('RESEARCHDESK_WORKBENCH_ROOT=' + str(self.root) + '\n', text)
        self.assertIn('RESEARCHDESK_RUNTIME_PYTHON=' + str(self.parent / 'runtime/bin/python'), text)
        self.assertEqual(stat.S_IMODE(environment.stat().st_mode), 0o600)
        other = self.parent / 'other-workbench'
        with self.assertRaisesRegex(runner.RunnerError, 'binding_mismatch'):
            runner._sync_deployment_environment(other, self.config)
        self.assertEqual(environment.read_bytes(), first)

    def test_environment_rejects_symlinks_and_line_injection(self):
        (self.directory / '.env').symlink_to(self.parent / 'elsewhere')
        with self.assertRaisesRegex(runner.RunnerError, 'symlink'):
            runner._sync_deployment_environment(self.root, self.config)
        (self.directory / '.env').unlink()
        with self.assertRaisesRegex(runner.RunnerError, 'value_invalid'):
            runner._sync_environment(self.directory, {'RESEARCHDESK_WORKBENCH_ROOT': 'one\nTOKEN=bad'})
        self.assertFalse((self.directory / '.env').exists())

    def test_setup_installs_sdk_before_preflight_and_binds_before_starting(self):
        config = dict(self.config, runner={'name': 'fixture', 'labels': ['researchdesk']})
        config['_venv'].mkdir()
        (config['_venv'] / 'pyvenv.cfg').write_text('fixture\n')
        (self.directory / '.runner').write_text(json.dumps({
            'agentName': 'fixture', 'gitHubUrl': 'https://github.com/fixture-owner/researchdesk'}))
        calls = []
        def run(command, *args, **kwargs):
            calls.append(command)
            return SimpleNamespace(returncode=0, stdout='')
        def preflight():
            self.assertIn('requirements-codex.txt', calls[0][-1])
            self.assertTrue((self.directory / '.env').is_file())
            calls.append(['sdk-preflight'])
        with mock.patch.dict(os.environ, {}, clear=True), \
                mock.patch.object(runner.os, 'getuid', return_value=os.getuid() or 501), \
                mock.patch.object(runner.shutil, 'which', return_value='/fixture/tool'), \
                mock.patch.object(runner, '_platform', return_value=('osx', 'arm64')), \
                mock.patch.object(runner, '_repository', return_value='fixture-owner/researchdesk'), \
                mock.patch.object(runner, '_run', side_effect=run), \
                mock.patch.object(runner, '_install_package'), \
                mock.patch.object(runner, '_service_state', side_effect=['not_installed', 'stopped']), \
                mock.patch.object(runner, 'doctor', return_value={'runner': {'service': 'running'}}):
            runner.setup(self.root, config, pre_start=preflight)
        self.assertLess(calls.index(['sdk-preflight']), calls.index(['./svc.sh', 'start']))


if __name__ == '__main__':
    unittest.main()
