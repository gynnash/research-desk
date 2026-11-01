"""Offline adapter boundaries: no SDK process, credentials, network or inference."""

import io
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import researchdesk_codex as codex


def task(task_id, phase, model='fixture-generator'):
    return codex.TaskSpec(
        task_id=task_id, stage='insight', phase=phase, topic='agent_memory',
        cycle_id='offline-fixture', model=model, input_dir=Path('/not-read'),
        instructions='Offline adapter contract only.')


class CodexAdapterAcceptance(unittest.TestCase):
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
            self.assertIn('per_model_request_budget_hook_unavailable', readiness['reasons'])
            self.assertIn('siwc_child_environment_not_accepted', readiness['reasons'])
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


if __name__ == '__main__':
    unittest.main()
