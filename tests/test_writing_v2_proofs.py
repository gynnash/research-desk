"""Read-only version boundaries against the preserved real Writing proof.

No topic is confirmed and no provider or source endpoint is contacted. The
existing v1 admission is the regression oracle for prompts, bindings and prose.
"""

import copy
from pathlib import Path
import socket
import sys
import unittest
from unittest import mock

import yaml


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import researchdesk_membership as membership
import researchdesk_offline as store
import researchdesk_writing_admission as admission
import researchdesk_writing_job as job
import researchdesk_writing_member as writing


APPROVAL = 'approval-20261019-161304-eeb7d0a7582e'
BATCH = 'writing-' + APPROVAL
PLAN = ROOT / ('reports/agent-memory/writing-admissions/%s/plan.yaml' % BATCH)


class FrozenWritingVersions(unittest.TestCase):
    def setUp(self):
        if not PLAN.is_file():
            self.skipTest('需要保留的真实 v1 Writing 准入证明；不补建或联网')
        self.bundle = yaml.safe_load(PLAN.read_text(encoding='utf-8'))['verification_bundle']
        for name in ('__init__', 'status', 'models', 'infer'):
            patcher = mock.patch.object(membership.MembershipClient, name,
                side_effect=AssertionError('Version proof checks must never contact membership'))
            patcher.start()
            self.addCleanup(patcher.stop)
        connection = mock.patch.object(socket, 'create_connection',
            side_effect=AssertionError('Version proof checks must never use the network'))
        connection.start()
        self.addCleanup(connection.stop)

    def test_existing_v1_formal_admission_remains_verifiable(self):
        self.assertNotIn('style_profile', self.bundle)
        self.assertEqual(writing.instructions(self.bundle, 'writing'), writing.WRITING_INSTRUCTIONS)
        self.assertEqual(writing.instructions(self.bundle, 'review'), writing.REVIEW_INSTRUCTIONS)
        receipt = admission.verify(ROOT, 'agent-memory', APPROVAL, historical=True)
        self.assertEqual(receipt['status'], 'accepted')
        self.assertEqual(receipt['new_model_calls'], 0)
        self.assertEqual(len(receipt['output_hashes']), 3)

    def test_v2_style_cannot_replay_v1_response_bindings(self):
        bundle = copy.deepcopy(self.bundle)
        text = (ROOT / 'config/writing_style.md').read_text(encoding='utf-8')
        bundle['style_profile'] = {'version': 'writing-v2', 'path': 'config/writing_style.md',
                                   'sha256': store.digest(text.encode('utf-8')), 'text': text}
        base = 'reports/test/agent-memory/writing-runs/' + BATCH
        manifest = store.checked_yaml(ROOT, base + '/manifest.yaml')
        events = store.read_events(ROOT, base)
        with self.assertRaises(job.JobError):
            job._verify_bindings(ROOT, base, events, manifest, bundle)

    def test_history_cannot_gain_unconfirmed_author_experience(self):
        bundle = copy.deepcopy(self.bundle)
        bundle['topic_card']['author_notes'] = '未经该次页面确认的新经历。'
        bundle.pop('input_fingerprint')
        bundle['input_fingerprint'] = store.digest(bundle)
        with self.assertRaises(store.OfflineError):
            admission._historical_bundle(ROOT, bundle)


if __name__ == '__main__':
    unittest.main()
