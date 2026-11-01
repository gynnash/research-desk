#!/usr/bin/env python3
"""Codex backend contract and deterministic, network-free contract driver.

The real backend is deliberately fail-closed. The pinned SDK has been inspected,
but ResearchDesk's SIWC isolation, filesystem boundary and per-inference budget
have not been accepted. Merely installing the SDK does not authorize inference.
No constructor, preflight or mock method starts a Codex process or reads auth.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, replace
import hashlib
from importlib import metadata
import sys
from pathlib import Path
from typing import Any, Callable, Mapping, Optional


SDK_PACKAGE = "openai-codex"
SDK_VERSION = "0.163.0"
RUNTIME_PACKAGE = "openai-codex-cli-bin"
WHEEL_SHA256 = "d151e3ff8188bc2c07a962855d598b93bf87a49ec3440810e45a5f2e1167d99e"
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


class CodexBackend:
    """Real-SDK readiness boundary; live methods remain explicitly disabled.

    profile is non-secret configuration only. Boolean declarations in YAML
    cannot bypass unimplemented acceptance gates. In particular, no API-key
    fallback, ambient Codex login or private SDK attribute is used.
    """

    def __init__(self, profile=None):
        self.profile = dict(profile) if isinstance(profile, Mapping) else {}

    def preflight(self) -> dict:
        sdk = _installed_version(SDK_PACKAGE)
        runtime = _installed_version(RUNTIME_PACKAGE)
        reasons = []
        if sys.version_info < (3, 10):
            reasons.append("python_3_10_required")
        if sdk != SDK_VERSION:
            reasons.append("sdk_missing_or_version_mismatch")
        if runtime != SDK_VERSION:
            reasons.append("bundled_runtime_missing_or_version_mismatch")
        # These are implementation/acceptance gaps, never caller attestations.
        reasons.extend([
            "siwc_child_environment_not_accepted",
            "filesystem_and_tool_environment_isolation_not_accepted",
            "per_model_request_budget_hook_unavailable",
        ])
        return {
            "backend": "codex", "driver": "python_sdk", "live_ready": False,
            "offline_ready": True, "sdk_required": SDK_VERSION,
            "sdk_installed": sdk, "runtime_installed": runtime,
            "capability_evidence": "static_official_wheel_inspection",
            "model_access_verified": False,
            "capabilities": {
                "provider_config_overrides": True,
                "child_env_overrides": True,
                "child_env_replacement": False,
                "client_identity": True,
                "turn_notifications": True,
                "thread_read_resume": True,
                "turn_interrupt": True,
                "per_inference_reservation": False,
            },
            "reasons": reasons,
        }

    def _blocked(self, handle=None, task=None, on_event=None) -> TaskResult:
        handle = handle or {}
        result = TaskResult(
            status="blocked", thread_id=handle.get("thread_id"),
            turn_id=handle.get("turn_id"),
            requested_model=task.model if task else None,
            failure_class="codex_live_not_accepted")
        _emit(on_event, {"type": "backend/blocked", "thread_id": result.thread_id,
                         "turn_id": result.turn_id,
                         "failure_class": result.failure_class,
                         "reasons": self.preflight()["reasons"]})
        return result

    def start(self, task: TaskSpec, on_event: EventSink = None) -> TaskResult:
        return self._blocked(task=task, on_event=on_event)

    def continue_turn(self, handle: dict, task: TaskSpec,
                      on_event: EventSink = None) -> TaskResult:
        return self._blocked(handle, task, on_event)

    def inspect(self, handle: dict) -> TaskResult:
        return self._blocked(handle)

    def resume(self, handle: dict) -> TaskResult:
        # No new turn; no automatic replay of an uncertain inference.
        return self._blocked(handle)

    def interrupt(self, handle: dict) -> TaskResult:
        return self._blocked(handle)


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
