"""Dedicated Child-process host for one Eitaa MessengerAccount runtime."""

from __future__ import annotations

import base64
import os
from pathlib import Path
from typing import Mapping
import uuid

from ..errors import EitaaRuntimeError, WorkerIpcError
from ..infrastructure.config import BridgeConfigLoader
from ..infrastructure.coordinator import MessengerAccountRuntimeRecord
from ..infrastructure.worker_ipc import IPC_PROTOCOL_VERSION, IpcEnvelope
from .account_runtime import EitaaAccountRuntime
from .eitaa_auth_child_operations import EitaaAuthChildOperations
from .eitaa_provider_runtime_operations import EitaaProviderRuntimeOperations
from .provider_adapter import ProviderWorkerDispatchResult

_RUNTIME_RECORD_FIELDS = frozenset(
    {
        "messenger_account_id",
        "phone_account_id",
        "provider",
        "lifecycle_state",
        "desired_worker_state",
        "auth_state",
        "session_generation",
        "storage_revision",
    }
)


def _canonical_uuid4(value: object, *, field: str) -> str:
    try:
        parsed = uuid.UUID(str(value))
    except (ValueError, AttributeError) as exc:
        raise WorkerIpcError(
            "The Eitaa worker identity is invalid.",
            safe_context={"field": field},
            code="eitaa_process_identity_invalid",
        ) from exc
    if parsed.version != 4 or str(parsed) != str(value):
        raise WorkerIpcError(
            "The Eitaa worker identity is invalid.",
            safe_context={"field": field},
            code="eitaa_process_identity_invalid",
        )
    return str(parsed)


class EitaaProviderProcessWorker:
    """Own all mutable account runtime objects inside exactly one Child."""

    provider = "eitaa"

    def __init__(self, messenger_account_id: str, config_file: str | Path) -> None:
        self.messenger_account_id = _canonical_uuid4(
            messenger_account_id,
            field="messenger_account_id",
        )
        self.config = BridgeConfigLoader.load(config_file)
        if not self.config.features.worker_process.enabled:
            raise WorkerIpcError(
                "The Eitaa worker-process feature is disabled.",
                code="eitaa_worker_process_feature_disabled",
            )
        self.runtime: EitaaAccountRuntime | None = None
        self._provider_operations: EitaaProviderRuntimeOperations | None = None
        self._auth_operations: EitaaAuthChildOperations | None = None
        self.worker_instance_id: str | None = None
        self.worker_generation: int | None = None
        self._core_opened = False

    def dispatch(self, request: IpcEnvelope) -> ProviderWorkerDispatchResult:
        if (
            request.provider != self.provider
            or request.messenger_account_id != self.messenger_account_id
        ):
            raise WorkerIpcError(
                "The Eitaa worker request scope is invalid.",
                code="ipc_worker_scope_mismatch",
            )
        if request.method == "worker.hello":
            self._require_fields(request.payload, frozenset())
            return ProviderWorkerDispatchResult(
                {
                    "status": "ready" if self.runtime is not None else "bootstrap_ready",
                    "worker_pid": os.getpid(),
                    "protocol_version": IPC_PROTOCOL_VERSION,
                    "provider": self.provider,
                    "messenger_account_id": self.messenger_account_id,
                    "runtime_boundary": "child_process",
                }
            )
        if request.method == "worker.health":
            if self.runtime is None:
                self._require_fields(request.payload, frozenset())
            else:
                self._require_runtime_fields(request.payload, frozenset())
            return ProviderWorkerDispatchResult(
                {
                    "status": "ready" if self.runtime is not None else "bootstrap_ready",
                    "worker_pid": os.getpid(),
                    "core_opened": self._core_opened,
                    "worker_instance_id": self.worker_instance_id,
                    "worker_generation": self.worker_generation,
                }
            )
        if request.method == "worker.heartbeat":
            self._require_runtime_fields(request.payload, frozenset())
            return ProviderWorkerDispatchResult(
                {
                    "status": "ready",
                    "worker_pid": os.getpid(),
                    "worker_instance_id": self.worker_instance_id,
                    "worker_generation": self.worker_generation,
                }
            )
        if request.method == "eitaa.runtime.start":
            self._require_fields(
                request.payload,
                frozenset(
                    {"runtime_record", "worker_instance_id", "worker_generation"}
                ),
            )
            if self.runtime is not None:
                raise WorkerIpcError(
                    "The Eitaa process runtime is already started.",
                    code="eitaa_process_runtime_already_started",
                )
            record = self._runtime_record(request.payload.get("runtime_record"))
            worker_instance_id = _canonical_uuid4(
                request.payload.get("worker_instance_id"),
                field="worker_instance_id",
            )
            worker_generation = request.payload.get("worker_generation")
            if (
                isinstance(worker_generation, bool)
                or not isinstance(worker_generation, int)
                or worker_generation <= 0
            ):
                raise WorkerIpcError(
                    "The Eitaa worker generation is invalid.",
                    code="eitaa_process_identity_invalid",
                )
            runtime = EitaaAccountRuntime.account_process(self.config, record)
            self.runtime = runtime
            self._provider_operations = EitaaProviderRuntimeOperations(
                runtime,
                self.config,
            )
            self._auth_operations = EitaaAuthChildOperations(
                runtime,
                self.config,
            )
            self.worker_instance_id = worker_instance_id
            self.worker_generation = worker_generation
            return ProviderWorkerDispatchResult(
                {
                    "status": "ready",
                    "worker_pid": os.getpid(),
                    "worker_instance_id": worker_instance_id,
                    "worker_generation": worker_generation,
                    "runtime": runtime.safe_summary(),
                    "core_opened": self._core_opened,
                    "core_owner_pid": os.getpid(),
                    "core_open_deferred": True,
                }
            )
        if request.method == "eitaa.runtime.describe":
            self._require_runtime_fields(request.payload, frozenset())
            runtime = self._require_runtime()
            return ProviderWorkerDispatchResult(
                {
                    "status": "ready",
                    "worker_pid": os.getpid(),
                    "worker_instance_id": self.worker_instance_id,
                    "worker_generation": self.worker_generation,
                    "runtime": runtime.safe_summary(),
                    "core_opened": self._core_opened,
                }
            )
        if request.method == "eitaa.runtime.core_probe":
            self._require_runtime_fields(request.payload, frozenset())
            runtime = self._require_runtime()
            return ProviderWorkerDispatchResult(
                {
                    "status": "ready",
                    "core_owner_pid": os.getpid(),
                    "core_opened": self._core_opened,
                    "core_open_deferred": not self._core_opened,
                    "database_file_name": runtime.ownership.core.database_file.name,
                    "session_file_name": runtime.ownership.core.session_file.name,
                    "media_directory_name": runtime.ownership.core.media_directory.name,
                }
            )
        if request.method == "eitaa.runtime.refresh_generation":
            self._require_runtime_fields(
                request.payload,
                frozenset({"session_generation"}),
            )
            generation = request.payload.get("session_generation")
            if (
                isinstance(generation, bool)
                or not isinstance(generation, int)
                or generation < 0
            ):
                raise WorkerIpcError(
                    "The Eitaa process generation is invalid.",
                    code="eitaa_process_generation_refresh_invalid",
                )
            self._require_runtime().refresh_process_session_generation(generation)
            return ProviderWorkerDispatchResult(
                {"status": "ready", "session_generation": generation}
            )
        if request.method == "eitaa.runtime.close_core":
            self._require_runtime_fields(request.payload, frozenset())
            self._require_runtime().close_shared_core()
            self._require_provider_operations().mark_core_closed()
            self._core_opened = False
            return ProviderWorkerDispatchResult(
                {"status": "ready", "core_opened": False}
            )
        if request.method.startswith("eitaa.provider."):
            return self._dispatch_provider_operation(request)
        if request.method.startswith("eitaa.auth."):
            return self._dispatch_auth_operation(request)
        if request.method == "worker.stop":
            if self.runtime is None:
                self._require_fields(request.payload, frozenset())
            else:
                self._require_runtime_fields(request.payload, frozenset())
            return ProviderWorkerDispatchResult(
                {"status": "stopped"},
                stop_requested=True,
            )
        raise WorkerIpcError(
            "The Eitaa worker IPC method is not supported.",
            code="ipc_method_not_supported",
        )

    def close(self) -> None:
        runtime = self.runtime
        self.runtime = None
        self._provider_operations = None
        self._auth_operations = None
        self.worker_instance_id = None
        self.worker_generation = None
        self._core_opened = False
        if runtime is not None:
            runtime.close()

    def _require_runtime(self) -> EitaaAccountRuntime:
        if self.runtime is None:
            raise EitaaRuntimeError(
                "The Eitaa process runtime has not started.",
                code="eitaa_process_runtime_not_started",
            )
        return self.runtime

    def _require_provider_operations(self) -> EitaaProviderRuntimeOperations:
        operations = self._provider_operations
        if operations is None:
            raise EitaaRuntimeError(
                "The Eitaa provider operation runtime has not started.",
                code="eitaa_process_runtime_not_started",
            )
        return operations

    def _require_auth_operations(self) -> EitaaAuthChildOperations:
        operations = self._auth_operations
        if operations is None:
            raise EitaaRuntimeError(
                "The Eitaa authentication runtime has not started.",
                code="eitaa_process_runtime_not_started",
            )
        return operations

    def _dispatch_auth_operation(
        self,
        request: IpcEnvelope,
    ) -> ProviderWorkerDispatchResult:
        operations = self._require_auth_operations()
        if request.method == "eitaa.auth.status":
            self._require_runtime_fields(request.payload, frozenset())
            return ProviderWorkerDispatchResult(operations.status())
        if request.method == "eitaa.auth.request_code":
            self._require_runtime_fields(
                request.payload,
                frozenset({"phone"}),
            )
            supplied = request.payload.get("phone")
            if supplied is not None and not isinstance(supplied, str):
                raise WorkerIpcError(
                    "The Eitaa login phone payload is invalid.",
                    code="ipc_payload_invalid",
                )
            return ProviderWorkerDispatchResult(
                operations.request_code(supplied_phone=supplied)
            )
        if request.method == "eitaa.auth.submit_code":
            self._require_runtime_fields(
                request.payload,
                frozenset({"challenge_id", "code"}),
            )
            challenge_id = request.payload.get("challenge_id")
            code = request.payload.get("code")
            if not isinstance(challenge_id, str) or not isinstance(code, str):
                raise WorkerIpcError(
                    "The Eitaa login code payload is invalid.",
                    code="ipc_payload_invalid",
                )
            return ProviderWorkerDispatchResult(
                operations.submit_code(challenge_id=challenge_id, code=code)
            )
        if request.method == "eitaa.auth.submit_password":
            self._require_runtime_fields(
                request.payload,
                frozenset({"challenge_id", "credential"}),
            )
            challenge_id = request.payload.get("challenge_id")
            credential = request.payload.get("credential")
            if not isinstance(challenge_id, str) or not isinstance(credential, str):
                raise WorkerIpcError(
                    "The Eitaa login password payload is invalid.",
                    code="ipc_payload_invalid",
                )
            return ProviderWorkerDispatchResult(
                operations.submit_password(
                    challenge_id=challenge_id,
                    credential=credential,
                )
            )
        if request.method == "eitaa.auth.reset_local_session":
            self._require_runtime_fields(
                request.payload,
                frozenset({"automatic_recovery"}),
            )
            automatic = request.payload.get("automatic_recovery")
            if not isinstance(automatic, bool):
                raise WorkerIpcError(
                    "The Eitaa session reset payload is invalid.",
                    code="ipc_payload_invalid",
                )
            return ProviderWorkerDispatchResult(
                operations.reset_local_session(automatic_recovery=automatic)
            )
        if request.method == "eitaa.auth.logout":
            self._require_runtime_fields(request.payload, frozenset())
            return ProviderWorkerDispatchResult(operations.logout())
        raise WorkerIpcError(
            "The Eitaa auth IPC method is not supported.",
            code="ipc_method_not_supported",
        )

    def _dispatch_provider_operation(
        self,
        request: IpcEnvelope,
    ) -> ProviderWorkerDispatchResult:
        operations = self._require_provider_operations()
        try:
            if request.method == "eitaa.provider.dialogs.query":
                self._require_runtime_fields(
                    request.payload,
                    frozenset({"site_key", "cursor", "limit"}),
                )
                payload = operations.list_dialogs(
                    site_key=str(request.payload.get("site_key") or ""),
                    cursor=request.payload.get("cursor"),
                    limit=request.payload.get("limit"),
                )
                return ProviderWorkerDispatchResult(payload)
            if request.method == "eitaa.provider.history.query":
                self._require_runtime_fields(
                    request.payload,
                    frozenset(
                        {
                            "site_key",
                            "peer_reference",
                            "peer_kind",
                            "cursor",
                            "limit",
                        }
                    ),
                )
                payload = operations.load_history(
                    site_key=str(request.payload.get("site_key") or ""),
                    peer_reference=request.payload.get("peer_reference"),
                    peer_kind=request.payload.get("peer_kind"),
                    cursor=request.payload.get("cursor"),
                    limit=request.payload.get("limit"),
                )
                return ProviderWorkerDispatchResult(payload)
            if request.method == "eitaa.provider.messages.send_text":
                self._require_runtime_fields(
                    request.payload,
                    frozenset(
                        {
                            "site_key",
                            "peer_reference",
                            "peer_kind",
                            "text",
                            "idempotency_key",
                        }
                    ),
                )
                peer_kind = str(request.payload.get("peer_kind") or "unknown")
                if peer_kind not in {
                    "private",
                    "group",
                    "channel",
                    "bot",
                    "unknown",
                }:
                    raise WorkerIpcError(
                        "The Eitaa provider peer kind is invalid.",
                        code="ipc_payload_invalid",
                    )
                payload = operations.send_text(
                    site_key=str(request.payload.get("site_key") or ""),
                    peer_reference=request.payload.get("peer_reference"),
                    text=request.payload.get("text"),
                    idempotency_key=request.payload.get("idempotency_key"),
                )
                return ProviderWorkerDispatchResult(payload)
            if request.method == "eitaa.provider.media.read":
                self._require_runtime_fields(
                    request.payload,
                    frozenset(
                        {
                            "site_key",
                            "peer_reference",
                            "message_reference",
                            "media_reference",
                            "variant",
                            "max_bytes",
                        }
                    ),
                )
                payload = operations.read_media(
                    site_key=str(request.payload.get("site_key") or ""),
                    peer_reference=request.payload.get("peer_reference"),
                    message_reference=request.payload.get("message_reference"),
                    media_reference=request.payload.get("media_reference"),
                    variant=request.payload.get("variant"),
                    max_bytes=request.payload.get("max_bytes"),
                )
                return ProviderWorkerDispatchResult(payload)
            if request.method == "eitaa.provider.media.read_chunk":
                self._require_runtime_fields(
                    request.payload,
                    frozenset({"cache_reference", "offset", "max_bytes"}),
                )
                payload, data = operations.read_media_chunk(
                    cache_reference=request.payload.get("cache_reference"),
                    offset=request.payload.get("offset"),
                    max_bytes=request.payload.get("max_bytes"),
                )
                return ProviderWorkerDispatchResult(
                    {**payload, "data_base64": base64.b64encode(data).decode("ascii")}
                )
            if request.method == "eitaa.provider.contacts.query":
                self._require_runtime_fields(
                    request.payload,
                    frozenset({"site_key", "cursor", "limit"}),
                )
                payload = operations.list_contacts(
                    site_key=str(request.payload.get("site_key") or ""),
                    cursor=request.payload.get("cursor"),
                    limit=request.payload.get("limit"),
                )
                return ProviderWorkerDispatchResult(payload)
            if request.method == "eitaa.provider.contacts.upsert":
                self._require_runtime_fields(
                    request.payload,
                    frozenset(
                        {
                            "site_key",
                            "identity",
                            "display_name",
                            "idempotency_key",
                        }
                    ),
                )
                payload = operations.upsert_contact(
                    site_key=str(request.payload.get("site_key") or ""),
                    identity=request.payload.get("identity"),
                    display_name=request.payload.get("display_name"),
                    idempotency_key=request.payload.get("idempotency_key"),
                )
                return ProviderWorkerDispatchResult(payload)
            raise WorkerIpcError(
                "The Eitaa provider operation is not supported.",
                code="ipc_method_not_supported",
            )
        finally:
            self._core_opened = operations.core_opened

    def _runtime_record(self, value: object) -> MessengerAccountRuntimeRecord:
        if not isinstance(value, Mapping) or set(value) != _RUNTIME_RECORD_FIELDS:
            raise WorkerIpcError(
                "The Eitaa runtime record payload is invalid.",
                code="ipc_payload_invalid",
            )
        account_id = _canonical_uuid4(
            value.get("messenger_account_id"),
            field="messenger_account_id",
        )
        phone_account_id = _canonical_uuid4(
            value.get("phone_account_id"),
            field="phone_account_id",
        )
        session_generation = value.get("session_generation")
        storage_revision = value.get("storage_revision")
        if (
            account_id != self.messenger_account_id
            or value.get("provider") != "eitaa"
            or value.get("lifecycle_state") != "active"
            or value.get("desired_worker_state") != "running"
            or not isinstance(value.get("auth_state"), str)
            or isinstance(session_generation, bool)
            or not isinstance(session_generation, int)
            or session_generation < 0
            or isinstance(storage_revision, bool)
            or storage_revision != 1
        ):
            raise WorkerIpcError(
                "The Eitaa runtime record is not runnable.",
                code="eitaa_process_runtime_record_invalid",
            )
        return MessengerAccountRuntimeRecord(
            messenger_account_id=account_id,
            phone_account_id=phone_account_id,
            provider="eitaa",
            lifecycle_state="active",
            desired_worker_state="running",
            auth_state=str(value["auth_state"]),
            session_generation=session_generation,
            storage_revision=storage_revision,
        )

    def _require_runtime_fields(
        self,
        payload: Mapping[str, object],
        expected: frozenset[str],
    ) -> None:
        self._require_runtime()
        control_fields = frozenset({"worker_instance_id", "worker_generation"})
        self._require_fields(payload, expected | control_fields)
        if (
            payload.get("worker_instance_id") != self.worker_instance_id
            or payload.get("worker_generation") != self.worker_generation
        ):
            raise WorkerIpcError(
                "The Eitaa worker request fence does not match this generation.",
                code="eitaa_process_fence_mismatch",
            )

    @staticmethod
    def _require_fields(
        payload: Mapping[str, object],
        expected: frozenset[str],
    ) -> None:
        if set(payload) != expected:
            raise WorkerIpcError(
                "The Eitaa worker request payload is invalid.",
                code="ipc_payload_invalid",
            )
