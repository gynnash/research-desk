"""Pure v2 presentation and frozen-profile checks; no providers or filesystem writes."""

from copy import deepcopy
from pathlib import Path
import sys
import unittest

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import researchdesk_offline as store
import researchdesk_writing_style as style


def profile(text='从真实问题进入，不按资料顺序汇报。'):
    return {'version': 'writing-v2', 'path': 'config/writing_style.md',
            'sha256': store.digest(text.encode('utf-8')), 'text': text}


def bundle():
    return {'style_profile': profile(), 'topic': 'agent-memory', 'approval_id': 'approval-sample',
            'input_fingerprint': 'f' * 64, 'models': {'writing': 'writer', 'review': 'reviewer'},
            'evidence': [
                {'id': 'R1', 'title': '论文甲', 'path': 'reports/agent-memory/paper.md',
                 'source_urls': ['https://arxiv.org/html/2610.00001v1']},
                {'id': 'R2', 'title': '同一论文的历史研究', 'path': 'reports/agent-memory/history.md',
                 'source_urls': ['https://arxiv.org/html/2610.00001v1']},
                {'id': 'R3', 'title': '作者笔记', 'path': 'insights/agent-memory/note.md',
                 'source_urls': []}]}


def candidate():
    return {'title': '先把问题说清楚', 'summary': '不重复展示内部摘要。',
            'sections': [
                {'heading': '', 'paragraphs': [
                    {'kind': 'author_experience', 'text': '我最近先用一组输入核对排序。', 'evidence_ids': []},
                    {'kind': 'commentary', 'text': '真正要核对的是什么？', 'evidence_ids': []}]},
                {'heading': '测试与验收', 'paragraphs': [
                    {'kind': 'author_claim', 'text': '论文作者报告了任务内的改善。', 'evidence_ids': ['R1']},
                    {'kind': 'inference', 'text': '这提示我们先核对输入约定。', 'evidence_ids': ['R2', 'R3']},
                    {'kind': 'fact', 'text': '论文讨论了这组任务。', 'evidence_ids': ['R1', 'R2']}]}],
            'limitations': ['这里只依据给定节选，未独立复现实验。']}


class WritingStyle(unittest.TestCase):
    def test_profile_requires_exact_frozen_bytes_and_safe_path(self):
        value = profile()
        self.assertIs(style.validate_profile(value), value)
        for altered in [dict(value, text=value['text'] + '变化'),
                        dict(value, path='config/../private.md'),
                        dict(value, path='/config/writing_style.md'),
                        dict(value, version='writing-v3'),
                        dict(value, extra=True), dict(value, text='')]:
            with self.subTest(altered=altered):
                with self.assertRaises(store.OfflineError):
                    style.validate_profile(altered)

    def test_role_prompts_include_frozen_style_and_keep_fact_boundaries(self):
        value = bundle()
        before = deepcopy(value)
        for role in ('writing', 'review'):
            text = style.instructions(value, role)
            self.assertIn(value['style_profile']['text'], text)
            self.assertIn('author_notes', text)
            self.assertIn('commentary', text)
            self.assertIn('author_experience', text)
            self.assertIn('human_baseline', text)
        self.assertEqual(value, before)
        with self.assertRaises(store.OfflineError):
            style.instructions(value, 'publisher')
        with self.assertRaises(store.OfflineError):
            style.instructions({}, 'writing')

    def test_readable_body_and_deduplicated_claim_sources(self):
        value = bundle()
        article = candidate()
        before = deepcopy((value, article))
        path, text = style.render('candidate', article, value, 'writing-sample', '> TEST：唯一声明。')
        self.assertEqual(path, 'articles/test/agent-memory/writing-sample/candidate.md')
        metadata = yaml.safe_load(text.split('---', 2)[1])
        self.assertEqual(metadata['writing_version'], 'writing-v2')
        self.assertEqual(metadata['style_profile_sha256'], value['style_profile']['sha256'])
        self.assertFalse(metadata['publish_authorized'])
        self.assertEqual(text.count('> TEST：唯一声明。'), 1)
        body = text.split('# 先把问题说清楚', 1)[1]
        for pollution in ('## 导读', '已确认角度', '目标字数', '原作者声称，未经',
                          'R1', '确认记录', article['summary']):
            self.assertNotIn(pollution, body)
        self.assertIn('我最近先用一组输入核对排序。\n\n真正要核对的是什么？', body)
        self.assertNotIn('\n## \n', body)
        self.assertIn('论文作者报告了任务内的改善。〔[1](https://arxiv.org/html/2610.00001v1)〕', body)
        self.assertIn('这提示我们先核对输入约定。\n', body)
        self.assertIn('论文讨论了这组任务。〔[1](https://arxiv.org/html/2610.00001v1)〕', body)
        self.assertEqual(body.count('1. [论文甲]'), 1)
        self.assertIn('2. [作者笔记](../../../../insights/agent-memory/note.md)', body)
        self.assertIn('阅读范围：这里只依据给定节选，未独立复现实验。', body)
        self.assertEqual((value, article), before)

    def test_only_used_sources_are_exposed_and_no_limitations_can_be_empty(self):
        value, article = bundle(), candidate()
        article['sections'] = [article['sections'][0]]
        article['limitations'] = []
        _, text = style.render('draft', article, value, 'writing-sample', '> TEST：唯一声明。')
        self.assertNotIn('## 参考来源', text)
        self.assertNotIn('阅读范围：', text)
        self.assertNotIn('https://', text)

    def test_unknown_evidence_or_unsafe_source_cannot_render(self):
        value, article = bundle(), candidate()
        article['sections'][1]['paragraphs'][0]['evidence_ids'] = ['unknown']
        with self.assertRaises(store.OfflineError):
            style.render('candidate', article, value, 'writing-sample', '> TEST')
        article = candidate()
        value['evidence'][0]['source_urls'] = ['https://user:secret@example.com/paper']
        with self.assertRaises(store.OfflineError):
            style.render('candidate', article, value, 'writing-sample', '> TEST')


if __name__ == '__main__':
    unittest.main()
