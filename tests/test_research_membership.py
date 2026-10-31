"""Membership research guardrails use disposable vaults and a fake provider.

These checks spend no member quota and never read a real credential profile.
"""

import copy
import hashlib
import json
from pathlib import Path
import shutil
import socket
import sys
import tempfile
import unittest
from unittest import mock

import yaml


REPOSITORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY / 'scripts'))
import researchdesk_analyze as analyze
import researchdesk_collect as collect
import researchdesk_offline as store


class AbstractFetcher:
    def __init__(self):
        self.text = (REPOSITORY / 'workflows/test/example-topic/fixtures/collection/arxiv.xml').read_text()
        self.calls = []

    def fetch(self, url):
        self.calls.append(url)
        return {'url': url, 'requested_url': url, 'status': 200, 'redirects': [],
                'content_type': 'application/atom+xml', 'text': self.text,
                'fetched_at': '2026-10-19T00:00:00+00:00',
                'sha256': hashlib.sha256(self.text.encode()).hexdigest()}


class FakeMembershipClient:
    def __init__(self):
        self.calls = []
        self.catalog = [{'slug': 'test-research-model', 'display_name': 'Test Research'},
                        {'slug': 'test-review-model', 'display_name': 'Test Review'}]
        self.decisions = ['pass']
        self.actual_model = None
        self.fail_on_call = None
        self.research_mutator = None
        self.review_mutator = None
        self.usage = None
        self.account = {'authenticated': True, 'plan_permission': True,
                        'authorization': 'official_chatgpt_oauth',
                        'account_fingerprint': 'fake-test-account'}

    def status(self):
        return copy.deepcopy(self.account)

    def models(self):
        return copy.deepcopy(self.catalog)

    def authorization_summary(self):
        return {'identity_verified': True, 'plan_usage_enabled': True,
                'scope': ['chatgpt.tokens.use.direct']}

    def infer(self, model, instructions, input_text, **limits):
        self.calls.append({'model': model, 'instructions': instructions,
                           'input_text': input_text, 'limits': limits})
        if len(self.calls) == self.fail_on_call:
            raise OSError('Simulated interrupted stream without a terminal event')
        payload, _ = json.JSONDecoder().raw_decode(input_text)
        if 'candidate' in payload:
            reviewed = payload['candidate']
            decision = self.decisions[min(sum(c['model'] == 'test-review-model' for c in self.calls) - 1,
                                          len(self.decisions) - 1)]
            result = {'decision': decision, 'coverage_acknowledged': True, 'issues': [],
                      'checks': [{'claim_index': i, 'verdict': 'supported',
                                  'evidence_ids': c['evidence_ids']}
                                 for i, c in enumerate(reviewed['claims'])]}
            if self.review_mutator:
                self.review_mutator(result)
        else:
            result = {'summary': '这是一份仅核对固定摘要的测试研究。',
                      'claims': [
                          {'kind': 'author_claim', 'text': '材料称这是描述记忆块的虚构练习。', 'evidence_ids': ['A1']},
                          {'kind': 'fact', 'text': '摘要声明没有报告测量结果。', 'evidence_ids': ['A2']},
                          {'kind': 'inference', 'text': '该摘要不足以比较系统性能。', 'evidence_ids': ['A2']}],
                      'limitations': ['仅阅读摘要，未核验全文或实验数据', '材料是虚构的解析测试样例。']}
            if self.research_mutator:
                self.research_mutator(result)
        return {'text': json.dumps(result, ensure_ascii=False),
                'model': self.actual_model or model, 'response_id': 'response-test-%s' % len(self.calls),
                'usage': self.usage}


class MembershipResearchAcceptance(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='researchdesk-membership-tests-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        for relative in ('config/test/example-topic', 'sources/papers', 'sources/blogs',
                         'reports/test/agent-memory', 'insights', 'articles', 'workflows'):
            (self.root / relative).mkdir(parents=True, exist_ok=True)
        for name in ('legacy_sources.yaml',):
            shutil.copyfile(REPOSITORY / 'config' / name, self.root / 'config' / name)
        (self.root / 'config/research_topics.yaml').write_text(yaml.safe_dump({
            'schema_version': 1, 'topics': {'agent-memory': {
                'name': 'Fictional test topic', 'enabled': True,
                'description': 'Synthetic offline framework input.',
                'scope': ['Synthetic records'], 'keywords': ['fixture', 'memory']}}}))
        config = yaml.safe_load((REPOSITORY / 'config/test/example-topic/collection.yaml').read_text())
        config['topic'] = 'agent-memory'
        config['sources'] = [source for source in config['sources'] if source['id'] == 'arxiv']
        config['sources'][0].pop('fallback_urls', None)
        config_path = self.root / 'config/test/example-topic/collection.yaml'
        config_path.write_text(yaml.safe_dump(config, allow_unicode=True))
        self.fetcher = AbstractFetcher()
        self.receipt = collect.collect(self.root, config_path, 'collection-test', fetcher=self.fetcher)['artifacts']['receipt']
        self.client = FakeMembershipClient()

    def run_batch(self, batch='member-first', **overrides):
        arguments = {'research_model': 'test-research-model', 'review_model': 'test-review-model',
                     'fetcher': self.fetcher, 'max_calls': 4}
        arguments.update(overrides)
        with mock.patch.object(socket, 'create_connection', side_effect=AssertionError('Real network prohibited')), \
                mock.patch.object(socket.socket, 'connect', side_effect=AssertionError('Real network prohibited')):
            return analyze.run(self.root, self.receipt, batch, self.client, **arguments)

    def directory(self, batch='member-first'):
        return self.root / 'reports/test/agent-memory/membership' / batch

    def event_values(self):
        return [yaml.safe_load(p.read_text()) for p in sorted(self.directory().glob('events/*.yaml'))]

    def test_real_mode_uses_two_models_and_preserves_unknown_usage(self):
        result = self.run_batch()
        self.assertEqual(result['status'], 'test_accepted')
        self.assertIs(result['production_accepted'], False)
        self.assertEqual(result['coverage'], 'abstract_only')
        self.assertEqual(result['completed_calls'], 2)
        self.assertEqual(result['reserved_calls'], 2)
        self.assertEqual(result['actual_models'], ['test-research-model', 'test-review-model'])
        self.assertEqual(result['usage'], [None, None])
        self.assertIsNone(result['membership_remaining_quota'])
        self.assertIsNone(result['api_billed_cost'])
        self.assertIn('TEST', (self.root / result['report_path']).read_text())
        self.assertEqual(list(self.root.glob('.github/workflows/*')), [])

    def test_reviewer_receives_original_evidence_and_candidate(self):
        self.run_batch()
        generated = json.loads(self.client.calls[0]['input_text'])
        reviewed = json.loads(self.client.calls[1]['input_text'])
        self.assertEqual(generated['original_abstract'], reviewed['original_abstract'])
        self.assertEqual(len(reviewed['candidate']['claims']), 3)
        self.assertIn('独立', self.client.calls[1]['instructions'])
        self.assertNotEqual(self.client.calls[0]['model'], self.client.calls[1]['model'])

    def test_same_requested_model_is_blocked_without_spending(self):
        with self.assertRaises(store.OfflineError):
            self.run_batch(review_model='test-research-model')
        self.assertEqual(self.client.calls, [])

    def test_unavailable_review_model_is_blocked_without_spending(self):
        self.client.catalog = self.client.catalog[:1]
        with self.assertRaises(store.OfflineError):
            self.run_batch()
        self.assertEqual(self.client.calls, [])

    def test_identity_without_member_usage_scope_cannot_spend(self):
        self.client.account['plan_permission'] = False
        with self.assertRaises(store.OfflineError):
            self.run_batch()
        self.assertEqual(self.client.calls, [])

    def test_different_account_cannot_resume_original_batch(self):
        self.run_batch()
        self.client.account['account_fingerprint'] = 'different-test-account'
        with self.assertRaises(store.OfflineError):
            self.run_batch()
        self.assertEqual(len(self.client.calls), 2)

    def test_actual_model_mismatch_keeps_unknown_reservation_without_retry(self):
        self.client.actual_model = 'test-research-model'
        with self.assertRaises(store.OfflineError):
            self.run_batch()
        self.assertEqual(len(self.client.calls), 2)
        with self.assertRaises(store.OfflineError):
            self.run_batch()
        self.assertEqual(len(self.client.calls), 2)
        events = self.event_values()
        self.assertEqual(sum(e['type'] == 'call_reserved' for e in events), 2)
        self.assertEqual(sum(e['type'] == 'call_completed' for e in events), 1)
        self.assertFalse((self.directory() / 'receipt.yaml').exists())

    def test_unknown_stream_outcome_does_not_reissue_on_resume(self):
        self.client.fail_on_call = 1
        with self.assertRaises(OSError):
            self.run_batch()
        with self.assertRaises(store.OfflineError):
            self.run_batch()
        self.assertEqual(len(self.client.calls), 1)
        self.assertEqual(self.event_values()[0]['usage_status'], 'unknown')

    def test_completed_run_is_idempotent(self):
        first = self.run_batch()
        second = self.run_batch()
        self.assertTrue(second['cached'])
        self.assertEqual(first['report_sha256'], second['report_sha256'])
        self.assertEqual(len(self.client.calls), 2)

    def test_new_batch_cannot_research_identical_evidence_again(self):
        self.run_batch()
        with self.assertRaises(store.OfflineError):
            self.run_batch(batch='member-second')
        self.assertEqual(len(self.client.calls), 2)

    def test_budget_and_model_binding_cannot_change_on_resume(self):
        self.run_batch()
        with self.assertRaises(store.OfflineError):
            self.run_batch(max_calls=2)
        self.assertEqual(len(self.client.calls), 2)

    def test_formal_and_preexisting_test_notes_remain_unchanged(self):
        notes = [self.root / 'reports/human.md', self.root / 'reports/test/agent-memory/human.md']
        for path in notes:
            path.write_text('人工批注：不要覆盖。\n')
        before = {str(path): path.read_bytes() for path in notes}
        self.run_batch()
        self.assertEqual(before, {str(path): path.read_bytes() for path in notes})

    def test_human_edit_to_historical_test_note_blocks_resume(self):
        note = self.root / 'reports/test/agent-memory/human.md'
        note.write_text('运行前人工笔记\n')
        self.run_batch()
        note.write_text('运行后新增人工笔记\n')
        with self.assertRaises(store.OfflineError):
            self.run_batch()
        self.assertEqual(note.read_text(), '运行后新增人工笔记\n')
        self.assertEqual(len(self.client.calls), 2)

    def test_human_edit_to_report_is_never_overwritten(self):
        result = self.run_batch()
        report = self.root / result['report_path']
        report.write_text(report.read_text() + '\n人工修改\n')
        after = report.read_bytes()
        with self.assertRaises(store.OfflineError):
            self.run_batch()
        self.assertEqual(report.read_bytes(), after)
        self.assertEqual(len(self.client.calls), 2)

    def test_modified_checkpoint_stops_without_more_requests(self):
        self.run_batch()
        checkpoint = self.directory() / 'checkpoints/research-0.yaml'
        checkpoint.write_text(checkpoint.read_text() + '\nmanual_change: true\n')
        with self.assertRaises(store.OfflineError):
            self.run_batch()
        self.assertEqual(len(self.client.calls), 2)

    def test_recomputed_receipt_hash_cannot_falsify_ledger(self):
        self.run_batch()
        receipt = self.directory() / 'receipt.yaml'
        value = yaml.safe_load(receipt.read_text())
        value['completed_calls'] = 0
        receipt.write_text(yaml.safe_dump(value, allow_unicode=True))
        Path(str(receipt) + '.sha256').write_text(store.digest(receipt.read_bytes()) + '\n')
        with self.assertRaisesRegex(store.OfflineError, '账本'):
            self.run_batch()
        self.assertEqual(len(self.client.calls), 2)

    def test_topic_configuration_change_invalidates_saved_analysis(self):
        self.run_batch()
        config = self.root / 'config/research_topics.yaml'
        config.write_text(config.read_text() + '\n# Human changed research context\n')
        with self.assertRaises(store.OfflineError):
            self.run_batch()
        self.assertEqual(len(self.client.calls), 2)

    def test_changed_original_abstract_blocks_before_inference(self):
        self.fetcher.text = self.fetcher.text.replace('no measured results', 'changed measured results')
        with self.assertRaises(store.OfflineError):
            self.run_batch()
        self.assertEqual(self.client.calls, [])

    def test_pass_requires_every_claim_to_be_checked(self):
        self.client.review_mutator = lambda result: result.update(checks=[])
        with self.assertRaises(store.OfflineError):
            self.run_batch()
        self.assertFalse((self.directory() / 'receipt.yaml').exists())

    def test_pass_cannot_hide_unsupported_claim(self):
        self.client.review_mutator = lambda result: result['checks'][0].update(verdict='unsupported')
        with self.assertRaises(store.OfflineError):
            self.run_batch()

    def test_unknown_review_severity_is_not_accepted(self):
        self.client.review_mutator = lambda result: result.update(issues=[{
            'severity': 'unknown', 'location': 'claim 0', 'reason': 'Unsupported', 'suggestion': 'Revise'}])
        with self.assertRaises(store.OfflineError):
            self.run_batch()

    def test_abstract_coverage_requires_explicit_review_acknowledgment(self):
        self.client.review_mutator = lambda result: result.pop('coverage_acknowledged')
        with self.assertRaises(store.OfflineError):
            self.run_batch()

    def test_research_cannot_cite_nonexistent_evidence(self):
        self.client.research_mutator = lambda result: result['claims'][0].update(evidence_ids=['A999'])
        with self.assertRaises(store.OfflineError):
            self.run_batch()
        self.assertEqual(len(self.client.calls), 1)

    def test_one_revision_uses_four_calls_and_shared_evidence(self):
        self.client.decisions = ['revise', 'pass']
        result = self.run_batch()
        self.assertEqual(result['status'], 'test_accepted')
        self.assertEqual(result['revision_count'], 1)
        self.assertEqual(len(self.client.calls), 4)
        self.assertIn('上轮候选及独立审阅', self.client.calls[2]['input_text'])
        self.assertEqual([call['model'] for call in self.client.calls],
                         ['test-research-model', 'test-review-model'] * 2)

    def test_second_revision_request_stops_after_four_calls(self):
        self.client.decisions = ['revise', 'revise']
        result = self.run_batch()
        self.assertEqual(result['status'], 'revise')
        self.assertEqual(result['revision_count'], 1)
        self.assertEqual(len(self.client.calls), 4)

    def test_two_call_budget_preserves_revise_result_without_extra_spending(self):
        self.client.decisions = ['revise']
        result = self.run_batch(max_calls=2)
        self.assertEqual(result['status'], 'revise')
        self.assertEqual(result['revision_count'], 0)
        self.assertEqual(len(self.client.calls), 2)
        self.assertTrue((self.root / result['report_path']).exists())


if __name__ == '__main__':
    unittest.main(verbosity=2)
