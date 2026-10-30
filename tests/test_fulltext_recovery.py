"""Full-text linked recovery retains frozen reading evidence and budget limits."""

import unittest
from unittest import mock

import yaml

import test_fulltext_cycle as cycle_fixture
import test_recovery as recovery_fixture
from test_insight import FakeInsightClient
import researchdesk_insight_inputs as inputs
import researchdesk_offline as store
import researchdesk_recovery as recovery


class FulltextRecovery(unittest.TestCase):
    fake_research = cycle_fixture.FulltextCycle.fake_research
    fake_insight = cycle_fixture.FulltextCycle.fake_insight

    def setUp(self):
        cycle_fixture.FulltextCycle.setUp(self)
        if getattr(self, 'archive_enabled', False):
            self.config['archive'] = True
        self.config['budget']['max_calls_per_cycle'] = 16
        self.config_path.write_text(yaml.safe_dump(self.config, allow_unicode=True, sort_keys=False))
        self.research_run.side_effect = self.real_research_run
        self.insight_run.side_effect = self.real_insight_run
        self.old_client = recovery_fixture.StageClient()
        self.old_client.research.review_decisions = ['pass', 'pass']
        self.old_client.insight.generation_text_overrides = []
        self.old_client.insight.review_decisions = ['reject']
        def research_scope(value):
            coverage = self.old_client.research.calls[-1]['payload']['coverage']
            value['limitations'] = ['读取抽取全文文本，未独立复现实验。' if coverage == 'full_text'
                                    else '仅读取博客节选，未独立复现实验。']
        self.old_client.research.research_mutator = research_scope
        self.old_client.insight.research_mutator = self.insight_scope
        original = self.cycle.run(self.root, self.config_path, 'first', client=self.old_client,
                                  fetcher=self.fetcher)
        self.assertEqual(original['status'], 'insight_blocked')
        self.assertEqual(original['reserved_calls'], 6)
        self.client = FakeInsightClient()
        self.client.research_mutator = self.insight_scope
        self.identifier = 'first-recovery-1'
        self.base = 'reports/test/custom-topic/cycles/' + self.identifier
        self.request = recovery.make_request(self.root, self.config_path, 'first')
        path = self.root / 'config/recoveries/first.yaml'
        path.parent.mkdir(parents=True)
        path.write_text(yaml.safe_dump(self.request, allow_unicode=True, sort_keys=False))
        self.original_bytes = {relative: (self.root / relative).read_bytes()
                               for relative in self.request['original_files']}

    @staticmethod
    def insight_scope(value):
        value['coverage_note'] = 'R1读取抽取全文文本，R2为博客节选，H1为历史人工基线，未复现实验。'

    def test_fulltext_recovery_keeps_v3_and_exact_body_without_repeating_research(self):
        self.assertEqual(self.request['prompt_version'], 'insight-v3')
        result = recovery.run(self.root, self.config_path, 'first', self.client, fetcher=self.fetcher)
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['new_reserved_calls'], 2)
        self.assertEqual(result['reserved_calls'], 8)
        self.assertEqual(len(self.old_client.research.calls), 4)
        self.assertEqual(len(self.client.calls), 2)
        new_config = inputs.load_config(self.root, self.base + '/configs/insight.yaml')
        self.assertEqual(new_config['prompts']['version'], 'insight-v3')
        self.assertEqual(new_config['budget']['max_input_chars'], 500000)
        lineage = recovery.verify_lineage(self.root, 'custom-topic', self.identifier)
        self.assertEqual(lineage['prompt_version'], 'insight-v3')
        current = self.client.calls[0]['payload']['evidence'][0]
        old = self.old_client.insight.calls[0]['payload']['evidence'][0]
        for key in ('coverage', 'reading_scope', 'acquisition_attempts', 'original_material', 'locators'):
            self.assertEqual(current[key], old[key])
        projected = lineage['verification_bundle']['evidence'][0]
        self.assertEqual(projected['reading_scope'], current['reading_scope'])
        self.assertEqual(projected['acquisition_attempts'], current['acquisition_attempts'])
        with mock.patch.object(self.fetcher, 'fetch', side_effect=AssertionError('Offline lineage may not fetch')):
            recovery.verify_lineage(self.root, 'custom-topic', self.identifier)
        replay = recovery.run(self.root, self.config_path, 'first', self.client, fetcher=self.fetcher)
        self.assertTrue(replay['cached'])
        self.assertEqual(len(self.client.calls), 2)
        self.assertEqual(len(self.old_client.research.calls), 4)
        self.assertEqual(self.original_bytes,
                         {relative: (self.root / relative).read_bytes() for relative in self.original_bytes})

    def test_legacy_prompt_upgrade_stays_v2(self):
        for original in ('insight-v1', 'insight-v2'):
            self.assertEqual(recovery._prompt_version({'prompts': {'version': original}}), 'insight-v2')
        self.assertEqual(recovery._prompt_version({'prompts': {'version': 'insight-v3'}}), 'insight-v3')
        with self.assertRaises(store.OfflineError):
            recovery._prompt_version({'prompts': {'version': 'unknown'}})

    def test_live_config_upgrade_preserves_original_request_and_recovery_limits(self):
        self.config['budget']['max_input_chars'] = 600000
        self.config['budget']['max_calls_per_cycle'] = 20
        self.config['reading']['paper_max_chars'] = 120000
        self.config_path.write_text(yaml.safe_dump(self.config, allow_unicode=True, sort_keys=False))
        self.assertEqual(recovery.make_request(self.root, self.config_path, 'first'), self.request)
        self.assertEqual(recovery.requested(self.root, self.config_path, 'first'), self.identifier)
        result = recovery.run(self.root, self.config_path, 'first', self.client, fetcher=self.fetcher)
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(len(self.client.calls), 2)
        frozen = inputs.load_config(self.root, self.base + '/configs/insight.yaml')
        self.assertEqual(frozen['budget']['max_input_chars'], 500000)
        self.assertEqual(recovery.verify_lineage(self.root, 'custom-topic', self.identifier)['max_calls_per_cycle'], 16)
        self.assertEqual(self.original_bytes,
                         {relative: (self.root / relative).read_bytes() for relative in self.original_bytes})


class ArchivedFulltextRecovery(unittest.TestCase):
    """Reuse the real failed-cycle fixture, changing only its archive policy."""

    archive_enabled = True
    setUp = FulltextRecovery.setUp
    fake_research = FulltextRecovery.fake_research
    fake_insight = FulltextRecovery.fake_insight
    insight_scope = staticmethod(FulltextRecovery.insight_scope)

    def test_linked_recovery_uses_immutable_archives_with_all_fetches_offline(self):
        originals = [relative for relative in self.request['original_files']
                     if relative.endswith(('/original.yaml', '/original.yaml.sha256', '/original.md'))]
        self.assertEqual(len(originals), 6)  # Two exact originals, hashes and reading views.
        with mock.patch.object(self.fetcher, 'fetch', side_effect=AssertionError('Recovery must replay archives')) as fetch, \
                mock.patch.object(self.fetcher, 'fetch_pdf', side_effect=AssertionError('Recovery must not download PDFs')) as pdf:
            result = recovery.run(self.root, self.config_path, 'first', self.client, fetcher=self.fetcher)
            self.assertEqual(result['status'], 'completed')
            self.assertEqual(result['new_reserved_calls'], 2)
            self.assertEqual(result['reserved_calls'], 8)
            lineage = recovery.verify_lineage(self.root, 'custom-topic', self.identifier)
            self.assertTrue(set(originals).issubset(lineage['original_files']))
            self.assertTrue(recovery.run(self.root, self.config_path, 'first', self.client, fetcher=self.fetcher)['cached'])
            fetch.assert_not_called()
            pdf.assert_not_called()
        self.assertEqual(len(self.old_client.research.calls), 4)
        self.assertEqual(len(self.client.calls), 2)
        self.assertEqual(self.original_bytes,
                         {relative: (self.root / relative).read_bytes() for relative in self.original_bytes})
        old = self.old_client.insight.calls[0]['payload']['evidence'][0]
        current = self.client.calls[0]['payload']['evidence'][0]
        self.assertEqual(old['original_material'], current['original_material'])


if __name__ == '__main__':
    unittest.main()
