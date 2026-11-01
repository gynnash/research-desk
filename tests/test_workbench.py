"""Private initialization must preserve existing settings and real usage."""

from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import researchdesk_batch as batch
import researchdesk_membership as membership
import researchdesk_offline as store
import researchdesk_workbench as workbench


class Workbench(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='researchdesk-init-tests-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        for target, attribute in ((socket, 'create_connection'), (socket.socket, 'connect'),
                                  (subprocess, 'run'), (membership, 'MembershipClient')):
            patcher = mock.patch.object(target, attribute,
                                       side_effect=AssertionError('Initialization must stay offline'))
            patcher.start()
            self.addCleanup(patcher.stop)

    def document(self, relative):
        return yaml.safe_load((self.root / relative).read_text())

    def write_document(self, relative, value):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(value, allow_unicode=True, sort_keys=False))

    def snapshot(self):
        return {p.relative_to(self.root).as_posix(): p.read_bytes()
                for p in self.root.rglob('*') if p.is_file()}

    def monthly_usage(self, month):
        with mock.patch.object(batch, 'now', return_value=month + '-01T00:00:00+00:00'):
            return batch.monthly_budget(self.root, {
                'backend': 'chatgpt_plan', 'budget': {'month_max_calls': 100}})

    def test_fresh_copy_is_offline_empty_disabled_and_has_no_inherited_usage(self):
        result = workbench.initialize(self.root)
        self.assertEqual(result['status'], 'initialized')
        self.assertEqual(result['model_calls'], 0)
        template = yaml.safe_load((workbench.REPOSITORY / workbench.TEMPLATE).read_text())
        self.assertEqual(self.document(workbench.LOCAL_CONFIG), template)
        self.assertEqual((self.root / workbench.LOCAL_CONFIG).read_bytes(),
                         (workbench.REPOSITORY / workbench.TEMPLATE).read_bytes())
        self.assertEqual(self.document(workbench.STATE), {
            'schema_version': 1, 'usage_months': {}, 'selected_identity_keys': []})
        self.assertEqual(self.monthly_usage('2026-10'), (0, 100))
        self.assertEqual(self.monthly_usage('2026-11'), (0, 100))
        self.assertFalse(self.document('config/automation.yaml')['enabled'])
        self.assertFalse(self.document('config/admission.yaml')['enabled'])
        self.assertFalse(self.document('config/writing_admission.yaml')['publish_authorized'])
        for relative in workbench.generated_config_paths():
            self.assertTrue((self.root / relative).is_file(), relative)
        for directory in ('collection', 'summary', 'insights', 'articles'):
            self.assertEqual(list((self.root / directory / 'agent_memory').iterdir()), [])
        self.assertFalse((self.root / 'reports').exists())
        self.assertFalse((self.root / '.git').exists())
        self.assertEqual(workbench.apply(self.root, check_only=True)['status'], 'valid')

    def test_repeated_initialization_and_apply_are_idempotent(self):
        workbench.initialize(self.root)
        before = self.snapshot()
        workbench.initialize(self.root)
        workbench.apply(self.root)
        workbench.apply(self.root, check_only=True)
        self.assertEqual(self.snapshot(), before)

    def test_uninitialized_cloud_schedule_stays_disabled_without_writing(self):
        import researchdesk_schedule as schedule
        self.assertEqual(schedule.plan(self.root, 'schedule')['cycle_id'], '')
        self.assertEqual(schedule.plan(self.root, 'workflow_dispatch',
                                       requested_operation='catchup')['cycle_id'], '')
        with self.assertRaises(store.OfflineError):
            schedule.plan(self.root, 'workflow_dispatch', requested_operation='run')
        self.assertEqual(self.snapshot(), {})

    def test_user_can_copy_template_before_initializing(self):
        local = self.root / workbench.LOCAL_CONFIG
        local.parent.mkdir(parents=True)
        local.write_bytes((workbench.REPOSITORY / workbench.TEMPLATE).read_bytes())
        before = local.read_bytes()
        workbench.initialize(self.root)
        self.assertEqual(local.read_bytes(), before, 'the copied personal template remains editable')
        self.assertEqual(self.document(workbench.STATE)['usage_months'], {})
        for directory in ('collection', 'summary', 'insights', 'articles'):
            self.assertTrue((self.root / directory / 'agent_memory').is_dir())

    def test_all_topic_ids_are_validated_before_initialization_writes(self):
        template = yaml.safe_load((workbench.REPOSITORY / workbench.TEMPLATE).read_text())
        template.setdefault('research_topics', {}).setdefault('topics', {})['../escape'] = {
            'name': 'Invalid direction', 'enabled': False,
            'description': 'Even an inactive direction cannot escape the workbench.',
            'scope': ['Fixture'], 'keywords': ['fixture']}
        self.write_document(workbench.TEMPLATE, template)
        before = self.snapshot()
        with self.assertRaises(store.OfflineError):
            workbench.initialize(self.root)
        self.assertEqual(self.snapshot(), before, 'invalid extra topics must fail before writing settings')
        self.assertFalse((self.root / workbench.LOCAL_CONFIG).exists())
        self.assertFalse((self.root / workbench.STATE).exists())

    def test_one_local_entry_applies_settings_to_existing_entrypoints(self):
        workbench.initialize(self.root)
        local = self.document(workbench.LOCAL_CONFIG)
        local['workbench_id'] = 'my-personal-workbench'
        local.setdefault('membership_budget', {})['month_max_calls'] = 50
        local.setdefault('research', {}).setdefault('discovery', {})['max_documents'] = 3
        local.setdefault('models', {})['review'] = 'fixture-independent-review'
        local['writing_style'] = '# Personal style\n\nExplain practical mechanisms clearly.\n'
        self.write_document(workbench.LOCAL_CONFIG, local)
        before = self.snapshot()
        with self.assertRaises(store.OfflineError):
            workbench.apply(self.root, check_only=True)
        self.assertEqual(self.snapshot(), before, 'check must not modify any file')
        workbench.apply(self.root)
        self.assertEqual(self.document('config/membership_budget.yaml')['month_max_calls'], 50)
        self.assertEqual(self.document('config/cycles/default.yaml')['discovery']['max_documents'], 3)
        self.assertEqual(self.document('config/confirmation-v2.yaml')['workbench_id'], 'my-personal-workbench')
        self.assertEqual(self.document('config/confirmation.yaml')['workbench_id'], 'my-personal-workbench')
        self.assertEqual(self.document('config/local/codex-insight.yaml')['runtime']['workbench_id'],
                         'my-personal-workbench')
        self.assertEqual(self.document('config/cycles/default.yaml')['models']['review'],
                         'fixture-independent-review')
        self.assertEqual(self.document('config/local/codex-insight.yaml')['models']['review'],
                         'fixture-independent-review')
        self.assertEqual(self.document('config/confirmation-v2.yaml')['writing']['models']['review'],
                         'fixture-independent-review')
        self.assertEqual((self.root / 'config/writing_style.md').read_text(), local['writing_style'])
        self.assertEqual(workbench.apply(self.root, check_only=True)['status'], 'valid')

    def test_existing_settings_require_adoption_and_preserve_original_bytes_and_usage(self):
        template = yaml.safe_load((workbench.REPOSITORY / workbench.TEMPLATE).read_text())
        expected = workbench.render(workbench.load_effective(self.root, overrides=template))
        for relative, payload in expected.items():
            if relative == workbench.GENERATED_FILES['insight']:
                continue
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes((b'# Personal configuration: retain exact bytes.\n' if relative.endswith('.yaml')
                              else b'') + payload)
        self.write_document(workbench.STATE, {'schema_version': 1,
            'usage_months': {'2026-10': 86}, 'selected_identity_keys': ['url:https://example.org/already-selected']})
        event_path = 'reports/test/agent_memory/codex-requests/previous-test/events/000001.yaml'
        store.save_yaml(self.root, event_path, {
            'schema_version': 1, 'type': 'request_reserved', 'backend': 'codex',
            'topic': 'agent_memory', 'cycle_id': 'previous-test', 'task_id': 'previous-task',
            'request_id': '00000000-0000-0000-0000-000000000001',
            'month': '2026-11', 'at': '2026-11-01T00:00:00+00:00'})
        note = self.root / 'summary/agent_memory/manual-note.md'
        note.parent.mkdir(parents=True, exist_ok=True)
        note.write_text('# My research note\n\nRetain this manual annotation.\n')
        before = self.snapshot()
        with self.assertRaises(store.OfflineError):
            workbench.initialize(self.root)
        self.assertEqual(self.snapshot(), before)
        result = workbench.initialize(self.root, adopt_existing=True)
        self.assertEqual(result['status'], 'adopted')
        for relative, payload in before.items():
            self.assertEqual((self.root / relative).read_bytes(), payload, relative)
        self.assertEqual(self.monthly_usage('2026-10'), (86, 100))
        self.assertEqual(self.monthly_usage('2026-11'), (1, 100))
        workbench.apply(self.root, check_only=True)
        workbench.initialize(self.root)
        workbench.apply(self.root)
        for relative, payload in before.items():
            self.assertEqual((self.root / relative).read_bytes(), payload, relative)

    def test_manual_compatibility_edit_is_not_overwritten_even_if_other_settings_changed(self):
        workbench.initialize(self.root)
        changed = self.document('config/membership_budget.yaml')
        changed['month_max_calls'] = 80
        self.write_document('config/membership_budget.yaml', changed)
        local = self.document(workbench.LOCAL_CONFIG)
        local.setdefault('research', {}).setdefault('discovery', {})['max_documents'] = 3
        self.write_document(workbench.LOCAL_CONFIG, local)
        before = self.snapshot()
        with self.assertRaises(store.OfflineError):
            workbench.apply(self.root)
        self.assertEqual(self.snapshot(), before, 'all destinations must be checked before any write')

    def test_symlinked_local_directory_is_rejected_without_writes(self):
        outside = tempfile.TemporaryDirectory(prefix='researchdesk-init-external-')
        self.addCleanup(outside.cleanup)
        (self.root / 'config').mkdir()
        (self.root / 'config/local').symlink_to(Path(outside.name), target_is_directory=True)
        with self.assertRaises(store.OfflineError):
            workbench.initialize(self.root)
        self.assertEqual(list(Path(outside.name).iterdir()), [])


if __name__ == '__main__':
    unittest.main()
