"""Versioned paragraph semantics keep natural prose inside independent review."""

from copy import deepcopy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import offline as store
import writing_member as member


class WritingV2Paragraphs(unittest.TestCase):
    def setUp(self):
        text = '围绕具体问题解释判断，章节说明本节内容。'
        self.bundle = {
            'style_profile': {'version': 'writing-v2', 'path': 'config/writing_style.md',
                              'sha256': store.digest(text.encode()), 'text': text},
            'topic_card': {'title': '测试与验收', 'author_notes': '我用一组输入检查过排序。', 'target_words': 800},
            'evidence': [{'id': 'R1', 'origin': 'reviewed_research',
                          'can_support_original_facts': True, 'claims': [{'kind': 'fact'}]}]}
        self.candidate = {'title': '测试与验收', 'summary': '内部摘要。', 'limitations': [],
            'sections': [{'heading': '', 'paragraphs': [
                {'kind': 'author_experience', 'text': '我用一组输入检查过排序。', 'evidence_ids': []},
                {'kind': 'commentary', 'text': '这里究竟应该检查什么？', 'evidence_ids': []}]},
                {'heading': '哪些结果可以核对', 'paragraphs': [
                    {'kind': 'fact', 'text': '材料列出了任务输入。', 'evidence_ids': ['R1']}]}]}

    def review(self):
        return {'decision': 'pass', 'coverage_acknowledged': True, 'issues': [],
            'checks': [{'section_index': si, 'paragraph_index': pi,
                        'verdict': 'supported', 'evidence_ids': p['evidence_ids']}
                       for si, s in enumerate(self.candidate['sections'])
                       for pi, p in enumerate(s['paragraphs'])]}

    def test_natural_opening_and_author_notes_still_need_complete_review(self):
        member.validate_candidate(self.candidate, self.bundle, 'outline')
        self.assertEqual(member.validate_review(self.candidate, self.review(), self.bundle), 'pass')
        omitted = self.review()
        omitted['checks'].pop(0)
        with self.assertRaises(store.OfflineError):
            member.validate_review(self.candidate, omitted, self.bundle)
        blocked = self.review()
        blocked['issues'] = [{'severity': 'blocking', 'location': '章节',
                              'reason': '标题与正文无关。', 'suggestion': '围绕当前问题重写标题。'}]
        with self.assertRaises(store.OfflineError):
            member.validate_review(self.candidate, blocked, self.bundle)

    def test_missing_author_notes_or_fact_sources_cannot_borrow_transition_exception(self):
        self.bundle['topic_card']['author_notes'] = ''
        with self.assertRaises(store.OfflineError):
            member.validate_candidate(self.candidate, self.bundle, 'outline')
        self.candidate['sections'][0]['paragraphs'].pop(0)
        self.candidate['sections'][1]['paragraphs'][0]['evidence_ids'] = []
        with self.assertRaises(store.OfflineError):
            member.validate_candidate(self.candidate, self.bundle, 'outline')
        self.candidate['sections'][1]['paragraphs'][0]['evidence_ids'] = ['R1']
        unsupported = self.review()
        unsupported['checks'][0]['verdict'] = 'unsupported'
        with self.assertRaises(store.OfflineError):
            member.validate_review(self.candidate, unsupported, self.bundle)

    def test_v1_does_not_silently_accept_v2_or_unknown_profile(self):
        legacy = deepcopy(self.bundle)
        legacy.pop('style_profile')
        self.assertEqual(member.instructions(legacy, 'writing'), member.WRITING_INSTRUCTIONS)
        self.assertEqual(member.instructions(legacy, 'review'), member.REVIEW_INSTRUCTIONS)
        with self.assertRaises(store.OfflineError):
            member.validate_candidate(self.candidate, legacy, 'outline')
        self.bundle['style_profile']['version'] = 'writing-v3'
        with self.assertRaises(store.OfflineError):
            member.instructions(self.bundle, 'writing')


if __name__ == '__main__':
    unittest.main()
