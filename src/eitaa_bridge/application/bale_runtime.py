"""Account runtime and bounded parent-side proxy for Bale personal accounts."""



from __future__ import annotations



import asyncio

import base64

from dataclasses import dataclass

import os

from pathlib import Path

import threading

import time

from typing import Callable

from typing import Any, Mapping

from uuid import uuid4



from ..config import BridgeConfig

from ..errors import ProviderExtensionError

from ..infrastructure.coordinator import CoordinatorDatabase, MessengerAccountRuntimeRecord, WorkerInstanceRecord

from ..infrastructure.diagnostics import RuntimeLogger

from ..infrastructure.worker_ipc import IpcEnvelope

from ..providers.contracts import ProviderAccountContext, SensitiveProviderValue

from .bale_provider_worker import BaleProviderProcessWorker

from .process_runtime import EitaaProcessWorkerClient





@dataclass(frozen=True, slots=True)

class BaleWorkerOwnership:

    messenger_account_id: str

    account_runtime_directory: Path



    @classmethod

    def for_account(cls, config: BridgeConfig, account_id: str) -> "BaleWorkerOwnership":

        return cls(account_id, config.source_file.parent / "runtime" / "providers" / "bale" / account_id)





class BaleAccountRuntime:

    """The coordinator's worker instance is the fence for both ownership modes."""



    def __init__(

        self, config: BridgeConfig, record: MessengerAccountRuntimeRecord,

        worker: WorkerInstanceRecord, coordinator: CoordinatorDatabase,

        logger: RuntimeLogger, *, client: EitaaProcessWorkerClient | None = None,

        failure_callback: Callable[..., None] | None = None,

    ) -> None:

        if record.provider != "bale" or worker.messenger_account_id != record.messenger_account_id:

            raise ProviderExtensionError("Bale runtime account mismatch.", code="provider_extension_scope_invalid")

        self.config = config

        self.runtime_record = record

        self.worker = worker

        self.client = client

        self._coordinator = coordinator

        self._logger = logger

        self._failure_callback = failure_callback

        self._auth_lock = threading.RLock()

        self._request_lock = threading.RLock()

        self._closed = False

        self._heartbeat_stop = threading.Event()

        self._heartbeat_thread: threading.Thread | None = None

        self._local_worker = None if client is not None else BaleProviderProcessWorker(

            record.messenger_account_id, config.source_file,

        )

        result = self.request("bale.runtime.start", {

            "runtime_record": record.safe_summary(),

            "worker_instance_id": worker.worker_instance_id,

            "worker_generation": worker.generation,

        }, started=False)

        if result.get("status") != "ready" or result.get("worker_instance_id") != worker.worker_instance_id or result.get("worker_generation") != worker.generation:

            self.close()

            raise ProviderExtensionError("Invalid Bale worker handshake.", code="bale_worker_handshake_invalid")

        if client is not None:

            client.bind_fence(worker.worker_instance_id, worker.generation)

            client._session_generation = record.session_generation



    @property

    def process_id(self) -> int:

        return self.client.process_id if self.client is not None else os.getpid()



    def request(

        self, method: str, payload: Mapping[str, object] | None = None,

        *, timeout_seconds: float = 30.0, started: bool = True,

    ) -> dict[str, object]:

        if self._closed:

            raise ProviderExtensionError("Bale runtime is closed.", code="bale_runtime_closed")

        selected = dict(payload or {})

        if started:

            selected.update({

                "worker_instance_id": self.worker.worker_instance_id,

                "worker_generation": self.worker.generation,

                "session_generation": self.runtime_record.session_generation,

            })

        if self.client is not None:

            return self.client.request(method, selected, timeout_seconds=timeout_seconds)

        assert self._local_worker is not None

        envelope = IpcEnvelope(

            "request", str(uuid4()), self.runtime_record.messenger_account_id,

            "bale", method, int(time.time() * 1000 + timeout_seconds * 1000),

            uuid4().hex, selected, "local", "",

        )

        with self._request_lock:

            return dict(self._local_worker.dispatch(envelope).payload)



    def start_supervisor(self, *, heartbeat_seconds: float | None = None) -> None:

        if self._heartbeat_thread is not None:

            return



        policy = self.config.features.worker_process

        interval = heartbeat_seconds or policy.heartbeat_interval_seconds



        def heartbeat() -> None:

            failures = 0

            while not self._heartbeat_stop.wait(interval):

                if self.client is not None and self.client.process.poll() is not None:

                    if self._failure_callback is not None:

                        self._failure_callback(self, "worker_process_exited", self.client.process.poll())

                    break

                try:

                    if self.client is not None:

                        # A busy request owns the control channel; its own bounded

                        # deadline is responsible for timing it out.

                        if not self.client._request_lock.acquire(blocking=False):

                            continue

                        try:

                            self.request("worker.heartbeat", timeout_seconds=policy.heartbeat_timeout_seconds)

                        finally:

                            self.client._request_lock.release()

                    self._coordinator.heartbeat_worker(self.worker.worker_instance_id)

                    failures = 0

                except Exception as exc:

                    failures += 1

                    if failures >= policy.heartbeat_failure_threshold and self._failure_callback is not None:

                        self._failure_callback(self, "worker_heartbeat_failed", None)

                        break



        self._heartbeat_thread = threading.Thread(target=heartbeat, name=f"bale-worker-{self.runtime_record.messenger_account_id[:8]}", daemon=True)

        self._heartbeat_thread.start()



    def safe_summary(self) -> dict[str, object]:

        return {

            "provider": "bale", "messenger_account_id": self.runtime_record.messenger_account_id,

            "runtime_boundary": "child_process" if self.client is not None else "in_process",

            "closed": self._closed,

        }



    def close(self) -> None:

        if self._closed:

            return

        self._closed = True

        self._heartbeat_stop.set()

        if self._heartbeat_thread is not None and self._heartbeat_thread is not threading.current_thread():

            self._heartbeat_thread.join(timeout=2)

        if self.client is not None:

            self.client.close()

        elif self._local_worker is not None:

            self._local_worker.close()



    def fence(self, *, reason_code: str) -> None:

        self._closed = True

        self._heartbeat_stop.set()

        if self.client is not None:

            self.client.terminate()

        elif self._local_worker is not None:

            self._local_worker.close()





class BaleRuntimeBackend:

    """Facade-shaped async proxy; secrets and wire objects stay in the owner."""



    def __init__(self, runtime: BaleAccountRuntime) -> None:

        self.runtime = runtime

        self.deadline_unix_ms: int | None = None



    async def _request(self, method: str, payload: Mapping[str, object], timeout: float = 30) -> dict[str, object]:

        if self.deadline_unix_ms is not None:

            remaining = (self.deadline_unix_ms - time.time() * 1000) / 1000

            if remaining <= 0:

                raise ProviderExtensionError("Deadline expired.", code="provider_operation_deadline_expired")

            timeout = min(timeout, remaining)

        return await asyncio.to_thread(self.runtime.request, method, payload, timeout_seconds=timeout)



    async def auth_start(self, phone: str) -> dict[str, Any]:

        result = await self._request("bale.auth.start", {"phone": phone})

        return {"transaction_hash": result["challenge_id"]}



    async def auth_code(self, challenge_id: str, code: str) -> dict[str, Any]:

        result = await self._request("bale.auth.code", {"challenge_id": challenge_id, "code": code})

        return {"authenticated": result.get("step") == "completed", "next": result.get("step")}



    async def auth_password(self, challenge_id: str, password: str) -> dict[str, Any]:

        result = await self._request("bale.auth.password", {"challenge_id": challenge_id, "credential": password})

        return {"authenticated": result.get("step") == "completed"}



    async def connect(self, *, subscribe: bool = False) -> dict[str, Any]:

        return {"connected": (await self._request("bale.auth.restore", {})).get("authenticated") is True}



    async def list_contacts(self) -> list[dict[str, Any]]:

        return list((await self._request("bale.provider.contacts.query", {}, 90))["contacts"])



    async def search_contacts(self, query: str) -> list[dict[str, Any]]:

        return list((await self._request("bale.provider.contacts.search", {"query": query}, 90))["contacts"])



    async def add_contact_by_phone(self, phone: str, name: str) -> dict[str, Any]:

        return await self._request("bale.provider.contacts.add_phone", {"phone": phone, "display_name": name}, 90)



    async def add_contact(self, user_id: int) -> dict[str, Any]:

        return await self._request("bale.provider.contacts.add_id", {"user_id": user_id}, 90)



    async def remove_contact(self, user_id: int) -> dict[str, Any]:

        return await self._request("bale.provider.contacts.remove", {"user_id": user_id}, 90)



    async def list_dialogs(self, *, limit: int, offset_date: int | None = None) -> list[dict[str, Any]]:

        return list((await self._request("bale.provider.dialogs.query", {"limit": limit, "offset_date": offset_date}, 90))["dialogs"])



    async def read_history(self, user_id: int, *, limit: int, offset_date: int | None = None) -> list[dict[str, Any]]:

        return list((await self._request("bale.provider.history.query", {"user_id": user_id, "limit": limit, "offset_date": offset_date}, 90))["messages"])



    async def send_text(self, user_id: int, text: str) -> dict[str, Any]:

        return await self._request("bale.provider.messages.send_text", {"user_id": user_id, "text": text}, 30)



    async def send_file_bytes(self, user_id: int, filename: str, data: bytes, *, caption: str = "") -> dict[str, Any]:

        return await self._request("bale.provider.messages.send_media", {"user_id": user_id,

            "filename": filename, "data_base64": base64.b64encode(data).decode("ascii"), "caption": caption}, 90)



    async def read_media(self, user_id: int, message_id: int, *, max_bytes: int) -> dict[str, Any]:

        return await self._request("bale.provider.media.read", {"user_id": user_id,

            "message_id": message_id, "max_bytes": max_bytes}, 90)



    async def close(self) -> None:

        # The registry owns the runtime; one request's adapter must not close it.

        return None





class BaleVaultSessionStore:

    """Opaque reference to an encrypted account vault, never its passphrase."""



    def __init__(self, runtime: BaleAccountRuntime) -> None:

        self.runtime = runtime



    def _require_scope(self, context: ProviderAccountContext) -> None:

        record = self.runtime.runtime_record

        if context.provider != "bale" or context.messenger_account_id != record.messenger_account_id or context.session_generation != record.session_generation:

            raise ProviderExtensionError("Bale session scope changed.", code="provider_extension_scope_invalid")



    def load(self, context: ProviderAccountContext) -> SensitiveProviderValue | None:

        self._require_scope(context)

        status = self.runtime.request("bale.auth.status", {})

        return SensitiveProviderValue.from_text("bale:vault:v1") if status.get("has_vault") is True else None



    def save(self, context: ProviderAccountContext, value: SensitiveProviderValue) -> None:

        self._require_scope(context)

        if value.reveal_bytes() != b"bale:vault:v1" or self.load(context) is None:

            raise ProviderExtensionError("Bale vault is not persisted.", code="bale_vault_missing")



    def archive(self, context: ProviderAccountContext, *, reason_code: str) -> None:

        self._require_scope(context)

        if not reason_code or len(reason_code) > 64:

            raise ProviderExtensionError("Invalid Bale archive reason.", code="provider_session_archive_reason_invalid")

        self.runtime.request("bale.auth.logout", {})
