"""Provider-neutral fake worker used to prove the Phase 7 IPC boundary."""

from __future__ import annotations

import os
import time
from typing import Mapping

from ..errors import WorkerIpcError
from ..infrastructure.worker_ipc import IPC_PROTOCOL_VERSION, IpcEnvelope
from .provider_adapter import ProviderWorkerDispatchResult


class FakeProviderWorker:
    """A deterministic worker with no provider session, network, or user data."""

    provider = "fake"

    def __init__(self, messenger_account_id: str) -> None:
        self.messenger_account_id = messenger_account_id
        self.started_monotonic = time.monotonic()
        self.request_count = 0

    def dispatch(self, request: IpcEnvelope) -> ProviderWorkerDispatchResult:
        if (
            request.provider != self.provider
            or request.messenger_account_id != self.messenger_account_id
        ):
            raise WorkerIpcError(
                "The fake worker request scope is invalid.",
                code="ipc_worker_scope_mismatch",
            )
        self.request_count += 1
        if request.method == "worker.hello":
            self._require_fields(request.payload, frozenset())
            return ProviderWorkerDispatchResult(
                {
                    "status": "ready",
                    "worker_pid": os.getpid(),
                    "protocol_version": IPC_PROTOCOL_VERSION,
                    "provider": self.provider,
                    "messenger_account_id": self.messenger_account_id,
                    "capabilities": [
                        "worker.health",
                        "fake.echo_opaque",
                        "worker.stop",
                    ],
                }
            )
        if request.method == "worker.health":
            self._require_fields(request.payload, frozenset())
            return ProviderWorkerDispatchResult(
                {
                    "status": "ready",
                    "request_count": self.request_count,
                    "uptime_ms": max(
                        0,
                        int((time.monotonic() - self.started_monotonic) * 1000),
                    ),
                }
            )
        if request.method == "fake.echo_opaque":
            self._require_fields(request.payload, frozenset({"opaque_reference"}))
            opaque_reference = request.payload.get("opaque_reference")
            if (
                not isinstance(opaque_reference, str)
                or not 1 <= len(opaque_reference) <= 256
            ):
                raise WorkerIpcError(
                    "The fake worker opaque reference is invalid.",
                    code="ipc_fake_reference_invalid",
                )
            return ProviderWorkerDispatchResult(
                {"opaque_reference": opaque_reference}
            )
        if request.method == "worker.stop":
            self._require_fields(request.payload, frozenset())
            return ProviderWorkerDispatchResult(
                {"status": "stopped"},
                stop_requested=True,
            )
        raise WorkerIpcError(
            "The worker IPC method is not supported.",
            code="ipc_method_not_supported",
        )

    @staticmethod
    def _require_fields(
        payload: Mapping[str, object],
        expected: frozenset[str],
    ) -> None:
        if set(payload) != expected:
            raise WorkerIpcError(
                "The fake worker request payload is invalid.",
                code="ipc_payload_invalid",
            )

    def close(self) -> None:
        return None
