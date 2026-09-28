"""Offline regression for Bale's product boundary; no provider network access."""

from __future__ import annotations

import asyncio
import time
from uuid import uuid4

import pytest

from eitaa_bridge.application.bale_provider_adapter import BaleProviderApplicationAdapter
from eitaa_bridge.application.bale_account_owner import BaleAccountOwner
from eitaa_bridge.application.bale_provider_worker import BaleProviderProcessWorker
from eitaa_bridge.errors import ProviderExtensionError
from eitaa_bridge.application.m2m_api import _DIALOG_REFERENCE
from eitaa_bridge.providers.bale import bale_extension_registration
from eitaa_bridge.providers.contracts import (
    ProviderAccountContext,
    ProviderContactUpsertRequest,
    ProviderOperationContext,
    ProviderPeerReference,
    ProviderSendTextRequest,
    SensitiveProviderValue,
)
from eitaa_bridge.providers.testing import InMemoryProviderSessionStore
from eitaa_bridge.infrastructure.worker_ipc import IpcEnvelope


def _adapter(backend):
    account = ProviderAccountContext(str(uuid4()), str(uuid4()), "bale", 1, 1)
    adapter = BaleProviderApplicationAdapter(
        account, InMemoryProviderSessionStore(),
        bale_extension_registration().manifest, backend_factory=lambda: backend,
    )
    operation = ProviderOperationContext(account, "a" * 32, int(time.time() * 1000) + 30000)
    return adapter, operation


class _Backend:
    def __init__(self):
        self.sent = []
        self.imported = []
        self.added = []

    async def list_contacts(self):
        return [{"peer": {"id": 42, "type": 1}, "name": "Example", "access_hash": 99}]

    async def add_contact_by_phone(self, phone, name):
        self.imported.append((phone, name))
        return {"matched": True, "users": [{"id": 42, "access_hash": 99}]}

    async def add_contact(self, user_id):
        self.added.append(user_id)
        return {"added": True}

    async def send_text(self, peer_id, text):
        self.sent.append((peer_id, text))
        return {"random_id": 17, "sent": True}


def test_contact_protocol_lists_safe_references_and_imports_with_name():
    async def exercise():
        backend = _Backend()
        adapter, operation = _adapter(backend)
        page = await adapter.list_contacts(operation, cursor=None, limit=20)
        assert page.contacts[0].contact_reference == "bale:user:42"
        assert "99" not in repr(page)
        receipt = await adapter.upsert_contact(
            operation, ProviderContactUpsertRequest(
                SensitiveProviderValue.from_text("+10000000000"),
                "Example", "bale-import-00000001",
            ),
        )
        assert receipt.contact_reference == "bale:user:42"
        assert len(backend.imported) == 1
        assert backend.imported[0][1] == "Example"

    asyncio.run(exercise())


def test_peer_reference_keeps_type_for_colliding_numeric_ids():
    async def exercise():
        backend = _Backend()
        adapter, operation = _adapter(backend)
        request = ProviderSendTextRequest(
            ProviderPeerReference("bale:group:42", "group"), "fixture", "bale-send-00000001",
        )
        try:
            await adapter.send_text(operation, request)
        except Exception as exc:
            assert getattr(exc, "code", None) == "provider_peer_kind_unsupported"
        else:
            raise AssertionError("A group must not be sent as a private user")
        assert backend.sent == []

    asyncio.run(exercise())


def test_existing_id_only_contact_is_not_overwritten():
    async def exercise():
        backend = _Backend()
        adapter, operation = _adapter(backend)
        receipt = await adapter.upsert_contact(
            operation, ProviderContactUpsertRequest(
                SensitiveProviderValue.from_text("bale:user:42"),
                "Replacement", "bale-import-00000002",
            ),
        )
        assert receipt.created is False
        assert backend.added == []
        assert backend.imported == []

    asyncio.run(exercise())


def test_m2m_parser_accepts_typed_bale_reference():
    assert _DIALOG_REFERENCE.fullmatch("bale:user:42") is not None
    assert _DIALOG_REFERENCE.fullmatch("bale:group:42") is not None
    assert _DIALOG_REFERENCE.fullmatch("bale:peer:42") is None


def test_unowned_default_bale_vault_is_never_constructed():
    account = ProviderAccountContext(str(uuid4()), str(uuid4()), "bale", 1, 1)
    adapter = BaleProviderApplicationAdapter(
        account, InMemoryProviderSessionStore(), bale_extension_registration().manifest,
    )
    with pytest.raises(ProviderExtensionError) as failure:
        adapter._get_backend()
    assert failure.value.code == "provider_account_runtime_unavailable"


def test_two_account_owners_keep_vault_paths_secrets_and_loops_separate(tmp_path):
    constructed = []

    class OwnedBackend:
        def __init__(self, **options):
            self.options = options
            self.loop = asyncio.get_running_loop()
            self.invocations = 0
            constructed.append(self)

        async def list_contacts(self):
            assert asyncio.get_running_loop() is self.loop
            self.invocations += 1
            return []

        async def close(self):
            assert asyncio.get_running_loop() is self.loop

    first = BaleAccountOwner(tmp_path, str(uuid4()), backend_factory=OwnedBackend)
    second = BaleAccountOwner(tmp_path, str(uuid4()), backend_factory=OwnedBackend)
    try:
        asyncio.run(first.list_contacts())
        asyncio.run(second.list_contacts())
        asyncio.run(first.list_contacts())
        assert len(constructed) == 2
        assert constructed[0].loop is not constructed[1].loop
        assert constructed[0].invocations == 2
        assert constructed[1].invocations == 1
        assert constructed[0].options["vault_path"] != constructed[1].options["vault_path"]
        assert constructed[0].options["passphrase"] != constructed[1].options["passphrase"]
        keys = list(tmp_path.rglob("vault.key*"))
        assert len(keys) == 2
        assert all(path.is_file() for path in keys)
    finally:
        asyncio.run(first.close())
        asyncio.run(second.close())


def test_account_owner_restart_reuses_only_its_own_secret_without_provider_traffic(tmp_path):
    account_id = str(uuid4())
    created = []

    class OfflineBackend:
        def __init__(self, **options):
            created.append(options)

        async def list_contacts(self):
            return []

        async def close(self):
            pass

    first = BaleAccountOwner(tmp_path, account_id, backend_factory=OfflineBackend)
    assert created == []
    asyncio.run(first.list_contacts())
    asyncio.run(first.close())
    restarted = BaleAccountOwner(tmp_path, account_id, backend_factory=OfflineBackend)
    try:
        assert len(created) == 1
        asyncio.run(restarted.list_contacts())
        assert len(created) == 2
        assert created[0]["passphrase"] == created[1]["passphrase"]
        assert created[0]["vault_path"] == created[1]["vault_path"]
    finally:
        asyncio.run(restarted.close())


def test_bale_client_log_handlers_are_account_scoped(tmp_path):
    from eitaa_bridge.application.bale_client.client import BaleClient
    from eitaa_bridge.application.bale_client.config import BaleConfig

    clients = []
    for account in ("account-a", "account-b"):
        config = BaleConfig()
        config.vault_path = tmp_path / account / "session.vault"
        config.log_path = tmp_path / account / "client.log"
        clients.append(BaleClient(config))
    try:
        assert clients[0].log is not clients[1].log
        assert clients[0].log.propagate is False
        assert clients[1].log.propagate is False
        assert clients[0].log.handlers[0].baseFilename != clients[1].log.handlers[0].baseFilename
    finally:
        for client in clients:
            asyncio.run(client.close())


def test_bale_worker_requires_start_and_generation_and_keeps_challenge_private(tmp_path):
    account_id, instance_id = str(uuid4()), str(uuid4())
    calls = []

    class OfflineOwner:
        def __init__(self, base, account):
            calls.append(("construct", account))

        async def auth_start(self, phone):
            calls.append(("challenge", "account"))
            return {"transaction_hash": "synthetic-private-transaction"}

        async def auth_code(self, transaction, code):
            assert transaction == "synthetic-private-transaction"
            calls.append(("code", "account"))
            return {"authenticated": True, "user_id": 42}

        async def close(self):
            calls.append(("close", "account"))

    worker = BaleProviderProcessWorker(
        account_id, tmp_path / "bridge.json", owner_factory=OfflineOwner,
    )

    def envelope(method, payload, *, selected_account=account_id):
        return IpcEnvelope(
            "request", str(uuid4()), selected_account, "bale", method,
            int(time.time() * 1000) + 30000, uuid4().hex, payload,
            "synthetic", "0" * 64,
        )

    assert worker.dispatch(envelope("worker.hello", {})).payload["status"] == "bootstrap_ready"
    assert calls == []
    with pytest.raises(Exception) as not_started:
        worker.dispatch(envelope("bale.auth.start", {"phone": "+10000000000", "worker_instance_id": instance_id, "worker_generation": 1, "session_generation": 1}))
    assert getattr(not_started.value, "code", None) == "bale_worker_fence_mismatch"
    worker.dispatch(envelope("bale.runtime.start", {
        "runtime_record": {
            "provider": "bale", "messenger_account_id": account_id,
            "lifecycle_state": "active", "desired_worker_state": "running",
            "storage_revision": 1, "session_generation": 1,
        }, "worker_instance_id": instance_id, "worker_generation": 1,
    }))
    assert calls == [("construct", account_id)]
    start = worker.dispatch(envelope("bale.auth.start", {
        "phone": "+10000000000", "worker_instance_id": instance_id, "worker_generation": 1, "session_generation": 1,
    })).payload
    assert "transaction_hash" not in start
    assert "phone" not in start
    with pytest.raises(Exception) as stale:
        worker.dispatch(envelope("bale.auth.code", {
            "challenge_id": start["challenge_id"], "code": "000000",
            "worker_instance_id": instance_id, "worker_generation": 2, "session_generation": 1,
        }))
    assert getattr(stale.value, "code", None) == "bale_worker_fence_mismatch"
    completed = worker.dispatch(envelope("bale.auth.code", {
        "challenge_id": start["challenge_id"], "code": "000000",
        "worker_instance_id": instance_id, "worker_generation": 1, "session_generation": 1,
    })).payload
    assert completed == {"step": "completed"}
    with pytest.raises(Exception) as replay:
        worker.dispatch(envelope("bale.auth.code", {
            "challenge_id": start["challenge_id"], "code": "000000",
            "worker_instance_id": instance_id, "worker_generation": 1, "session_generation": 1,
        }))
    assert getattr(replay.value, "code", None) == "bale_challenge_invalid"
    with pytest.raises(Exception) as scope:
        worker.dispatch(envelope("worker.heartbeat", {
            "worker_instance_id": instance_id, "worker_generation": 1, "session_generation": 1,
        }, selected_account=str(uuid4())))
    assert getattr(scope.value, "code", None) == "ipc_worker_scope_mismatch"
    worker.close()
