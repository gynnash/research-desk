"""Full-text scope, immutable history and role inputs; no network or model calls."""

import copy
from pathlib import Path
import sys
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import batch
import insight
import insight_inputs
import offline as store
import test_research_batch as fixtures
from test_insight import FakeInsightClient


class FulltextFetcher(fixtures.FixtureFetcher):
    def __init__(self):
        super().__init__()
        self.fulltext_unavailable = False
        self.body = ('This fictional method stores source references and checks evidence boundaries. ' * 10)

    def fetch_pdf(self, url):
        self.calls.append(url)
        raise fixtures.SourceError('Synthetic full-text unavailable')

    def fetch(self, url):
        if '/html/' in url or '/pdf/' in url:
            self.calls.append(url)
            if self.fulltext_unavailable or '/pdf/' in url:
                raise fixtures.SourceError('Synthetic full-text unavailable')
            text = ('<html><head><meta name="citation_arxiv_id" content="2610.01234v2"></head>'
                    '<body><article class="ltx_document"><h1>Fixture paper</h1>'
                    '<section class="ltx_section" id="method"><h2>Method</h2><p>' + self.body + '</p></section>'
                    '<section class="ltx_section" id="limits"><h2>Limitations</h2><p>' + self.body + '</p></section>'
                    '</article></body></html>')
            return {'url': url, 'requested_url': url, 'redirects': [], 'text': text,
                    'content_type': 'text/html', 'status': 200}
        return super().fetch(url)


class FulltextReview(unittest.TestCase):
    def setUp(self):
        # Borrow fixture setup without inheriting its unrelated test suite.
        fixtures.ConfigDrivenResearchBatch.setUp(self)
        self.config['sources'] = self.config['sources'][:1]
        self.config['budget'].update(max_documents=1, max_calls_per_batch=4)
        self.fetcher = FulltextFetcher()
        self.client.research_mutator = self.scope_limitations

    def scope_limitations(self, result):
        coverage = self.client.calls[-1]['payload']['coverage']
        result['limitations'] = [{'full_text': '已阅读抽取全文；未独立复现实验。',
                                  'excerpt': '仅阅读按章节组织的正文节选，未独立复现实验。',
                                  'abstract_only': '仅阅读摘要，未核验全文或复现实验。'}[coverage]]

    def run_batch(self, batch_id):
        self.config_path.write_text(yaml.safe_dump(self.config, allow_unicode=True, sort_keys=False))
        return batch.run(self.root, self.config_path, batch_id, self.client, fetcher=self.fetcher)

    def enable_fulltext(self, cap=6000):
        self.config['prompts']['version'] = 'research-batch-v2'
        self.config['sources'][0].update(reading={'mode': 'full_text_preferred'}, evidence_max_chars=cap)

    def plan(self, batch_id):
        return store.checked_yaml(self.root,
            'reports/test/custom-topic/research-batches/%s/items/paper-one/candidate.yaml' % batch_id)

    def test_v1_prompts_request_and_fingerprint_are_frozen(self):
        self.assertEqual(store.digest(batch.RESEARCH_INSTRUCTIONS.encode()),
                         '905e0bfd7b9a3f938b87c251f2362a5fced825375dcd9e2bb6b22bdb1883d60b')
        self.assertEqual(store.digest(batch.REVIEW_INSTRUCTIONS.encode()),
                         '7e9d04f637bc8da45823c6b6a0ccdfd78a1e1712cfcf64967cca58b611bb3450')
        result = self.run_batch('legacy')
        manifest = store.checked_yaml(self.root, 'reports/test/custom-topic/research-batches/legacy/manifest.yaml')
        config = batch.inputs.load_config(self.root, self.config_path)
        expected = store.digest({'config': config, 'authorization': manifest['authorization'],
            'research_prompt': batch.RESEARCH_INSTRUCTIONS, 'review_prompt': batch.REVIEW_INSTRUCTIONS})
        self.assertEqual(manifest['fingerprint'], expected)
        self.assertEqual(set(self.client.calls[0]['payload']),
                         {'topic', 'research_context', 'metadata', 'coverage', 'original_material'})
        self.assertEqual(result['items'][0]['coverage'], 'abstract_only')
        report = (self.root / result['items'][0]['report_path']).read_text()
        self.assertNotIn('## 正文阅读记录', report)
        self.assertIn('仅论文摘要，未核验全文或实验数据', report)

    def test_v2_generation_and_review_share_same_body_sections_and_scope(self):
        self.enable_fulltext()
        result = self.run_batch('fulltext')
        self.assertEqual(result['items'][0]['status'], 'test_accepted')
        research, review = [item['payload'] for item in self.client.calls]
        self.assertEqual(research, {key: value for key, value in review.items() if key != 'candidate'})
        self.assertEqual(research['coverage'], 'full_text')
        self.assertIn('[S1]', research['original_material'])
        self.assertIn('A1:', research['original_material'])
        self.assertEqual(research['reading_scope']['format'], 'html')
        self.assertTrue(all('section_id' in item for item in research['evidence_index']))
        report = (self.root / result['items'][0]['report_path']).read_text()
        self.assertIn('## 正文阅读记录', report)
        self.assertIn('https://arxiv.org/html/2610.01234v2#method', report)
        self.assertIn('未独立复现实验', report)
        self.assertNotIn('仅论文摘要', report)

    def test_excerpt_and_abstract_fallback_are_not_claimed_as_fulltext(self):
        self.enable_fulltext(cap=700)
        excerpt = self.run_batch('excerpt')
        self.assertEqual(excerpt['items'][0]['coverage'], 'excerpt')
        report = (self.root / excerpt['items'][0]['report_path']).read_text()
        self.assertIn('仅阅读按章节组织的正文节选', report)
        self.assertIn('按预算截断：是', report)
        self.fetcher.fulltext_unavailable = True
        fallback = self.run_batch('fallback')
        self.assertEqual(fallback['items'][0]['coverage'], 'abstract_only')
        report = (self.root / fallback['items'][0]['report_path']).read_text()
        self.assertIn('全文获取失败后降级为仅摘要', report)
        self.assertIn('获取失败：html；原因：Synthetic full-text unavailable', report)
        self.assertIn('获取失败：pdf；原因：Synthetic full-text unavailable', report)

    def test_abstract_upgrade_is_separate_update_and_identical_fulltext_is_duplicate(self):
        self.run_batch('abstract')
        prior = {path: path.read_bytes() for path in self.root.rglob('*') if path.is_file()
                 and 'research-batches/abstract/' in path.as_posix()}
        self.enable_fulltext()
        deep = self.run_batch('deep')
        self.assertEqual(self.plan('deep')['action'], 'update')
        self.assertEqual(deep['completed_calls'], 2)
        self.assertEqual(prior, {path: path.read_bytes() for path in prior})
        duplicate = self.run_batch('same-fulltext')
        self.assertEqual(duplicate['items'][0]['status'], 'duplicate')
        self.assertEqual(duplicate['completed_calls'], 0)
        self.assertEqual(len(self.client.calls), 4)

    def test_profile_changes_are_not_silently_deduplicated(self):
        self.enable_fulltext()
        self.run_batch('profile')
        candidate = self.plan('profile')['candidate']
        changed = copy.deepcopy(candidate)
        changed['evidence']['reading_profile'] = 'arxiv-fulltext-v2'
        self.assertFalse(batch.same_evidence(candidate, changed))

    def test_failed_deepening_of_legacy_abstract_spends_no_model_calls(self):
        self.run_batch('old-abstract')
        self.enable_fulltext()
        self.fetcher.fulltext_unavailable = True
        result = self.run_batch('no-fulltext')
        self.assertEqual(result['completed_calls'], 0)
        self.assertEqual(result['items'][0]['status'], 'duplicate')
        self.assertEqual(result['items'][0]['reason'], 'full_text_unavailable_abstract_already_researched')
        self.assertEqual(len(self.client.calls), 2)
        self.fetcher.fulltext_unavailable = False
        result = self.run_batch('fulltext-recovered')
        self.assertEqual(result['completed_calls'], 2)
        self.assertEqual(self.plan('fulltext-recovered')['action'], 'update')

    def test_insight_v3_preserves_reading_scope_without_changing_v2_projection(self):
        self.enable_fulltext()
        self.run_batch('insight-input')
        candidate = self.plan('insight-input')['candidate']
        record = {'id': 'R1', 'origin': 'reviewed_research', 'path': 'report.md',
                  'source_ids': [candidate['source_id']], 'source_url': candidate['metadata']['source_url'],
                  'source_urls': [candidate['metadata']['source_url']], 'coverage': 'full_text',
                  'metadata': candidate['metadata'], 'original_material': 'A1: test',
                  'reading_scope': batch.reading_scope(candidate), 'locators': candidate['evidence']['locators'],
                  'acquisition_attempts': candidate['acquisition_attempts']}
        bundle = {'topic': 'custom-topic', 'research_context': {}, 'evidence': [record]}
        old = insight_inputs.model_payload(bundle, 'insight-v2')
        new = insight_inputs.model_payload(bundle, 'insight-v3')
        self.assertNotIn('reading_scope', old['evidence'][0])
        self.assertEqual(new['evidence'][0]['reading_scope'], record['reading_scope'])
        self.assertEqual(new['evidence'][0]['locators'], record['locators'])
        self.assertEqual(insight.instructions_for({'prompts': {'version': 'insight-v2'}}),
                         (insight.GENERATION_INSTRUCTIONS + '\n' + insight.CITATION_SCOPE_INSTRUCTIONS,
                          insight.REVIEW_INSTRUCTIONS + '\n' + insight.CITATION_SCOPE_INSTRUCTIONS))
        self.assertIn('全文阅读本身不构成研究结果的独立验证',
                      insight.instructions_for({'prompts': {'version': 'insight-v3'}})[0])

    def test_fulltext_checkpoint_revalidation_and_insight_share_original_body(self):
        self.enable_fulltext()
        research = self.run_batch('reviewed-fulltext')
        identifier = 'paper-11111111-1111-4111-8111-111111111111'
        history_path = self.root / 'sources/papers' / (identifier + '.md')
        history_path.write_text('---\n' + yaml.safe_dump({
            'id': identifier, 'kind': 'paper', 'title': 'Handwritten history', 'topics': ['custom-topic'],
            'source_url': 'https://arxiv.org/abs/2610.09999v1', 'arxiv_id': '2610.09999',
            'source_version': 'v1'}, sort_keys=False) + '---\n# Handwritten history\nA historical research hypothesis.\n')
        config = {'schema_version': 1, 'mode': 'insight_test', 'backend': 'chatgpt_plan',
            'topic': 'custom-topic', 'topics_file': 'config/research_topics.yaml',
            'models': {'generation': 'fixture-research', 'review': 'fixture-review'},
            'budget': {'max_calls': 4, 'month_max_calls': 10, 'max_input_chars': 500000,
                       'max_output_chars': 12000, 'timeout_seconds': 120, 'max_revisions': 1},
            'prompts': {'version': 'insight-v3'},
            'research_inputs': [{'receipt': research['receipt_path'],
                                 'config': self.config_path.relative_to(self.root).as_posix()}],
            'historical_inputs': [{'path': history_path.relative_to(self.root).as_posix(),
                                   'sha256': store.digest(history_path.read_bytes()), 'origin': 'human_baseline'}]}
        path = self.root / 'config/test/custom-topic/insight.yaml'
        path.write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False))
        client = FakeInsightClient()
        def synthesis_scope(candidate):
            candidate['coverage_note'] = 'R1读取抽取全文文本，未复现实验；H1为历史人工基线。'
            candidate['report']['comparisons'][1]['evidence_ids'] = ['R1']
        client.research_mutator = synthesis_scope
        result = insight.run(self.root, path, 'fulltext-synthesis', client, fetcher=self.fetcher)
        self.assertEqual(result['status'], 'test_accepted')
        generation, review = [call['payload'] for call in client.calls]
        self.assertEqual(generation, {key: value for key, value in review.items() if key != 'candidate'})
        evidence = generation['evidence'][0]
        self.assertEqual(evidence['coverage'], 'full_text')
        self.assertEqual(evidence['original_material'], self.client.calls[0]['payload']['original_material'])
        self.assertEqual(evidence['reading_scope'], self.client.calls[0]['payload']['reading_scope'])
        loaded = insight_inputs.load_config(self.root, path)
        self.fetcher.fulltext_unavailable = True
        with self.assertRaises(fixtures.SourceError):
            insight_inputs.prepare_bundle(self.root, loaded, fetcher=self.fetcher)
        self.assertEqual(len(client.calls), 2)


if __name__ == '__main__':
    unittest.main()
