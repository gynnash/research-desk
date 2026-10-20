"""Offline recovery transport checks; all Git, process and network I/O is blocked.

These tests isolate the trusted worker/publisher plumbing. The recovery module's
lineage and request validation are exercised separately by its own tests.
"""

import contextlib
import io
import json
from pathlib import Path
import socket
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock


REPOSITORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY / 'scripts'))
import researchdesk_admission as admission
import researchdesk_cycle as cycle
import researchdesk_job as job
import researchdesk_offline as store
import researchdesk_runner as runtime


TOPIC = 'custom-topic'
ORIGINAL = 'original-cycle'
RECOVERY = ORIGINAL + '-recovery-1'
CONFIG = 'config/cycles/custom-topic.yaml'
ORIGINAL_RECEIPT = 'reports/test/%s/cycles/%s/receipt.yaml' % (TOPIC, ORIGINAL)
RECOVERY_BASE = 'reports/test/%s/cycles/%s' % (TOPIC, RECOVERY)


class RecoveryJobTransfer(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='researchdesk-recovery-job-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve() / 'vault'
        self.root.mkdir()
        self.state = self.root.parent / 'state'
        self.artifact = self.root.parent / 'artifact'
        store.save_yaml(self.root, ORIGINAL_RECEIPT, {'immutable': 'original receipt'})
        (self.root / CONFIG).parent.mkdir(parents=True)
        (self.root / CONFIG).write_text('topic: custom-topic\n')
        self.original_bytes = {relative: (self.root / relative).read_bytes()
                               for relative in (CONFIG, ORIGINAL_RECEIPT, ORIGINAL_RECEIPT + '.sha256')}
        self.baseline = {relative: job.sha(content) for relative, content in self.original_bytes.items()}
        python = self.root.parent / 'venv/bin/python'
        python.parent.mkdir(parents=True)
        python.write_text('offline placeholder\n')
        self.host = {'_venv': python.parent.parent, '_profile': self.root.parent / 'existing-profile'}
        self.untracked = []
        self.staged = []
        self.dirty = b''
        self.recovery = SimpleNamespace(
            requested=mock.Mock(return_value=RECOVERY), verify_lineage=mock.Mock())
        self.addCleanup(mock.patch.stopall)
        mock.patch.dict(sys.modules, {'researchdesk_recovery': self.recovery}).start()
        mock.patch.dict('os.environ', {'GITHUB_ACTIONS': 'false'}).start()
        mock.patch.object(cycle, 'load_config', return_value={'topic': TOPIC}).start()
        mock.patch.object(runtime, 'load_config', return_value=self.host).start()
        self.tracked = mock.patch.object(job, 'tracked', return_value=self.baseline).start()
        self.git = mock.patch.object(job, 'git', side_effect=self.fake_git).start()
        self.process = mock.patch.object(job.subprocess, 'run',
                                         return_value=SimpleNamespace(returncode=0, stdout='')).start()
        self.enabled = mock.patch.object(job, 'admission_enabled', return_value=False).start()
        self.admission = mock.patch.object(admission, 'run', return_value={'status': 'accepted'}).start()
        mock.patch.object(socket, 'create_connection', side_effect=AssertionError('Network prohibited')).start()
        mock.patch.object(socket.socket, 'connect', side_effect=AssertionError('Network prohibited')).start()
        self.addCleanup(self.assert_original_bytes_unchanged)

    def assert_original_bytes_unchanged(self):
        self.assertEqual(self.original_bytes, {relative: (self.root / relative).read_bytes()
                                              for relative in self.original_bytes})

    def fake_git(self, root, *arguments):
        if arguments == ('rev-parse', 'HEAD'):
            return b'offline-base-commit\n'
        if arguments == ('diff', '--name-only'):
            return self.dirty
        if arguments == ('diff', '--cached', '--name-only'):
            return b''
        if arguments == ('ls-files', '--others', '--exclude-standard', '-z'):
            return b'\0'.join(path.encode() for path in self.untracked)
        if arguments == ('diff', '--cached', '--name-only', '-z'):
            return b'\0'.join(path.encode() for path in self.staged)
        if arguments[:2] == ('add', '--'):
            self.staged = list(arguments[2:])
            return b''
        if arguments[0] in {'config', 'commit', 'push'}:
            return b''
        raise AssertionError('Unexpected Git operation: %r' % (arguments,))

    def execute(self, operation='recover', fail_after=None):
        with contextlib.redirect_stdout(io.StringIO()) as output:
            result = job.execute(self.root, self.state, CONFIG, ORIGINAL, operation, fail_after)
        return result, json.loads(output.getvalue())

    def context(self):
        return json.loads((self.state / 'context.json').read_text())

    def checkpoint(self, name='recovery.yaml', value=None):
        relative = RECOVERY_BASE + '/' + name
        store.save_yaml(self.root, relative, value or {'offline': 'recovery checkpoint'})
        return [relative, relative + '.sha256']

    def receipt(self, research='test_accepted', insight='test_accepted'):
        return self.checkpoint('receipt.yaml', {'stages': {
            'research': {'status': research}, 'insight': {'status': insight}}})

    def artifact_for(self, files=None, operation='recover'):
        files = files or {RECOVERY_BASE + '/recovery.yaml': b'offline: recovery checkpoint\n'}
        self.artifact.mkdir()
        hashes = {}
        for relative, content in files.items():
            target = self.artifact / 'payload' / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
            hashes[relative] = job.sha(content)
            if relative.endswith('.yaml'):
                sidecar = relative + '.sha256'
                digest = (job.sha(content) + '\n').encode()
                (self.artifact / 'payload' / sidecar).write_bytes(digest)
                hashes[sidecar] = job.sha(digest)
        manifest = {'schema_version': 1, 'topic': TOPIC, 'cycle_id': RECOVERY,
                    'operation': operation, 'base_commit': 'offline-base-commit',
                    'baseline_blobs': self.baseline, 'files': hashes}
        (self.artifact / 'manifest.json').write_text(json.dumps(manifest))
        return manifest

    def apply(self):
        with contextlib.redirect_stdout(io.StringIO()) as output:
            job.apply(self.root, self.artifact)
        return json.loads(output.getvalue())

    def assert_no_publication(self):
        self.assertFalse(any(call.args[1] in {'commit', 'push'} for call in self.git.call_args_list))

    def test_explicit_recovery_uses_existing_runtime_and_original_input_id(self):
        result, summary = self.execute()
        self.assertEqual(result, 0)
        self.recovery.requested.assert_called_once_with(self.root, CONFIG, ORIGINAL)
        self.assertEqual(self.context()['cycle_id'], RECOVERY)
        self.assertEqual(self.context()['operation'], 'recover')
        self.assertEqual(self.context()['baseline_blobs'], self.baseline)
        self.assertEqual(self.process.call_args.args[0], [
            str(self.host['_venv'] / 'bin/python'), str(self.root / 'scripts/researchdesk_recovery.py'),
            '--root', str(self.root), '--config', CONFIG, '--cycle-id', ORIGINAL,
            '--profile', str(self.host['_profile'])])
        self.assertEqual(summary['cycle_id'], RECOVERY)
        self.assertEqual(summary['admission'], 'not_requested')

    def test_original_run_routes_only_when_exact_request_is_present(self):
        self.execute('run')
        self.assertEqual(self.context()['operation'], 'recover')
        self.assertEqual(self.context()['cycle_id'], RECOVERY)
        self.assertIn(str(self.root / 'scripts/researchdesk_recovery.py'), self.process.call_args.args[0])

    def test_original_research_interruption_is_rejected_before_recovery_context(self):
        with self.assertRaisesRegex(job.JobError, 'recovery_interruption_must_follow_new_review'):
            job.execute(self.root, self.state, CONFIG, ORIGINAL, 'run', fail_after='after_research')
        self.assertFalse(self.state.exists())
        self.process.assert_not_called()

    def test_recovery_review_interruption_reaches_bounded_runner(self):
        with contextlib.redirect_stdout(io.StringIO()):
            job.execute(self.root, self.state, CONFIG, ORIGINAL, 'run', fail_after='after_review')
        self.assertEqual(self.process.call_args.args[0][-2:], ['--fail-after', 'after_review'])

    def test_normal_run_without_request_keeps_original_cycle(self):
        self.recovery.requested.return_value = None
        self.execute('run')
        self.assertEqual(self.context()['operation'], 'run')
        self.assertEqual(self.context()['cycle_id'], ORIGINAL)
        command = self.process.call_args.args[0]
        self.assertEqual(command[1], str(self.root / 'scripts/researchdesk_cycle.py'))
        self.assertIn('run', command)
        self.assertEqual(command[command.index('--cycle-id') + 1], ORIGINAL)

    def test_explicit_recovery_without_request_fails_before_execution(self):
        self.recovery.requested.return_value = None
        with self.assertRaisesRegex(job.JobError, 'recovery_request_required'):
            self.execute()
        self.assertFalse(self.state.exists())
        self.process.assert_not_called()

    def test_invalid_request_hashes_cannot_start_recovery(self):
        self.recovery.requested.side_effect = store.OfflineError('bound original changed')
        with self.assertRaisesRegex(store.OfflineError, 'bound original changed'):
            self.execute('run')
        self.assertFalse(self.state.exists())
        self.process.assert_not_called()

    def test_accepted_recovery_uses_same_admission_gate_with_new_cycle_id(self):
        self.receipt()
        self.enabled.return_value = True
        result, summary = self.execute('run')
        self.assertEqual(result, 0)
        self.assertEqual(summary['admission'], 'accepted')
        self.assertEqual(len(self.process.call_args_list), 2)
        command = self.process.call_args_list[1].args[0]
        self.assertIn('admit', command)
        self.assertEqual(command[command.index('--cycle-id') + 1], RECOVERY)

    def test_incomplete_recovery_does_not_admit(self):
        self.receipt(insight='blocked')
        self.enabled.return_value = True
        _, summary = self.execute()
        self.assertEqual(summary['admission'], 'no_accepted_bundle')
        self.assertEqual(self.process.call_count, 1)

    def test_failed_recovery_preserves_recovery_context_without_admission(self):
        self.process.return_value.returncode = 1
        self.enabled.return_value = True
        result, summary = self.execute()
        self.assertEqual(result, 1)
        self.assertEqual(summary['admission'], 'not_requested')
        self.assertEqual(self.context()['cycle_id'], RECOVERY)
        self.assertEqual(self.process.call_count, 1)

    def test_only_recovery_untracked_checkpoints_are_resumable(self):
        self.untracked = self.checkpoint()
        self.execute()
        self.assertEqual(self.context()['cycle_id'], RECOVERY)

    def test_original_cycle_untracked_files_cannot_enter_recovery_transfer(self):
        self.untracked = [ORIGINAL_RECEIPT, ORIGINAL_RECEIPT + '.sha256']
        with self.assertRaisesRegex(job.JobError, 'unpublished_other_cycle_files_require_recovery'):
            self.execute()
        self.process.assert_not_called()

    def test_export_scopes_new_files_and_preserves_baseline(self):
        self.execute()
        self.untracked = self.checkpoint()
        with contextlib.redirect_stdout(io.StringIO()):
            job.export(self.root, self.state, self.artifact)
        manifest = json.loads((self.artifact / 'manifest.json').read_text())
        self.assertEqual(manifest['cycle_id'], RECOVERY)
        self.assertEqual(manifest['operation'], 'recover')
        self.assertEqual(set(manifest['files']), set(self.untracked))
        self.assertNotIn(ORIGINAL_RECEIPT, manifest['files'])

    def test_changed_tracked_input_blocks_export(self):
        self.execute()
        self.dirty = ORIGINAL_RECEIPT.encode()
        with self.assertRaisesRegex(job.JobError, 'tracked_inputs_changed_preserve_worker'):
            job.export(self.root, self.state, self.artifact)
        self.assertFalse(self.artifact.exists())

    def test_changed_tracked_input_cannot_start_recovery(self):
        self.dirty = ORIGINAL_RECEIPT.encode()
        with self.assertRaisesRegex(job.JobError, 'worker_has_modified_tracked_files'):
            self.execute()
        self.process.assert_not_called()
        self.assertFalse(self.state.exists())

    def test_apply_checks_lineage_even_without_admission_plan(self):
        self.artifact_for()
        def inspect_lineage(root, topic, cycle_id):
            self.assertTrue((root / RECOVERY_BASE / 'recovery.yaml').is_file())
            self.assertEqual((topic, cycle_id), (TOPIC, RECOVERY))
            self.process.assert_not_called()
        self.recovery.verify_lineage.side_effect = inspect_lineage
        result = self.apply()
        self.recovery.verify_lineage.assert_called_once_with(self.root, TOPIC, RECOVERY)
        self.assertFalse(result['production_accepted'])
        self.admission.assert_not_called()

    def test_invalid_lineage_blocks_admission_and_publication(self):
        self.artifact_for()
        self.recovery.verify_lineage.side_effect = store.OfflineError('lineage changed')
        with self.assertRaisesRegex(store.OfflineError, 'lineage changed'):
            self.apply()
        self.admission.assert_not_called()
        self.process.assert_not_called()
        self.assert_no_publication()

    def test_recovery_admission_runs_only_after_publisher_lineage_check(self):
        plan_path = 'reports/%s/admissions/%s/plan.yaml' % (TOPIC, RECOVERY)
        self.artifact_for({RECOVERY_BASE + '/recovery.yaml': b'offline: checkpoint\n',
                           plan_path: b'files: {}\n'})
        self.enabled.return_value = True
        def admit_after_lineage(root, topic, cycle_id):
            self.recovery.verify_lineage.assert_called_once_with(root, topic, cycle_id)
            return {'status': 'accepted'}
        self.admission.side_effect = admit_after_lineage
        result = self.apply()
        self.admission.assert_called_once_with(self.root, TOPIC, RECOVERY)
        self.assertTrue(result['production_accepted'])

    def test_recovery_admission_still_requires_enabled_policy(self):
        plan_path = 'reports/%s/admissions/%s/plan.yaml' % (TOPIC, RECOVERY)
        self.artifact_for({RECOVERY_BASE + '/recovery.yaml': b'offline: checkpoint\n',
                           plan_path: b'files: {}\n'})
        with self.assertRaisesRegex(job.JobError, 'formal_admission_disabled'):
            self.apply()
        self.recovery.verify_lineage.assert_called_once()
        self.admission.assert_not_called()
        self.assert_no_publication()

    def test_original_checkpoint_cannot_be_copied_or_overwritten_by_recovery(self):
        self.artifact_for({ORIGINAL_RECEIPT: b'immutable: changed\n'})
        with self.assertRaisesRegex(job.JobError, 'transfer_outside_cycle_paths'):
            self.apply()
        self.recovery.verify_lineage.assert_not_called()
        self.assert_no_publication()

    def test_changed_publisher_baseline_blocks_recovery_before_copy(self):
        self.artifact_for()
        self.tracked.return_value = dict(self.baseline, **{CONFIG: 'changed-blob'})
        with self.assertRaisesRegex(job.JobError, 'main_inputs_changed_preserve_artifact'):
            self.apply()
        self.assertFalse((self.root / RECOVERY_BASE).exists())
        self.recovery.verify_lineage.assert_not_called()
        self.assert_no_publication()

    def test_replayed_transfer_adds_nothing_and_preserves_recovery_checkpoint(self):
        self.artifact_for()
        first = self.apply()
        saved = (self.root / RECOVERY_BASE / 'recovery.yaml').read_bytes()
        self.git.reset_mock()
        second = self.apply()
        self.assertGreater(first['saved_files'], 0)
        self.assertEqual(second['saved_files'], 0)
        self.assertEqual((self.root / RECOVERY_BASE / 'recovery.yaml').read_bytes(), saved)
        self.assertEqual(self.recovery.verify_lineage.call_count, 2)
        self.assert_no_publication()

    def test_direct_admit_checks_existing_recovery_manifest(self):
        self.checkpoint()
        self.enabled.return_value = True
        with contextlib.redirect_stdout(io.StringIO()):
            job.admit(self.root, CONFIG, RECOVERY)
        self.recovery.verify_lineage.assert_called_once_with(self.root, TOPIC, RECOVERY)
        self.admission.assert_called_once_with(self.root, TOPIC, RECOVERY)

    def test_direct_admit_cannot_bypass_failed_recovery_lineage(self):
        self.checkpoint()
        self.enabled.return_value = True
        self.recovery.verify_lineage.side_effect = store.OfflineError('lineage changed')
        with self.assertRaisesRegex(store.OfflineError, 'lineage changed'):
            job.admit(self.root, CONFIG, RECOVERY)
        self.admission.assert_not_called()


if __name__ == '__main__':
    unittest.main()
