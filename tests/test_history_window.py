"""Small offline regressions for dated, source-bound historical comparison."""

import copy
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import researchdesk_cycle_discovery as discovery
import researchdesk_insight as insight
import researchdesk_insight_inputs as inputs
import researchdesk_offline as store
import researchdesk_recovery as recovery
import researchdesk_admission as admission
import researchdesk_cycle as cycle
import test_fulltext_review as fulltext_fixtures
import test_research_batch as batch_fixtures
from test_insight import FakeInsightClient


class HistoricalWindow(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='researchdesk-history-test-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        (self.root / 'config').mkdir()
        (self.root / 'config/research_topics.yaml').write_text(yaml.safe_dump({
            'schema_version': 1, 'topics': {'memory': {'name': 'Memory', 'enabled': True,
                'description': 'Offline history fixture.', 'scope': ['Memory'], 'keywords': ['memory']}}}))

    def note(self, relative, metadata, body):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('---\n' + yaml.safe_dump(metadata, sort_keys=False) + '---\n\n' + body)
        return relative

    def source(self, number, collected='2026-10-01', published='2026-02-01'):
        identifier = 'blog-00000000-0000-4000-8000-%012d' % number
        return self.note('sources/blogs/memory/' + identifier + '.md', {
            'id': identifier, 'kind': 'blog', 'topics': ['memory'], 'title': 'Fixture blog',
            'source_url': 'https://example.org/blog/%s' % number,
            'collected_at': collected, 'published_at': published}, '# Fixture blog\nManual background.')

    def admit(self, relative, cycle):
        path = self.root / ('reports/memory/admissions/%s/accepted.yaml' % cycle)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump({
            'topic': 'memory', 'cycle_id': cycle, 'production_accepted': True, 'status': 'accepted',
            'output_hashes': {relative: store.digest((self.root / relative).read_bytes())}}))
        Path(str(path) + '.sha256').write_text(store.digest(path.read_bytes()))

    def report(self, name, source, day):
        identifier = Path(source).stem
        relative = self.note('reports/memory/' + name + '.md', {
            'kind': 'synthesis', 'topics': ['memory']},
            '> AI 自动研究记录，已通过独立模型审阅\n\n# Comparison\n' + identifier)
        self.admit(relative, 'memory-' + day.replace('-', '') + '-0300')
        return relative

    def select(self, limit=40):
        return discovery.select_history(self.root, 'memory', limit,
                                        lookback_days=180, as_of='2026-10-30T01:00:00Z')

    def test_real_dates_override_lexicographic_filename_and_publication_age(self):
        older = self.source(1, '2026-06-01', '2023-01-01')
        newer = self.source(2, '2026-10-01', '2023-01-01')
        self.report('zzzz-old-prefix', older, '2026-06-01')
        latest = self.report('aaaa-new-prefix', newer, '2026-10-29')
        selected = self.select(2)
        self.assertEqual(selected[-1]['path'], latest)
        self.assertEqual(selected[-1]['research_date'], '2026-10-29')
        self.assertEqual(selected[-1]['date_basis'], 'admission_cycle_plan')
        self.assertEqual(selected[-1]['historical_origin'], 'admitted_ai')
        self.assertEqual(selected[-1]['published_dates'], ['2023-01-01'])

    def test_months_are_sampled_before_repeating_latest_month(self):
        wanted = set()
        for number, day in enumerate(('2026-06-10', '2026-08-10', '2026-10-10', '2026-10-20'), 1):
            source = self.source(number, day)
            report = self.report('report-%s' % number, source, day)
            if number != 3:
                wanted.add(report)
        selected = self.select(6)
        self.assertEqual({item['path'] for item in selected if item['path'].startswith('reports/')}, wanted)

    def test_repeated_reports_do_not_displace_new_original_source(self):
        source = self.source(1)
        self.report('newest', source, '2026-10-29')
        repeated = self.report('repeated', source, '2026-10-28')
        different = self.report('different', self.source(2), '2026-10-20')
        paths = {item['path'] for item in self.select(4)}
        self.assertIn(different, paths)
        self.assertNotIn(repeated, paths)

    def test_unknown_date_dependency_is_background_and_forged_dates_fail(self):
        source = self.source(1, None)
        self.report('known-cycle', source, '2026-10-20')
        selected = self.select(4)
        config = {'topic': 'memory', 'topic_name': 'Memory', 'prompts': {'version': 'insight-v4'},
                  'historical_inputs': selected}
        evidence, provenance = inputs._historical_evidence(self.root, config)
        dependency = next(item for item in evidence if item['path'] == source)
        self.assertFalse(dependency['temporal_eligible'])
        self.assertIsNone(dependency['research_date'])
        self.assertIn('不能支持跨时间趋势', dependency['historical_status'])
        self.assertEqual(provenance[0]['historical_origin'], dependency['historical_origin'])
        coverage = inputs.history_coverage(evidence)
        self.assertEqual(coverage['actual_span_days'], 0)
        self.assertEqual(coverage['undated_documents'], 1)
        config['historical_inputs'][0]['research_date'] = '2026-05-01'
        with self.assertRaisesRegex(store.OfflineError, '日期'):
            inputs._historical_evidence(self.root, config)

    def test_unknown_and_expired_dates_are_not_selected_as_time_evidence(self):
        unknown = self.source(1, None)
        expired = self.source(2, '2025-01-01')
        current = self.source(3, '2026-08-01')
        selected = self.select()
        self.assertEqual([item['path'] for item in selected], [current])
        self.assertNotIn(unknown, str(selected))
        self.assertNotIn(expired, str(selected))

    def test_old_mode_and_prompts_remain_compatible(self):
        self.source(1)
        selected = discovery.select_history(self.root, 'memory', 6)
        self.assertEqual(set(selected[0]), {'path', 'sha256', 'origin'})
        with self.assertRaises(store.OfflineError):
            discovery.select_history(self.root, 'memory', 40)
        self.assertEqual(insight.instructions_for({'prompts': {'version': 'insight-v1'}}),
                         (insight.GENERATION_INSTRUCTIONS, insight.REVIEW_INSTRUCTIONS))
        self.assertEqual(recovery._prompt_version({'prompts': {'version': 'insight-v4'}}), 'insight-v4')

    def test_v4_projection_render_and_human_edits_keep_historical_boundaries(self):
        source = self.source(1)
        report = self.report('dated-report', source, '2026-10-20')
        with (self.root / report).open('a') as handle:
            handle.write('\nHuman annotation.\n')
        selected = self.select()
        config = {'topic': 'memory', 'topic_name': 'Memory', 'prompts': {'version': 'insight-v4'},
                  'historical_inputs': selected}
        evidence, _ = inputs._historical_evidence(self.root, config)
        self.assertEqual(evidence[-1]['historical_origin'], 'human_modified')
        bundle = {'topic': 'memory', 'research_context': {}, 'evidence': evidence, 'input_fingerprint': 'fixture'}
        before = copy.deepcopy(bundle)
        payload = inputs.model_payload(bundle, 'insight-v4')
        self.assertEqual(bundle, before)
        self.assertEqual(payload['evidence'][-1]['date_basis'], 'admission_cycle_plan')
        self.assertEqual(payload['history_coverage']['actual_start'], '2026-10-01')
        self.assertNotIn('history_coverage', inputs.model_payload(bundle, 'insight-v3'))
        candidate = {'coverage_note': 'Fixture only.', 'report': {'title': 'Fixture', 'summary': 'Bounded.',
            'comparisons': [{'kind': 'inference', 'text': 'Hypothesis.', 'evidence_ids': ['H1', 'H2']}],
            'limitations': ['Not a trend.'], 'open_questions': ['Needs more history.']},
            'insights': [], 'topics': []}
        _, contents = insight.render_outputs(self.root, 'reports/test/memory/fixture', config, 'fixture', candidate, bundle)
        text = next(iter(contents.values()))
        self.assertIn('跨度 19 天', text)
        self.assertIn('人工修改的历史研究', text)
        self.assertIn('不代表完整覆盖', text)

    def test_v4_config_accepts_bounded_larger_history_and_rejects_legacy_expansion(self):
        for number in range(12):
            self.source(number)
        receipt = 'reports/test/memory/research-batches/fixture/receipt-attempt-1.yaml'
        target = self.root / receipt
        target.parent.mkdir(parents=True)
        target.write_text('{}')
        (self.root / 'config/research.yaml').write_text('{}')
        value = {'schema_version': 1, 'mode': 'insight_test', 'backend': 'chatgpt_plan',
            'topic': 'memory', 'topics_file': 'config/research_topics.yaml',
            'models': {'generation': 'fixture-generation', 'review': 'fixture-review'},
            'budget': {'max_calls': 4, 'month_max_calls': 100, 'max_input_chars': 500000,
                'max_output_chars': 8000, 'timeout_seconds': 120, 'max_revisions': 1},
            'prompts': {'version': 'insight-v4'},
            'research_inputs': [{'receipt': receipt, 'config': 'config/research.yaml'}],
            'historical_inputs': self.select()}
        path = self.root / 'config/insight.yaml'
        path.write_text(yaml.safe_dump(value))
        self.assertEqual(len(inputs.load_config(self.root, path)['historical_inputs']), 12)
        value['prompts']['version'] = 'insight-v3'
        value['historical_inputs'] = [{key: item[key] for key in ('path', 'sha256', 'origin')}
                                    for item in value['historical_inputs']]
        path.write_text(yaml.safe_dump(value))
        with self.assertRaisesRegex(store.OfflineError, '1–10'):
            inputs.load_config(self.root, path)


class AlignedCycle(unittest.TestCase):
    """One actual cycle/admission chain, using fixtures at external boundaries."""

    def setUp(self):
        batch_fixtures.ConfigDrivenResearchBatch.setUp(self)

    def test_rolling_fulltext_history_v4_and_formal_admission(self):
        class CombinedClient(FakeInsightClient):
            def infer(self, model, instructions, input_text, **limits):
                if 'evidence' not in json.loads(input_text):
                    return batch_fixtures.FakeMemberClient.infer(self, model, instructions, input_text, **limits)
                return super().infer(model, instructions, input_text, **limits)

        client = CombinedClient()
        def scope(result):
            if 'evidence' not in client.calls[-1]['payload']:
                result['limitations'] = ['已阅读虚构抽取全文，未独立复现实验。']
            else:
                result['coverage_note'] = 'R1读取虚构抽取正文，历史材料采集于6月与10月，未经本轮原文复核。'
                result['report']['comparisons'][1]['evidence_ids'] = ['R1']
                result['report']['limitations'] = ['给定历史窗口只覆盖已有资料，不代表行业趋势。']
        client.research_mutator = scope
        fetcher = fulltext_fixtures.FulltextFetcher()
        for number, day in enumerate(('2026-06-01', '2026-10-01'), 1):
            identifier = 'blog-11111111-1111-4111-8111-%012d' % number
            target = self.root / 'sources/blogs' / (identifier + '.md')
            target.write_text('---\n' + yaml.safe_dump({
                'schema_version': 1, 'id': identifier, 'kind': 'blog', 'title': 'Historical fixture',
                'source': 'Handwritten fixture', 'source_url': 'https://example.org/history/%s' % number,
                'topics': ['custom-topic'], 'collected_at': day, 'published_at': '2023-01-01',
                'authors': [], 'status': 'inbox', 'related_sources': [], 'related_notes': []}, sort_keys=False)
                + '---\n# Historical fixture\n## 人工笔记\nKeep this human annotation unchanged.\n')
        protected = {path: path.read_bytes() for path in self.root.glob('sources/blogs/*.md')}
        config = {'schema_version': 1, 'mode': 'research_cycle_test', 'backend': 'chatgpt_plan',
            'topic': 'custom-topic', 'topics_file': 'config/research_topics.yaml',
            'reading': {'mode': 'full_text_preferred', 'paper_max_chars': 12000},
            'window': {'mode': 'rolling', 'days': 60},
            'selection': {'mode': 'community_attention', 'min_score': 0.1, 'max_requests': 10},
            'discovery': {'max_candidates': 20, 'max_documents': 1, 'max_per_source': 1,
                'evidence_max_chars': 6000, 'sources': [{'id': 'arxiv', 'adapter': 'arxiv',
                    'entry_url': 'https://export.arxiv.org/api/query'}]},
            'models': {'research': 'fixture-research', 'insight': 'fixture-research', 'review': 'fixture-review'},
            'budget': {'max_calls_per_cycle': 8, 'research_max_calls': 4, 'insight_max_calls': 4,
                'max_input_chars': 500000, 'max_output_chars': 10000, 'timeout_seconds': 120, 'max_revisions': 1},
            'history': {'lookback_days': 180, 'max_documents': 30}}
        path = self.root / 'config/cycles/custom-topic.yaml'
        path.parent.mkdir()
        path.write_text(yaml.safe_dump(config, sort_keys=False))
        identifier = 'custom-topic-20261030-0300'
        def listing(root, resolved, cycle_id, fetcher=None):
            return {'schema_version': 1, 'mode': 'cycle_discovery_test', 'topic': 'custom-topic',
                'cycle_id': cycle_id, 'window_start': resolved['window_start'], 'window_end': resolved['window_end'],
                'status': 'complete', 'source_status': [{'id': 'arxiv', 'status': 'complete', 'complete_window': True}],
                'candidates': [{'published_at': '2026-10-02', 'identity_keys': ['arxiv:2610.01234'],
                    'attention': {'community_attention_score': 2}, 'source': {
                    'id': 'paper-one', 'adapter': 'arxiv', 'kind': 'paper',
                    'url': 'https://export.arxiv.org/api/query?id_list=2610.01234v2', 'evidence_max_chars': 6000}}],
                'deferred': [], 'production_accepted': False}
        fixed = datetime(2026, 10, 30, 1, tzinfo=timezone.utc)
        with mock.patch.object(cycle, 'datetime', wraps=datetime) as clock, \
                mock.patch.object(discovery, 'discover', side_effect=listing), \
                mock.patch.object(discovery, 'select_history', wraps=discovery.select_history) as history:
            clock.now.return_value = fixed
            receipt = cycle.run(self.root, path, identifier, client=client, fetcher=fetcher)
        self.assertEqual(receipt['status'], 'completed', store.checked_yaml(self.root,
            'reports/test/custom-topic/cycles/' + identifier + '/research-result.yaml'))
        self.assertEqual(receipt['reserved_calls'], 4)
        history.assert_called_once_with(self.root, 'custom-topic', 30, lookback_days=180, as_of=fixed.isoformat())
        self.assertEqual((datetime.fromisoformat(receipt['window_end']) -
                          datetime.fromisoformat(receipt['window_start'])).days, 60)
        base = 'reports/test/custom-topic/cycles/' + identifier
        child = store.checked_yaml(self.root, base + '/configs/insight.yaml')
        self.assertEqual(child['prompts']['version'], 'insight-v4')
        self.assertEqual(store.checked_yaml(self.root, base + '/configs/research.yaml')['prompts']['version'],
                         'research-batch-v2')
        research_calls = [call['payload'] for call in client.calls if 'evidence' not in call['payload']]
        self.assertEqual(research_calls[0]['coverage'], 'full_text')
        self.assertEqual(research_calls[0], {key: value for key, value in research_calls[1].items() if key != 'candidate'})
        insight_calls = [call['payload'] for call in client.calls if 'evidence' in call['payload']]
        self.assertEqual(insight_calls[0], {key: value for key, value in insight_calls[1].items() if key != 'candidate'})
        self.assertEqual(insight_calls[0]['history_coverage']['actual_span_days'], 122)
        self.assertEqual({item['research_date'] for item in insight_calls[0]['evidence'] if item['origin'] == 'human_baseline'},
                         {'2026-06-01', '2026-10-01'})
        self.assertTrue(all(item['historical_origin'] == 'human_note' for item in insight_calls[0]['evidence']
                            if item['origin'] == 'human_baseline'))
        plan = admission.plan(self.root, 'custom-topic', identifier, fetcher=fetcher)
        accepted = admission.run(self.root, 'custom-topic', identifier, fetcher=fetcher)
        self.assertTrue(accepted['production_accepted'])
        self.assertEqual(accepted['new_model_calls'], 0)
        self.assertEqual(len(client.calls), 4)
        synthesis = (self.root / ('reports/custom-topic/' + identifier + '-synthesis.md')).read_text()
        self.assertIn('跨度 122 天', synthesis)
        self.assertIn('## 历史覆盖', synthesis)
        source_cards = [content for relative, content in plan['files'].items() if relative.startswith('sources/papers/')]
        self.assertEqual(len(source_cards), 1)
        self.assertIn('单篇详细研究', source_cards[0])
        self.assertNotIn('## 主张与证据', source_cards[0])
        self.assertNotIn(fetcher.body.strip(), source_cards[0])
        self.assertEqual(protected, {target: target.read_bytes() for target in protected})
        frozen = store.checked_yaml(self.root, base + '/receipt.yaml')
        self.assertEqual(receipt, frozen)


if __name__ == '__main__':
    unittest.main()
