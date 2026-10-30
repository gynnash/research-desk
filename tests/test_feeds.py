import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scripts'))
from researchdesk_feeds import parse_article, parse_feed
from researchdesk_sources import SourceError


class FeedTests(unittest.TestCase):
    def test_rss_metadata_summary_and_encoded_content_are_distinct(self):
        xml = '''<rss xmlns:content="http://purl.org/rss/1.0/modules/content/"
          xmlns:dc="http://purl.org/dc/elements/1.1/"><channel><title>Official Tech</title>
          <item><title>Agent memory</title><link>https://tech.example/blog/memory?utm_source=rss</link>
          <pubDate>Thu, 29 Oct 2026 12:00:00 GMT</pubDate><dc:creator>Alice</dc:creator>
          <description>&lt;p&gt;Short summary&lt;/p&gt;</description>
          <content:encoded><![CDATA[<article><p>Publisher supplied content only.</p></article>]]></content:encoded>
          </item><item><title>duplicate</title><link>https://tech.example/blog/memory</link></item>
          <item><title>external</title><link>https://other.example/story</link></item></channel></rss>'''
        items = parse_feed(xml, 'https://tech.example/feed/', ['tech.example'])
        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual(item['source_url'], 'https://tech.example/blog/memory')
        self.assertEqual(item['published_at'], '2026-10-29')
        self.assertEqual(item['authors'], ['Alice'])
        self.assertEqual(item['feed_summary'], 'Short summary')
        self.assertEqual(item['feed_content_coverage'], 'publisher_feed_content')
        self.assertEqual(item['feed_content_origin'], 'https://tech.example/feed/')
        self.assertNotIn('body_text', item)
        self.assertNotIn('coverage', item)

    def test_atom_explicit_dates_and_allowlisted_https_upgrade(self):
        xml = '''<feed xmlns="http://www.w3.org/2005/Atom"><title>阮一峰的网络日志</title>
          <entry><title>AI 与记忆</title><link rel="alternate" type="text/html"
          href="http://www.ruanyifeng.com/blog/2026/10/example.html"/>
          <published>2026-10-20T00:00:00Z</published><updated>2026-10-21T01:00:00Z</updated>
          <author><name>阮一峰</name></author><content type="html">&lt;p&gt;Explicit feed body&lt;/p&gt;</content>
          </entry></feed>'''
        item = parse_feed(xml, 'https://www.ruanyifeng.com/blog/atom.xml', ['www.ruanyifeng.com'])[0]
        self.assertTrue(item['source_url'].startswith('https://'))
        self.assertEqual(item['published_at'], '2026-10-20')
        self.assertEqual(item['upstream_updated_at'], '2026-10-21T01:00:00Z')
        self.assertEqual(item['authors'], ['阮一峰'])

    def test_absent_date_is_not_inferred_from_url_or_updated(self):
        rss = '<rss><channel><item><title>Memory</title><link>https://tech.example/2026/10/29/memory</link></item></channel></rss>'
        self.assertIsNone(parse_feed(rss, 'https://tech.example/feed', ['tech.example'])[0]['published_at'])
        atom = '''<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>Memory</title>
          <link href="https://tech.example/entry"/><updated>2026-10-29</updated></entry></feed>'''
        self.assertIsNone(parse_feed(atom, 'https://tech.example/feed', ['tech.example'])[0]['published_at'])

    def test_article_explicit_boundary_excludes_script_navigation(self):
        html = '''<html><head><link rel="canonical" href="/memory/"/>
          <meta property="article:published_time" content="2026-10-29T08:00:00Z"/></head>
          <body><nav>Navigation must not enter the body.</nav><h1>Memory analysis</h1>
          <article><p>This is the actual article explaining memory retrieval and evidence.</p>
          <script>SECRET_SCRIPT</script><nav>INNER_NAV</nav><footer>FOOTER</footer></article></body></html>'''
        result = parse_article(html, 'https://tech.example/memory', 'Official Tech', ['tech.example'])
        self.assertEqual(result['coverage'], 'fulltext')
        self.assertEqual(result['metadata']['source_url'], 'https://tech.example/memory/')
        self.assertEqual(result['metadata']['published_at'], '2026-10-29')
        self.assertNotIn('SECRET_SCRIPT', result['body_text'])
        self.assertNotIn('INNER_NAV', result['body_text'])
        self.assertNotIn('Navigation', result['body_text'])

    def test_official_huggingface_body_survives_related_article_cards(self):
        html = '''<h1>Agent Memory</h1><div class="blog-content prose"><p>Original official
          article body describes how the memory system retrieves saved evidence.</p></div>
          <article>Unrelated model card<time datetime="2024-01-01">Updated</time></article>
          <article>Unrelated collection card</article>'''
        result = parse_article(html, 'https://huggingface.co/blog/memory', 'Hugging Face', ['huggingface.co'])
        self.assertEqual(result['extraction']['boundary'], 'blog-content')
        self.assertNotIn('Unrelated', result['body_text'])
        self.assertIsNone(result['metadata']['published_at'])

    def test_meituan_visible_date_and_article_container(self):
        html = '''<h1>AI 记忆系统</h1><span class="vp-post-date">2026-10-29</span>
          <div class="vp-page-content"><p>这是正式技术博客正文，介绍如何构建可靠的智能体记忆系统，以及需要核实的评测和工程边界。</p></div>'''
        result = parse_article(html, 'https://tech.meituan.com/2026/10/29/memory.html', '美团技术团队', ['tech.meituan.com'])
        self.assertEqual(result['metadata']['published_at'], '2026-10-29')
        self.assertEqual(result['extraction']['boundary'], 'vp-page-content')

    def test_matching_jsonld_body_and_no_javascript_shell_fallback(self):
        html = '''<script type="application/ld+json">{"@type":"BlogPosting",
          "url":"https://tech.example/memory","headline":"Memory research",
          "articleBody":"A sufficiently long explicit article body about useful memory evidence and retrieval.",
          "datePublished":"2026-10-29","author":{"name":"Alice"}}</script>'''
        result = parse_article(html, 'https://tech.example/memory', 'Tech', ['tech.example'])
        self.assertEqual(result['extraction']['boundary'], 'matching_jsonld_articleBody')
        self.assertEqual(result['metadata']['authors'], ['Alice'])
        with self.assertRaises(SourceError):
            parse_article(html.replace('https://tech.example/memory', 'https://tech.example/other'),
                          'https://tech.example/memory', 'Tech', ['tech.example'])
        with self.assertRaises(SourceError):
            parse_article('<h1>Memory</h1><main>Please login to read this page.</main><script>render()</script>',
                          'https://tech.example/memory', 'Tech', ['tech.example'])

    def test_mismatched_or_ambiguous_canonical_rejected(self):
        base = '<h1>Memory</h1><article>A sufficiently long original body about memory and evidence.</article>'
        for canonical in ['<link rel="canonical" href="/different"/>',
                          '<link rel="canonical" href="https://other.example/memory"/>',
                          '<link rel="canonical" href="/memory"/><link rel="canonical" href="/memory"/>']:
            with self.assertRaises(SourceError):
                parse_article(canonical + base, 'https://tech.example/memory', 'Tech', ['tech.example'])

    def test_archive_mode_retains_full_body_and_rejects_over_limit(self):
        body = 'memory evidence ' * 8000
        html = '<h1>Memory</h1><article>' + body + '</article>'
        excerpt = parse_article(html, 'https://tech.example/memory', 'Tech', ['tech.example'])
        full = parse_article(html, 'https://tech.example/memory', 'Tech', ['tech.example'], retain_full=True)
        self.assertEqual(len(excerpt['body_text']), 100_000)
        self.assertEqual(excerpt['coverage'], 'excerpt')
        self.assertEqual(full['body_text'], body.strip())
        self.assertEqual(full['coverage'], 'fulltext')
        with self.assertRaises(SourceError):
            parse_article('<h1>Memory</h1><article>' + 'x' * 500_001 + '</article>',
                          'https://tech.example/memory', 'Tech', ['tech.example'], retain_full=True)

    def test_verified_feed_date_fallback_and_article_date_priority(self):
        html = '<h1>Memory</h1><article>A sufficiently long original body about memory and evidence.</article>'
        evidence = {'published_at': '2026-10-29', 'feed_url': 'https://tech.example/feed.xml',
                    'response_sha256': 'a' * 64}
        result = parse_article(html, 'https://tech.example/memory', 'Tech', ['tech.example'], feed_metadata=evidence)
        self.assertEqual(result['metadata']['published_at'], '2026-10-29')
        self.assertEqual(result['publication_date_basis'], 'publisher_feed')
        self.assertEqual(result['publication_date_evidence'], evidence)
        self.assertNotIn('publication_date_basis', result['metadata'])
        result = parse_article('<meta property="article:published_time" content="2026-10-28"/>' + html,
                               'https://tech.example/memory', 'Tech', ['tech.example'], feed_metadata=evidence)
        self.assertEqual(result['metadata']['published_at'], '2026-10-28')
        self.assertEqual(result['publication_date_basis'], 'article')
        self.assertNotIn('publication_date_evidence', result)
        result = parse_article(html, 'https://tech.example/memory', 'Tech', ['tech.example'],
                               feed_metadata=dict(evidence, published_at=None))
        self.assertIsNone(result['metadata']['published_at'])
        self.assertIsNone(result['publication_date_basis'])
        for changes in [{'response_sha256': 'missing'}, {'feed_url': 'https://other.example/feed'},
                        {'feed_url': 'http://tech.example/feed'}, {'published_at': '2026-02-30'},
                        {'published_at': '2026-10-29T12:00:00Z'}, {'unexpected': 'field'}]:
            with self.assertRaises(SourceError):
                parse_article(html, 'https://tech.example/memory', 'Tech', ['tech.example'],
                              feed_metadata=dict(evidence, **changes))

    def test_structure_entities_bounds_and_bad_dates_fail_closed(self):
        for xml in ['<!DOCTYPE rss [<!ENTITY a "hello">]><rss><channel/></rss>',
                    '<feed>not RSS or Atom</feed>',
                    '<rss><channel><item><title>Memory</title><link>https://tech.example/memory</link><pubDate>tomorrow</pubDate></item></channel></rss>',
                    '<rss><channel>' + '<x>' * 101 + '</x>' * 101 + '</channel></rss>']:
            with self.assertRaises(SourceError):
                parse_feed(xml, 'https://tech.example/feed', ['tech.example'])
        with self.assertRaises(SourceError):
            parse_feed('x' * 2_000_001, 'https://tech.example/feed', ['tech.example'])
        with self.assertRaises(SourceError):
            parse_feed('<rss><channel/></rss>', 'https://127.0.0.1/feed', ['127.0.0.1'])


if __name__ == '__main__':
    unittest.main()
