#!/usr/bin/env python3
"""Codex backend contract and deterministic, network-free contract driver.

The real driver uses only the public SDK. A local budgeted Responses gateway and
verified runtime isolation are required before starting it. Constructors and
preflight never launch a process, read authorization or perform inference.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, replace
import hashlib
import importlib
from importlib import metadata
import importlib.util
import json
import os
import platform
import queue
import sys
import threading
import time
from pathlib import Path
from typing import Any, Callable, Mapping, Optional
from contextlib import contextmanager


SDK_PACKAGE = "openai-codex"
SDK_VERSION = "0.163.0"
RUNTIME_PACKAGE = "openai-codex-cli-bin"
EventSink = Optional[Callable[[dict], None]]


@dataclass
class TaskSpec:
    task_id: str
    stage: str
    phase: str
    topic: str
    cycle_id: str
    model: str
    input_dir: Path
    instructions: str


@dataclass
class TaskResult:
    status: str
    thread_id: Optional[str] = None
    turn_id: Optional[str] = None
    final_response: Optional[str] = None
    requested_model: Optional[str] = None
    observed_model: Optional[str] = None
    usage: Optional[dict] = None
    # None means unknown, not one request per task or turn.
    model_request_count: Optional[int] = None
    failure_class: Optional[str] = None


def _installed_version(package: str) -> Optional[str]:
    """Read distribution metadata only; never import/start the SDK runtime."""
    try:
        return metadata.version(package)
    except metadata.PackageNotFoundError:
        return None


def _emit(sink: EventSink, event: dict) -> None:
    if sink is not None:
        # The callback is the durable journal boundary; do not swallow errors.
        sink(deepcopy(event))


def sdk_event(event: Any, thread_id: Optional[str] = None,
              turn_id: Optional[str] = None) -> dict:
    """Normalize the inspected SDK Notification without raw reasoning/secrets.

    This uses Notification.method/payload from the public wheel. It does not
    create another JSON-RPC transport and is also usable with offline probes.
    """
    payload = event.payload
    if hasattr(payload, "model_dump"):
        value = payload.model_dump(mode="json", by_alias=True)
    elif isinstance(payload, Mapping):
        value = dict(payload)
    else:
        value = {}
    kind = event.method
    result = {"type": kind,
              "thread_id": value.get("threadId", thread_id),
              "turn_id": value.get("turnId", turn_id)}
    if kind in ("turn/started", "turn/completed"):
        turn = value.get("turn", {})
        result["turn_id"] = turn.get("id", result["turn_id"])
        result["status"] = turn.get("status")
    elif kind == "thread/started":
        result["thread_id"] = value.get("thread", {}).get("id", thread_id)
    elif kind == "thread/tokenUsage/updated":
        result["usage"] = value.get("tokenUsage")
    elif kind == "model/rerouted":
        result.update({"requested_model": value.get("fromModel"),
                       "observed_model": value.get("toModel")})
    elif kind in ("item/started", "item/completed"):
        item = value.get("item", {})
        # No raw reasoning, command output, tool arguments or auth response.
        result["item"] = {key: item[key] for key in ("id", "type", "status")
                          if key in item}
    return result


def _plain(value):
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json", by_alias=True)
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def _sdk_module():
    return importlib.import_module("openai_codex")


def _runtime_binary():
    distribution = metadata.distribution(RUNTIME_PACKAGE)
    for entry in distribution.files or ():
        if str(entry).endswith("/bin/codex"):
            return Path(distribution.locate_file(entry)).resolve()
    raise RuntimeError("bundled_runtime_binary_missing")


def _build_runtime(task, binary, gateway, directory):
    isolation = importlib.import_module("codex_isolation")
    runtime = isolation.build_runtime(
        task, binary, gateway.token, gateway.base_url, run_directory=directory)
    checked = isolation.verify_isolation(runtime)
    if not (checked.get("passed") or checked.get("ok")):
        raise RuntimeError("runtime_isolation_probe_failed")
    return runtime


def _response_from_items(items):
    fallback = None
    for wrapped in reversed(items or []):
        item = _plain(wrapped)
        if "root" in item:
            item = item["root"]
        if item.get("type") != "agentMessage":
            continue
        if item.get("phase") == "final_answer":
            return item.get("text")
        if item.get("phase") is None and fallback is None:
            fallback = item.get("text")
    return fallback


class CodexBackend:
    """Public SDK lifecycle with a budgeted gateway and verified file boundary."""

    def __init__(self, profile=None, root=None, gateway_factory=None):
        self.profile = dict(profile) if isinstance(profile, Mapping) else {}
        self.root = Path(root).resolve() if root is not None else None
        self.gateway_factory = gateway_factory
        self._active = {}
        self._results = {}
        self._state_lock = threading.RLock()

    def _directory(self):
        value = self.profile.get("run_directory")
        if not isinstance(value, str) or not Path(value).is_absolute():
            return None
        path = Path(value)
        if path.is_symlink():
            return None
        path = path.resolve()
        if self.root is not None:
            try:
                path.relative_to(self.root)
                return None
            except ValueError:
                pass
        return path

    def preflight(self) -> dict:
        sdk = _installed_version(SDK_PACKAGE)
        runtime = _installed_version(RUNTIME_PACKAGE)
        reasons = []
        if sys.version_info < (3, 10):
            reasons.append("python_3_10_required")
        if platform.system() != "Darwin":
            reasons.append("macos_isolation_profile_required")
        if sdk != SDK_VERSION:
            reasons.append("sdk_missing_or_version_mismatch")
        if runtime != SDK_VERSION:
            reasons.append("bundled_runtime_missing_or_version_mismatch")
        if self.profile.get("sdk_version", SDK_VERSION) != SDK_VERSION:
            reasons.append("sdk_profile_version_mismatch")
        if self.profile.get("auth_source") != "researchdesk_siwc":
            reasons.append("researchdesk_siwc_required")
        if self.root is None:
            reasons.append("repository_root_required")
        if self._directory() is None:
            reasons.append("external_run_directory_required")
        if (self.gateway_factory is None
                and importlib.util.find_spec("codex_gateway") is None):
            reasons.append("budgeted_membership_gateway_unavailable")
        if importlib.util.find_spec("codex_isolation") is None:
            reasons.append("runtime_isolation_unavailable")
        return {
            "backend": "codex", "driver": "python_sdk", "live_ready": not reasons,
            "offline_ready": True, "sdk_required": SDK_VERSION,
            "sdk_installed": sdk, "runtime_installed": runtime,
            "capability_evidence": "pinned_sdk_and_local_gateway",
            "model_access_verified": False,
            "capabilities": {
                "provider_config_overrides": True,
                "child_env_overrides": True,
                "child_env_replacement": False,
                "client_identity": True,
                "turn_notifications": True,
                "thread_read_resume": True,
                "turn_interrupt": True,
                "per_inference_reservation": True,
            },
            "reasons": reasons,
        }

    def _blocked(self, handle=None, task=None, on_event=None) -> TaskResult:
        handle = handle or {}
        result = TaskResult(
            status="blocked", thread_id=handle.get("thread_id"),
            turn_id=handle.get("turn_id"),
            requested_model=task.model if task else None,
            failure_class="codex_preflight_failed")
        _emit(on_event, {"type": "backend/blocked", "thread_id": result.thread_id,
                         "turn_id": result.turn_id,
                         "failure_class": result.failure_class,
                         "reasons": self.preflight()["reasons"]})
        return result

    def _state(self):
        directory = self._directory()
        if directory is None:
            return {"schema_version": 1, "threads": {}}
        path = directory / "adapter-state.json"
        if path.is_symlink():
            raise RuntimeError("adapter_state_symlink")
        if not path.exists():
            return {"schema_version": 1, "threads": {}}
        value = json.loads(path.read_text(encoding="utf-8"))
        if value.get("schema_version") != 1 or not isinstance(value.get("threads"), dict):
            raise RuntimeError("adapter_state_invalid")
        return value

    def _remember(self, task, thread_id, turn_id=None, result=None):
        with self._state_lock:
            value = self._state()
            entry = value["threads"].setdefault(thread_id, {"turns": {}})
            entry["task"] = {key: getattr(task, key) for key in (
                "task_id", "stage", "phase", "topic", "cycle_id", "model")}
            entry["task"]["input_dir"] = str(Path(task.input_dir).resolve())
            if turn_id is not None:
                entry["turns"][turn_id] = {
                    "task": dict(entry["task"]),
                    "status": result.status if result else "blocked_unknown"}
            directory = self._directory()
            directory.mkdir(parents=True, exist_ok=True, mode=0o700)
            temporary = directory / (".adapter-state-%s" % threading.get_ident())
            descriptor = os.open(str(temporary), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            try:
                with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                    json.dump(value, stream, ensure_ascii=False, sort_keys=True)
                    stream.write("\n")
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(str(temporary), str(directory / "adapter-state.json"))
            finally:
                if temporary.exists():
                    temporary.unlink()

    def _task_for_handle(self, handle):
        entry = self._state()["threads"].get(handle.get("thread_id"))
        if entry is None:
            return None
        saved = entry.get("turns", {}).get(handle.get("turn_id"), {}).get("task", entry["task"])
        return TaskSpec(**dict(saved, input_dir=Path(saved["input_dir"]), instructions=""))

    def _gateway(self, task, read_only=False):
        if self.gateway_factory is not None:
            return self.gateway_factory(task)
        from codex_gateway import DEFAULT_MAX_REQUESTS, MembershipGateway
        max_requests = 0 if read_only else self.profile.get("max_requests_per_task", DEFAULT_MAX_REQUESTS)
        if max_requests != 0 and task.stage == "insight":
            # Runtime allowance can grow without changing the frozen task profile.
            from batch import cycle_request_budget
            policy = cycle_request_budget(self.root, task.topic, task.cycle_id)
            if policy is not None:
                max_requests = policy.get("insight_max_requests_per_task", max_requests)
        return MembershipGateway(
            self.root, task.topic, task.cycle_id, task.task_id,
            allowed_models=[task.model], phase=task.phase,
            max_requests=max_requests)

    @contextmanager
    def _session(self, task, read_only=False):
        with self._gateway(task, read_only=read_only) as gateway:
            runtime = _build_runtime(task, _runtime_binary(), gateway, self._directory())
            sdk = _sdk_module()
            overrides = tuple(runtime["config_overrides"]) + (
                'model_provider="researchdesk_gateway"',
                'model_providers.researchdesk_gateway.name="ResearchDesk ChatGPT plan"',
                'model_providers.researchdesk_gateway.base_url=' + json.dumps(gateway.base_url),
                'model_providers.researchdesk_gateway.env_key=' + json.dumps(
                    runtime["gateway_token_env_var"]),
                'model_providers.researchdesk_gateway.wire_api="responses"',
                'model_providers.researchdesk_gateway.requires_openai_auth=false',
                'model_providers.researchdesk_gateway.supports_websockets=false',
                'model_providers.researchdesk_gateway.request_max_retries=0',
                'model_providers.researchdesk_gateway.stream_max_retries=0',
            )
            config = sdk.CodexConfig(
                codex_bin=str(runtime["codex_bin"]), config_overrides=overrides,
                cwd=str(Path(task.input_dir).resolve()), env=runtime["env"],
                client_name="ResearchDesk", client_title="ResearchDesk",
                client_version="0.1", experimental_api=False)
            with sdk.Codex(config) as client:
                yield client, gateway, sdk

    @staticmethod
    def _meter(gateway, task, result):
        result.model_request_count = gateway.request_count(task.task_id)
        getter = getattr(gateway, "response_model", None)
        if not callable(getter):
            getter = getattr(gateway, "observed_model", None)
        if callable(getter):
            result.observed_model = getter(task.task_id) or result.observed_model
        return result

    def _consume(self, turn, task, gateway, on_event):
        result = TaskResult("blocked_unknown", turn.thread_id, turn.id,
                            requested_model=task.model,
                            failure_class="turn_terminal_not_received")
        channel = queue.Queue()
        def read_events():
            try:
                for event in turn.stream():
                    channel.put(("event", event))
            except Exception:
                channel.put(("error", None))
            finally:
                channel.put(("end", None))
        threading.Thread(target=read_events, daemon=True).start()
        timeout = self.profile.get("timeout_seconds", 240)
        deadline = time.monotonic() + max(1, float(timeout))
        items = []
        timed_out = False
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                if timed_out:
                    result.failure_class = "timeout_terminal_unknown"
                    break
                timed_out = True
                _emit(on_event, {"type": "turn/interrupt_requested",
                                 "thread_id": turn.thread_id, "turn_id": turn.id})
                # SDK interrupt waits on RPC; do not let that wait disable timeout.
                def request_interrupt():
                    try:
                        turn.interrupt()
                    except Exception:
                        pass
                threading.Thread(target=request_interrupt, daemon=True).start()
                deadline = time.monotonic() + 5
                continue
            try:
                kind, event = channel.get(timeout=remaining)
            except queue.Empty:
                continue
            if kind != "event":
                break
            value = _plain(event.payload)
            native = sdk_event(event, turn.thread_id, turn.id)
            _emit(on_event, native)
            if event.method == "item/completed" and value.get("turnId") == turn.id:
                items.append(value.get("item", {}))
            elif event.method == "thread/tokenUsage/updated":
                if value.get("turnId") == turn.id:
                    result.usage = value.get("tokenUsage")
            elif event.method == "model/rerouted":
                if value.get("turnId") == turn.id:
                    result.observed_model = value.get("toModel")
            elif event.method == "turn/completed":
                completed = value.get("turn", {})
                if completed.get("id") != turn.id:
                    continue
                status = completed.get("status")
                if status not in ("completed", "failed", "interrupted"):
                    break
                result.status = status
                result.final_response = _response_from_items(items) or _response_from_items(
                    completed.get("items", []))
                result.failure_class = None if status == "completed" else "codex_turn_" + status
                break
        return self._meter(gateway, task, result)

    def _execute(self, task, on_event, handle=None):
        if not self.preflight()["live_ready"]:
            return self._blocked(handle, task, on_event)
        thread_id = handle.get("thread_id") if handle else None
        turn_id = None
        turn_requested = False
        try:
            with self._session(task) as (client, gateway, sdk):
                options = {"approval_mode": sdk.ApprovalMode.deny_all,
                           "cwd": str(Path(task.input_dir).resolve()),
                           "model_provider": "researchdesk_gateway"}
                if thread_id is not None:
                    thread = client.thread_resume(thread_id, **options)
                else:
                    thread = client.thread_start(model=task.model, **options)
                    thread_id = thread.id
                    self._remember(task, thread_id)
                    _emit(on_event, {"type": "thread/started", "thread_id": thread_id,
                                     "turn_id": None})
                turn_requested = True
                turn = thread.turn(task.instructions, model=task.model,
                                   approval_mode=sdk.ApprovalMode.deny_all)
                turn_id = turn.id
                self._remember(task, thread_id, turn_id)
                self._active[(thread_id, turn_id)] = (turn, thread)
                _emit(on_event, {"type": "turn/started", "thread_id": thread_id,
                                 "turn_id": turn_id, "status": "inProgress"})
                result = self._consume(turn, task, gateway, on_event)
                self._remember(task, thread_id, turn_id, result)
                self._results[(thread_id, turn_id)] = result
                return result
        except Exception:
            # No raw SDK/upstream error: it could contain credentials or content.
            result = TaskResult(
                "blocked_unknown" if turn_requested else "failed", thread_id, turn_id,
                requested_model=task.model,
                failure_class="codex_connection_or_journal_failed" if turn_requested else "codex_start_failed")
            if thread_id is not None:
                self._remember(task, thread_id, turn_id, result)
            return result
        finally:
            self._active.pop((thread_id, turn_id), None)

    def start(self, task: TaskSpec, on_event: EventSink = None) -> TaskResult:
        return self._execute(task, on_event)

    def continue_turn(self, handle: dict, task: TaskSpec,
                      on_event: EventSink = None) -> TaskResult:
        previous = self.inspect(handle)
        if previous.status != "completed":
            return replace(previous, failure_class="previous_turn_not_completed")
        return self._execute(task, on_event, handle)

    def inspect(self, handle: dict) -> TaskResult:
        key = (handle.get("thread_id"), handle.get("turn_id"))
        if key in self._results:
            return deepcopy(self._results[key])
        if not self.preflight()["live_ready"]:
            return self._blocked(handle)
        try:
            task = self._task_for_handle(handle)
            if task is None:
                return TaskResult("blocked_unknown", *key,
                                  failure_class="runtime_context_missing")
            with self._session(task, read_only=True) as (client, gateway, sdk):
                thread = client.thread_resume(
                    handle["thread_id"], approval_mode=sdk.ApprovalMode.deny_all,
                    model_provider="researchdesk_gateway")
                snapshot = _plain(thread.read(include_turns=True)).get("thread", {})
                turn = next((turn for turn in snapshot.get("turns", [])
                             if turn.get("id") == handle.get("turn_id")), None)
                if turn is None:
                    return TaskResult("blocked_unknown", *key,
                                      failure_class="turn_not_available")
                status = turn.get("status")
                result = TaskResult(
                    status if status in ("completed", "failed", "interrupted") else "blocked_unknown",
                    *key, final_response=_response_from_items(turn.get("items", [])),
                    requested_model=task.model,
                    failure_class=None if status == "completed" else "recovered_turn_" + str(status))
                return self._meter(gateway, task, result)
        except Exception:
            return TaskResult("blocked_unknown", *key, failure_class="inspect_failed")

    def resume(self, handle: dict) -> TaskResult:
        return self.inspect(handle)

    def interrupt(self, handle: dict) -> TaskResult:
        key = (handle.get("thread_id"), handle.get("turn_id"))
        active = self._active.get(key)
        if active is None:
            result = self.inspect(handle)
            if result.status in ("completed", "failed", "interrupted", "blocked"):
                return result
            return replace(result, status="blocked_unknown",
                           failure_class="interrupt_handle_unavailable")
        try:
            active[0].interrupt()
        except Exception:
            return TaskResult("blocked_unknown", *key, failure_class="interrupt_request_failed")
        return TaskResult("blocked_unknown", *key, failure_class="interrupt_confirmation_pending")


class MockCodexBackend:
    """Scripted native-event driver. Never imports SDK or performs network I/O.

    scripts maps task_id (preferred) or phase to an explicit result mapping:
      {"events": [{"type": "item/completed", ...}, ...],
       "status": "completed", "final_response": "...", "usage": {...}}
    Use status=blocked_unknown plus inspect_status/inspect_final_response to
    simulate losing a connection before a completed result can be reconciled.
    A list of mappings under one key supplies successive, explicit attempts.
    """

    def __init__(self, scripts=None, profile=None):
        self.scripts = deepcopy(scripts or {})
        self.profile = dict(profile) if isinstance(profile, Mapping) else {}
        self.calls = []
        self._records = {}
        self._tasks = {}
        self._positions = {}
        self._turn_number = 0

    def preflight(self) -> dict:
        return {"backend": "mock_codex", "driver": "scripted_offline",
                "live_ready": False, "offline_ready": True, "reasons": [],
                "model_access_verified": False}

    @staticmethod
    def _key(handle):
        return (handle.get("thread_id"), handle.get("turn_id"))

    def _script(self, task):
        key = task.task_id if task.task_id in self.scripts else task.phase
        script = self.scripts.get(key)
        if isinstance(script, list):
            position = self._positions.get(key, 0)
            self._positions[key] = position + 1
            script = script[position] if position < len(script) else None
        return deepcopy(script) if isinstance(script, Mapping) else None

    def _execute(self, task, on_event, thread_id=None):
        script = self._script(task)
        if script is None:
            result = TaskResult(status="blocked", requested_model=task.model,
                                failure_class="mock_script_missing")
            _emit(on_event, {"type": "backend/blocked", "thread_id": thread_id,
                             "turn_id": None, "failure_class": result.failure_class})
            return result
        self._turn_number += 1
        if thread_id is None:
            thread_id = "mock-thread-" + hashlib.sha256(
                task.task_id.encode("utf-8")).hexdigest()[:16]
            _emit(on_event, {"type": "thread/started", "thread_id": thread_id,
                             "turn_id": None})
        turn_id = "mock-turn-%d" % self._turn_number
        result = TaskResult(
            status="blocked_unknown", thread_id=thread_id, turn_id=turn_id,
            requested_model=task.model, failure_class="mock_connection_lost")
        self._records[(thread_id, turn_id)] = {"result": result, "script": script}
        self._tasks[task.task_id] = (thread_id, turn_id)
        _emit(on_event, {"type": "turn/started", "thread_id": thread_id,
                         "turn_id": turn_id, "status": "inProgress"})
        for raw in script.get("events", []):
            event = deepcopy(raw)
            event.setdefault("type", "mock/event")
            # Script IDs cannot impersonate another task's thread or turn.
            event.update(thread_id=thread_id, turn_id=turn_id)
            _emit(on_event, event)
        status = script.get("status", "completed")
        if status in ("unknown", "running", "inProgress"):
            status = "blocked_unknown"
        result = TaskResult(
            status=status, thread_id=thread_id, turn_id=turn_id,
            final_response=script.get("final_response"),
            requested_model=task.model, observed_model=script.get("observed_model"),
            usage=deepcopy(script.get("usage")),
            model_request_count=script.get("model_request_count"),
            failure_class=script.get("failure_class") or (
                "mock_connection_lost" if status == "blocked_unknown" else None))
        self._records[(thread_id, turn_id)]["result"] = result
        if status in ("completed", "failed", "interrupted"):
            _emit(on_event, {"type": "turn/completed", "thread_id": thread_id,
                             "turn_id": turn_id, "status": status})
        return deepcopy(result)

    def start(self, task: TaskSpec, on_event: EventSink = None) -> TaskResult:
        self.calls.append({"operation": "start", "task_id": task.task_id})
        # Calling start twice is never a hidden second model request.
        if task.task_id in self._tasks:
            thread_id, turn_id = self._tasks[task.task_id]
            return self.inspect({"thread_id": thread_id, "turn_id": turn_id})
        return self._execute(task, on_event)

    def continue_turn(self, handle: dict, task: TaskSpec,
                      on_event: EventSink = None) -> TaskResult:
        self.calls.append({"operation": "continue_turn", "task_id": task.task_id,
                           "handle": deepcopy(handle)})
        previous = self.inspect(handle)
        if previous.status != "completed":
            return replace(previous, failure_class="previous_turn_not_completed")
        if task.task_id in self._tasks:
            thread_id, turn_id = self._tasks[task.task_id]
            return self.inspect({"thread_id": thread_id, "turn_id": turn_id})
        return self._execute(task, on_event, thread_id=handle["thread_id"])

    def inspect(self, handle: dict) -> TaskResult:
        self.calls.append({"operation": "inspect", "handle": deepcopy(handle)})
        record = self._records.get(self._key(handle))
        if record is None:
            return TaskResult(status="blocked_unknown",
                              thread_id=handle.get("thread_id"),
                              turn_id=handle.get("turn_id"),
                              failure_class="mock_handle_unknown")
        script, result = record["script"], record["result"]
        if "inspect_status" in script:
            result = replace(
                result, status=script["inspect_status"],
                final_response=script.get("inspect_final_response", result.final_response),
                failure_class=script.get("inspect_failure_class"))
            record["result"] = result
        return deepcopy(result)

    def resume(self, handle: dict) -> TaskResult:
        self.calls.append({"operation": "resume", "handle": deepcopy(handle)})
        return self.inspect(handle)

    def interrupt(self, handle: dict) -> TaskResult:
        self.calls.append({"operation": "interrupt", "handle": deepcopy(handle)})
        record = self._records.get(self._key(handle))
        if record is None or record["result"].status == "completed":
            return self.inspect(handle)
        # A request is not a confirmed interruption unless explicitly scripted.
        if record["script"].get("interrupt_status") == "interrupted":
            record["result"] = replace(record["result"], status="interrupted",
                                       failure_class="mock_interrupted")
            return deepcopy(record["result"])
        return replace(record["result"], status="blocked_unknown",
                       failure_class="interrupt_confirmation_unknown")
