"""Standalone collection archives fictional originals without contacting models."""

import copy
from datetime import datetime, timezone
from pathlib import Path
import sys
from unittest import mock
import unittest

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import researchdesk_archive as archive
import researchdesk_membership as membership
import researchdesk_offline as store
import researchdesk_writing as writing
import test_cycle as cycle_fixtures
from test_fulltext_review import FulltextFetcher


REAL_DISCOVER = cycle_fixtures.importlib.import_module('researchdesk_cycle_discovery').discover


class FixedClock(datetime):
    @classmethod
    def now(cls, tz=None):
        value = cls(2026, 10, 31, 12, tzinfo=timezone.utc)
        return value.astimezone(tz) if tz else value.replace(tzinfo=None)


class CollectionFetcher(FulltextFetcher):
    def __init__(self):
        super().__init__()
        self.blog_tail = 'The final fictional paragraph must survive full collection.'
        long_body = ('This fictional public article explains source retrieval and memory boundaries. ' * 80)
        self.blog = self.blog.replace('</article>', '<p>' + long_body + self.blog_tail + '</p></article>')

    def fetch(self, url):
        if 'arxiv.org/abs/' in url:
            self.calls.append(url)
            text = (cycle_fixtures.REPOSITORY /
                    'workflows/test/example-topic/fixtures/collection/arxiv-abstract.html').read_text()
            return {'url': url, 'requested_url': url, 'content_type': 'text/html',
                    'status': 200, 'redirects': [], 'text': text,
                    'sha256': store.digest(text.encode())}
        if url.rstrip('/') == 'https://www.letta.com/blog':
            self.calls.append(url)
            text = (cycle_fixtures.REPOSITORY /
                    'workflows/test/example-topic/fixtures/collection/blog-list.html').read_text()
            return {'url': url, 'requested_url': url, 'content_type': 'text/html',
                    'status': 200, 'redirects': [], 'text': text,
                    'sha256': store.digest(text.encode())}
        return super().fetch(url)


class CollectionOnly(unittest.TestCase):
    fake_research = cycle_fixtures.ResearchInsightCycle.fake_research
    fake_insight = cycle_fixtures.ResearchInsightCycle.fake_insight

    def setUp(self):
        # Existing cycle fixtures create only disposable files and prohibit
        # socket use; their model stubs are replaced by hard failure guards.
        cycle_fixtures.ResearchInsightCycle.setUp(self)
        self.config.update(archive=True, window={'mode': 'rolling', 'days': 60},
                           reading={'mode': 'full_text_required',
                                    'paper_max_chars': 200000, 'blog_max_chars': 200000})
        self.config_path.write_text(yaml.safe_dump(self.config, allow_unicode=True, sort_keys=False))
        self.discovery.side_effect = REAL_DISCOVER
        self.fetcher = CollectionFetcher()
        self.research_run.side_effect = AssertionError('Research must not run during collection')
        self.insight_run.side_effect = AssertionError('Insight must not run during collection')
        self.member_client = mock.patch.object(membership, 'MembershipClient',
            side_effect=AssertionError('Collection must not instantiate membership')).start()
        self.writer = mock.patch.object(writing, 'run',
            side_effect=AssertionError('Writing must not run during collection')).start()
        mock.patch.object(self.cycle, 'datetime', FixedClock).start()

    def collect(self, identifier='first', **kwargs):
        return self.cycle.collect_originals(self.root, self.config_path, identifier,
                                            fetcher=self.fetcher, **kwargs)

    def assert_no_models(self):
        self.member_client.assert_not_called()
        self.research_run.assert_not_called()
        self.insight_run.assert_not_called()
        self.writer.assert_not_called()
        self.client.infer.assert_not_called()

    def read_candidate(self, record):
        return store.checked_yaml(self.root, record['candidate_path'])['candidate']

    def test_real_discovery_to_two_complete_original_archives_without_model_contact(self):
        receipt = self.collect()
        self.assertEqual(receipt['status'], 'collected')
        self.assertEqual(len(receipt['records']), 2)
        self.assertEqual(receipt['model_calls'], 0)
        self.assertFalse(receipt['production_accepted'])
        self.assert_no_models()
        self.assertTrue(any('search_query=' in url for url in self.fetcher.calls))
        self.assertTrue(any('/html/' in url for url in self.fetcher.calls))
        for record in receipt['records']:
            self.assertEqual(record['coverage'], 'full_text')
            candidate = self.read_candidate(record)
            restored, material, snapshot = archive.load(self.root, candidate)
            self.assertEqual(restored, candidate)
            self.assertFalse(candidate['evidence']['truncated'])
            self.assertEqual(candidate['evidence']['selected_chars'], candidate['evidence']['total_chars'])
            self.assertEqual(record['original_path'], candidate['archive']['path'])
            if candidate['kind'] == 'blog':
                self.assertIn(self.fetcher.blog_tail, material)
                self.assertIn(self.fetcher.blog_tail, (self.root / record['original_markdown_path']).read_text())
            self.assertEqual(store.digest(material.encode()), candidate['evidence']['evidence_sha256'])
        self.assertFalse((self.root / 'sources/originals').exists())
        batch = self.root / 'reports/test/custom-topic/research-batches/first'
        self.assertFalse((batch / 'manifest.yaml').exists())
        self.assertFalse((batch / 'events').exists())
        self.assertFalse(list(batch.glob('items/*/report.md')))
        self.assertFalse(list(batch.glob('items/*/result.yaml')))

    def test_cached_collection_uses_no_http_and_human_modified_original_is_not_replaced(self):
        first = self.collect()
        before = {p.relative_to(self.root): p.read_bytes()
                  for p in self.root.rglob('*') if p.is_file()}
        self.fetcher.calls.clear()
        self.fetcher.fetch = mock.Mock(side_effect=AssertionError('Cached collection must not fetch'))
        self.fetcher.fetch_pdf = mock.Mock(side_effect=AssertionError('Cached collection must not fetch PDF'))
        cached = self.collect()
        self.assertTrue(cached['cached'])
        self.assertEqual(cached['records'], first['records'])
        self.assertEqual(before, {p.relative_to(self.root): p.read_bytes()
                                  for p in self.root.rglob('*') if p.is_file()})
        target = self.root / first['records'][0]['original_markdown_path']
        target.write_text(target.read_text() + '\nMy annotation must survive.\n')
        modified = target.read_bytes()
        with self.assertRaises(store.OfflineError):
            self.collect()
        self.assertEqual(target.read_bytes(), modified)
        self.fetcher.fetch.assert_not_called()
        self.fetcher.fetch_pdf.assert_not_called()
        self.assert_no_models()

    def test_interrupted_collection_resumes_existing_original_and_fetches_only_remaining(self):
        with self.assertRaises(store.SimulatedInterruption):
            self.collect(fail_after='after_first_original')
        base = self.root / 'reports/test/custom-topic/research-batches/first/items'
        plans = sorted(base.glob('*/candidate.yaml'))
        self.assertEqual(len(plans), 1)
        first = store.checked_yaml(self.root, plans[0].relative_to(self.root))['candidate']
        saved = {relative: (self.root / relative).read_bytes() for relative in
                 (first['archive']['path'], first['archive']['markdown_path'])}
        self.fetcher.calls.clear()
        receipt = self.collect()
        self.assertEqual(len(receipt['records']), 2)
        selected = next(self.read_candidate(record) for record in receipt['records']
                        if record['source_id'] == first['source_id'])
        self.assertEqual(selected, first)
        self.assertEqual(saved, {relative: (self.root / relative).read_bytes() for relative in saved})
        self.assertTrue(self.fetcher.calls)
        self.assertFalse(any('arxiv.org' in url for url in self.fetcher.calls))
        self.assertTrue(all('letta.com' in url for url in self.fetcher.calls))
        self.assert_no_models()

    def test_prior_selected_url_alias_and_arxiv_new_version_are_not_collected_again(self):
        self.collect()
        snapshot = copy.deepcopy(store.checked_yaml(self.root,
            'reports/test/custom-topic/cycles/first/discovery.yaml'))
        snapshot['cycle_id'] = 'second'
        for item in snapshot['candidates']:
            metadata = item['metadata']
            if item['kind'] == 'paper':
                metadata.update(source_url='https://arxiv.org/pdf/2610.01234v3.pdf?utm_source=alias',
                                source_version='v3')
            else:
                metadata['source_url'] += '?utm_source=alias'
            item['identity_keys'] = store.identities(metadata)
            item['source']['url'] = metadata['source_url']
        self.discovery.side_effect = lambda *args, **kwargs: copy.deepcopy(snapshot)
        self.fetcher.calls.clear()
        second = self.collect('second')
        self.assertEqual(second['status'], 'empty')
        self.assertEqual(second['records'], [])
        self.assertEqual(self.fetcher.calls, [])
        self.assert_no_models()

    def test_disabled_topic_stops_before_fetch_or_output(self):
        path = self.root / 'config/research_topics.yaml'
        topics = yaml.safe_load(path.read_text())
        topics['topics']['custom-topic']['enabled'] = False
        path.write_text(yaml.safe_dump(topics))
        before = {p.relative_to(self.root): p.read_bytes()
                  for p in self.root.rglob('*') if p.is_file()}
        with self.assertRaises(store.OfflineError):
            self.collect()
        self.assertEqual(self.fetcher.calls, [])
        self.assertEqual(before, {p.relative_to(self.root): p.read_bytes()
                                  for p in self.root.rglob('*') if p.is_file()})
        self.assert_no_models()


if __name__ == '__main__':
    unittest.main()
