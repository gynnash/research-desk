"""Explicit cleanup exceptions preserve old hashes without hiding changed notes."""

import hashlib
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import admission
import batch
import offline as store
import retired
import writing_member_inputs as writing


NOTE = 'reports/test/agent-memory/old-offline/acceptance.md'


class RetiredNotes(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.expected = store.digest(b'old fictional acceptance\n')
        (self.root / 'config').mkdir()
        self.register()

    def register(self, path=NOTE, sha256=None):
        value = {'schema_version': 1, 'notes': {
            path: {'sha256': sha256 or self.expected, 'reason': 'Explicit cleanup of historical fixture note'}}}
        (self.root / retired.CONFIG).write_text(yaml.safe_dump(value), encoding='utf-8')

    def test_missing_exact_note_preserves_original_proof_hash(self):
        baseline = {NOTE: self.expected}
        batch.verify_notes(self.root, baseline)
        admission._verify_hashes(self.root, baseline)
        self.assertEqual(admission._hashes(self.root, [NOTE]), baseline)
        self.assertFalse((self.root / NOTE).exists())

    def test_wrong_hash_and_unregistered_missing_note_fail(self):
        for baseline in ({NOTE: '0' * 64}, {NOTE.replace('acceptance', 'other'): self.expected}):
            with self.subTest(baseline=baseline):
                with self.assertRaises(store.OfflineError):
                    batch.verify_notes(self.root, baseline)
                with self.assertRaises(store.OfflineError):
                    admission._verify_hashes(self.root, baseline)

    def test_present_modified_note_is_never_exempt(self):
        target = self.root / NOTE
        target.parent.mkdir(parents=True)
        target.write_text('human modification', encoding='utf-8')
        self.assertIsNone(retired.missing_hash(self.root, NOTE, self.expected))
        for verifier in (batch.verify_notes, admission._verify_hashes):
            with self.assertRaises(store.OfflineError):
                verifier(self.root, {NOTE: self.expected})

    def test_symlink_and_symlink_parent_are_rejected(self):
        target = self.root / NOTE
        target.parent.mkdir(parents=True)
        target.symlink_to(self.root / 'missing-target')
        with self.assertRaises(store.OfflineError):
            batch.verify_notes(self.root, {NOTE: self.expected})
        target.unlink()
        target.parent.rmdir()
        target.parent.symlink_to(self.root / 'missing-directory')
        with self.assertRaises(store.OfflineError):
            retired.missing_hash(self.root, NOTE, self.expected)

    def test_formal_wildcard_traversal_and_invalid_hash_registration_fail(self):
        for path, sha256 in (
                ('reports/agent-memory/formal.md', self.expected),
                ('reports/test/agent-memory/*.md', self.expected),
                ('reports/test/../formal.md', self.expected),
                (NOTE, 'not-a-hash')):
            with self.subTest(path=path, sha256=sha256):
                self.register(path, sha256)
                with self.assertRaises(store.OfflineError):
                    retired.missing_hash(self.root, NOTE, self.expected)

    def test_duplicate_registration_fails(self):
        (self.root / retired.CONFIG).write_text(
            'schema_version: 1\nnotes:\n  ' + NOTE + ': {}\n  ' + NOTE + ': {}\n', encoding='utf-8')
        with self.assertRaises(store.OfflineError):
            retired.missing_hash(self.root, NOTE, self.expected)

    def _git(self, remote_registered=True, deletion_committed=True):
        payload = (self.root / retired.CONFIG).read_bytes()
        blob = hashlib.sha1(b'blob ' + str(len(payload)).encode() + b'\0' + payload).hexdigest()
        index = ('100644 ' + blob + ' 0\t' + retired.CONFIG + '\0').encode()
        tree = ('100644 blob ' + blob + '\t' + retired.CONFIG + '\0').encode()
        old = ('100644 blob ' + 'a' * 40 + '\t' + NOTE + '\0').encode()

        def fake(root, *args):
            if args[0] == 'ls-files':
                return index
            if args[0] == 'ls-tree':
                if args[-1] == 'refs/remotes/origin/main' and not remote_registered:
                    return b''
                return tree if deletion_committed else tree + old
            if args == ('rev-parse', '--show-object-format'):
                return b'sha1\n'
            raise AssertionError(args)
        return fake

    def test_writing_requires_synced_registry_and_committed_deletion(self):
        with mock.patch.object(writing, '_git', side_effect=self._git()):
            writing._synced_hashes(self.root, {NOTE: self.expected})
        for fake in (self._git(remote_registered=False), self._git(deletion_committed=False)):
            with self.subTest(fake=fake), mock.patch.object(writing, '_git', side_effect=fake):
                with self.assertRaises(store.OfflineError):
                    writing._synced_hashes(self.root, {NOTE: self.expected})


if __name__ == '__main__':
    unittest.main()
