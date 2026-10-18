"""Offline acceptance tests: all writes stay in temporary repositories.

The checked-in YAML is deliberately fictional. No test needs network, an API
credential, an Obsidian process, or the real research material to be modified.
"""

import copy
import hashlib
from pathlib import Path
import shutil
import socket
import sys
import tempfile
import unittest
from unittest import mock
import uuid

import yaml


REPOSITORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY / "scripts"))
import researchdesk_offline as offline  # noqa: E402


class OfflineResearchAcceptance(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="researchdesk-offline-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        for path in ("config", "sources/papers", "sources/blogs", "reports", "insights", "articles", "workflows/test/agent-memory/fixtures"):
            (self.root / path).mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPOSITORY / "config/research_topics.yaml", self.root / "config/research_topics.yaml")
        self.fixture = yaml.safe_load((REPOSITORY / "workflows/test/agent-memory/fixtures/offline.yaml").read_text(encoding="utf-8"))
        self.fixture_path = self.root / "workflows/test/agent-memory/fixtures/input.yaml"
        self.save_fixture()

    def save_fixture(self):
        self.fixture_path.write_text(yaml.safe_dump(self.fixture, allow_unicode=True, sort_keys=False), encoding="utf-8")

    def single(self, index=0):
        self.fixture["candidates"] = [copy.deepcopy(self.fixture["candidates"][index])]
        self.save_fixture()
        return self.fixture["candidates"][0]

    def run_batch(self, batch="offline-20261020-010000", **kwargs):
        return offline.run(self.root, self.fixture_path, batch, **kwargs)

    def sources(self):
        return sorted(self.root.glob("sources/*/test/*/*.md"))

    def run_dir(self, batch="offline-20261020-010000"):
        return self.root / "reports/test/agent-memory" / batch

    def yaml_file(self, path):
        return yaml.safe_load(path.read_text(encoding="utf-8"))

    def events(self):
        return [self.yaml_file(path) for path in sorted(self.root.glob("reports/test/*/*/events/*.yaml"))]

    def source_metadata(self, path):
        return yaml.safe_load(path.read_text(encoding="utf-8").split("---", 2)[1])

    def snapshot(self, paths):
        return {str(path.relative_to(self.root)): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}

    def formal_note(self, name="human", kind="paper", **overrides):
        stable_id = ("paper-" if kind == "paper" else "blog-") + str(uuid.uuid4())
        metadata = {
            "schema_version": 1, "id": stable_id, "kind": kind,
            "title": "人工笔记（测试仓库）", "source": "人工测试样例",
            "source_url": "https://example.invalid/human/" + name,
            "authors": [], "published_at": None,
            "collected_at": "2026-10-01", "updated_at": "2026-10-02",
            "topics": ["agent-memory"], "status": "reading",
            "related_sources": [], "related_notes": [],
        }
        if kind == "paper":
            metadata.update(arxiv_id=None, doi=None, source_version="v1")
        metadata.update(overrides)
        path = self.root / "sources" / ("papers" if kind == "paper" else "blogs") / (name + ".md")
        path.write_text("---\n" + yaml.safe_dump(metadata, allow_unicode=True, sort_keys=False) + "---\n\n# 人工判断\n\n保留这段批注及阅读状态。\n", encoding="utf-8")
        return path, stable_id

    def assert_blocked(self):
        result = self.run_batch()
        self.assertEqual(result["counts"]["test_accepted"], 0)
        self.assertGreaterEqual(result["counts"]["blocked"], 1)
        self.assertEqual(self.sources(), [])
        return result

    def test_fixed_fixture_pass_revision_and_rejection(self):
        result = self.run_batch()
        self.assertEqual(result["mode"], "offline")
        self.assertEqual(result["counts"]["test_accepted"], 2)
        self.assertEqual(result["counts"]["rejected"], 1)
        self.assertEqual(result["calls"], 8)
        self.assertEqual(result["cost_units"], 16)
        self.assertEqual(len(self.sources()), 2)
        for path in self.sources():
            metadata = self.source_metadata(path)
            self.assertEqual(metadata["status"], "inbox")
            self.assertEqual(uuid.UUID(metadata["id"].split("-", 1)[1]).version, 4)
            self.assertIn("example.invalid", metadata["source_url"])
            self.assertIn("虚构", path.read_text(encoding="utf-8"))
        blog = next(path for path in self.sources() if "/blogs/" in str(path))
        self.assertIsNone(self.source_metadata(blog)["published_at"])
        self.assertEqual(self.source_metadata(blog)["authors"], [])
        self.assertNotIn("显式字段可能降低延迟", blog.read_text(encoding="utf-8"))
        self.assertTrue((self.run_dir() / "manifest.yaml").is_file())

    def test_fixed_fixture_never_connects_to_network(self):
        with mock.patch.object(socket, "create_connection", side_effect=AssertionError("network prohibited")), mock.patch.object(socket.socket, "connect", side_effect=AssertionError("network prohibited")):
            self.assertEqual(self.run_batch()["counts"]["test_accepted"], 2)

    def test_repeat_batch_reuses_results_ids_and_budget(self):
        first = self.run_batch()
        immutable_paths = self.sources() + [self.run_dir() / "manifest.yaml"] + list(self.root.glob("reports/test/*/*/events/*.yaml"))
        before = self.snapshot(immutable_paths)
        second = self.run_batch()
        self.assertEqual(second["calls"], first["calls"])
        self.assertEqual(second["cost_units"], first["cost_units"])
        self.assertEqual([item.get("reserved_id") for item in first["items"]], [item.get("reserved_id") for item in second["items"]])
        self.assertEqual(before, self.snapshot(immutable_paths))

    def test_cross_batch_skips_accepted_and_same_evidence_rejection(self):
        self.run_batch()
        before = self.snapshot(self.sources())
        result = self.run_batch("offline-20261023-010000")
        self.assertEqual(result["calls"], 0)
        self.assertEqual(result["counts"]["test_accepted"], 0)
        self.assertEqual(before, self.snapshot(self.sources()))

    def test_after_review_recovery_keeps_uuid_and_avoids_new_calls(self):
        self.single()
        with self.assertRaises(offline.SimulatedInterruption):
            self.run_batch(fail_after="after_review")
        plan_before = (self.run_dir() / "manifest.yaml").read_bytes()
        plan = self.yaml_file(self.run_dir() / "manifest.yaml")
        reserved = plan["items"][0]["reserved_id"]
        self.assertEqual(uuid.UUID(reserved.split("-", 1)[1]).version, 4)
        self.assertEqual(self.sources(), [])
        result = self.run_batch()
        self.assertEqual(result["calls"], 2)
        self.assertEqual(result["cost_units"], 4)
        self.assertEqual(result["items"][0]["reserved_id"], reserved)
        self.assertEqual(plan_before, (self.run_dir() / "manifest.yaml").read_bytes())
        self.assertEqual(self.source_metadata(self.sources()[0])["id"], reserved)

    def test_unknown_request_keeps_reservation_and_role_limit(self):
        self.single()
        with self.assertRaises(offline.SimulatedInterruption):
            self.run_batch(fail_after="after_reservation")
        result = self.run_batch()
        self.assertEqual(result["calls"], 3)
        self.assertEqual(result["cost_units"], 14)
        self.assertEqual(result["counts"]["test_accepted"], 1)
        repeated = self.run_batch()
        self.assertEqual(repeated["calls"], 3)
        self.assertEqual(repeated["cost_units"], 14)

    def test_budget_exhaustion_cannot_be_reset_by_resume(self):
        self.single()
        self.fixture["budget"]["max_calls"] = 1
        self.save_fixture()
        first = self.run_batch()
        self.assertEqual(first["calls"], 1)
        self.assertEqual(first["counts"]["test_accepted"], 0)
        self.assertEqual(first["counts"]["deferred"], 1)
        second = self.run_batch()
        self.assertEqual(second["calls"], 1)
        self.assertEqual(self.sources(), [])

    def test_monthly_budget_is_shared_across_batches(self):
        candidate = self.single()
        self.fixture["budget"]["month_max_cost_units"] = 20
        candidate["research"][0]["usage"]["cost_units"] = 8
        candidate["reviews"][0]["usage"]["cost_units"] = 8
        self.save_fixture()
        first = self.run_batch()
        self.assertEqual(first["cost_units"], 16)
        self.assertEqual(first["counts"]["test_accepted"], 1)
        candidate["key"] = "another-paper"
        candidate["metadata"]["source_url"] += "-another"
        candidate["metadata"]["doi"] = "10.99999/another-offline-paper"
        self.save_fixture()
        second = self.run_batch("offline-20261023-010000")
        self.assertEqual(second["calls"], 0)
        self.assertEqual(second["counts"]["deferred"], 1)

    def test_same_model_configuration_is_rejected_before_calls(self):
        self.fixture["models"]["review"] = self.fixture["models"]["research"]
        self.save_fixture()
        with self.assertRaises(offline.OfflineError):
            self.run_batch()
        self.assertEqual(self.events(), [])
        self.assertEqual(self.sources(), [])

    def test_actual_reviewer_identity_must_match_configuration(self):
        candidate = self.single()
        candidate["reviews"][0]["model_id"] = self.fixture["models"]["research"]
        self.save_fixture()
        self.assert_blocked()

    def test_pass_with_blocking_issue_is_invalid(self):
        candidate = self.single()
        candidate["reviews"][0]["issues"] = [{"location": "summary", "severity": "blocking", "reason": "unsupported", "suggestion": "remove"}]
        self.save_fixture()
        self.assert_blocked()

    def test_pass_without_claim_checks_is_invalid(self):
        candidate = self.single()
        candidate["reviews"][0]["checks"] = []
        self.save_fixture()
        self.assert_blocked()

    def test_second_revision_is_terminal_and_cannot_publish(self):
        candidate = self.single(1)
        candidate["reviews"][1] = copy.deepcopy(candidate["reviews"][0])
        candidate["reviews"][1]["request_id"] = "mock-second-revise"
        self.save_fixture()
        first = self.run_batch()
        self.assertEqual(first["calls"], 4)
        self.assertEqual(first["counts"]["test_accepted"], 0)
        self.assertEqual(self.sources(), [])
        self.assertEqual(self.run_batch()["calls"], 4)

    def test_reject_and_blocked_decisions_do_not_create_source(self):
        candidate = self.single(2)
        self.assertEqual(self.run_batch()["counts"]["rejected"], 1)
        self.assertEqual(self.sources(), [])
        candidate["key"] = "blocked-item"
        candidate["metadata"]["source_url"] += "-blocked"
        candidate["reviews"][0]["decision"] = "blocked"
        self.save_fixture()
        result = self.run_batch("offline-20261023-010000")
        self.assertEqual(result["counts"]["blocked"], 1)
        self.assertEqual(self.sources(), [])

    def test_unmatched_evidence_excerpt_cannot_publish(self):
        candidate = self.single()
        candidate["evidence"]["locators"][0]["quote"] = "原始文本中根本不存在的引文"
        self.save_fixture()
        try:
            result = self.run_batch()
        except offline.OfflineError:
            pass
        else:
            self.assertEqual(result["counts"]["test_accepted"], 0)
        self.assertEqual(self.sources(), [])

    def test_unknown_evidence_id_cannot_be_approved_by_mock_pass(self):
        candidate = self.single()
        candidate["research"][0]["claims"][0]["evidence_ids"] = ["E-does-not-exist"]
        candidate["reviews"][0]["checks"][0]["evidence_ids"] = ["E-does-not-exist"]
        self.save_fixture()
        self.assert_blocked()

    def test_same_batch_arxiv_abs_pdf_and_version_share_identity(self):
        candidate = self.single()
        candidate["metadata"]["doi"] = None
        candidate["metadata"]["arxiv_id"] = None
        candidate["metadata"]["source_url"] = "https://arxiv.org/abs/2601.00001v1"
        candidate["metadata"]["source_version"] = "v1"
        duplicate = copy.deepcopy(candidate)
        duplicate["key"] = "same-paper-pdf"
        duplicate["metadata"]["source_url"] = "https://arxiv.org/pdf/2601.00001v1.pdf"
        self.fixture["candidates"].append(duplicate)
        self.save_fixture()
        result = self.run_batch()
        self.assertEqual(result["counts"]["test_accepted"], 1)
        self.assertEqual(result["counts"]["duplicate"], 1)
        self.assertEqual(result["calls"], 2)
        self.assertEqual(len(self.sources()), 1)

    def test_new_arxiv_version_creates_update_without_touching_human_note(self):
        path, source_id = self.formal_note(arxiv_id="2310.08560", source_url="https://arxiv.org/abs/2310.08560v2", source_version="v2")
        before = path.read_bytes()
        candidate = self.single()
        candidate["metadata"].update(arxiv_id=None, doi=None, source_url="https://arxiv.org/pdf/2310.08560v9.pdf", source_version="v9")
        self.save_fixture()
        result = self.run_batch()
        self.assertEqual(result["counts"]["update_proposed"], 1)
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(self.sources(), [])
        updates = list(self.run_dir().glob("updates/*.md"))
        self.assertEqual(len(updates), 1)
        self.assertIn(source_id, updates[0].read_text(encoding="utf-8"))

    def test_doi_link_and_case_match_existing_record(self):
        path, _ = self.formal_note(doi="10.99999/offline-memory-example")
        before = path.read_bytes()
        candidate = self.single()
        candidate["metadata"].update(doi=None, source_url="https://doi.org/10.99999/OFFLINE-MEMORY-EXAMPLE")
        self.save_fixture()
        result = self.run_batch()
        self.assertEqual(result["counts"]["duplicate"], 1)
        self.assertEqual(result["calls"], 0)
        self.assertEqual(path.read_bytes(), before)

    def test_canonical_url_strips_tracking_but_keeps_content_query_order(self):
        path, _ = self.formal_note(kind="blog", source_url="https://example.invalid/blog/item?a=1&b=2")
        before = path.read_bytes()
        candidate = self.single(1)
        candidate["research"] = [candidate["research"][1]]
        candidate["reviews"] = [candidate["reviews"][1]]
        candidate["metadata"]["source_url"] = "https://EXAMPLE.invalid:443/blog/item?utm_source=offline&a=1&b=2#part"
        distinct = copy.deepcopy(candidate)
        distinct["key"] = "content-query-order-matters"
        distinct["metadata"]["source_url"] = "https://example.invalid/blog/item?b=2&a=1"
        self.fixture["candidates"].append(distinct)
        self.save_fixture()
        result = self.run_batch()
        self.assertEqual(result["counts"]["duplicate"], 1)
        self.assertEqual(result["counts"]["test_accepted"], 1)
        self.assertEqual(path.read_bytes(), before)

    def test_identity_bridge_between_two_records_is_blocked(self):
        first, _ = self.formal_note(name="one", arxiv_id="2601.00001", doi="10.99999/one")
        second, _ = self.formal_note(name="two", arxiv_id="2601.00002", doi="10.99999/two")
        before = self.snapshot([first, second])
        candidate = self.single()
        candidate["metadata"].update(arxiv_id="2601.00001", doi="10.99999/two")
        self.save_fixture()
        result = self.assert_blocked()
        self.assertEqual(result["calls"], 0)
        self.assertEqual(before, self.snapshot([first, second]))

    def test_human_edit_to_test_source_is_preserved_on_resume(self):
        self.single()
        self.run_batch()
        path = self.sources()[0]
        path.write_text(path.read_text(encoding="utf-8") + "\n人工补充：禁止覆盖。\n", encoding="utf-8")
        before = path.read_bytes()
        with self.assertRaises(offline.OfflineError):
            self.run_batch()
        self.assertEqual(before, path.read_bytes())

    def test_fixture_change_invalidates_saved_review(self):
        self.single()
        with self.assertRaises(offline.SimulatedInterruption):
            self.run_batch(fail_after="after_review")
        self.fixture["candidates"][0]["research"][0]["summary"] = "审阅后偷偷替换的候选"
        self.save_fixture()
        with self.assertRaises(offline.OfflineError):
            self.run_batch()
        self.assertEqual(self.sources(), [])

    def test_human_edit_to_checkpoint_is_preserved_and_blocks_resume(self):
        self.single()
        with self.assertRaises(offline.SimulatedInterruption):
            self.run_batch(fail_after="after_review")
        paths = sorted(self.run_dir().glob("checkpoints/**/research-*.yaml"))
        self.assertTrue(paths)
        path = paths[0]
        path.write_text(path.read_text(encoding="utf-8") + "\n# 人工检查批注，不得覆盖。\n", encoding="utf-8")
        before = path.read_bytes()
        with self.assertRaises(offline.OfflineError):
            self.run_batch()
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(self.sources(), [])

    def test_human_baseline_change_invalidates_unpublished_review(self):
        path, _ = self.formal_note()
        self.single()
        with self.assertRaises(offline.SimulatedInterruption):
            self.run_batch(fail_after="after_review")
        path.write_text(path.read_text(encoding="utf-8") + "\n新的人工结论。\n", encoding="utf-8")
        before = path.read_bytes()
        with self.assertRaises(offline.OfflineError):
            self.run_batch()
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(self.sources(), [])

    def test_batch_and_topic_path_traversal_are_rejected(self):
        with self.assertRaises(offline.OfflineError):
            self.run_batch("../formal-material")
        self.fixture["candidates"][0]["topic"] = "../../articles"
        self.save_fixture()
        with self.assertRaises(offline.OfflineError):
            self.run_batch()
        self.assertEqual(self.sources(), [])
        self.assertEqual(list((self.root / "articles").iterdir()), [])

    def test_symlink_cannot_redirect_test_writes_into_formal_directory(self):
        self.single()
        (self.root / "reports/test").symlink_to(self.root / "articles", target_is_directory=True)
        with self.assertRaises(offline.OfflineError):
            self.run_batch()
        self.assertEqual(list((self.root / "articles").iterdir()), [])
        self.assertEqual(self.sources(), [])

    def test_all_generated_files_stay_inside_topic_test_directories(self):
        before = {path.relative_to(self.root) for path in self.root.rglob("*") if path.is_file()}
        self.run_batch()
        after = {path.relative_to(self.root) for path in self.root.rglob("*") if path.is_file()}
        prefixes = ("sources/papers/test/agent-memory/", "sources/blogs/test/agent-memory/", "reports/test/agent-memory/")
        self.assertTrue(after - before)
        for path in after - before:
            self.assertTrue(str(path).startswith(prefixes), str(path))


if __name__ == "__main__":
    unittest.main()
