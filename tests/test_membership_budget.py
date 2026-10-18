"""Shared membership policy is tested without OAuth, networking, or inference."""

import copy
from pathlib import Path
import socket
import sys
import tempfile
import unittest
from unittest import mock

import yaml


REPOSITORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY / 'scripts'))
import researchdesk_batch as batch
import researchdesk_offline as store


class MembershipBudgetPolicy(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='researchdesk-budget-tests-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        (self.root / 'config').mkdir()
        self.policy_path = self.root / 'config/membership_budget.yaml'
        self.config = {'backend': 'chatgpt_plan', 'budget': {'month_max_calls': 10}}
        self.policy = {'schema_version': 1, 'backend': 'chatgpt_plan', 'month_max_calls': 100}
        self.at = '2026-10-19T00:00:00+00:00'
        self.addCleanup(mock.patch.stopall)
        mock.patch.object(batch, 'now', return_value=self.at).start()
        mock.patch.object(socket, 'create_connection',
                          side_effect=AssertionError('Network prohibited')).start()
        mock.patch.object(socket.socket, 'connect',
                          side_effect=AssertionError('Network prohibited')).start()

    def write_policy(self, policy=None):
        self.policy_path.write_text(yaml.safe_dump(self.policy if policy is None else policy,
                                                   sort_keys=False))

    def record_run(self, entry, calls, topic='agent-memory', name='old', cap=10,
                   completed=0, backend='chatgpt_plan', month='2026-10'):
        base = 'reports/test/%s/%s/%s' % (topic, entry, name)
        manifest = {'schema_version': 1, 'backend': backend,
                    'created_at': month + '-01T00:00:00+00:00'}
        manifest['limits' if entry == 'membership' else 'budget'] = {'month_max_calls': cap}
        store.save_yaml(self.root, base + '/manifest.yaml', manifest)
        events = []
        for index in range(calls):
            identity = '%s-%s' % (name, index)
            store.append_event(self.root, base, events, {
                'type': 'call_reserved', 'reservation_id': identity,
                'role': 'research', 'revision': index, 'model_id': 'offline-fixture',
                'month': month, 'at': self.at, 'usage_status': 'unknown'})
            if index < completed:
                path = base + '/checkpoints/response-%s.yaml' % index
                sha = store.save_yaml(self.root, path, {
                    'result': {'text': '{"fixture":true}', 'model': 'offline-fixture',
                               'usage': {'total_tokens': 12}}})
                store.append_event(self.root, base, events, {
                    'type': 'call_completed', 'reservation_id': identity,
                    'role': 'research', 'revision': index, 'model_id': 'offline-fixture',
                    'response_path': path, 'response_sha256': sha,
                    'usage': {'total_tokens': 12}, 'at': self.at})
        store.save_yaml(self.root, base + '/receipt.yaml', {
            'status': 'fixture', 'reserved_calls': calls, 'completed_calls': completed,
            'effective_month_max_calls': cap})
        return base

    def test_explicit_policy_raises_old_cap_without_resetting_ten_reservations(self):
        self.record_run('membership', 2, name='member', completed=1)
        self.record_run('research-batches', 4, name='research', completed=4)
        self.record_run('insight-runs', 4, name='insight', completed=3)
        self.assertEqual(batch.monthly_budget(self.root, self.config), (10, 10))
        self.write_policy()
        self.assertEqual(batch.monthly_budget(self.root, self.config), (10, 100))

    def test_all_entry_points_topics_and_unknown_outcomes_share_reservations(self):
        self.write_policy()
        self.record_run('membership', 2, name='member', completed=0)
        self.record_run('research-batches', 3, name='research', completed=1)
        self.record_run('insight-runs', 4, topic='another-topic', name='insight', completed=4)
        self.assertEqual(batch.monthly_budget(self.root, self.config), (9, 100))

    def test_missing_policy_preserves_minimum_of_config_and_previous_real_limits(self):
        self.config['budget']['month_max_calls'] = 100
        self.record_run('membership', 2, name='legacy', cap=10)
        self.record_run('research-batches', 2, name='research', cap=20)
        self.assertEqual(batch.monthly_budget(self.root, self.config), (4, 10))
        self.config['budget']['month_max_calls'] = 6
        self.assertEqual(batch.monthly_budget(self.root, self.config), (4, 6))

    def test_policy_is_authoritative_even_when_batch_default_is_lower(self):
        self.write_policy()
        self.config['budget']['month_max_calls'] = 4
        self.record_run('research-batches', 3, cap=2)
        self.assertEqual(batch.monthly_budget(self.root, self.config), (3, 100))

    def test_policy_change_does_not_reset_usage_or_modify_historical_files(self):
        self.record_run('membership', 2, name='legacy', completed=1)
        self.record_run('research-batches', 4, name='research', completed=4)
        self.record_run('insight-runs', 4, name='insight', completed=3)
        baseline = {path: path.read_bytes() for path in self.root.rglob('*') if path.is_file()}
        self.write_policy()
        self.assertEqual(batch.monthly_budget(self.root, self.config), (10, 100))
        self.write_policy(dict(self.policy, month_max_calls=20))
        self.assertEqual(batch.monthly_budget(self.root, self.config), (10, 20))
        for path, payload in baseline.items():
            self.assertEqual(path.read_bytes(), payload, path.relative_to(self.root).as_posix())

    def test_mock_runs_do_not_consume_real_budget_or_inherit_real_policy(self):
        self.write_policy()
        self.record_run('research-batches', 8, backend='mock', cap=2)
        self.record_run('membership', 2, name='real')
        self.assertEqual(batch.monthly_budget(self.root, self.config), (2, 100))
        config = {'backend': 'mock', 'budget': {'month_max_calls': 7}}
        self.assertEqual(batch.monthly_budget(self.root, config), (0, 7))
        self.policy_path.write_text('invalid: [\n')
        self.assertEqual(batch.monthly_budget(self.root, config), (0, 7))

    def test_previous_month_reservations_are_not_charged_again(self):
        self.write_policy()
        self.record_run('membership', 5, name='past', cap=2, month='2026-09')
        self.record_run('insight-runs', 2, name='current')
        self.assertEqual(batch.monthly_budget(self.root, self.config), (2, 100))

    def test_invalid_policy_fields_fail_closed(self):
        changes = [
            {'schema_version': 2}, {'schema_version': True}, {'backend': 'mock'},
            {'backend': 'api_key'}, {'month_max_calls': True}, {'month_max_calls': '100'},
            {'month_max_calls': 100.0}, {'month_max_calls': 0}, {'month_max_calls': 1},
            {'month_max_calls': -1}, {'month_max_calls': 1001}, {'month_max_calls': None},
            {'unexpected': 'unsupported'}]
        for change in changes:
            self.write_policy(dict(copy.deepcopy(self.policy), **change))
            with self.subTest(change=change), self.assertRaises((store.OfflineError, ValueError, yaml.YAMLError)):
                batch.monthly_budget(self.root, self.config)

    def test_missing_fields_and_non_mapping_policy_are_rejected(self):
        for key in self.policy:
            value = copy.deepcopy(self.policy)
            value.pop(key)
            self.write_policy(value)
            with self.subTest(missing=key), self.assertRaises((store.OfflineError, ValueError, yaml.YAMLError)):
                batch.monthly_budget(self.root, self.config)
        for raw in ('null\n', '[]\n', '100\n', 'invalid: [\n'):
            self.policy_path.write_text(raw)
            with self.subTest(raw=raw), self.assertRaises((store.OfflineError, ValueError, yaml.YAMLError)):
                batch.monthly_budget(self.root, self.config)

    def test_duplicate_yaml_policy_keys_are_rejected(self):
        for suffix in ('month_max_calls: 100\n', 'month_max_calls: 1000\n', 'backend: mock\n'):
            self.write_policy()
            self.policy_path.write_text(self.policy_path.read_text() + suffix)
            with self.subTest(suffix=suffix), self.assertRaises((store.OfflineError, ValueError, yaml.YAMLError)):
                batch.monthly_budget(self.root, self.config)

    def test_policy_symlink_and_broken_symlink_are_rejected(self):
        target = self.root / 'outside-policy.yaml'
        target.write_text(yaml.safe_dump(self.policy))
        self.policy_path.symlink_to(target)
        with self.assertRaises((store.OfflineError, ValueError)):
            batch.monthly_budget(self.root, self.config)
        self.policy_path.unlink()
        self.policy_path.symlink_to(self.root / 'absent-policy.yaml')
        with self.assertRaises((store.OfflineError, ValueError)):
            batch.monthly_budget(self.root, self.config)

    def test_policy_directory_symlink_is_rejected(self):
        directory = self.root / 'config-target'
        directory.mkdir()
        (directory / self.policy_path.name).write_text(yaml.safe_dump(self.policy))
        (self.root / 'config').rmdir()
        (self.root / 'config').symlink_to(directory, target_is_directory=True)
        with self.assertRaises((store.OfflineError, ValueError)):
            batch.monthly_budget(self.root, self.config)

    def test_numeric_policy_bounds_are_inclusive(self):
        for cap in (2, 1000):
            self.write_policy(dict(self.policy, month_max_calls=cap))
            with self.subTest(cap=cap):
                self.assertEqual(batch.monthly_budget(self.root, self.config), (0, cap))


if __name__ == '__main__':
    unittest.main()
