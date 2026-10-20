"""Linked recovery end to end, with fake providers and blocked sockets only."""

import copy
import json
from pathlib import Path
import sys
import unittest
from unittest import mock

import yaml

REPOSITORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY / 'scripts'))
import researchdesk_admission as admission
import researchdesk_batch as research
import researchdesk_cycle as cycle
import researchdesk_insight as insight
import researchdesk_insight_inputs as inputs
import researchdesk_offline as store
import researchdesk_recovery as recovery
import test_cycle
from test_insight import FakeInsightClient
from test_research_batch import FakeMemberClient


class StageClient(FakeMemberClient):
    def __init__(self):
        super().__init__()
        self.research = FakeMemberClient()
        self.research.review_decisions = ['revise', 'pass', 'pass']
        self.insight = FakeInsightClient()
        self.insight.generation_text_overrides = ['{']
        self.insight.review_decisions = ['revise']

    def infer(self, model, instructions, input_text, **limits):
        client = self.insight if 'evidence' in json.loads(input_text) else self.research
        return client.infer(model, instructions, input_text, **limits)


class LinkedRecovery(unittest.TestCase):
    fake_research = test_cycle.ResearchInsightCycle.fake_research
    fake_insight = test_cycle.ResearchInsightCycle.fake_insight

    def setUp(self):
        test_cycle.ResearchInsightCycle.setUp(self)
        self.config['budget']['max_calls_per_cycle'] = 16
        self.config_path.write_text(yaml.safe_dump(self.config, allow_unicode=True, sort_keys=False))
        self.research_run.side_effect = self.real_research_run
        def legacy_run(root, path, identifier, *args, **kwargs):
            target = root / path
            value = store.load_yaml(target)
            value['prompts']['version'] = 'insight-v1'
            self.rewrite(target.relative_to(root).as_posix(), value)
            return self.real_insight_run(root, path, identifier, *args, **kwargs)
        self.insight_run.side_effect = legacy_run
        self.old_client = StageClient()
        original = cycle.run(self.root, self.config_path, 'first', client=self.old_client, fetcher=self.fetcher)
        self.assertEqual(original['status'], 'insight_blocked')
        self.assertEqual(original['reserved_calls'], 9)
        self.insight_run.side_effect = self.real_insight_run
        self.client = FakeInsightClient()
        self.identifier = 'first-recovery-1'
        self.base = 'reports/test/custom-topic/cycles/' + self.identifier
        self.new_base = 'reports/test/custom-topic/insight-runs/' + self.identifier
        self.request_path = self.root / 'config/recoveries/first.yaml'
        self.request_path.parent.mkdir(parents=True)
        self.request = recovery.make_request(self.root, self.config_path, 'first')
        self.request_path.write_text(yaml.safe_dump(self.request, allow_unicode=True, sort_keys=False))
        self.original_bytes = {relative: (self.root / relative).read_bytes()
                               for relative in self.request['original_files']}

    def rewrite(self, relative, value):
        path = self.root / relative
        path.write_text(yaml.safe_dump(value, allow_unicode=True, sort_keys=False))
        Path(str(path) + '.sha256').write_text(store.digest(path.read_bytes()) + '\n')

    def run_recovery(self, **kwargs):
        return recovery.run(self.root, self.config_path, 'first', self.client, fetcher=self.fetcher, **kwargs)

    def assert_original_unchanged(self):
        self.assertEqual(self.original_bytes, {path: (self.root / path).read_bytes() for path in self.original_bytes})

    def assert_no_accepted(self):
        self.assertFalse((self.root / self.new_base / 'report.md').exists())
        self.assertFalse((self.root / 'reports/custom-topic/admissions/first-recovery-1/accepted.yaml').exists())

    def test_two_fresh_calls_reuse_exact_research_and_preserve_original(self):
        result = self.run_recovery()
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['new_reserved_calls'], 2)
        self.assertEqual(result['reserved_calls'], 11)
        self.assertEqual(len(self.client.calls), 2)
        self.assertIn('evidence_index', self.client.calls[0]['payload'])
        self.assertEqual(self.client.calls[0]['payload']['evidence_index'], self.client.calls[1]['payload']['evidence_index'])
        self.assertEqual(self.request['max_new_calls'], 4)
        self.assertEqual(len(self.old_client.research.calls), 6)
        lineage = recovery.verify_lineage(self.root, 'custom-topic', self.identifier)
        self.assertEqual(lineage['original_reserved_calls'], 9)
        self.assert_original_unchanged()
        monthly, cap = research.monthly_budget(self.root, inputs.load_config(self.root, self.base + '/configs/insight.yaml'))
        self.assertEqual((monthly, cap), (11, 100))

    def test_replay_and_interrupted_acceptance_add_no_calls(self):
        with self.assertRaises(store.SimulatedInterruption):
            self.run_recovery(fail_after='after_review')
        self.assertEqual(len(self.client.calls), 2)
        recovery.verify_lineage(self.root, 'custom-topic', self.identifier)
        result = self.run_recovery()
        self.assertEqual(result['status'], 'completed')
        before = {p.relative_to(self.root).as_posix(): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        self.assertTrue(self.run_recovery()['cached'])
        self.assertEqual(len(self.client.calls), 2)
        self.assertEqual(before, {p.relative_to(self.root).as_posix(): p.read_bytes() for p in self.root.rglob('*') if p.is_file()})
        self.assert_original_unchanged()

    def test_one_revision_requires_independent_pass_and_exactly_four_calls(self):
        self.client.review_decisions = ['revise', 'pass']
        result = self.run_recovery()
        self.assertEqual((result['new_reserved_calls'], result['reserved_calls']), (4, 13))
        self.assertEqual(len(self.client.calls), 4)
        self.assert_original_unchanged()

    def test_repeated_revise_stays_blocked_and_idempotent(self):
        self.client.review_decisions = ['revise', 'revise']
        result = self.run_recovery()
        self.assertEqual(result['status'], 'insight_blocked')
        self.assertEqual(result['new_reserved_calls'], 4)
        self.assertTrue(self.run_recovery()['cached'])
        self.assertEqual(len(self.client.calls), 4)
        with self.assertRaises(store.OfflineError):
            admission.plan(self.root, 'custom-topic', self.identifier, fetcher=self.fetcher)
        self.assert_no_accepted()
        self.assert_original_unchanged()

    def test_reviewer_reject_cannot_create_or_admit_outputs(self):
        self.client.review_decisions = ['reject']
        self.assertEqual(self.run_recovery()['status'], 'insight_blocked')
        with self.assertRaises(store.OfflineError):
            admission.run(self.root, 'custom-topic', self.identifier, fetcher=self.fetcher)
        self.assertEqual(len(self.client.calls), 2)
        self.assert_no_accepted()

    def test_unknown_new_request_is_counted_and_never_retried(self):
        self.client.fail_on_call = 1
        with self.assertRaises(OSError):
            self.run_recovery()
        recovery.verify_lineage(self.root, 'custom-topic', self.identifier)
        with self.assertRaises(store.OfflineError):
            self.run_recovery()
        self.assertEqual(len(self.client.calls), 1)
        monthly, _ = research.monthly_budget(self.root, inputs.load_config(self.root, self.base + '/configs/insight.yaml'))
        self.assertEqual(monthly, 10)
        self.assert_no_accepted()
        self.assert_original_unchanged()

    def test_changed_raw_source_stops_before_new_call(self):
        self.fetcher.paper = self.fetcher.paper.replace('Memory', 'ChangedMemory')
        with self.assertRaises(store.OfflineError):
            self.run_recovery()
        self.assertEqual(self.client.calls, [])
        self.assert_no_accepted()

    def test_changed_history_stops_before_new_call(self):
        path = self.root / self.history[0]['path']
        path.write_text(path.read_text() + '\nHuman addition.\n')
        with self.assertRaises(store.OfflineError):
            self.run_recovery()
        self.assertEqual(self.client.calls, [])
        self.assert_no_accepted()

    def test_original_accepted_or_unknown_call_cannot_receive_request(self):
        relative = 'reports/test/custom-topic/cycles/first/receipt.yaml'
        value = store.checked_yaml(self.root, relative)
        value['status'] = 'completed'
        self.rewrite(relative, value)
        with self.assertRaises(store.OfflineError):
            recovery.make_request(self.root, self.config_path, 'first')
        value['status'] = 'insight_blocked'
        old_path = 'reports/test/custom-topic/insight-runs/first/receipt.yaml'
        old = store.checked_yaml(self.root, old_path)
        old['reserved_calls'] += 1
        self.rewrite(old_path, old)
        self.rewrite('reports/test/custom-topic/cycles/first/insight-result.yaml', old)
        for path in (old_path, 'reports/test/custom-topic/cycles/first/insight-result.yaml'):
            value['input_hashes'][path] = store.digest((self.root / path).read_bytes())
        self.rewrite(relative, value)
        with self.assertRaises(store.OfflineError):
            recovery.make_request(self.root, self.config_path, 'first')
        self.assertEqual(self.client.calls, [])

    def test_changed_bound_config_is_refused_before_inference(self):
        self.config['budget']['max_input_chars'] += 1
        self.config_path.write_text(yaml.safe_dump(self.config))
        with self.assertRaises(store.OfflineError):
            self.run_recovery()
        self.assertEqual(self.client.calls, [])

    def test_changed_original_checkpoint_even_with_new_sidecar_is_rejected(self):
        relative = 'reports/test/custom-topic/insight-runs/first/checkpoints/review-1.yaml'
        value = store.checked_yaml(self.root, relative)
        value['result']['text'] += ' '
        self.rewrite(relative, value)
        with self.assertRaises(store.OfflineError):
            self.run_recovery()
        self.assertEqual(self.client.calls, [])

    def test_absent_or_changed_request_cannot_bypass_duplicate_guard(self):
        self.request_path.unlink()
        with self.assertRaises(store.OfflineError):
            self.run_recovery()
        self.request['max_new_calls'] = 5
        self.request_path.write_text(yaml.safe_dump(self.request))
        with self.assertRaises(store.OfflineError):
            self.run_recovery()
        self.assertEqual(self.client.calls, [])

    def test_arbitrary_or_second_recovery_id_is_refused(self):
        for identifier in ('first-recovery-1', 'first-recovery-2', '../first'):
            with self.subTest(identifier=identifier), self.assertRaises(store.OfflineError):
                recovery.recovery_id(identifier)
        old_config = 'reports/test/custom-topic/cycles/first/configs/insight.yaml'
        with self.assertRaises(store.OfflineError):
            self.real_insight_run(self.root, old_config, 'other-id', self.client, fetcher=self.fetcher)
        self.assertEqual(self.client.calls, [])

    def test_wrong_account_stops_before_new_request(self):
        self.client.account['account_fingerprint'] = 'another-account'
        with self.assertRaises(store.OfflineError):
            self.run_recovery()
        self.assertEqual(self.client.calls, [])
        self.assert_no_accepted()

    def test_current_month_cap_cannot_be_increased_by_recovery(self):
        (self.root / 'config/membership_budget.yaml').write_text(yaml.safe_dump({
            'schema_version': 1, 'backend': 'chatgpt_plan', 'month_max_calls': 10}))
        with self.assertRaises(store.OfflineError):
            self.run_recovery()
        self.assertEqual(self.client.calls, [])
        self.assert_no_accepted()

    def test_frozen_monthly_cap_survives_later_workspace_limit_increase(self):
        with mock.patch.object(research, 'monthly_budget', return_value=(100, 1000)):
            with self.assertRaises(store.OfflineError):
                self.run_recovery()
        self.assertEqual(self.client.calls, [])
        self.assert_no_accepted()

    def test_original_cumulative_limit_is_checked_before_each_new_pair(self):
        # A valid original fixture with a ten-call cap leaves only one call,
        # which cannot fund a new generation/review pair.
        self.config['budget']['max_calls_per_cycle'] = 10
        self.config_path.write_text(yaml.safe_dump(self.config, allow_unicode=True, sort_keys=False))
        original_base = 'reports/test/custom-topic/cycles/first'
        manifest = store.checked_yaml(self.root, original_base + '/manifest.yaml')
        manifest['config'] = cycle.load_config(self.root, self.config_path)
        self.rewrite(original_base + '/manifest.yaml', manifest)
        receipt = store.checked_yaml(self.root, original_base + '/receipt.yaml')
        receipt['input_hashes'][original_base + '/manifest.yaml'] = store.digest((self.root / original_base / 'manifest.yaml').read_bytes())
        self.rewrite(original_base + '/receipt.yaml', receipt)
        self.request_path.write_text(yaml.safe_dump(recovery.make_request(self.root, self.config_path, 'first')))
        with self.assertRaises(store.OfflineError):
            self.run_recovery()
        self.assertEqual(self.client.calls, [])
        self.assert_no_accepted()

    def test_fresh_pass_can_be_admitted_and_cached_offline_with_lineage(self):
        self.run_recovery()
        result = admission.run(self.root, 'custom-topic', self.identifier, fetcher=self.fetcher)
        self.assertEqual(result['status'], 'accepted')
        self.assertTrue(result['production_accepted'])
        self.assertFalse(result['writing_started'])
        self.assertFalse(result['publish_authorized'])
        self.assertTrue(set(self.original_bytes).issubset(result['input_hashes']))
        with mock.patch.object(self.fetcher, 'fetch', side_effect=AssertionError('cached admission must not fetch')):
            self.assertTrue(admission.run(self.root, 'custom-topic', self.identifier, fetcher=self.fetcher)['cached'])
        self.assertTrue(self.run_recovery()['cached'])
        self.assertEqual(len(self.client.calls), 2)
        self.assert_original_unchanged()

    def test_resigned_compact_projection_cannot_change_original_evidence(self):
        self.run_recovery()
        original = store.checked_yaml(self.root, self.base + '/recovery.yaml')
        new_manifest_path = self.new_base + '/manifest.yaml'
        manifest = store.checked_yaml(self.root, new_manifest_path)
        mutations = [
            lambda bundle: bundle['evidence'][0]['metadata'].update(title='False title'),
            lambda bundle: bundle['evidence'][0].update(coverage='full_text'),
            lambda bundle: bundle['evidence'][0].update(source_ids=['paper-other']),
            lambda bundle: bundle['evidence'][0].update(research_claims=[]),
            lambda bundle: bundle['research_context'].update(name='Other topic'),
            lambda bundle: bundle['evidence'][-1].update(source_urls=['https://other.example/'])]
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                value = copy.deepcopy(original)
                mutate(value['verification_bundle'])
                self.rewrite(self.base + '/recovery.yaml', value)
                manifest['recovery'] = recovery.binding(self.root, 'custom-topic', self.identifier)
                self.rewrite(new_manifest_path, manifest)
                with self.assertRaisesRegex(store.OfflineError, '离线证据投影'):
                    recovery.verify_lineage(self.root, 'custom-topic', self.identifier)
        self.assert_original_unchanged()

    def test_missing_lineage_cannot_downgrade_linked_insight_to_ordinary(self):
        self.run_recovery()
        (self.root / self.base / 'recovery.yaml').unlink()
        with self.assertRaisesRegex(store.OfflineError, '缺失恢复记录'):
            recovery.verify_if_present(self.root, 'custom-topic', self.identifier)
        with self.assertRaises(store.OfflineError):
            admission.plan(self.root, 'custom-topic', self.identifier, fetcher=self.fetcher)
        self.assertFalse((self.root / 'reports/custom-topic/admissions/first-recovery-1/accepted.yaml').exists())

    def test_changed_lineage_after_plan_cannot_admit(self):
        self.run_recovery()
        admission.plan(self.root, 'custom-topic', self.identifier, fetcher=self.fetcher)
        value = store.checked_yaml(self.root, self.base + '/recovery.yaml')
        value['original_reserved_calls'] = 0
        self.rewrite(self.base + '/recovery.yaml', value)
        with self.assertRaises(store.OfflineError):
            admission.run(self.root, 'custom-topic', self.identifier, fetcher=self.fetcher)
        self.assertFalse((self.root / 'reports/custom-topic/admissions/first-recovery-1/accepted.yaml').exists())



class SavedRecoveryRequest(unittest.TestCase):
    def test_exact_authorized_morning_slot_binds_102_original_files(self):
        original = 'agent-memory-20261020-0300'
        relative = 'config/recoveries/' + original + '.yaml'
        if not (REPOSITORY / relative).is_file():
            self.skipTest('One-time request is not installed in this checkout')
        request = store.load_yaml(REPOSITORY / relative)
        self.assertEqual(request, recovery.make_request(REPOSITORY, 'config/cycles/agent-memory.yaml', original))
        self.assertEqual(len(request['original_files']), 102)
        self.assertEqual((request['original_reserved_calls'], request['max_new_calls'],
                          request['max_calls_per_cycle'], request['month_max_calls']), (9, 4, 16, 100))
        self.assertEqual(recovery.requested(REPOSITORY, 'config/cycles/agent-memory.yaml', original), original + '-recovery-1')


if __name__ == '__main__':
    unittest.main()
