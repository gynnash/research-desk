"""Extracted originals replay without network or real membership/model calls."""

from copy import deepcopy
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest import mock

import yaml

import test_research_batch as fixtures
from test_fulltext_review import FulltextFetcher
import archive
import batch
import batch_inputs as inputs
import insight_inputs
import offline as store


class OriginalArchives(unittest.TestCase):
    def setUp(self):
        fixtures.ConfigDrivenResearchBatch.setUp(self)
        for source in self.config['sources']:
            source['archive'] = True
        self.fetcher = FulltextFetcher()

    def run_batch(self, identifier='first', **kwargs):
        return fixtures.ConfigDrivenResearchBatch.run_batch(self, identifier, **kwargs)

    def plan(self, key='paper-one', identifier='first'):
        return store.checked_yaml(self.root,
            'reports/test/custom-topic/research-batches/%s/items/%s/candidate.yaml' % (identifier, key))

    def test_archive_replays_completed_batch_and_insight_inputs_without_network(self):
        receipt = self.run_batch()
        self.assertEqual(receipt['status'], 'test_accepted')
        self.assertEqual(len(self.client.calls), 4)
        originals = {}
        for key in ('paper-one', 'blog-one'):
            candidate = self.plan(key)['candidate']
            restored, material, snapshot = archive.load(self.root, candidate)
            originals[key] = material
            self.assertEqual(restored, candidate)
            self.assertIn('> TEST', (self.root / candidate['archive']['markdown_path']).read_text())
            self.assertNotIn('> TEST', archive.render_markdown(snapshot, formal=True))
            self.assertTrue(archive.relative_path(candidate).startswith('sources/originals/custom-topic/'))
        self.fetcher.fetch = mock.Mock(side_effect=AssertionError('Network prohibited after archive'))
        self.fetcher.fetch_pdf = mock.Mock(side_effect=AssertionError('Network prohibited after archive'))
        replay = self.run_batch()
        self.assertTrue(replay['cached'])
        config = inputs.load_config(self.root, self.config_path)
        evidence, proof = insight_inputs._research_evidence(self.root, {
            'topic': config['topic'], '_topics_sha256': config['_topics_sha256'],
            'research_inputs': [{'receipt': receipt['receipt_path'],
                                 'config': self.config_path.relative_to(self.root).as_posix()}]}, self.fetcher)
        self.assertEqual(len(evidence), 2)
        self.assertEqual([item['original_material'] for item in evidence], list(originals.values()))
        self.assertEqual(len(proof), 2)
        self.fetcher.fetch.assert_not_called()
        self.assertEqual(len(self.client.calls), 4)

    def test_full_extraction_survives_smaller_model_reading_budget(self):
        self.config['sources'] = self.config['sources'][:1]
        self.config['sources'][0].update(reading={'mode': 'full_text_preferred'}, evidence_max_chars=700)
        self.config['budget'].update(max_documents=1, max_calls_per_batch=4)
        self.config['prompts']['version'] = 'research-batch-v2'
        self.client.research_mutator = lambda result: result.update(limitations=['仅读取正文节选，未复现实验。'])
        receipt = self.run_batch()
        self.assertEqual(receipt['status'], 'test_accepted')
        candidate = self.plan()['candidate']
        _, material, snapshot = archive.load(self.root, candidate)
        self.assertEqual(candidate['evidence']['coverage'], 'excerpt')
        self.assertGreater(snapshot['document']['total_chars'], len(material))
        self.assertIn(self.fetcher.body.strip(), archive.render_markdown(snapshot))
        self.assertEqual(snapshot['document']['format'], 'html')
        self.assertTrue(all(item.get('sha256') for item in snapshot['responses']))

    def test_model_failure_before_reservation_resumes_archived_original(self):
        self.config['sources'] = self.config['sources'][:1]
        self.config['budget'].update(max_documents=1, max_calls_per_batch=4)
        with mock.patch.object(batch, 'process', side_effect=RuntimeError('fixture interruption')):
            first = self.run_batch()
        self.assertEqual(first['completed_calls'], 0)
        candidate = self.plan()['candidate']
        saved = (self.root / candidate['archive']['path']).read_bytes()
        self.fetcher.fetch = mock.Mock(side_effect=AssertionError('No network retry'))
        result = self.run_batch()
        self.assertEqual(result['status'], 'test_accepted')
        self.assertEqual(result['completed_calls'], 2)
        self.assertEqual(saved, (self.root / candidate['archive']['path']).read_bytes())
        self.fetcher.fetch.assert_not_called()

    def test_semantic_material_tamper_rejected_even_after_resigning_file(self):
        self.run_batch()
        candidate = deepcopy(self.plan()['candidate'])
        path = self.root / candidate['archive']['path']
        snapshot = yaml.safe_load(path.read_text())
        snapshot['material'] += '\nInjected unsupported evidence'
        path.write_text(yaml.safe_dump(snapshot, allow_unicode=True, sort_keys=False))
        changed_hash = store.digest(path.read_bytes())
        path.with_name(path.name + '.sha256').write_text(changed_hash + '\n')
        candidate['archive']['sha256'] = changed_hash
        with self.assertRaisesRegex(store.OfflineError, '精确阅读材料'):
            archive.load(self.root, candidate)

    def test_missing_or_edited_reading_view_never_falls_back_to_network(self):
        self.run_batch()
        candidate = self.plan()['candidate']
        reading = self.root / candidate['archive']['markdown_path']
        reading.write_text(reading.read_text() + '\nHuman change must survive.\n')
        before = reading.read_bytes()
        self.fetcher.fetch = mock.Mock(side_effect=AssertionError('No network fallback'))
        with self.assertRaisesRegex(store.OfflineError, '禁止联网替换'):
            self.run_batch()
        self.assertEqual(reading.read_bytes(), before)
        self.fetcher.fetch.assert_not_called()

    def test_empty_archive_binding_cannot_downgrade_to_legacy_network_replay(self):
        self.run_batch()
        relative = 'reports/test/custom-topic/research-batches/first/items/paper-one/candidate.yaml'
        path = self.root / relative
        value = yaml.safe_load(path.read_text())
        value['candidate']['archive'] = {}
        path.write_text(yaml.safe_dump(value, allow_unicode=True, sort_keys=False))
        path.with_name(path.name + '.sha256').write_text(store.digest(path.read_bytes()) + '\n')
        self.fetcher.fetch = mock.Mock(side_effect=AssertionError('No legacy network downgrade'))
        with self.assertRaisesRegex(store.OfflineError, '归档绑定无效'):
            self.run_batch()
        self.fetcher.fetch.assert_not_called()

    def test_abstract_fallback_archives_abstract_without_claiming_fulltext(self):
        self.config['sources'] = self.config['sources'][:1]
        self.config['sources'][0]['reading'] = {'mode': 'full_text_preferred'}
        self.config['budget'].update(max_documents=1, max_calls_per_batch=4)
        self.config['prompts']['version'] = 'research-batch-v2'
        self.fetcher.fulltext_unavailable = True
        self.run_batch()
        _, _, snapshot = archive.load(self.root, self.plan()['candidate'])
        self.assertEqual(snapshot['document']['format'], 'abstract')
        view = archive.render_markdown(snapshot)
        self.assertIn('当前仅有摘要', view)
        self.assertIn('html / failed', view)
        self.assertIn('pdf / failed', view)

    def test_pdf_fallback_archives_extracted_sections_without_binary_payload(self):
        from test_fulltext_cycle import PdfCycleFetcher
        self.config['sources'] = self.config['sources'][:1]
        self.config['sources'][0]['reading'] = {'mode': 'full_text_preferred'}
        self.config['budget'].update(max_documents=1, max_calls_per_batch=4)
        self.config['prompts']['version'] = 'research-batch-v2'
        self.fetcher = PdfCycleFetcher()
        text = 'arXiv:2610.01234v2\n1 Method\n' + self.fetcher.body + '\n2 Limitations\n' + self.fetcher.body
        reader = SimpleNamespace(is_encrypted=False, pages=[SimpleNamespace(extract_text=lambda: text)])
        with mock.patch.dict(sys.modules, {'pypdf': SimpleNamespace(PdfReader=lambda *a, **kw: reader)}):
            self.run_batch()
        candidate = self.plan()['candidate']
        _, _, snapshot = archive.load(self.root, candidate)
        self.assertEqual(snapshot['document']['format'], 'pdf')
        self.assertIn('#page=1', archive.render_markdown(snapshot))
        self.assertEqual(snapshot['responses'][-1]['sha256'], store.digest(b'%PDF-fictional-cycle-fixture'))
        self.assertNotIn('%PDF-fictional', (self.root / candidate['archive']['path']).read_text())

    def test_archive_creation_interruption_reuses_original_uuid_and_bytes(self):
        self.config_path.write_text(yaml.safe_dump(self.config, allow_unicode=True, sort_keys=False))
        config = inputs.load_config(self.root, self.config_path)
        source = config['sources'][0]
        capture = {}
        candidate, material = inputs.fetch_candidate(self.root, config, source, self.fetcher, capture=capture)
        base = 'reports/test/custom-topic/research-batches/interrupted'
        saved = archive.save(self.root, base, candidate, material, source, capture)
        before = (self.root / saved['archive']['path']).read_bytes()
        refetched, material = inputs.fetch_candidate(self.root, config, source, self.fetcher, capture=capture)
        self.assertNotEqual(refetched['source_id'], candidate['source_id'])
        adopted = archive.save(self.root, base, refetched, material, source, capture)
        self.assertEqual(adopted, saved)
        self.assertEqual((self.root / saved['archive']['path']).read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
