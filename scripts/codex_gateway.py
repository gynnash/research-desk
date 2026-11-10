"""Loopback-only Responses bridge with per-request membership reservations.

Codex receives a disposable capability, never the user's OAuth token. There is
no general proxy, tool loop, HTTP retry, or response rewriting in this module.
"""

import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import secrets
import threading
from uuid import uuid4

import batch as shared
import offline as store


DEFAULT_MAX_REQUESTS = 100


def _request_events(root):
    root = Path(root).resolve()
    positions = {}
    for path in sorted((root / 'reports/test').glob('*/codex-requests/*/events/*.yaml')):
        relative = path.relative_to(root).as_posix()
        positions[path.parent] = positions.get(path.parent, 0) + 1
        if path.name != '%06d.yaml' % positions[path.parent]:
            raise store.OfflineError('Codex 请求预留序列不连续')
        event = store.checked_yaml(root, relative)
        parts = Path(relative).parts
        if (event.get('schema_version') != 1 or event.get('type') != 'request_reserved'
                or event.get('backend') != 'codex' or event.get('topic') != parts[2]
                or event.get('cycle_id') != parts[4]
                or not isinstance(event.get('month'), str) or not re.fullmatch(r'\d{4}-\d{2}', event['month'])
                or not isinstance(event.get('task_id'), str) or not event['task_id']
                or not isinstance(event.get('request_id'), str)
                or not re.fullmatch(r'[0-9a-f-]{36}', event['request_id'])
                or not isinstance(event.get('at'), str) or event['at'][:7] != event['month']):
            raise store.OfflineError('Codex 请求预留账本无效，不能重置用量')
        yield event


def reserved_calls(root, month):
    """Actual forwarded-request reservations, independent of task/turn count."""
    return sum(event['month'] == month for event in _request_events(root))


def _json_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate JSON key')
        result[key] = value
    return result


class _StreamObservation:
    """Best-effort public model/usage metadata; never changes streamed bytes."""
    def __init__(self):
        self.pending = b''
        self.model = self.usage = None

    def feed(self, chunk):
        self.pending += chunk
        while b'\n\n' in self.pending.replace(b'\r\n', b'\n'):
            normalized = self.pending.replace(b'\r\n', b'\n')
            frame, self.pending = normalized.split(b'\n\n', 1)
            data = b'\n'.join(line[5:].lstrip() for line in frame.split(b'\n') if line.startswith(b'data:'))
            try:
                value = json.loads(data)
            except (ValueError, UnicodeError):
                continue
            if not isinstance(value, dict) or value.get('type') != 'response.completed':
                continue
            response = value.get('response', {})
            model = response.get('model') if isinstance(response, dict) else None
            if (isinstance(response, dict) and response.get('status') == 'completed' and isinstance(model, str)
                    and re.fullmatch(r'[A-Za-z0-9._:/-]{1,200}', model)):
                self.model = model
                usage = response.get('usage')
                if isinstance(usage, dict):
                    self.usage = {key: val for key, val in usage.items()
                                  if key in {'input_tokens', 'output_tokens', 'total_tokens'}
                                  and type(val) is int and val >= 0} or None
        # Observability is optional. A very large event must not add a model
        # output limit or retain arbitrary generated content in diagnostics.
        if len(self.pending) > 2_000_000:
            self.pending = b''


class MembershipGateway:
    def __init__(self, root, topic, cycle_id, task_id, allowed_models,
                 max_requests=DEFAULT_MAX_REQUESTS, client=None, phase='codex'):
        self.root = Path(root).resolve()
        if any(not isinstance(value, str) or not store.SAFE_ID.fullmatch(value) for value in (topic, cycle_id)):
            raise store.OfflineError('Codex 网关主题或轮次无效')
        if any(not isinstance(value, str) or not value or len(value) > 200
               or any(ord(char) < 32 for char in value) for value in (task_id, phase)):
            raise store.OfflineError('Codex 网关任务身份无效')
        if (not isinstance(allowed_models, (list, tuple, set)) or not allowed_models
                or any(not isinstance(model, str) or not re.fullmatch(r'[A-Za-z0-9._:/-]{1,200}', model)
                       for model in allowed_models)):
            raise store.OfflineError('Codex 网关必须配置模型白名单')
        if type(max_requests) is not int or not 0 <= max_requests <= 1000:
            raise store.OfflineError('Codex 每任务请求上限必须为非负整数，0 只允许读取已存状态')
        self.topic, self.cycle_id, self.task_id, self.phase = topic, cycle_id, task_id, phase
        self.allowed_models = set(allowed_models)
        self.max_requests, self.client = max_requests, client
        self.token = secrets.token_urlsafe(32)
        self.base_url = None
        self._server = self._thread = None
        self._running = threading.Event()

    def request_count(self, task_id):
        return sum(event['task_id'] == task_id for event in _request_events(self.root))

    def observed_model(self, task_id):
        requests = {event['request_id']: event for event in _request_events(self.root)
                    if event['task_id'] == task_id}
        models = set()
        for path in sorted((self.root / 'reports/test').glob('*/codex-requests/*/observations/*.yaml')):
            value = store.checked_yaml(self.root, path.relative_to(self.root))
            request = requests.get(value.get('request_id'))
            if request is not None:
                if (value.get('task_id') != task_id or not isinstance(value.get('model'), str)
                        or not re.fullmatch(r'[A-Za-z0-9._:/-]{1,200}', value['model'])):
                    raise store.OfflineError('Codex 响应模型记录无效')
                models.add(value['model'])
        return next(iter(models)) if len(models) == 1 else None

    def _reserve(self, model):
        with shared.global_budget_lock(self.root):
            count, cap = shared.monthly_budget(self.root, {
                'backend': 'chatgpt_plan', 'budget': {'month_max_calls': 100}})
            if count >= cap or self.request_count(self.task_id) >= self.max_requests:
                raise store.OfflineError('Codex 会员请求预算已用尽')
            shared.ensure_cycle_room(self.root, self.topic, self.cycle_id, 'insight')
            base = 'reports/test/%s/codex-requests/%s/events' % (self.topic, self.cycle_id)
            directory = store.safe_path(self.root, base)
            paths = sorted(directory.glob('*.yaml'))
            if any(path.name != '%06d.yaml' % (index + 1) for index, path in enumerate(paths)):
                raise store.OfflineError('Codex 请求预留序列不连续')
            at = shared.now()
            event = {
                'schema_version': 1, 'type': 'request_reserved', 'backend': 'codex',
                'topic': self.topic, 'cycle_id': self.cycle_id, 'task_id': self.task_id,
                'phase': self.phase, 'model_id': model, 'month': at[:7], 'at': at,
                'request_id': str(uuid4()), 'usage_status': 'unknown'}
            store.save_yaml(self.root, '%s/%06d.yaml' % (base, len(paths) + 1), event)
            return event

    def _observe(self, reservation, observation):
        if observation.model is not None:
            path = 'reports/test/%s/codex-requests/%s/observations/%s.yaml' % (
                self.topic, self.cycle_id, reservation['request_id'])
            store.save_yaml(self.root, path, {
                'schema_version': 1, 'type': 'response_observed', 'task_id': self.task_id,
                'request_id': reservation['request_id'], 'model': observation.model,
                'usage': observation.usage, 'source': 'responses_sse.response.completed'})

    def _forward(self, payload, headers):
        if not self._running.is_set():
            raise store.OfflineError('Codex 网关已停止')
        if self.client is None:
            from membership import MembershipClient, DEFAULT_PROFILE
            profile = DEFAULT_PROFILE
            runtime_path = self.root / 'config/runtime.yaml'
            if runtime_path.exists() or runtime_path.is_symlink():
                from runner import load_config
                # Honor the same local account selection as the legacy worker.
                # Invalid explicit settings must fail, never use another account.
                profile = load_config(self.root)['_profile']
            self.client = MembershipClient(profile, self.root)
        return self.client.forward_responses(payload, headers=headers)

    def _handler_class(self):
        gateway = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = 'HTTP/1.1'

            def log_message(self, *args):
                pass

            def _error(self, status, code):
                body = json.dumps({'error': {'code': code, 'message': code}}).encode()
                self.send_response(status)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(body)))
                self.send_header('Cache-Control', 'no-store')
                self.send_header('Connection', 'close')
                self.end_headers()
                self.wfile.write(body)
                self.close_connection = True

            def _unsupported(self):
                self._error(405 if self.path == '/v1/responses' else 404, 'route_not_allowed')

            do_GET = do_PUT = do_PATCH = do_DELETE = do_OPTIONS = do_HEAD = _unsupported

            def do_POST(self):
                started = False
                upstream = None
                try:
                    self.connection.settimeout(30)
                    if self.path != '/v1/responses':
                        self._error(404, 'route_not_allowed')
                        return
                    auth = self.headers.get_all('Authorization', [])
                    expected = 'Bearer ' + gateway.token
                    if len(auth) != 1 or not hmac.compare_digest(auth[0], expected):
                        self._error(401, 'invalid_capability')
                        return
                    lengths = self.headers.get_all('Content-Length', [])
                    if (len(lengths) != 1 or not re.fullmatch(r'[0-9]+', lengths[0])
                            or self.headers.get('Transfer-Encoding')
                            or self.headers.get('Content-Encoding', 'identity').lower() != 'identity'
                            or self.headers.get('Content-Type', '').split(';')[0].strip().lower() != 'application/json'):
                        self._error(400, 'unsupported_request_encoding')
                        return
                    raw = self.rfile.read(int(lengths[0]))
                    if len(raw) != int(lengths[0]):
                        self._error(400, 'incomplete_request')
                        return
                    try:
                        payload = json.loads(raw, object_pairs_hook=_json_object,
                                             parse_constant=lambda value: (_ for _ in ()).throw(ValueError('non-finite JSON')))
                    except (ValueError, UnicodeError):
                        self._error(400, 'invalid_json')
                        return
                    if (not isinstance(payload, dict) or not isinstance(payload.get('model'), str)
                            or payload['model'] not in gateway.allowed_models
                            or payload.get('store') is not False or payload.get('stream') is not True):
                        self._error(400, 'request_policy_violation')
                        return
                    identity = {}
                    for name in ('Originator', 'User-Agent'):
                        values = self.headers.get_all(name, [])
                        if len(values) > 1 or any(char in '\r\n\0' for value in values for char in value):
                            self._error(400, 'invalid_client_identity')
                            return
                        if values:
                            identity[name] = values[0]
                    try:
                        if not gateway._running.is_set():
                            self._error(503, 'gateway_stopped')
                            return
                        reservation = gateway._reserve(payload['model'])
                    except store.OfflineError:
                        self._error(429, 'membership_budget_unavailable')
                        return
                    upstream = gateway._forward(payload, identity)
                    status = getattr(upstream, 'status', 200)
                    if status != 200:
                        self._error(status if isinstance(status, int) and 400 <= status <= 599 else 502,
                                    'upstream_request_failed')
                        return
                    self.send_response(200)
                    self.send_header('Content-Type', 'text/event-stream')
                    self.send_header('Cache-Control', 'no-store')
                    self.send_header('Connection', 'close')
                    # Codex may carry turn state across Responses requests.
                    getheader = getattr(upstream, 'getheader', None)
                    if getheader:
                        for name in ('x-codex-turn-state', 'x-request-id'):
                            value = getheader(name)
                            if isinstance(value, str) and not any(char in value for char in '\r\n\0'):
                                self.send_header(name, value)
                    self.end_headers()
                    self.close_connection = True
                    started = True
                    read = getattr(upstream, 'read1', None) or upstream.read
                    observation = _StreamObservation()
                    observed = False
                    while True:
                        chunk = read(65536)
                        if not chunk:
                            break
                        if observation is not None:
                            try:
                                observation.feed(chunk)
                                if observation.model is not None and not observed:
                                    gateway._observe(reservation, observation)
                                    observed = True
                            except Exception:
                                observation = None  # Optional diagnostics cannot break a valid response.
                        self.wfile.write(chunk)
                        self.wfile.flush()
                except Exception:
                    # Neither upstream exceptions nor raw responses are safe
                    # diagnostics: they can contain OAuth headers or content.
                    if not started:
                        self._error(502, 'upstream_unavailable')
                    self.close_connection = True
                finally:
                    if upstream is not None:
                        upstream.close()

        return Handler

    def start(self):
        if self._server is not None:
            raise store.OfflineError('Codex 网关已经启动')

        class Server(ThreadingHTTPServer):
            daemon_threads = True

            def handle_error(self, request, client_address):
                pass

        self._server = Server(('127.0.0.1', 0), self._handler_class())
        self.base_url = 'http://127.0.0.1:%s/v1' % self._server.server_port
        self._running.set()
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return self

    def stop(self):
        if self._server is not None:
            self._running.clear()
            self._server.shutdown()
            self._server.server_close()
            self._thread.join(timeout=5)
            self._server = self._thread = None
            self.base_url = None
            self.token = secrets.token_urlsafe(32)

    def __enter__(self):
        return self.start()

    def __exit__(self, *args):
        self.stop()
