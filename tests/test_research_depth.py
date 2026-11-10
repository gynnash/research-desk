"""Full-original research depth and presentation, using only local fixtures."""

from copy import deepcopy
from pathlib import Path
import sys
import unittest

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import batch
import offline as store
import test_research_batch as fixtures
from test_fulltext_review import FulltextFetcher


def detailed_response():
    return {
        'summary': '这是一份基于完整虚构原文的机制解读，用来核对分节正文和独立审阅的衔接。',
        'claims': [
            {'kind': 'author_claim', 'text': text, 'evidence_ids': ['A1']}
            for text in (
                '## 保存引用为何有助于核对\n\n作者讨论保存来源引用的机制。',
                '在这一虚构方法中，来源引用为后续证据核对保留定位信息。',
                '## 证据边界如何贯穿处理流程\n\n作者把检查证据边界作为方法的一部分。',
                '处理时仍然需要区分被保存的内容和它能支持的判断。',
                '## 方法说明与效果验证的距离\n\n这份虚构正文说明了机制，没有提供量化性能结果。',
                '不能根据方法说明直接得出相对于其他系统的性能优势。')],
        'limitations': ['已阅读抽取全文，未独立复现实验；虚构样例不构成真实研究结论。']}


class ResearchDepth(unittest.TestCase):
    def setUp(self):
        fixtures.ConfigDrivenResearchBatch.setUp(self)
        self.config['sources'] = self.config['sources'][:1]
        self.config['sources'][0].update(reading={'mode': 'full_text_preferred'}, evidence_max_chars=6000)
        self.config['prompts']['version'] = 'research-batch-v4'
        self.config['budget'].update(max_documents=1, max_calls_per_batch=4, max_output_chars=24000)
        self.fetcher = FulltextFetcher()
        self.client.research_mutator = lambda result: (result.clear(), result.update(detailed_response()))

    def run_batch(self, identity='depth'):
        self.config_path.write_text(yaml.safe_dump(self.config, allow_unicode=True, sort_keys=False))
        return batch.run(self.root, self.config_path, identity, self.client, fetcher=self.fetcher)

    def test_v3_fingerprint_stays_frozen_and_v4_reviews_concrete_details(self):
        self.assertEqual(tuple(store.digest(value.encode()) for value in batch.instructions_for('research-batch-v3')),
                         ('0ee5a0a927c5976a2c0804765aee63c02bd0beb2f5f415f6f51d694c599a138e',
                          '7bf0f2200e610d0e80004148f041d19fe8a7829528a98c4b699e6315fe4d53cc'))
        generation, review = batch.instructions_for('research-batch-v4')
        for subject in ('基线', '指标', '数值', '比较条件', '方法步骤', '因果'):
            self.assertIn(subject, generation + review)
        self.assertIn('只复述摘要', review)
        self.assertIn('原文没有', review)

    def test_complete_body_reaches_both_roles_and_becomes_a_sectioned_article(self):
        self.client.review_decisions = ['revise', 'pass']
        result = self.run_batch()
        self.assertEqual(result['items'][0]['status'], 'test_accepted')
        self.assertEqual(result['completed_calls'], 4)
        generation, review = [call['payload'] for call in self.client.calls[:2]]
        self.assertEqual(generation, {key: value for key, value in review.items() if key != 'candidate'})
        self.assertEqual(generation['coverage'], 'full_text')
        self.assertEqual(self.client.calls[0]['limits']['max_output_chars'], 24000)
        body = (self.root / result['items'][0]['report_path']).read_text()
        self.assertIn('## 保存引用为何有助于核对', body)
        self.assertIn('## 证据边界如何贯穿处理流程', body)
        self.assertNotIn('## 问题、方法与结果', body)
        main, sources = body.split('## 资料来源与阅读范围')
        self.assertNotIn('A1', main)
        self.assertNotIn('https://', main)
        self.assertIn('https://arxiv.org/abs/2610.01234v2', sources)
        self.assertIn('未独立复现实验', body)
        cached = self.run_batch()
        self.assertTrue(cached['cached'])
        self.assertEqual(len(self.client.calls), 4)

    def test_summary_fallback_and_truncated_body_use_no_model_calls(self):
        self.fetcher.fulltext_unavailable = True
        result = self.run_batch('unavailable')
        self.assertEqual(result['completed_calls'], 0)
        self.assertEqual(self.client.calls, [])
        self.fetcher.fulltext_unavailable = False
        self.config['sources'][0]['evidence_max_chars'] = 700
        result = self.run_batch('truncated')
        self.assertEqual(result['completed_calls'], 0)
        self.assertNotEqual(result['items'][0]['status'], 'test_accepted')
        self.assertEqual(self.client.calls, [])

    def test_eleven_paragraph_revision_still_reaches_independent_review(self):
        self.client.review_decisions = ['revise', 'pass']

        def expanded_revision(result):
            result.clear()
            result.update(detailed_response())
            if 'previous_review' in self.client.calls[-1]['payload']:
                # A revision may split existing explanations into shorter,
                # checkable paragraphs while retaining the same section count.
                for claim in result['claims'][:5]:
                    extra = deepcopy(claim)
                    extra['text'] = extra['text'].split('\n\n')[-1]
                    result['claims'].append(extra)

        self.client.research_mutator = expanded_revision
        result = self.run_batch('expanded-revision')
        self.assertEqual(result['items'][0]['status'], 'test_accepted')
        self.assertEqual(result['items'][0]['revision_count'], 1)
        self.assertEqual(result['completed_calls'], 4)
        self.assertEqual(len(self.client.calls[-1]['payload']['candidate']['claims']), 11)
        self.assertEqual(self.client.calls[-1]['payload']['coverage'], 'full_text')

    def test_natural_fulltext_scope_reaches_independent_review(self):
        def natural_scope(result):
            result.clear()
            result.update(detailed_response())
            result['limitations'] = ['已阅读提供的完整抽取文本，未独立复现实验。']

        self.client.research_mutator = natural_scope
        result = self.run_batch('natural-scope')
        self.assertEqual(result['items'][0]['status'], 'test_accepted')
        self.assertEqual(result['completed_calls'], 2)
        self.assertIn('完整抽取文本', self.client.calls[1]['payload']['candidate']['limitations'][0])

    def test_author_native_baseline_names_are_not_internal_references(self):
        self.fetcher.body += ' Native baselines are named S0, S1 and S2.'

        def native_names(result):
            result.clear()
            result.update(detailed_response())
            result['claims'][1]['text'] += ' 作者将原生基线命名为 S0、S1 与 S2。'

        self.client.research_mutator = native_names
        result = self.run_batch('native-baselines')
        self.assertEqual(result['items'][0]['status'], 'test_accepted')
        self.assertEqual(result['completed_calls'], 2)
        self.assertIn('S0、S1 与 S2', self.client.calls[1]['payload']['candidate']['claims'][1]['text'])

    def test_prose_structure_and_internal_reference_leaks_are_checked(self):
        candidate = {'evidence': {'coverage': 'full_text', 'locators': [{'id': 'A1'}]}}
        valid = detailed_response()
        batch.validate_research(candidate, valid, 'research-batch-v4')
        terse = deepcopy(valid)
        terse['claims'] = terse['claims'][:3]
        with self.assertRaises(store.OfflineError):
            batch.validate_research(candidate, terse, 'research-batch-v4')
        for field in ('summary', 'text'):
            leaked = deepcopy(valid)
            if field == 'summary':
                leaked[field] += ' 详见 [A1]。'
            else:
                leaked['claims'][0][field] += ' [^source]'
            with self.assertRaises(store.OfflineError):
                batch.validate_research(candidate, leaked, 'research-batch-v4')


if __name__ == '__main__':
    unittest.main()
