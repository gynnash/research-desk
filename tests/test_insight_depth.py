"""Small offline checks for detailed, readable initial-batch synthesis."""

import copy
from pathlib import Path
import sys
import tempfile
import unittest

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import insight
import insight_inputs as inputs
import offline as store


def fixture():
    records = [dict(id='R%s' % number, origin='reviewed_research',
                    source_ids=['paper-one' if number == 1 else 'blog-two'],
                    identity_keys=['url:https://example.org/%s' % number],
                    path='reports/memory/study-%s.md' % number,
                    source_url='https://example.org/%s' % number,
                    source_urls=['https://example.org/%s' % number],
                    metadata={'title': '论文机制' if number == 1 else '博客设计'},
                    coverage='full_text', research_summary='已审阅方法与结果。',
                    research_claims=[], research_limitations=['未复现实验。'],
                    original_material='完整测试正文。') for number in (1, 2)]
    candidate = {'outcome': 'ready', 'coverage_note': '本批已读正文，尚无历史积累。',
                 'report': {'title': '记忆写入与使用的分工', 'summary': '作者分别讨论了记忆更新与检索，机制可比较而实验不能直接排序。',
                            'comparisons': [
                                {'text': '论文作者解释记忆更新的机制。', 'kind': 'author_claim', 'evidence_ids': ['R1']},
                                {'text': '博客说明检索进入上下文的路径。', 'kind': 'author_claim', 'evidence_ids': ['R2']},
                                {'text': '我们推测更新与检索需要联合验证。', 'kind': 'inference', 'evidence_ids': ['R1', 'R2']}],
                            'limitations': ['本批没有跨时间历史，不能推断行业趋势。'],
                            'open_questions': ['固定检索预算后，更新策略是否仍会影响任务成功？']},
                 'insights': [{'title': '分开检查写入和使用', 'hypothesis': '两种机制提示保存与任务使用可能存在不同失败点，这是待验证假设。',
                               'evidence_ids': ['R1', 'R2'], 'counterpoints': ['也可能只是任务设置不同。'],
                               'limitations': ['没有统一任务比较。'], 'validation': ['固定任务和模型，分别改变更新与检索策略。']}],
                 'topics': [{'title': '记忆为什么写下了却用不上？', 'angle': '从两个实际机制解释问题。',
                             'audience': 'Agent工程读者', 'why_now': '这批原文提供了可比较的设计。',
                             'insight_indices': [0], 'evidence_ids': ['R1', 'R2'],
                             'key_questions': ['哪些环节影响记忆使用？'], 'evidence_gaps': ['还需相同任务验证。']}]}
    bundle = {'topic': 'memory', 'research_context': {'name': 'Memory'},
              'evidence': records, 'input_fingerprint': 'a' * 64}
    return candidate, bundle


class DeepInsight(unittest.TestCase):
    def test_initial_batch_needs_distinct_current_sources_without_relaxing_legacy(self):
        candidate, bundle = fixture()
        self.assertTrue(insight.validate_candidate(candidate, bundle, prompt_version='insight-v6'))
        with self.assertRaises(store.OfflineError):
            insight.validate_candidate(candidate, bundle, prompt_version='insight-v5')
        same = copy.deepcopy(bundle)
        same['evidence'][1]['identity_keys'] = same['evidence'][0]['identity_keys']
        with self.assertRaises(store.OfflineError):
            insight.validate_candidate(candidate, same, prompt_version='insight-v6')
        candidate['insights'][0]['evidence_ids'] = ['R1', 'H1']
        with self.assertRaises(store.OfflineError):
            insight.validate_candidate(candidate, bundle, prompt_version='insight-v6')

    def test_existing_history_still_must_be_used(self):
        candidate, bundle = fixture()
        bundle['evidence'].append(dict(id='H1', origin='human_baseline', source_ids=['historical'], identity_keys=[]))
        with self.assertRaises(store.OfflineError):
            insight.validate_candidate(candidate, bundle, prompt_version='insight-v6')

    def test_initial_article_has_readable_body_source_footer_and_no_fake_trend(self):
        candidate, bundle = fixture()
        config = {'topic': 'memory', 'prompts': {'version': 'insight-v6'}}
        outputs, content = insight.render_outputs(Path('/tmp'), 'reports/test/memory/insight-runs/first',
                                                   config, 'first', candidate, bundle)
        self.assertEqual(outputs['insights'], [])
        article = content[outputs['report']]
        self.assertIn('这是初始批次，尚无历史积累', article)
        body, footer = article.split('## 资料来源与阅读范围', 1)
        self.assertIn('两种机制提示保存与任务使用', body)
        self.assertIn('论文机制](https://example.org/1)', footer)
        self.assertNotIn('R1', body.split('---', 2)[2])
        self.assertNotIn('H1', article)
        payload = inputs.model_payload(bundle, 'insight-v6')
        self.assertEqual(payload['history_coverage']['documents'], 0)
        self.assertEqual(payload['evidence'][0]['original_material'], '完整测试正文。')

    def test_v6_config_allows_empty_history_and_larger_output_budget_only_explicitly(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            (root / 'config').mkdir()
            (root / 'config/research_topics.yaml').write_text(yaml.safe_dump({
                'schema_version': 1, 'topics': {'memory': {'enabled': True, 'name': 'Memory',
                'description': '记忆研究', 'scope': ['Memory'], 'keywords': ['memory']}}}))
            receipt = 'reports/test/memory/research-batches/first/receipt-attempt-1.yaml'
            (root / receipt).parent.mkdir(parents=True)
            (root / receipt).write_text('{}')
            (root / 'config/research.yaml').write_text('{}')
            config = {'schema_version': 1, 'mode': 'insight_test', 'backend': 'chatgpt_plan',
                      'topic': 'memory', 'topics_file': 'config/research_topics.yaml',
                      'models': {'generation': 'fixture-research', 'review': 'fixture-review'},
                      'budget': {'max_calls': 4, 'month_max_calls': 100, 'max_input_chars': 500000,
                                 'max_output_chars': 24000, 'timeout_seconds': 120, 'max_revisions': 1},
                      'prompts': {'version': 'insight-v6'},
                      'research_inputs': [{'receipt': receipt, 'config': 'config/research.yaml'}],
                      'historical_inputs': []}
            path = root / 'config/insight.yaml'
            path.write_text(yaml.safe_dump(config))
            self.assertEqual(inputs.load_config(root, path)['historical_inputs'], [])
            config['prompts']['version'] = 'insight-v5'
            config['budget']['max_output_chars'] = 12000
            path.write_text(yaml.safe_dump(config))
            with self.assertRaises(store.OfflineError):
                inputs.load_config(root, path)


if __name__ == '__main__':
    unittest.main()
