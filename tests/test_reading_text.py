"""Presentation keeps reviewed facts and scope, without providers or vault writes."""

from copy import deepcopy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import researchdesk_reading_text as reading


def sources():
    return [
        {'id': 'R1', 'display_title': '论文甲', 'kind': 'paper', 'coverage': 'abstract_only',
         'origin': 'reviewed_research', 'source_urls': ['https://arxiv.org/abs/2610.00001v1']},
        {'id': 'R2', 'display_title': '博客乙', 'kind': 'blog', 'coverage': 'excerpt',
         'origin': 'reviewed_research', 'source_urls': ['https://example.org/blog']},
        {'id': 'H1', 'display_title': '历史笔记丙', 'coverage': 'historical_note',
         'origin': 'human_baseline', 'source_urls': ['https://example.org/history']},
        {'id': 'H2', 'display_title': '历史笔记丁', 'coverage': 'historical_note',
         'origin': 'human_baseline', 'source_urls': ['https://example.org/history-two']},
    ]


class ReadingText(unittest.TestCase):
    def test_research_retains_numbers_and_abstract_boundary(self):
        evidence = dict(sources()[0], research_summary='作者提出一种记忆组织方法。',
                        research_claims=[{'kind': 'author_claim', 'text': '作者报告完成24项中的16项。',
                                          'evidence_ids': ['A1']}],
                        research_limitations=['仅有abstract_only，未检查完整评测。'])
        before = deepcopy(evidence)
        text = reading.research(evidence)
        self.assertIn('作者报告完成24项中的16项。', text)
        self.assertIn('仅有仅摘要，未检查完整评测。', text)
        self.assertIn('仅阅读摘要，未核验全文或复现实验', text)
        self.assertIn('https://arxiv.org/abs/2610.00001v1', text)
        self.assertNotIn('A1', text)
        self.assertNotIn('**作者', text)
        self.assertEqual(evidence, before)

    def test_synthesis_resolves_current_ranges_without_rebinding_old_namespace(self):
        evidence = sources()
        candidate = {'coverage_note': '来源相关不等于独立验证。',
                    'report': {'title': '理解记忆证据', 'summary': 'R1–R2关注不同问题。',
                    'comparisons': [{'kind': 'inference', 'text': 'R1与H1可以有限比较。', 'evidence_ids': ['R1', 'H1']}],
                    'limitations': ['H1–H2未重新核验；historical-H1-R2不是本轮来源。'],
                    'open_questions': ['R1的基线是否可比？']},
                    'insights': [{'title': '证据需要组合', 'hypothesis': '这是一条待验证假设。',
                                  'evidence_ids': ['R1', 'R2'], 'counterpoints': ['也可能由任务不同导致。'],
                                  'limitations': ['没有直接比较。'], 'validation': ['固定模型再检验。']}]}
        before = deepcopy((candidate, evidence))
        text = reading.synthesis(candidate, evidence)
        self.assertIn('这些研究材料关注不同问题。', text)
        self.assertIn('本轮采用的这些历史笔记未重新核验', text)
        self.assertIn('历史文档自身的来源编号不是本轮来源', text)
        self.assertNotRegex(text, r'\b[RH]\d+\b')
        for retained in ('这是一条待验证假设。', '也可能由任务不同导致。', '没有直接比较。',
                         '固定模型再检验。', '不能据此确认行业趋势', '仅阅读正文节选',
                         '来源相关不等于独立验证。', 'https://example.org/history-two'):
            self.assertIn(retained, text)
        self.assertEqual((candidate, evidence), before)

    def test_topic_keeps_value_questions_and_missing_evidence(self):
        card = {'title': '怎样检查证据', 'angle': '从R1切入。', 'why_now': '当前资料提出这个问题。',
                'audience': '工程师', 'key_questions': ['如何定义充分？'],
                'evidence_gaps': ['缺少全文评测。'], 'evidence_ids': ['R1']}
        text = reading.topic(card, sources())
        for retained in ('从《论文甲》切入。', '当前资料提出这个问题。', '工程师',
                         '如何定义充分？', '缺少全文评测。', 'https://arxiv.org/abs/2610.00001v1'):
            self.assertIn(retained, text)
        self.assertNotIn('https://example.org/blog', text)
        self.assertNotIn('确认记录', text)

    def test_writing_preserves_legacy_lead_and_every_body_sentence_without_audit_heading(self):
        candidate = {'title': '先说清问题', 'summary': '这篇文章讨论如何先核对输入。',
                     'sections': [{'heading': '', 'paragraphs': [
                         {'kind': 'author_experience', 'text': '我先核对了一组输入。', 'evidence_ids': []},
                         {'kind': 'author_claim', 'text': '作者报告得到16分。', 'evidence_ids': ['R1']},
                         {'kind': 'commentary', 'text': '我先核对了一组输入。', 'evidence_ids': []}]}],
                     'limitations': ['本篇只依据摘要，未复现实验。']}
        text = reading.writing(candidate, {'evidence': sources()})
        self.assertEqual(text.count('我先核对了一组输入。'), 2)
        self.assertIn('作者报告得到16分。', text)
        self.assertIn('本篇只依据摘要，未复现实验。', text)
        self.assertIn('# 先说清问题\n\n' + candidate['summary'] + '\n\n', text)
        self.assertNotIn('## 导读', text)
        self.assertNotIn('## \n', text)
        self.assertNotIn('author_claim', text)

    def test_ranges_are_scoped_types_but_single_references_use_literal_short_titles(self):
        evidence = sources()
        evidence[0]['display_title'] = 'Fixture Alpha: A Fictional Parser Paper'
        evidence[1]['display_title'] = 'Fixture Beta: Another Fictional Parser Paper'
        evidence[1]['kind'] = 'paper'
        text = reading._clean('R1–R2仅有摘要；H1–H2未复核。R1不同于R2。', evidence)
        self.assertEqual(text, '这些论文仅有摘要；本轮采用的这些历史笔记未复核。'
                              '《Fixture Alpha》不同于《Fixture Beta》。')
        for item in evidence[:2]:
            item['kind'] = 'blog'
        self.assertEqual(reading._clean('R1–R2仅有节选。', evidence), '这些博客仅有节选。')
        self.assertIn('这里提及的本轮研究资料', reading._clean('R1–R3仅有摘要。', evidence))
        research = dict(evidence[0], research_summary='作者提出该方法。',
                        research_claims=[], research_limitations=[])
        body = reading.research(research)
        self.assertTrue(body.startswith('# Fixture Alpha: A Fictional Parser Paper\n'))
        self.assertIn('[Fixture Alpha: A Fictional Parser Paper]', body)
        self.assertEqual(reading._mentioned('R1–R2与H1–H2。', evidence), {'R1', 'R2', 'H1', 'H2'})


if __name__ == '__main__':
    unittest.main()
