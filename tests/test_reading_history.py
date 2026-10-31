"""Reading copies do not become independent historical research evidence."""

from pathlib import Path
import sys
import tempfile
import unittest

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import researchdesk_cycle_discovery as discovery


class ReadingHistory(unittest.TestCase):
    def test_reading_copies_are_skipped_while_human_notes_remain(self):
        with tempfile.TemporaryDirectory(prefix='researchdesk-reading-history-') as directory:
            root = Path(directory)

            def write(relative, metadata, body):
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('---\n' + yaml.safe_dump(metadata) + '---\n\n' + body,
                                encoding='utf-8')
                return relative

            (root / 'config').mkdir()
            (root / 'config/research_topics.yaml').write_text(yaml.safe_dump({
                'topics': {'memory': {'name': 'Memory', 'enabled': True}}}), encoding='utf-8')
            identifier = 'blog-00000000-0000-4000-8000-000000000001'
            source = write('sources/blogs/memory/' + identifier + '.md', {
                'id': identifier, 'kind': 'blog', 'topics': ['memory'],
                'source_url': 'https://example.org/memory', 'collected_at': '2026-10-01',
                'published_at': '2026-09-01'}, '# Original\n')
            metadata = {'topics': ['memory'], 'collected_at': '2026-10-01'}
            manual = write('insights/memory/manual.md', dict(metadata, kind='human_note'),
                           '# My observations\n' + identifier)
            copies = {
                write(folder + '/memory/readable.md', dict(metadata, kind='reading_note',
                    origin=[manual]), '# Reading copy\n' + identifier)
                for folder in ('reports', 'insights')
            }

            for options in ({}, {'lookback_days': 180, 'as_of': '2026-10-31T01:00:00Z'}):
                with self.subTest(options=options):
                    selected = discovery.select_history(root, 'memory', 6, **options)
                    paths = {item['path'] for item in selected}
                    self.assertEqual(paths, {source, manual})
                    self.assertTrue(paths.isdisjoint(copies))
                    self.assertTrue(all(item['origin'] == 'human_baseline' for item in selected))


if __name__ == '__main__':
    unittest.main()
