"""Offline regression for Bale's product boundary; no provider network access."""

from __future__ import annotations

import asyncio
import time
from uuid import uuid4

import pytest

from eitaa_bridge.application.bale_provider_adapter import BaleProviderApplicationAdapter
from eitaa_bridge.application.bale_account_owner import BaleAccountOwner
from eitaa_bridge.application.bale_provider_worker import BaleProviderProcessWorker
from eitaa_bridge.errors import ProviderExtensionError, WorkerIpcError
from eitaa_bridge.application.m2m_api import _DIALOG_REFERENCE
from eitaa_bridge.providers.contracts import ProviderSendMediaRequest, ProviderSendStatus
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
        self.sent_files = []
        self.peer_types = []
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

    async def send_text(self, peer_id, text, peer_type=1):
        self.sent.append((peer_id, text))
        self.peer_types.append(peer_type)
        return {"random_id": 17, "sent": True}

    async def send_file_bytes(self, peer_id, filename, data, *, caption=None, peer_type=1):
        self.sent_files.append((peer_id, filename, peer_type))
        return {"sent": True, "submission_reference": "bale:submission:file-42"}


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


def test_group_send_keeps_type_and_legacy_reference_stays_rejected():
    async def exercise():
        backend = _Backend()
        adapter, operation = _adapter(backend)
        # A typed group reference routes as a group chat, never as a private user.
        receipt = await adapter.send_text(
            operation, ProviderSendTextRequest(
                ProviderPeerReference("bale:group:42", "group"), "fixture", "bale-send-00000001",
            ),
        )
        assert receipt.status == ProviderSendStatus.SUCCEEDED
        assert backend.sent == [(42, "fixture")]
        assert backend.peer_types == [2]
        # A legacy untyped reference must still not be silently redirected into a group.
        try:
            await adapter.send_text(
                operation, ProviderSendTextRequest(
                    ProviderPeerReference("bale:peer:42", "group"), "fixture", "bale-send-00000002",
                ),
            )
        except Exception as exc:
            assert getattr(exc, "code", None) == "provider_peer_reference_invalid"
        else:
            raise AssertionError("A legacy peer reference must not address a group")
        # Channel send routes as a channel chat with peer_type=3 for text and media alike.
        channel_text = ProviderSendTextRequest(
            ProviderPeerReference("bale:channel:42", "channel"), "fixture channel", "bale-send-00000003",
        )
        receipt_channel = await adapter.send_text(operation, channel_text)
        assert receipt_channel.status == ProviderSendStatus.SUCCEEDED
        assert backend.sent[-1] == (42, "fixture channel")
        assert backend.peer_types[-1] == 3

        channel_media = ProviderSendMediaRequest(
            ProviderPeerReference("bale:channel:42", "channel"), "fixture.txt", b"fixture", "bale-media-00000004", "",
        )
        receipt_media = await adapter.send_media(operation, channel_media)
        assert receipt_media.status == ProviderSendStatus.SUCCEEDED
        assert backend.sent_files[-1] == (42, "fixture.txt", 3)

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


def test_dialog_name_enrichment_is_optional_cached_and_invalidated(tmp_path):
    from eitaa_bridge.application.bale_client.api import BaleApiError

    created = []

    class Backend:
        def __init__(self, **options):
            self.contacts_calls = 0
            self.fail_contacts = True
            self.title = None
            created.append(self)

        async def list_dialogs(self, **kwargs):
            return [{"peer": {"id": 42, "type": 1}, "title": self.title}]

        async def list_contacts(self):
            self.contacts_calls += 1
            if self.fail_contacts:
                raise BaleApiError("synthetic limit", code="bale_rpc_error")
            return [{"peer": {"id": 42, "type": 1}, "name": "Fixture name"}]

        async def add_contact(self, user_id):
            return {"added": True}

        async def close(self):
            pass

    owner = BaleAccountOwner(tmp_path, str(uuid4()), backend_factory=Backend)
    try:
        first = asyncio.run(owner.list_dialogs())
        assert first[0]["title"] is None
        assert created[0].contacts_calls == 1
        assert asyncio.run(owner.list_dialogs())[0]["title"] is None
        assert created[0].contacts_calls == 1  # Polling does not refetch the address book.

        created[0].fail_contacts = False
        asyncio.run(owner.add_contact(42))
        assert asyncio.run(owner.list_dialogs())[0]["title"] == "Fixture name"
        assert created[0].contacts_calls == 2
        assert asyncio.run(owner.list_dialogs())[0]["title"] == "Fixture name"
        assert created[0].contacts_calls == 2

        created[0].title = "Server title"
        assert asyncio.run(owner.list_dialogs())[0]["title"] == "Server title"
        assert created[0].contacts_calls == 2
    finally:
        asyncio.run(owner.close())


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
    with pytest.raises(Exception) as wrong_identity:
        worker.dispatch(envelope("bale.auth.code", {
            "challenge_id": str(uuid4()), "code": "000000",
            "worker_instance_id": instance_id, "worker_generation": 1, "session_generation": 1,
        }))
    assert getattr(wrong_identity.value, "code", None) == "bale_challenge_invalid"
    assert worker._challenge[0] == start["challenge_id"]
    with pytest.raises(Exception) as stale_session:
        worker.dispatch(envelope("bale.auth.code", {
            "challenge_id": start["challenge_id"], "code": "000000",
            "worker_instance_id": instance_id, "worker_generation": 1, "session_generation": 0,
        }))
    assert getattr(stale_session.value, "code", None) == "bale_worker_fence_mismatch"
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
    expiring = worker.dispatch(envelope("bale.auth.start", {
        "phone": "+10000000000", "worker_instance_id": instance_id,
        "worker_generation": 1, "session_generation": 1,
    })).payload
    worker._challenge = (expiring["challenge_id"], "code", time.monotonic() - 1, "synthetic-private-transaction")
    with pytest.raises(Exception) as expired:
        worker.dispatch(envelope("bale.auth.code", {
            "challenge_id": expiring["challenge_id"], "code": "000000",
            "worker_instance_id": instance_id, "worker_generation": 1, "session_generation": 1,
        }))
    assert getattr(expired.value, "code", None) == "bale_challenge_invalid"
    assert worker._challenge is None
    with pytest.raises(Exception) as scope:
        worker.dispatch(envelope("worker.heartbeat", {
            "worker_instance_id": instance_id, "worker_generation": 1, "session_generation": 1,
        }, selected_account=str(uuid4())))
    assert getattr(scope.value, "code", None) == "ipc_worker_scope_mismatch"
    worker.close()


@pytest.mark.parametrize("second_factor", [False, True])
def test_bale_worker_connects_saved_session_before_first_dialog_query(tmp_path, second_factor):
    account_id, instance_id = str(uuid4()), str(uuid4())

    class OfflineOwner:
        def __init__(self, base, account):
            self.saved = False
            self.connected = False

        async def auth_start(self, phone):
            return {"transaction_hash": "synthetic-private-transaction"}

        async def auth_code(self, transaction, code):
            if second_factor:
                return {"authenticated": False, "next": "password"}
            self.saved = True
            return {"authenticated": True}

        async def auth_password(self, transaction, password):
            self.saved = True
            return {"authenticated": True}

        async def has_vault(self):
            return self.saved

        async def connect(self, **kwargs):
            self.connected = self.saved
            return {"connected": self.connected}

        async def list_dialogs(self, *, limit):
            if not self.connected:
                raise WorkerIpcError("Not connected.", code="bale_not_connected")
            return []

        async def close(self):
            pass

    worker = BaleProviderProcessWorker(account_id, tmp_path / "bridge.json", owner_factory=OfflineOwner)

    def envelope(method, payload):
        return IpcEnvelope(
            "request", str(uuid4()), account_id, "bale", method,
            int(time.time() * 1000) + 30000, uuid4().hex, payload,
            "synthetic", "0" * 64,
        )

    try:
        worker.dispatch(envelope("bale.runtime.start", {
            "runtime_record": {
                "provider": "bale", "messenger_account_id": account_id,
                "lifecycle_state": "active", "desired_worker_state": "running",
                "storage_revision": 1, "session_generation": 1,
            }, "worker_instance_id": instance_id, "worker_generation": 1,
        }))
        fence = {"worker_instance_id": instance_id, "worker_generation": 1, "session_generation": 1}
        started = worker.dispatch(envelope("bale.auth.start", {"phone": "+10000000000", **fence})).payload
        code_result = worker.dispatch(envelope("bale.auth.code", {
            "challenge_id": started["challenge_id"], "code": "000000", **fence,
        })).payload
        if second_factor:
            assert code_result["step"] == "password"
            assert worker.dispatch(envelope("bale.auth.password", {
                "challenge_id": started["challenge_id"], "credential": "synthetic-password", **fence,
            })).payload == {"step": "completed"}
        else:
            assert code_result == {"step": "completed"}
        assert worker.dispatch(envelope("bale.provider.dialogs.query", {
            "limit": 20, "offset_date": None, **fence,
        })).payload == {"dialogs": []}
        assert worker.owner.connected is True
        worker.owner.connected = False
        with pytest.raises(WorkerIpcError) as disconnected:
            worker.dispatch(envelope("bale.provider.dialogs.query", {
                "limit": 20, "offset_date": None, **fence,
            }))
        assert disconnected.value.code == "bale_not_connected"
        assert worker.dispatch(envelope("bale.provider.dialogs.query", {
            "limit": 20, "offset_date": None, **fence,
        })).payload == {"dialogs": []}
        assert worker.owner.connected is True
    finally:
        worker.close()


def test_owner_deadline_cancels_on_owned_loop_and_later_requests_work(tmp_path):
    from threading import Event
    cancelled = Event()
    constructed = []
    class Backend:
        def __init__(self, **kwargs):
            self.slow = True
            constructed.append(self)
        async def list_contacts(self):
            if self.slow:
                try:
                    await asyncio.sleep(20)
                finally:
                    cancelled.set()
            return []
        async def close(self):
            pass
    owner = BaleAccountOwner(tmp_path, str(uuid4()), backend_factory=Backend)
    async def exercise():
        with pytest.raises(TimeoutError):
            await asyncio.wait_for(owner.list_contacts(), timeout=0.1)
        assert await asyncio.to_thread(cancelled.wait, 2)
        constructed[0].slow = False
        assert await asyncio.gather(owner.list_contacts(), owner.list_contacts()) == [[], []]
        assert len(constructed) == 1
        await owner.close()
    asyncio.run(exercise())


def test_exact_phone_lookup_preserves_existing_name_and_never_imports(tmp_path):
    calls = []
    class Backend:
        def __init__(self, **kwargs):
            pass
        async def list_contacts(self):
            return [{"peer": {"id": 42, "type": 1}, "name": "Original fixture name"}]
        async def lookup_contact_by_phone(self, phone):
            calls.append("lookup")
            return [{"peer": {"id": 42, "type": 1}}]
        async def add_contact_by_phone(self, phone, name):
            calls.append("import")
            raise AssertionError("Existing contact must not be overwritten")
        async def close(self):
            pass
    owner = BaleAccountOwner(tmp_path, str(uuid4()), backend_factory=Backend)
    async def exercise():
        result = await owner.add_contact_by_phone("+10000000000", "Different fixture name")
        assert result == {"matched": True, "users": [{"id": 42}], "created": False}
        assert calls == ["lookup"]
        assert not list(tmp_path.rglob("contact-bindings.json"))
        await owner.close()
    asyncio.run(exercise())


def test_download_enforces_stream_limit_when_declared_size_is_wrong(tmp_path):
    from types import SimpleNamespace
    from eitaa_bridge.application.bale_client.client import BaleClient
    from eitaa_bridge.application.bale_client.errors import ProtocolError
    class Response:
        headers = {"content-length": "1"}
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass
        def raise_for_status(self):
            pass
        async def aiter_bytes(self, size):
            assert size <= 65536
            yield b"1234"
            yield b"5678"
    class Http:
        def stream(self, *args):
            return Response()
    class Client:
        http = Http()
        async def get_file_url(self, details):
            return SimpleNamespace(url="https://fixture.invalid/media", chunk_size=10**9)
    path = tmp_path / "generated.download"
    with pytest.raises(ProtocolError):
        asyncio.run(BaleClient.download_file(Client(), SimpleNamespace(size=1), path, max_bytes=5))
    assert path.read_bytes() == b"1234"
