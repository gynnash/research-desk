"""Reader refresh is trusted-local and follows successful formal acceptance."""

import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import admission
import job
import offline as store
import writing_admission as writing


class ReadingPublication(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='researchdesk-reading-pipeline-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / 'vault'
        self.root.mkdir()
        self.artifact = Path(temporary.name) / 'artifact'
        self.artifact.mkdir()
        (self.artifact / 'payload').mkdir()
        (self.root / '研究首页.md').write_text('# Existing reader home\n')
        self.staged = []
        self.operations = []
        self.reader = SimpleNamespace(refresh=mock.Mock(return_value=[]))
        self.addCleanup(mock.patch.stopall)
        mock.patch.dict(sys.modules, {'reading': self.reader}).start()
        self.git = mock.patch.object(job, 'git', side_effect=self.git_call).start()
        mock.patch.object(job, 'tracked', return_value={'研究首页.md': 'home-blob'}).start()
        self.plan = mock.patch.object(job, 'formal_plan', return_value=({'files': {}}, set())).start()
        self.inspect = mock.patch.object(job, 'inspect_files').start()
        mock.patch.object(job, 'verify_recovery').start()
        mock.patch.object(job, 'admission_enabled', return_value=True).start()
        self.accept = mock.patch.object(admission, 'run', return_value={'status': 'accepted'}).start()
        mock.patch.object(job.subprocess, 'run', return_value=SimpleNamespace(returncode=0)).start()

    def git_call(self, root, *arguments):
        self.operations.append(arguments)
        if arguments[:2] == ('add', '--'):
            self.staged = list(arguments[2:])
        if arguments == ('diff', '--cached', '--name-only', '-z'):
            return b'\0'.join(path.encode() for path in self.staged)
        if arguments == ('rev-parse', 'HEAD'):
            return b'accepted-commit\n'
        return b''

    def apply(self, operation='admit'):
        manifest = {'schema_version': 1, 'topic': 'agent-memory', 'cycle_id': 'reader-cycle',
            'operation': operation, 'base_commit': 'base',
            'baseline_blobs': {'研究首页.md': 'home-blob'}, 'files': {}}
        (self.artifact / 'manifest.json').write_text(json.dumps(manifest))
        with contextlib.redirect_stdout(io.StringIO()) as output:
            job.apply(self.root, self.artifact)
        return json.loads(output.getvalue())

    def test_formal_cached_publish_includes_changed_tracked_home_and_new_reader(self):
        def refresh(root):
            self.accept.assert_called_once_with(root, 'agent-memory', 'reader-cycle')
            (root / '研究首页.md').write_text('# Updated reader home\n')
            reading_path = 'reports/agent-memory/reading/reader-cycle.md'
            target = root / reading_path
            target.parent.mkdir(parents=True)
            target.write_text('# Readable reviewed result\n')
            return ['研究首页.md', reading_path]

        self.reader.refresh.side_effect = refresh
        result = self.apply()
        self.assertEqual(self.staged, ['reports/agent-memory/reading/reader-cycle.md', '研究首页.md'])
        self.assertEqual(result['saved_files'], 2)
        self.assertIs(result['production_accepted'], True)
        self.assertTrue(any(operation[0] == 'push' for operation in self.operations))
        self.inspect.assert_called()  # Transfer/formal validation remains separate.

    def test_test_only_transfer_never_refreshes_or_publishes_reading_files(self):
        self.plan.return_value = (None, set())
        result = self.apply(operation='run')
        self.reader.refresh.assert_not_called()
        self.accept.assert_not_called()
        self.assertEqual(result['saved_files'], 0)
        self.assertFalse(any(operation[0] in {'add', 'commit', 'push'} for operation in self.operations))

    def test_failed_admission_does_not_refresh(self):
        self.accept.side_effect = store.OfflineError('acceptance failed')
        with self.assertRaisesRegex(store.OfflineError, 'acceptance failed'):
            self.apply()
        self.reader.refresh.assert_not_called()
        self.assertFalse(self.staged)

    def test_reader_conflict_stops_before_any_git_publication(self):
        self.reader.refresh.side_effect = store.OfflineError('preserve human reader note')
        with self.assertRaisesRegex(store.OfflineError, 'preserve human'):
            self.apply()
        self.assertFalse(any(operation[0] in {'add', 'commit', 'push'} for operation in self.operations))

    def test_artifacts_still_cannot_supply_reader_home_or_unplanned_reading_files(self):
        self.assertFalse(job.allowed('研究首页.md', 'agent-memory', 'reader-cycle', set()))
        self.assertFalse(job.allowed('reports/agent-memory/reading/reader-cycle.md',
                                     'agent-memory', 'reader-cycle', set()))


class WritingReadingRefresh(unittest.TestCase):
    def test_new_and_cached_formal_acceptance_refresh_after_admission_returns(self):
        for cached in (False, True):
            with self.subTest(cached=cached):
                order = []
                result = {'status': 'accepted', 'cached': cached}
                reader = SimpleNamespace(refresh=mock.Mock(side_effect=lambda root: order.append('refresh')))
                with mock.patch.dict(sys.modules, {'reading': reader}), \
                        mock.patch.object(writing, '_run', side_effect=lambda *args: order.append('accepted') or result):
                    actual = writing.run(Path('/tmp/vault'), 'approval-one')
                self.assertIs(actual, result)
                self.assertEqual(order, ['accepted', 'refresh'])
                reader.refresh.assert_called_once_with(Path('/tmp/vault').resolve())

    def test_failed_or_interrupted_admission_never_refreshes(self):
        reader = SimpleNamespace(refresh=mock.Mock())
        with mock.patch.dict(sys.modules, {'reading': reader}), \
                mock.patch.object(writing, '_run', side_effect=store.SimulatedInterruption('not accepted')):
            with self.assertRaises(store.SimulatedInterruption):
                writing.run(Path('/tmp/vault'), 'approval-one')
        reader.refresh.assert_not_called()


if __name__ == '__main__':
    unittest.main()
