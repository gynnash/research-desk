"""Two configuration layers must be predictable and preserve a live workbench."""

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import yaml

REPOSITORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY / 'scripts'))
import researchdesk_membership as membership
import researchdesk_offline as store
import researchdesk_workbench as workbench


class LayeredConfiguration(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='researchdesk-layers-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        system = REPOSITORY / workbench.SYSTEM_CONFIG
        self.write_bytes(workbench.SYSTEM_CONFIG, system.read_bytes())
        self.system = self.read(workbench.SYSTEM_CONFIG)
        for target, attribute in ((socket, 'create_connection'), (socket.socket, 'connect'),
                                  (subprocess, 'run'), (membership, 'MembershipClient')):
            patcher = mock.patch.object(target, attribute,
                                       side_effect=AssertionError('Configuration must stay offline'))
            patcher.start()
            self.addCleanup(patcher.stop)

    def write_bytes(self, relative, payload):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)

    def write(self, relative, value):
        self.write_bytes(relative, yaml.safe_dump(
            value, allow_unicode=True, sort_keys=False).encode('utf-8'))

    def read(self, relative):
        return yaml.safe_load((self.root / relative).read_text())

    def effective(self, overrides):
        return workbench.load_effective(self.root, overrides=overrides)

    def snapshot(self):
        return {path.relative_to(self.root).as_posix(): path.read_bytes()
                for path in self.root.rglob('*') if path.is_file()}

    def test_user_layer_inherits_defaults_and_replaces_scalars_and_positional_lists(self):
        self.system['runtime']['membership']['profile'] = '/tmp/fixture-system-profile'
        self.write(workbench.SYSTEM_CONFIG, self.system)
        overrides = {
            'schema_version': 1,
            'workbench_id': 'fixture-workbench',
            'membership_budget': {'month_max_calls': 37},
            'research': {'window': {'days': 45}},
            'insight': {'generation': {'target_words': [1600, 2200]}},
            'runtime': {'runner': {'labels': ['fixture-runner']},
                        'membership': {'profile': None}},
        }
        original = deepcopy(overrides)
        result = self.effective(overrides)
        self.assertEqual(result['workbench_id'], 'fixture-workbench')
        self.assertEqual(result['membership_budget']['month_max_calls'], 37)
        self.assertEqual(result['research']['window'], {'mode': 'rolling', 'days': 45})
        self.assertEqual(result['research']['reading'], self.system['research']['reading'])
        self.assertEqual(result['insight']['generation']['target_words'], [1600, 2200])
        self.assertEqual(result['runtime']['runner']['labels'], ['fixture-runner'])
        self.assertIsNone(result['runtime']['membership']['profile'])
        self.assertEqual(overrides, original, 'merging cannot rewrite caller-owned overrides')
        self.assertEqual(self.read(workbench.SYSTEM_CONFIG), self.system)

    def test_source_updates_inherit_fields_append_new_ids_and_disable_defaults(self):
        extra = {'id': 'fixture-blog', 'adapter': 'rss', 'publisher': 'Fixture publisher',
                 'entry_url': 'https://example.org/feed.xml', 'allowed_hosts': ['example.org'],
                 'enabled': True}
        result = self.effective({'schema_version': 1, 'research': {'discovery': {'sources': [
            {'id': 'letta', 'sitemap_max_pages': 2}, {'id': 'langchain', 'enabled': False}, extra]}}})
        by_id = {entry['id']: entry for entry in result['research']['discovery']['sources']}
        self.assertEqual(by_id['letta']['adapter'], 'letta')
        self.assertEqual(by_id['letta']['entry_url'],
                         next(s for s in self.system['research']['discovery']['sources']
                              if s['id'] == 'letta')['entry_url'])
        self.assertEqual(by_id['letta']['sitemap_max_pages'], 2)
        rendered = workbench.render(result)
        runtime = yaml.safe_load(rendered['config/cycles/default.yaml'])
        sources = runtime['discovery']['sources']
        self.assertNotIn('langchain', {source['id'] for source in sources})
        self.assertEqual(sources[-1]['id'], 'fixture-blog')
        self.assertEqual(sources[-1]['allowed_hosts'], ['example.org'])
        self.assertTrue(all('enabled' not in source for source in sources))
        self.assertEqual(len(sources), len(self.system['research']['discovery']['sources']))

    def test_changing_adapter_replaces_incompatible_source_fields(self):
        replacement = {'id': 'huggingface-blog', 'adapter': 'letta',
                       'entry_url': 'https://www.letta.com/blog/'}
        result = self.effective({'schema_version': 1,
                                'research': {'discovery': {'sources': [replacement]}}})
        selected = next(source for source in result['research']['discovery']['sources']
                        if source['id'] == replacement['id'])
        self.assertEqual(selected, replacement)
        self.assertNotIn('publisher', selected)
        self.assertNotIn('allowed_hosts', selected)
        workbench.render(result)

    def test_duplicate_source_ids_are_rejected_in_either_layer(self):
        duplicate = {'schema_version': 1, 'research': {'discovery': {
            'sources': [{'id': 'letta', 'enabled': False}, {'id': 'letta', 'enabled': True}]}}}
        with self.assertRaises(store.OfflineError):
            self.effective(duplicate)
        self.system['research']['discovery']['sources'].append(
            deepcopy(self.system['research']['discovery']['sources'][0]))
        self.write(workbench.SYSTEM_CONFIG, self.system)
        with self.assertRaises(store.OfflineError):
            self.effective({'schema_version': 1})

    def test_topic_and_model_shortcuts_expand_with_explicit_stage_overrides_winning(self):
        result = self.effective({
            'schema_version': 1,
            'topic': 'agent_rl',
            'models': {'generation': 'fixture-generator', 'review': 'fixture-reviewer',
                       'writing': 'fixture-writer'},
            'research_topics': {'topics': {'agent_rl': {
                'name': 'Agent RL', 'enabled': True, 'description': 'Fictional research direction.',
                'scope': ['Fictional research scope.'], 'keywords': ['agent reinforcement learning']}}},
            'research': {'models': {'research': 'fixture-research-specialist'}},
            'insight': {'models': {'review': 'fixture-insight-reviewer'}},
            'confirmation': {'writing': {'models': {'writing': 'fixture-writing-specialist'}}},
        })
        self.assertEqual(result['research']['topic'], 'agent_rl')
        self.assertEqual(result['insight']['topic'], 'agent_rl')
        for section in ('confirmation', 'admission', 'writing_admission'):
            self.assertEqual(result[section]['topics'], ['agent_rl'])
        self.assertEqual(result['research']['models']['research'], 'fixture-research-specialist')
        self.assertEqual(result['research']['models']['insight'], 'fixture-generator')
        self.assertEqual(result['research']['models']['review'], 'fixture-reviewer')
        self.assertEqual(result['insight']['models'], {
            'generation': 'fixture-generator', 'review': 'fixture-insight-reviewer'})
        self.assertEqual(result['confirmation']['writing']['models'], {
            'writing': 'fixture-writing-specialist', 'review': 'fixture-reviewer'})
        workbench.render(result)

    def test_migration_preserves_active_config_bytes_usage_and_removed_default_sources(self):
        legacy = deepcopy(self.system)
        legacy['workbench_id'] = 'fixture-existing-workbench'
        legacy['membership_budget']['month_max_calls'] = 73
        legacy['writing_style'] = '# Personal fixture style\n\nRetain this preference.\n'
        legacy['research']['discovery']['sources'] = [
            source for source in legacy['research']['discovery']['sources'] if source['id'] != 'letta']
        old_payload = b'# Preserve the old complete personal configuration.\n' + yaml.safe_dump(
            legacy, allow_unicode=True, sort_keys=False).encode('utf-8')
        self.write_bytes(workbench.LOCAL_CONFIG, old_payload)
        expected = workbench.render(legacy)
        managed = {}
        for relative, payload in expected.items():
            payload = (b'# Keep existing snapshot bytes.\n' + payload
                       if relative.endswith('.yaml') else payload)
            self.write_bytes(relative, payload)
            managed[relative] = hashlib.sha256(payload).hexdigest()
        self.write_bytes(workbench.MANIFEST, json.dumps(managed, indent=2).encode())
        self.write(workbench.STATE, {'schema_version': 1, 'usage_months': {'2026-10': 86},
                                    'selected_identity_keys': ['url:https://example.org/selected']})
        ledger = 'reports/test/agent_memory/codex-requests/fixture/events/000001.yaml'
        self.write_bytes(ledger, b'type: request_reserved\nmonth: 2026-11\n')
        before = self.snapshot()
        workbench.migrate(self.root)
        self.assertEqual((self.root / 'config/local/workbench.before-layers.yaml').read_bytes(),
                         old_payload)
        for relative, payload in before.items():
            if relative not in {workbench.LOCAL_CONFIG, workbench.MANIFEST}:
                self.assertEqual((self.root / relative).read_bytes(), payload, relative)
        self.assertLess(len((self.root / workbench.LOCAL_CONFIG).read_bytes()), len(old_payload))
        current = workbench.render(workbench.load_effective(self.root))
        for relative, payload in expected.items():
            self.assertEqual(current[relative], payload, relative)
        patch_sources = self.read(workbench.LOCAL_CONFIG)['research']['discovery']['sources']
        self.assertIn({'id': 'letta', 'enabled': False}, patch_sources)
        workbench.apply(self.root, check_only=True)
        self.assertEqual((self.root / workbench.STATE).read_bytes(), before[workbench.STATE])
        self.assertEqual((self.root / ledger).read_bytes(), before[ledger])

    def test_unrepresentable_legacy_source_order_is_preserved_when_migration_refuses(self):
        legacy = deepcopy(self.system)
        legacy['research']['discovery']['sources'].reverse()
        self.write(workbench.LOCAL_CONFIG, legacy)
        managed = {}
        for relative, payload in workbench.render(legacy).items():
            self.write_bytes(relative, payload)
            managed[relative] = hashlib.sha256(payload).hexdigest()
        self.write_bytes(workbench.MANIFEST, json.dumps(managed, indent=2).encode())
        before = self.snapshot()
        # Full previous-generation files remain usable without silently adding
        # or reordering source choices, even if compacting cannot express them.
        self.assertEqual(workbench.load_effective(self.root)['research']['discovery']['sources'],
                         legacy['research']['discovery']['sources'])
        workbench.apply(self.root, check_only=True)
        with self.assertRaises(store.OfflineError):
            workbench.migrate(self.root)
        self.assertEqual(self.snapshot(), before)
        workbench.apply(self.root, check_only=True)


if __name__ == '__main__':
    unittest.main()
