"""Bounded Beijing schedule checks; no research, inference, Git or network."""

from datetime import datetime
from pathlib import Path
import shutil
import socket
import sys
import tempfile
import unittest
from unittest import mock

import yaml


REPOSITORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY / 'scripts'))
import researchdesk_offline as store
import researchdesk_schedule as schedule


class BeijingSchedule(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='researchdesk-schedule-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        for relative in ('config/automation.yaml', 'config/admission.yaml',
                         'config/cycles/agent-memory.yaml', 'config/research_topics.yaml'):
            target = self.root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(REPOSITORY / relative, target)
        self.config = schedule.load_config(self.root)
        self.addCleanup(mock.patch.stopall)
        mock.patch.object(socket, 'create_connection', side_effect=AssertionError('Network prohibited')).start()
        mock.patch.object(socket.socket, 'connect', side_effect=AssertionError('Network prohibited')).start()

    def due(self, value):
        return schedule.due_slot(self.root, self.config, datetime.fromisoformat(value))

    def accepted(self, cycle_id):
        path = self.root / ('reports/agent-memory/admissions/%s/accepted.yaml' % cycle_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('production_accepted: true\n', encoding='utf-8')
        Path(str(path) + '.sha256').write_text(store.digest(path.read_bytes()) + '\n', encoding='utf-8')

    def test_workflow_and_config_use_previous_utc_day(self):
        workflow = yaml.load((REPOSITORY / '.github/workflows/researchdesk-manual.yml').read_text(),
                             Loader=yaml.BaseLoader)
        self.assertEqual(self.config['schedule_utc'], '0 19 * * 1,4')
        self.assertEqual(workflow['on']['schedule'], [{'cron': self.config['schedule_utc']}])
        self.assertEqual(self.config['catchup'], {'lookback_days': 14, 'max_slots_per_run': 1})
        self.config['schedule_utc'] = '0 1 * * 2,5'
        (self.root / 'config/automation.yaml').write_text(yaml.safe_dump(self.config), encoding='utf-8')
        with self.assertRaises(store.OfflineError):
            schedule.load_config(self.root)

    def test_tuesday_before_at_and_after_0300_use_beijing_date(self):
        self.assertEqual(self.due('2026-10-19T18:59:59+00:00')['cycle_id'], '')
        for value in ('2026-10-19T19:00:00+00:00', '2026-10-20T03:00:00+08:00',
                      '2026-10-20T03:00:01+08:00'):
            with self.subTest(now=value):
                result = self.due(value)
                self.assertEqual(result['cycle_id'], 'agent-memory-20261020-0300')
                self.assertEqual(result['slot_utc'], '2026-10-19T19:00:00+00:00')

    def test_friday_slot_is_thursday_utc_and_completed_tuesday_is_skipped(self):
        self.accepted('agent-memory-20261020-0300')
        self.assertEqual(self.due('2026-10-23T02:59:59+08:00')['cycle_id'], '')
        result = self.due('2026-10-23T03:00:00+08:00')
        self.assertEqual(result['cycle_id'], 'agent-memory-20261023-0300')
        self.assertEqual(result['slot_utc'], '2026-10-22T19:00:00+00:00')

    def test_reviewed_slot_resumes_until_admitted_and_terminal_slot_is_not_repeated(self):
        relative = 'reports/test/agent-memory/cycles/agent-memory-20261020-0300/receipt.yaml'
        store.save_yaml(self.root, relative, {'stages': {
            'research': {'status': 'test_accepted'}, 'insight': {'status': 'test_accepted'}}})
        old = self.root / 'reports/test/agent-memory/cycles/old-0900/receipt.yaml'
        old.parent.mkdir(parents=True, exist_ok=True)
        old.write_text('historical: preserve\n', encoding='utf-8')
        before = {path.relative_to(self.root): path.read_bytes()
                  for path in self.root.rglob('*') if path.is_file()}
        first = self.due('2026-10-23T03:00:00+08:00')
        self.assertEqual(first['cycle_id'], 'agent-memory-20261020-0300')
        self.assertEqual(self.due('2026-10-23T03:00:00+08:00'), first)
        self.assertEqual(before, {path.relative_to(self.root): path.read_bytes()
                                  for path in self.root.rglob('*') if path.is_file()})
        self.accepted(first['cycle_id'])
        self.assertEqual(self.due('2026-10-23T03:00:00+08:00')['cycle_id'],
                         'agent-memory-20261023-0300')
        store.save_yaml(self.root, 'reports/test/agent-memory/cycles/agent-memory-20261023-0300/receipt.yaml',
                        {'stages': {'research': {'status': 'blocked'}}})
        self.assertEqual(self.due('2026-10-23T03:00:00+08:00')['cycle_id'], '')
        self.assertEqual(old.read_text(), 'historical: preserve\n')

    def test_catchup_is_oldest_due_slot_within_14_days_and_activation_is_respected(self):
        result = self.due('2026-11-03T09:00:00+08:00')
        self.assertEqual(result['cycle_id'], 'agent-memory-20261023-0300')
        self.assertEqual(result['slot_utc'], '2026-10-22T19:00:00+00:00')
        self.assertEqual(schedule.plan(self.root, 'workflow_dispatch', requested_operation='catchup',
                                       now=datetime.fromisoformat('2026-11-03T09:00:00+08:00')), result)
        self.config['activated_at'] = '2026-10-20T03:00:01+08:00'
        self.assertEqual(self.due('2026-10-23T03:00:00+08:00')['cycle_id'],
                         'agent-memory-20261023-0300')


if __name__ == '__main__':
    unittest.main()
