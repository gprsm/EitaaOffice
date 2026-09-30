"""Dedicated worker process / adapter for one Bale MessengerAccount runtime."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
import time
from typing import Any, Mapping
import uuid

from ..errors import WorkerIpcError
from ..infrastructure.worker_ipc import IPC_PROTOCOL_VERSION, IpcEnvelope
from .bale_client.api import BaleApi, BaleApiError
from .provider_adapter import ProviderWorkerDispatchResult


def _canonical_uuid4(value: object, *, field: str) -> str:
    try:
        parsed = uuid.UUID(str(value))
    except (ValueError, AttributeError) as exc:
        raise WorkerIpcError(
            "The Bale worker identity is invalid.",
            safe_context={"field": field},
            code="bale_process_identity_invalid",
        ) from exc
    if parsed.version != 4 or str(parsed) != str(value):
        raise WorkerIpcError(
            "The Bale worker identity is invalid.",
            safe_context={"field": field},
            code="bale_process_identity_invalid",
        )
    return str(parsed)


class BaleProviderProcessWorker:
    """Isolate mutable Bale account runtime and networking inside an account worker."""

    provider = "bale"

    def __init__(
        self,
        messenger_account_id: str,
        config_file: str | Path | None = None,
        *,
        base_dir: Path | None = None,
        api: BaleApi | None = None,
    ) -> None:
        self.messenger_account_id = _canonical_uuid4(
            messenger_account_id,
            field="messenger_account_id",
        )
        self.config_file = config_file
        self.started_monotonic = time.monotonic()
        self.request_count = 0
        self._base_dir = base_dir or (Path("data") / "coordinator" / "accounts" / self.messenger_account_id)
        self._api = api

    def _ensure_api(self) -> BaleApi:
        if self._api is not None:
            return self._api
        self._base_dir.mkdir(parents=True, exist_ok=True)
        self._api = BaleApi.create(base_dir=self._base_dir)
        return self._api

    def dispatch(self, request: IpcEnvelope) -> ProviderWorkerDispatchResult:
        if (
            request.provider != self.provider
            or request.messenger_account_id != self.messenger_account_id
        ):
            raise WorkerIpcError(
                "The Bale worker request scope is invalid.",
                code="ipc_worker_scope_mismatch",
            )
        self.request_count += 1
        method = request.method
        payload = request.payload

        if method == "worker.hello":
            return ProviderWorkerDispatchResult(
                {
                    "status": "ready",
                    "worker_pid": os.getpid(),
                    "protocol_version": IPC_PROTOCOL_VERSION,
                    "provider": self.provider,
                    "messenger_account_id": self.messenger_account_id,
                    "capabilities": [
                        "worker.health",
                        "bale.auth_start",
                        "bale.auth_code",
                        "bale.auth_password",
                        "bale.account_card",
                        "bale.list_dialogs",
                        "bale.read_history",
                        "bale.send_text",
                        "bale.list_contacts",
                        "bale.add_contact_by_phone",
                        "worker.stop",
                    ],
                }
            )

        if method == "worker.health":
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

        if method == "worker.stop":
            self.close()
            return ProviderWorkerDispatchResult(
                {"status": "stopped"},
                stop_requested=True,
            )

        # Operational methods
        try:
            api = self._ensure_api()
            result_payload = self._run_async(self._dispatch_operation(api, method, payload))
            return ProviderWorkerDispatchResult(result_payload)
        except BaleApiError as exc:
            raise WorkerIpcError(
                f"Bale worker operation failed: {exc}",
                safe_context={"code": exc.code},
                code=exc.code or "bale_worker_operation_failed",
            ) from exc

    async def _dispatch_operation(
        self, api: BaleApi, method: str, payload: Mapping[str, Any]
    ) -> dict[str, Any]:
        if method == "bale.auth_start":
            phone = str(payload.get("phone") or "")
            res = await api.auth_start(phone)
            return {"ok": True, "result": res}

        if method == "bale.auth_code":
            tx = str(payload.get("transaction_hash") or "")
            code = str(payload.get("code") or "")
            res = await api.auth_code(tx, code)
            return {"ok": True, "result": res}

        if method == "bale.auth_password":
            tx = str(payload.get("transaction_hash") or "")
            password = str(payload.get("password") or "")
            res = await api.auth_password(tx, password)
            return {"ok": True, "result": res}

        if method == "bale.account_card":
            res = await api.account_card()
            return {"ok": True, "result": res}

        if method == "bale.list_dialogs":
            limit = int(payload.get("limit") or 50)
            res = await api.list_dialogs(limit=limit)
            return {"ok": True, "result": res}

        if method == "bale.read_history":
            user_id = int(payload.get("user_id") or 0)
            limit = int(payload.get("limit") or 30)
            res = await api.read_history(user_id=user_id, limit=limit)
            return {"ok": True, "result": res}

        if method == "bale.send_text":
            user_id = int(payload.get("user_id") or 0)
            text = str(payload.get("text") or "")
            res = await api.send_text(user_id=user_id, text=text)
            return {"ok": True, "result": res}

        if method == "bale.list_contacts":
            res = await api.list_contacts()
            return {"ok": True, "result": res}

        if method == "bale.add_contact_by_phone":
            phone = str(payload.get("phone") or "")
            name = str(payload.get("name") or "")
            res = await api.add_contact_by_phone(phone, name)
            return {"ok": True, "result": res}

        raise WorkerIpcError(
            f"Unsupported Bale worker method: {method}",
            code="ipc_method_not_supported",
        )

    def _run_async(self, coro: Any) -> Any:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            new_loop = asyncio.new_event_loop()
            try:
                return new_loop.run_until_complete(coro)
            finally:
                new_loop.close()
        else:
            return asyncio.run(coro)

    def close(self) -> None:
        if self._api is not None and hasattr(self._api, "close"):
            try:
                self._run_async(self._api.close())
            except Exception:
                pass
            self._api = None
