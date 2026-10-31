"""Mandatory full originals fail closed; no network or membership calls."""

from copy import deepcopy
from types import SimpleNamespace
import sys
import unittest
from unittest import mock

import yaml

import test_research_batch as fixtures
from test_fulltext import PAPER, HTML, BODY, FixedFetcher
import researchdesk_archive as archive
import researchdesk_batch_inputs as inputs
import researchdesk_cycle_discovery as discovery
import researchdesk_fulltext as fulltext
import researchdesk_offline as store
from researchdesk_sources import SourceError


class RequiredFulltext(unittest.TestCase):
    def setUp(self):
        fixtures.ConfigDrivenResearchBatch.setUp(self)

    def test_paper_cannot_fall_back_to_abstract_or_unreadable_pdf_page(self):
        with self.assertRaisesRegex(SourceError, 'Full text required.*HTML/PDF unavailable'):
            fulltext.acquire_paper(PAPER, FixedFetcher(), require_full=True)
        reader = SimpleNamespace(is_encrypted=False, pages=[
            SimpleNamespace(extract_text=lambda: BODY),
            SimpleNamespace(extract_text=lambda: '')])
        with mock.patch.dict(sys.modules, {'pypdf': SimpleNamespace(PdfReader=lambda *a, **kw: reader)}):
            with self.assertRaisesRegex(SourceError, 'one or more PDF pages'):
                fulltext.acquire_paper(PAPER, FixedFetcher(pdf=b'%PDF-fixture'), require_full=True)

    def test_complete_paper_cannot_be_silently_truncated_for_model(self):
        document = fulltext.acquire_paper(PAPER, FixedFetcher(html=HTML), require_full=True)
        record = deepcopy(PAPER)
        record['metadata']['source_url'] = 'https://arxiv.org/abs/2610.01234'
        record.update(coverage='abstract_only', content_hash=store.digest(record['body_text'].encode()))
        source = {'reading': {'mode': 'full_text_required'}, 'evidence_max_chars': 200}
        with self.assertRaises(SourceError):
            inputs.project_material(record, document, source)

    def test_blog_preserves_entire_body_and_archive_replays_full_model_input(self):
        source = deepcopy(self.config['sources'][1])
        source.update(reading={'mode': 'full_text_required'}, archive=True, evidence_max_chars=200000)
        body = 'A public fictional mechanism stores evidence and revisits its retrieval choices. ' * 350
        self.fetcher.blog = self.fetcher.blog.replace('</article>', '<p>' + body + '</p></article>')
        capture = {}
        candidate, material = inputs.fetch_candidate(self.root, self.config, source, self.fetcher, capture=capture)
        evidence = candidate['evidence']
        self.assertEqual(evidence['coverage'], 'full_text')
        self.assertEqual(evidence['reading_profile'], 'blog-fulltext-v1')
        self.assertEqual(evidence['total_chars'], evidence['selected_chars'])
        self.assertIn(body.strip()[-200:], material)
        candidate = archive.save(self.root, 'reports/test/custom-topic/research-batches/full-blog',
                                 candidate, material, source, capture)
        replayed, replay_material, _ = archive.load(self.root, candidate)
        self.assertEqual(replay_material, material)
        self.assertEqual(replayed, candidate)
        source['evidence_max_chars'] = 1000
        with self.assertRaisesRegex(SourceError, 'no excerpt accepted'):
            inputs.fetch_candidate(self.root, self.config, source, self.fetcher)

    def test_short_or_access_gated_blog_is_not_called_full_text(self):
        source = dict(self.config['sources'][1], reading={'mode': 'full_text_required'}, archive=True)
        with self.assertRaisesRegex(SourceError, 'incomplete or too short'):
            inputs.fetch_candidate(self.root, self.config, source, self.fetcher)
        self.fetcher.blog = self.fetcher.blog.replace('</article>', '<p>' + BODY * 8 +
            ' Subscribe to continue reading.</p></article>')
        with self.assertRaisesRegex(SourceError, 'access gate'):
            inputs.fetch_candidate(self.root, self.config, source, self.fetcher)

    def test_v4_config_requires_archive_and_accepts_larger_output(self):
        self.config['prompts']['version'] = 'research-batch-v4'
        self.config['budget']['max_output_chars'] = 24000
        for source in self.config['sources']:
            source.update(reading={'mode': 'full_text_required'}, archive=True, evidence_max_chars=200000)
        self.config_path.write_text(yaml.safe_dump(self.config))
        self.assertEqual(inputs.load_config(self.root, self.config_path)['prompts']['version'], 'research-batch-v4')
        self.config['sources'][1].pop('archive')
        self.config_path.write_text(yaml.safe_dump(self.config))
        with self.assertRaisesRegex(store.OfflineError, '原文归档'):
            inputs.load_config(self.root, self.config_path)

    def test_retained_identity_state_prevents_reselecting_cleaned_results(self):
        state = self.root / 'config/research_state.yaml'
        state.write_text(yaml.safe_dump({'schema_version': 1, 'selected_identity_keys': ['url:https://example.org/old'],
                                        'usage_months': {}, 'previous_commit': 'retained'}))
        self.assertIn('url:https://example.org/old', discovery.previously_selected(self.root, 'custom-topic', 'first'))
        state.write_text(yaml.safe_dump({'schema_version': 1, 'selected_identity_keys': [None]}))
        with self.assertRaisesRegex(store.OfflineError, '历史去重状态无效'):
            discovery.previously_selected(self.root, 'custom-topic', 'first')


if __name__ == '__main__':
    unittest.main()
