"""Original-source collection acceptance: fixed transport, no network or model.

Small hand-written HTML/Atom fixtures exercise parser boundaries. Integration
tests run in disposable repositories and never touch production source notes.
"""

from email.message import Message
import hashlib
import io
from pathlib import Path
import shutil
import socket
import sys
import tempfile
import unittest
from unittest import mock
import uuid
from urllib.error import HTTPError

import yaml


REPOSITORY = Path(__file__).resolve().parents[1]
FIXTURES = REPOSITORY / "workflows/test/example-topic/fixtures/collection"
sys.path.insert(0, str(REPOSITORY / "scripts"))
import researchdesk_sources as sources  # noqa: E402


def fixture(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


class SourceParserAcceptance(unittest.TestCase):
    def test_arxiv_keeps_first_publication_and_updated_separate(self):
        records = sources.parse_arxiv_feed(fixture("arxiv.xml"))
        self.assertEqual(len(records), 1)
        record = records[0]
        metadata = record["metadata"]
        self.assertEqual(record["kind"], "paper")
        self.assertEqual(metadata["published_at"], "2026-10-02")
        self.assertTrue(record["upstream_updated_at"].startswith("2026-10-12"))
        self.assertEqual(metadata["arxiv_id"], "2610.01234")
        self.assertEqual(metadata["source_version"], "v2")
        self.assertEqual(metadata["doi"], "10.99999/fixture.memory")
        self.assertEqual(metadata["authors"], ["Fixture Author"])
        self.assertEqual(record["coverage"], "abstract_only")
        self.assertIn("no measured results", record["body_text"])

    def test_arxiv_stable_identity_across_versions(self):
        first = sources.parse_arxiv_feed(fixture("arxiv.xml"))[0]
        second = sources.parse_arxiv_feed(fixture("arxiv.xml").replace("01234v2", "01234v3"))[0]
        self.assertEqual(first["metadata"]["arxiv_id"], second["metadata"]["arxiv_id"])
        self.assertNotEqual(first["metadata"]["source_version"], second["metadata"]["source_version"])

    def test_arxiv_empty_valid_feed_is_not_parse_failure(self):
        self.assertEqual(sources.parse_arxiv_feed('<feed xmlns="http://www.w3.org/2005/Atom"><title>Empty</title></feed>'), [])

    def test_arxiv_rejects_html_instead_of_feed(self):
        with self.assertRaises(sources.SourceError):
            sources.parse_arxiv_feed(fixture("blog-list.html"))

    def test_arxiv_rejects_malformed_xml(self):
        with self.assertRaises(sources.SourceError):
            sources.parse_arxiv_feed("<feed><entry>")

    def test_arxiv_abstract_fallback_keeps_abstract_only_and_version(self):
        record = sources.parse_arxiv_abstract(fixture("arxiv-abstract.html"), "https://arxiv.org/abs/2610.01234v2")
        self.assertEqual(record["kind"], "paper")
        self.assertEqual(record["metadata"]["arxiv_id"], "2610.01234")
        self.assertEqual(record["metadata"]["source_version"], "v2")
        self.assertEqual(record["metadata"]["published_at"], "2026-10-02")
        self.assertEqual(record["coverage"], "abstract_only")
        self.assertIn("no measured results", record["body_text"])
        self.assertNotIn("Subscribe", record["body_text"])

    def test_blog_list_selects_only_same_site_article_links(self):
        urls = sources.parse_blog_list(fixture("blog-list.html"), "https://www.letta.com/blog/", "letta")
        self.assertTrue(any(url.rstrip("/") == "https://www.letta.com/blog/fixture-memory" for url in urls))
        self.assertFalse(any("pricing" in url or "outside.invalid" in url for url in urls))
        self.assertFalse(any(url.rstrip("/") == "https://www.letta.com/blog" for url in urls))

    def test_langchain_new_domain_list(self):
        urls = sources.parse_blog_list(fixture("blog-list.html"), "https://www.langchain.com/blog", "langchain")
        self.assertTrue(any(url.rstrip("/") == "https://www.langchain.com/blog/fixture-memory" for url in urls))
        self.assertFalse(any("outside.invalid" in url for url in urls))

    def test_blog_list_layout_failure_is_not_empty_discovery(self):
        with self.assertRaises(sources.SourceError):
            sources.parse_blog_list("<html><body><h1>Enable JavaScript</h1></body></html>", "https://www.letta.com/blog/", "letta")

    def test_blog_list_preserves_content_query_and_trailing_slash(self):
        html = '<main><a href="/blog/memory/?edition=a">A</a><a href="/blog/memory/?edition=b">B</a></main>'
        urls = sources.parse_blog_list(html, "https://www.letta.com/blog/", "letta")
        self.assertEqual(set(urls), {"https://www.letta.com/blog/memory/?edition=a", "https://www.letta.com/blog/memory/?edition=b"})

    def test_visible_author_wins_over_jsonld_organization(self):
        record = sources.parse_blog_article(fixture("blog-article.html"), "https://www.letta.com/blog/fixture-memory?utm_source=test", "letta")
        metadata = record["metadata"]
        self.assertEqual(metadata["title"], "Fixture Agent Memory")
        self.assertEqual(metadata["authors"], ["Fixture Human Author"])
        self.assertEqual(metadata["published_at"], "2026-10-10")
        self.assertEqual(metadata["source_url"].rstrip("/"), "https://www.letta.com/blog/fixture-memory")
        self.assertNotIn("utm_", metadata["source_url"])
        self.assertTrue(record["upstream_updated_at"].startswith("2026-10-12"))

    def test_article_evidence_excludes_navigation_footer_and_jsonld(self):
        record = sources.parse_blog_article(fixture("blog-article.html"), "https://www.letta.com/blog/fixture-memory", "letta")
        self.assertIn("persistent memory blocks", record["body_text"])
        self.assertNotIn("magical", record["body_text"])
        self.assertNotIn("newsletter", record["body_text"])
        self.assertNotIn("@context", record["body_text"])

    def test_unknown_article_date_and_authors_stay_unknown(self):
        record = sources.parse_blog_article(fixture("blog-unknown-date.html"), "https://www.letta.com/blog/undated", "letta")
        self.assertIsNone(record["metadata"]["published_at"])
        self.assertEqual(record["metadata"]["authors"], [])
        self.assertIsNone(record["upstream_updated_at"])

    def test_article_without_canonical_keeps_content_query(self):
        record = sources.parse_blog_article(fixture("blog-unknown-date.html"), "https://www.letta.com/blog/undated/?edition=a&utm_source=test", "letta")
        self.assertEqual(record["metadata"]["source_url"], "https://www.letta.com/blog/undated/?edition=a")

    def test_declared_canonical_can_normalize_only_trailing_slash(self):
        html = fixture("blog-article.html").replace('href="https://www.letta.com/blog/fixture-memory"', 'href="https://www.letta.com/blog/fixture-memory/"')
        record = sources.parse_blog_article(html, "https://www.letta.com/blog/fixture-memory", "letta")
        self.assertEqual(record["metadata"]["source_url"], "https://www.letta.com/blog/fixture-memory/")

    def test_layout_change_without_article_body_fails(self):
        with self.assertRaises(sources.SourceError):
            sources.parse_blog_article("<html><h1>Just a navigation heading</h1><nav>Agent memory</nav></html>", "https://www.letta.com/blog/layout-changed", "letta")

    def test_external_canonical_url_is_rejected(self):
        html = fixture("blog-article.html").replace("https://www.letta.com/blog/fixture-memory", "https://outside.invalid/stolen")
        with self.assertRaises(sources.SourceError):
            sources.parse_blog_article(html, "https://www.letta.com/blog/fixture-memory", "letta")

    def test_content_hash_ignores_navigation_changes(self):
        original = fixture("blog-article.html")
        revised = original.replace("magical Agent Memory performance", "a changed navigation claim")
        first = sources.parse_blog_article(original, "https://www.letta.com/blog/fixture-memory", "letta")
        second = sources.parse_blog_article(revised, "https://www.letta.com/blog/fixture-memory", "letta")
        self.assertEqual(first["content_hash"], second["content_hash"])

    def test_content_hash_detects_body_change(self):
        original = fixture("blog-article.html")
        revised = original.replace("persistent memory blocks", "revised memory boundaries")
        first = sources.parse_blog_article(original, "https://www.letta.com/blog/fixture-memory", "letta")
        second = sources.parse_blog_article(revised, "https://www.letta.com/blog/fixture-memory", "letta")
        self.assertNotEqual(first["content_hash"], second["content_hash"])

    def test_langchain_article_metadata(self):
        html = fixture("blog-article.html").replace("www.letta.com", "www.langchain.com")
        record = sources.parse_blog_article(html, "https://www.langchain.com/blog/fixture-memory", "langchain")
        self.assertEqual(record["metadata"]["source"], "LangChain")
        self.assertEqual(record["metadata"]["authors"], ["Fixture Human Author"])

    def test_langchain_related_card_author_is_not_article_author(self):
        html = fixture("blog-article.html").replace("www.letta.com", "www.langchain.com")
        html = html.replace('<div class="byline"><a rel="author">Fixture Human Author</a></div>', '<div class="blog-author-wrapper is-blog-post"><span class="author-name">Fixture Human Author</span></div>')
        html = html.replace("</main>", '<aside><div class="blog-author-wrapper"><span class="author-name">Unrelated Card Author</span></div></aside></main>')
        record = sources.parse_blog_article(html, "https://www.langchain.com/blog/fixture-memory", "langchain")
        self.assertEqual(record["metadata"]["authors"], ["Fixture Human Author"])

    def test_allowlist_blocks_unsupported_origins_credentials_and_protocols(self):
        for url in ("https://outside.invalid/blog/memory", "http://www.letta.com/blog/memory", "file:///etc/passwd", "https://user:secret@www.letta.com/blog/memory", "https://www.letta.com.evil.invalid/blog/memory", "https://127.0.0.1/blog/memory"):
            with self.subTest(url=url), self.assertRaises(sources.SourceError):
                sources.validate_url(url)


class FakeResponse(io.BytesIO):
    def __init__(self, payload, content_type="text/html; charset=utf-8", status=200, **headers):
        super().__init__(payload.encode("utf-8") if isinstance(payload, str) else payload)
        self.status = status
        self.headers = Message()
        self.headers["Content-Type"] = content_type
        for key, value in headers.items():
            self.headers[key.replace("_", "-")] = str(value)

    def getcode(self):
        return self.status


class SourceTransportAcceptance(unittest.TestCase):
    def resolver(self, *args, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]

    def fetcher(self, opener, **kwargs):
        return sources.SafeFetcher(opener=opener, resolver=self.resolver, sleep=lambda _: None, arxiv_interval=3, **kwargs)

    def test_transport_records_digest_and_mime_without_network(self):
        body = fixture("blog-article.html")
        def opener(request, timeout):
            return FakeResponse(body)
        with mock.patch.object(socket, "create_connection", side_effect=AssertionError("real network prohibited")):
            result = self.fetcher(opener).fetch("https://www.letta.com/blog/fixture-memory")
        self.assertEqual(result["text"], body)
        self.assertEqual(result["status"], 200)
        self.assertEqual(result["sha256"], hashlib.sha256(body.encode()).hexdigest())
        self.assertIn("text/html", result["content_type"])
        self.assertTrue(result["fetched_at"])

    def test_transport_rejects_oversized_stream_without_content_length(self):
        with self.assertRaises(sources.SourceError):
            self.fetcher(lambda request, timeout: FakeResponse("x" * 65), max_bytes=64).fetch("https://www.letta.com/blog/fixture-memory")

    def test_transport_rejects_oversized_content_length(self):
        with self.assertRaises(sources.SourceError):
            self.fetcher(lambda request, timeout: FakeResponse("x", Content_Length=1000), max_bytes=64).fetch("https://www.letta.com/blog/fixture-memory")

    def test_transport_does_not_retry_forbidden(self):
        calls = []
        def opener(request, timeout):
            calls.append(request.full_url)
            raise HTTPError(request.full_url, 403, "Forbidden", Message(), io.BytesIO())
        with self.assertRaises(sources.SourceError):
            self.fetcher(opener, retries=2).fetch("https://www.letta.com/blog/fixture-memory")
        self.assertEqual(len(calls), 1)

    def test_transport_retries_transient_failure_with_bound(self):
        calls = []
        def opener(request, timeout):
            calls.append(request.full_url)
            raise HTTPError(request.full_url, 503, "Unavailable", Message(), io.BytesIO())
        with self.assertRaises(sources.SourceError):
            self.fetcher(opener, retries=2).fetch("https://www.letta.com/blog/fixture-memory")
        self.assertEqual(len(calls), 3)

    def test_redirect_cannot_escape_source_whitelist(self):
        calls = []
        def opener(request, timeout):
            calls.append(request.full_url)
            headers = Message()
            headers["Location"] = "https://outside.invalid/trap"
            raise HTTPError(request.full_url, 302, "Found", headers, io.BytesIO())
        with self.assertRaises(sources.SourceError):
            self.fetcher(opener).fetch("https://www.letta.com/blog/fixture-memory")
        self.assertEqual(len(calls), 1)

    def test_dns_private_address_never_reaches_transport(self):
        opener = mock.Mock(side_effect=AssertionError("private host must be rejected before request"))
        private_resolver = lambda *args, **kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))]
        fetcher = sources.SafeFetcher(opener=opener, resolver=private_resolver, sleep=lambda _: None, arxiv_interval=3)
        with self.assertRaises(sources.SourceError):
            fetcher.fetch("https://www.letta.com/blog/fixture-memory")
        opener.assert_not_called()

    def test_redirect_loop_has_finite_limit(self):
        calls = []
        def opener(request, timeout):
            calls.append(request.full_url)
            headers = Message()
            headers["Location"] = "/blog/fixture-memory"
            raise HTTPError(request.full_url, 302, "Found", headers, io.BytesIO())
        with self.assertRaises(sources.SourceError):
            self.fetcher(opener).fetch("https://www.letta.com/blog/fixture-memory")
        self.assertLessEqual(len(calls), 8)


class FixedFetcher:
    """Small source-shaped transport; its use cannot contact the real network."""

    def __init__(self, config):
        self.calls = []
        self.responses = {}
        for source in config["sources"]:
            if source["id"] == "arxiv":
                self.responses[source["entry_url"]] = fixture("arxiv.xml")
            else:
                self.responses[source["entry_url"]] = fixture("blog-list.html")
                host = "www.letta.com" if source["id"] == "letta" else "www.langchain.com"
                self.responses["https://" + host + "/blog/fixture-memory"] = fixture("blog-article.html").replace("www.letta.com", host)

    def fetch(self, url):
        self.calls.append(url)
        value = self.responses.get(url)
        if isinstance(value, Exception):
            raise value
        if value is None:
            raise sources.SourceError("Unconfigured fixed transport URL: " + url)
        return {"url": url, "requested_url": url, "status": 200, "redirects": [],
                "content_type": "application/atom+xml" if url.startswith("https://export.arxiv.org/") else "text/html",
                "text": value, "fetched_at": "2026-10-20T01:00:00+00:00",
                "sha256": hashlib.sha256(value.encode()).hexdigest()}


class CollectionIntegrationAcceptance(unittest.TestCase):
    def setUp(self):
        import researchdesk_collect
        self.collector = researchdesk_collect
        self.temporary = tempfile.TemporaryDirectory(prefix="researchdesk-collection-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        for relative in ("config/test/example-topic", "sources/papers", "sources/blogs", "reports", "insights", "articles", "workflows"):
            (self.root / relative).mkdir(parents=True, exist_ok=True)
        for name in ("legacy_sources.yaml",):
            shutil.copyfile(REPOSITORY / "config" / name, self.root / "config" / name)
        (self.root / 'config/research_topics.yaml').write_text(yaml.safe_dump({
            'schema_version': 1, 'topics': {'agent-memory': {
                'name': 'Fictional test topic', 'enabled': True,
                'description': 'Synthetic offline framework input.',
                'scope': ['Synthetic records'], 'keywords': ['fixture', 'memory']}}}))
        self.config = yaml.safe_load((REPOSITORY / "config/test/example-topic/collection.yaml").read_text(encoding="utf-8"))
        self.config['topic'] = 'agent-memory'
        for source in self.config["sources"]:
            source.pop("fallback_urls", None)
            source.pop("seed_urls", None)
        self.config_path = self.root / "config/test/example-topic/collection.yaml"
        self.save_config()
        self.fetcher = FixedFetcher(self.config)

    def save_config(self):
        self.config_path.write_text(yaml.safe_dump(self.config, allow_unicode=True, sort_keys=False), encoding="utf-8")

    def one_blog(self):
        self.config["sources"] = [source for source in self.config["sources"] if source["id"] == "letta"]
        self.save_config()
        self.fetcher = FixedFetcher(self.config)

    def run_batch(self, batch="collection-fixed-first"):
        with mock.patch.object(socket, "create_connection", side_effect=AssertionError("network prohibited")), mock.patch.object(socket.socket, "connect", side_effect=AssertionError("network prohibited")):
            return self.collector.collect(self.root, self.config_path, batch, fetcher=self.fetcher)

    def notes(self):
        return sorted(self.root.glob("sources/*/test/*/*.md"))

    def snapshot(self, paths):
        return {str(path.relative_to(self.root)): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}

    def test_collects_three_sources_with_mock_analysis_only_in_test(self):
        result = self.run_batch()
        self.assertEqual(result["status"], "complete")
        self.assertEqual(len(result["records"]), 3)
        self.assertEqual(result["changes"]["new"], 3)
        self.assertEqual(result["analysis"]["counts"]["test_accepted"], 3)
        self.assertEqual(len(self.notes()), 3)
        for path in self.notes():
            text = path.read_text(encoding="utf-8")
            self.assertIn("TEST", text)
            self.assertTrue("模拟" in text or "mock" in text)
        self.assertEqual(list(self.root.glob("sources/papers/*.md")), [])
        self.assertEqual(list(self.root.glob("sources/blogs/*.md")), [])
        self.assertEqual(list(self.root.glob(".github/workflows/*")), [])

    def test_same_batch_resume_does_not_refetch_or_recall(self):
        first = self.run_batch()
        calls = list(self.fetcher.calls)
        notes = self.snapshot(self.notes())
        second = self.run_batch()
        self.assertEqual(self.fetcher.calls, calls)
        self.assertEqual(first["analysis"]["calls"], second["analysis"]["calls"])
        self.assertEqual(notes, self.snapshot(self.notes()))

    def test_new_batch_unchanged_evidence_is_not_new_research(self):
        self.run_batch()
        notes = self.snapshot(self.notes())
        result = self.run_batch("collection-fixed-second")
        self.assertEqual(result["changes"]["unchanged"], 3)
        self.assertEqual(result["changes"]["new"], 0)
        self.assertEqual((result["analysis"] or {}).get("calls", 0), 0)
        self.assertEqual(notes, self.snapshot(self.notes()))

    def test_content_update_creates_suggestion_preserving_previous_note(self):
        self.one_blog()
        self.run_batch()
        notes = self.snapshot(self.notes())
        url = "https://www.letta.com/blog/fixture-memory"
        self.fetcher.responses[url] = self.fetcher.responses[url].replace("persistent memory blocks", "revised memory boundaries")
        result = self.run_batch("collection-fixed-update")
        self.assertEqual(result["changes"]["updated"], 1)
        self.assertEqual(notes, self.snapshot(self.notes()))
        self.assertEqual(len(self.notes()), 1)
        self.assertTrue(list(self.root.glob("reports/test/agent-memory/**/updates/*.md")))

    def test_article_date_change_is_update_even_when_body_unchanged(self):
        self.one_blog()
        self.run_batch()
        url = "https://www.letta.com/blog/fixture-memory"
        self.fetcher.responses[url] = self.fetcher.responses[url].replace('"dateModified":"2026-10-12"', '"dateModified":"2026-10-15"')
        result = self.run_batch("collection-fixed-date-update")
        self.assertEqual(result["changes"]["updated"], 1)

    def test_individual_source_failure_is_partial_with_error(self):
        entry = next(source["entry_url"] for source in self.config["sources"] if source["id"] == "letta")
        self.fetcher.responses[entry] = sources.SourceError("HTTP 403 fixture")
        result = self.run_batch()
        self.assertEqual(result["status"], "partial")
        self.assertEqual(len(result["records"]), 2)
        letta = next(source for source in result["sources"] if source["id"] == "letta")
        self.assertIn("403", letta.get("error", ""))

    def test_all_sources_failure_is_failed_not_zero_new_success(self):
        for source in self.config["sources"]:
            self.fetcher.responses[source["entry_url"]] = sources.SourceError("offline source failure")
        result = self.run_batch()
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["records"], [])
        self.assertEqual(self.notes(), [])

    def test_same_batch_retries_only_failed_source(self):
        entry = next(source["entry_url"] for source in self.config["sources"] if source["id"] == "letta")
        expected = self.fetcher.responses[entry]
        self.fetcher.responses[entry] = sources.SourceError("temporary fixture failure")
        first = self.run_batch()
        self.assertEqual(first["status"], "partial")
        first_calls = len(self.fetcher.calls)
        previous_notes = self.snapshot(self.notes())
        self.fetcher.responses[entry] = expected
        second = self.run_batch()
        self.assertEqual(second["status"], "complete")
        retried = self.fetcher.calls[first_calls:]
        self.assertTrue(retried)
        self.assertTrue(all("letta.com" in url for url in retried))
        for relative, digest in previous_notes.items():
            self.assertEqual(hashlib.sha256((self.root / relative).read_bytes()).hexdigest(), digest)
        self.assertEqual(len(self.notes()), 3)

    def test_collection_checkpoint_resumes_without_refetch_after_interruption(self):
        with self.assertRaises(self.collector.offline.SimulatedInterruption):
            self.collector.collect(self.root, self.config_path, "collection-fixed-first", fetcher=self.fetcher, fail_after="after_collection")
        previous_calls = list(self.fetcher.calls)
        result = self.run_batch()
        self.assertEqual(result["status"], "complete")
        self.assertEqual(self.fetcher.calls, previous_calls)
        self.assertEqual(len(self.notes()), 3)

    def test_existing_formal_note_is_never_overwritten(self):
        self.one_blog()
        metadata = {"schema_version": 1, "id": "blog-" + str(uuid.uuid4()), "kind": "blog",
                    "title": "人工阅读笔记", "source": "Letta", "source_url": "https://www.letta.com/blog/fixture-memory",
                    "authors": [], "published_at": None, "collected_at": "2026-10-01", "updated_at": "2026-10-02",
                    "topics": ["agent-memory"], "status": "reading", "related_sources": [], "related_notes": []}
        path = self.root / "sources/blogs/human-note.md"
        path.write_text("---\n" + yaml.safe_dump(metadata, allow_unicode=True) + "---\n\n# 人工批注\n\n保留我的判断。\n", encoding="utf-8")
        previous = path.read_bytes()
        result = self.run_batch()
        self.assertEqual(path.read_bytes(), previous)
        self.assertEqual(result["changes"]["new"], 0)
        self.assertEqual(self.notes(), [])

    def test_modified_collection_checkpoint_is_preserved_and_stops_resume(self):
        result = self.run_batch()
        path = self.root / result["checkpoint_paths"][0]
        path.write_text(path.read_text(encoding="utf-8") + "\n# human annotation\n", encoding="utf-8")
        previous = path.read_bytes()
        calls = list(self.fetcher.calls)
        with self.assertRaises(self.collector.offline.OfflineError):
            self.run_batch()
        self.assertEqual(path.read_bytes(), previous)
        self.assertEqual(self.fetcher.calls, calls)

    def test_modified_chatgpt_bundle_is_preserved_and_stops_resume(self):
        result = self.run_batch()
        path = self.root / result["artifacts"]["bundle"]
        path.write_text(path.read_text(encoding="utf-8") + "\n# human annotation\n", encoding="utf-8")
        previous = path.read_bytes()
        with self.assertRaises(self.collector.offline.OfflineError):
            self.run_batch()
        self.assertEqual(path.read_bytes(), previous)

    def test_conflicting_existing_identities_are_partial_and_never_accepted(self):
        self.one_blog()
        for name in ("first", "second"):
            metadata = {"schema_version": 1, "id": "blog-" + str(uuid.uuid4()), "kind": "blog",
                        "title": "Identity conflict fixture " + name, "source": "Letta",
                        "source_url": "https://www.letta.com/blog/fixture-memory", "authors": [], "published_at": None,
                        "collected_at": "2026-10-01", "updated_at": "2026-10-01", "topics": ["agent-memory"],
                        "status": "reading", "related_sources": [], "related_notes": []}
            path = self.root / "sources/blogs" / (name + ".md")
            path.write_text("---\n" + yaml.safe_dump(metadata) + "---\n\nHuman notes\n", encoding="utf-8")
        existing = self.snapshot(list(self.root.glob("sources/blogs/*.md")))
        result = self.run_batch()
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["changes"]["blocked"], 1)
        self.assertEqual(self.notes(), [])
        self.assertEqual(existing, self.snapshot(list(self.root.glob("sources/blogs/*.md"))))

    def assert_missing_analysis_checkpoint_stops_resume(self, relative):
        self.one_blog()
        result = self.run_batch()
        directory = self.root / "reports/test/agent-memory" / result["analysis_batch"]
        path = directory / relative
        self.assertTrue(path.exists())
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
        remaining = self.snapshot([item for item in self.root.rglob("*") if item.is_file()])
        calls = list(self.fetcher.calls)
        with self.assertRaises(self.collector.offline.OfflineError):
            self.run_batch()
        self.assertEqual(calls, self.fetcher.calls)
        self.assertEqual(remaining, self.snapshot([item for item in self.root.rglob("*") if item.is_file()]))

    def test_deleted_analysis_event_directory_cannot_reuse_complete_receipt(self):
        self.assert_missing_analysis_checkpoint_stops_resume("events")

    def test_deleted_analysis_manifest_cannot_reuse_complete_receipt(self):
        self.assert_missing_analysis_checkpoint_stops_resume("manifest.yaml")

    def test_deleted_analysis_summary_cannot_reuse_complete_receipt(self):
        self.assert_missing_analysis_checkpoint_stops_resume("summary-attempt-1.yaml")


if __name__ == "__main__":
    unittest.main()
