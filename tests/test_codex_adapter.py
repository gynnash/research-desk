"""Offline adapter boundaries: no SDK process, credentials, network or inference."""

import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from contextlib import contextmanager, ExitStack

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import codex


def task(task_id, phase, model='fixture-generator'):
    return codex.TaskSpec(
        task_id=task_id, stage='insight', phase=phase, topic='agent_memory',
        cycle_id='offline-fixture', model=model, input_dir=Path('/not-read'),
        instructions='Offline adapter contract only.')


class CodexAdapterAcceptance(unittest.TestCase):
    def test_frozen_task_limit_can_increase_without_enabling_read_only_requests(self):
        backend = codex.CodexBackend({'max_requests_per_task': 3}, root=Path('/not-read'))
        generation = task('generate', 'generation')
        with patch('batch.cycle_request_budget', return_value=None):
            self.assertEqual(backend._gateway(generation).max_requests, 3)

        with patch('batch.cycle_request_budget',
                   return_value={'insight_max_requests_per_task': 100}) as policy:
            self.assertEqual(backend._gateway(generation).max_requests, 100)
            self.assertEqual(backend._gateway(generation, read_only=True).max_requests, 0)
            disabled = codex.CodexBackend({'max_requests_per_task': 0}, root=backend.root)
            self.assertEqual(disabled._gateway(generation).max_requests, 0)
            policy.assert_called_once_with(backend.root, generation.topic, generation.cycle_id)
        self.assertEqual(backend.profile['max_requests_per_task'], 3)

    def test_real_backend_stays_blocked_even_with_matching_versions_and_live_flag(self):
        forbidden = AssertionError('Preflight must not start SDK or read credentials')
        with patch.object(codex, '_installed_version', return_value=codex.SDK_VERSION), \
                patch.object(codex.sys, 'version_info', (3, 10, 0)), \
                patch.object(subprocess, 'Popen', side_effect=forbidden), \
                patch('builtins.open', side_effect=forbidden), \
                patch.object(io, 'open', side_effect=forbidden), \
                patch.object(os, 'open', side_effect=forbidden):
            backend = codex.CodexBackend({'live_ready': True})
            readiness = backend.preflight()
            self.assertFalse(readiness['live_ready'])
            self.assertEqual(readiness['sdk_installed'], codex.SDK_VERSION)
            self.assertIn('repository_root_required', readiness['reasons'])
            self.assertIn('researchdesk_siwc_required', readiness['reasons'])
            handle = {'thread_id': 'unopened-thread', 'turn_id': 'unopened-turn'}
            results = [backend.start(task('generate', 'generation')),
                       backend.continue_turn(handle, task('revise', 'revision')),
                       backend.inspect(handle), backend.resume(handle),
                       backend.interrupt(handle)]
            self.assertTrue(all(result.status == 'blocked' for result in results))
            self.assertTrue(all(result.model_request_count is None for result in results))

    def test_sdk_events_exclude_raw_reasoning_tool_arguments_and_output(self):
        for item_type in ('reasoning', 'commandExecution', 'mcpToolCall'):
            with self.subTest(item_type=item_type):
                event = SimpleNamespace(method='item/completed', payload={
                    'threadId': 'thread-1', 'turnId': 'turn-1',
                    'item': {'id': 'item-1', 'type': item_type, 'status': 'completed',
                             'content': 'PRIVATE_REASONING',
                             'arguments': {'access_token': 'SECRET_ARGUMENT'},
                             'command': 'PRIVATE_COMMAND',
                             'aggregatedOutput': 'PRIVATE_OUTPUT'},
                })
                normalized = codex.sdk_event(event)
                self.assertEqual(normalized, {
                    'type': 'item/completed', 'thread_id': 'thread-1', 'turn_id': 'turn-1',
                    'item': {'id': 'item-1', 'type': item_type, 'status': 'completed'},
                })

    def test_unknown_turn_is_inspected_and_resumed_without_starting_another_turn(self):
        backend = codex.MockCodexBackend({'generation': {
            'status': 'blocked_unknown', 'inspect_status': 'completed',
            'inspect_final_response': 'Recovered completed response.',
        }})
        events = []
        result = backend.start(task('generate', 'generation'), events.append)
        self.assertEqual(result.status, 'blocked_unknown')
        handle = {'thread_id': result.thread_id, 'turn_id': result.turn_id}
        inspected = backend.inspect(handle)
        resumed = backend.resume(handle)
        self.assertEqual(inspected.status, 'completed')
        self.assertEqual(resumed.final_response, 'Recovered completed response.')
        self.assertEqual((resumed.thread_id, resumed.turn_id),
                         (result.thread_id, result.turn_id))
        self.assertEqual(sum(event['type'] == 'turn/started' for event in events), 1)
        self.assertEqual([call['operation'] for call in backend.calls].count('start'), 1)
        self.assertNotIn('continue_turn', [call['operation'] for call in backend.calls])

    def test_revision_reuses_generator_thread_and_review_is_independent(self):
        backend = codex.MockCodexBackend({
            'generation': {'status': 'completed', 'final_response': 'Candidate.',
                           'events': [
                               {'type': 'item/completed', 'item': {'id': 'read-1'}},
                               {'type': 'item/completed', 'item': {'id': 'read-2'}},
                           ]},
            'revision': {'status': 'completed', 'final_response': 'Revised candidate.'},
            'review': {'status': 'completed', 'final_response': 'Accuracy passed.'},
        })
        events = []
        generated = backend.start(task('generate', 'generation'), events.append)
        handle = {'thread_id': generated.thread_id, 'turn_id': generated.turn_id}
        revised = backend.continue_turn(handle, task('revise', 'revision'), events.append)
        reviewed = backend.start(task('review', 'review', 'fixture-reviewer'), events.append)
        self.assertEqual(generated.thread_id, revised.thread_id)
        self.assertNotEqual(generated.turn_id, revised.turn_id)
        self.assertNotEqual(reviewed.thread_id, revised.thread_id)
        self.assertNotEqual(reviewed.requested_model, revised.requested_model)
        self.assertEqual(sum(event['type'] == 'item/completed' for event in events), 2)
        for result in (generated, revised, reviewed):
            self.assertEqual(result.status, 'completed')
            self.assertIsNone(result.usage)
            self.assertIsNone(result.model_request_count)
            self.assertIsNone(result.observed_model)


@contextmanager
def sdk_lifecycle_fixture(terminal='completed'):
    """Exercise the real driver through fake public SDK objects, never a process."""
    calls, threads, configurations = [], {}, []

    class Gateway:
        base_url = 'http://127.0.0.1:12345/v1'
        token = 'DISPOSABLE_FIXTURE_CAPABILITY'
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def request_count(self, task_id):
            return 2
        def response_model(self, task_id):
            return 'fixture-observed-model'

    class Turn:
        def __init__(self, thread):
            self.thread_id = thread.id
            self.id = 'turn-%d' % len(calls)
            self.thread = thread
        def interrupt(self):
            calls.append(('interrupt', self.id))
        def stream(self):
            item = {'id': 'answer', 'type': 'agentMessage',
                    'phase': 'final_answer', 'text': 'Final fixture response.'}
            yield SimpleNamespace(method='item/completed', payload={
                'threadId': self.thread_id, 'turnId': self.id, 'item': item})
            yield SimpleNamespace(method='thread/tokenUsage/updated', payload={
                'threadId': self.thread_id, 'turnId': self.id,
                'tokenUsage': {'total': {'totalTokens': 17}}})
            if terminal is not None:
                result = {'id': self.id, 'status': terminal, 'items': [item]}
                self.thread.turns.append(result)
                yield SimpleNamespace(method='turn/completed', payload={
                    'threadId': self.thread_id, 'turn': result})

    class Thread:
        def __init__(self, identity):
            self.id, self.turns = identity, []
        def turn(self, instructions, **kwargs):
            calls.append(('turn', self.id))
            return Turn(self)
        def read(self, **kwargs):
            calls.append(('read', self.id))
            return {'thread': {'id': self.id, 'turns': self.turns}}

    class Client:
        def __init__(self, config):
            configurations.append(config)
        def __enter__(self):
            return self
        def __exit__(self, *args):
            calls.append(('close', None))
        def thread_start(self, **kwargs):
            identity = 'thread-%d' % (len(threads) + 1)
            threads[identity] = Thread(identity)
            calls.append(('thread_start', identity))
            return threads[identity]
        def thread_resume(self, identity, **kwargs):
            calls.append(('thread_resume', identity))
            return threads[identity]

    sdk = SimpleNamespace(Codex=Client, CodexConfig=lambda **kwargs: kwargs,
                          ApprovalMode=SimpleNamespace(deny_all='deny_all'))
    with tempfile.TemporaryDirectory() as temporary, ExitStack() as stack:
        directory = Path(temporary)
        root = directory / 'repository'
        root.mkdir()
        profile = {'auth_source': 'researchdesk_siwc',
                   'run_directory': str(directory / 'runtime')}
        stack.enter_context(patch.object(codex, '_installed_version', return_value=codex.SDK_VERSION))
        stack.enter_context(patch.object(codex.sys, 'version_info', (3, 12, 0)))
        stack.enter_context(patch.object(codex.platform, 'system', return_value='Darwin'))
        stack.enter_context(patch.object(codex.importlib.util, 'find_spec', return_value=object()))
        stack.enter_context(patch.object(codex, '_sdk_module', return_value=sdk))
        stack.enter_context(patch.object(codex, '_runtime_binary', return_value=Path('/fixture/codex')))
        stack.enter_context(patch.object(codex, '_build_runtime', return_value={
            'codex_bin': '/fixture/wrapper', 'config_overrides': (), 'env': {},
            'gateway_token_env_var': 'FIXTURE_GATEWAY_CAPABILITY'}))
        factory = lambda task_spec: Gateway()
        yield (codex.CodexBackend(profile, root, factory), profile, root,
               factory, calls, configurations)


class CodexPublicSdkLifecycle(unittest.TestCase):
    def test_completed_stream_and_cross_instance_resume_do_not_replay_a_turn(self):
        with sdk_lifecycle_fixture() as (backend, profile, root, factory, calls, configurations):
            events = []
            result = backend.start(task('generate', 'generation'), events.append)
            self.assertEqual(result.status, 'completed')
            self.assertEqual(result.final_response, 'Final fixture response.')
            self.assertEqual(result.usage, {'total': {'totalTokens': 17}})
            self.assertEqual(result.model_request_count, 2)
            self.assertEqual(result.observed_model, 'fixture-observed-model')
            handle = {'thread_id': result.thread_id, 'turn_id': result.turn_id}
            recovered = codex.CodexBackend(profile, root, factory).resume(handle)
            self.assertEqual(recovered.status, 'completed')
            self.assertEqual(recovered.final_response, result.final_response)
            self.assertEqual(sum(operation == 'turn' for operation, _ in calls), 1)
            self.assertEqual(sum(operation == 'close' for operation, _ in calls), 2)
            self.assertTrue(any(event['type'] == 'turn/completed' for event in events))
            self.assertEqual(configurations[0]['client_name'], 'ResearchDesk')
            self.assertFalse(configurations[0]['experimental_api'])
            self.assertIn('model_providers.researchdesk_gateway.env_key="FIXTURE_GATEWAY_CAPABILITY"',
                          configurations[0]['config_overrides'])

    def test_stream_text_is_not_success_without_completed_terminal_status(self):
        for terminal in (None, 'failed', 'interrupted'):
            with self.subTest(terminal=terminal), sdk_lifecycle_fixture(terminal) as fixture:
                result = fixture[0].start(task('generate', 'generation'))
                self.assertEqual(result.status, terminal or 'blocked_unknown')
                self.assertEqual(result.model_request_count, 2)
                self.assertNotEqual(result.status, 'completed')


if __name__ == '__main__':
    unittest.main()
