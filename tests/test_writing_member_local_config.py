"""Local-only configuration must not weaken confirmed Writing evidence checks."""

import hashlib
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import researchdesk_offline as store
import researchdesk_writing_member_inputs as inputs


class PrivateWritingConfiguration(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix='researchdesk-private-writing-')
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name).resolve()
        self.write('config/local/workbench.yaml', 'schema_version: 1\n')
        self.config = 'config/membership_budget.yaml'
        self.digest = self.write(self.config, 'schema_version: 1\nmonth_max_calls: 100\n')
        self.confirmation = 'reports/example/writing-approvals/approval-one/confirmed.yaml'
        self.confirmation_hash = self.write(self.confirmation, 'decision: confirmed\n')
        self.is_ancestor = True

    def write(self, relative, text):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')
        return store.digest(path.read_bytes())

    def git(self, root, *arguments):
        # Only the confirmation is tracked. The actual Git executable and all
        # credential/model/network operations stay outside this regression.
        path = self.root / self.confirmation
        payload = path.read_bytes()
        blob = hashlib.sha1(b'blob ' + str(len(payload)).encode() + b'\0' + payload).hexdigest()
        if arguments == ('rev-parse', '--show-object-format'):
            return b'sha1\n'
        if arguments == ('merge-base', '--is-ancestor', 'HEAD', 'refs/remotes/origin/main'):
            if not self.is_ancestor:
                raise store.OfflineError('持久工作台与远端历史分叉')
            return b''
        if arguments == ('ls-files', '--stage', '-z'):
            return ('100644 ' + blob + ' 0\t' + self.confirmation + '\0').encode()
        if arguments[0] == 'ls-tree':
            if self.remote_confirmed or arguments[-1] == 'refs/heads/main':
                return ('100644 blob ' + blob + '\t' + self.confirmation + '\0').encode()
            return b''
        raise AssertionError(arguments)

    def test_untracked_configuration_is_frozen_but_confirmation_must_remain_synced(self):
        with mock.patch.object(inputs, '_git', side_effect=self.git) as git:
            self.assertEqual(inputs._synced(self.root, self.config), self.digest)
            git.assert_not_called()
            hashes = {self.config: self.digest, self.confirmation: self.confirmation_hash}
            self.remote_confirmed = True
            inputs._synced_hashes(self.root, hashes)
            self.remote_confirmed = False
            with self.assertRaisesRegex(store.OfflineError, '尚未完整同步到 main'):
                inputs._synced_hashes(self.root, hashes)
            self.write(self.config, 'schema_version: 1\nmonth_max_calls: 200\n')
            with self.assertRaisesRegex(store.OfflineError, '本地配置已变化'):
                inputs._synced_hashes(self.root, hashes)

    def test_custom_research_configuration_is_not_exempted_by_local_workbench(self):
        relative = 'config/examples/research_batch.yaml'
        digest = self.write(relative, 'mode: historical_research_snapshot\n')
        self.remote_confirmed = True
        with mock.patch.object(inputs, '_git', side_effect=self.git):
            with self.assertRaisesRegex(store.OfflineError, '尚未完整同步到 main'):
                inputs._synced_hashes(self.root, {relative: digest})

    def test_diverged_workbench_cannot_authorize_even_matching_confirmation_bytes(self):
        self.remote_confirmed = True
        self.is_ancestor = False
        with mock.patch.object(inputs, '_git', side_effect=self.git):
            with self.assertRaisesRegex(store.OfflineError, '历史分叉'):
                inputs._synced_hashes(self.root, {self.confirmation: self.confirmation_hash})


if __name__ == '__main__':
    unittest.main()
