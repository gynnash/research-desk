"""Focused real-proof confirmation checks, entirely in disposable workbenches.

The admitted Research/Insight candidate, independent review, request ledger and
mechanical link-repair proof are copied byte for byte. Only Git transport uses a
local test publisher; neither a passing decision nor the provenance verifier is
replaced. No real topic in the user's vault is confirmed by these checks.
"""

import http.client
import importlib
import json
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest import mock

import yaml


REPOSITORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY / 'scripts'))
import researchdesk_membership as membership
import researchdesk_offline as store
import researchdesk_sources as sources

TOPIC = 'agent-memory'
CYCLE = 'cycle-agent-memory-gh-20261019'
CARD = 'formal-topic-agent-memory-%s-1' % CYCLE
BASE = 'reports/%s/admissions/%s' % (TOPIC, CYCLE)


class RealTopicConfirmation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = REPOSITORY / BASE / 'plan.yaml'
        if not path.is_file():
            raise unittest.SkipTest('本测试需要已有真实独立审阅及正式准入证明；不联网或伪造 pass 补建')
        cls.confirmation = importlib.import_module('researchdesk_confirmation')
        cls.plan = yaml.safe_load(path.read_text(encoding='utf-8'))

    def git(self, *arguments):
        return subprocess.run(['git', '-C', str(self.root), *arguments], check=True,
                              capture_output=True, text=True).stdout.strip()

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='researchdesk-confirmation-tests-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        # Copy precisely the existing immutable proof and its protected notes,
        # not fixture-generated approvals or the user's Git/Obsidian settings.
        shutil.copytree(REPOSITORY / 'config', self.root / 'config')
        paths = set(self.plan['input_hashes']) | set(self.plan['protected_notes']) | set(self.plan['output_hashes'])
        paths |= {path.relative_to(REPOSITORY).as_posix()
                  for path in (REPOSITORY / BASE).iterdir() if path.is_file()}
        for relative in list(paths):
            if (REPOSITORY / (relative + '.sha256')).is_file():
                paths.add(relative + '.sha256')
        for relative in sorted(paths):
            retired = importlib.import_module('researchdesk_retired')
            expected = self.plan['input_hashes'].get(relative, self.plan['protected_notes'].get(relative))
            if not (REPOSITORY / relative).exists() and retired.missing_hash(REPOSITORY, relative, expected):
                continue
            destination = self.root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(REPOSITORY / relative, destination)
        self.git('init', '-b', 'main')
        self.git('config', 'user.name', 'ResearchDesk isolated confirmation test')
        self.git('config', 'user.email', 'confirmation-test@example.invalid')
        self.git('add', '.')
        self.git('commit', '-m', 'Copy genuinely admitted topic and proof')
        self.published = []

        def local_publisher(root, new_files, message):
            self.assertEqual(Path(root).resolve(), self.root)
            self.published.append(tuple(new_files))
            self.git('add', '--', *new_files)
            self.git('commit', '-m', message)
            return True

        self.publisher = local_publisher
        self.config = self.confirmation.load_config(self.root)
        self.now = [1700000000.0]
        self.app = self.confirmation.ConfirmationStore(
            self.root, self.config, publisher=self.publisher, clock=lambda: self.now[0])
        self.original = self.hashes()
        for patcher in (
            mock.patch.object(membership.MembershipClient, 'infer', side_effect=AssertionError('Confirmation must not infer')),
            mock.patch.object(sources.SafeFetcher, 'fetch', side_effect=AssertionError('Confirmation must not fetch')),
        ):
            self.addCleanup(patcher.stop)
            patcher.start()
        # HTTP assertions may connect to the disposable loopback server only.
        original_connect = socket.socket.connect

        def loopback_only(connection, address):
            if not isinstance(address, tuple) or address[0] not in {'127.0.0.1', '::1', 'localhost'}:
                raise AssertionError('External network prohibited in confirmation acceptance')
            return original_connect(connection, address)

        network = mock.patch.object(socket.socket, 'connect', loopback_only)
        self.addCleanup(network.stop)
        network.start()

    def hashes(self):
        return {path.relative_to(self.root).as_posix(): store.digest(path.read_bytes())
                for path in self.root.rglob('*') if path.is_file() and '.git' not in path.relative_to(self.root).parts}

    def assert_original_unchanged(self):
        for relative, expected in self.original.items():
            self.assertEqual(store.digest((self.root / relative).read_bytes()), expected, relative)

    def preview(self):
        return self.app.preview(CARD, {})

    def error(self):
        return (store.OfflineError, ValueError)

    def test_real_proof_preview_is_read_only_and_retains_evidence_limits(self):
        topics = self.app.list_topics()
        self.assertEqual([topic['id'] for topic in topics], [CARD])
        preview = self.preview()
        self.assertEqual(preview['topic_id'], CARD)
        self.assertEqual({entry['id'] for entry in preview['evidence']}, {'R1', 'R2', 'H1'})
        self.assertTrue(any(entry['origin'] == 'human_baseline' for entry in preview['evidence']))
        self.assertTrue(any('abstract' in entry['coverage'] for entry in preview['evidence']))
        self.assertTrue(preview['evidence_gaps'])
        self.assertTrue(preview['review']['independent'])
        self.assertEqual(len(set(preview['review']['models'].values())), 2)
        self.assertFalse(preview['writing_started'])
        self.assertFalse(preview['publish_authorized'])
        self.assertEqual(self.hashes(), self.original)
        self.assertFalse(self.published)

    def test_changed_evidence_refuses_old_preview_and_keeps_human_edit(self):
        preview = self.preview()
        historical = next(entry['path'] for entry in preview['evidence'] if entry['origin'] == 'human_baseline')
        target = self.root / historical
        changed = target.read_bytes() + '\n人工补充：这段必须保留。\n'.encode('utf-8')
        target.write_bytes(changed)
        with self.assertRaises(self.error()):
            self.app.confirm(preview['preview_id'], acknowledged=True)
        self.assertEqual(target.read_bytes(), changed)
        self.assertFalse(list((self.root / 'reports' / TOPIC).glob('writing-approvals/*/confirmed.yaml')))
        self.assertFalse(self.published)

    def test_expired_preview_and_repeated_confirmation_never_add_second_approval(self):
        expired = self.preview()
        self.now[0] += 86400
        with self.assertRaises(self.error()):
            self.app.confirm(expired['preview_id'], acknowledged=True)
        self.assertFalse(self.published)
        fresh = self.preview()
        confirmed = self.app.confirm(fresh['preview_id'], acknowledged=True)
        before = self.hashes()
        with self.assertRaises(self.error()):
            self.app.confirm(fresh['preview_id'], acknowledged=True)
        self.assertEqual(self.hashes(), before)
        self.assertEqual(len(self.published), 1)
        self.assertFalse(confirmed['publish_authorized'])
        self.assert_original_unchanged()

    def test_explicit_confirmation_survives_unrelated_commit_and_revoke_is_append_only(self):
        preview = self.preview()
        with self.assertRaises(self.error()):
            self.app.confirm(preview['preview_id'], acknowledged=False)
        (self.root / 'unrelated-note.md').write_text('# 与证据无关的新增文件\n', encoding='utf-8')
        self.git('add', 'unrelated-note.md')
        self.git('commit', '-m', 'Unrelated main change does not authorize or invalidate writing')
        confirmed = self.app.confirm(preview['preview_id'], acknowledged=True)
        self.assertEqual(len(self.published), 1)
        written = {relative: value for relative, value in self.hashes().items() if relative not in self.original}
        approval_files = [relative for relative in written if '/writing-approvals/' in relative]
        self.assertEqual(len(approval_files), 4)
        confirmation_path = next(relative for relative in approval_files if relative.endswith('/confirmed.yaml'))
        preview_path = confirmation_path.removesuffix('confirmed.yaml') + 'preview.yaml'
        record = yaml.safe_load((self.root / confirmation_path).read_text(encoding='utf-8'))
        frozen = yaml.safe_load((self.root / preview_path).read_text(encoding='utf-8'))
        self.assertEqual(record['origin'], 'local_confirmation_page')
        self.assertEqual(record['decision'], 'confirmed')
        self.assertEqual(record['writing_scope'], ['outline', 'draft', 'candidate'])
        self.assertEqual(record['preview_sha256'], store.digest(frozen))
        self.assertTrue(record['writing_authorized'])
        self.assertFalse(record['writing_started'])
        self.assertFalse(record['publish_authorized'])
        self.assertNotIn(preview['preview_id'], (self.root / preview_path).read_text(encoding='utf-8'))
        for relative in (confirmation_path, preview_path):
            self.assertEqual((self.root / (relative + '.sha256')).read_text().strip(),
                             store.digest((self.root / relative).read_bytes()))
        revoked = self.app.revoke(confirmed['id'], '用户暂缓这一选题')
        self.assertEqual(len(self.published), 2)
        for relative, value in written.items():
            self.assertEqual(store.digest((self.root / relative).read_bytes()), value, relative)
        self.assertTrue(list((self.root / 'reports' / TOPIC).glob('writing-approvals/*/revocations/*/event.yaml')))
        self.assertFalse(revoked['publish_authorized'])
        self.assert_original_unchanged()

    def test_unsynced_confirmation_retains_record_without_dispatch(self):
        app = self.confirmation.ConfirmationStore(
            self.root, self.config, publisher=lambda root, new_files, message: False)
        preview = app.preview(CARD, {})
        confirmed = app.confirm(preview['preview_id'], acknowledged=True)
        self.assertEqual(confirmed['status'], 'pending_sync')
        self.assertFalse(confirmed['writing_started'])
        self.assertFalse(confirmed['publish_authorized'])
        self.assertTrue(list((self.root / 'reports' / TOPIC).glob('writing-approvals/*/confirmed.yaml')))
        self.assert_original_unchanged()

    def test_real_git_commit_failure_preserves_complete_staged_record_and_retry_pushes(self):
        origin_directory = tempfile.TemporaryDirectory(prefix='researchdesk-confirmation-origin-')
        self.addCleanup(origin_directory.cleanup)
        origin = Path(origin_directory.name).resolve()
        subprocess.run(['git', 'init', '--bare', '--initial-branch=main', str(origin)],
                       check=True, capture_output=True)
        self.git('remote', 'add', 'origin', str(origin))
        self.git('push', '-u', 'origin', 'main')
        app = self.confirmation.ConfirmationStore(self.root, self.config)
        preview = app.preview(CARD, {})
        hook = self.root / '.git/hooks/pre-commit'
        hook.write_text('#!/bin/sh\nexit 1\n', encoding='utf-8')
        hook.chmod(0o700)
        try:
            confirmed = app.confirm(preview['preview_id'], acknowledged=True)
            self.assertEqual(confirmed['status'], 'pending_sync')
            staged = self.git('status', '--porcelain', '--untracked-files=all').splitlines()
            self.assertEqual(len(staged), 4)
            self.assertTrue(all(line.startswith('A ') for line in staged))
            saved = {relative: value for relative, value in self.hashes().items()
                     if relative not in self.original}
            self.assertEqual(len(saved), 4)
            self.assertTrue(any(relative.endswith('/confirmed.yaml') for relative in saved))
            for relative in saved:
                if not relative.endswith('.sha256'):
                    self.assertEqual((self.root / (relative + '.sha256')).read_text().strip(), saved[relative])
        finally:
            hook.unlink()
        # A restarted process must surface the complete unsynced confirmation
        # instead of losing it along with the old in-memory preview capability.
        restarted = self.confirmation.ConfirmationStore(self.root, self.config)
        self.assertEqual(restarted.list_confirmations()[0]['status'], 'pending_sync')
        self.assertEqual(restarted.list_topics()[0]['confirmation_id'], confirmed['id'])
        recovered = restarted.retry_sync(confirmed['id'])
        self.assertEqual(recovered['status'], 'confirmed_waiting_writer')
        self.assertTrue(recovered['synced'])
        self.assertFalse(recovered['writing_started'])
        self.assertEqual(self.git('status', '--porcelain'), '')
        self.assertEqual(self.git('rev-parse', 'HEAD'), self.git('rev-parse', 'origin/main'))
        for relative, expected in saved.items():
            self.assertEqual(store.digest((self.root / relative).read_bytes()), expected)
            remote = subprocess.run(['git', '--git-dir=' + str(origin), 'show', 'main:' + relative],
                                    check=True, capture_output=True).stdout
            self.assertEqual(store.digest(remote), expected)
        self.assert_original_unchanged()

    def test_http_loopback_host_origin_csrf_and_read_only_get_gates(self):
        server = self.confirmation.create_server(self.root, self.config, port=0, publisher=self.publisher)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(thread.join, 5)
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        origin = 'http://127.0.0.1:%s' % server.server_port

        def request(method, path, body=None, headers=None):
            connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=5)
            try:
                connection.request(method, path, None if body is None else json.dumps(body), headers or {})
                response = connection.getresponse()
                content = response.read()
                return response.status, json.loads(content) if content else None
            finally:
                connection.close()

        status, _ = request('GET', '/api/topics')
        self.assertEqual(status, 200)
        status, _ = request('GET', '/api/confirm')
        self.assertIn(status, (404, 405))
        body = {'topic_id': CARD, 'choices': {}}
        good = {'Content-Type': 'application/json', 'Origin': origin, 'X-ResearchDesk-CSRF': server.csrf_token}
        for headers in (
            {**good, 'Host': 'attacker.invalid'},
            {**good, 'Origin': 'https://attacker.invalid'},
            {key: value for key, value in good.items() if key != 'X-ResearchDesk-CSRF'},
        ):
            status, _ = request('POST', '/api/preview', body, headers)
            self.assertEqual(status, 403)
        status, preview = request('POST', '/api/preview', body, good)
        self.assertEqual(status, 200)
        status, _ = request('POST', '/api/confirm', {'preview_id': preview['preview_id'], 'acknowledged': False}, good)
        self.assertIn(status, (400, 403, 409))
        self.assertEqual(self.hashes(), self.original)
        self.assertFalse(self.published)
        with self.assertRaises((store.OfflineError, ValueError, OSError)):
            self.confirmation.create_server(self.root, self.config, host='0.0.0.0', port=0, publisher=self.publisher)


if __name__ == '__main__':
    unittest.main()
