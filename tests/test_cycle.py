"""Five offline orchestration checks; Research and Insight are stubbed locally."""

import copy
import importlib
from pathlib import Path
import socket
import sys
import tempfile
import unittest
from unittest import mock

import yaml


REPOSITORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY / 'scripts'))
import researchdesk_offline as store
from test_research_batch import FakeMemberClient, FixtureFetcher


class ResearchInsightCycle(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='researchdesk-cycle-tests-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        for directory in ('config/cycles', 'sources/papers', 'sources/blogs',
                          'reports/test/custom-topic', 'insights', 'articles'):
            (self.root / directory).mkdir(parents=True, exist_ok=True)
        (self.root / 'config/research_topics.yaml').write_text(yaml.safe_dump({
            'schema_version': 1, 'topics': {'custom-topic': {
                'name': 'Cycle Fixture', 'enabled': True, 'description': '离线编排测试。',
                'scope': ['可追溯研究'], 'keywords': ['memory']}}}, allow_unicode=True))
        (self.root / 'config/membership_budget.yaml').write_text(yaml.safe_dump({
            'schema_version': 1, 'backend': 'chatgpt_plan', 'month_max_calls': 100}))
        self.config = {
            'schema_version': 1, 'mode': 'research_cycle_test', 'backend': 'chatgpt_plan',
            'topic': 'custom-topic', 'topics_file': 'config/research_topics.yaml',
            'window': {'initial_days': 7, 'overlap_hours': 48},
            'discovery': {'max_candidates': 20, 'max_documents': 2, 'max_per_source': 1,
                          'evidence_max_chars': 6000, 'sources': [
                              {'id': 'arxiv', 'adapter': 'arxiv',
                               'entry_url': 'https://export.arxiv.org/api/query'},
                              {'id': 'letta', 'adapter': 'letta',
                               'entry_url': 'https://www.letta.com/blog/'}]},
            'models': {'research': 'fixture-research', 'insight': 'fixture-research',
                       'review': 'fixture-review'},
            'budget': {'max_calls_per_cycle': 10, 'research_max_calls': 6,
                       'insight_max_calls': 4, 'max_input_chars': 30000,
                       'max_output_chars': 8000, 'timeout_seconds': 120,
                       'max_revisions': 1}, 'history': {'max_documents': 6}}
        self.config_path = self.root / 'config/cycles/custom-topic.yaml'
        self.config_path.write_text(yaml.safe_dump(self.config, allow_unicode=True, sort_keys=False))
        self.snapshot = {
            'schema_version': 1, 'mode': 'cycle_discovery_test', 'topic': 'custom-topic',
            'cycle_id': 'first', 'status': 'complete',
            'window_start': '2026-10-12T00:00:00+00:00',
            'window_end': '2026-10-19T00:00:00+00:00',
            'candidates': [
                {'source': {'id': 'paper-one', 'adapter': 'arxiv', 'kind': 'paper',
                            'url': 'https://export.arxiv.org/api/query?id_list=2610.01234v2',
                            'evidence_max_chars': 6000}},
                {'source': {'id': 'blog-one', 'adapter': 'letta', 'kind': 'blog',
                            'url': 'https://www.letta.com/blog/fixture-memory',
                            'evidence_max_chars': 6000}}],
            'deferred': [], 'source_status': [
                {'id': 'arxiv', 'status': 'complete', 'complete_window': True},
                {'id': 'letta', 'status': 'complete', 'complete_window': True}],
            'production_accepted': False}
        historical_source = REPOSITORY / 'sources/papers/paper-4eb3be4b-7189-49aa-bafd-f88f77a972f4.md'
        frontmatter, body = historical_source.read_text().split('---', 2)[1:]
        metadata = yaml.safe_load(frontmatter)
        metadata.update(topics=['custom-topic'], related_sources=[], related_notes=[])
        history = self.root / 'sources/papers' / historical_source.name
        history.write_text('---\n' + yaml.safe_dump(metadata, allow_unicode=True, sort_keys=False) + '---' + body)
        self.history = [{'path': history.relative_to(self.root).as_posix(),
                         'sha256': store.digest(history.read_bytes()), 'origin': 'human_baseline'}]
        self.client = FakeMemberClient()
        self.client.infer = mock.Mock(side_effect=AssertionError('Model inference prohibited'))
        self.fetcher = FixtureFetcher()
        self.addCleanup(mock.patch.stopall)
        mock.patch.object(socket, 'create_connection',
                          side_effect=AssertionError('Network prohibited')).start()
        mock.patch.object(socket.socket, 'connect',
                          side_effect=AssertionError('Network prohibited')).start()
        self.cycle = importlib.import_module('researchdesk_cycle')
        self.discovery = mock.patch.object(self.cycle.discovery, 'discover',
                                           side_effect=lambda *a, **k: copy.deepcopy(self.snapshot)).start()
        self.history_selection = mock.patch.object(self.cycle.discovery, 'select_history',
                                                   return_value=self.history).start()
        self.research_run = mock.patch.object(self.cycle.research, 'run',
                                              side_effect=self.fake_research).start()
        self.insight_run = mock.patch.object(self.cycle.insight, 'run',
                                             side_effect=self.fake_insight).start()

    def fake_research(self, root, config_path, batch_id, *args, **kwargs):
        path = Path(config_path)
        config = yaml.safe_load((path if path.is_absolute() else Path(root) / path).read_text())
        base = 'reports/test/custom-topic/research-batches/' + batch_id
        result = {'status': 'test_accepted', 'topic': 'custom-topic',
                  'backend': 'chatgpt_plan', 'production_accepted': False,
                  'reserved_calls': len(config['sources']) * 2,
                  'completed_calls': len(config['sources']) * 2,
                  'items': [{'key': source['id'], 'status': 'test_accepted'}
                            for source in config['sources']],
                  'receipt_path': base + '/receipt-attempt-1.yaml'}
        store.save_yaml(Path(root), result['receipt_path'], result)
        return result

    def fake_insight(self, root, config_path, batch_id, *args, **kwargs):
        result = {'status': 'test_accepted', 'topic': 'custom-topic',
                  'backend': 'chatgpt_plan', 'production_accepted': False,
                  'reserved_calls': 2, 'completed_calls': 2, 'output_hashes': {},
                  'writing_started': False, 'approval_required': True}
        store.save_yaml(Path(root), 'reports/test/custom-topic/insight-runs/' + batch_id + '/receipt.yaml', result)
        return result

    def run_cycle(self, **kwargs):
        return self.cycle.run(self.root, self.config_path, 'first', client=self.client,
                              fetcher=self.fetcher, **kwargs)

    def test_one_entry_runs_research_then_insight(self):
        result = self.run_cycle()
        self.assertEqual(result['status'], 'completed')
        self.research_run.assert_called_once()
        self.insight_run.assert_called_once()
        self.client.infer.assert_not_called()
        self.assertFalse((self.root / '.github').exists())

    def test_same_cycle_id_is_cached_without_new_child_or_model_calls(self):
        first = self.run_cycle()
        second = self.run_cycle()
        self.assertEqual(first['status'], second['status'])
        self.discovery.assert_called_once()
        self.research_run.assert_called_once()
        self.insight_run.assert_called_once()
        self.client.infer.assert_not_called()

    def test_after_research_resume_only_continues_insight(self):
        with self.assertRaises(store.SimulatedInterruption):
            self.run_cycle(fail_after='after_research')
        self.research_run.assert_called_once()
        self.insight_run.assert_not_called()
        result = self.run_cycle()
        self.assertEqual(result['status'], 'completed')
        self.research_run.assert_called_once()
        self.insight_run.assert_called_once()
        self.client.infer.assert_not_called()

    def test_no_new_discovery_never_calls_research_or_insight(self):
        self.snapshot['candidates'] = []
        result = self.run_cycle()
        self.assertEqual(result['status'], 'no_new')
        self.research_run.assert_not_called()
        self.insight_run.assert_not_called()
        self.client.infer.assert_not_called()

    def test_source_failure_is_recorded_without_claiming_complete_cycle(self):
        self.snapshot['status'] = 'partial'
        self.snapshot['source_status'][1].update(status='failed', complete_window=False,
                                                 error_type='SyntheticSourceError')
        self.snapshot['candidates'] = self.snapshot['candidates'][:1]
        result = self.run_cycle()
        self.assertEqual(result['status'], 'partial')
        self.assertIn('failed', str(result))
        self.client.infer.assert_not_called()


if __name__ == '__main__':
    unittest.main()
