"""Parent-side control proxy for one account-owned Eitaa Child process."""

from __future__ import annotations

from collections import deque
from collections.abc import Collection, Mapping
from contextlib import contextmanager
import json
import os
from pathlib import Path
import queue
import signal
import subprocess
import sys
import threading
import time
from typing import Any, Callable, Iterator

from ..config import BridgeConfig
from ..errors import EitaaRuntimeError, WorkerIpcError
from ..infrastructure.data_scope import ProviderAccountScope
from ..infrastructure.coordinator import (
    CoordinatorDatabase,
    MessengerAccountRuntimeRecord,
    WorkerInstanceRecord,
)
from ..infrastructure.diagnostics import RuntimeLogger
from ..infrastructure.eitaa.session_ownership import EitaaSessionOwnership
from ..infrastructure.worker_ipc import (
    IPC_MAX_MESSAGE_BYTES,
    WorkerIpcCodec,
    WorkerIpcSecretFile,
)
from .scheduler import EitaaPriority

_RESPONSE_EOF = object()
_RESPONSE_INVALID = object()
_SAFE_ERROR_CODE = frozenset("abcdefghijklmnopqrstuvwxyz0123456789_")
_PARENT_FORBIDDEN_FIELDS = frozenset(
    {
        "active_dialog_sync_job",
        "auth_challenge",
        "auth_lock",
        "auth_runtime",
        "avatar_source_cache",
        "avatar_source_cache_lock",
        "avatar_source_cache_ttl_seconds",
        "background_tasks",
        "contact_import_cancellations",
        "contact_import_jobs",
        "contact_import_lock",
        "content_index_active",
        "content_index_cancellations",
        "content_index_jobs",
        "content_index_lock",
        "content_index_store",
        "dialog_catalog",
        "dialog_sync_jobs",
        "eitaa_contacts_cache",
        "eitaa_contacts_cache_lock",
        "eitaa_contacts_cache_ttl_seconds",
        "eitaa_lock",
        "jobs_lock",
        "media_cache_files",
        "media_cache_lock",
        "pending_read_receipts",
        "read_queue_lock",
        "read_receipt_delay_seconds",
        "read_worker_active",
        "sender_directory",
    }
)
_PROVIDER_OPERATION_METHODS = frozenset(
    {
        "eitaa.provider.dialogs.query",
        "eitaa.provider.history.query",
        "eitaa.provider.messages.send_text",
        "eitaa.provider.media.read",
        "eitaa.provider.media.read_chunk",
        "eitaa.provider.contacts.query",
        "eitaa.provider.contacts.upsert",
    }
)


class EitaaProcessWorkerClient:
    """Synchronous authenticated control channel to one already-spawned Child."""

    def __init__(
        self,
        process: subprocess.Popen[str],
        codec: WorkerIpcCodec,
        *,
        messenger_account_id: str,
        request_timeout_seconds: int,
    ) -> None:
        self.process = process
        self.codec = codec
        self.messenger_account_id = messenger_account_id
        self.request_timeout_seconds = request_timeout_seconds
        self._responses: queue.Queue[str | object] = queue.Queue(maxsize=128)
        self._stderr_codes: deque[str] = deque(maxlen=32)
        self._request_lock = threading.RLock()
        self._closed = False
        self._worker_pid: int | None = None
        self._worker_instance_id: str | None = None
        self._worker_generation: int | None = None
        self._stdout_thread = threading.Thread(
            target=self._read_stdout,
            name=f"eitaa-ipc-out-{messenger_account_id[:8]}",
            daemon=True,
        )
        self._stderr_thread = threading.Thread(
            target=self._read_stderr,
            name=f"eitaa-ipc-err-{messenger_account_id[:8]}",
            daemon=True,
        )
        self._stdout_thread.start()
        self._stderr_thread.start()

    @classmethod
    def spawn(
        cls,
        config: BridgeConfig,
        ownership: EitaaSessionOwnership,
    ) -> "EitaaProcessWorkerClient":
        account_id = ownership.messenger_account_id
        runtime_directory = ownership.account_runtime_directory
        if account_id is None or runtime_directory is None:
            raise EitaaRuntimeError(
                "A process worker requires account-scoped runtime paths.",
                code="eitaa_process_account_scope_required",
            )
        feature = config.features.worker_process
        material, secret_file = WorkerIpcSecretFile.create(
            runtime_directory / "ipc",
            messenger_account_id=account_id,
            provider="eitaa",
            ttl_seconds=min(300, max(5, feature.startup_timeout_seconds * 2)),
        )
        command = [
            sys.executable,
            "-m",
            "eitaa_bridge.interfaces.provider_worker",
            "--provider",
            "eitaa",
            "--messenger-account-id",
            account_id,
            "--secret-file",
            str(secret_file),
            "--config",
            str(config.source_file),
        ]
        environment = dict(os.environ)
        source_packages = Path(__file__).resolve().parents[2]
        environment["PYTHONPATH"] = os.pathsep.join(
            part
            for part in (
                str(source_packages),
                environment.get("PYTHONPATH", ""),
            )
            if part
        )
        environment["PYTHONUTF8"] = "1"
        environment["PYTHONIOENCODING"] = "utf-8"
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        process: subprocess.Popen[str] | None = None
        client: EitaaProcessWorkerClient | None = None
        try:
            process = subprocess.Popen(
                command,
                cwd=config.source_file.parent,
                env=environment,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="strict",
                bufsize=1,
                creationflags=creationflags,
            )
            client = cls(
                process,
                WorkerIpcCodec(material),
                messenger_account_id=account_id,
                request_timeout_seconds=feature.request_timeout_seconds,
            )
            hello = client.request(
                "worker.hello",
                timeout_seconds=feature.startup_timeout_seconds,
            )
            reported_pid = hello.get("worker_pid")
            if (
                hello.get("status") != "bootstrap_ready"
                or isinstance(reported_pid, bool)
                or not isinstance(reported_pid, int)
                or reported_pid <= 0
                or reported_pid == os.getpid()
                or hello.get("provider") != "eitaa"
                or hello.get("messenger_account_id") != account_id
                or hello.get("runtime_boundary") != "child_process"
            ):
                raise EitaaRuntimeError(
                    "The Eitaa Child returned an invalid bootstrap handshake.",
                    safe_context={
                        "status": hello.get("status"),
                        "worker_pid_valid": (
                            isinstance(reported_pid, int)
                            and not isinstance(reported_pid, bool)
                            and reported_pid > 0
                            and reported_pid != os.getpid()
                        ),
                        "provider": hello.get("provider"),
                        "account_matches": (
                            hello.get("messenger_account_id") == account_id
                        ),
                        "runtime_boundary": hello.get("runtime_boundary"),
                    },
                    code="eitaa_process_bootstrap_handshake_invalid",
                )
            client._worker_pid = reported_pid
            return client
        except Exception:
            secret_file.unlink(missing_ok=True)
            if client is not None:
                client.terminate()
            elif process is not None and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=3)
            raise

    @property
    def process_id(self) -> int:
        return int(self._worker_pid or self.process.pid)

    @property
    def stderr_codes(self) -> tuple[str, ...]:
        return tuple(self._stderr_codes)

    def bind_fence(self, worker_instance_id: str, worker_generation: int) -> None:
        if (
            not isinstance(worker_instance_id, str)
            or not worker_instance_id
            or isinstance(worker_generation, bool)
            or not isinstance(worker_generation, int)
            or worker_generation <= 0
        ):
            raise EitaaRuntimeError(
                "The Eitaa Child fence is invalid.",
                code="eitaa_process_fence_invalid",
            )
        with self._request_lock:
            if self._worker_instance_id is not None:
                if (
                    self._worker_instance_id == worker_instance_id
                    and self._worker_generation == worker_generation
                ):
                    return
                raise EitaaRuntimeError(
                    "The Eitaa Child fence is already bound.",
                    code="eitaa_process_fence_already_bound",
                )
            self._worker_instance_id = worker_instance_id
            self._worker_generation = worker_generation

    def request(
        self,
        method: str,
        payload: Mapping[str, object] | None = None,
        *,
        timeout_seconds: float | None = None,
    ) -> dict[str, object]:
        timeout = float(timeout_seconds or self.request_timeout_seconds)
        selected_payload = dict(payload or {})
        if self._worker_instance_id is not None and method not in {
            "worker.hello",
            "eitaa.runtime.start",
        }:
            supplied_instance = selected_payload.get("worker_instance_id")
            supplied_generation = selected_payload.get("worker_generation")
            if supplied_instance not in {None, self._worker_instance_id} or (
                supplied_generation not in {None, self._worker_generation}
            ):
                raise EitaaRuntimeError(
                    "The Eitaa Child request fence is inconsistent.",
                    code="eitaa_process_fence_mismatch",
                )
            selected_payload["worker_instance_id"] = self._worker_instance_id
            selected_payload["worker_generation"] = self._worker_generation
        deadline = int(time.time() * 1000 + timeout * 1000)
        raw = self.codec.request(
            method,
            selected_payload,
            deadline_unix_ms=deadline,
        )
        expected = self.codec.decode(raw, expected_kind="request")
        with self._request_lock:
            if self._closed or self.process.poll() is not None:
                raise EitaaRuntimeError(
                    "The Eitaa Child process is not available.",
                    safe_context={
                        "messenger_account_id": self.messenger_account_id,
                        "stderr_codes": self.stderr_codes,
                    },
                    code="eitaa_process_unavailable",
                )
            stream = self.process.stdin
            if stream is None:
                raise EitaaRuntimeError(
                    "The Eitaa Child input channel is unavailable.",
                    code="eitaa_process_channel_unavailable",
                )
            try:
                stream.write(raw + "\n")
                stream.flush()
            except (BrokenPipeError, OSError) as exc:
                raise EitaaRuntimeError(
                    "The Eitaa Child request could not be written.",
                    safe_context={"error_type": type(exc).__name__},
                    code="eitaa_process_channel_failed",
                ) from exc
            try:
                response_raw = self._responses.get(timeout=timeout)
            except queue.Empty as exc:
                raise EitaaRuntimeError(
                    "The Eitaa Child request timed out.",
                    safe_context={"messenger_account_id": self.messenger_account_id},
                    code="eitaa_process_request_timeout",
                ) from exc
            if response_raw is _RESPONSE_EOF:
                raise EitaaRuntimeError(
                    "The Eitaa Child exited before replying.",
                    safe_context={
                        "messenger_account_id": self.messenger_account_id,
                        "stderr_codes": self.stderr_codes,
                    },
                    code="eitaa_process_exited",
                )
            if response_raw is _RESPONSE_INVALID:
                self.terminate()
                raise EitaaRuntimeError(
                    "The Eitaa Child response stream violated its size or queue limit.",
                    code="eitaa_process_response_invalid",
                )
            assert isinstance(response_raw, str)
            try:
                response = self.codec.decode(response_raw, expected_kind="response")
            except WorkerIpcError as exc:
                self.terminate()
                raise EitaaRuntimeError(
                    "The Eitaa Child response failed IPC validation.",
                    safe_context={"ipc_error_code": exc.code},
                    code="eitaa_process_response_invalid",
                ) from exc
            if (
                response.correlation_id != expected.correlation_id
                or response.method != expected.method
            ):
                self.terminate()
                raise EitaaRuntimeError(
                    "The Eitaa Child response correlation is invalid.",
                    code="eitaa_process_response_correlation_invalid",
                )
            error = response.payload.get("error")
            if isinstance(error, Mapping):
                code = str(error.get("code") or "eitaa_process_request_failed")
                if (
                    not 3 <= len(code) <= 64
                    or code[0] not in "abcdefghijklmnopqrstuvwxyz"
                    or any(character not in _SAFE_ERROR_CODE for character in code)
                ):
                    code = "eitaa_process_request_failed"
                raise EitaaRuntimeError(
                    "The Eitaa Child rejected the request.",
                    safe_context={"messenger_account_id": self.messenger_account_id},
                    code=code,
                )
            return dict(response.payload)

    def close(self) -> None:
        with self._request_lock:
            if self._closed:
                return
            try:
                if self.process.poll() is None:
                    self.request("worker.stop", timeout_seconds=5)
            finally:
                self._closed = True
                if self.process.stdin is not None:
                    try:
                        self.process.stdin.close()
                    except OSError:
                        pass
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.terminate()
            raise EitaaRuntimeError(
                "The Eitaa Child did not stop within the shutdown deadline.",
                code="eitaa_process_stop_timeout",
            )
        if self.process.returncode != 0:
            raise EitaaRuntimeError(
                "The Eitaa Child exited unsuccessfully.",
                safe_context={"stderr_codes": self.stderr_codes},
                code="eitaa_process_exit_failed",
            )

    def terminate(self) -> None:
        self._closed = True
        if self.process.stdin is not None:
            try:
                self.process.stdin.close()
            except OSError:
                pass
        worker_pid = self._worker_pid
        if (
            worker_pid is not None
            and worker_pid != self.process.pid
            and self.process.poll() is None
        ):
            try:
                os.kill(worker_pid, signal.SIGTERM)
            except (ProcessLookupError, PermissionError, OSError):
                pass
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=3)

    def _read_stdout(self) -> None:
        stream = self.process.stdout
        if stream is not None:
            try:
                while True:
                    line = stream.readline(IPC_MAX_MESSAGE_BYTES + 2)
                    if not line:
                        break
                    if len(line.encode("utf-8")) > IPC_MAX_MESSAGE_BYTES + 1:
                        self._queue_response(_RESPONSE_INVALID)
                        break
                    selected = line.rstrip("\r\n")
                    if selected:
                        if not self._queue_response(selected):
                            break
            except (OSError, UnicodeError):
                pass
        self._queue_response(_RESPONSE_EOF)

    def _queue_response(self, value: str | object) -> bool:
        try:
            self._responses.put(value, timeout=1.0)
            return True
        except queue.Full:
            try:
                self.process.terminate()
            except OSError:
                pass
            return False

    def _read_stderr(self) -> None:
        stream = self.process.stderr
        if stream is None:
            return
        try:
            while True:
                line = stream.readline(4098)
                if not line:
                    break
                if len(line.encode("utf-8")) > 4097:
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(payload, dict):
                    continue
                code = payload.get("error_code")
                if (
                    isinstance(code, str)
                    and 3 <= len(code) <= 64
                    and code[0] in "abcdefghijklmnopqrstuvwxyz"
                    and all(character in _SAFE_ERROR_CODE for character in code)
                ):
                    self._stderr_codes.append(code)
        except (OSError, UnicodeError):
            return


class RemoteEitaaSchedulerView:
    """Read-only scheduler DTO; callbacks never cross the process boundary."""

    def __init__(self, client: EitaaProcessWorkerClient) -> None:
        self._client = client

    def snapshot(self) -> dict[str, object]:
        payload = self._client.request("eitaa.runtime.describe")
        runtime = payload.get("runtime")
        if not isinstance(runtime, Mapping):
            raise EitaaRuntimeError(
                "The Eitaa Child scheduler summary is invalid.",
                code="eitaa_process_response_invalid",
            )
        scheduler = runtime.get("scheduler")
        if not isinstance(scheduler, Mapping):
            raise EitaaRuntimeError(
                "The Eitaa Child scheduler summary is missing.",
                code="eitaa_process_response_invalid",
            )
        return dict(scheduler)

    @staticmethod
    def is_worker_thread() -> bool:
        return False

    @staticmethod
    def has_higher_priority_work(_priority: EitaaPriority | int) -> bool:
        raise EitaaRuntimeError(
            "Scheduler coordination requires an explicit process RPC.",
            code="eitaa_process_operation_ipc_required",
        )


class EitaaProcessRuntime:
    """Parent control plane with no provider Core, cache, job, or account log."""

    is_process_isolated = True

    def __init__(
        self,
        config: BridgeConfig,
        runtime_record: MessengerAccountRuntimeRecord,
        worker: WorkerInstanceRecord,
        ownership: EitaaSessionOwnership,
        client: EitaaProcessWorkerClient,
        *,
        coordinator: CoordinatorDatabase,
        application_logger: RuntimeLogger,
    ) -> None:
        self.config = config
        self.runtime_record = runtime_record
        self.worker = worker
        self.ownership = ownership
        self.data_scope = ProviderAccountScope.for_account(
            runtime_record.messenger_account_id,
            provider=runtime_record.provider,
        )
        self.client = client
        self._coordinator = coordinator
        self.logger = application_logger
        self.scheduler = RemoteEitaaSchedulerView(client)
        self._closed = False
        self._close_lock = threading.Lock()
        self._supervisor_stop = threading.Event()
        self._supervisor_thread: threading.Thread | None = None
        self._supervisor_failure_reported = False
        self._supervisor_last_heartbeat_at: float | None = None
        self._supervisor_consecutive_failures = 0

    @property
    def process_id(self) -> int:
        return self.client.process_id

    @property
    def is_account_scoped(self) -> bool:
        return True

    def health(self) -> dict[str, object]:
        return self.client.request("worker.health")

    def core_probe(self) -> dict[str, object]:
        return self.client.request("eitaa.runtime.core_probe")

    def provider_operation_request(
        self,
        method: str,
        payload: Mapping[str, object],
        *,
        timeout_seconds: float,
    ) -> dict[str, object]:
        """Call only the audited, high-level provider RPC allowlist."""

        if method not in _PROVIDER_OPERATION_METHODS:
            raise EitaaRuntimeError(
                "The Eitaa provider RPC method is not allowlisted.",
                safe_context={"method": str(method)[:64]},
                code="eitaa_process_operation_ipc_forbidden",
            )
        if self._closed:
            raise EitaaRuntimeError(
                "The Eitaa process runtime is closed.",
                code="eitaa_process_unavailable",
            )
        return self.client.request(
            method,
            payload,
            timeout_seconds=timeout_seconds,
        )

    def safe_summary(self) -> dict[str, object]:
        payload = self.client.request("eitaa.runtime.describe")
        runtime = payload.get("runtime")
        if not isinstance(runtime, Mapping):
            raise EitaaRuntimeError(
                "The Eitaa process runtime summary is invalid.",
                code="eitaa_process_response_invalid",
            )
        return {
            **dict(runtime),
            "process_isolated": True,
            "process_id": self.process_id,
            "worker_instance_id": self.worker.worker_instance_id,
            "worker_generation": self.worker.generation,
            "supervisor": self.supervisor_summary(),
        }

    def supervisor_summary(self) -> dict[str, object]:
        return {
            "running": bool(
                self._supervisor_thread is not None
                and self._supervisor_thread.is_alive()
                and not self._supervisor_stop.is_set()
            ),
            "consecutive_failures": self._supervisor_consecutive_failures,
            "heartbeat_observed": self._supervisor_last_heartbeat_at is not None,
            "failure_reported": self._supervisor_failure_reported,
        }

    def start_supervisor(
        self,
        on_failure: Callable[["EitaaProcessRuntime", str, int | None], None],
    ) -> None:
        if self._supervisor_thread is not None:
            return
        feature = self.config.features.worker_process
        self._supervisor_stop.clear()

        def supervise() -> None:
            while not self._supervisor_stop.wait(feature.heartbeat_interval_seconds):
                if self._closed:
                    return
                wrapper_exit = self.client.process.poll()
                if wrapper_exit is not None:
                    self._report_supervisor_failure(
                        on_failure,
                        "worker_process_exited",
                        wrapper_exit,
                    )
                    return
                try:
                    heartbeat = self.client.request(
                        "worker.heartbeat",
                        timeout_seconds=feature.heartbeat_timeout_seconds,
                    )
                    if (
                        heartbeat.get("status") != "ready"
                        or heartbeat.get("worker_pid") != self.process_id
                        or heartbeat.get("worker_instance_id")
                        != self.worker.worker_instance_id
                        or heartbeat.get("worker_generation") != self.worker.generation
                    ):
                        raise EitaaRuntimeError(
                            "The Eitaa Child heartbeat fence is invalid.",
                            code="eitaa_process_heartbeat_invalid",
                        )
                    self.worker = self._coordinator.heartbeat_worker_fenced(
                        self.worker.worker_instance_id,
                        expected_generation=self.worker.generation,
                        expected_process_id=self.process_id,
                    )
                    if self._supervisor_consecutive_failures:
                        self.logger.emit(
                            "eitaa_process_heartbeat_recovered",
                            fields={
                                "messenger_account_id": (
                                    self.runtime_record.messenger_account_id
                                ),
                                "worker_instance_id": self.worker.worker_instance_id,
                                "worker_generation": self.worker.generation,
                                "consecutive_failures": (
                                    self._supervisor_consecutive_failures
                                ),
                            },
                        )
                    self._supervisor_consecutive_failures = 0
                    self._supervisor_last_heartbeat_at = time.monotonic()
                except Exception as exc:
                    self._supervisor_consecutive_failures += 1
                    self.logger.emit(
                        "eitaa_process_heartbeat_failed",
                        level="warning",
                        fields={
                            "messenger_account_id": (
                                self.runtime_record.messenger_account_id
                            ),
                            "worker_instance_id": self.worker.worker_instance_id,
                            "worker_generation": self.worker.generation,
                            "consecutive_failures": (
                                self._supervisor_consecutive_failures
                            ),
                            "error_type": type(exc).__name__,
                            "error_code": getattr(exc, "code", None),
                        },
                    )
                    if (
                        self._supervisor_consecutive_failures
                        >= feature.heartbeat_failure_threshold
                    ):
                        self._report_supervisor_failure(
                            on_failure,
                            "worker_heartbeat_failure_limit",
                            self.client.process.poll(),
                        )
                        return

        self._supervisor_thread = threading.Thread(
            target=supervise,
            name=f"eitaa-process-supervisor-{self.runtime_record.messenger_account_id[:8]}",
            daemon=True,
        )
        self._supervisor_thread.start()
        self.logger.emit(
            "eitaa_process_supervisor_started",
            fields={
                "messenger_account_id": self.runtime_record.messenger_account_id,
                "worker_instance_id": self.worker.worker_instance_id,
                "worker_generation": self.worker.generation,
                "heartbeat_interval_seconds": feature.heartbeat_interval_seconds,
                "heartbeat_failure_threshold": feature.heartbeat_failure_threshold,
            },
        )

    def _report_supervisor_failure(
        self,
        on_failure: Callable[["EitaaProcessRuntime", str, int | None], None],
        reason_code: str,
        exit_code: int | None,
    ) -> None:
        if self._supervisor_failure_reported or self._closed:
            return
        self._supervisor_failure_reported = True
        self._supervisor_stop.set()
        try:
            on_failure(self, reason_code, exit_code)
        except Exception as exc:
            self.logger.emit(
                "eitaa_process_recovery_callback_failed",
                level="error",
                fields={
                    "messenger_account_id": self.runtime_record.messenger_account_id,
                    "worker_instance_id": self.worker.worker_instance_id,
                    "worker_generation": self.worker.generation,
                    "error_type": type(exc).__name__,
                    "error_code": getattr(exc, "code", None),
                },
            )

    def stop_supervisor(self) -> None:
        self._supervisor_stop.set()
        thread = self._supervisor_thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=2.0)
        self._supervisor_thread = None

    def fence(self, *, reason_code: str) -> None:
        with self._close_lock:
            if self._closed:
                return
            self._closed = True
        self.stop_supervisor()
        self.client.terminate()
        self.logger.emit(
            "eitaa_process_worker_fenced",
            level="warning",
            fields={
                "messenger_account_id": self.runtime_record.messenger_account_id,
                "worker_instance_id": self.worker.worker_instance_id,
                "worker_generation": self.worker.generation,
                "reason_code": reason_code,
            },
        )

    def refresh_auth_record(self) -> MessengerAccountRuntimeRecord:
        record = self._coordinator.messenger_account_runtime(
            self.runtime_record.messenger_account_id
        )
        self.runtime_record = record
        return record

    def transition_auth(
        self,
        *,
        expected_states: Collection[str],
        expected_generation: int,
        new_state: str,
        increment_generation: bool,
        reason_code: str,
        action: str,
        mark_validated: bool = False,
        audit_when_unchanged: bool = True,
        actor_app_user_id: str | None = None,
        actor_global_role: str | None = None,
        request_id: str | None = None,
        safe_metadata: Mapping[str, Any] | None = None,
    ) -> MessengerAccountRuntimeRecord:
        record = self._coordinator.transition_messenger_auth(
            self.runtime_record.messenger_account_id,
            expected_states=expected_states,
            expected_generation=expected_generation,
            new_state=new_state,
            increment_generation=increment_generation,
            reason_code=reason_code,
            action=action,
            mark_validated=mark_validated,
            audit_when_unchanged=audit_when_unchanged,
            actor_app_user_id=actor_app_user_id,
            actor_global_role=actor_global_role,
            request_id=request_id,
            safe_metadata=safe_metadata,
        )
        self.client.request(
            "eitaa.runtime.refresh_generation",
            {"session_generation": record.session_generation},
        )
        self.runtime_record = record
        return record

    def audit_auth_event(
        self,
        *,
        action: str,
        result: str,
        reason_code: str,
        actor_app_user_id: str | None = None,
        actor_global_role: str | None = None,
        request_id: str | None = None,
        safe_metadata: Mapping[str, Any] | None = None,
    ) -> None:
        self._coordinator.audit_messenger_auth_event(
            self.runtime_record.messenger_account_id,
            action=action,
            result=result,
            reason_code=reason_code,
            actor_app_user_id=actor_app_user_id,
            actor_global_role=actor_global_role,
            request_id=request_id,
            safe_metadata=safe_metadata,
        )

    def resolve_login_phone(self, supplied_phone: str | None = None) -> str:
        del supplied_phone
        raise EitaaRuntimeError(
            "Provider authentication requires a dedicated sensitive Child RPC.",
            code="eitaa_process_auth_ipc_required",
        )

    def run_sync(
        self,
        *,
        priority: EitaaPriority,
        kind: str,
        callback: Any,
        timeout: float | None = None,
    ) -> Any:
        del priority, kind, callback, timeout
        raise EitaaRuntimeError(
            "Python callbacks cannot cross the Eitaa process boundary.",
            code="eitaa_process_callback_not_serializable",
        )

    @contextmanager
    def operation_scope(self) -> Iterator[None]:
        raise EitaaRuntimeError(
            "Provider operations require an explicit DTO-based Child RPC.",
            code="eitaa_process_operation_ipc_required",
        )
        yield

    def close_shared_core(self) -> None:
        self.client.request("eitaa.runtime.close_core")

    def close(self) -> None:
        with self._close_lock:
            if self._closed:
                return
            self._closed = True
        self.stop_supervisor()
        close_error: Exception | None = None
        try:
            self.client.close()
        except Exception as exc:
            close_error = exc
        try:
            self._coordinator.complete_worker_stop(
                self.runtime_record.messenger_account_id,
                worker_instance_id=self.worker.worker_instance_id,
                reason_code=(
                    "worker_process_closed"
                    if close_error is None
                    else "worker_process_close_failed"
                ),
                pause_account=False,
            )
        except Exception as exc:
            if close_error is None:
                close_error = exc
        if close_error is not None:
            raise EitaaRuntimeError(
                "The Eitaa process runtime did not close cleanly.",
                safe_context={
                    "messenger_account_id": self.runtime_record.messenger_account_id,
                    "error_type": type(close_error).__name__,
                },
                code="eitaa_process_runtime_close_failed",
            ) from close_error

    def __getattr__(self, name: str) -> Any:
        if name in _PARENT_FORBIDDEN_FIELDS:
            raise EitaaRuntimeError(
                "Mutable provider state is owned by the Eitaa Child process.",
                safe_context={"field": name},
                code="eitaa_process_parent_state_forbidden",
            )
        if name in {"peer_directory", "contact_peers_directory", "upload_directory"}:
            raise EitaaRuntimeError(
                "Account files require an explicit Eitaa Child transfer RPC.",
                safe_context={"field": name},
                code="eitaa_process_file_transfer_ipc_required",
            )
        raise AttributeError(name)
