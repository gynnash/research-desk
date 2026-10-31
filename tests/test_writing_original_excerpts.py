"""Small offline checks for the Writer's already-admitted archive projection.

The archive/admission verifiers are mocked at their boundaries here; their
separate tests own those proofs. Candidate files, hashes, locator slices and
formal Markdown comparisons remain real. No model, network or approval writes.
"""

from copy import deepcopy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import researchdesk_admission as admission
import researchdesk_archive as archive
import researchdesk_confirmation_inputs as inputs
import researchdesk_offline as store


class WritingOriginalExcerpts(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix='researchdesk-writing-excerpts-')
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name).resolve()
        self.text = 'The reviewed mechanism preserves observations and retrieves their evidence.'
        prefix = 'Unselected heading. '
        self.snapshot = {'document': {'sections': [{'id': 'S1',
            'text': prefix + self.text + ' Unreviewed extra results must remain excluded.'}]}}
        self.locator = {'id': 'A1', 'section_id': 'S1',
            'location': 'https://arxiv.org/html/2610.12345v1#S1; chars %s-%s' %
                        (len(prefix) + 1, len(prefix) + len(self.text)),
            'text_sha256': store.digest(self.text.encode()), 'quote': 'The reviewed mechanism'}
        base = 'reports/test/agent-memory/research-batches/fixed/items/paper-one/'
        self.material = 'A1: ' + self.text
        self.candidate = {'topic': 'agent-memory', 'key': 'paper-one',
            'source_id': 'paper-11111111-1111-4111-8111-111111111111',
            'archive': {'path': base + 'original.yaml', 'sha256': 'a' * 64,
                        'markdown_path': base + 'original.md'},
            'evidence': {'locators': [self.locator]}}
        for relative, payload in ((base + 'original.yaml', b'fixed archive boundary\n'),
                                  (base + 'original.md', b'# Fixed original\n')):
            self.write(relative, payload)
        self.write(base + 'original.yaml.sha256',
                   (store.digest((self.root / (base + 'original.yaml')).read_bytes()) + '\n').encode())
        candidate_path = base + 'candidate.yaml'
        candidate_payload = yaml.safe_dump({'candidate': self.candidate}, sort_keys=False).encode()
        self.write(candidate_path, candidate_payload)
        self.write(candidate_path + '.sha256', (store.digest(candidate_payload) + '\n').encode())
        self.formal = archive.relative_path(self.candidate)
        self.formal_content = '# Frozen admitted original\n\n' + self.text + '\n'
        self.write(self.formal, self.formal_content.encode())
        self.value = {'verification_bundle': {'provenance': {'research_inputs': [{
            'id': 'R1', 'candidate_path': candidate_path,
            'candidate_sha256': store.digest(candidate_payload),
            'original_material_sha256': store.digest(self.material.encode())}]}},
            'source_id_map': {}, 'files': {self.formal: self.formal_content}}
        self.item = {'id': 'R1', 'origin': 'reviewed_research', 'coverage': 'excerpt',
            'source_url': 'https://arxiv.org/abs/2610.12345v1', 'locators': [self.locator],
            'research_claims': [{'evidence_ids': ['A1']}]}

    def write(self, relative, payload):
        target = self.root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)

    def project(self, value=None, snapshot=None):
        with mock.patch.object(archive, 'load', return_value=(self.candidate, self.material,
                self.snapshot if snapshot is None else snapshot)), mock.patch.object(
                admission, 'effective_files', return_value={self.formal: self.formal_content}):
            return inputs._original_excerpts(self.root, self.value if value is None else value, self.item)

    def test_archive_slices_only_exact_reviewed_locator_and_freezes_file_hashes(self):
        excerpts, note, hashes = self.project()
        self.assertEqual([item['text'] for item in excerpts], [self.text])
        self.assertEqual(excerpts[0]['reading_scope'], 'excerpt')
        self.assertTrue(excerpts[0]['excerpt_only'])
        self.assertEqual(excerpts[0]['archive_path'], self.formal)
        self.assertEqual(excerpts[0]['archive_sha256'], store.digest(self.formal_content.encode()))
        self.assertIn('不扩大原阅读范围', note)
        self.assertNotIn('Unreviewed extra results', str(excerpts))
        self.assertEqual(set(hashes), {self.formal, self.candidate['archive']['path'],
            self.candidate['archive']['path'] + '.sha256', self.candidate['archive']['markdown_path']})
        for relative, digest in hashes.items():
            self.assertEqual(digest, store.digest((self.root / relative).read_bytes()))

    def test_unadmitted_or_changed_archive_content_is_rejected(self):
        with self.subTest('not formally admitted'):
            value = deepcopy(self.value)
            value['files'] = {}
            with self.assertRaisesRegex(store.OfflineError, '尚未正式准入'):
                self.project(value=value)
        with self.subTest('reviewed section changed'):
            snapshot = deepcopy(self.snapshot)
            snapshot['document']['sections'][0]['text'] = snapshot['document']['sections'][0]['text'].replace(
                'preserves', 'destroys')
            with self.assertRaisesRegex(store.OfflineError, '定位散列不同'):
                self.project(snapshot=snapshot)
        with self.subTest('formal Markdown changed'):
            self.write(self.formal, (self.formal_content + '\nAltered.\n').encode())
            with self.assertRaisesRegex(store.OfflineError, '正式原文归档已变化'):
                self.project()


if __name__ == '__main__':
    unittest.main()
