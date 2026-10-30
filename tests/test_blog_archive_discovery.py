"""Official sitemap discovery with fixed transport; no network or model calls."""

import copy
from email.message import Message
import io
from pathlib import Path
import socket
import sys
import tempfile
import unittest
from unittest import mock

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import researchdesk_cycle_discovery as discovery
import researchdesk_sources as sources


NS = 'http://www.sitemaps.org/schemas/sitemap/0.9'


def sitemap(rows):
    return '<urlset xmlns="%s">%s</urlset>' % (NS, ''.join(
        '<url><loc>%s</loc>%s</url>' % (
            url, '<lastmod>%s</lastmod>' % date if date else '') for url, date in rows))


def sitemap_index(urls):
    return '<sitemapindex xmlns="%s">%s</sitemapindex>' % (NS, ''.join(
        '<sitemap><loc>%s</loc></sitemap>' % url for url in urls))


def article(date='2026-10-15'):
    return ('<html><head><meta property="article:published_time" content="%s"></head>'
            '<body><h1>Fixture memory article</h1><article><div class="text-rich-text-v2-blog-post">'
            '<p>This fictional memory fixture contains no measured result or real experiment.</p>'
            '</div></article></body></html>') % date


def feed(urls, dated=True):
    return '<rss version="2.0"><channel><title>Fixture publisher</title>%s</channel></rss>' % ''.join(
        '<item><title>Memory fixture</title><link>%s</link>%s'
        '<description>Feed summary must never be research evidence.</description></item>' % (
            url, '<pubDate>Thu, 15 Oct 2026 00:00:00 GMT</pubDate>' if dated else '') for url in urls)


class Fetcher:
    def __init__(self, responses):
        self.responses, self.calls = responses, []

    def fetch(self, url):
        self.calls.append(url)
        response = self.responses.get(url)
        if response is None:
            raise sources.SourceError('Unconfigured fixture URL')
        if isinstance(response, Exception):
            raise response
        kind, text = response
        return {'url': url, 'content_type': kind, 'text': text}


class BlogArchiveDiscovery(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='researchdesk-blog-archive-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / 'config').mkdir()
        (self.root / 'config/research_topics.yaml').write_text(yaml.safe_dump({
            'topics': {'custom-topic': {'enabled': True, 'keywords': ['memory']}}}))
        self.archive = 'https://www.letta.com/sitemap.xml'
        self.config = {'topic': 'custom-topic', 'window': {'mode': 'rolling', 'days': 60},
            'window_start': '2026-09-01T00:00:00+00:00', 'window_end': '2026-11-01T00:00:00+00:00',
            'discovery': {'max_candidates': 80, 'max_documents': 5, 'max_per_source': 5,
                'evidence_max_chars': 6000, 'sources': [{'id': 'letta', 'adapter': 'letta',
                    'entry_url': 'https://www.letta.com/blog/', 'sitemap_url': self.archive}]}}

    def run_discovery(self, responses, config=None):
        fetcher = Fetcher(responses)
        result = discovery.discover(self.root, config or self.config, 'archive-fixture', fetcher)
        return result, fetcher.calls

    def test_lastmod_prioritizes_but_never_replaces_first_publication(self):
        old = 'https://www.letta.com/blog/old-memory/'
        new = 'https://www.letta.com/blog/new-memory/'
        result, calls = self.run_discovery({
            self.archive: ('application/xml', sitemap([(new, '2024-01-01'), (old, '2026-10-29')])),
            old: ('text/html', article('2024-01-01')), new: ('text/html', article())})
        self.assertEqual(calls, [self.archive, old, new])
        self.assertEqual([item['url'] for item in result['candidates']], [new])
        self.assertEqual(result['deferred'][0]['reason'], 'outside_window')
        self.assertEqual(result['status'], 'complete')
        self.assertTrue(result['source_status'][0]['complete_window'])

    def test_body_cap_is_partial_even_when_recent_dates_look_covered(self):
        urls = ['https://www.letta.com/blog/memory-%s/' % number for number in range(3)]
        self.config['discovery']['max_candidates'] = 2
        responses = {self.archive: ('application/xml', sitemap([
            (urls[0], None), (urls[1], '2026-10-01'), (urls[2], '2026-10-29')]))}
        responses.update({url: ('text/html', article()) for url in urls})
        result, calls = self.run_discovery(responses)
        self.assertEqual(calls, [self.archive, urls[2], urls[1]])
        status = result['source_status'][0]
        self.assertEqual((status['discovered'], status['inspected']), (3, 2))
        self.assertTrue(status['sitemap_index_complete'])
        self.assertFalse(status['complete_window'])
        self.assertEqual(result['status'], 'partial')

    def test_unknown_or_invalid_lastmod_still_checks_article(self):
        url = 'https://www.letta.com/blog/memory/'
        for date in (None, 'not-a-date'):
            with self.subTest(date=date):
                result, calls = self.run_discovery({
                    self.archive: ('application/xml', sitemap([(url, date)])),
                    url: ('text/html', article())})
                self.assertIn(url, calls)
                self.assertEqual(len(result['candidates']), 1)
                self.assertEqual(result['source_status'][0]['sitemap_metadata_errors'], int(date is not None))

    def test_sitemap_index_page_budget_and_external_children_are_honest(self):
        first, second = 'https://www.letta.com/posts-1.xml', 'https://www.letta.com/posts-2.xml'
        url = 'https://www.letta.com/blog/memory/'
        self.config['discovery']['sources'][0]['sitemap_max_pages'] = 2
        result, calls = self.run_discovery({
            self.archive: ('text/xml', sitemap_index([first, second, 'https://outside.invalid/posts.xml'])),
            first: ('application/xml', sitemap([(url, None)])), url: ('text/html', article())})
        self.assertEqual(calls, [self.archive, first, url])
        self.assertFalse(result['source_status'][0]['sitemap_index_complete'])
        self.assertEqual(result['status'], 'partial')
        self.assertTrue(result['source_status'][0]['error_types'])

    def test_failed_child_keeps_other_articles_but_marks_partial(self):
        first, second = 'https://www.letta.com/posts-1.xml', 'https://www.letta.com/posts-2.xml'
        url = 'https://www.letta.com/blog/memory/'
        result, _ = self.run_discovery({
            self.archive: ('application/xml', sitemap_index([first, second])),
            first: ('application/xml', sitemap([(url, None)])),
            second: sources.SourceError('Synthetic outage'), url: ('text/html', article())})
        self.assertEqual(len(result['candidates']), 1)
        self.assertEqual(result['status'], 'partial')
        self.assertFalse(result['source_status'][0]['complete_window'])

    def test_sitemap_rejects_entities_and_html_instead_of_xml(self):
        for text in ('<!DOCTYPE a [<!ENTITY x "fixture">]><urlset/>', '<html>Login required</html>'):
            with self.subTest(text=text):
                result, calls = self.run_discovery({self.archive: ('application/xml', text)})
                self.assertEqual(result['status'], 'failed')
                self.assertEqual(calls, [self.archive])

    def test_langchain_rss_mime_can_contain_sitemap(self):
        config = copy.deepcopy(self.config)
        archive = 'https://www.langchain.com/sitemap.xml'
        url = 'https://www.langchain.com/blog/memory'
        config['discovery']['sources'] = [{'id': 'langchain', 'adapter': 'langchain',
            'entry_url': 'https://www.langchain.com/blog', 'sitemap_url': archive}]
        result, _ = self.run_discovery({archive: ('application/rss+xml', sitemap([(url, None)])),
                                       url: ('text/html', article())}, config)
        self.assertEqual(result['status'], 'complete')
        self.assertEqual(result['candidates'][0]['metadata']['source'], 'LangChain')

    def test_legacy_listing_remains_a_bounded_observation(self):
        self.config['discovery']['sources'][0].pop('sitemap_url')
        url = 'https://www.letta.com/blog/memory/'
        result, calls = self.run_discovery({'https://www.letta.com/blog/': (
            'text/html', '<a href="%s">Memory</a>' % url), url: ('text/html', article())})
        self.assertEqual(calls, ['https://www.letta.com/blog/', url])
        self.assertEqual(result['status'], 'partial')
        self.assertNotIn('sitemap_index_complete', result['source_status'][0])

    def test_fetcher_accepts_official_rss_xml_mime(self):
        class Response(io.BytesIO):
            status = 200
            headers = Message()
            headers['Content-Type'] = 'application/rss+xml; charset=utf-8'

            def geturl(self):
                return 'https://www.langchain.com/sitemap.xml'

        resolver = lambda *args, **kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('8.8.8.8', 443))]
        fetcher = sources.SafeFetcher(opener=lambda request, timeout: Response(sitemap([]).encode()),
                                      resolver=resolver, sleep=lambda _: None)
        self.assertEqual(fetcher.fetch('https://www.langchain.com/sitemap.xml')['content_type'],
                         'application/rss+xml')

    def test_rss_without_feed_date_fetches_article_and_keeps_window_unproven(self):
        entry, url = 'https://www.letta.com/feed.xml', 'https://www.letta.com/blog/memory/'
        self.config['discovery']['sources'] = [{'id': 'custom-feed', 'adapter': 'rss',
            'entry_url': entry, 'publisher': 'Fixture publisher', 'allowed_hosts': ['www.letta.com']}]
        result, calls = self.run_discovery({entry: ('application/rss+xml', feed([url], dated=False)),
                                           url: ('text/html', article())})
        self.assertEqual(calls, [entry, url])
        self.assertEqual(result['status'], 'partial')
        candidate = result['candidates'][0]
        self.assertEqual(candidate['metadata']['published_at'], '2026-10-15')
        self.assertEqual(candidate['source']['publisher'], 'Fixture publisher')
        self.assertEqual(candidate['source']['allowed_hosts'], ['www.letta.com'])
        self.assertNotIn('feed_summary', candidate)
        self.assertFalse(result['source_status'][0]['complete_window'])

    def test_rss_summary_does_not_replace_unavailable_original(self):
        entry, url = 'https://www.letta.com/feed.xml', 'https://www.letta.com/blog/memory/'
        self.config['discovery']['sources'] = [{'id': 'custom-feed', 'adapter': 'rss',
            'entry_url': entry, 'publisher': 'Fixture publisher', 'allowed_hosts': ['www.letta.com']}]
        result, _ = self.run_discovery({entry: ('application/rss+xml', feed([url])),
                                       url: ('text/html', '<html><h1>Login required</h1></html>')})
        self.assertEqual(result['candidates'], [])
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(result['deferred'][0]['reason'], 'article_failed')

    def test_rss_date_binding_falls_back_only_when_article_has_no_date(self):
        entry, url = 'https://www.letta.com/feed.xml', 'https://www.letta.com/blog/memory/'
        self.config['discovery']['sources'] = [{'id': 'custom-feed', 'adapter': 'rss',
            'entry_url': entry, 'publisher': 'Fixture publisher', 'allowed_hosts': ['www.letta.com']}]
        result, _ = self.run_discovery({entry: ('application/rss+xml', feed([url])),
                                       url: ('text/html', article(''))})
        candidate = result['candidates'][0]
        self.assertEqual(candidate['metadata']['published_at'], '2026-10-15')
        binding = candidate['source']['feed_metadata']
        self.assertEqual(binding['published_at'], '2026-10-15')
        self.assertEqual(binding['feed_url'], entry)
        self.assertRegex(binding['response_sha256'], '^[0-9a-f]{64}$')
        old, _ = self.run_discovery({entry: ('application/rss+xml', feed([url])),
                                    url: ('text/html', article('2024-01-01'))})
        self.assertEqual(old['candidates'], [])
        self.assertEqual(old['deferred'][0]['reason'], 'outside_window')

    def test_multiple_rss_sources_balance_and_limit_by_source_id(self):
        entries = ['https://www.letta.com/feed-%s.xml' % number for number in range(2)]
        urls = [['https://www.letta.com/blog/memory-%s-%s/' % (publisher, number)
                 for number in range(2)] for publisher in range(2)]
        self.config['discovery']['max_per_source'] = 1
        self.config['selection'] = {'mode': 'community_attention', 'min_score': 0.1, 'max_requests': 240}
        self.config['discovery']['sources'] = [
            {'id': 'publisher-%s' % number, 'adapter': 'rss', 'entry_url': entry,
             'publisher': 'Publisher %s' % number, 'allowed_hosts': ['www.letta.com']}
            for number, entry in enumerate(entries)]
        responses = {entry: ('application/rss+xml', feed(urls[number]))
                     for number, entry in enumerate(entries)}
        responses.update({url: ('text/html', article()) for group in urls for url in group})
        observed = []

        def rank(items, *args):
            observed.extend(item['source_id'] for item in items)
            return items, {'status': 'complete', 'deferred': []}

        with mock.patch('researchdesk_attention.rank_candidates', side_effect=rank):
            result, _ = self.run_discovery(responses)
        self.assertEqual(observed, ['publisher-0', 'publisher-1', 'publisher-0', 'publisher-1'])
        self.assertEqual([item['source_id'] for item in result['candidates']], ['publisher-0', 'publisher-1'])
        self.assertEqual([item['selected'] for item in result['source_status']], [1, 1])


if __name__ == '__main__':
    unittest.main()
