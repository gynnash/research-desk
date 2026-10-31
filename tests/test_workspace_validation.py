"""Validate new reading directories using fictional collection/model fixtures."""

from contextlib import redirect_stderr, redirect_stdout
import io
from pathlib import Path
import shutil
import unittest

import yaml

import test_research_entry as fixtures
from workflows import validate


REPOSITORY = Path(__file__).resolve().parents[1]


class WorkspaceValidation(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.ResearchEntry('test_collection_to_detailed_reviewed_summaries_and_idempotent_resume')
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root = self.fixture.root
        for relative in ('README.md', '.gitignore', 'workflows/README.md',
                         'workflows/source-schema.md', 'workflows/maintenance.md',
                         'workflows/requirements.txt', 'workflows/templates/paper.md',
                         'workflows/templates/blog.md'):
            target = self.root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(REPOSITORY / relative, target)
        self.collection = self.fixture.collect()
        self.result = self.fixture.run_research()
        self.assertEqual(self.result['status'], 'complete')
        self.calls = len(self.fixture.client.calls)

    def check(self):
        output, errors = io.StringIO(), io.StringIO()
        with redirect_stdout(output), redirect_stderr(errors):
            status = validate.check(self.root, include_test=True)
        self.assertEqual(len(self.fixture.client.calls), self.calls)
        self.fixture.member.assert_not_called()
        return status, output.getvalue(), errors.getvalue()

    def test_valid_reviewed_workspace_counts_only_real_layout_and_skips_readmes(self):
        (self.root / 'collection/README.md').write_text('# 采集入口\n')
        (self.root / 'summary/README.md').write_text('# 逐篇总结入口\n')
        status, output, errors = self.check()
        self.assertEqual(status, 0, errors)
        self.assertIn('2 篇采集原文，2 篇逐篇总结', output)
        self.assertEqual(errors, '')

    def test_changed_original_summary_or_index_fails_without_calls(self):
        relatives = [self.collection['records'][0]['original_markdown_path'],
                     self.result['summary_paths'][0], self.collection['collection_manifest_path']]
        for relative in relatives:
            with self.subTest(relative=relative):
                target = self.root / relative
                before = target.read_bytes()
                target.write_bytes(before + '\n人工修改，必须保留。\n'.encode())
                modified = target.read_bytes()
                try:
                    status, _, errors = self.check()
                    self.assertEqual(status, 1)
                    self.assertTrue(errors)
                    self.assertEqual(target.read_bytes(), modified)
                finally:
                    target.write_bytes(before)

    def test_invalid_summary_scope_models_and_symlink_fail(self):
        target = self.root / self.result['summary_paths'][0]
        before = target.read_text()
        metadata, body = before.split('---', 2)[1:]
        data = yaml.safe_load(metadata)
        changes = ({'collection_original': '../../outside.md'},
                   {'review_model': data['research_model']}, {'review_status': 'rejected'})
        for change in changes:
            with self.subTest(change=change):
                target.write_text('---\n' + yaml.safe_dump(dict(data, **change), allow_unicode=True,
                                                          sort_keys=False) + '---' + body)
                try:
                    self.assertEqual(self.check()[0], 1)
                finally:
                    target.write_text(before)
        original = self.root / self.collection['records'][0]['original_markdown_path']
        payload = original.read_bytes()
        alternate = self.root / 'outside.md'
        alternate.write_bytes(payload)
        original.unlink()
        original.symlink_to(alternate)
        try:
            status, _, errors = self.check()
            self.assertEqual(status, 1)
            self.assertIn('符号链接', errors)
        finally:
            original.unlink()
            original.write_bytes(payload)


if __name__ == '__main__':
    unittest.main()
