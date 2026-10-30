"""Readable research documents keep the same evidence and independent review."""

from datetime import date, timedelta
from pathlib import Path
import re
import sys
import unittest

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import researchdesk_batch as batch
import researchdesk_catalog as catalog
import researchdesk_insight as insight
import researchdesk_insight_inputs as inputs
import researchdesk_offline as store
import test_research_batch as research_fixtures
from test_fulltext_review import FulltextFetcher
import test_insight as insight_fixtures
import test_cycle as cycle_fixtures
import test_archive_admission as archive_fixtures


class FrozenInstructions(unittest.TestCase):
    def test_legacy_prompt_bytes_are_unchanged(self):
        expected = {
            'research-batch-v1': ('905e0bfd7b9a3f938b87c251f2362a5fced825375dcd9e2bb6b22bdb1883d60b',
                                  '7e9d04f637bc8da45823c6b6a0ccdfd78a1e1712cfcf64967cca58b611bb3450'),
            'research-batch-v2': ('f2bc64c703125e6eccec39eb2a4377ce4c2e3a3c376b9beac460db5a8c278bcf',
                                  '2413e44f34458ba82fbc1d824d08c66ee3ec46ee05854d0912f57f63c18eb36b'),
            'insight-v1': ('a67988094817643a7764a7d6513f3d3eeac3f311f0e344bf448cc75d35cafb56',
                           'b5e6727874db346e99eedfde3ecd6a38300d4e7dce9da03919c4eba0a6a21d23'),
            'insight-v2': ('7432708f0668761403bcb2c46cff7e10d75111f38d2b78ded87b7e6d9ba1fa30',
                           '32144fff66ce745c2fdcad65d3d5e071d2d09f54f448a52ae46cb7a68a452fe4'),
            'insight-v3': ('082d264aae3a603179f97247b3d9b090a27adb15739442286fc5cb4273853b9b',
                           'fcb6bd24af9a908c4cbac4b76340e809416fce247985c583d03e3881b3548eef'),
            'insight-v4': ('2ae2b143c4a84d7d2e514c3a1abde70878b781aba626379c58793ea76cba63f7',
                           '1c5b98c3a0e96bf5fe6028ba3e1288576e403370c82bb543f4b0c75b7495c89d')}
        for version, hashes in expected.items():
            with self.subTest(version=version):
                prompts = (batch.instructions_for(version) if version.startswith('research') else
                           insight.instructions_for({'prompts': {'version': version}}))
                self.assertEqual(tuple(store.digest(value.encode()) for value in prompts), hashes)

    def test_new_prompts_review_summary_transitions_and_causality_without_new_schema(self):
        for version, resolver in [('research-batch-v3', batch.instructions_for),
                                  ('insight-v5', lambda value: insight.instructions_for({'prompts': {'version': value}}))]:
            generation, review = resolver(version)
            self.assertIn('summary', review)
            self.assertIn('因果', review)
            self.assertIn('输出字符预算', generation)
            self.assertIn('evidence_ids', generation)
            self.assertIn('未复现实验', generation.replace('未独立复现实验', '未复现实验'))
            self.assertIn('正文不写逐段引用', generation)
            self.assertNotIn('程序会生成段末脚注', generation)
            self.assertNotIn('程序负责段末简洁脚注', generation)


class ArticleResearch(unittest.TestCase):
    def setUp(self):
        research_fixtures.ConfigDrivenResearchBatch.setUp(self)
        self.config['sources'] = self.config['sources'][:1]
        self.config['prompts']['version'] = 'research-batch-v3'
        self.config['budget'].update(max_documents=1, max_calls_per_batch=4, max_output_chars=8000)
        self.config['sources'][0]['reading'] = {'mode': 'full_text_preferred'}
        self.fetcher = FulltextFetcher()
        def limits(result):
            coverage = self.client.calls[-1]['payload']['coverage']
            result['limitations'] = [{'full_text': '已阅读抽取全文，未独立复现实验。',
                                      'excerpt': '仅阅读正文节选，未独立复现实验。',
                                      'abstract_only': '仅阅读摘要，未核验全文或复现实验。'}[coverage]]
        self.client.research_mutator = limits

    def run_batch(self, identity='readable'):
        self.config_path.write_text(yaml.safe_dump(self.config, allow_unicode=True, sort_keys=False))
        return batch.run(self.root, self.config_path, identity, self.client, fetcher=self.fetcher)

    def test_v3_reuses_same_body_for_two_roles_and_renders_plain_prose(self):
        result = self.run_batch()
        self.assertEqual(result['completed_calls'], 2)
        generation, review = [call['payload'] for call in self.client.calls]
        self.assertEqual(generation, {key: value for key, value in review.items() if key != 'candidate'})
        self.assertEqual(generation['coverage'], 'full_text')
        self.assertIn('reading_scope', generation)
        self.assertIn('summary', self.client.calls[1]['instructions'])
        report = (self.root / result['items'][0]['report_path']).read_text()
        body, sources = report.split('## 资料来源与阅读范围', 1)
        self.assertNotIn('[^', report)
        self.assertNotIn('## 主张与证据', body)
        self.assertNotIn('**作者声称', body)
        self.assertRegex(sources, r'- \[[^\n]+\]\(https://arxiv.org/abs/2610.01234v2\)')
        self.assertIn('完整抽取正文', sources)
        self.assertIn('未独立复现实验', report)
        for internal in ('研究模型', '独立审阅', '字符', '散列', '修订次数', '获取失败：', 'A1', 'S1'):
            self.assertNotIn(internal, report)

    def test_excerpt_and_failed_fulltext_boundaries_survive_article_rendering(self):
        self.config['sources'][0]['evidence_max_chars'] = 700
        result = self.run_batch('excerpt')
        report = (self.root / result['items'][0]['report_path']).read_text()
        self.assertIn('仅阅读正文节选', report)
        candidate = store.checked_yaml(self.root,
            'reports/test/custom-topic/research-batches/excerpt/items/paper-one/candidate.yaml')['candidate']
        self.assertTrue(candidate['evidence']['truncated'])
        self.fetcher.fulltext_unavailable = True
        result = self.run_batch('fallback')
        report = (self.root / result['items'][0]['report_path']).read_text()
        self.assertIn('全文未能获取，本次仅阅读摘要', report)
        self.assertNotIn('Synthetic full-text unavailable', report)
        candidate = store.checked_yaml(self.root,
            'reports/test/custom-topic/research-batches/fallback/items/paper-one/candidate.yaml')['candidate']
        self.assertEqual({entry['format'] for entry in candidate['acquisition_attempts'] if entry['status'] == 'failed'},
                         {'html', 'pdf'})

    def test_plain_abstract_does_not_claim_a_fulltext_fetch_failed(self):
        self.config['sources'][0].pop('reading')
        result = self.run_batch()
        report = (self.root / result['items'][0]['report_path']).read_text()
        self.assertIn('仅阅读摘要', report)
        self.assertNotIn('全文未能获取', report)
        self.assertNotIn('[^', report)


class ArticleInsight(unittest.TestCase):
    def setUp(self):
        insight_fixtures.InsightLoop.setUp(self)
        self.config['prompts']['version'] = 'insight-v5'
        self.config['budget'].update(max_input_chars=500000, max_output_chars=8000)
        entry = self.config['historical_inputs'][0]
        metadata = yaml.safe_load(self.history_path.read_text().split('---', 2)[1])
        entry.update(inputs.history_details(self.root, entry['path'], metadata, self.history_path.read_bytes()))
        end = date(2026, 10, 31)
        entry['history_window'] = {'start': (end - timedelta(days=180)).isoformat(),
                                   'end': end.isoformat(), 'lookback_days': 180}

    def test_v5_keeps_evidence_internal_and_only_lists_sources_at_end(self):
        original = self.history_path.read_bytes()
        insight_fixtures.InsightLoop.write_config(self)
        result = insight.run(self.root, self.config_path, 'readable', self.client, fetcher=self.fetcher)
        self.assertEqual(result['status'], 'test_accepted')
        self.assertEqual(len(self.client.calls), 2)
        generation, review = [call['payload'] for call in self.client.calls]
        self.assertEqual(generation, {key: value for key, value in review.items() if key != 'candidate'})
        self.assertIn('history_coverage', generation)
        self.assertEqual(generation['evidence'][-1]['historical_origin'], 'human_note')
        self.assertIn('完整叙述', self.client.calls[1]['instructions'])
        self.assertEqual(result['outputs']['insights'], [])
        for relative in result['output_hashes']:
            if not relative.endswith('.md'):
                continue
            text = (self.root / relative).read_text()
            body, sources = text.split('## 资料来源与阅读范围', 1)
            body = body.split('---', 2)[2]
            self.assertNotRegex(body, r'\[(?:R|H)\d+\]')
            self.assertNotIn('[^', text)
            self.assertRegex(sources, r'- \[[^\n]+\]\(https://')
            for internal in ('研究记录', '独立审阅', '字符', '散列', '修订次数', '跨度', 'R1', 'H1', 'A1'):
                self.assertNotIn(internal, body + sources)
            self.assertIn('未经本轮原文复核', sources)
            self.assertIn('仅阅读摘要', sources)
        self.assertEqual(generation['history_coverage']['actual_span_days'], 0)
        synthesis = (self.root / result['outputs']['report']).read_text()
        self.assertIn('## 记忆的可用性需要独立验证', synthesis)
        self.assertIn('可把记忆保存与任务使用分开验证', synthesis)
        self.assertIn('这些有限材料没有直接比较不同方案', synthesis)
        self.assertIn('设计跨会话任务', synthesis)
        metadata = yaml.safe_load(synthesis.split('---', 2)[1])
        self.assertEqual(set(metadata['source_ids']), {identifier for record in generation['evidence']
                                                       for identifier in record['source_ids']})
        topic = (self.root / result['outputs']['topics'][0]).read_text()
        self.assertIn('[本轮深度思考](', topic)
        self.assertNotIn('insight-1.md', topic)
        self.assertIn('待你确认选题', topic)
        self.assertIn('approval_required: true', topic)
        self.assertIn('writing_started: false', topic)
        self.assertEqual(self.history_path.read_bytes(), original)
        rerun = insight.run(self.root, self.config_path, 'readable', self.client, fetcher=self.fetcher)
        self.assertTrue(rerun['cached'])
        self.assertEqual(len(self.client.calls), 2)


class ArticleCycle(unittest.TestCase):
    fake_research = cycle_fixtures.ResearchInsightCycle.fake_research
    fake_insight = cycle_fixtures.ResearchInsightCycle.fake_insight

    def setUp(self):
        cycle_fixtures.ResearchInsightCycle.setUp(self)

    def test_explicit_new_presentation_selects_v3_v5_without_changing_budgets(self):
        self.config.update(presentation='technical_article')
        self.config['history']['lookback_days'] = 180
        self.config_path.write_text(yaml.safe_dump(self.config, allow_unicode=True, sort_keys=False))
        result = cycle_fixtures.ResearchInsightCycle.run_cycle(self)
        self.assertEqual(result['status'], 'completed')
        base = 'reports/test/custom-topic/cycles/first/configs/'
        research = store.checked_yaml(self.root, base + 'research.yaml')
        generated = store.checked_yaml(self.root, base + 'insight.yaml')
        self.assertEqual(research['prompts']['version'], 'research-batch-v3')
        self.assertEqual(generated['prompts']['version'], 'insight-v5')
        self.assertEqual(generated['budget']['max_output_chars'], 8000)
        self.client.infer.assert_not_called()

    def test_old_frozen_cycle_ignores_new_live_presentation_on_resume(self):
        with self.assertRaises(store.SimulatedInterruption):
            cycle_fixtures.ResearchInsightCycle.run_cycle(self, fail_after='after_research')
        old_research = (self.root / 'reports/test/custom-topic/cycles/first/configs/research.yaml').read_bytes()
        self.config.update(presentation='technical_article')
        self.config['history']['lookback_days'] = 180
        self.config_path.write_text(yaml.safe_dump(self.config, allow_unicode=True, sort_keys=False))
        cycle_fixtures.ResearchInsightCycle.run_cycle(self)
        self.assertEqual((self.root / 'reports/test/custom-topic/cycles/first/configs/research.yaml').read_bytes(), old_research)
        child = store.checked_yaml(self.root, 'reports/test/custom-topic/cycles/first/configs/insight.yaml')
        self.assertEqual(child['prompts']['version'], 'insight-v2')
        self.research_run.assert_called_once()


class FormalArticleCycle(unittest.TestCase):
    def setUp(self):
        archive_fixtures.ArchivedFormalCycle.setUp(self)

    def test_archived_v3_v5_formal_files_remain_verifiable_and_linked(self):
        plan, accepted, identifier, client, fetcher = archive_fixtures.ArchivedFormalCycle.run_archived_cycle(
            self, presentation='technical_article')
        entries, proofs = catalog.collect(self.root)
        self.assertEqual(len(proofs), 1)
        self.assertTrue({'synthesis', 'research', 'topic_proposal', 'original_snapshot', 'source'}
                        .issubset({entry['group'] for entry in entries}))
        self.assertIn('测试记忆材料的有限比较', catalog.render(self.root))
        for path, content in plan['files'].items():
            if not path.endswith('.md'):
                continue
            for target in re.findall(r'\[[^\]]+\]\(([^)\n]+)\)', content):
                if '://' in target or target.startswith('#'):
                    continue
                self.assertNotIn('/test/', target)
                self.assertTrue((self.root / Path(path).parent / target).resolve().is_file(), (path, target))
        synthesis_path = next(entry['path'] for entry in entries if entry['group'] == 'synthesis')
        synthesis = (self.root / synthesis_path).read_text()
        self.assertIn('## 资料来源与阅读范围', synthesis)
        self.assertNotIn('[^', synthesis)
        self.assertNotIn('> TEST', synthesis)
        source_ids = yaml.safe_load(synthesis.split('---', 2)[1])['source_ids']
        self.assertFalse(set(source_ids) & set(accepted['source_id_map']))
        self.assertEqual(len(client.calls), 4)
        self.assertEqual(accepted['new_model_calls'], 0)
        fetcher.fetch.assert_not_called()
        fetcher.fetch_pdf.assert_not_called()


if __name__ == '__main__':
    unittest.main()
