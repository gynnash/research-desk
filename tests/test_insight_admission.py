"""Formal SDK Insight admission uses fictional sources and no network or models."""

import copy
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import researchdesk_harness as harness
import researchdesk_insight_admission as admission
import researchdesk_offline as store
import test_codex_harness as codex_fixtures
import test_research_entry as research_fixtures


class LiveFixtureBackend(codex_fixtures.RecordingBackend):
    """Shape of a live SDK response; all execution remains an in-memory stub."""
    name = 'codex'

    def preflight(self):
        return {'live_ready': True, 'offline_ready': True, 'backend': self.name}


def prepare_cycle(testcase, admit=True):
    """Reusable complete portable proofs without an initialized real workspace."""
    temporary = tempfile.TemporaryDirectory(prefix='researchdesk-admission-fixtures-')
    testcase.addCleanup(temporary.cleanup)
    external = Path(temporary.name).resolve()
    seed = external / 'seed'
    (seed / 'config/cycles').mkdir(parents=True)
    system = yaml.safe_load((ROOT / 'config/system.yaml').read_text())
    (seed / 'config/cycles/default.yaml').write_text(yaml.safe_dump(system['research']))
    shutil.copyfile(ROOT / 'config/legacy_sources.yaml', seed / 'config/legacy_sources.yaml')
    fixture = research_fixtures.ResearchEntry('test_collection_to_detailed_reviewed_summaries_and_idempotent_resume')
    with patch.object(research_fixtures.fixtures, 'REPOSITORY', seed):
        fixture.setUp()
    testcase.addCleanup(fixture.doCleanups)
    fixture.collect()
    fixture.run_research()
    config = yaml.safe_load((ROOT / 'config/examples/codex-insight.yaml').read_text())
    config['models'] = {'generation': 'fixture-generator', 'review': 'fixture-independent-reviewer'}
    (fixture.root / 'config/codex-insight.yaml').write_text(yaml.safe_dump(config))
    backend = LiveFixtureBackend(observed={'generation': 'fixture-generator', 'review': 'fixture-independent-reviewer'})
    result = harness.run(fixture.root, 'config/codex-insight.yaml', 'first', backend=backend,
                         state_root=external / 'runtime')
    testcase.assertEqual(result['status'], 'complete')
    if admit:
        admission.admit(fixture.root, 'agent_memory', 'first')
    return fixture, backend


class InsightAdmission(unittest.TestCase):
    def setUp(self):
        self.fixture, self.backend = prepare_cycle(self, admit=False)
        self.root = self.fixture.root
        self.calls = (len(self.fixture.client.calls), list(self.backend.calls))

    def sdk_receipt(self):
        return store.checked_yaml(self.root, 'reports/test/agent_memory/codex-insight/first/accepted.yaml')

    def replace_sdk_receipt(self, value):
        relative = 'reports/test/agent_memory/codex-insight/first/accepted.yaml'
        for name in (relative, relative + '.sha256'):
            (self.root / name).unlink()
        store.save_yaml(self.root, relative, value)

    def assert_no_new_calls(self):
        self.assertEqual((len(self.fixture.client.calls), self.backend.calls), self.calls)
        self.fixture.member.assert_not_called()

    def test_readable_formal_report_topics_and_idempotent_load(self):
        original_test = (self.root / 'insights/test/agent_memory/first/report.md').read_bytes()
        result = admission.admit(self.root, 'agent_memory', 'first')
        self.assertEqual(result['status'], 'accepted')
        value = admission.load(self.root, 'agent_memory', 'first')
        self.assertEqual(value['mode'], admission.MODE)
        self.assertEqual(value['models']['review'], 'fixture-independent-reviewer')
        self.assertEqual(value['path_scheme'], admission.PATH_SCHEME)
        report_path = 'insights/agent_memory/观察0~first/写入与使用之间.md'
        self.assertIn(report_path, result['outputs'])
        report = (self.root / report_path).read_text()
        self.assertNotIn('> TEST', report)
        self.assertIn('## 参考资料', report)
        topic_path = self.root / 'articles/agent_memory/first-topic-1.md'
        topic = store.frontmatter(topic_path)
        self.assertEqual(topic['id'], 'formal-topic-agent_memory-first-1')
        self.assertEqual(topic['kind'], 'topic_proposal')
        self.assertTrue(topic['approval_required'])
        self.assertFalse(topic['writing_started'])
        self.assertFalse(topic['publish_authorized'])
        self.assertTrue(all(source['original_text'] for source in value['bundle']['sources']))
        stored = admission._checked(self.root, admission.base_path('agent_memory', 'first') + '/plan.yaml')
        self.assertNotIn('original_text', stored['bundle']['sources'][0])
        self.assertEqual((self.root / 'insights/test/agent_memory/first/report.md').read_bytes(), original_test)
        self.assertTrue(admission.admit(self.root, 'agent_memory', 'first')['cached'])
        self.assert_no_new_calls()

    def test_interrupted_legacy_plan_keeps_its_original_paths(self):
        plan_path = admission.base_path('agent_memory', 'first') + '/plan.yaml'
        legacy_plan = admission._plan(self.root, 'agent_memory', 'first', path_scheme=None)
        admission.legacy._save(self.root, plan_path, legacy_plan)
        before = (self.root / plan_path).read_bytes()
        report_path = 'insights/agent_memory/first/report.md'
        self.assertIn(report_path, admission.admit(self.root, 'agent_memory', 'first')['outputs'])
        self.assertIn(report_path, admission.load(self.root, 'agent_memory', 'first')['output_hashes'])
        self.assertEqual((self.root / plan_path).read_bytes(), before)
        self.assert_no_new_calls()

    def test_clean_checkout_without_private_configuration_verifies_and_does_not_write(self):
        admission.admit(self.root, 'agent_memory', 'first')
        shutil.rmtree(self.root / 'config')
        before = {path.relative_to(self.root): path.read_bytes()
                  for path in self.root.rglob('*') if path.is_file()}
        value = admission.load(self.root, 'agent_memory', 'first')
        self.assertEqual(value['candidate']['topics'][0]['title'], '记忆写下后怎样用起来？')
        self.assertFalse((self.root / 'config').exists())
        after = {path.relative_to(self.root): path.read_bytes()
                 for path in self.root.rglob('*') if path.is_file()}
        self.assertEqual(before, after)
        self.assert_no_new_calls()

    def test_human_conflict_is_checked_before_any_formal_write(self):
        target = self.root / 'articles/agent_memory/first-topic-1.md'
        target.parent.mkdir(parents=True)
        target.write_text('# 人工笔记，不可覆盖\n')
        with self.assertRaisesRegex(store.OfflineError, '人工修改'):
            admission.admit(self.root, 'agent_memory', 'first')
        self.assertEqual(target.read_text(), '# 人工笔记，不可覆盖\n')
        self.assertFalse((self.root / 'insights/agent_memory').exists())
        self.assertFalse((self.root / 'reports/agent_memory').exists())
        self.assert_no_new_calls()

    def test_parent_file_conflict_is_checked_before_any_formal_write(self):
        target = self.root / 'articles/agent_memory'
        target.write_text('人工保存的同名文件，不可覆盖。\n')
        with self.assertRaisesRegex(store.OfflineError, '父目录已有人工文件'):
            admission.admit(self.root, 'agent_memory', 'first')
        self.assertEqual(target.read_text(), '人工保存的同名文件，不可覆盖。\n')
        self.assertFalse((self.root / 'insights/agent_memory').exists())
        self.assertFalse((self.root / 'reports/agent_memory').exists())
        self.assert_no_new_calls()

    def test_simulation_cannot_be_admitted_even_when_all_hashes_match(self):
        receipt = self.sdk_receipt()
        receipt['simulation'] = True
        self.replace_sdk_receipt(receipt)
        with self.assertRaisesRegex(store.OfflineError, '真实后端'):
            admission.admit(self.root, 'agent_memory', 'first')
        self.assertFalse((self.root / 'reports/agent_memory').exists())
        self.assert_no_new_calls()

    def test_other_backends_cannot_claim_a_formal_codex_admission(self):
        original = self.sdk_receipt()
        for backend in ('codex_mock', 'mock_codex', 'other_backend'):
            with self.subTest(backend=backend):
                receipt = copy.deepcopy(original)
                receipt['backend'] = backend
                self.replace_sdk_receipt(receipt)
                with self.assertRaisesRegex(store.OfflineError, '真实后端'):
                    admission.admit(self.root, 'agent_memory', 'first')
        self.assert_no_new_calls()

    def test_same_actual_model_is_not_independent(self):
        receipt = self.sdk_receipt()
        for role in ('generation', 'review'):
            receipt['models'][role]['observed_model'] = 'same-model'
        self.replace_sdk_receipt(receipt)
        with self.assertRaisesRegex(store.OfflineError, '相同模型'):
            admission.admit(self.root, 'agent_memory', 'first')
        self.assert_no_new_calls()

    def test_candidate_or_review_change_cannot_be_promoted(self):
        path = self.root / 'reports/test/agent_memory/codex-insight/first/candidate.yaml'
        path.write_text(path.read_text() + '\nunsupported_fact: changed\n')
        with self.assertRaisesRegex(store.OfflineError, '发生变化'):
            admission.admit(self.root, 'agent_memory', 'first')
        self.assert_no_new_calls()

    def test_original_change_and_formal_note_change_are_detected_without_overwrite(self):
        admission.admit(self.root, 'agent_memory', 'first')
        value = admission.load(self.root, 'agent_memory', 'first')
        original = self.root / value['bundle']['sources'][0]['original_path']
        before = original.read_text()
        original.write_text(before + '\n人工补充。\n')
        with self.assertRaises(store.OfflineError):
            admission.load(self.root, 'agent_memory', 'first')
        original.write_text(before)
        formal = self.root / next(path for path in value['output_hashes'] if path.startswith('insights/'))
        formal.write_text(formal.read_text() + '\n我的研究笔记。\n')
        with self.assertRaisesRegex(store.OfflineError, '发生变化'):
            admission.admit(self.root, 'agent_memory', 'first')
        self.assertIn('我的研究笔记', formal.read_text())
        self.assert_no_new_calls()

    def test_current_topic_config_change_does_not_rewrite_historical_input(self):
        admission.admit(self.root, 'agent_memory', 'first')
        path = self.root / 'config/research_topics.yaml'
        path.write_text('schema_version: 1\ntopics: {}\n')
        value = admission.load(self.root, 'agent_memory', 'first')
        self.assertTrue(value['configuration_snapshots'])
        self.assertEqual(path.read_text(), 'schema_version: 1\ntopics: {}\n')
        self.assert_no_new_calls()

    def test_interrupted_plan_or_final_marker_write_resumes_without_model_calls(self):
        original_create = admission.legacy._create
        failures = {'plan': False, 'accepted': False}

        def interrupt_before_marker(root, relative, text):
            for name in failures:
                if relative.endswith('/' + name + '.yaml.sha256') and not failures[name]:
                    failures[name] = True
                    raise OSError('Synthetic interruption before SHA marker')
            return original_create(root, relative, text)

        with patch.object(admission.legacy, '_create', side_effect=interrupt_before_marker):
            with self.assertRaises(OSError):
                admission.admit(self.root, 'agent_memory', 'first')
            with self.assertRaises(OSError):
                admission.admit(self.root, 'agent_memory', 'first')
            self.assertEqual(admission.admit(self.root, 'agent_memory', 'first')['status'], 'accepted')
        self.assertEqual(admission.load(self.root, 'agent_memory', 'first')['mode'], admission.MODE)
        self.assert_no_new_calls()


if __name__ == '__main__':
    unittest.main()
