"""Actual archived Research -> Insight v4 -> formal admission with fake boundaries."""

from datetime import datetime, timezone
import json
from pathlib import Path
import re
import unittest
from unittest import mock

import yaml

import test_research_batch as batch_fixtures
import test_fulltext_review as fulltext_fixtures
from test_insight import FakeInsightClient
import researchdesk_admission as admission
import researchdesk_cycle as cycle
import researchdesk_cycle_discovery as discovery
import researchdesk_offline as store


class ArchivedFormalCycle(unittest.TestCase):
    def setUp(self):
        batch_fixtures.ConfigDrivenResearchBatch.setUp(self)

    def run_archived_cycle(self):
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
            'topic': 'custom-topic', 'topics_file': 'config/research_topics.yaml', 'archive': True,
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
        # A source already present in the isolated test namespace must receive
        # a distinct formal ID; this exercises the archive metadata remapping.
        original_candidate = store.checked_yaml(self.root,
            'reports/test/custom-topic/research-batches/' + identifier + '/items/paper-one/candidate.yaml')['candidate']
        test_source = self.root / 'sources/papers/test/custom-topic' / (original_candidate['source_id'] + '.md')
        test_source.parent.mkdir(parents=True)
        test_source.write_text('---\n' + yaml.safe_dump(dict(original_candidate['metadata'],
            schema_version=1, id=original_candidate['source_id'], kind='paper', topics=['custom-topic'],
            collected_at='2026-10-30', updated_at='2026-10-30', status='inbox',
            related_sources=[], related_notes=[]), allow_unicode=True, sort_keys=False)
            + '---\n> TEST：离线虚构样例，不可作为正式研究证据。\n\n## 人工笔记\nKeep this source annotation.\n')
        protected[test_source] = test_source.read_bytes()
        fetcher.fetch = mock.Mock(side_effect=AssertionError('Network forbidden during admission'))
        fetcher.fetch_pdf = mock.Mock(side_effect=AssertionError('Network forbidden during admission'))
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

        return plan, accepted, identifier, client, fetcher

    def test_offline_admission_links_replay_and_tamper_protection(self):
        plan, accepted, identifier, client, fetcher = self.run_archived_cycle()
        originals = [(path, content) for path, content in plan['files'].items()
                     if path.startswith('sources/originals/')]
        self.assertEqual(len(originals), 1)
        original_path, original_content = originals[0]
        metadata = yaml.safe_load(original_content.split('---', 2)[1])
        self.assertEqual(metadata['kind'], 'original_snapshot')
        self.assertIn(metadata['source_id'], accepted['source_id_map'].values())
        self.assertNotIn(metadata['source_id'], accepted['source_id_map'])
        self.assertEqual(metadata['coverage'], 'full_text')
        self.assertEqual(metadata['research_coverage'], 'full_text')
        self.assertTrue(metadata['authors'])
        self.assertTrue(metadata['published_at'])
        self.assertEqual(metadata['source_version'], 'v2')
        self.assertNotIn('> TEST', original_content)
        self.assertIn(fetcher.body.strip(), original_content)
        links = []
        for path, content in plan['files'].items():
            if path.startswith(('reports/', 'sources/papers/', 'sources/blogs/')):
                for target in re.findall(r'\[[^\]]+\]\(([^)]+)\)', content):
                    if 'originals/' in target:
                        resolved = (self.root / Path(path).parent / target).resolve()
                        self.assertEqual(resolved, self.root / original_path)
                        self.assertTrue(resolved.is_file())
                        links.append(path)
        self.assertEqual(len(links), 2)  # One source card and its detailed report.
        again = admission.run(self.root, 'custom-topic', identifier, fetcher=fetcher)
        self.assertTrue(again['cached'])
        self.assertEqual(len(client.calls), 4)
        fetcher.fetch.assert_not_called()
        fetcher.fetch_pdf.assert_not_called()
        candidate_path = ('reports/test/custom-topic/research-batches/' + identifier
                          + '/items/paper-one/candidate.yaml')
        candidate = store.checked_yaml(self.root, candidate_path)['candidate']
        for relative in (original_path, candidate['archive']['path'], candidate['archive']['markdown_path']):
            with self.subTest(tamper=relative):
                target = self.root / relative
                before = target.read_bytes()
                try:
                    target.write_bytes(before + b'\nHuman addition preserved by failed admission.\n')
                    with self.assertRaises(store.OfflineError):
                        admission.run(self.root, 'custom-topic', identifier, fetcher=fetcher)
                    self.assertTrue(target.read_bytes().endswith(b'Human addition preserved by failed admission.\n'))
                    self.assertEqual(len(client.calls), 4)
                finally:
                    target.write_bytes(before)
        self.assertTrue(admission.run(self.root, 'custom-topic', identifier, fetcher=fetcher)['cached'])


if __name__ == '__main__':
    unittest.main()
