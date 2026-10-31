"""Reader navigation and create-only storage; proofs have separate regressions."""

from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import researchdesk_offline as store
import researchdesk_reading as reading


class ReadingHome(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='researchdesk-reading-home-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.report = 'reports/agent-memory/解读/2026-10-30/paper.md'
        self.synthesis = 'insights/agent-memory/综述/2026-10-30.md'
        self.topic = 'articles/agent-memory/选题/2026-10-30.md'

        def research(root, files, warnings):
            files.update({self.report: '# 论文方法\n\n原有方法解释。\n',
                          self.synthesis: '# 综合思考\n\n这还是待验证的研究线索。\n',
                          self.topic: '# 选题\n\n写作前仍需确认。\n'})
            return [{'topic': 'agent-memory', 'cycle_id': 'agent-memory-20261030-0300',
                     'date': '2026-10-30', 'actual': '2026-10-30 03:07', 'title': '综合思考',
                     'synthesis': self.synthesis, 'insights': [{'title': '洞察问题'}],
                     'topics': [{'title': '选题', 'path': self.topic}],
                     'entries': [{'title': '论文', 'kind': '论文', 'updated': False,
                                  'source_url': 'https://arxiv.org/abs/2610.00001v1',
                                  'report': self.report, 'coverage': '仅摘要'}]}]

        for patcher in (mock.patch.object(reading, '_research_cycles', side_effect=research),
                        mock.patch.object(reading, '_writings', return_value=[]),
                        mock.patch.object(reading, '_library', return_value=({}, []))):
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_home_lists_specific_content_and_retains_manual_text_during_refresh(self):
        old = '# 我的旧首页\n\n用户的原有批注必须保留。\n'
        (self.root / reading.HOME).write_text(old)
        changed = reading.refresh(self.root)
        self.assertEqual(set(changed), {reading.HOME, self.report, self.synthesis, self.topic})
        text = (self.root / reading.HOME).read_text()
        for content in ('2026-10-30', '洞察问题', '仅摘要', '原有批注必须保留', '方法与总结'):
            self.assertIn(content, text)
        self.assertEqual(reading.refresh(self.root), [])
        with (self.root / reading.HOME).open('a') as handle:
            handle.write('\n我的新判断：继续核对评测条件。\n')
        self.assertEqual(reading.refresh(self.root), [])
        self.assertIn('我的新判断', (self.root / reading.HOME).read_text())

    def test_manual_reading_note_conflict_is_preserved_before_any_write(self):
        reading.refresh(self.root)
        target = self.root / self.report
        target.write_text(target.read_text() + '\n人工批注。\n')
        before = {p.relative_to(self.root).as_posix(): p.read_bytes()
                  for p in self.root.rglob('*') if p.is_file()}
        with self.assertRaisesRegex(store.OfflineError, '人工修改'):
            reading.refresh(self.root)
        self.assertEqual(before, {p.relative_to(self.root).as_posix(): p.read_bytes()
                                 for p in self.root.rglob('*') if p.is_file()})

    def test_invalid_admissions_cannot_make_a_stale_home_pass(self):
        def invalid(root, files, warnings):
            warnings.append('现有准入完整性待核对。')
            return []
        with mock.patch.object(reading, '_research_cycles', side_effect=invalid):
            with self.assertRaisesRegex(store.OfflineError, '未通过校验'):
                reading.build(self.root)
        with mock.patch.object(reading, '_research_cycles', return_value=[]):
            self.assertEqual(reading.refresh(self.root), [])

    def test_editorial_reading_keeps_author_text_but_cannot_rebind_its_source(self):
        path = 'insights/agent-memory/综述/edited.md'
        original = reading._reading(self.root, path, '# 原始排版\n', 'reports/original.md',
                                    '综合思考', 'agent-memory', '固定的原研究。')
        edited = original.replace('kind: reading_note\n', 'kind: reading_note\neditorial: true\n')
        edited = edited.replace('# 原始排版', '# 作者整理后的连贯说明')
        target = self.root / path
        target.parent.mkdir(parents=True)
        target.write_text(edited)
        self.assertEqual(reading._reading(self.root, path, '# 新的机械模板\n', 'reports/original.md',
                                         '综合思考', 'agent-memory', '固定的原研究。'), edited)
        with self.assertRaisesRegex(store.OfflineError, '绑定不同'):
            reading._reading(self.root, path, '# 新的机械模板\n', 'reports/another.md',
                             '综合思考', 'agent-memory', '固定的原研究。')


if __name__ == '__main__':
    unittest.main()
