"""Four create-only admission checks using copied, genuinely reviewed proof.

The first plan is prepared separately from the accepted GitHub research cycle.
These checks replay its complete production gate and any hash-bound link repair
in disposable vaults: no model response, pass decision, provenance reader or
writer is replaced. Historical plan/accepted bytes remain unchanged.
"""

import importlib
import json
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
import researchdesk_membership as membership
import researchdesk_offline as store
import researchdesk_sources as sources

TOPIC = 'agent-memory'
CYCLE = 'cycle-agent-memory-gh-20261019'
BASE = 'reports/%s/admissions/%s' % (TOPIC, CYCLE)


class CreateOnlyAdmission(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = REPOSITORY / BASE / 'plan.yaml'
        if not path.is_file():
            raise unittest.SkipTest('需要先对真实 GitHub 轮次完成首次原文复核并保存准入 plan；本测试不联网补建')
        cls.admission = importlib.import_module('researchdesk_admission')
        cls.original_plan = yaml.safe_load(path.read_text(encoding='utf-8'))
        if not cls.original_plan.get('files'):
            raise AssertionError('真实准入计划缺少待创建产物')

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='researchdesk-admission-tests-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        # Keep all real checkpoint/provenance inputs, but begin before this
        # cycle's formal files or acceptance record were created. Originals
        # in the user's vault are only read and are never modified.
        omitted = set(self.original_plan['files']) | {BASE + '/accepted.yaml', BASE + '/accepted.yaml.sha256'}

        def ignore(directory, names):
            relative = Path(directory).relative_to(REPOSITORY)
            return [name for name in names if (relative / name).as_posix() in omitted]

        for folder in ('config', 'sources', 'reports', 'insights', 'articles', 'workflows'):
            shutil.copytree(REPOSITORY / folder, self.root / folder, ignore=ignore)
        inference_patch = mock.patch.object(
            membership.MembershipClient, 'infer', side_effect=AssertionError('Admission must not infer'))
        fetch_patch = mock.patch.object(
            sources.SafeFetcher, 'fetch', side_effect=AssertionError('Cached admission must not fetch'))
        network_patch = mock.patch.object(socket.socket, 'connect', side_effect=AssertionError('Network prohibited'))
        for patcher in (inference_patch, fetch_patch, network_patch):
            self.addCleanup(patcher.stop)
        self.infer = inference_patch.start()
        self.fetch = fetch_patch.start()
        network_patch.start()

    def admit(self, **kwargs):
        return self.admission.run(self.root, TOPIC, CYCLE, **kwargs)

    def accepted(self):
        return self.root / BASE / 'accepted.yaml'

    def assert_no_external_calls(self):
        self.infer.assert_not_called()
        self.fetch.assert_not_called()

    def assert_created(self):
        verified = self.admission.plan(self.root, TOPIC, CYCLE)
        effective = self.admission.effective_files(self.root, verified)
        self.assertEqual(set(effective), set(self.original_plan['files']))
        for relative, content in effective.items():
            self.assertEqual((self.root / relative).read_bytes(), content.encode('utf-8'))

    def rewrite_yaml(self, relative, value):
        """Mutate only a disposable proof, including its transport checksum."""
        path = self.root / relative
        payload = yaml.safe_dump(value, allow_unicode=True, sort_keys=False).encode('utf-8')
        path.write_bytes(payload)
        Path(str(path) + '.sha256').write_text(store.digest(payload) + '\n', encoding='utf-8')

    def test_modified_backend_or_nonpassing_review_cannot_be_admitted(self):
        cycle_receipt = 'reports/test/%s/cycles/%s/receipt.yaml' % (TOPIC, CYCLE)
        value = yaml.safe_load((self.root / cycle_receipt).read_text(encoding='utf-8'))
        original = (self.root / cycle_receipt).read_bytes()
        value['backend'] = 'mock'
        self.rewrite_yaml(cycle_receipt, value)
        with self.assertRaises(store.OfflineError):
            self.admit()
        self.assertFalse(self.accepted().exists())
        self.assertFalse(any((self.root / path).exists() for path in self.original_plan['files']))
        (self.root / cycle_receipt).write_bytes(original)
        Path(str(self.root / cycle_receipt) + '.sha256').write_text(store.digest(original) + '\n')
        review_path = 'reports/test/%s/insight-runs/%s/checkpoints/review-1.yaml' % (TOPIC, CYCLE)
        checkpoint = yaml.safe_load((self.root / review_path).read_text(encoding='utf-8'))
        review = json.loads(checkpoint['result']['text'])
        review['decision'] = 'reject'
        checkpoint['result']['text'] = json.dumps(review, ensure_ascii=False)
        self.rewrite_yaml(review_path, checkpoint)
        with self.assertRaises(store.OfflineError):
            self.admit()
        self.assertFalse(self.accepted().exists())
        self.assert_no_external_calls()

    def test_create_then_same_cycle_replay_adds_nothing_and_calls_no_model(self):
        first = self.admit()
        self.assertEqual(first['status'], 'accepted')
        self.assertIs(first['production_accepted'], True)
        self.assert_created()
        before = {path.relative_to(self.root).as_posix(): store.digest(path.read_bytes())
                  for path in self.root.rglob('*') if path.is_file()}
        second = self.admit()
        self.assertIs(second['cached'], True)
        after = {path.relative_to(self.root).as_posix(): store.digest(path.read_bytes())
                 for path in self.root.rglob('*') if path.is_file()}
        self.assertEqual(before, after)
        self.assert_no_external_calls()

    def test_existing_human_file_is_preserved_and_no_acceptance_is_written(self):
        relative = next(iter(self.original_plan['files']))
        target = self.root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        human = '# 人工笔记\n\n请保留此内容。\n'.encode('utf-8')
        target.write_bytes(human)
        with self.assertRaises(store.OfflineError):
            self.admit()
        self.assertEqual(target.read_bytes(), human)
        self.assertFalse(self.accepted().exists())
        self.assertFalse(any((self.root / path).exists()
                             for path in self.original_plan['files'] if path != relative))
        self.assert_no_external_calls()

    def test_interrupted_create_resumes_without_overwriting_saved_output(self):
        with self.assertRaises(store.SimulatedInterruption):
            self.admit(fail_after='after_first_output')
        saved = [self.root / path for path in self.original_plan['files'] if (self.root / path).exists()]
        self.assertEqual(len(saved), 1)
        original = saved[0].read_bytes()
        self.assertFalse(self.accepted().exists())
        result = self.admit()
        self.assertEqual(result['status'], 'accepted')
        self.assertEqual(saved[0].read_bytes(), original)
        self.assert_created()
        self.assert_no_external_calls()


if __name__ == '__main__':
    unittest.main()
