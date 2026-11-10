"""Public attention uses fixed JSON, never a model, account or live network."""

from datetime import datetime, timezone
from email.message import Message
import hashlib
import io
import json
from pathlib import Path
import socket
import sys
import unittest
from urllib.parse import parse_qs, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import attention
import sources


START, END = '2026-09-01T00:00:00Z', '2026-11-01T00:00:00Z'
POLICY = {'mode': 'community_attention', 'min_score': 0.1, 'max_requests': 120}
STAMP = int(datetime(2026, 10, 16, tzinfo=timezone.utc).timestamp())


def item(identifier='2610.01234', kind='paper'):
    return {'kind': kind, 'metadata': {'arxiv_id': identifier,
            'source_url': 'https://arxiv.org/abs/' + identifier,
            'published_at': '2026-10-15'}} if kind == 'paper' else {
                'kind': kind, 'metadata': {'source_url': 'https://www.letta.com/blog/memory',
                                         'published_at': '2026-10-15'}}


def story(url, points=20, comments=3, identifier='123', timestamp=STAMP):
    return {'url': url, 'points': points, 'num_comments': comments,
            'objectID': identifier, 'created_at_i': timestamp}


class FixedFetcher:
    def __init__(self, hf=None, hn=None):
        self.hf, self.hn, self.calls = hf, hn, []

    def fetch_json(self, url):
        self.calls.append(url)
        value = self.hf if 'huggingface.co' in url else self.hn
        if callable(value):
            value = value(url)
        if isinstance(value, Exception):
            raise value
        raw = json.dumps(value).encode()
        return {'json': value, 'sha256': hashlib.sha256(raw).hexdigest(),
                'fetched_at': '2026-10-30T00:00:00Z'}


class AttentionAcceptance(unittest.TestCase):
    def test_true_metrics_rank_globally_and_keep_missing_unknown(self):
        def hf(url):
            identifier = url.rsplit('/', 1)[-1]
            return {'id': identifier, 'upvotes': 2 if identifier.endswith('4') else 50}
        fetcher = FixedFetcher(hf, {'hits': []})
        ranked, summary = attention.rank_candidates([item(), item('2610.01235')], fetcher, POLICY, START, END)
        self.assertEqual(ranked[0]['metadata']['arxiv_id'], '2610.01235')
        evidence = ranked[0]['attention']
        self.assertEqual(evidence['status'], 'partial')
        self.assertIsNone(evidence['providers'][0]['metrics']['comments'])
        self.assertEqual(evidence['providers'][0]['observed_at'], '2026-10-30T00:00:00Z')
        self.assertEqual(len(evidence['providers'][0]['response_sha256']), 64)
        self.assertEqual(summary['requests_used'], 4)

    def test_hn_exact_identity_window_and_duplicate_story_boundaries(self):
        same = story('https://arxiv.org/pdf/2610.01234v2.pdf?utm_source=hn')
        payload = {'hits': [same, same, story('https://arxiv.org/abs/2610.99999', points=10000),
                           story('https://arxiv.org/abs/2610.01234', points=10000, identifier='124', timestamp=1)],
                   'nbHits': 20}
        ranked, _ = attention.rank_candidates([item()], FixedFetcher(
            sources.SourceError('Public source HTTP 404'), payload), POLICY, START, END)
        hn = ranked[0]['attention']['providers'][1]
        self.assertEqual(hn['metrics'], {'points': 20, 'comments': 3, 'matching_stories': 1})
        self.assertFalse(hn['search_complete'])
        query = parse_qs(urlsplit(hn['request_url']).query)
        self.assertEqual(query['restrictSearchableAttributes'], ['url'])
        self.assertIn('created_at_i>=', query['numericFilters'][0])

    def test_unavailable_and_wrong_paper_identity_are_unknown_not_zero(self):
        for hf in (sources.SourceError('Public source HTTP 404'), {'id': '2610.99999', 'upvotes': 999},
                   {'id': '2610.01234'}):
            with self.subTest(hf=hf):
                ranked, summary = attention.rank_candidates([item()], FixedFetcher(hf, {}), POLICY, START, END)
                self.assertEqual(ranked, [])
                deferred = summary['deferred'][0]
                self.assertEqual(deferred['reason'], 'attention_unknown')
                self.assertIsNone(deferred['attention']['community_attention_score'])

    def test_valid_empty_search_is_below_minimum_not_global_zero_claim(self):
        ranked, summary = attention.rank_candidates([item(kind='blog')], FixedFetcher(hn={'hits': []}),
                                                     POLICY, START, END)
        self.assertEqual(ranked, [])
        deferred = summary['deferred'][0]
        self.assertEqual(deferred['reason'], 'attention_below_minimum')
        self.assertEqual(deferred['attention']['providers'][0]['status'], 'no_matching_story')
        self.assertIn('not zero global attention', deferred['attention']['providers'][0]['limitation'])

    def test_budget_does_not_fall_back_to_date_or_invent_scores(self):
        fetcher = FixedFetcher({'id': '2610.01234', 'upvotes': 1}, {'hits': []})
        ranked, summary = attention.rank_candidates([item(), item('2610.01235')], fetcher,
            dict(POLICY, max_requests=1), START, END)
        self.assertEqual(len(fetcher.calls), 1)
        self.assertEqual(len(ranked), 1)
        self.assertEqual(summary['deferred'][0]['reason'], 'attention_unknown')
        self.assertTrue(all(p['reason'] == 'request_budget_exhausted'
                            for p in summary['deferred'][0]['attention']['providers']))

    def test_old_publication_is_not_rescued_by_new_upstream_timestamp(self):
        old = item()
        old['metadata']['published_at'] = '2024-01-01'
        old['upstream_updated_at'] = '2026-10-30'
        fetcher = FixedFetcher()
        ranked, summary = attention.rank_candidates([old], fetcher, POLICY, START, END)
        self.assertEqual(ranked, [])
        self.assertEqual(fetcher.calls, [])
        self.assertEqual(summary['deferred'][0]['reason'], 'outside_attention_window')


class JSONFetchAcceptance(unittest.TestCase):
    def fetcher(self, raw=b'{"hits": []}', content_type='application/json', host='93.184.216.34', limit=1000):
        self.requests = []
        def transport(request, timeout):
            self.requests.append(request)
            response = io.BytesIO(raw)
            response.status = 200
            response.headers = Message()
            response.headers['Content-Type'] = content_type
            response.geturl = lambda: request.full_url
            return response
        return sources.SafeFetcher(opener=transport, max_bytes=limit, retries=0,
            resolver=lambda *args, **kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, '', (host, 443))])

    def test_json_is_explicit_opt_in_and_retains_network_size_guards(self):
        url = 'https://hn.algolia.com/api/v1/search?query=memory'
        fetcher = self.fetcher()
        self.assertEqual(fetcher.fetch_json(url)['json'], {'hits': []})
        self.assertEqual(self.requests[0].get_header('Accept'), 'application/json')
        with self.assertRaises(sources.SourceError):
            fetcher.fetch(url)
        with self.assertRaises(sources.SourceError):
            self.fetcher(host='127.0.0.1').fetch_json(url)
        with self.assertRaises(sources.SourceError):
            self.fetcher(limit=3).fetch_json(url)

    def test_invalid_or_ambiguous_json_and_html_are_rejected(self):
        for raw in (b'{"votes":1,"votes":9}', b'{"votes":NaN}', b'not-json'):
            with self.subTest(raw=raw), self.assertRaises(sources.SourceError):
                self.fetcher(raw).fetch_json('https://huggingface.co/api/papers/2610.01234')
        with self.assertRaises(sources.SourceError):
            self.fetcher(b'<html>Login</html>', 'text/html').fetch_json(
                'https://huggingface.co/api/papers/2610.01234')


if __name__ == '__main__':
    unittest.main()
