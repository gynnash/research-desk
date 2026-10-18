"""Focused URL-history checks with disposable notes and no model/network calls."""

import copy
from pathlib import Path
import socket
import sys
import tempfile
import unittest
from unittest import mock

import yaml


REPOSITORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY / 'scripts'))
import researchdesk_batch as batch
import researchdesk_batch_inputs as inputs
import researchdesk_identity as identity
import researchdesk_offline as store


BLOG = 'https://www.letta.com/blog/fixture-memory'
SOURCE_ID = 'blog-2031dcca-0e25-4518-a08c-a27594417402'


def candidate(url=BLOG, *, kind='blog', version=None, content='full-text', evidence='excerpt'):
    metadata = {'source_url': url, 'title': 'Memory fixture', 'source': 'Fixture',
                'authors': ['Fixture Author'], 'published_at': '2026-10-14'}
    if kind == 'paper':
        metadata.update(arxiv_id='2610.01234', source_version=version)
    value = {'key': 'fixture', 'kind': kind, 'metadata': metadata,
             'source_id': SOURCE_ID.replace('blog-', kind + '-'),
             'existing_source_path': None, 'existing_source_metadata': None,
             'upstream_updated_at': '2026-10-14', 'content_hash': store.digest(content),
             'evidence': {'coverage': 'abstract_only' if kind == 'paper' else 'excerpt',
                          'content_hash': store.digest(content),
                          'evidence_sha256': store.digest(evidence)}}
    value['identity_keys'] = store.identities(metadata)
    value['metadata_hash'] = store.digest({'metadata': metadata,
                                          'upstream_updated_at': value['upstream_updated_at']})
    return value


class UrlHistoryDedup(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='researchdesk-url-dedup-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        for directory in ('sources/papers', 'sources/blogs', 'reports', 'insights', 'articles'):
            (self.root / directory).mkdir(parents=True, exist_ok=True)
        self.addCleanup(mock.patch.stopall)
        mock.patch.object(socket, 'create_connection', side_effect=AssertionError('Network prohibited')).start()
        mock.patch.object(socket.socket, 'connect', side_effect=AssertionError('Network prohibited')).start()

    def classify_with_history(self, current, prior, *, result=None):
        result = result or {'status': 'test_accepted', 'report_path': 'reports/test/old/report.md'}
        with mock.patch.object(batch, 'previous_candidates', return_value=[
                ('reports/test/old/research-batches/old', prior, result, [])]):
            return batch.classify(self.root, 'reports/test/current', current, 'chatgpt_plan', set())

    def test_shared_url_policy_removes_tracking_but_preserves_effective_queries(self):
        tracked = BLOG + '?view=full&utm_source=newsletter&gclid=click#part-2'
        self.assertEqual(store.identities({'source_url': tracked}),
                         store.identities({'source_url': BLOG + '?view=full'}))
        for distinct in (BLOG + '?view=compact', BLOG + '/', BLOG + '?view=full&view=compact',
                         BLOG + '?view=compact&view=full'):
            self.assertNotEqual(store.identities({'source_url': distinct}),
                                store.identities({'source_url': BLOG + '?view=full'}))

    def test_official_arxiv_abs_pdf_and_versions_share_paper_identity(self):
        urls = ('https://arxiv.org/abs/2610.01234v1',
                'http://export.arxiv.org/pdf/2610.01234v2.pdf#page=3',
                'https://arxiv.org/html/2610.01234v3?utm_campaign=fixture')
        for url in urls:
            self.assertIn('arxiv:2610.01234', store.identities({'source_url': url}))

    def test_history_url_spelling_is_duplicate_without_rewriting_old_proof(self):
        prior = candidate(BLOG + '?utm_source=old#summary')
        current = candidate(BLOG + '?fbclid=new')
        current['source_id'] = 'blog-fc8c60f7-6b86-4e44-8c9e-a6bad5dfeae4'
        # Persisted older keys may have a different URL spelling. They remain
        # immutable; current matching is recomputed from source metadata.
        prior['identity_keys'] = ['url:' + prior['metadata']['source_url']]
        before = copy.deepcopy(prior)
        self.assertNotEqual(prior['metadata_hash'], current['metadata_hash'])
        self.assertEqual(self.classify_with_history(current, prior)['action'], 'duplicate')
        self.assertEqual(current['source_id'], prior['source_id'])
        self.assertEqual(prior, before)

    def test_same_batch_url_alias_is_blocked_but_distinct_query_can_be_researched(self):
        seen = set()
        with mock.patch.object(batch, 'previous_candidates', return_value=[]):
            first = batch.classify(self.root, 'new', candidate(BLOG + '?utm_source=one'), 'chatgpt_plan', seen)
            alias = batch.classify(self.root, 'new', candidate(BLOG + '#second'), 'chatgpt_plan', seen)
            distinct = batch.classify(self.root, 'new', candidate(BLOG + '?view=compact'), 'chatgpt_plan', seen)
        self.assertEqual(first['action'], 'research')
        self.assertEqual(alias, {'action': 'blocked', 'reason': 'same_batch_identity_conflict'})
        self.assertEqual(distinct['action'], 'research')

    def test_arxiv_url_spelling_dedups_but_version_change_stays_an_update(self):
        prior = candidate('https://arxiv.org/pdf/2610.01234v2.pdf', kind='paper', version='v2')
        same = candidate('https://arxiv.org/abs/2610.01234v2', kind='paper', version='v2')
        changed = candidate('https://arxiv.org/abs/2610.01234v3', kind='paper', version='v3')
        self.assertEqual(self.classify_with_history(same, prior)['action'], 'duplicate')
        self.assertEqual(self.classify_with_history(changed, prior)['action'], 'update')

    def test_content_excerpts_and_explicit_upstream_updates_are_not_false_duplicates(self):
        prior = candidate()
        changed_date = candidate()
        changed_date['upstream_updated_at'] = '2026-10-15'
        for current in (candidate(content='changed full text'), candidate(evidence='wider excerpt'), changed_date):
            with self.subTest(current=current):
                self.assertEqual(self.classify_with_history(current, prior)['action'], 'update')

    def test_formal_and_test_notes_are_found_by_url_and_preserved(self):
        html = (REPOSITORY / 'workflows/test/agent-memory/fixtures/collection/blog-article.html').read_text()
        fetcher = mock.Mock()
        fetcher.fetch.return_value = {'url': BLOG, 'text': html, 'content_type': 'text/html'}
        source = {'id': 'blog', 'adapter': 'letta', 'kind': 'blog', 'url': BLOG, 'evidence_max_chars': 6000}
        for folder in ('sources/blogs/agent-memory', 'sources/blogs/test/agent-memory'):
            with self.subTest(folder=folder):
                path = self.root / folder / (SOURCE_ID + '.md')
                path.parent.mkdir(parents=True, exist_ok=True)
                metadata = dict(candidate(BLOG + '?utm_source=historic#notes')['metadata'],
                                id=SOURCE_ID, kind='blog', status='analyzed')
                path.write_text('---\n' + yaml.safe_dump(metadata) + '---\n\n## 人工笔记\n\n保留。\n')
                original = path.read_bytes()
                value, _ = inputs.fetch_candidate(self.root, {'topic': 'agent-memory'}, source, fetcher)
                self.assertEqual(value['source_id'], SOURCE_ID)
                self.assertEqual(value['existing_source_path'], path.relative_to(self.root).as_posix())
                self.assertEqual(path.read_bytes(), original)
                if '/test/' not in folder:
                    with mock.patch.object(batch, 'previous_candidates', return_value=[]):
                        decision = batch.classify(self.root, 'new', value, 'chatgpt_plan', set())
                    self.assertEqual(decision['reason'], 'formal_note_requires_proven_update')
                path.unlink()


if __name__ == '__main__':
    unittest.main()
