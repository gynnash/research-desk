"""Insight acceptance uses temporary vaults and fake membership responses only.

No test reads a real OAuth profile, accesses a public source, or spends membership
usage. The Research inputs are generated and independently reviewed through the
existing fake-provider batch path before Insight receives them.
"""

import copy
import hashlib
import json
import importlib
from pathlib import Path
import sys
import unittest

import yaml


REPOSITORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY / 'scripts'))
import test_research_batch as research_test
import researchdesk_batch as research_batch
import researchdesk_offline as store


class FakeInsightClient(research_test.FakeMemberClient):
    """Returns a bounded synthesis; its claims never assert a population trend."""

    def __init__(self):
        super().__init__()
        self.generation_text_overrides = []
        self.generation_count = 0

    @staticmethod
    def synthesis():
        return {
            'outcome': 'ready',
            'coverage_note': '仅依据论文摘要、博客节选与登记历史笔记，未核验全文或复现实验。',
            'report': {
                'title': '测试记忆材料的有限比较',
                'summary': '仅比较给定摘要、节选与历史笔记，不据此判断整个领域的趋势。',
                'comparisons': [
                    {'kind': 'author_claim', 'text': '论文材料讨论记忆机制。', 'evidence_ids': ['R1']},
                    {'kind': 'fact', 'text': '博客节选描述持久记忆块。', 'evidence_ids': ['R2']},
                    {'kind': 'inference', 'text': '历史资料可帮助提出记忆检索的待验证问题。',
                     'evidence_ids': ['R1', 'H1']}],
                'limitations': ['本次只读论文摘要、博客节选及历史笔记，未核验全文与实验。',
                                '这些资料不足以建立领域趋势或性能排序。'],
                'open_questions': ['应当怎样验证检索到的记忆可用于当前任务？']},
            'insights': [{
                'title': '记忆的可用性需要独立验证',
                'hypothesis': '可把记忆保存与任务使用分开验证，这是一条待检验的推断。',
                'evidence_ids': ['R1', 'H1'],
                'counterpoints': ['这些有限材料没有直接比较不同方案。'],
                'limitations': ['摘要、节选与历史笔记不能证明稳定的长期表现。'],
                'validation': ['设计跨会话任务，检查保存、检索和使用各环节。']}],
            'topics': [{
                'title': '保存的记忆为什么还需要验证？',
                'angle': '从给定资料解释保存、检索与实际使用的区别。',
                'audience': '希望理解 Agent Memory 的工程读者。',
                'why_now': '本轮材料提供了可比较的机制讨论，仍需人工判断写作价值。',
                'insight_indices': [0], 'evidence_ids': ['R1', 'H1'],
                'key_questions': ['怎样确认历史信息在任务中被正确使用？'],
                'evidence_gaps': ['缺少跨方案实验和生产长期运行证据。']}]}

    def infer(self, model, instructions, input_text, **limits):
        payload, _ = json.JSONDecoder().raw_decode(input_text)
        self.calls.append({'model': model, 'instructions': instructions,
                           'input_text': input_text, 'payload': payload, 'limits': limits})
        if len(self.calls) == self.fail_on_call:
            raise OSError('Synthetic unknown request outcome')
        if 'candidate' in payload:
            candidate = payload['candidate']
            decision = (self.review_decisions[self.review_count]
                        if self.review_count < len(self.review_decisions) else 'pass')
            self.review_count += 1
            targets = [('report.comparisons.%s' % index, item['evidence_ids'])
                       for index, item in enumerate(candidate['report']['comparisons'])]
            targets.insert(0, ('report', sorted(set(e for item in candidate['report']['comparisons']
                                                   for e in item['evidence_ids']))))
            targets.extend(('insights.%s' % index, item['evidence_ids'])
                           for index, item in enumerate(candidate['insights']))
            targets.extend(('topics.%s' % index, item['evidence_ids'])
                           for index, item in enumerate(candidate['topics']))
            result = {'decision': decision, 'coverage_acknowledged': True,
                      'topic_gate_confirmed': True, 'issues': [],
                      'checks': [{'target': target, 'verdict': 'supported', 'evidence_ids': evidence}
                                 for target, evidence in targets]}
            if decision == 'revise':
                result['issues'] = [{'severity': 'warning', 'location': 'report.summary',
                                     'reason': '需要明确比较的样本范围',
                                     'suggestion': '保留摘要、节选和历史笔记的阅读范围。'}]
            if self.review_mutator:
                self.review_mutator(result)
        else:
            result = self.synthesis()
            if self.research_mutator:
                self.research_mutator(result)
        text = json.dumps(result, ensure_ascii=False)
        if 'candidate' not in payload:
            if self.generation_count < len(self.generation_text_overrides):
                text = self.generation_text_overrides[self.generation_count]
            self.generation_count += 1
        return {'text': text,
                'model': self.actual_model or model,
                'response_id': 'fixture-insight-%s' % len(self.calls),
                'usage': {'input_tokens': 100, 'output_tokens': 80, 'total_tokens': 180}}


class InsightLoop(unittest.TestCase):
    def setUp(self):
        # The shared setup patches sockets to fail, creates a custom research
        # direction, and supplies handwritten arXiv/Letta parser fixtures.
        research_test.ConfigDrivenResearchBatch.setUp(self)
        receipt = research_batch.run(self.root, self.config_path, 'research',
                                     self.client, fetcher=self.fetcher)
        self.research_client = self.client
        self.research_config = copy.deepcopy(self.config)
        self.research_config_path = self.config_path
        self.research_receipt = receipt
        source = REPOSITORY / 'sources/papers/paper-4eb3be4b-7189-49aa-bafd-f88f77a972f4.md'
        frontmatter, body = source.read_text().split('---', 2)[1:]
        metadata = yaml.safe_load(frontmatter)
        metadata['topics'] = ['custom-topic']
        metadata['related_sources'] = []
        metadata['related_notes'] = []
        self.history_path = self.root / 'sources/papers' / source.name
        self.history_path.write_text('---\n' + yaml.safe_dump(metadata, allow_unicode=True,
                                                              sort_keys=False) + '---' + body)
        self.config = {
            'schema_version': 1, 'mode': 'insight_test', 'backend': 'chatgpt_plan',
            'topic': 'custom-topic', 'topics_file': 'config/research_topics.yaml',
            'models': {'generation': 'fixture-research', 'review': 'fixture-review'},
            'budget': {'max_calls': 4, 'month_max_calls': 10,
                       'max_input_chars': 30000, 'max_output_chars': 12000,
                       'timeout_seconds': 120, 'max_revisions': 1},
            'prompts': {'version': 'insight-v1'},
            'research_inputs': [{'receipt': receipt['receipt_path'],
                                 'config': self.research_config_path.relative_to(self.root).as_posix()}],
            'historical_inputs': [{'path': self.history_path.relative_to(self.root).as_posix(),
                                   'sha256': hashlib.sha256(self.history_path.read_bytes()).hexdigest(),
                                   'origin': 'human_baseline'}]}
        self.config_path = self.root / 'config/test/custom-topic/insight.yaml'
        self.client = FakeInsightClient()

    def write_config(self):
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(yaml.safe_dump(self.config, allow_unicode=True, sort_keys=False))

    def directory(self, batch_id='first'):
        return self.root / 'reports/test/custom-topic/insight-runs' / batch_id

    def run_insight(self, batch_id='first', **kwargs):
        self.write_config()
        insight = importlib.import_module('researchdesk_insight')
        return insight.run(self.root, self.config_path, batch_id, self.client,
                           fetcher=self.fetcher, **kwargs)

    def assert_blocked(self, batch_id='first'):
        try:
            receipt = self.run_insight(batch_id)
        except (store.OfflineError, ValueError, yaml.YAMLError):
            return
        self.assertNotEqual(receipt['status'], 'test_accepted')

    def old_unknown_reservations(self, count, cap=10):
        base = 'reports/test/custom-topic/membership/old-unknown'
        candidate = store.checked_yaml(self.root,
            'reports/test/custom-topic/research-batches/research/items/paper-one/candidate.yaml')['candidate']
        candidate = copy.deepcopy(candidate)
        candidate['metadata'].update(arxiv_id='2610.09999',
                                     source_url='https://arxiv.org/abs/2610.09999')
        candidate['identity_keys'] = store.identities(candidate['metadata'])
        store.save_yaml(self.root, base + '/manifest.yaml', {
            'backend': 'chatgpt_plan', 'created_at': research_batch.now(),
            'candidate': candidate, 'source_id': candidate['source_id'],
            'limits': {'month_max_calls': cap}})
        events = []
        for index in range(count):
            store.append_event(self.root, base, events, {
                'type': 'call_reserved', 'reservation_id': 'old-unknown-%s' % index,
                'month': research_batch.now()[:7], 'usage_status': 'unknown'})

    def interrupted_ledger(self):
        with self.assertRaises(store.SimulatedInterruption):
            self.run_insight(fail_after='after_review')
        base = self.directory().relative_to(self.root).as_posix()
        return base, store.read_events(self.root, base)

    def replace_test_ledger(self, base, events):
        """Re-sign attacker-controlled fixture bytes to exercise semantic gates."""
        directory = self.root / base / 'events'
        for path in directory.iterdir():
            path.unlink()
        for index, event in enumerate(events, 1):
            store.save_yaml(self.root, '%s/events/%06d.yaml' % (base, index), event)

    def assert_ledger_attack_stopped(self):
        self.assert_blocked()
        self.assertEqual(len(self.client.calls), 2)
        self.assertFalse((self.directory() / 'report.md').exists())
        self.assertFalse((self.root / 'insights/test/custom-topic/first').exists())
        self.assertFalse((self.root / 'articles/test/custom-topic/first').exists())

    def test_duplicate_reservation_in_ledger_cannot_create_outputs(self):
        base, events = self.interrupted_ledger()
        reservation = next(e for e in events if e['type'] == 'call_reserved')
        events.append(copy.deepcopy(reservation))
        self.replace_test_ledger(base, events)
        self.assert_ledger_attack_stopped()

    def test_forged_revision_reservation_in_ledger_is_rejected(self):
        base, events = self.interrupted_ledger()
        reservation = copy.deepcopy(next(e for e in events if e['type'] == 'call_reserved'))
        reservation.update(reservation_id='generation-9', revision=9)
        events.append(reservation)
        self.replace_test_ledger(base, events)
        self.assert_ledger_attack_stopped()

    def test_pending_extra_revision_after_pass_cannot_create_outputs(self):
        base, events = self.interrupted_ledger()
        reservation = copy.deepcopy(next(e for e in events if e['type'] == 'call_reserved'))
        reservation.update(reservation_id='generation-1', revision=1)
        events.append(reservation)
        self.replace_test_ledger(base, events)
        self.assert_ledger_attack_stopped()

    def test_duplicate_completion_in_ledger_cannot_create_outputs(self):
        base, events = self.interrupted_ledger()
        completion = next(e for e in events if e['type'] == 'call_completed')
        events.append(copy.deepcopy(completion))
        self.replace_test_ledger(base, events)
        self.assert_ledger_attack_stopped()

    def test_completion_without_earlier_reservation_is_rejected(self):
        base, events = self.interrupted_ledger()
        events = [e for e in events if not (e['type'] == 'call_reserved'
                                          and e['role'] == 'generation')]
        self.replace_test_ledger(base, events)
        self.assert_ledger_attack_stopped()

    def test_completion_model_cannot_differ_from_reserved_model(self):
        base, events = self.interrupted_ledger()
        completion = next(e for e in events if e['type'] == 'call_completed')
        completion['model_id'] = 'fixture-review'
        self.replace_test_ledger(base, events)
        self.assert_ledger_attack_stopped()

    def test_completion_usage_cannot_differ_from_checkpoint(self):
        base, events = self.interrupted_ledger()
        completion = next(e for e in events if e['type'] == 'call_completed')
        completion['usage'] = {'total_tokens': 0}
        self.replace_test_ledger(base, events)
        self.assert_ledger_attack_stopped()

    def test_completion_checkpoint_must_belong_to_same_role_and_revision(self):
        base, events = self.interrupted_ledger()
        generation, review = [e for e in events if e['type'] == 'call_completed']
        generation['response_path'] = review['response_path']
        generation['response_sha256'] = review['response_sha256']
        self.replace_test_ledger(base, events)
        self.assert_ledger_attack_stopped()

    def test_unknown_ledger_event_cannot_approve_writing_or_outputs(self):
        base, events = self.interrupted_ledger()
        events.append({'type': 'writing_approved', 'approved': True,
                       'at': research_batch.now()})
        self.replace_test_ledger(base, events)
        self.assert_ledger_attack_stopped()

    def test_fake_local_validation_failure_on_valid_generation_is_rejected(self):
        base, events = self.interrupted_ledger()
        generation = next(e for e in events if e['type'] == 'call_completed'
                          and e['role'] == 'generation')
        checkpoint = store.checked_yaml(self.root, generation['response_path'])
        # Remove review0's records so the forged event must be rejected because
        # generation0 is valid, not merely because review0 already happened.
        events = [e for e in events if e.get('role') != 'review'
                  and e['type'] != 'acceptance_interruption']
        events.append({'type': 'local_validation_failed', 'revision': 0,
                       'response_sha256': store.digest(checkpoint['result']['text'].encode()),
                       'at': research_batch.now()})
        self.replace_test_ledger(base, events)
        self.assert_ledger_attack_stopped()

    def test_manifest_fields_are_rebound_even_when_fingerprint_is_unchanged(self):
        base, _ = self.interrupted_ledger()
        path = self.root / base / 'manifest.yaml'
        sidecar = path.with_name(path.name + '.sha256')
        original_bytes, original_sidecar = path.read_bytes(), sidecar.read_bytes()
        original = yaml.safe_load(original_bytes)
        models = dict(original['models'], generation='fixture-unbound-model')
        budget = dict(original['budget'], month_max_calls=1000)
        authorization = dict(original['authorization'], account_fingerprint='another-account')
        changes = [
            ('models', models), ('budget', budget), ('authorization', authorization),
            ('input_fingerprint', '0' * 64),
            ('provenance', {'research_inputs': [], 'historical_inputs': []}),
            ('topic', 'another-topic'), ('batch_id', 'another-batch'),
            ('mode', 'production'), ('backend', 'mock'),
            ('writing_started', True), ('schema_version', 2)]
        try:
            for key, value in changes:
                manifest = dict(copy.deepcopy(original), **{key: value})
                self.assertEqual(manifest['fingerprint'], original['fingerprint'])
                path.write_text(yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False))
                sidecar.write_text(store.digest(path.read_bytes()) + '\n')
                with self.subTest(field=key):
                    self.assert_ledger_attack_stopped()
        finally:
            path.write_bytes(original_bytes)
            sidecar.write_bytes(original_sidecar)

    def test_duplicate_acceptance_interruption_is_rejected(self):
        base, events = self.interrupted_ledger()
        events.append(copy.deepcopy(next(e for e in events
                                        if e['type'] == 'acceptance_interruption')))
        self.replace_test_ledger(base, events)
        self.assert_ledger_attack_stopped()

    def test_completed_extra_revision_after_pass_cannot_create_outputs(self):
        base, events = self.interrupted_ledger()
        reservation = copy.deepcopy(next(e for e in events if e['type'] == 'call_reserved'))
        completion = copy.deepcopy(next(e for e in events if e['type'] == 'call_completed'))
        original_checkpoint = store.checked_yaml(self.root, completion['response_path'])
        path = base + '/checkpoints/generation-1.yaml'
        sha = store.save_yaml(self.root, path, original_checkpoint)
        reservation.update(reservation_id='generation-1', revision=1)
        completion.update(reservation_id='generation-1', revision=1,
                          response_path=path, response_sha256=sha)
        events.extend([reservation, completion])
        self.replace_test_ledger(base, events)
        self.assert_ledger_attack_stopped()

    def test_old_membership_unknown_calls_are_in_shared_monthly_budget(self):
        self.old_unknown_reservations(2)
        result = self.run_insight()
        self.assertEqual(result['status'], 'test_accepted')
        self.assertEqual(result['monthly_reserved_calls'], 8)
        self.assertEqual(result['effective_month_max_calls'], 10)

    def test_exhausted_monthly_budget_blocks_insight_before_call(self):
        self.old_unknown_reservations(6)
        self.assert_blocked()
        self.assertEqual(self.client.calls, [])

    def test_research_budget_counts_prior_insight_calls_in_reverse_direction(self):
        self.old_unknown_reservations(4)
        result = self.run_insight()
        self.assertEqual(result['status'], 'test_accepted')
        self.assertEqual(result['monthly_reserved_calls'], 10)
        self.fetcher.paper = self.fetcher.paper.replace('memory blocks', 'updated memory boundaries')
        self.fetcher.blog = self.fetcher.blog.replace('persistent memory blocks', 'updated memory boundaries')
        before = len(self.research_client.calls)
        result = research_batch.run(self.root, self.research_config_path, 'research-after-insight',
                                    self.research_client, fetcher=self.fetcher)
        self.assertEqual(len(self.research_client.calls), before)
        self.assertEqual(result['status'], 'failed')

    def test_paper_and_its_own_history_are_not_two_independent_sources(self):
        metadata = store.frontmatter(self.history_path)
        metadata.update(arxiv_id='2610.01234', source_url='https://arxiv.org/abs/2610.01234',
                        doi='10.48550/arxiv.2610.01234')
        body = self.history_path.read_text().split('---', 2)[2]
        self.history_path.write_text('---\n' + yaml.safe_dump(metadata, allow_unicode=True,
                                                              sort_keys=False) + '---' + body)
        self.config['historical_inputs'][0]['sha256'] = store.digest(self.history_path.read_bytes())
        self.assert_blocked()
        self.assertLessEqual(len(self.client.calls), 1)

    def test_two_model_calls_create_report_insight_and_unapproved_topic(self):
        result = self.run_insight()
        self.assertEqual(result['status'], 'test_accepted')
        self.assertEqual(result['reserved_calls'], 2)
        self.assertEqual(result['completed_calls'], 2)
        self.assertEqual([c['model'] for c in self.client.calls],
                         ['fixture-research', 'fixture-review'])
        self.assertFalse(result['writing_started'])
        self.assertTrue(result['approval_required'])
        self.assertEqual(result['outputs']['report'],
                         'reports/test/custom-topic/insight-runs/first/report.md')
        self.assertEqual(len(result['outputs']['insights']), 1)
        self.assertEqual(len(result['outputs']['topics']), 1)
        for path in result['outputs']['topics']:
            metadata = store.frontmatter(self.root / path)
            self.assertEqual(metadata['status'], 'proposed')
            self.assertIs(metadata['approval_required'], True)
            self.assertIs(metadata['writing_started'], False)
            self.assertIs(metadata['publish_authorized'], False)

    def test_review_receives_same_source_material_as_generation(self):
        self.run_insight()
        generation, review = [c['payload'] for c in self.client.calls]
        for key in ('evidence', 'research_context', 'topic'):
            self.assertEqual(generation[key], review[key])
        serialized = json.dumps(generation, ensure_ascii=False)
        self.assertIn('R1', serialized)
        self.assertIn('H1', serialized)
        self.assertIn('abstract_only', serialized)
        self.assertIn('excerpt', serialized)

    def test_member_response_must_respect_configured_output_limit(self):
        self.config['budget']['max_output_chars'] = 1000
        self.assert_blocked()
        self.assertEqual(len(self.client.calls), 1)

    def test_completed_replay_spends_no_additional_calls(self):
        first = self.run_insight()
        second = self.run_insight()
        self.assertEqual(first['outputs'], second['outputs'])
        self.assertEqual(len(self.client.calls), 2)

    def test_completed_replay_survives_other_runs_using_monthly_budget(self):
        first = self.run_insight()
        self.old_unknown_reservations(2)
        second = self.run_insight()
        self.assertEqual(first['outputs'], second['outputs'])
        self.assertEqual(len(self.client.calls), 2)

    def test_interruption_after_review_replays_without_new_calls(self):
        with self.assertRaises(store.SimulatedInterruption):
            self.run_insight(fail_after='after_review')
        self.assertEqual(len(self.client.calls), 2)
        self.assertFalse((self.directory() / 'report.md').exists())
        result = self.run_insight()
        self.assertEqual(result['status'], 'test_accepted')
        self.assertEqual(len(self.client.calls), 2)

    def test_single_revision_is_reviewed_with_four_call_cap(self):
        self.client.review_decisions = ['revise', 'pass']
        result = self.run_insight()
        self.assertEqual(result['status'], 'test_accepted')
        self.assertEqual(len(self.client.calls), 4)
        self.assertEqual([c['model'] for c in self.client.calls],
                         ['fixture-research', 'fixture-review'] * 2)
        self.run_insight()
        self.assertEqual(len(self.client.calls), 4)

    def test_malformed_initial_json_gets_one_revision_and_independent_review(self):
        self.client.generation_text_overrides = [json.dumps(FakeInsightClient.synthesis()) + '}']
        result = self.run_insight()
        self.assertEqual(result['status'], 'test_accepted')
        self.assertEqual(result['revision_count'], 1)
        self.assertEqual(result['reserved_calls'], 3)
        self.assertEqual(result['completed_calls'], 3)
        self.assertEqual([call['model'] for call in self.client.calls],
                         ['fixture-research', 'fixture-research', 'fixture-review'])
        self.assertEqual(self.client.review_count, 1)
        self.run_insight()
        self.assertEqual(len(self.client.calls), 3)

    def test_second_malformed_generation_does_not_get_another_retry(self):
        invalid = json.dumps(FakeInsightClient.synthesis()) + '}'
        self.client.generation_text_overrides = [invalid, invalid]
        self.assert_blocked()
        self.assertEqual(len(self.client.calls), 2)
        self.assertEqual(self.client.review_count, 0)
        self.assert_blocked()
        self.assertEqual(len(self.client.calls), 2)
        self.assertFalse((self.directory() / 'report.md').exists())

    def test_second_revision_is_not_retried(self):
        self.client.review_decisions = ['revise', 'revise', 'pass']
        self.assert_blocked()
        self.assertLessEqual(len(self.client.calls), 4)
        self.run_insight()
        self.assertLessEqual(len(self.client.calls), 4)

    def test_two_call_budget_does_not_begin_a_revision(self):
        self.config['budget']['max_calls'] = 2
        self.client.review_decisions = ['revise', 'pass']
        self.assert_blocked()
        self.assertEqual(len(self.client.calls), 2)
        self.run_insight()
        self.assertEqual(len(self.client.calls), 2)

    def test_unknown_model_outcome_is_reserved_and_never_resent(self):
        self.client.fail_on_call = 1
        with self.assertRaises(OSError):
            self.run_insight()
        self.assertEqual(len(self.client.calls), 1)
        self.client.fail_on_call = None
        self.assert_blocked()
        self.assertEqual(len(self.client.calls), 1)

    def test_insufficient_evidence_does_not_force_insight_or_topic(self):
        self.client.research_mutator = lambda result: (result.clear(), result.update(
            outcome='insufficient_evidence', reason='样本有限，尚不能生成有充分依据的洞察。'))
        result = self.run_insight()
        self.assertNotEqual(result['status'], 'test_accepted')
        self.assertEqual(len(self.client.calls), 1)
        self.assertFalse((self.directory() / 'report.md').exists())
        self.assertFalse((self.root / 'articles/test/custom-topic/first').exists())

    def test_model_cannot_self_approve_or_start_writing(self):
        insight = importlib.import_module('researchdesk_insight')
        self.write_config()
        config = insight.inputs.load_config(self.root, self.config_path)
        bundle = insight.inputs.prepare_bundle(self.root, config, fetcher=self.fetcher)
        for key, value in (('status', 'approved'), ('approved', True),
                           ('writing_started', True), ('publish_authorized', True)):
            candidate = FakeInsightClient.synthesis()
            candidate['topics'][0][key] = value
            with self.subTest(key=key), self.assertRaises((store.OfflineError, ValueError)):
                insight.validate_candidate(candidate, bundle)
        self.client.research_mutator = lambda result: result['topics'][0].update(status='approved')
        self.assert_blocked()
        self.assertEqual(len(self.client.calls), 1)

    def test_unknown_evidence_cannot_reach_review_or_output(self):
        self.client.research_mutator = lambda result: result['report']['comparisons'][0].update(
            evidence_ids=['R999'])
        self.assert_blocked()
        self.assertEqual(len(self.client.calls), 1)

    def test_insight_needs_new_research_and_historical_evidence(self):
        self.client.research_mutator = lambda result: result['insights'][0].update(evidence_ids=['R1', 'R2'])
        self.assert_blocked()
        self.assertEqual(len(self.client.calls), 1)

    def test_more_than_two_insights_is_rejected(self):
        self.client.research_mutator = lambda result: result['insights'].extend(
            [copy.deepcopy(result['insights'][0]), copy.deepcopy(result['insights'][0])])
        self.assert_blocked()
        self.assertEqual(len(self.client.calls), 1)

    def test_more_than_two_topic_cards_is_rejected(self):
        self.client.research_mutator = lambda result: result['topics'].extend(
            [copy.deepcopy(result['topics'][0]), copy.deepcopy(result['topics'][0])])
        self.assert_blocked()
        self.assertEqual(len(self.client.calls), 1)

    def test_unknown_claim_kind_is_rejected(self):
        self.client.research_mutator = lambda result: result['report']['comparisons'][0].update(kind='proven')
        self.assert_blocked()
        self.assertEqual(len(self.client.calls), 1)

    def test_history_note_alone_cannot_be_claimed_as_original_fact(self):
        self.client.research_mutator = lambda result: result['report']['comparisons'][0].update(
            kind='fact', evidence_ids=['H1'])
        self.assert_blocked()
        self.assertEqual(len(self.client.calls), 1)

    def test_topic_must_reference_an_existing_insight(self):
        self.client.research_mutator = lambda result: result['topics'][0].update(insight_indices=[999])
        self.assert_blocked()
        self.assertEqual(len(self.client.calls), 1)

    def test_pass_must_review_every_output_and_comparison(self):
        self.client.review_mutator = lambda result: result['checks'].pop()
        self.assert_blocked()
        self.assertEqual(len(self.client.calls), 2)

    def test_pass_with_blocking_issue_cannot_publish_test_outputs(self):
        self.client.review_mutator = lambda result: result['issues'].append({
            'severity': 'blocking', 'location': 'insights.0', 'reason': '证据不足',
            'suggestion': '缩小推断范围'})
        self.assert_blocked()
        self.assertFalse((self.directory() / 'report.md').exists())

    def test_pass_with_unsupported_check_is_rejected(self):
        self.client.review_mutator = lambda result: result['checks'][0].update(verdict='unsupported')
        self.assert_blocked()
        self.assertEqual(len(self.client.calls), 2)

    def test_pass_requires_coverage_and_topic_gate_acknowledgement(self):
        insight = importlib.import_module('researchdesk_insight')
        self.run_insight()
        self.write_config()
        config = insight.inputs.load_config(self.root, self.config_path)
        bundle = insight.inputs.prepare_bundle(self.root, config, fetcher=self.fetcher)
        candidate = self.client.calls[1]['payload']['candidate']
        review = FakeInsightClient().infer('fixture-review', 'validation fixture',
                                           json.dumps({'candidate': candidate}))
        review = json.loads(review['text'])
        for flag in ('coverage_acknowledged', 'topic_gate_confirmed'):
            invalid_review = copy.deepcopy(review)
            invalid_review[flag] = False
            with self.subTest(flag=flag), self.assertRaises((store.OfflineError, ValueError)):
                insight.validate_review(candidate, invalid_review, bundle)
        self.assertEqual(len(self.client.calls), 2)

    def test_same_models_are_rejected_before_call(self):
        self.config['models']['review'] = self.config['models']['generation']
        self.assert_blocked()
        self.assertEqual(self.client.calls, [])

    def test_actual_model_mismatch_stops_and_never_reissues(self):
        self.client.actual_model = 'wrong-model'
        self.assert_blocked()
        self.assertEqual(len(self.client.calls), 1)
        self.client.actual_model = None
        self.assert_blocked()
        self.assertEqual(len(self.client.calls), 1)

    def test_unavailable_model_and_missing_plan_permission_cannot_spend(self):
        self.client.catalog = self.client.catalog[:1]
        self.assert_blocked()
        self.assertEqual(self.client.calls, [])
        self.client = FakeInsightClient()
        self.client.account['plan_permission'] = False
        self.assert_blocked('no-plan')
        self.assertEqual(self.client.calls, [])

    def test_history_hash_mismatch_rejects_without_call_or_overwrite(self):
        self.history_path.write_text(self.history_path.read_text() + '\n人工新增解释\n')
        before = self.history_path.read_bytes()
        self.assert_blocked()
        self.assertEqual(self.client.calls, [])
        self.assertEqual(self.history_path.read_bytes(), before)

    def test_unaccepted_research_receipt_rejects_before_insight_call(self):
        receipt = self.root / self.research_receipt['receipt_path']
        value = yaml.safe_load(receipt.read_text())
        value['status'] = 'partial'
        receipt.write_text(yaml.safe_dump(value, allow_unicode=True, sort_keys=False))
        receipt.with_name(receipt.name + '.sha256').write_text(store.digest(receipt.read_bytes()) + '\n')
        self.assert_blocked()
        self.assertEqual(self.client.calls, [])

    def test_mock_research_cannot_become_real_insight(self):
        receipt = self.root / self.research_receipt['receipt_path']
        value = yaml.safe_load(receipt.read_text())
        value['backend'] = 'mock'
        receipt.write_text(yaml.safe_dump(value, allow_unicode=True, sort_keys=False))
        receipt.with_name(receipt.name + '.sha256').write_text(store.digest(receipt.read_bytes()) + '\n')
        self.assert_blocked()
        self.assertEqual(self.client.calls, [])

    def test_changed_original_material_invalidates_accepted_research(self):
        self.fetcher.paper = self.fetcher.paper.replace('memory blocks', 'changed source evidence')
        self.assert_blocked()
        self.assertEqual(self.client.calls, [])

    def test_changed_research_report_is_preserved_and_rejected(self):
        path = self.root / self.research_receipt['items'][0]['report_path']
        path.write_text(path.read_text() + '\n人工修改\n')
        before = path.read_bytes()
        self.assert_blocked()
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(self.client.calls, [])

    def test_config_paths_and_cross_topic_inputs_are_rejected(self):
        original = copy.deepcopy(self.config)
        changes = [('topics_file', '../outside.yaml'),
                   ('topic', 'another-topic')]
        for key, value in changes:
            self.config = copy.deepcopy(original)
            self.config[key] = value
            with self.subTest(key=key):
                self.assert_blocked('invalid-' + key.replace('_', '-'))
                self.assertEqual(self.client.calls, [])
        self.config = copy.deepcopy(original)
        self.config['research_inputs'][0]['receipt'] = 'reports/test/another-topic/research-batches/x/receipt.yaml'
        self.assert_blocked('cross-topic')
        self.assertEqual(self.client.calls, [])

    def test_historical_test_path_and_symlink_are_rejected(self):
        original = copy.deepcopy(self.config['historical_inputs'])
        target = self.root / 'reports/test/custom-topic/history.md'
        target.write_bytes(self.history_path.read_bytes())
        self.config['historical_inputs'][0]['path'] = target.relative_to(self.root).as_posix()
        self.assert_blocked('test-history')
        self.assertEqual(self.client.calls, [])
        self.config['historical_inputs'] = copy.deepcopy(original)
        link = self.history_path.parent / 'link.md'
        link.symlink_to(self.history_path)
        self.config['historical_inputs'][0]['path'] = link.relative_to(self.root).as_posix()
        self.assert_blocked('linked-history')
        self.assertEqual(self.client.calls, [])

    def test_invalid_config_fields_duplicate_keys_and_budget_are_rejected(self):
        self.config['surprise'] = 'unsupported'
        self.assert_blocked()
        self.assertEqual(self.client.calls, [])
        self.config.pop('surprise')
        for key, value in (('max_calls', True), ('max_calls', 8), ('max_revisions', 2)):
            original = copy.deepcopy(self.config['budget'])
            self.config['budget'][key] = value
            with self.subTest(key=key, value=value):
                self.assert_blocked('invalid-' + key.replace('_', '-'))
                self.assertEqual(self.client.calls, [])
            self.config['budget'] = original
        self.write_config()
        self.config_path.write_text(self.config_path.read_text() + '\nbackend: api_key\n')
        insight = importlib.import_module('researchdesk_insight')
        with self.assertRaises((store.OfflineError, ValueError, yaml.YAMLError)):
            insight.run(self.root, self.config_path, 'duplicate-key', self.client, fetcher=self.fetcher)
        self.assertEqual(self.client.calls, [])

    def test_output_edit_is_never_overwritten_or_reanalysed(self):
        result = self.run_insight()
        for index, relative in enumerate([result['outputs']['report']] + result['outputs']['insights']
                                         + result['outputs']['topics']):
            path = self.root / relative
            path.write_text(path.read_text() + '\n人工修订\n')
            before = path.read_bytes()
            with self.subTest(path=relative):
                self.assert_blocked()
                self.assertEqual(path.read_bytes(), before)
                self.assertEqual(len(self.client.calls), 2)

    def test_checkpoint_edit_is_preserved_and_never_reissued(self):
        self.run_insight()
        path = self.directory() / 'checkpoints/generation-0.yaml'
        path.write_text(path.read_text() + '\nmanual_edit: true\n')
        before = path.read_bytes()
        self.assert_blocked()
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(len(self.client.calls), 2)

    def test_same_batch_cannot_change_budget_to_reset_its_calls(self):
        self.run_insight()
        self.config['budget']['max_calls'] = 2
        self.assert_blocked()
        self.assertEqual(len(self.client.calls), 2)

    def test_symlink_topic_output_cannot_write_formal_articles(self):
        target = self.root / 'articles/human'
        target.mkdir()
        note = target / 'topic-1.md'
        note.write_text('已有正式人工文章，必须保留。\n')
        link = self.root / 'articles/test/custom-topic/first'
        link.parent.mkdir(parents=True, exist_ok=True)
        link.symlink_to(target, target_is_directory=True)
        before = note.read_bytes()
        self.assert_blocked()
        self.assertEqual(note.read_bytes(), before)
        self.assertEqual(list(target.iterdir()), [note])

    def test_existing_notes_unchanged_and_new_outputs_are_only_test_paths(self):
        before = {path: path.read_bytes() for path in self.root.rglob('*') if path.is_file()}
        self.run_insight()
        for path, content in before.items():
            self.assertEqual(path.read_bytes(), content, str(path))
        for path in self.root.rglob('*'):
            if not path.is_file() or path in before:
                continue
            relative = path.relative_to(self.root).as_posix()
            self.assertTrue(any(relative.startswith(prefix) for prefix in (
                'config/test/custom-topic/insight.yaml',
                'reports/test/custom-topic/insight-runs/first/',
                'insights/test/custom-topic/first/',
                'articles/test/custom-topic/first/')), relative)
        self.assertFalse((self.root / '.github').exists())


if __name__ == '__main__':
    unittest.main()
