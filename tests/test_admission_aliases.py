"""Replay the actual October 27 renderer without replacing identity validation.

This tests the deterministic promotion boundary, not live source revalidation.
No plan or accepted marker is created by these tests.
"""
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest import mock
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import researchdesk_admission as admission
import researchdesk_batch as research
import researchdesk_identity as identity
import researchdesk_insight as insight
import researchdesk_insight_inputs as inputs
import researchdesk_offline as store

CYCLE = 'agent-memory-20261027-0300'
FORMAL = 'blog-05c33166-b18e-425e-91e0-36ddd26f21aa'
ALIAS = 'blog-be47c817-56d3-4fa5-bb9a-bd19be5c68df'


@unittest.skipUnless(
    (ROOT / ('reports/agent-memory/admissions/' + CYCLE + '/plan.yaml')).is_file(),
    'Historical October 27 production proof was explicitly reset; generic admission tests remain active')
class October27Aliases(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        # Replay before this cycle's admission even after its real outputs
        # have been added to the repository. Earlier alias proofs stay intact.
        base = 'reports/agent-memory/admissions/' + CYCLE + '/'
        stored_plan = ROOT / (base + 'plan.yaml')
        omitted = set()
        if stored_plan.is_file():
            omitted.update(yaml.safe_load(stored_plan.read_text())['files'])
            omitted.update(base + name for name in ('accepted.yaml', 'accepted.yaml.sha256'))

        def ignore(directory, names):
            relative = Path(directory).relative_to(ROOT)
            return [name for name in names if (relative / name).as_posix() in omitted]

        for folder in ('config', 'sources', 'reports', 'insights', 'articles'):
            shutil.copytree(ROOT / folder, self.root / folder, ignore=ignore)
        base = 'reports/test/agent-memory/insight-runs/' + CYCLE
        manifest = store.checked_yaml(self.root, base + '/manifest.yaml')
        self.bundle = {'input_fingerprint': manifest['input_fingerprint'],
                       'evidence': sum(manifest['provenance'].values(), [])}
        self.config = inputs.load_config(self.root, 'reports/test/agent-memory/cycles/' + CYCLE + '/configs/insight.yaml')
        self.candidate = insight.parse_response(store.checked_yaml(self.root, base + '/checkpoints/generation-0.yaml')['result']['text'], 'generation')
        self.records = []
        for proof in manifest['provenance']['research_inputs']:
            original = store.checked_yaml(self.root, proof['candidate_path'])['candidate']
            item = str(Path(proof['candidate_path']).parent)
            batch = str(Path(proof['manifest']).parent)
            result = store.checked_yaml(self.root, item + '/result.yaml')
            revision = result['revision_count']
            read = lambda role: research.parse_result(store.checked_yaml(self.root, item + '/checkpoints/%s-%s.yaml' % (role, revision))['result']['text'])
            self.records.append({'candidate': original, 'research': read('research'), 'review': read('review'),
                                 'revision': revision, 'manifest': store.checked_yaml(self.root, batch + '/manifest.yaml'),
                                 'report_path': proof['path']})

    def render(self):
        return admission._render(self.root, 'agent-memory', CYCLE, self.config, self.bundle, self.candidate, self.records)

    def test_historical_alias_is_reused_and_all_formal_links_resolve(self):
        before = research.notes_snapshot(self.root)
        # The pre-fix implementation reproducibly rejects this exact data.
        with mock.patch.object(identity, 'source_index', side_effect=store.source_index):
            with self.assertRaisesRegex(store.OfflineError, '正式与测试来源存在多个身份ID'):
                self.render()
        files, mapping = self.render()
        self.assertEqual(mapping[FORMAL], FORMAL)
        self.assertNotIn('sources/blogs/agent-memory/' + FORMAL + '.md', files)
        self.assertIn('reports/agent-memory/' + CYCLE + '-update-' + FORMAL + '.md', files)
        self.assertEqual(len(files), 10)
        self.assertFalse(any('/test/' in path for path in files))
        admission._check_links(self.root, files, admission._base('agent-memory', CYCLE) + '/accepted.yaml')
        research.verify_notes(self.root, before)

    def test_unproved_alias_still_fails_closed(self):
        marker = self.root / 'reports/agent-memory/admissions/cycle-agent-memory-gh-20261019/accepted.yaml'
        marker.unlink()
        with self.assertRaisesRegex(store.OfflineError, '正式与测试来源存在多个身份ID'):
            self.render()

    def test_tampered_acceptance_checksum_is_rejected(self):
        marker = self.root / 'reports/agent-memory/admissions/cycle-agent-memory-gh-20261019/accepted.yaml.sha256'
        marker.write_text('0' * 64 + '\n')
        with self.assertRaisesRegex(store.OfflineError, '正式准入记录散列无效'):
            self.render()


if __name__ == '__main__':
    unittest.main()
