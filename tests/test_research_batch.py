"""Config-driven batch acceptance uses fake models and handwritten source fixtures.

Every test uses a disposable vault. These checks never read an OAuth profile,
connect to the network, or spend a user's ChatGPT membership allowance.
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
FIXTURES = REPOSITORY / 'workflows/test/example-topic/fixtures/collection'
sys.path.insert(0, str(REPOSITORY / 'scripts'))
import batch
import offline as store
from sources import SourceError, parse_arxiv_abstract


class FixtureFetcher:
    def __init__(self):
        self.paper = (FIXTURES / 'arxiv.xml').read_text()
        self.blog = (FIXTURES / 'blog-article.html').read_text()
        self.calls = []
        self.failed = set()

    def fetch(self, url):
        self.calls.append(url)
        key = 'paper' if 'arxiv.org' in url else 'blog'
        if key in self.failed:
            raise SourceError('Synthetic source temporarily unavailable')
        text = self.paper if key == 'paper' else self.blog
        return {'url': url, 'requested_url': url, 'status': 200,
                'redirects': [], 'text': text,
                'content_type': 'application/atom+xml' if key == 'paper' else 'text/html',
                'fetched_at': '2026-10-19T00:00:00+00:00',
                'sha256': hashlib.sha256(text.encode()).hexdigest()}


class FakeMemberClient:
    def __init__(self):
        self.calls = []
        self.catalog = [{'slug': 'fixture-research', 'display_name': 'Research'},
                        {'slug': 'fixture-review', 'display_name': 'Review'}]
        self.account = {'authenticated': True, 'plan_permission': True,
                        'authorization': 'official_chatgpt_oauth',
                        'account_fingerprint': 'fixture-account'}
        self.fail_on_call = None
        self.actual_model = None
        self.review_decisions = []
        self.review_count = 0
        self.research_mutator = None
        self.review_mutator = None

    def models(self):
        return copy.deepcopy(self.catalog)

    def status(self):
        return copy.deepcopy(self.account)

    def authorization_summary(self):
        return {'identity_verified': True, 'plan_usage_enabled': True,
                'scope': ['chatgpt.tokens.use.direct']}

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
            result = {'decision': decision, 'coverage_acknowledged': True,
                      'issues': [], 'checks': [
                          {'claim_index': index, 'verdict': 'supported',
                           'evidence_ids': claim['evidence_ids']}
                          for index, claim in enumerate(candidate['claims'])]}
            if decision == 'revise':
                result['issues'] = [{'severity': 'warning', 'location': 'summary',
                                     'reason': '需要更明确的材料范围说明',
                                     'suggestion': '注明仅摘要或节选，未核验全文。'}]
            if self.review_mutator:
                self.review_mutator(result)
        else:
            result = {'summary': '仅依据虚构解析材料整理的测试研究。',
                      'claims': [
                          {'kind': 'author_claim', 'text': '材料介绍记忆块。', 'evidence_ids': ['A1']},
                          {'kind': 'fact', 'text': '这是用于解析验收的材料。', 'evidence_ids': ['A1']},
                          {'kind': 'inference', 'text': '仅此材料不足以比较系统性能。', 'evidence_ids': ['A1']}],
                      'limitations': ['仅阅读摘要或节选，未核验全文和实验。',
                                      '本测试使用虚构来源样例。']}
            if self.research_mutator:
                self.research_mutator(result)
        return {'text': json.dumps(result, ensure_ascii=False),
                'model': self.actual_model or model,
                'response_id': 'fixture-response-%s' % len(self.calls),
                'usage': {'input_tokens': 50, 'output_tokens': 30, 'total_tokens': 80}}


class ConfigDrivenResearchBatch(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='researchdesk-batch-tests-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        for folder in ('config/test/custom-topic', 'sources/papers', 'sources/blogs',
                       'reports/test/custom-topic', 'insights', 'articles', 'workflows'):
            (self.root / folder).mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPOSITORY / 'config/legacy_sources.yaml', self.root / 'config/legacy_sources.yaml')
        self.topics_path = self.root / 'config/research_topics.yaml'
        self.topics_path.write_text(yaml.safe_dump({'schema_version': 1, 'topics': {
            'custom-topic': {'name': 'Custom Topic', 'enabled': True,
                             'description': '可配置的测试方向。',
                             'scope': ['可重现的证据研究'], 'keywords': ['memory']}}}, allow_unicode=True))
        self.config = {'schema_version': 1, 'mode': 'research_batch_test',
                       'backend': 'chatgpt_plan', 'topic': 'custom-topic',
                       'topics_file': 'config/research_topics.yaml',
                       'models': {'research': 'fixture-research', 'review': 'fixture-review'},
                       'budget': {'max_documents': 2, 'max_calls_per_item': 4,
                                  'max_calls_per_batch': 6, 'month_max_calls': 10,
                                  'max_input_chars': 20000, 'max_output_chars': 10000,
                                  'timeout_seconds': 120, 'max_revisions': 1},
                       'sources': [
                           {'id': 'paper-one', 'adapter': 'arxiv', 'kind': 'paper',
                            'url': 'https://export.arxiv.org/api/query?id_list=2610.01234v2',
                            'evidence_max_chars': 6000},
                           {'id': 'blog-one', 'adapter': 'letta', 'kind': 'blog',
                            'url': 'https://www.letta.com/blog/fixture-memory',
                            'evidence_max_chars': 6000}],
                       'prompts': {'version': 'research-batch-v1'}}
        self.config_path = self.root / 'config/test/custom-topic/research-batch.yaml'
        self.config_path.write_text(yaml.safe_dump(self.config, allow_unicode=True, sort_keys=False))
        self.fetcher = FixtureFetcher()
        self.client = FakeMemberClient()
        self.addCleanup(mock.patch.stopall)
        mock.patch.object(socket, 'create_connection', side_effect=AssertionError('Network prohibited')).start()
        mock.patch.object(socket.socket, 'connect', side_effect=AssertionError('Network prohibited')).start()

    def run_batch(self, batch_id='first', **kwargs):
        self.config_path.write_text(yaml.safe_dump(self.config, allow_unicode=True, sort_keys=False))
        return batch.run(self.root, self.config_path, batch_id, self.client,
                         fetcher=self.fetcher, **kwargs)

    def directory(self, batch_id='first'):
        return self.root / 'reports/test/custom-topic/research-batches' / batch_id

    def assert_no_calls(self):
        self.assertEqual(self.client.calls, [])
        self.assertEqual(self.fetcher.calls, [])

    def test_custom_topic_two_sources_use_four_independent_model_calls(self):
        result = self.run_batch()
        self.assertEqual(result['status'], 'test_accepted')
        self.assertIs(result['production_accepted'], False)
        self.assertEqual(result['reserved_calls'], 4)
        self.assertEqual(result['completed_calls'], 4)
        self.assertEqual(len(self.client.calls), 4)
        self.assertEqual([c['model'] for c in self.client.calls],
                         ['fixture-research', 'fixture-review'] * 2)
        self.assertEqual(len(result['items']), 2)
        self.assertEqual(len(list(self.directory().glob('items/*/report.md'))), 2)
        for call in self.client.calls:
            self.assertEqual(call['limits']['max_output_chars'], 10000)
            self.assertEqual(call['limits']['timeout_seconds'], 120)
        for path in self.root.rglob('*'):
            if path.is_file() and path.relative_to(self.root).parts[0] not in {'config'}:
                if path.relative_to(self.root).as_posix() == 'reports/test/custom-topic/.offline.lock':
                    continue  # Existing shared test-only process lock is not research output.
                self.assertTrue(str(path.relative_to(self.root)).startswith(
                    'reports/test/custom-topic/research-batches/'), path)

    def test_review_receives_same_original_material_as_research(self):
        self.run_batch()
        for index in (0, 2):
            research = self.client.calls[index]['payload']
            review = self.client.calls[index + 1]['payload']
            self.assertEqual(research['original_material'], review['original_material'])
            self.assertEqual(research['metadata'], review['metadata'])
            self.assertEqual(research['coverage'], review['coverage'])
            self.assertEqual(len(review['candidate']['claims']), 3)

    def test_research_direction_scope_and_keywords_reach_both_models(self):
        self.run_batch()
        expected = {'name': 'Custom Topic', 'scope': ['可重现的证据研究'], 'keywords': ['memory']}
        for call in self.client.calls:
            self.assertEqual(call['payload']['research_context'], expected)

    def test_paper_and_blog_evidence_coverages_are_explicit(self):
        self.run_batch()
        research = [c['payload'] for c in self.client.calls if 'candidate' not in c['payload']]
        self.assertEqual({c['coverage'] for c in research}, {'abstract_only', 'excerpt'})
        for call in research:
            self.assertIn('A1', call['original_material'])
        reports = '\n'.join(p.read_text() for p in self.directory().glob('items/*/report.md'))
        self.assertIn('TEST', reports)
        self.assertIn('摘要', reports)
        self.assertIn('节选', reports)

    def test_invalid_mode_and_unknown_config_fields_fail_before_fetch_or_infer(self):
        original = copy.deepcopy(self.config)
        for change in ({'mode': 'production'}, {'backend': 'api_key'}, {'surprise': True}):
            self.config = dict(copy.deepcopy(original), **change)
            with self.subTest(change=change), self.assertRaises((store.OfflineError, ValueError)):
                self.run_batch()
            self.assert_no_calls()

    def test_duplicate_yaml_keys_fail_closed(self):
        text = yaml.safe_dump(self.config, allow_unicode=True)
        self.config_path.write_text(text + '\nbackend: api_key\n')
        with self.assertRaises((store.OfflineError, ValueError, yaml.YAMLError)):
            batch.run(self.root, self.config_path, 'first', self.client, fetcher=self.fetcher)
        self.assert_no_calls()

    def test_topics_path_cannot_escape_vault(self):
        for path in ('../outside.yaml', '/private/tmp/outside.yaml', 'config/../research_topics.yaml'):
            self.config['topics_file'] = path
            with self.subTest(path=path), self.assertRaises((store.OfflineError, ValueError)):
                self.run_batch()
            self.assert_no_calls()

    def test_topics_symlink_is_rejected(self):
        link = self.root / 'config/linked-topics.yaml'
        link.symlink_to(self.topics_path)
        self.config['topics_file'] = 'config/linked-topics.yaml'
        with self.assertRaises((store.OfflineError, ValueError)):
            self.run_batch()
        self.assert_no_calls()

    def test_disabled_topic_cannot_start(self):
        topics = yaml.safe_load(self.topics_path.read_text())
        topics['topics']['custom-topic']['enabled'] = False
        self.topics_path.write_text(yaml.safe_dump(topics))
        with self.assertRaises((store.OfflineError, ValueError)):
            self.run_batch()
        self.assert_no_calls()

    def test_adapter_kind_and_host_must_agree(self):
        original = copy.deepcopy(self.config['sources'])
        for change in ({'url': 'https://example.invalid/secret'},
                       {'adapter': 'arxiv'}, {'kind': 'paper'},
                       {'url': 'https://www.langchain.com/blog/fixture-memory'}):
            self.config['sources'] = copy.deepcopy(original)
            self.config['sources'][1].update(change)
            with self.subTest(change=change), self.assertRaises((store.OfflineError, SourceError, ValueError)):
                self.run_batch()
            self.assert_no_calls()

    def test_same_generation_and_review_model_cannot_spend(self):
        self.config['models']['review'] = self.config['models']['research']
        with self.assertRaises((store.OfflineError, ValueError)):
            self.run_batch()
        self.assertEqual(self.client.calls, [])

    def test_boolean_negative_or_unbounded_budgets_are_rejected_before_spending(self):
        original = copy.deepcopy(self.config['budget'])
        for field, value in (('max_calls_per_batch', True), ('max_calls_per_item', -1),
                             ('max_documents', 100), ('max_revisions', 99)):
            self.config['budget'] = dict(original, **{field: value})
            with self.subTest(field=field), self.assertRaises((store.OfflineError, ValueError)):
                self.run_batch()
            self.assert_no_calls()

    def test_unavailable_model_cannot_spend(self):
        self.client.catalog = self.client.catalog[:1]
        with self.assertRaises((store.OfflineError, ValueError)):
            self.run_batch()
        self.assertEqual(self.client.calls, [])

    def test_identity_without_membership_permission_cannot_spend(self):
        self.client.account['plan_permission'] = False
        with self.assertRaises((store.OfflineError, ValueError)):
            self.run_batch()
        self.assertEqual(self.client.calls, [])

    def test_completed_batch_resume_does_not_add_model_calls(self):
        first = self.run_batch()
        second = self.run_batch()
        self.assertTrue(second.get('cached'))
        self.assertEqual(first['items'], second['items'])
        self.assertEqual(len(self.client.calls), 4)

    def test_controlled_interruption_resumes_after_first_item(self):
        with self.assertRaises(store.SimulatedInterruption):
            self.run_batch(fail_after='after_first_item')
        self.assertEqual(len(self.client.calls), 2)
        result = self.run_batch()
        self.assertEqual(result['status'], 'test_accepted')
        self.assertEqual(len(self.client.calls), 4)
        self.assertEqual(result['completed_calls'], 4)
        self.assertEqual(len(list(self.directory().glob('items/*/report.md'))), 2)

    def test_source_failure_is_partial_and_retry_only_spends_missing_item(self):
        self.fetcher.failed.add('paper')
        first = self.run_batch()
        self.assertEqual(first['status'], 'partial')
        self.assertEqual(len(self.client.calls), 2)
        self.fetcher.failed.clear()
        second = self.run_batch()
        self.assertEqual(second['status'], 'test_accepted')
        self.assertEqual(len(self.client.calls), 4)
        self.assertGreaterEqual(len(list(self.directory().glob('receipt-attempt-*.yaml'))), 2)

    def test_arxiv_response_must_match_configured_paper_and_version(self):
        self.fetcher.paper = self.fetcher.paper.replace('01234v2', '09999v3')
        result = self.run_batch()
        self.assertEqual(result['status'], 'partial')
        self.assertEqual(len(self.client.calls), 2)
        self.assertTrue(all(c['payload']['metadata']['source'] == 'Letta' for c in self.client.calls))

    def test_arxiv_html_cannot_override_contradictory_declared_version(self):
        html = (FIXTURES / 'arxiv-abstract.html').read_text().replace(
            'name="citation_arxiv_id" content="2610.01234"',
            'name="citation_arxiv_id" content="2610.01234v3"')
        with self.assertRaisesRegex(SourceError, 'version mismatch'):
            parse_arxiv_abstract(html, 'https://arxiv.org/abs/2610.01234v2')

    def test_unknown_request_never_retries_and_does_not_block_healthy_item(self):
        self.client.fail_on_call = 1
        first = self.run_batch()
        self.assertEqual(first['status'], 'partial')
        self.assertEqual(len(self.client.calls), 3)
        self.assertEqual(first['reserved_calls'], 3)
        self.assertEqual(first['completed_calls'], 2)
        self.assertEqual(sum(x['status'] == 'test_accepted' for x in first['items']), 1)
        self.client.fail_on_call = None
        self.run_batch()
        self.assertEqual(len(self.client.calls), 3)

    def test_new_batch_reuses_identical_evidence_without_spending(self):
        self.run_batch()
        result = self.run_batch(batch_id='second')
        self.assertEqual(len(self.client.calls), 4)
        self.assertEqual(result['reserved_calls'], 0)
        self.assertEqual(result['completed_calls'], 0)

    def test_duplicate_source_identity_within_one_batch_is_not_researched_twice(self):
        self.config['sources'][1] = dict(self.config['sources'][0], id='paper-two',
                                       url=self.config['sources'][0]['url'] + '&max_results=1')
        result = self.run_batch()
        self.assertEqual(len(self.client.calls), 2)
        self.assertEqual(result['completed_calls'], 2)

    def test_updated_source_gets_separate_report_without_overwriting_prior(self):
        self.run_batch()
        before = {p: p.read_bytes() for p in self.directory().rglob('*') if p.is_file()}
        self.fetcher.paper = self.fetcher.paper.replace('01234v2', '01234v3').replace(
            'memory blocks', 'revised memory boundaries')
        self.config['sources'][0]['url'] = self.config['sources'][0]['url'].replace('01234v2', '01234v3')
        result = self.run_batch(batch_id='updated')
        self.assertEqual(len(self.client.calls), 6)
        self.assertEqual(result['completed_calls'], 2)
        self.assertEqual(before, {p: p.read_bytes() for p in before})
        self.assertEqual(len(list(self.directory('updated').glob('items/*/report.md'))), 1)

    def test_wider_blog_excerpt_is_new_evidence_instead_of_false_duplicate(self):
        paragraph = '<p>This fictional parser fixture describes persistent memory blocks.</p>'
        self.fetcher.blog = self.fetcher.blog.replace(paragraph, paragraph * 20)
        self.config['sources'][1]['evidence_max_chars'] = 200
        self.run_batch()
        self.config['sources'][1]['evidence_max_chars'] = 6000
        result = self.run_batch(batch_id='wider-excerpt')
        self.assertEqual(result['completed_calls'], 2)
        self.assertEqual(len(self.client.calls), 6)
        self.assertEqual(len(list(self.directory('wider-excerpt').glob('items/*/report.md'))), 1)

    def test_monthly_cap_cannot_be_raised_by_starting_another_batch(self):
        self.config['budget']['month_max_calls'] = 4
        self.config['budget']['max_calls_per_batch'] = 4
        self.run_batch()
        self.config['budget']['month_max_calls'] = 10
        self.fetcher.paper = self.fetcher.paper.replace('memory blocks', 'new memory boundaries')
        try:
            self.run_batch(batch_id='attempt-budget-reset')
        except (store.OfflineError, ValueError):
            pass
        self.assertEqual(len(self.client.calls), 4)

    def test_monthly_reservations_are_shared_across_research_topics(self):
        self.config['budget']['month_max_calls'] = 4
        self.config['budget']['max_calls_per_batch'] = 4
        self.run_batch()
        topics = yaml.safe_load(self.topics_path.read_text())
        topics['topics']['another-topic'] = copy.deepcopy(topics['topics']['custom-topic'])
        self.topics_path.write_text(yaml.safe_dump(topics, allow_unicode=True))
        self.config['topic'] = 'another-topic'
        self.config['budget']['month_max_calls'] = 10
        self.fetcher.paper = self.fetcher.paper.replace('memory blocks', 'revised memory boundaries')
        self.fetcher.blog = self.fetcher.blog.replace('persistent memory blocks', 'revised memory boundaries')
        result = self.run_batch(batch_id='different-topic')
        self.assertEqual(result['effective_month_max_calls'], 4)
        self.assertEqual(len(self.client.calls), 4)
        self.assertEqual(result['status'], 'failed')

    def test_existing_single_paper_membership_unknown_calls_consume_shared_budget(self):
        config = batch.inputs.load_config(self.root, self.config_path)
        candidate, _ = batch.inputs.fetch_candidate(self.root, config, self.config['sources'][0], self.fetcher)
        candidate = copy.deepcopy(candidate)
        candidate['metadata'].update(arxiv_id='2610.09999', source_url='https://arxiv.org/abs/2610.09999')
        candidate['identity_keys'] = store.identities(candidate['metadata'])
        base = 'reports/test/custom-topic/membership/historical-unknown'
        store.save_yaml(self.root, base + '/manifest.yaml', {
            'backend': 'chatgpt_plan', 'created_at': batch.now(),
            'candidate': candidate, 'source_id': candidate['source_id'],
            'limits': {'month_max_calls': 4}})
        events = []
        for index in range(2):
            store.append_event(self.root, base, events, {'type': 'call_reserved',
                'reservation_id': 'unknown-%s' % index, 'month': batch.now()[:7],
                'usage_status': 'unknown'})
        result = self.run_batch()
        self.assertEqual(result['effective_month_max_calls'], 4)
        self.assertEqual(result['monthly_reserved_calls'], 4)
        self.assertEqual(result['completed_calls'], 2)
        self.assertEqual(len(self.client.calls), 2)

    def test_same_batch_cannot_change_bound_model_or_budget(self):
        self.run_batch()
        self.config['budget']['max_calls_per_batch'] = 4
        with self.assertRaises((store.OfflineError, ValueError)):
            self.run_batch()
        self.assertEqual(len(self.client.calls), 4)

    def test_preexisting_formal_and_test_notes_are_unchanged(self):
        notes = [self.root / 'reports/human.md', self.root / 'reports/test/custom-topic/human.md']
        for path in notes:
            path.write_text('人工研究笔记，请保留。\n')
        before = {path: path.read_bytes() for path in notes}
        self.run_batch()
        self.assertEqual(before, {path: path.read_bytes() for path in notes})

    def test_human_edit_to_existing_test_note_prevents_resume(self):
        note = self.root / 'reports/test/custom-topic/human.md'
        note.write_text('原人工笔记\n')
        self.run_batch()
        note.write_text('人工补充\n')
        with self.assertRaises((store.OfflineError, ValueError)):
            self.run_batch()
        self.assertEqual(note.read_text(), '人工补充\n')
        self.assertEqual(len(self.client.calls), 4)

    def test_human_edit_to_report_is_never_overwritten(self):
        self.run_batch()
        report = next(self.directory().glob('items/*/report.md'))
        report.write_text(report.read_text() + '\n人工修改\n')
        before = report.read_bytes()
        with self.assertRaises((store.OfflineError, ValueError)):
            self.run_batch()
        self.assertEqual(report.read_bytes(), before)
        self.assertEqual(len(self.client.calls), 4)

    def test_checkpoint_edit_cannot_trigger_new_model_requests(self):
        self.run_batch()
        checkpoint = next(self.directory().glob('items/*/checkpoints/research-0.yaml'))
        checkpoint.write_text(checkpoint.read_text() + '\nmanual_change: true\n')
        with self.assertRaises((store.OfflineError, ValueError)):
            self.run_batch()
        self.assertEqual(len(self.client.calls), 4)

    def test_actual_model_mismatch_is_blocked_and_not_reissued(self):
        self.client.actual_model = 'unexpected-model'
        first = self.run_batch()
        self.assertNotEqual(first['status'], 'test_accepted')
        before = len(self.client.calls)
        self.client.actual_model = None
        self.run_batch()
        self.assertEqual(len(self.client.calls), before)

    def test_pass_requires_review_of_every_claim(self):
        self.client.review_mutator = lambda result: result['checks'].pop()
        result = self.run_batch()
        self.assertNotEqual(result['status'], 'test_accepted')
        self.assertFalse(any(x['status'] == 'test_accepted' for x in result['items']))

    def test_nonexistent_evidence_id_is_not_released_for_review_or_acceptance(self):
        self.client.research_mutator = lambda result: result['claims'][0].update(evidence_ids=['A999'])
        result = self.run_batch()
        self.assertNotEqual(result['status'], 'test_accepted')
        self.assertTrue(all(c['model'] == 'fixture-research' for c in self.client.calls))

    def test_research_without_explicit_coverage_limitation_cannot_pass(self):
        self.client.research_mutator = lambda result: result.update(limitations=['更多研究仍有必要。'])
        result = self.run_batch()
        self.assertNotEqual(result['status'], 'test_accepted')
        self.assertFalse(any(x['status'] == 'test_accepted' for x in result['items']))

    def test_pass_with_blocking_issue_cannot_be_accepted(self):
        def blocking_issue(result):
            result['issues'].append({'severity': 'blocking', 'location': 'claim 0',
                                     'reason': '超出材料范围', 'suggestion': '删除无依据主张'})
        self.client.review_mutator = blocking_issue
        result = self.run_batch()
        self.assertNotEqual(result['status'], 'test_accepted')
        self.assertFalse(any(x['status'] == 'test_accepted' for x in result['items']))

    def test_pass_requires_explicit_evidence_coverage_acknowledgement(self):
        self.client.review_mutator = lambda result: result.update(coverage_acknowledged=False)
        result = self.run_batch()
        self.assertNotEqual(result['status'], 'test_accepted')
        self.assertFalse(any(x['status'] == 'test_accepted' for x in result['items']))

    def test_one_revision_is_researched_and_independently_reviewed_with_six_call_cap(self):
        self.client.review_decisions = ['revise', 'pass', 'pass']
        result = self.run_batch()
        self.assertEqual(result['status'], 'test_accepted')
        self.assertEqual(result['completed_calls'], 6)
        self.assertEqual(len(self.client.calls), 6)
        self.assertEqual([x['model'] for x in self.client.calls],
                         ['fixture-research', 'fixture-review'] * 3)
        self.run_batch()
        self.assertEqual(len(self.client.calls), 6)

    def test_repeated_revision_requests_stop_after_one_revision(self):
        self.client.review_decisions = ['revise'] * 6
        result = self.run_batch()
        self.assertNotEqual(result['status'], 'test_accepted')
        self.assertLessEqual(len(self.client.calls), 6)
        self.assertLessEqual(sum(c['model'] == 'fixture-research' and
                                 c['payload']['metadata']['source'] == 'arXiv'
                                 for c in self.client.calls), 2)

    def test_no_schedule_or_non_test_output_is_created(self):
        before = {p.relative_to(self.root): p.read_bytes()
                  for p in self.root.rglob('*') if p.is_file()}
        self.run_batch()
        for path in self.root.rglob('*'):
            if path.is_file() and path.relative_to(self.root) not in before:
                if path.relative_to(self.root).as_posix() == 'reports/test/custom-topic/.offline.lock':
                    continue
                self.assertTrue(path.relative_to(self.root).as_posix().startswith(
                    'reports/test/custom-topic/research-batches/'), path)
        self.assertFalse((self.root / '.github').exists())


if __name__ == '__main__':
    unittest.main()
