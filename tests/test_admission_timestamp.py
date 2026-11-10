"""A changed blog date cannot invalidate identical reviewed source evidence.

The fixtures still pass through the real source parsers and full Research
checkpoint verification. All providers are fake and network access is blocked.
"""

import copy
from pathlib import Path
import sys
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import test_insight
import admission
import batch_inputs as research_inputs
import insight_inputs as inputs
import offline as store


class AdmissionTimestamp(unittest.TestCase):
    def setUp(self):
        # Borrow setup only, without inheriting the entire Insight test suite.
        test_insight.InsightLoop.setUp(self)
        test_insight.InsightLoop.write_config(self)
        self.loaded = inputs.load_config(self.root, self.config_path)
        self.baseline = inputs.prepare_bundle(self.root, self.loaded, fetcher=self.fetcher)
        self.real_fetch = research_inputs.fetch_candidate
        self.research_calls = len(self.research_client.calls)

    def changed_fetch(self, kind='blog', mutate=None):
        def fetch(*args, **kwargs):
            candidate, material = self.real_fetch(*args, **kwargs)
            if candidate['kind'] == kind:
                candidate['upstream_updated_at'] = '2026-10-28T18:06:04.136Z'
                candidate['metadata_hash'] = store.digest({
                    'metadata': candidate['metadata'],
                    'upstream_updated_at': candidate['upstream_updated_at']})
                if mutate is not None:
                    candidate, material = mutate(candidate, material)
            return candidate, material
        return fetch

    def prepare(self, **kwargs):
        return inputs.prepare_bundle(self.root, self.loaded, fetcher=self.fetcher, **kwargs)

    def assert_no_new_model_calls(self):
        self.assertEqual(len(self.research_client.calls), self.research_calls)
        self.assertEqual(self.client.calls, [])

    def valid_revalidation(self):
        records = []
        with mock.patch.object(research_inputs, 'fetch_candidate', side_effect=self.changed_fetch()):
            bundle = self.prepare(blog_timestamp_revalidations=records)
        self.assertEqual(bundle, self.baseline)
        self.assertEqual(len(records), 1)
        return records

    def test_default_revalidation_remains_strict(self):
        with mock.patch.object(research_inputs, 'fetch_candidate', side_effect=self.changed_fetch()):
            with self.assertRaises(store.OfflineError):
                self.prepare()
        self.assert_no_new_model_calls()

    def test_opt_in_preserves_exact_bundle_and_original_proofs(self):
        records = self.valid_revalidation()
        record = records[0]
        self.assertEqual(set(record), {
            'candidate_path', 'candidate_sha256', 'source_url',
            'reviewed_upstream_updated_at', 'observed_upstream_updated_at',
            'reviewed_metadata_hash', 'observed_metadata_hash', 'content_hash',
            'material_sha256', 'checked_at'})
        candidate = store.checked_yaml(self.root, record['candidate_path'])['candidate']
        self.assertEqual(record['candidate_sha256'],
                         store.digest((self.root / record['candidate_path']).read_bytes()))
        self.assertEqual(record['reviewed_metadata_hash'], candidate['metadata_hash'])
        self.assertEqual(record['reviewed_upstream_updated_at'], candidate['upstream_updated_at'])
        self.assertEqual(record['observed_upstream_updated_at'], '2026-10-28T18:06:04.136Z')
        self.assertEqual(record['material_sha256'], candidate['evidence']['evidence_sha256'])
        self.assert_no_new_model_calls()

    def test_opt_in_does_not_allow_other_source_or_evidence_changes(self):
        def title(candidate, material):
            candidate['metadata']['title'] += ' changed'
            candidate['metadata_hash'] = store.digest({
                'metadata': candidate['metadata'],
                'upstream_updated_at': candidate['upstream_updated_at']})
            return candidate, material

        def content(candidate, material):
            # Even unchanged selected material cannot hide a changed full
            # extracted body: both copies of its content hash are checked.
            candidate['content_hash'] = '1' * 64
            candidate['evidence']['content_hash'] = candidate['content_hash']
            return candidate, material

        def coverage(candidate, material):
            candidate['evidence']['coverage'] = 'full_text'
            return candidate, material

        def material(candidate, text):
            return candidate, text + '\nA99: An unreviewed statement.'

        def forged_hash(candidate, material):
            candidate['metadata_hash'] = '0' * 64
            return candidate, material

        def locator(candidate, material):
            candidate['evidence']['locators'][0]['quote'] += ' changed'
            return candidate, material

        for mutation in (title, content, coverage, material, forged_hash, locator):
            with self.subTest(change=mutation.__name__):
                records = []
                with mock.patch.object(research_inputs, 'fetch_candidate',
                                       side_effect=self.changed_fetch(mutate=mutation)):
                    with self.assertRaises(store.OfflineError):
                        self.prepare(blog_timestamp_revalidations=records)
                self.assertEqual(records, [])
        self.assert_no_new_model_calls()

    def test_paper_timestamp_drift_stays_strict(self):
        records = []
        with mock.patch.object(research_inputs, 'fetch_candidate',
                               side_effect=self.changed_fetch(kind='paper')):
            with self.assertRaises(store.OfflineError):
                self.prepare(blog_timestamp_revalidations=records)
        self.assertEqual(records, [])
        self.assert_no_new_model_calls()

    def test_saved_revalidation_cannot_be_changed_or_rebound(self):
        records = self.valid_revalidation()
        plan = {
            'verification_bundle': self.baseline,
            'input_hashes': {r['candidate_path']: r['candidate_sha256'] for r in records},
            'source_revalidations': records}
        admission._verify_source_revalidations(self.root, plan)
        changes = {
            'candidate_sha256': '0' * 64,
            'source_url': 'https://www.letta.com/blog/different-source',
            'reviewed_upstream_updated_at': '2026-01-01T00:00:00Z',
            'observed_upstream_updated_at': '2026-10-29T18:06:04.136Z',
            'reviewed_metadata_hash': '0' * 64,
            'observed_metadata_hash': '0' * 64,
            'content_hash': '0' * 64,
            'material_sha256': '0' * 64,
            'checked_at': 'invalid date'}
        for key, value in changes.items():
            with self.subTest(field=key):
                altered = copy.deepcopy(plan)
                altered['source_revalidations'][0][key] = value
                with self.assertRaises(store.OfflineError):
                    admission._verify_source_revalidations(self.root, altered)
        duplicate = copy.deepcopy(plan)
        duplicate['source_revalidations'] *= 2
        with self.assertRaises(store.OfflineError):
            admission._verify_source_revalidations(self.root, duplicate)
        self.assert_no_new_model_calls()

    def test_legacy_plan_and_unchanged_sources_need_no_exception_record(self):
        records = []
        self.assertEqual(self.prepare(blog_timestamp_revalidations=records), self.baseline)
        self.assertEqual(records, [])
        admission._verify_source_revalidations(self.root, {'verification_bundle': self.baseline})
        self.assert_no_new_model_calls()


if __name__ == '__main__':
    unittest.main()
