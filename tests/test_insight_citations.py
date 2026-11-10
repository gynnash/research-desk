"""Offline regression for historical and current evidence-label collisions."""

import copy
import json
from pathlib import Path
import sys
import unittest

REPOSITORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY / 'scripts'))
import insight
import insight_inputs as inputs


class CitationProjection(unittest.TestCase):
    def bundle(self):
        records = []
        for identifier, title, source in [('R1', 'MemSyco-Bench', 'paper-new-1'),
                                          ('R2', 'Co2In', 'paper-new-2')]:
            records.append({'id': identifier, 'origin': 'reviewed_research',
                'path': 'reports/' + identifier + '.md', 'source_ids': [source],
                'source_url': 'https://arxiv.org/abs/' + identifier,
                'source_urls': ['https://arxiv.org/abs/' + identifier],
                'coverage': 'abstract_only', 'metadata': {'title': title},
                'original_material': 'Unchanged material for ' + title})
        for identifier, title, source in [('H1', 'LangChain', 'blog-langchain'),
                                          ('H2', 'Letta', 'blog-letta')]:
            records.append({'id': identifier, 'origin': 'human_baseline',
                'path': 'sources/blogs/' + source + '.md', 'source_ids': [source],
                'source_url': 'https://example.org/' + source,
                'source_urls': ['https://example.org/' + source],
                'coverage': 'historical_note', 'text': '# ' + title + '\nHistorical note.'})
        records.append({'id': 'H5', 'origin': 'human_baseline',
            'path': 'reports/yesterday.md', 'source_ids': ['blog-langchain', 'blog-letta'],
            'source_url': None, 'source_urls': ['https://example.org/blog-langchain',
                                              'https://example.org/blog-letta'],
            'coverage': 'historical_note',
            'text': '# Yesterday\nR2节选是 LangChain；H1 是 Letta。\n'
                    '[R2](../reports/R2.md) [H1](https://example.org/H1)\n'
                    'R1、R2 与 H1—H6；R20；R2D2；AR2；R02。'})
        return {'topic': 'agent-memory', 'research_context': {}, 'evidence': records}

    def test_current_index_and_history_namespace_cannot_swap_sources(self):
        bundle = self.bundle()
        before = copy.deepcopy(bundle)
        payload = inputs.model_payload(bundle, 'insight-v2')
        self.assertEqual(payload['evidence_index']['R2']['title'], 'Co2In')
        self.assertEqual(payload['evidence_index']['R2']['coverage'], 'abstract_only')
        self.assertEqual(payload['evidence_index']['H1']['title'], 'LangChain')
        self.assertEqual(payload['evidence_index']['H2']['title'], 'Letta')
        historical = payload['evidence'][-1]
        self.assertIn('historical-H5-R2节选是 LangChain；historical-H5-H1 是 Letta', historical['text'])
        self.assertNotIn('historical-H5-R2', payload['evidence_index'])
        self.assertEqual(bundle, before)
        self.assertEqual(payload['evidence'][1]['original_material'], bundle['evidence'][1]['original_material'])

    def test_only_labels_change_and_destinations_and_longer_words_survive(self):
        record = self.bundle()['evidence'][-1]
        projected, aliases = inputs.scoped_history(record)
        self.assertIn('[historical-H5-R2](../reports/R2.md)', projected)
        self.assertIn('[historical-H5-H1](https://example.org/H1)', projected)
        self.assertIn('R2D2；AR2；R02', projected)
        for alias in sorted(aliases, key=len, reverse=True):
            projected = projected.replace(alias, alias.rsplit('-', 1)[1])
        self.assertEqual(projected, record['text'])

    def test_saved_collision_is_namespaced_without_modifying_historical_text(self):
        # Preserve the actual collision pattern as a small independent fixture;
        # production research may be reset without retiring this regression.
        original = ('# Historical synthesis\n\n'
                    'R1 为论文摘要；R2 节选描述文件卸载。\n'
                    'H1 历史笔记称 Letta 采用记忆块，H2 提供相关材料。\n')
        record = {'id': 'H5', 'text': original}
        projected, aliases = inputs.scoped_history(record)
        self.assertIn('historical-H5-R2 节选描述文件卸载', projected)
        self.assertIn('historical-H5-H1 历史笔记称 Letta', projected)
        self.assertEqual(set(aliases), {'historical-H5-R1', 'historical-H5-R2',
                                       'historical-H5-H1', 'historical-H5-H2'})
        self.assertEqual(record['text'], original)

    def test_nested_and_reference_link_destinations_are_byte_identical(self):
        text = ('[R2](../reports/foo_(bar)/R2.md)\n'
                '[H1](<../reports/a H1.md>)\n'
                '[R2]: ../reports/R2.md "title"\n'
                '[other]: <../reports/a H1.md>\n'
                'https://x.test/foo_(bar)/R2\n'
                '[H1](../reports/foo_\\(bar\\)/H1.md)\n')
        projected, aliases = inputs.scoped_history({'id': 'H5', 'text': text})
        self.assertEqual(projected, text.replace('[R2]', '[historical-H5-R2]').replace('[H1]', '[historical-H5-H1]'))
        self.assertEqual(aliases, ['historical-H5-H1', 'historical-H5-R2'])

    def test_link_spans_do_not_hide_adjacent_chinese_citations(self):
        text = ('[原始来源](https://example.org/path)；R2 是旧来源。\n'
                '见 https://example.org/path，R2 是旧来源。\n'
                '(https://example.org/foo_(bar)/H1)；H1 是旧来源。')
        projected, _ = inputs.scoped_history({'id': 'H5', 'text': text})
        expected = text.replace('；R2', '；historical-H5-R2').replace('，R2', '，historical-H5-R2')
        expected = expected.replace('；H1', '；historical-H5-H1')
        self.assertEqual(projected, expected)

    def test_multiline_angle_and_html_destinations_are_preserved(self):
        text = ('[old]:\n  ../reports/R2.md\n'
                '[R2](<../folder(a/R2.md>)；R2 来源\n'
                '<a href="../R2.md">R2</a><img src=../H1.png>')
        projected, _ = inputs.scoped_history({'id': 'H5', 'text': text})
        expected = text.replace('[R2]', '[historical-H5-R2]').replace('；R2', '；historical-H5-R2')
        expected = expected.replace('>R2<', '>historical-H5-R2<')
        self.assertEqual(projected, expected)

    def test_v1_projection_and_instructions_remain_byte_compatible(self):
        bundle = self.bundle()
        expected = {'topic': bundle['topic'], 'research_context': bundle['research_context'], 'evidence': []}
        for record in bundle['evidence']:
            keys = {'id', 'origin', 'path', 'source_ids', 'source_url', 'source_urls', 'coverage', 'historical_status'}
            keys |= ({'metadata', 'research_summary', 'research_claims', 'research_limitations', 'original_material'}
                     if record['origin'] == 'reviewed_research' else {'text'})
            expected['evidence'].append({key: value for key, value in record.items() if key in keys})
        self.assertEqual(json.dumps(inputs.model_payload(bundle), ensure_ascii=False),
                         json.dumps(expected, ensure_ascii=False))
        self.assertEqual(insight.instructions_for({'prompts': {'version': 'insight-v1'}}),
                         (insight.GENERATION_INSTRUCTIONS, insight.REVIEW_INSTRUCTIONS))
        generation, review = insight.instructions_for({'prompts': {'version': 'insight-v2'}})
        self.assertIn(insight.CITATION_SCOPE_INSTRUCTIONS, generation)
        self.assertIn(insight.CITATION_SCOPE_INSTRUCTIONS, review)

    def test_history_reordering_does_not_change_source_meanings(self):
        bundle = self.bundle()
        bundle['evidence'][2]['id'], bundle['evidence'][3]['id'] = 'H2', 'H1'
        bundle['evidence'].reverse()
        payload = inputs.model_payload(bundle, 'insight-v2')
        self.assertEqual(payload['evidence_index']['H1']['title'], 'Letta')
        self.assertEqual(payload['evidence_index']['H2']['title'], 'LangChain')
        self.assertEqual(payload['evidence_index']['R2']['title'], 'Co2In')

    def test_unknown_prompt_version_is_rejected(self):
        for action in (lambda: inputs.model_payload(self.bundle(), 'insight-v999'),
                       lambda: insight.instructions_for({'prompts': {'version': 'insight-v999'}})):
            with self.assertRaises(insight.store.OfflineError):
                action()


if __name__ == '__main__':
    unittest.main()
