#!/usr/bin/env python3
"""Regression checks for test/formal source isolation; all writes use temp copies."""

from contextlib import redirect_stderr, redirect_stdout
import copy
import importlib.util
from io import StringIO
from pathlib import Path
import shutil
import tempfile
import unittest

import yaml


REPOSITORY = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location("researchdesk_validator", REPOSITORY / "workflows/validate.py")
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)
FIRST_ID = "paper-6a45d199-3ed7-44ce-908d-0b264bb8dd9a"
SECOND_ID = "paper-a179342a-4edb-4aaa-a6f8-559d66c8d326"
BANNER = "> TEST：离线虚构样例，不可作为正式研究证据。"


class IsolationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="researchdesk-validator-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        for directory in ("config", "sources", "reports", "insights", "articles", "workflows"):
            shutil.copytree(REPOSITORY / directory, self.root / directory, ignore=shutil.ignore_patterns("test", "__pycache__"))
        for filename in ("README.md", ".gitignore"):
            shutil.copyfile(REPOSITORY / filename, self.root / filename)
        self.formal_path = next(path for path in (self.root / "sources/papers").rglob("paper-*.md"))
        self.formal_count = sum(path.read_text(encoding="utf-8").startswith("---\n") for folder in ("papers", "blogs") for path in (self.root / "sources" / folder).rglob("*.md"))
        self.formal = yaml.safe_load(self.formal_path.read_text(encoding="utf-8").split("---", 2)[1])
        self.data = copy.deepcopy(self.formal)
        self.data.update({"id": FIRST_ID, "title": "Fictional offline validation source", "source": "Offline fixture", "source_url": "https://example.invalid/researchdesk/fixture", "authors": [], "topics": ["agent-memory"], "status": "inbox", "related_sources": [], "related_notes": [], "arxiv_id": None, "doi": None, "source_version": None})

    def write_record(self, data=None, topic="agent-memory", body=BANNER, path=None):
        data = copy.deepcopy(data if data is not None else self.data)
        target = path or self.root / "sources/papers/test" / topic / f"{data['id']}.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("---\n" + yaml.safe_dump(data, allow_unicode=True, sort_keys=False) + "---\n\n" + body + "\n", encoding="utf-8")
        return target

    def check(self, include_test=False, expected=0):
        output = StringIO()
        with redirect_stdout(output), redirect_stderr(output):
            result = VALIDATOR.check(self.root, include_test=include_test)
        self.assertEqual(result, expected, output.getvalue())
        return output.getvalue()

    def test_test_records_are_counted_separately(self):
        self.write_record()
        self.assertIn(f"{self.formal_count} 条正式资料", self.check())
        self.assertIn("1 条测试资料", self.check(include_test=True))

    def test_source_identity_indexes_are_separate(self):
        self.data["source_url"] = self.formal["source_url"]
        self.data["arxiv_id"] = self.formal.get("arxiv_id")
        self.write_record()
        self.check(include_test=True)

    def test_malformed_test_path_fails_even_when_excluded(self):
        self.write_record(path=self.root / "sources/papers/test" / f"{FIRST_ID}.md")
        self.check(expected=1)
        self.check(include_test=True, expected=1)

    def test_unknown_topic_fails_even_when_excluded(self):
        self.write_record(topic="unknown-topic")
        self.check(expected=1)

    def test_filename_test_md_does_not_exempt_a_new_formal_source(self):
        target = self.root / "sources/papers/agent-memory/test.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("invalid formal source\n", encoding="utf-8")
        self.check(expected=1)

    def test_missing_banner_is_rejected_when_tests_are_included(self):
        self.write_record(body="No test provenance banner")
        self.check()
        self.check(include_test=True, expected=1)

    def test_invalid_test_schema_is_not_a_legacy_exemption(self):
        del self.data["source_url"]
        self.write_record()
        self.check()
        self.check(include_test=True, expected=1)

    def test_test_source_cannot_reference_formal_source(self):
        self.data["related_sources"] = [self.formal["id"]]
        self.write_record()
        self.check(include_test=True, expected=1)

    def test_formal_source_cannot_reference_test_source(self):
        self.write_record()
        self.formal["related_sources"] = [FIRST_ID]
        self.write_record(self.formal, path=self.formal_path)
        self.check(expected=1)
        self.check(include_test=True, expected=1)

    def test_formal_source_cannot_reference_test_note(self):
        note = self.root / "reports/test/agent-memory/fixture.md"
        note.parent.mkdir(parents=True)
        note.write_text(BANNER + "\n", encoding="utf-8")
        self.formal["related_notes"] = [note.relative_to(self.root).as_posix()]
        self.write_record(self.formal, path=self.formal_path)
        self.check(expected=1)

    def test_test_note_must_match_source_topic(self):
        note = self.root / "reports/test/agent-rl/fixture.md"
        note.parent.mkdir(parents=True)
        note.write_text(BANNER + "\n", encoding="utf-8")
        self.data["related_notes"] = [note.relative_to(self.root).as_posix()]
        self.write_record()
        self.check(include_test=True, expected=1)

    def test_config_test_yaml_is_still_parsed(self):
        config = self.root / "config/test/example-topic/invalid.yaml"
        config.parent.mkdir(parents=True)
        config.write_text("same_key: 1\nsame_key: 2\n", encoding="utf-8")
        self.check(expected=1)
        self.check(include_test=True, expected=1)

    def test_duplicate_sources_inside_test_space_are_rejected(self):
        self.write_record()
        self.data["id"] = SECOND_ID
        self.write_record()
        self.check(include_test=True, expected=1)

    def test_test_record_cannot_be_added_to_legacy_exemptions(self):
        record = self.write_record()
        legacy_path = self.root / "config/legacy_sources.yaml"
        legacy = yaml.safe_load(legacy_path.read_text(encoding="utf-8"))
        legacy["files"].append({"path": record.relative_to(self.root).as_posix(), "reason": "Attempted test exemption"})
        legacy_path.write_text(yaml.safe_dump(legacy, sort_keys=False), encoding="utf-8")
        self.check(expected=1)
        self.check(include_test=True, expected=1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
