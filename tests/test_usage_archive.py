"""Clearing research outputs must not clear real membership reservations."""

from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import researchdesk_batch as batch
import researchdesk_offline as store


class ArchivedUsage(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='researchdesk-usage-tests-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        (self.root / 'config').mkdir()
        self.state = self.root / 'config/research_state.yaml'
        self.state.write_text(yaml.safe_dump({'schema_version': 1, 'usage_months': {'2026-10': 69}}))
        self.config = {'backend': 'chatgpt_plan', 'budget': {'month_max_calls': 100}}
        clock = patch.object(batch, 'now', return_value='2026-10-31T01:00:00+00:00')
        clock.start()
        self.addCleanup(clock.stop)

    def add_run(self, folder, identity, backend='chatgpt_plan', month='2026-10'):
        base = 'reports/test/agent-memory/%s/%s' % (folder, identity)
        store.save_yaml(self.root, base + '/manifest.yaml', {
            'backend': backend, 'created_at': month + '-31T00:00:00+00:00',
            'budget': {'month_max_calls': 100}})
        events = []
        store.append_event(self.root, base, events, {
            'type': 'call_reserved', 'reservation_id': identity,
            'month': month, 'usage_status': 'unknown'})

    def test_cleared_run_directories_still_count_69_and_new_stage_reservations_add_up(self):
        self.assertFalse((self.root / 'reports').exists())
        self.assertEqual(batch.monthly_budget(self.root, self.config), (69, 100))
        self.add_run('research-batches', 'research')
        self.add_run('insight-runs', 'insight')
        self.add_run('writing-runs', 'writing')
        self.add_run('research-batches', 'previous-month', month='2026-09')
        self.add_run('research-batches', 'mock', backend='mock')
        self.assertEqual(batch.monthly_budget(self.root, self.config), (72, 100))
        with patch.object(batch, 'now', return_value='2026-11-01T00:00:00+00:00'):
            self.assertEqual(batch.monthly_budget(self.root, self.config), (0, 100))

    def test_mock_does_not_consume_archived_or_new_membership_usage(self):
        self.add_run('research-batches', 'research')
        self.assertEqual(batch.monthly_budget(self.root, dict(self.config, backend='mock')), (0, 100))

    def test_invalid_or_symlinked_archive_fails_closed(self):
        for value in ({'schema_version': 2, 'usage_months': {'2026-10': 69}},
                      {'schema_version': 1, 'usage_months': {'2026-10': -1}},
                      {'schema_version': 1, 'usage_months': {'2026-10': True}},
                      {'schema_version': 1, 'usage_months': {'2026-10': '69'}},
                      {'schema_version': 1, 'usage_months': {'October': 69}},
                      {'schema_version': 1}, None):
            with self.subTest(value=value):
                self.state.write_text(yaml.safe_dump(value))
                with self.assertRaises(store.OfflineError):
                    batch.monthly_budget(self.root, self.config)
        self.state.unlink()
        target = self.root / 'untrusted-state.yaml'
        target.write_text(yaml.safe_dump({'schema_version': 1, 'usage_months': {'2026-10': 0}}))
        self.state.symlink_to(target)
        with self.assertRaises(store.OfflineError):
            batch.monthly_budget(self.root, self.config)


if __name__ == '__main__':
    unittest.main()
