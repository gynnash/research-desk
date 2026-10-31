"""Rolling discovery boundaries and frozen selection, without network/models."""

import copy
from datetime import datetime, timedelta
from pathlib import Path
import sys
import unittest
from unittest import mock
from urllib.parse import parse_qs, urlsplit

import yaml

import test_cycle as fixtures

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import researchdesk_cycle_discovery as discovery
import researchdesk_offline as store
from researchdesk_sources import SourceError


REAL_DISCOVER = discovery.discover
START, END = '2026-09-01T00:00:00+00:00', '2026-11-01T00:00:00+00:00'


def paper(identifier, date='2026-10-15', version='v2', score=1):
    metadata = {'arxiv_id': identifier, 'source_url': 'https://arxiv.org/abs/' + identifier,
                'published_at': date, 'source_version': version, 'title': 'Fixture memory study'}
    return {'kind': 'paper', 'adapter': 'arxiv', 'metadata': metadata, 'published_at': date,
            'identity_keys': store.identities(metadata),
            'attention': {'community_attention_score': score},
            'source': {'id': 'arxiv-' + identifier.replace('.', '-'), 'adapter': 'arxiv',
                       'kind': 'paper', 'url': metadata['source_url'] + version,
                       'evidence_max_chars': 6000}}


def atom(rows, total=None):
    entries = ''.join('<entry><id>https://arxiv.org/abs/%sv2</id><title>Memory fixture</title>'
                      '<author><name>Fixture</name></author><published>%sT00:00:00Z</published>'
                      '<updated>2026-10-25T00:00:00Z</updated><summary>Memory fixture source; '
                      'no real experiments or performance claims.</summary></entry>' % row for row in rows)
    return ('<feed xmlns="http://www.w3.org/2005/Atom" '
            'xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/">'
            '<opensearch:totalResults>%s</opensearch:totalResults>%s</feed>' % (
                len(rows) if total is None else total, entries))


class DiscoveryFetcher(fixtures.FixtureFetcher):
    def __init__(self, rows, votes=None, unknown=()):
        super().__init__()
        self.rows, self.votes, self.unknown = rows, votes or {}, set(unknown)
        self.api_urls = []

    def fetch(self, url):
        if '/api/query' not in url:
            if url.rstrip('/') == 'https://www.letta.com/blog':
                return {'url': url, 'content_type': 'text/html', 'text':
                        (fixtures.REPOSITORY / 'workflows/test/example-topic/fixtures/collection/blog-list.html').read_text()}
            return super().fetch(url)
        self.api_urls.append(url)
        query = parse_qs(urlsplit(url).query)
        start, limit = int(query['start'][0]), int(query['max_results'][0])
        text = atom(self.rows[start:start + limit], total=len(self.rows))
        return {'url': url, 'text': text, 'content_type': 'application/atom+xml'}

    def fetch_json(self, url):
        if 'huggingface.co' in url:
            identifier = url.rsplit('/', 1)[-1]
            if identifier in self.unknown:
                raise SourceError('Synthetic missing public record')
            value = {'id': identifier, 'upvotes': self.votes.get(identifier, 1), 'numComments': 0}
        else:
            original = parse_qs(urlsplit(url).query)['query'][0]
            if any(identifier in original for identifier in self.unknown):
                raise SourceError('Synthetic unavailable discussion provider')
            value = {'hits': []}
            if 'letta.com' in original:
                value = {'hits': [{'url': original, 'objectID': '12345',
                    'created_at_i': 1791504000, 'points': 10000, 'num_comments': 100}]}
        return {'json': value, 'sha256': store.digest(value), 'fetched_at': END}


class RollingSelectionAcceptance(unittest.TestCase):
    fake_research = fixtures.ResearchInsightCycle.fake_research
    fake_insight = fixtures.ResearchInsightCycle.fake_insight
    run_cycle = fixtures.ResearchInsightCycle.run_cycle

    def setUp(self):
        fixtures.ResearchInsightCycle.setUp(self)
        self.config.update(window={'mode': 'rolling', 'days': 60},
                           selection={'mode': 'community_attention', 'min_score': 0.1, 'max_requests': 240},
                           history={'lookback_days': 180, 'max_documents': 30})
        self.config['discovery'].update(max_candidates=40, max_documents=5, max_per_source=5)
        self.save_config()

    def save_config(self):
        self.config_path.write_text(yaml.safe_dump(self.config, allow_unicode=True, sort_keys=False))

    def make_snapshot(self, items):
        return dict(self.snapshot_value(), candidates=items)

    def snapshot_value(self):
        return {'window_start': START, 'window_end': END, 'candidates': [], 'deferred': []}

    def test_rolling_sixty_days_ignores_previous_complete_cursor(self):
        store.save_yaml(self.root, 'reports/test/custom-topic/cycles/old/receipt.yaml',
                        {'discovery_complete': True, 'window_end': '2026-10-29T00:00:00+00:00'})
        _, manifest, _ = self.cycle.discover_cycle(self.root, self.config_path, 'rolling-window')
        self.assertEqual(datetime.fromisoformat(manifest['window_end']) -
                         datetime.fromisoformat(manifest['window_start']), timedelta(days=60))

    def test_paper_discovery_queries_publication_window_in_twenty_item_pages(self):
        config = copy.deepcopy(self.config)
        config.pop('selection')
        config['discovery']['sources'] = config['discovery']['sources'][:1]
        config.update(window_start=START, window_end=END)
        fetcher = DiscoveryFetcher([('2610.%05d' % value, '2026-10-15') for value in range(10000, 10021)])
        result = REAL_DISCOVER(self.root, config, 'paged', fetcher)
        queries = [parse_qs(urlsplit(url).query) for url in fetcher.api_urls]
        self.assertEqual([query['start'] for query in queries], [['0'], ['20']])
        self.assertTrue(all(query['max_results'] == ['20'] for query in queries))
        self.assertIn('submittedDate:[202609010000 TO 202611010000]', queries[0]['search_query'][0])
        self.assertTrue(all(query['sortBy'] == ['submittedDate'] for query in queries))
        self.assertEqual(result['source_status'][0]['inspected'], 21)
        self.assertTrue(result['source_status'][0]['complete_window'])

    def test_global_attention_beats_publication_date_and_unknown_does_not_become_hot(self):
        config = copy.deepcopy(self.config)
        config.update(window_start=START, window_end=END)
        config['discovery']['max_documents'] = 2
        fetcher = DiscoveryFetcher([('2610.10001', '2026-10-20'), ('2610.10002', '2026-09-10'),
                                    ('2610.10003', '2026-10-21')],
                                   votes={'2610.10001': 2, '2610.10002': 50}, unknown=['2610.10003'])
        result = REAL_DISCOVER(self.root, config, 'attention', fetcher)
        self.assertEqual([item['adapter'] for item in result['candidates']], ['letta', 'arxiv'])
        self.assertEqual(result['candidates'][1]['metadata']['arxiv_id'], '2610.10002')
        unknown = next(item for item in result['deferred'] if item['metadata'].get('arxiv_id') == '2610.10003')
        self.assertEqual(unknown['reason'], 'attention_unknown')
        self.assertIsNone(unknown['attention']['community_attention_score'])

    def test_old_selected_pdf_identity_excludes_new_arxiv_version_before_fetching(self):
        old = paper('2610.10001', version='v1')
        old['metadata']['source_url'] = 'https://arxiv.org/pdf/2610.10001v1.pdf?utm_source=old'
        store.save_yaml(self.root, 'reports/test/custom-topic/cycles/old/manifest.yaml',
                        {'backend': 'chatgpt_plan', 'mode': 'research_cycle_test'})
        store.save_yaml(self.root, 'reports/test/custom-topic/cycles/old/selection.yaml', {'candidates': [old]})
        used = discovery.previously_selected(self.root, 'custom-topic', 'new')
        self.assertIn('arxiv:2610.10001', used)
        snapshot = self.make_snapshot([paper('2610.10001', version='v3'), paper('2610.10002')])
        with mock.patch.object(self.cycle.common, 'fetch_candidate', return_value=({}, 'unused')) as fetch, \
                mock.patch.object(self.cycle.research, 'classify', return_value={'action': 'research'}):
            selected = self.cycle.plan_candidates(self.root, self.config, 'new', snapshot, self.fetcher)
        self.assertEqual([entry['metadata']['arxiv_id'] for entry in selected['candidates']], ['2610.10002'])
        self.assertEqual(fetch.call_count, 1)

    def test_rolling_drops_old_pending_and_expired_candidates_and_reuses_frozen_selection(self):
        store.save_yaml(self.root, 'reports/test/custom-topic/cycles/old/pending.yaml',
                        {'items': [paper('2610.10001', score=999)]})
        snapshot = self.make_snapshot([paper('2610.10002', date='2024-01-01', score=999), paper('2610.10003')])
        with mock.patch.object(self.cycle.common, 'fetch_candidate', return_value=({}, 'unused')) as fetch, \
                mock.patch.object(self.cycle.research, 'classify', return_value={'action': 'research'}):
            first = self.cycle.plan_candidates(self.root, self.config, 'new', snapshot, self.fetcher)
            frozen = (self.root / 'reports/test/custom-topic/cycles/new/selection.yaml').read_bytes()
            second = self.cycle.plan_candidates(self.root, self.config, 'new', self.make_snapshot([]), self.fetcher)
        self.assertEqual([entry['metadata']['arxiv_id'] for entry in first['candidates']], ['2610.10003'])
        self.assertEqual(first, second)
        self.assertEqual(fetch.call_count, 1)
        self.assertEqual((self.root / 'reports/test/custom-topic/cycles/new/selection.yaml').read_bytes(), frozen)

    def test_after_research_failure_keeps_frozen_selection_and_does_not_call_model(self):
        self.snapshot['candidates'] = [paper('2610.01234')]
        self.snapshot['candidates'][0]['source']['url'] = 'https://export.arxiv.org/api/query?id_list=2610.01234v2'
        with self.assertRaises(store.SimulatedInterruption):
            self.run_cycle(fail_after='after_research')
        path = self.root / 'reports/test/custom-topic/cycles/first/selection.yaml'
        frozen = path.read_bytes()
        self.snapshot['candidates'] = []
        result = self.run_cycle()
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(path.read_bytes(), frozen)
        self.research_run.assert_called_once()
        self.client.infer.assert_not_called()

    def test_legacy_window_still_uses_its_old_cursor_and_no_attention_provider(self):
        self.config['window'] = {'initial_days': 7, 'overlap_hours': 48}
        self.config.pop('selection')
        self.config['discovery'].update(max_candidates=20, max_documents=2, max_per_source=1)
        self.save_config()
        store.save_yaml(self.root, 'reports/test/custom-topic/cycles/old/receipt.yaml',
                        {'discovery_complete': True, 'window_end': '2026-10-29T00:00:00+00:00'})
        _, manifest, _ = self.cycle.discover_cycle(self.root, self.config_path, 'legacy-window')
        self.assertEqual(manifest['window_start'], '2026-10-27T00:00:00+00:00')
        self.assertNotIn('selection', manifest['config'])


if __name__ == '__main__':
    unittest.main()
