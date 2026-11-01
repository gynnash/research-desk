"""Public source parsing and transport safety using fixed HTML/Atom inputs.

The injected transport never contacts real sources or model services.
"""

from email.message import Message
import hashlib
import io
from pathlib import Path
import socket
import sys
import unittest
from unittest import mock
from urllib.error import HTTPError


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
        self.assertEqual(metadata["title"], "Fixture Research")
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


if __name__ == "__main__":
    unittest.main()
