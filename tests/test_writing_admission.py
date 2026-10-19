"""Create-only Writing admission in disposable, locally synchronized vaults.

The fixture reuses genuine Research/Insight admission proof and the real page
confirmation code. Only the six Writing responses are simulated. Every model
entry point and external connection is prohibited; the user's vault is read
only and all writes and local Git remotes live in temporary directories.
"""

import importlib
from pathlib import Path
import re
import subprocess
import sys
import unittest
from unittest import mock

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_writing_member as fixture

store = fixture.store
confirmation = fixture.confirmation
TOPIC = fixture.TOPIC


class WritingAdmission(unittest.TestCase):
    # Reuse fixture setup/helpers without inheriting its independent test suite.
    git = fixture.RealMemberWriting.git
    hashes = fixture.RealMemberWriting.hashes
    confirm = fixture.RealMemberWriting.confirm
    run_writing = fixture.RealMemberWriting.run_writing
    complete_synced_batch = fixture.RealMemberWriting.complete_synced_batch

    @classmethod
    def setUpClass(cls):
        fixture.RealMemberWriting.setUpClass.__func__(cls)
        cls.formal = importlib.import_module('researchdesk_writing_admission')

    def setUp(self):
        fixture.RealMemberWriting.setUp(self)
        prohibited = AssertionError('Admission must not construct or contact a membership backend')
        for name in ('__init__', 'status', 'models', 'infer'):
            patcher = mock.patch.object(fixture.membership.MembershipClient, name,
                                        side_effect=prohibited)
            patcher.start()
            self.addCleanup(patcher.stop)

    def admit(self, record, root=None, **options):
        return self.formal.run(root or self.root, record['id'], **options)

    def view(self, record, root=None):
        return self.formal.inspect(root or self.root, TOPIC, record['id'])

    def assert_unchanged(self, before, root=None):
        root = root or self.root
        for relative, sha in before.items():
            self.assertEqual(store.digest((root / relative).read_bytes()), sha, relative)

    def fork(self, name):
        """Each gate scenario has its own local main and bare origin."""
        origin, root = self.root.parent / (name + '.git'), self.root.parent / name
        for command in (['git', 'clone', '--quiet', '--bare', str(self.origin), str(origin)],
                        ['git', 'clone', '--quiet', str(origin), str(root)]):
            subprocess.run(command, check=True, capture_output=True)
        self.git_at(root, 'config', 'user.name', 'ResearchDesk isolated admission test')
        self.git_at(root, 'config', 'user.email', 'admission-test@example.invalid')
        return root

    def git_at(self, root, *arguments):
        return subprocess.run(['git', '-C', str(root), *arguments], check=True,
                              capture_output=True, text=True).stdout.strip()

    def commit_at(self, root, message):
        self.git_at(root, 'add', '.')
        self.git_at(root, 'commit', '-m', message)
        self.git_at(root, 'push', 'origin', 'main')

    def test_reviewed_three_stage_admission_preserves_history_and_replays_without_calls(self):
        record, result = self.complete_synced_batch()
        before = self.hashes()
        admitted = self.admit(record)
        current = self.view(record)
        self.assertEqual(current['status'], 'accepted')
        self.assertTrue(current['production_accepted'])
        self.assertFalse(current['publish_authorized'])
        self.assertEqual(current['new_model_calls'], 0)
        self.assertEqual({item['stage'] for item in current['documents']}, set(self.writing.STAGES))
        self.assertEqual(len(current['documents']), 3)
        for item in current['documents']:
            self.assertTrue(item['path'].startswith('articles/agent-memory/'))
            target = self.root / item['path']
            text = target.read_text(encoding='utf-8')
            _, frontmatter, body = text.split('---', 2)
            metadata = yaml.safe_load(frontmatter)
            self.assertTrue(metadata['production_accepted'])
            self.assertFalse(metadata['publish_authorized'])
            self.assertNotIn('> TEST', body)
            self.assertIn('https://', body)
            for link in re.findall(r'\]\(([^)]+)\)', body):
                if '://' not in link:
                    resolved = (target.parent / link.split('#', 1)[0]).resolve()
                    self.assertTrue(resolved.is_file(), link)
                    self.assertNotIn('test', resolved.relative_to(self.root).parts, link)
        self.assert_unchanged(before)
        after = self.hashes()
        replay = self.admit(record)
        self.assertTrue(replay['cached'])
        self.assertEqual(self.hashes(), after)
        self.assertEqual(len(self.client.calls), result['completed_calls'])
        self.assertEqual(admitted['new_model_calls'], 0)

    def test_conflicts_symlinks_and_human_edits_are_preserved(self):
        record, _ = self.complete_synced_batch()
        batch = 'writing-' + record['id']
        target = self.root / ('articles/%s/%s-outline.md' % (TOPIC, batch))
        target.parent.mkdir(parents=True, exist_ok=True)
        manual = '# 人工撰写，正式准入不能覆盖。\n'.encode()
        target.write_bytes(manual)
        with self.assertRaises(store.OfflineError):
            self.admit(record)
        self.assertEqual(target.read_bytes(), manual)
        self.assertFalse(self.view(record)['documents'])
        # Cleanup is confined to this test's disposable vault.
        target.unlink()
        external = self.root.parent / 'outside-human-note.md'
        external.write_bytes(manual)
        target.symlink_to(external)
        with self.assertRaises(store.OfflineError):
            self.admit(record)
        self.assertTrue(target.is_symlink())
        self.assertEqual(external.read_bytes(), manual)
        target.unlink()
        self.admit(record)
        target.write_bytes(target.read_bytes() + manual)
        changed = target.read_bytes()
        with self.assertRaises(store.OfflineError):
            self.admit(record)
        self.assertEqual(target.read_bytes(), changed)
        self.assertEqual(self.view(record)['status'], 'integrity_changed')
        self.assertEqual(len(self.client.calls), 6)

    def test_unsynced_revoked_changed_review_or_changed_test_cannot_enter_formal_library(self):
        record = self.confirm()
        result = self.run_writing(record)
        with self.assertRaises(store.OfflineError):
            self.admit(record)
        self.assertFalse(self.view(record)['documents'])
        self.commit_at(self.root, 'Sync reviewed Writing before isolated admission checks')
        for scenario in ('changed_review', 'changed_test', 'revoked'):
            with self.subTest(scenario=scenario):
                root = self.fork(scenario)
                if scenario == 'changed_review':
                    relative = ('reports/test/%s/writing-runs/writing-%s/'
                                'stages/candidate.yaml' % (TOPIC, record['id']))
                    path = root / relative
                    value = yaml.safe_load(path.read_text(encoding='utf-8'))
                    value['review']['decision'] = 'reject'
                    payload = yaml.safe_dump(value, allow_unicode=True, sort_keys=False).encode()
                    path.write_bytes(payload)
                    path.with_name(path.name + '.sha256').write_text(store.digest(payload) + '\n')
                    self.commit_at(root, 'Isolated changed review with matching checksum')
                elif scenario == 'changed_test':
                    path = root / next(iter(result['output_hashes']))
                    path.write_bytes(path.read_bytes() + '\n人工测试备注：请保留。\n'.encode())
                    self.commit_at(root, 'Isolated human edit to test article')
                else:
                    app = confirmation.ConfirmationStore(root, confirmation.load_config(root))
                    app.revoke(record['id'], '隔离验收撤回，不影响用户确认记录')
                before = {p.relative_to(root).as_posix(): p.read_bytes()
                          for p in root.rglob('*') if p.is_file() and '.git' not in p.relative_to(root).parts}
                with self.assertRaises((store.OfflineError, self.formal.job.JobError)):
                    self.admit(record, root=root)
                for relative, content in before.items():
                    self.assertEqual((root / relative).read_bytes(), content, relative)
                self.assertFalse(self.view(record, root=root)['documents'])
        self.assertEqual(len(self.client.calls), 6)

    def test_interrupted_create_only_admission_resumes_saved_plan(self):
        record, _ = self.complete_synced_batch()
        before = self.hashes()
        with self.assertRaises(store.SimulatedInterruption):
            self.admit(record, fail_after='after_first_output')
        self.assert_unchanged(before)
        partial = self.hashes()
        replay = self.admit(record)
        self.assertEqual(self.view(record)['status'], 'accepted')
        self.assert_unchanged(partial)
        self.assertEqual(replay['new_model_calls'], 0)
        self.assertEqual(len(self.client.calls), 6)

    def test_page_exposes_verified_formal_history_and_blocks_modified_drafts(self):
        record, _ = self.complete_synced_batch()
        self.admit(record)
        self.commit_at(self.root, 'Save isolated formal three-stage Writing result')
        entry = next(item for item in self.app.list_confirmations() if item['id'] == record['id'])
        formal = entry['writing']['formal']
        self.assertEqual(formal['status'], 'accepted')
        self.assertEqual(len(formal['documents']), 3)
        self.assertEqual(len(entry['writing']['documents']), 3)
        target = formal['documents'][0]['path']
        document = self.app.document(target)
        self.assertEqual(document['path'], target)
        self.assertEqual(document['text'], (self.root / target).read_text(encoding='utf-8'))
        with self.assertRaises(confirmation.ConfirmationError):
            self.app.start_writing(record['id'])
        # Expanding a later admission policy cannot erase verified history or
        # silently rebind the original create-only admission to a new policy.
        policy_path = self.root / 'config/writing_admission.yaml'
        original_policy = policy_path.read_bytes()
        expanded_policy = yaml.safe_load(original_policy)
        expanded_policy['topics'].append('agent-rl')
        policy_path.write_text(yaml.safe_dump(expanded_policy, allow_unicode=True, sort_keys=False),
                               encoding='utf-8')
        entry = next(item for item in self.app.list_confirmations() if item['id'] == record['id'])
        self.assertEqual(entry['writing']['formal']['status'], 'accepted')
        self.assertEqual(self.app.document(target), document)
        with self.assertRaises(store.OfflineError):
            self.admit(record)
        policy_path.write_bytes(original_policy)
        # Reading formal history after withdrawal grants no new execution.
        self.app.revoke(record['id'], '隔离验收撤回后保留历史稿件')
        self.assertEqual(self.app.document(target), document)
        path = self.root / target
        changed = path.read_bytes() + '\n人工正式改稿：保留且不重写。\n'.encode()
        path.write_bytes(changed)
        entry = next(item for item in self.app.list_confirmations() if item['id'] == record['id'])
        self.assertEqual(entry['writing']['formal']['status'], 'integrity_changed')
        self.assertFalse(entry['writing']['formal']['documents'])
        with self.assertRaises(confirmation.ConfirmationError):
            self.app.document(target)
        self.assertEqual(path.read_bytes(), changed)
        self.assertEqual(len(self.client.calls), 6)


if __name__ == '__main__':
    unittest.main()
