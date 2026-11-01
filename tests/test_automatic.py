"""Persistent scheduled orchestration; sources/models/auth are all injected."""

from datetime import datetime
import json
from pathlib import Path
import socket
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import researchdesk_automatic as automatic
import researchdesk_membership as membership
import researchdesk_offline as store
import researchdesk_workbench as workbench


class ScheduledPipeline(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='researchdesk-automatic-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        (self.root / 'config').mkdir()
        (self.root / workbench.SYSTEM_CONFIG).write_bytes((workbench.REPOSITORY / workbench.SYSTEM_CONFIG).read_bytes())
        workbench.initialize(self.root)
        for target, name in ((socket, 'create_connection'), (socket.socket, 'connect'),
                             (membership, 'MembershipClient')):
            guard = patch.object(target, name, side_effect=AssertionError('No real source, auth or model access'))
            guard.start()
            self.addCleanup(guard.stop)
        self.collector = Mock(return_value={'status': 'collected', 'records': [{'key': 'paper'}],
                                            'discovery_status': 'complete'})
        self.researcher = Mock(return_value={'status': 'complete',
            'items': [{'status': 'summarized'}], 'summary_paths': ['summary.md'],
            'reserved_calls': 2, 'completed_calls': 2})
        self.insight = Mock(return_value={'status': 'complete', 'model_request_count': 2,
                                          'receipt_path': 'accepted.yaml'})
        self.health = Mock(return_value={'membership_authorized': True, 'model_calls': 0})
        self.now = datetime.fromisoformat('2026-11-06T09:00:00+08:00')

    def local(self):
        return yaml.safe_load((self.root / workbench.LOCAL_CONFIG).read_text())

    def update(self, changes):
        value = workbench.merge_config(self.local(), changes)
        workbench._write(self.root / workbench.LOCAL_CONFIG, workbench._yaml(value))

    def run_pipeline(self, **kwargs):
        return automatic.run(self.root, collector=self.collector, researcher=self.researcher,
                             insight_runner=self.insight, health_checker=self.health, now=self.now, **kwargs)

    def test_disabled_schedule_never_initializes_sources_or_membership(self):
        result = self.run_pipeline()
        self.assertEqual(result['status'], 'skipped')
        self.assertEqual(result['reason'], 'automation_disabled')
        self.assertIsNone(result['receipt_path'])
        self.collector.assert_not_called()
        self.researcher.assert_not_called()
        self.insight.assert_not_called()

    def test_latest_slot_runs_once_and_freezes_selected_topic_without_private_configuration(self):
        private_profile = str(self.root.parent / 'private-member-profile')
        self.update({'automation': {'enabled': True},
            'runtime': {'membership': {'profile': private_profile}},
            'writing_style': 'PRIVATE AUTHOR STYLE MUST STAY LOCAL',
            'research_topics': {'topics': {'private_direction': {
                'name': 'Private unrelated direction', 'enabled': False,
                'description': 'Must not appear in public evidence context.',
                'scope': ['Private plans'], 'keywords': ['private-word']}}}})
        result = self.run_pipeline()
        self.assertEqual(result['status'], 'complete')
        self.assertTrue(result['terminal'])
        self.assertEqual(result['cycle_id'], 'agent_memory-20261106-0300')
        self.assertEqual(result['collection_count'], 1)
        self.assertEqual(result['summary_count'], 1)
        self.assertNotIn('model_calls', result, 'real execution cannot falsely report zero calls')
        context = store.checked_yaml(self.root, result['context_path'])
        self.assertEqual(set(context['selected_topic']['topics']), {'agent_memory'})
        self.assertEqual(set(yaml.safe_load(context['topics_yaml_text'])['topics']), {'agent_memory'})
        public_text = json.dumps(context)
        for forbidden in ('private_direction', private_profile, 'PRIVATE AUTHOR STYLE', 'state_directory'):
            self.assertNotIn(forbidden, public_text)
        self.assertTrue(context['research_config_path'].startswith('config/local/automation/'))
        self.assertEqual(self.collector.call_args.args[1], context['research_config_path'])
        self.assertEqual(self.researcher.call_args.kwargs['profile'], Path(private_profile))
        self.assertEqual(self.insight.call_args.args[1], context['insight_config_path'])
        second = self.run_pipeline()
        self.assertTrue(second['cached'])
        self.assertEqual(second['cycle_id'], result['cycle_id'])
        self.assertEqual(self.collector.call_count, 1)
        self.assertEqual(self.researcher.call_count, 1)
        self.assertEqual(self.insight.call_count, 1)

    def test_user_and_system_edits_automatically_apply_to_the_next_new_round(self):
        self.run_pipeline(event='manual', cycle_id='first')
        self.update({'research': {'discovery': {'max_documents': 2}}})
        inherited = self.local()
        inherited['research'].pop('window')
        workbench._write(self.root / workbench.LOCAL_CONFIG, workbench._yaml(inherited))
        system = yaml.safe_load((self.root / workbench.SYSTEM_CONFIG).read_text())
        system['research']['window']['days'] = 45
        (self.root / workbench.SYSTEM_CONFIG).write_bytes(workbench._yaml(system))
        seen = []
        self.collector.side_effect = lambda root, path, identity: (
            seen.append(store.load_yaml(root / path)) or
            {'status': 'empty', 'records': [], 'discovery_status': 'complete'})
        result = self.run_pipeline(event='manual', cycle_id='second')
        self.assertEqual(result['status'], 'no_new')
        self.assertEqual(seen[0]['discovery']['max_documents'], 2)
        self.assertEqual(seen[0]['window']['days'], 45)
        self.assertEqual(self.insight.call_count, 1)

    def test_changed_configuration_blocks_only_the_old_incomplete_round_without_new_calls(self):
        self.researcher.side_effect = store.OfflineError('Private provider failure')
        first = self.run_pipeline(event='manual', cycle_id='first')
        self.assertEqual(first['status'], 'failed')
        self.assertFalse(first['terminal'])
        self.assertFalse((self.root / automatic._base('agent_memory', 'first') / 'receipt.yaml').exists())
        self.update({'models': {'generation': 'fixture-new-generator'}})
        second = self.run_pipeline(event='manual', cycle_id='first')
        self.assertEqual(second['status'], 'blocked')
        self.assertEqual(second['reason'], 'configuration_changed')
        self.assertEqual(self.collector.call_count, 1)
        self.assertEqual(self.researcher.call_count, 1)
        self.insight.assert_not_called()
        self.researcher.side_effect = None
        newer = self.run_pipeline(event='manual', cycle_id='next-cycle')
        self.assertEqual(newer['status'], 'complete')
        self.assertEqual(self.researcher.call_count, 2)

    def test_unchanged_interrupted_round_reuses_frozen_config_and_keeps_attempts(self):
        self.insight.side_effect = [store.OfflineError('Network interrupted'),
                                    {'status': 'complete', 'model_request_count': 2}]
        first = self.run_pipeline(event='manual', cycle_id='first')
        old_receipt = (self.root / first['receipt_path']).read_bytes()
        context = (self.root / first['context_path']).read_bytes()
        second = self.run_pipeline(event='manual', cycle_id='first')
        self.assertEqual(second['status'], 'complete')
        self.assertEqual((self.root / first['receipt_path']).read_bytes(), old_receipt)
        self.assertEqual((self.root / first['context_path']).read_bytes(), context)
        self.assertEqual(self.insight.call_count, 2)
        self.assertEqual(self.collector.call_args_list[0].args, self.collector.call_args_list[1].args)
        self.assertEqual(second['attempt'], 2)

    def test_prepare_runs_under_the_pipeline_lock_before_reading_configuration(self):
        calls = []
        def prepare():
            with self.assertRaises(store.OfflineError):
                with automatic.pipeline_lock(self.root):
                    self.fail('The whole workbench must already be locked')
            self.update({'automation': {'enabled': True}})
            calls.append('prepared')
        result = self.run_pipeline(prepare=prepare)
        self.assertEqual(calls, ['prepared'])
        self.assertEqual(result['status'], 'complete')

    def test_rejected_research_stops_before_insight_and_failed_collection_is_not_no_new(self):
        self.researcher.return_value = {'status': 'failed', 'items': [{'status': 'reject'}], 'summary_paths': []}
        rejected = self.run_pipeline(event='manual', cycle_id='rejected')
        self.assertEqual(rejected['status'], 'research_rejected')
        self.assertTrue(rejected['terminal'])
        self.insight.assert_not_called()
        self.collector.return_value = {'status': 'empty', 'records': [], 'discovery_status': 'failed'}
        missing = self.run_pipeline(event='manual', cycle_id='missing')
        self.assertEqual(missing['status'], 'collection_incomplete')
        self.assertFalse(missing['terminal'])

    def test_sdk_or_authorization_failure_stops_before_spending_research_calls(self):
        self.health.side_effect = store.OfflineError('SDK not ready')
        result = self.run_pipeline(event='manual', cycle_id='not-ready')
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(result['failed_stage'], 'health')
        self.assertFalse(result['terminal'])
        self.researcher.assert_not_called()
        self.insight.assert_not_called()
        collected = self.run_pipeline(event='manual', operation='collect', cycle_id='collect-only')
        self.assertEqual(collected['status'], 'collected')
        self.assertEqual(collected['model_calls'], 0)
        self.assertEqual(self.health.call_count, 1)

    def test_deployment_start_marker_prevents_historical_startup_and_explicit_catchup_uses_oldest_slot(self):
        self.update({'automation': {'enabled': True, 'activated_at': '2026-10-01T00:00:00+08:00'}})
        marker = self.root / 'config/local/deployment-started-at.json'
        marker.write_text(json.dumps({'started_at': '2026-11-05T12:00:00+08:00'}))
        result = self.run_pipeline()
        self.assertEqual(result['cycle_id'], 'agent_memory-20261106-0300')
        marker.write_text(json.dumps({'started_at': '2026-11-06T12:00:00+08:00'}))
        future = self.run_pipeline()
        self.assertEqual(future['reason'], 'no_due_slot')
        marker.unlink()
        historical = self.run_pipeline(event='manual', operation='catchup')
        self.assertEqual(historical['cycle_id'], 'agent_memory-20261027-0300')


class RealStageIntegration(unittest.TestCase):
    def test_real_collect_research_and_sdk_harness_replay_fictional_full_text(self):
        import researchdesk_cycle as cycle
        import researchdesk_harness as harness
        import researchdesk_research as research
        import researchdesk_publish as publish
        import test_research_entry as fixtures
        from test_codex_harness import RecordingBackend
        fixture = fixtures.ResearchEntry('test_collection_to_detailed_reviewed_summaries_and_idempotent_resume')
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        root = fixture.root
        # This source fixture does not emulate attention providers, so its
        # explicit system policy leaves the optional attention ranking off.
        system = workbench._read(workbench.REPOSITORY / workbench.SYSTEM_CONFIG)
        system['research'].pop('selection', None)
        (root / workbench.SYSTEM_CONFIG).write_bytes(workbench._yaml(system))
        workbench.initialize(root, adopt_existing=True)
        with tempfile.TemporaryDirectory(prefix='researchdesk-integration-sdk-') as outside:
            backend = RecordingBackend()
            dependencies = {
                'collector': lambda root, path, identity: cycle.collect_originals(
                    root, path, identity, fetcher=fixture.fetcher),
                'researcher': lambda root, path, identity, profile: research.run(
                    root, path, identity, client=fixture.client, profile=profile),
                'insight_runner': lambda root, path, identity: harness.run(
                    root, path, identity, backend=backend, state_root=Path(outside)),
                'health_checker': lambda root, config: {'membership_authorized': True, 'model_calls': 0},
            }
            result = automatic.run(root, event='manual', cycle_id='first', **dependencies)
            self.assertEqual(result['status'], 'complete', result)
            self.assertEqual(result['collection_count'], 2)
            self.assertEqual(result['summary_count'], 2)
            self.assertEqual(len(fixture.client.calls), 4)
            self.assertEqual(len(backend.calls), 2)
            context = store.checked_yaml(root, result['context_path'])
            accepted = store.checked_yaml(root, 'reports/test/agent_memory/codex-insight/first/accepted.yaml')
            self.assertIn(context['topics_path'], accepted['input_hashes'])
            self.assertEqual(accepted['review_decision'], 'pass')
            cached = automatic.run(root, event='manual', cycle_id='first', **dependencies)
            self.assertTrue(cached['cached'])
            self.assertEqual(len(fixture.client.calls), 4)
            self.assertEqual(len(backend.calls), 2)
            fixture.member.assert_not_called()
            fixture.writer.assert_not_called()
            with tempfile.TemporaryDirectory(prefix='researchdesk-integration-artifact-') as transfer:
                artifact = Path(transfer) / 'artifact'
                publisher = Path(transfer) / 'publisher'
                publisher.mkdir()
                exported = publish.export(root, artifact, 'agent_memory', 'first', 'a' * 40)
                applied = publish.apply(publisher, artifact)
                self.assertEqual(applied['saved_files'], exported['exported_files'])
                self.assertTrue((publisher / 'collection/agent_memory/first/manifest.yaml').is_file())
                self.assertTrue((publisher / 'insights/test/agent_memory/first/report.md').is_file())
                self.assertFalse((publisher / 'config').exists())
                self.assertEqual(len(fixture.client.calls), 4)
                self.assertEqual(len(backend.calls), 2)


if __name__ == '__main__':
    unittest.main()
