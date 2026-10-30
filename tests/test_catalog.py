"""The reading index must not overwrite annotations or trust unaccepted files."""

from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import researchdesk_catalog as catalog
import researchdesk_offline as store


class ReadingCatalog(unittest.TestCase):
    def test_reading_version_requires_matching_admitted_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = 'reports/agent-memory/cycle-synthesis.md'
            original = root / source
            original.parent.mkdir(parents=True)
            original.write_text('已审阅内容', encoding='utf-8')
            reading = root / 'workbench/阅读/agent-memory/example.md'
            reading.parent.mkdir(parents=True)
            metadata = {'title': '可读技术文章', 'kind': 'research_reading', 'status': 'editorial',
                        'topic': 'agent-memory', 'source_cycle': 'cycle',
                        'derived_from': {source: store.digest(original.read_bytes())}}
            import yaml
            reading.write_text('---\n' + yaml.safe_dump(metadata, allow_unicode=True)
                               + '---\n\n正文。\n', encoding='utf-8')
            entries = [{'path': source, 'topic': 'agent-memory'}]
            self.assertEqual(catalog.reading_versions(root, entries)[source]['title'], '可读技术文章')
            with self.assertRaises(store.OfflineError):
                catalog.reading_versions(root, [])
            original.write_text('后来修改的依据', encoding='utf-8')
            with self.assertRaises(store.OfflineError):
                catalog.reading_versions(root, entries)

    def test_adopts_manual_snapshot_without_deleting_its_text(self):
        old = '---\ntitle: 手工索引\n---\n\n# 自己的阅读记录\n\n保留全部判断。\n'
        document = catalog.managed_document(old, '# 新索引\n')
        self.assertTrue(document.startswith('---\ntitle: 手工索引\n---\n'))
        self.assertIn('# 自己的阅读记录\n\n保留全部判断。\n', document)
        self.assertLess(document.index('# 新索引'), document.index('# 自己的阅读记录'))
        self.assertEqual(document, catalog.managed_document(document, '# 新索引\n'))

    def test_refresh_preserves_notes_outside_managed_region(self):
        document = '前面的人工笔记\n' + catalog.managed_document('', '# 旧索引\n') + '\n末尾判断\n'
        updated = catalog.managed_document(document, '# 新索引\n')
        self.assertTrue(updated.startswith('前面的人工笔记\n'))
        self.assertTrue(updated.endswith('\n末尾判断\n'))
        self.assertNotIn('# 旧索引', updated)

    def test_manual_edits_or_broken_markers_stop_refresh(self):
        document = catalog.managed_document('', '# 索引\n')
        for changed in (document.replace('# 索引', '# 人工改写'),
                        document.replace(catalog.END, ''), document + catalog.END):
            with self.subTest(changed=changed), self.assertRaises(store.OfflineError):
                catalog.managed_document(changed, '# 新索引\n')

    def test_check_is_read_only_and_explicit_write_is_scoped(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / catalog.TARGET
            path.parent.mkdir()
            path.write_text('# 人工快照\n', encoding='utf-8')
            other = root / 'notes.md'
            other.write_text('独立人工笔记', encoding='utf-8')
            with mock.patch.object(catalog, 'render', return_value='# 已核验索引\n'):
                self.assertFalse(catalog.update(root, check=True))
                self.assertEqual(path.read_text(), '# 人工快照\n')
                self.assertTrue(catalog.update(root, write=True))
                self.assertTrue(catalog.update(root, check=True))
                self.assertFalse(catalog.update(root, write=True))
            self.assertEqual(other.read_text(), '独立人工笔记')

    def test_unaccepted_markdown_is_not_listed_and_broken_acceptance_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            unaccepted = root / 'reports/agent-memory/unaccepted-synthesis.md'
            unaccepted.parent.mkdir(parents=True)
            unaccepted.write_text('看似正式，但没有接受证明。', encoding='utf-8')
            self.assertEqual(catalog.collect(root), ([], []))
            accepted = root / 'reports/agent-memory/admissions/example/accepted.yaml'
            accepted.parent.mkdir(parents=True)
            accepted.write_text('status: accepted\n', encoding='utf-8')
            with self.assertRaises(store.OfflineError):
                catalog.collect(root)

    def test_symlink_index_cannot_replace_another_note(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / 'my-note.md'
            target.write_text('人工内容', encoding='utf-8')
            index = root / catalog.TARGET
            index.parent.mkdir()
            index.symlink_to(target)
            with self.assertRaises(store.OfflineError):
                catalog.update(root, write=True)
            self.assertEqual(target.read_text(), '人工内容')


if __name__ == '__main__':
    unittest.main()
