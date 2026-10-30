"""Full-text cycle policy propagation and PDF fallback through real fake-model stages."""

import sys
from types import SimpleNamespace
import unittest
from unittest import mock

import yaml

import test_cycle as fixtures
from test_fulltext_review import FulltextFetcher
from test_insight import FakeInsightClient
import researchdesk_offline as store


class PdfCycleFetcher(FulltextFetcher):
    def __init__(self):
        super().__init__()
        self.fulltext_unavailable = True
        self.pdf_calls = []

    def fetch_pdf(self, url):
        self.pdf_calls.append(url)
        return {'url': url, 'requested_url': url, 'redirects': [], 'status': 200,
                'content_type': 'application/pdf', 'body': b'%PDF-fictional-cycle-fixture'}


class FulltextCycle(unittest.TestCase):
    def setUp(self):
        # Keep the existing temporary-vault, discovery and history fixtures.
        fixtures.ResearchInsightCycle.setUp(self)
        self.config['reading'] = {'mode': 'full_text_preferred', 'paper_max_chars': 80000}
        self.config['budget']['max_input_chars'] = 500000
        self.config_path.write_text(yaml.safe_dump(self.config, allow_unicode=True, sort_keys=False))
        self.fetcher = FulltextFetcher()

    def run_cycle(self, **kwargs):
        return self.cycle.run(self.root, self.config_path, 'first', client=self.client,
                              fetcher=self.fetcher, **kwargs)

    def fake_research(self, *args, **kwargs):
        return fixtures.ResearchInsightCycle.fake_research(self, *args, **kwargs)

    def fake_insight(self, *args, **kwargs):
        return fixtures.ResearchInsightCycle.fake_insight(self, *args, **kwargs)

    def test_new_cycle_policy_flows_to_paper_and_child_configs(self):
        result = self.run_cycle()
        self.assertEqual(result['status'], 'completed')
        base = 'reports/test/custom-topic/cycles/first/'
        selection = store.checked_yaml(self.root, base + 'selection.yaml')
        paper, blog = [item['source'] for item in selection['candidates']]
        self.assertEqual(paper['reading'], {'mode': 'full_text_preferred'})
        self.assertEqual(paper['evidence_max_chars'], 80000)
        self.assertNotIn('reading', blog)
        self.assertEqual(blog['evidence_max_chars'], 6000)
        research = store.checked_yaml(self.root, base + 'configs/research.yaml')
        insight = store.checked_yaml(self.root, base + 'configs/insight.yaml')
        self.assertEqual(research['sources'], [paper, blog])
        self.assertEqual(research['prompts']['version'], 'research-batch-v2')
        self.assertEqual(insight['prompts']['version'], 'insight-v3')
        self.assertEqual(research['budget']['max_input_chars'], 500000)
        self.assertEqual(insight['budget']['max_input_chars'], 500000)
        self.client.infer.assert_not_called()

    def test_pdf_fallback_is_cached_across_real_stages_and_completed_replay(self):
        self.research_run.side_effect = self.real_research_run
        self.insight_run.side_effect = self.real_insight_run
        self.client = fixtures.FiveSourceClient()
        # This two-source cycle needs only the first two source comparisons.
        self.client.synthesis = FakeInsightClient.synthesis
        def scope_response(value):
            if 'claims' in value:
                coverage = self.client.calls[-1]['payload']['coverage']
                value['limitations'] = ['读取抽取全文文本；未独立复现实验。' if coverage == 'full_text'
                                        else '仅读取博客节选，未独立复现实验。']
            else:
                value['coverage_note'] = 'R1读取PDF全文文本，R2读取博客节选，H1为历史人工基线；未复现实验。'
        self.client.research_mutator = scope_response
        self.fetcher = PdfCycleFetcher()
        text = 'arXiv:2610.01234v2\n1 Method\n' + self.fetcher.body + '\n2 Limitations\n' + self.fetcher.body
        reader = SimpleNamespace(is_encrypted=False, pages=[SimpleNamespace(extract_text=lambda: text)])
        with mock.patch.dict(sys.modules, {'pypdf': SimpleNamespace(PdfReader=lambda *a, **kw: reader)}):
            result = self.run_cycle()
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['reserved_calls'], 6)
        self.assertEqual(self.fetcher.pdf_calls, ['https://arxiv.org/pdf/2610.01234v2'])
        plan = store.checked_yaml(self.root,
            'reports/test/custom-topic/research-batches/first/items/paper-one/candidate.yaml')
        self.assertEqual(plan['candidate']['evidence']['format'], 'pdf')
        self.assertEqual(plan['candidate']['evidence']['coverage'], 'full_text')
        calls = [item['payload'] for item in self.client.calls]
        self.assertEqual(calls[0]['original_material'], calls[1]['original_material'])
        self.assertEqual(calls[4]['evidence'][0]['original_material'], calls[0]['original_material'])
        before_calls, before_fetches = len(self.client.calls), list(self.fetcher.pdf_calls)
        replay = self.run_cycle()
        self.assertTrue(replay['cached'])
        self.assertEqual(len(self.client.calls), before_calls)
        self.assertEqual(self.fetcher.pdf_calls, before_fetches)

    def test_live_policy_upgrade_does_not_replace_frozen_cycle_budget(self):
        self.run_cycle()
        before = store.checked_yaml(self.root, 'reports/test/custom-topic/cycles/first/manifest.yaml')
        self.config['reading']['paper_max_chars'] = 120000
        self.config['budget']['max_input_chars'] = 600000
        self.config_path.write_text(yaml.safe_dump(self.config, allow_unicode=True, sort_keys=False))
        result = self.run_cycle()
        self.assertTrue(result['cached'])
        after = store.checked_yaml(self.root, 'reports/test/custom-topic/cycles/first/manifest.yaml')
        self.assertEqual(before, after)
        self.assertEqual(after['config']['budget']['max_input_chars'], 500000)
        self.research_run.assert_called_once()
        self.insight_run.assert_called_once()

    def test_misplaced_cycle_snapshot_cannot_change_topic_or_cycle_identity(self):
        self.run_cycle()
        path = self.root / 'reports/test/custom-topic/cycles/first/manifest.yaml'
        original = yaml.safe_load(path.read_text())
        import copy
        for field, changed in [('topic', 'different-topic'), ('cycle_id', 'different-cycle'),
                               ('mode', 'different-mode'), ('backend', 'mock'),
                               ('production_accepted', True), ('config_topic', 'different-topic')]:
            with self.subTest(field=field):
                manifest = copy.deepcopy(original)
                if field == 'config_topic':
                    manifest['config']['topic'] = changed
                else:
                    manifest[field] = changed
                path.write_text(yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False))
                path.with_name(path.name + '.sha256').write_text(store.digest(path.read_bytes()) + '\n')
                with self.assertRaises(store.OfflineError):
                    self.run_cycle()

    def test_legacy_unselected_cycle_cannot_inherit_future_pending_reading_policy(self):
        self.config.pop('reading')
        self.config['budget']['max_input_chars'] = 30000
        self.config_path.write_text(yaml.safe_dump(self.config, allow_unicode=True, sort_keys=False))
        self.cycle.discover_cycle(self.root, self.config_path, 'first', fetcher=self.fetcher)
        pending_source = dict(self.snapshot['candidates'][0]['source'], id='future-paper',
                              reading={'mode': 'full_text_preferred'}, evidence_max_chars=80000)
        store.save_yaml(self.root, 'reports/test/custom-topic/cycles/future/pending.yaml',
                        {'items': [{'source': pending_source}]})
        result = self.run_cycle()
        self.assertEqual(result['status'], 'completed')
        child = store.checked_yaml(self.root, 'reports/test/custom-topic/cycles/first/configs/research.yaml')
        self.assertEqual(child['prompts']['version'], 'research-batch-v1')
        self.assertEqual(child['sources'][0]['id'], 'future-paper')
        self.assertNotIn('reading', child['sources'][0])
        self.assertEqual(child['sources'][0]['evidence_max_chars'], 6000)


if __name__ == '__main__':
    unittest.main()
