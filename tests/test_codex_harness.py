"""Offline acceptance checks for the Codex Insight harness.

The fake backend returns completed task results, never calls a model, and keeps
its call log across retries so duplicate inference is observable.
"""

import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import researchdesk_codex as codex
import researchdesk_harness as harness


def candidate(count=3):
    # Deliberately short: no prescribed headings, counterpoints, or source-count
    # matrix. Those are not prerequisites for an accurate, useful result.
    return {
        'outcome': 'ready',
        'report': {'title': '写入与使用之间',
                   'body': '作者将记忆更新与检索分开讨论。我们认为这值得分别验证。'},
        'insights': [{'title': '观察%s' % number,
                      'body': '这是限定于测试原文的研究线索。',
                      'source_ids': ['R1']} for number in range(count)],
        'topics': [{'title': '记忆写下后怎样用起来？', 'angle': '解释具体机制',
                    'audience': 'Agent 工程读者', 'source_ids': ['R1']}],
    }


class RecordingBackend:
    name = 'codex_mock'

    def __init__(self, scripts=None, inspected=None, observed=None):
        self.scripts = scripts or {
            'generation': candidate(),
            'review': {'decision': 'pass'},
        }
        self.inspected = inspected or {}
        self.observed = observed or {}
        self.calls = []
        self.tasks = {}
        self.handles = {}

    def preflight(self, *args, **kwargs):
        return {'ready': True, 'offline_ready': True, 'live_ready': False,
                'backend': self.name}

    def _result(self, task, value):
        wrapped = isinstance(value, dict) and '_status' in value
        status = value['_status'] if wrapped else 'completed'
        response = value.get('response') if wrapped else value
        handle = self.handles[task.task_id]
        return codex.TaskResult(
            status=status, thread_id=handle['thread_id'],
            turn_id=handle['turn_id'],
            final_response=(json.dumps(response, ensure_ascii=False)
                            if response is not None else None),
            requested_model=task.model, observed_model=self.observed.get(task.phase),
            usage=None, model_request_count=None,
            failure_class='connection_lost' if status == 'blocked_unknown' else None,
        )

    def _execute(self, method, task, on_event=None, thread_id=None):
        self.calls.append((method, task.phase))
        handle = {'thread_id': thread_id or 'thread-' + task.phase,
                  'turn_id': 'turn-' + task.phase}
        self.handles[task.task_id] = handle
        self.tasks[(handle['thread_id'], handle['turn_id'])] = task
        if on_event:
            on_event(dict(type='turn/started', **handle))
        return self._result(task, self.scripts[task.phase])

    def start(self, task, on_event=None):
        return self._execute('start', task, on_event)

    def continue_turn(self, handle, task, on_event=None):
        return self._execute('continue_turn', task, on_event,
                             thread_id=handle['thread_id'])

    def inspect(self, handle):
        task = self.tasks[(handle['thread_id'], handle['turn_id'])]
        self.calls.append(('inspect', task.phase))
        return self._result(task, self.inspected.get(task.phase, self.scripts[task.phase]))

    def resume(self, handle):
        return self.inspect(handle)

    def interrupt(self, handle):
        task = self.tasks[(handle['thread_id'], handle['turn_id'])]
        self.calls.append(('interrupt', task.phase))
        return self._result(task, {'_status': 'interrupted'})


class CodexHarnessAcceptance(unittest.TestCase):
    cycle = 'memory-fixture-20300101'

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        temporary = Path(self.temporary.name).resolve()
        self.root = temporary / 'repository'
        self.root.mkdir()
        self.state = temporary / 'runtime'
        self.config = self.root / 'config/codex.yaml'
        self.config.parent.mkdir()
        example = Path(__file__).resolve().parents[1] / 'config/examples/codex-insight.yaml'
        config = yaml.safe_load(example.read_text(encoding='utf-8'))
        self.config.write_text(yaml.safe_dump(config), encoding='utf-8')
        (self.config.parent / 'research_topics.yaml').write_text(yaml.safe_dump({
            'schema_version': 1, 'topics': {'agent_memory': {
                'enabled': True, 'name': 'Agent Memory', 'description': '记忆研究',
                'scope': ['记忆写入与使用'], 'keywords': ['agent memory'],
            }},
        }), encoding='utf-8')
        sources, hashes = [], {}
        for identity, role in [('R1', 'current'), ('H1', 'history')]:
            cycle = self.cycle if role == 'current' else 'history-fixture'
            base = 'agent_memory/%s/%s' % (cycle, identity.lower())
            summary_path = 'summary/%s.md' % base
            original_path = 'collection/agent_memory/%s/items/%s/original.md' % (
                cycle, identity.lower())
            summary = '已审阅总结：作者分别讨论记忆写入与使用。'
            original = '# 记忆机制\n\n作者分别讨论记忆写入与使用。'
            for relative, text in [(summary_path, summary), (original_path, original)]:
                path = self.root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding='utf-8')
                hashes[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
            sources.append({
                'id': identity, 'title': '测试原文 ' + identity,
                'url': 'https://example.org/' + identity,
                'source_id': identity.lower(), 'summary_path': summary_path,
                'original_path': original_path, 'summary_text': summary,
                'original_text': original, 'published_at': '2029-12-01',
                'research_date': '2030-01-01', 'role': role, 'coverage': 'full_text',
            })
        self.bundle = {'topic': 'agent_memory', 'cycle_id': self.cycle,
                       'sources': sources, 'input_hashes': hashes,
                       'history_note': '测试历史，不代表真实论文或趋势。'}
        def frozen_bundle(root, topic, cycle_id, **kwargs):
            bundle = copy.deepcopy(self.bundle)
            bundle['topic'], bundle['cycle_id'] = topic, cycle_id
            return bundle

        self.preparer = patch.object(harness, 'prepare_codex_bundle',
                                     side_effect=frozen_bundle)
        self.preparer.start()
        self.addCleanup(self.preparer.stop)

    def run_harness(self, backend, **kwargs):
        return harness.run(self.root, self.config, self.cycle, backend=backend,
                           state_root=self.state, **kwargs)

    def test_accuracy_review_preserves_all_insights_and_only_writes_test(self):
        backend = RecordingBackend()
        result = self.run_harness(backend)
        self.assertEqual(result['status'], 'complete')
        self.assertEqual(backend.calls, [('start', 'generation'), ('start', 'review')])
        self.assertEqual(result['task_count'], 2)
        self.assertEqual(result['turn_count'], 2)
        self.assertIsNone(result['model_request_count'])
        receipt = yaml.safe_load((self.root / result['receipt_path']).read_text(encoding='utf-8'))
        self.assertIsNone(receipt['model_request_count'])
        tasks = {task.phase: task for task in backend.tasks.values()}
        self.assertNotEqual(tasks['generation'].model, tasks['review'].model)
        outputs = list((self.root / 'insights').rglob('*.md'))
        self.assertTrue(outputs)
        text = '\n'.join(path.read_text(encoding='utf-8') for path in outputs)
        for number in range(3):
            self.assertIn('观察%s' % number, text)
        for parent in ['insights', 'articles']:
            for path in (self.root / parent).rglob('*.md'):
                self.assertIn('test', path.relative_to(self.root).parts)

    def test_unknown_generation_is_inspected_without_resending(self):
        backend = RecordingBackend(
            scripts={'generation': {'_status': 'blocked_unknown'},
                     'review': {'decision': 'pass'}},
        )
        self.assertEqual(self.run_harness(backend, retry_failed=True)['status'], 'blocked_unknown')
        self.assertEqual(self.run_harness(backend)['status'], 'blocked_unknown')
        self.assertEqual(backend.calls.count(('start', 'generation')), 1)
        backend.inspected['generation'] = candidate()
        self.assertEqual(self.run_harness(backend)['status'], 'complete')
        self.assertEqual(backend.calls.count(('start', 'generation')), 1)
        self.assertIn(('inspect', 'generation'), backend.calls)

    def test_explicit_failed_review_retry_keeps_the_generation_and_original_attempt(self):
        backend = RecordingBackend(scripts={
            'generation': candidate(), 'review': {'_status': 'failed'},
        })
        self.assertEqual(self.run_harness(backend)['status'], 'failed')
        self.assertEqual(self.run_harness(backend)['status'], 'failed')
        self.assertEqual(backend.calls, [('start', 'generation'), ('start', 'review')])
        backend.scripts['review'] = {'decision': 'pass'}
        result = self.run_harness(backend, retry_failed=True)
        self.assertEqual(result['status'], 'complete')
        self.assertEqual(result['failed_retry_count'], 1)
        self.assertEqual(result['task_count'], 3)
        self.assertEqual(backend.calls.count(('start', 'generation')), 1)
        self.assertEqual(backend.calls.count(('start', 'review')), 2)
        self.assertTrue(any(key.endswith('/review-attempt-2') for key in backend.handles))
        state = harness._checkpoint(next(self.state.rglob('state.json')))
        archived = state['failed_attempts'][0]
        self.assertEqual(archived['phase'], 'review')
        self.assertEqual(archived['task']['status'], 'failed')
        self.assertEqual(state['tasks']['review']['attempt'], 2)

    def test_repeated_explicit_failure_is_bounded_and_does_not_spend_a_third_attempt(self):
        backend = RecordingBackend(scripts={'generation': {'_status': 'failed'}})
        self.assertEqual(self.run_harness(backend)['status'], 'failed')
        self.assertEqual(self.run_harness(backend, retry_failed=True)['status'], 'failed')
        final = self.run_harness(backend, retry_failed=True)
        self.assertEqual(final['reason'], 'failed_retry_limit_reached')
        self.assertEqual(final['failed_retry_count'], 1)
        self.assertEqual(backend.calls, [('start', 'generation'), ('start', 'generation')])

    def test_completed_generation_is_reused_after_interruption(self):
        config = yaml.safe_load(self.config.read_text(encoding='utf-8'))
        config.pop('prompts', None)
        self.config.write_text(yaml.safe_dump(config), encoding='utf-8')
        backend = RecordingBackend()
        self.run_harness(backend, fail_after='generation')
        # The next day/new history must not change an already frozen task.
        with patch.object(harness, 'prepare_codex_bundle',
                          side_effect=AssertionError('Resume must use its frozen corpus')):
            self.assertEqual(self.run_harness(backend)['status'], 'complete')
        self.assertEqual(backend.calls.count(('start', 'generation')), 1)
        tasks = {task.phase: task for task in backend.tasks.values()}
        self.assertTrue(tasks['review'].instructions.startswith(harness.ACCURACY_REVIEW + '\n候选：'))

    def test_export_retry_reuses_review(self):
        backend = RecordingBackend()
        self.run_harness(backend, fail_after='export')
        self.assertEqual(self.run_harness(backend)['status'], 'complete')
        self.assertEqual(backend.calls, [('start', 'generation'), ('start', 'review')])

    def test_export_retry_preserves_manual_edit(self):
        backend = RecordingBackend()
        self.run_harness(backend, fail_after='export')
        paths = [path for parent in ['insights', 'articles']
                 for path in (self.root / parent).rglob('*.md')
                 if self.cycle in path.parts]
        self.assertTrue(paths)
        selected = paths[0]
        selected.write_text('人工补充，必须保留。', encoding='utf-8')
        self.assertEqual(self.run_harness(backend)['status'], 'conflict')
        self.assertEqual(selected.read_text(encoding='utf-8'), '人工补充，必须保留。')
        self.assertEqual(backend.calls, [('start', 'generation'), ('start', 'review')])

    def test_one_accuracy_revision_then_review_in_a_new_thread(self):
        config = yaml.safe_load(self.config.read_text(encoding='utf-8'))
        config['prompts'] = {'version': harness.CONCISE_PROMPT_VERSION}
        config['generation']['target_words'] = list(harness.CONCISE_TARGET_WORDS)
        self.config.write_text(yaml.safe_dump(config), encoding='utf-8')
        backend = RecordingBackend(scripts={
            'generation': candidate(1),
            'review': {'decision': 'revise', 'issues': [
                {'category': 'accuracy', 'location': 'report',
                 'reason': '应明确这是推测', 'suggestion': '限定结论范围'}]},
            'revision': candidate(1),
            'review_revision': {'decision': 'pass'},
        })
        self.assertEqual(self.run_harness(backend)['status'], 'complete')
        self.assertEqual(backend.calls, [
            ('start', 'generation'), ('start', 'review'),
            ('continue_turn', 'revision'), ('start', 'review_revision'),
        ])
        tasks = {task.phase: task for task in backend.tasks.values()}
        self.assertIn('正文和洞察合计参考 700–1200 字', tasks['generation'].instructions)
        self.assertIn('只保留会改变判断或验证方法的细节', tasks['generation'].instructions)
        self.assertIn('自然、合乎语法的现代中文', tasks['generation'].instructions)
        for phase in ('review', 'review_revision'):
            self.assertIn('中文若因语序、指代或修饰关系不明', tasks[phase].instructions)
        self.assertIn('用自然、合乎语法的中文消除歧义', tasks['revision'].instructions)
        self.assertEqual(self.run_harness(backend)['status'], 'complete')
        self.assertEqual(len(backend.calls), 4)

    def test_style_only_feedback_does_not_reject_or_rewrite(self):
        backend = RecordingBackend(scripts={
            'generation': candidate(1),
            'review': {'decision': 'revise', 'issues': [
                {'category': 'style', 'location': 'report',
                 'reason': '章节太少且没有反例小节', 'suggestion': '增加固定小节'}]},
        })
        self.assertEqual(self.run_harness(backend)['status'], 'complete')
        self.assertEqual(backend.calls, [('start', 'generation'), ('start', 'review')])

    def test_observed_same_model_cannot_claim_independent_model_review(self):
        backend = RecordingBackend(observed={'generation': 'same-runtime-model',
                                             'review': 'same-runtime-model'})
        self.assertNotIn(self.run_harness(backend)['status'], {'complete', 'no_insight'})
        self.assertFalse(list((self.root / 'insights').rglob('*.md')))

    def test_no_supported_insight_is_a_normal_outcome(self):
        backend = RecordingBackend(scripts={
            'generation': {'outcome': 'no_insight', 'insights': [], 'topics': [],
                           'report': {'title': '暂无线索', 'body': '本批不足以形成新的洞察。'}},
            'review': {'decision': 'pass'},
        })
        self.assertEqual(self.run_harness(backend)['status'], 'no_insight')
        self.assertFalse(list((self.root / 'articles').rglob('*.md')))


if __name__ == '__main__':
    unittest.main()
