"""Loopback-only gateway tests with fictional in-memory upstream streams."""

from copy import deepcopy
import http.client
import io
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest import mock

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import researchdesk_batch as shared
import researchdesk_codex_gateway as gateway
import researchdesk_offline as store


STREAM = (b'event: response.output_item.done\r\n'
          b'data: {"type":"response.output_item.done","item":{"type":"function_call","name":"read_file"}}\r\n\r\n'
          b'data: {"type":"response.completed","response":{"status":"completed","model":"actual-fixture-model",'
          b'"usage":{"input_tokens":10,"output_tokens":5,"total_tokens":15},"output":[]}}\n\n')


class Response(io.BytesIO):
    status = 200

    def getheader(self, name):
        return 'fixture-turn-state' if name == 'x-codex-turn-state' else None

    def read1(self, size=-1):
        return self.read(min(17, size))


class Client:
    def __init__(self):
        self.calls = []
        self.failure = None

    def forward_responses(self, payload, headers=None):
        self.calls.append((deepcopy(payload), dict(headers or {})))
        if self.failure:
            raise self.failure
        return Response(STREAM)


class LocalServer:
    """Exercise the real handler without requesting a sandbox socket bind."""
    def __init__(self, address, handler):
        if address != ('127.0.0.1', 0):
            raise AssertionError('Only a loopback random port is permitted')
        self.server_port = 12345
        self.closed = threading.Event()

    def serve_forever(self):
        self.closed.wait()

    def shutdown(self):
        self.closed.set()

    def server_close(self):
        pass


class LocalSocket:
    def __init__(self, raw):
        self.input = io.BytesIO(raw)
        self.output = io.BytesIO()

    def makefile(self, mode, *args):
        return self.input

    def sendall(self, data):
        self.output.write(data)

    def settimeout(self, value):
        pass


class CodexGateway(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='researchdesk-gateway-test-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        (self.root / 'config').mkdir()
        (self.root / 'config/membership_budget.yaml').write_text(yaml.safe_dump({
            'schema_version': 1, 'backend': 'chatgpt_plan', 'month_max_calls': 100}))
        self.client = Client()
        self.server_patch = mock.patch.object(gateway, 'ThreadingHTTPServer', LocalServer)
        self.server_patch.start()
        self.addCleanup(self.server_patch.stop)

    def make_gateway(self, **kwargs):
        return gateway.MembershipGateway(self.root, 'agent_memory', 'fixture-cycle',
            'fixture-task', ['fixture-model'], client=self.client, **kwargs)

    def request(self, bridge, payload=None, *, path='/v1/responses', method='POST', headers=None, raw=None):
        body = (json.dumps(payload or {'model': 'fixture-model', 'store': False,
                                      'stream': True, 'input': []}).encode() if raw is None else raw)
        given = {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + bridge.token,
                 'Originator': 'codex_sdk', 'User-Agent': 'fixture-codex/1', 'Content-Length': str(len(body))}
        given.update(headers or {})
        wire = ('%s %s HTTP/1.1\r\n' % (method, path) + ''.join(
            '%s: %s\r\n' % item for item in given.items()) + '\r\n').encode() + body
        socket = LocalSocket(wire)
        bridge._handler_class()(socket, ('127.0.0.1', 12345), bridge._server)
        response = http.client.HTTPResponse(LocalSocket(socket.output.getvalue()))
        response.begin()
        return response.status, dict(response.getheaders()), response.read()

    def test_stream_native_tool_payload_and_identity_pass_through_without_oauth(self):
        payload = {'model': 'fixture-model', 'store': False, 'stream': True,
                   'input': [{'type': 'function_call_output', 'call_id': 'fixture', 'output': 'file text'}],
                   'tools': [{'type': 'function', 'name': 'read_file', 'parameters': {'type': 'object'}}]}
        with self.make_gateway() as bridge:
            token = bridge.token
            status, headers, body = self.request(bridge, payload)
            self.assertEqual((status, body), (200, STREAM))
            self.assertEqual(headers['x-codex-turn-state'], 'fixture-turn-state')
            self.assertEqual(self.client.calls[0][0], payload)
            self.assertEqual(self.client.calls[0][1], {'Originator': 'codex_sdk', 'User-Agent': 'fixture-codex/1'})
            self.assertNotIn('Authorization', self.client.calls[0][1])
            self.assertEqual(bridge.request_count('fixture-task'), 1)
            self.assertEqual(bridge.observed_model('fixture-task'), 'actual-fixture-model')
        self.assertNotEqual(token, bridge.token)
        observations = list((self.root / 'reports/test').glob('*/codex-requests/*/observations/*.yaml'))
        self.assertEqual(len(observations), 1)
        metadata = store.checked_yaml(self.root, observations[0].relative_to(self.root))
        self.assertEqual(metadata['usage']['total_tokens'], 15)
        self.assertNotIn('output', metadata)

    def test_route_auth_model_storage_streaming_and_encoding_checks_do_not_spend(self):
        with self.make_gateway() as bridge:
            for options in (
                {'path': '/v1/models'}, {'path': '/v1/responses?url=https://example.org'},
                {'method': 'GET'}, {'headers': {'Authorization': 'Bearer invalid'}},
                {'payload': {'model': 'other-model', 'store': False, 'stream': True}},
                {'payload': {'model': 'fixture-model', 'store': True, 'stream': True}},
                {'payload': {'model': 'fixture-model', 'store': False, 'stream': False}},
                {'headers': {'Content-Encoding': 'gzip'}},
                {'headers': {'Transfer-Encoding': 'chunked'}},
                {'raw': b'{"model":"other","model":"fixture-model","store":false,"stream":true}'},
            ):
                with self.subTest(options=options):
                    status, _, body = self.request(bridge, **options)
                    self.assertIn(status, (400, 401, 404, 405))
                    self.assertNotIn(bridge.token.encode(), body)
            self.assertEqual(bridge.request_count('fixture-task'), 0)
        self.assertEqual(self.client.calls, [])

    def test_each_retry_reserves_a_request_and_task_cap_survives_gateway_restart(self):
        with self.make_gateway(max_requests=2) as bridge:
            self.assertEqual(self.request(bridge)[0], 200)
            self.assertEqual(self.request(bridge)[0], 200)
            self.assertEqual(self.request(bridge)[0], 429)
        with self.make_gateway(max_requests=2) as restarted:
            self.assertEqual(self.request(restarted)[0], 429)
            self.assertEqual(restarted.request_count('fixture-task'), 2)
        self.assertEqual(len(self.client.calls), 2)

    def test_read_only_inspection_gateway_cannot_forward_or_reserve(self):
        with self.make_gateway(max_requests=0) as bridge:
            self.assertEqual(self.request(bridge)[0], 429)
            self.assertEqual(bridge.request_count('fixture-task'), 0)
        self.assertEqual(self.client.calls, [])

    def test_shared_monthly_limit_includes_archived_legacy_and_gateway_requests(self):
        month = shared.now()[:7]
        (self.root / 'config/research_state.yaml').write_text(yaml.safe_dump({
            'schema_version': 1, 'usage_months': {month: 98}}))
        old = 'reports/test/agent_memory/research-batches/old'
        store.save_yaml(self.root, old + '/manifest.yaml', {
            'backend': 'chatgpt_plan', 'created_at': shared.now(), 'budget': {'month_max_calls': 100}})
        store.save_yaml(self.root, old + '/events/000001.yaml', {'type': 'call_reserved', 'month': month})
        with self.make_gateway() as bridge:
            self.assertEqual(self.request(bridge)[0], 200)
            self.assertEqual(self.request(bridge)[0], 429)
        config = {'backend': 'chatgpt_plan', 'budget': {'month_max_calls': 100}}
        self.assertEqual(shared.monthly_budget(self.root, config), (100, 100))
        self.assertEqual(gateway.reserved_calls(self.root, month), 1)

    def test_upstream_failure_keeps_reservation_and_redacts_exception(self):
        self.client.failure = OSError('Bearer do-not-print-upstream-secret')
        with self.make_gateway(max_requests=1) as bridge:
            status, _, body = self.request(bridge)
            self.assertEqual(status, 502)
            self.assertNotIn(b'do-not-print', body)
            self.assertEqual(bridge.request_count('fixture-task'), 1)
            self.assertIsNone(bridge.observed_model('fixture-task'))
            self.assertEqual(self.request(bridge)[0], 429)
        self.assertEqual(len(self.client.calls), 1)

    def test_changed_request_ledger_does_not_silently_reset_usage(self):
        with self.make_gateway() as bridge:
            self.assertEqual(self.request(bridge)[0], 200)
        event = next((self.root / 'reports/test').glob('*/codex-requests/*/events/*.yaml'))
        event.write_text(event.read_text() + '\nchanged: true\n')
        with self.assertRaises(store.OfflineError):
            gateway.reserved_calls(self.root, shared.now()[:7])

    def test_optional_observation_failure_does_not_change_or_interrupt_stream(self):
        with self.make_gateway() as bridge:
            with mock.patch.object(bridge, '_observe', side_effect=OSError('diagnostics unavailable')):
                status, _, body = self.request(bridge)
            self.assertEqual((status, body), (200, STREAM))
            self.assertEqual(bridge.request_count('fixture-task'), 1)
            self.assertIsNone(bridge.observed_model('fixture-task'))


if __name__ == '__main__':
    unittest.main()
