"""Future source cards link to one analysis instead of copying its prose."""

from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import admission


class SourceCard(unittest.TestCase):
    def test_card_keeps_source_scope_notes_and_valid_links_without_analysis_copy(self):
        identifier = 'paper-00000000-0000-4000-8000-000000000001'
        source = {'id': identifier, 'kind': 'paper', 'title': 'Memory paper',
                  'source_url': 'https://arxiv.org/abs/2610.01234', 'source_version': 'v2'}
        original = {'kind': 'paper', 'metadata': dict(source, arxiv_id='2610.01234'),
                    'evidence': {'coverage': 'full_text'}}
        path = 'sources/papers/agent-memory/' + identifier + '.md'
        report = 'reports/agent-memory/cycle-research-' + identifier + '.md'
        synthesis = 'reports/agent-memory/cycle-synthesis.md'
        accepted = 'reports/agent-memory/admissions/cycle/accepted.yaml'
        content = admission._source_card(source, original, path, report, synthesis, accepted)
        self.assertIn('https://arxiv.org/abs/2610.01234v2', content)
        self.assertIn('完整抽取正文', content)
        self.assertIn('## 人工笔记', content)
        self.assertNotIn('## 主张与证据', content)
        self.assertIn('来源卡不保存原文全文副本', content)
        self.assertEqual(admission._source_footer_links(content, path, report, accepted), content)
        with tempfile.TemporaryDirectory() as root:
            admission._check_links(Path(root), {path: content, report: '# Research',
                                               synthesis: '# Synthesis'}, accepted)


if __name__ == '__main__':
    unittest.main()
