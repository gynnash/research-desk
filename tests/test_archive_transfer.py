"""Public code examples need proven archive bytes, never a global guard bypass."""

from copy import deepcopy
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock

import yaml

import test_research_batch as fixtures
from test_fulltext_review import FulltextFetcher
import researchdesk_admission as admission
import researchdesk_archive as archive
import researchdesk_batch_inputs as inputs
import researchdesk_job as job
import researchdesk_offline as store


class ArchiveTransfer(unittest.TestCase):
    def setUp(self):
        fixtures.ConfigDrivenResearchBatch.setUp(self)
        self.config['sources'] = self.config['sources'][:1]
        self.config['sources'][0].update(archive=True, reading={'mode': 'full_text_preferred'})
        self.config['prompts']['version'] = 'research-batch-v2'
        self.config['budget'].update(max_documents=1, max_calls_per_batch=4)
        self.config_path.write_text(yaml.safe_dump(self.config, sort_keys=False))
        self.resolved = inputs.load_config(self.root, self.config_path)
        self.source = self.resolved['sources'][0]
        self.fetcher = FulltextFetcher()
        self.fetcher.body += ' Public example: api_key: example; cache directory /tmp/cache/.'
        self.base = 'reports/test/custom-topic/research-batches/first'
        self.candidate_path = self.base + '/items/paper-one/candidate.yaml'
        self.plan_path = 'reports/custom-topic/admissions/first/plan.yaml'

    def archived(self, metadata_example=False):
        capture = {}
        candidate, material = inputs.fetch_candidate(self.root, self.resolved, self.source,
                                                      self.fetcher, capture=capture)
        if metadata_example:
            capture['responses'][0]['extra_metadata'] = 'api_key: example'
        candidate = archive.save(self.root, self.base, candidate, material, self.source, capture)
        store.save_yaml(self.root, self.candidate_path, {'candidate': candidate})
        return candidate

    def formal(self, candidate):
        path, content = admission._archive_file(self.root, candidate, candidate['source_id'])
        plan = {'files': {path: content, 'reports/custom-topic/first-synthesis.md': '# Safe formal report'},
            'verification_bundle': {'provenance': {'research_inputs': [{'candidate_path': self.candidate_path}]}},
            'source_id_map': {candidate['source_id']: candidate['source_id']}}
        admission._save(self.root, self.plan_path, plan)
        admission._create(self.root, path, content)
        return path, plan

    def test_public_examples_pass_only_after_original_reconstruction(self):
        candidate = self.archived()
        formal, _ = self.formal(candidate)
        paths = [candidate['archive']['path'], candidate['archive']['markdown_path'], self.plan_path, formal]
        job.inspect_files(self.root, paths, 'custom-topic', 'first')
        self.assertEqual(self.client.calls, [])
        for path in paths:
            with self.subTest(path=path):
                self.assertIn('api_key: example', (self.root / path).read_text())
        # Ordinary configuration/receipt/research prose keeps the strict guard.
        for path in ('reports/test/custom-topic/cycles/first/receipt.yaml',
                     'reports/test/custom-topic/research-batches/first/report.md'):
            with self.subTest(ordinary=path), self.assertRaises(job.JobError):
                job.check_text(b'> TEST\napi_key: example\n/tmp/cache/', path)

    def test_non_body_metadata_and_non_original_plan_prose_stay_strict(self):
        candidate = self.archived(metadata_example=True)
        with self.assertRaisesRegex(job.JobError, 'possible_secret'):
            job.inspect_files(self.root, [candidate['archive']['path']], 'custom-topic', 'first', set())
        # A matching original never exempts unrelated report text in the plan.
        formal, plan = self.formal(candidate)
        plan['files']['reports/custom-topic/first-synthesis.md'] = 'api_key: example'
        target = self.root / self.plan_path
        target.write_text(yaml.safe_dump(plan, allow_unicode=True, sort_keys=False))
        target.with_name(target.name + '.sha256').write_text(store.digest(target.read_bytes()))
        with self.assertRaisesRegex(job.JobError, 'possible_secret'):
            job.inspect_files(self.root, [self.plan_path], 'custom-topic', 'first')

    def test_tampered_original_or_plan_cannot_request_public_exception(self):
        candidate = self.archived()
        formal, plan = self.formal(candidate)
        markdown = self.root / candidate['archive']['markdown_path']
        original = markdown.read_bytes()
        markdown.write_bytes(original + b'\napi_key: example\n')
        with self.assertRaisesRegex(job.JobError, 'unverified_original'):
            job.inspect_files(self.root, [candidate['archive']['path']], 'custom-topic', 'first')
        markdown.write_bytes(original)
        changed = deepcopy(plan)
        changed['files'][formal] += '\napi_key: example\n'
        target = self.root / self.plan_path
        target.write_text(yaml.safe_dump(changed, allow_unicode=True, sort_keys=False))
        target.with_name(target.name + '.sha256').write_text(store.digest(target.read_bytes()))
        with self.assertRaisesRegex(job.JobError, 'unverified_original'):
            job.inspect_files(self.root, [self.plan_path], 'custom-topic', 'first')

    def test_transfer_can_read_immutable_archive_from_baseline_but_prefers_payload(self):
        candidate = self.archived()
        formal, _ = self.formal(candidate)
        temporary = tempfile.TemporaryDirectory(prefix='researchdesk-archive-payload-')
        self.addCleanup(temporary.cleanup)
        payload = Path(temporary.name)
        for relative in (formal, self.plan_path, self.plan_path + '.sha256'):
            target = payload / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(self.root / relative, target)
        job.inspect_files(payload, [formal, self.plan_path], 'custom-topic', 'first', baseline_root=self.root)
        bad = payload / self.candidate_path
        bad.parent.mkdir(parents=True, exist_ok=True)
        bad.write_bytes((self.root / self.candidate_path).read_bytes() + b'\nchanged: true\n')
        with self.assertRaisesRegex(job.JobError, 'unverified_original'):
            job.inspect_files(payload, [formal], 'custom-topic', 'first', baseline_root=self.root)

    def test_credential_shapes_are_rejected_before_first_model_or_transfer(self):
        tokens = ['Bearer ' + 'a' * 30, 'sk-' + 'b' * 30,
                  'eyJ' + 'c' * 35 + '.' + 'd' * 25 + '.signature', 'api_key: ' + 'e' * 32]
        for token in tokens:
            with self.subTest(token_type=token[:8]):
                with self.assertRaisesRegex(job.JobError, 'possible_secret'):
                    job.check_text(token.encode(), 'sources/originals/custom-topic/fixture.md', True,
                                   public_metadata='verified metadata')
                self.fetcher.body = ('This fictional method describes memory without experimental claims. ' * 12
                                     + ' Public unsafe token example: ' + token)
                capture = {}
                candidate, material = inputs.fetch_candidate(self.root, self.resolved, self.source,
                                                              self.fetcher, capture=capture)
                with self.assertRaisesRegex(store.OfflineError, '疑似真实凭据'):
                    archive.save(self.root, self.base, candidate, material, self.source, capture)
                self.assertFalse((self.root / (self.base + '/items/paper-one/original.yaml')).exists())
                self.assertEqual(self.client.calls, [])

    def test_public_exception_keeps_file_size_limits(self):
        with self.assertRaisesRegex(job.JobError, 'too_large'):
            job.check_text(b'x' * 2_000_001, 'sources/originals/custom-topic/fixture.md', True,
                           public_metadata='verified metadata')
        with self.assertRaisesRegex(job.JobError, 'too_large'):
            job.check_text(b'x' * 12_000_001, self.plan_path, True, public_metadata='verified metadata')


if __name__ == '__main__':
    unittest.main()
