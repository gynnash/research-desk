"""New Insight topics reach page-confirmed Writing using fictional offline data."""
import copy
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import researchdesk_confirmation as page
import researchdesk_confirmation_inputs as previews
import researchdesk_offline as store
import researchdesk_writing_member as writing
import researchdesk_writing_member_inputs as inputs
from test_insight_admission import prepare_cycle
from test_research_batch import FakeMemberClient


class FakeWriter(FakeMemberClient):
    def __init__(self):
        super().__init__()
        self.catalog = [{'slug': 'fixture-writer'}, {'slug': 'fixture-writing-review'}]

    def infer(self, model, instructions, input_text, **limits):
        request = json.loads(input_text)
        self.calls.append(request)
        if 'candidate' in request:
            result = {'decision': 'pass', 'coverage_acknowledged': True, 'issues': [],
                'checks': [{'section_index': si, 'paragraph_index': pi,
                            'verdict': 'supported', 'evidence_ids': p['evidence_ids']}
                           for si, section in enumerate(request['candidate']['sections'])
                           for pi, p in enumerate(section['paragraphs'])]}
        else:
            result = {'title': request['topic_card']['title'], 'summary': 'Offline fictional summary.',
                'sections': [{'heading': 'Methods and evidence', 'paragraphs': [{
                    'kind': 'author_claim', 'text': '作者讨论如何保留原文证据及解释记忆机制。' * 35,
                    'evidence_ids': [request['evidence'][0]['id']]}]}], 'limitations': []}
        return {'text': json.dumps(result, ensure_ascii=False), 'model': model,
                'response_id': 'fictional-writing-%s' % len(self.calls),
                'usage': {'input_tokens': 10, 'output_tokens': 10, 'total_tokens': 20}}


class WritingSDKBridge(unittest.TestCase):
    def setUp(self):
        self.fixture, self.backend = prepare_cycle(self)
        self.root = self.fixture.root
        self.config = copy.deepcopy(yaml.safe_load((ROOT / 'config/system.yaml').read_text())['confirmation'])
        self.config['workbench_id'] = 'fixture-workbench'
        self.config['writing']['models'] = {'writing': 'fixture-writer', 'review': 'fixture-writing-review'}
        self.config['writing']['words']['default'] = 800
        (self.root / 'config/confirmation-v2.yaml').write_text(yaml.safe_dump(self.config))
        (self.root / 'config/writing_style.md').write_text('Explain technical methods clearly; do not invent personal experience.')
        (self.root / 'config/local').mkdir(exist_ok=True)
        (self.root / 'config/local/workbench.yaml').write_text('schema_version: 1\n')
        shutil.copyfile(ROOT / '.gitignore', self.root / '.gitignore')
        self.git('init', '-b', 'main')
        self.git('config', 'user.name', 'Fictional offline writer')
        self.git('config', 'user.email', 'writer@example.invalid')
        self.commit('Fictional reviewed source inputs')
        self.card = 'formal-topic-agent_memory-first-1'
        self.client = FakeWriter()

    def git(self, *arguments):
        return subprocess.run(['git', '-C', str(self.root), *arguments], check=True,
                              capture_output=True, text=True).stdout.strip()

    def commit(self, message, files=None):
        self.git('add', '--', *(files or ['.']))
        self.git('commit', '-m', message)
        self.git('update-ref', 'refs/remotes/origin/main', 'HEAD')

    def approve(self):
        def publish(root, files, message):
            self.commit(message, files)
            return True
        manager = page.ConfirmationStore(self.root, page.load_config(self.root), publisher=publish)
        topics = manager.list_topics()
        self.assertEqual([card['id'] for card in topics], [self.card])
        preview = manager.preview(self.card, {'target_words': 800})
        self.assertEqual(preview['admission_mode'], 'codex_insight_admission')
        record = manager.confirm(preview['preview_id'], acknowledged=True)
        return manager, record['id']

    def test_confirmed_new_topic_runs_three_stages_and_public_frozen_proof(self):
        manager, approval = self.approve()
        bundle = inputs.prepare_bundle(self.root, approval)
        self.assertTrue(bundle['evidence'][0]['original_excerpts'])
        self.assertTrue(bundle['evidence'][0]['claims'])
        self.assertEqual(inputs.verify_frozen_bundle(self.root, bundle), bundle)
        result = writing.run(self.root, approval, client=self.client, refresh=lambda: True, max_new_calls=6)
        self.assertEqual(result['status'], 'test_accepted')
        self.assertEqual(len(self.client.calls), 6)
        self.assertEqual(writing.run(self.root, approval, client=self.client, refresh=lambda: True,
                                    max_new_calls=0)['status'], 'test_accepted')
        self.assertEqual(len(self.client.calls), 6)
        self.assertEqual(manager.list_confirmations()[0]['writing']['status'], 'test_accepted')
        with (self.root / bundle['evidence'][0]['source_paths'][0]).open('a') as handle:
            handle.write('\nHuman correction retained.\n')
        with self.assertRaises(store.OfflineError):
            inputs.verify_frozen_bundle(self.root, bundle)

    def test_hosted_save_without_private_yaml_admits_create_only_formal_writing(self):
        import researchdesk_writing_deployment as deployed
        import researchdesk_writing_admission as formal
        _, approval = self.approve()
        bundle = inputs.prepare_bundle(self.root, approval)
        result = writing.run(self.root, approval, client=self.client, refresh=lambda: True, max_new_calls=6)
        self.assertEqual(result['status'], 'test_accepted')
        store.save_yaml(self.root, deployed._input_path(bundle['topic'], bundle['batch_id']), bundle)
        directory = tempfile.TemporaryDirectory(prefix='researchdesk-writing-transfer-')
        self.addCleanup(directory.cleanup)
        artifact, publisher = Path(directory.name) / 'artifact', Path(directory.name) / 'publisher'
        artifact.mkdir()
        files = {}
        for relative in deployed._files(self.root, bundle):
            data = (self.root / relative).read_bytes()
            target = artifact / 'payload' / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            files[relative] = store.digest(data)
        value = {'schema_version': 2, 'mode': deployed.MODE, 'topic': bundle['topic'],
                 'approval_id': approval, 'batch_id': bundle['batch_id'],
                 'base_commit': self.git('rev-parse', 'HEAD'),
                 'input_fingerprint': bundle['input_fingerprint'],
                 'input_hashes': {p: sha for p, sha in bundle['snapshot']['hashes'].items()
                                  if Path(p).parts[:1] != ('config',)}, 'files': files}
        (artifact / 'manifest.json').write_text(json.dumps(value))
        subprocess.run(['git', 'clone', '--quiet', '--no-hardlinks', str(self.root), str(publisher)],
                       check=True, capture_output=True)
        self.assertFalse((publisher / 'config/confirmation-v2.yaml').exists())
        self.assertFalse((publisher / 'config/local/workbench.yaml').exists())
        saved = deployed.apply(publisher, artifact, push=False)
        self.assertTrue(saved['production_accepted'])
        self.assertEqual(len(self.client.calls), 6)
        documents = formal.inspect(publisher, bundle['topic'], approval)
        self.assertEqual(documents['status'], 'accepted')
        self.assertEqual(len(documents['documents']), 3)
        self.assertFalse((publisher / 'config/confirmation-v2.yaml').exists())
        self.assertEqual(deployed.apply(publisher, artifact, push=False)['saved_files'], 0)
        target = publisher / documents['documents'][-1]['path']
        target.write_text(target.read_text() + '\nHuman edits are preserved.\n')
        with self.assertRaises(Exception):
            deployed.apply(publisher, artifact, push=False)
        self.assertIn('Human edits are preserved.', target.read_text())

    def test_unconfirmed_topic_cannot_start_writing(self):
        with self.assertRaises(store.OfflineError):
            writing.run(self.root, 'approval-20261101-000000-aaaaaaaaaaaa', client=self.client,
                        refresh=lambda: True, max_new_calls=6)
        self.assertEqual(self.client.calls, [])

    def test_separate_confirmation_checkout_reads_bound_private_config(self):
        directory = tempfile.TemporaryDirectory(prefix='researchdesk-page-binding-')
        self.addCleanup(directory.cleanup)
        target = Path(directory.name).resolve()
        subprocess.run(['git', 'init', '-b', 'main', str(target)], check=True, capture_output=True)
        page.bind_workbench(self.root, target)
        config = page.load_config(target)
        self.assertEqual(config['workbench_id'], 'fixture-workbench')
        self.assertEqual(config['_config_sha256'], page.load_config(self.root)['_config_sha256'])
        self.assertFalse((target / 'config').exists())
        self.assertNotIn('models', (target / '.git/researchdesk-workbench.json').read_text())


if __name__ == '__main__':
    unittest.main()
