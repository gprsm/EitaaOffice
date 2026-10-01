"""Main application acceptance with a stateful offline provider, not source regex."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from pathlib import Path
from uuid import uuid4

import pytest

from eitaa_bridge.application.api import BridgeApplicationApi
from eitaa_bridge.application.bale_provider_worker import BaleProviderProcessWorker
from eitaa_bridge.infrastructure.coordinator import ProtectedPhone


class Protector:
    def __init__(self):
        self.identities = {}

    def protect(self, phone):
        digest = hashlib.sha256(phone.encode()).digest()
        self.identities[digest] = phone
        return ProtectedPhone(digest, 1, hmac.new(b"synthetic-account-key", phone.encode(), hashlib.sha256).hexdigest(), "+••••••••00")

    def reveal(self, protected):
        return self.identities[protected.ciphertext]


class OfflineOwner:
    states = {}

    def __init__(self, base, account):
        self.account = account
        self.state = self.states.setdefault(account, {"vault": False, "calls": [], "contacts": {42: "Fixture"}, "messages": [], "phones": {}})

    async def auth_start(self, phone):
        self.state["calls"].append("start")
        return {"transaction_hash": "synthetic-private-transaction"}

    async def auth_code(self, transaction, code):
        assert transaction == "synthetic-private-transaction"
        self.state["calls"].append("code")
        return {"authenticated": False, "next": "password"}

    async def auth_password(self, transaction, password):
        self.state["vault"] = True
        self.state["calls"].append("password")
        return {"authenticated": True}

    async def has_vault(self):
        return self.state["vault"]

    async def connect(self, **kwargs):
        self.state["calls"].append("restore")
        return {"connected": self.state["vault"]}

    async def logout(self):
        self.state["vault"] = False
        return True

    async def list_contacts(self):
        return [{"peer": {"id": key, "type": 1}, "name": value, "access_hash": "private-hash"} for key, value in self.state["contacts"].items()]

    async def search_contacts(self, query):
        return [item for item in await self.list_contacts() if query.lower() in item["name"].lower()]

    async def add_contact_by_phone(self, phone, name):
        self.state["calls"].append("import")
        self.state["contacts"][43] = name
        self.state["phones"][phone] = 43
        return {"matched": True, "users": [{"id": 43, "access_hash": "private-hash"}]}

    async def lookup_phone(self, phone):
        return self.state["phones"].get(phone)

    async def add_contact(self, user_id):
        self.state["contacts"][user_id] = "Added"
        return {"added": True}

    async def remove_contact(self, user_id):
        self.state["calls"].append("remove")
        self.state["contacts"].pop(user_id, None)
        return {"removed": True}

    async def list_dialogs(self, *, limit):
        return [{"peer": {"id": 42, "type": 1}, "title": "Fixture", "unread_count": 2, "last_text": "Preview"},
                {"peer": {"id": 42, "type": 2}, "title": "Group", "unread_count": 0}][:limit]

    async def read_history(self, user_id, *, limit):
        return list(self.state["messages"][-limit:])

    async def send_text(self, user_id, text):
        self.state["calls"].append("send")
        self.state["messages"].append({"message_id": 17, "sender_id": 1, "date": 10, "text": text})
        return {"sent": True, "random_id": 99}

    async def send_file_bytes(self, user_id, name, data, *, caption):
        self.state["calls"].append("media_send")
        return {"sent": True}

    async def read_media_bytes(self, user_id, message_id, *, max_bytes):
        return {"data_base64": base64.b64encode(b"synthetic media").decode(), "mime_type": "text/plain"}

    async def close(self):
        pass


class DiskOfflineOwner(OfflineOwner):
    """Child-only synthetic fixture; not available as a production setting."""

    def __init__(self, base, account):
        self.path = Path(base) / f"synthetic-{account}.json"
        if self.path.exists():
            state = json.loads(self.path.read_text(encoding="utf-8"))
            state["contacts"] = {int(key): value for key, value in state["contacts"].items()}
            self.states[account] = state
        super().__init__(base, account)

    async def auth_password(self, *args):
        result = await super().auth_password(*args)
        self.path.write_text(json.dumps(self.state), encoding="utf-8")
        return result

    async def send_text(self, *args):
        result = await super().send_text(*args)
        self.path.write_text(json.dumps(self.state), encoding="utf-8")
        return result

    async def close(self):
        self.path.write_text(json.dumps(self.state), encoding="utf-8")


@pytest.fixture
def product(config_file, monkeypatch):
    import eitaa_bridge.application.bale_runtime as runtime
    OfflineOwner.states = {}
    monkeypatch.setattr(runtime, "BaleProviderProcessWorker", lambda account, config: BaleProviderProcessWorker(account, config, owner_factory=OfflineOwner))
    config = json.loads(config_file.read_text(encoding="utf-8"))
    config["features"] = {"multi_session": {"enabled": True}, "app_user_auth": {"enabled": True, "self_registration_enabled": True}}
    config_file.write_text(json.dumps(config), encoding="utf-8")
    app = BridgeApplicationApi(config_file, phone_protector=Protector())
    setup = app.dispatch("POST", "/api/v2/app-auth/setup", body={"username": "product.admin", "password": "synthetic long password", "display_name": "Test Admin"}, client_kind="test")
    setup_status = setup.status
    assert setup_status == 201
    token = setup.headers["Set-Cookie"].split(";", 1)[0].split("=", 1)[1]
    csrf = setup.payload["csrf_token"]

    def request(method, path, body=None):
        return app.dispatch(method, path, body=body, app_session_token=token, csrf_token=csrf, client_kind="test", correlation_id=uuid4().hex)

    yield app, request
    app.close()


def create_account(request, phone="+10000000000", provider="bale"):
    result = request("POST", "/api/v2/messenger-accounts", {"provider": provider, "phone": phone, "label": "Fixture Account"})
    assert result.status == 201
    account = result.payload["account"]["messenger_account_id"]
    started = request("POST", f"/api/v2/messenger-accounts/{account}/worker/start")
    assert started.status == 200
    return account


def login(request, account):
    base = f"/api/v2/messenger-accounts/{account}"
    challenge = request("POST", f"{base}/auth/start", {"confirm": True})
    assert challenge.status == 200
    code = request("POST", f"{base}/auth/code", {"challenge_id": challenge.payload["challenge_id"], "code": "000000"})
    assert code.status == 200
    assert code.payload["step"] == "password"
    password = request("POST", f"{base}/auth/password", {"challenge_id": challenge.payload["challenge_id"], "password": "synthetic-password"})
    assert password.status == 200
    assert password.payload["auth_state"] == "authenticated"
    return base


def test_main_product_auth_contacts_history_send_media_and_durable_replay(product):
    app, request = product
    account = create_account(request)
    assert OfflineOwner.states[account]["calls"] == []  # startup has no provider traffic
    base = login(request, account)
    dialogs = request("POST", f"{base}/dialogs/query", {"limit": 50})
    assert dialogs.status == 200
    assert [item["peer_reference"] for item in dialogs.payload["dialogs"]] == ["bale:user:42", "bale:group:42"]
    assert dialogs.payload["dialogs"][0]["last_text"] == "Preview"
    send = {"peer_reference": "bale:user:42", "peer_kind": "private", "text": "synthetic message", "idempotency_key": "bale-send-fixture-0001", "confirm": True}
    for _ in range(2):
        response = request("POST", f"{base}/messages/send-text", send)
        assert response.status == 201
        assert response.payload["message_reference"] == "bale:submission:99"
    assert OfflineOwner.states[account]["calls"].count("send") == 1
    history = request("POST", f"{base}/history/query", {"peer_reference": "bale:user:42", "peer_kind": "private"})
    assert history.status == 200
    assert len(history.payload["messages"]) == 1
    imported = {"identity": "+10000000001", "display_name": "Named Fixture", "idempotency_key": "bale-import-fixture-0001", "confirm": True}
    for _ in range(2):
        assert request("POST", f"{base}/contacts/upsert", imported).status == 201
    assert OfflineOwner.states[account]["calls"].count("import") == 1
    assert OfflineOwner.states[account]["contacts"][43] == "Named Fixture"
    contacts = request("POST", f"{base}/contacts/search", {"query": "Named"})
    assert contacts.status == 200
    assert contacts.payload["contacts"][0]["contact_reference"] == "bale:user:43"
    assert "private-hash" not in repr(contacts.payload)
    assert app._m2m_resolve_recipients([{"kind": "phone", "value": "+10000000001"}], account)[0]["peer_reference"] == "bale:user:43"
    media_send = {"peer_reference": "bale:user:42", "peer_kind": "private", "filename": "fixture.txt", "data_base64": base64.b64encode(b"fixture").decode(), "idempotency_key": "bale-media-fixture-0001", "confirm": True}
    for _ in range(2):
        assert request("POST", f"{base}/messages/send-media", media_send).status == 200
    assert OfflineOwner.states[account]["calls"].count("media_send") == 1
    media = request("POST", f"{base}/media/read", {"peer_reference": "bale:user:42", "peer_kind": "private", "message_reference": "bale:message:17", "media_reference": "bale:media:42:17", "variant": "full", "max_bytes": 512 * 1024})
    assert media.status == 200
    content = request("POST", f"{base}/media/content", {"content_reference": media.payload["content_reference"]})
    assert content.status == 200
    assert base64.b64decode(content.payload["data_base64"]) == b"synthetic media"
    removal = {"contact_reference": "bale:user:43", "idempotency_key": "bale-remove-fixture-0001", "confirm": True}
    for _ in range(2):
        assert request("POST", f"{base}/contacts/remove", removal).status == 200
    assert OfflineOwner.states[account]["calls"].count("remove") == 1
    # Clear memory caches: persisted receipts still prevent a second mutation.
    assert request("POST", f"{base}/contacts/remove", removal).status == 200


def test_two_bale_accounts_and_eitaa_do_not_share_peers_challenges_or_media(product):
    app, request = product
    first = create_account(request)
    second = create_account(request, "+10000000002")
    eitaa = create_account(request, "+10000000003", "eitaa")
    base = login(request, first)
    second_base = f"/api/v2/messenger-accounts/{second}"
    challenge = request("POST", f"{second_base}/auth/start", {"confirm": True})
    assert challenge.status == 200
    rejected = request("POST", f"{base}/auth/code", {"challenge_id": challenge.payload["challenge_id"], "code": "000000"})
    assert rejected.status != 200
    cancel = request("POST", f"{second_base}/auth/cancel")
    assert cancel.status == 200
    assert cancel.payload["auth_state"] == "absent"
    assert request("POST", f"{second_base}/auth/code", {"challenge_id": challenge.payload["challenge_id"], "code": "000000"}).status != 200
    login(request, second)
    assert app._runtime_registry.peek_runtime_for_account(eitaa).runtime_record.provider == "eitaa"
    assert request("POST", f"{base}/messages/send-text", {"peer_reference": "bale:user:42", "peer_kind": "private", "text": "first account only", "idempotency_key": "account-send-fixture-0001", "confirm": True}).status == 201
    assert OfflineOwner.states[second]["messages"] == []
    assert app._m2m_resolve_recipients([{"kind": "phone", "value": "+10000000001"}], second)[0]["status"] == "unresolved"
    assert request("POST", f"{base}/auth/logout", {"confirm": True}).status == 200
    assert OfflineOwner.states[first]["vault"] is False
    assert OfflineOwner.states[second]["vault"] is True


@pytest.mark.parametrize("process_mode", [False, True])
def test_actual_bale_worker_start_restart_without_network(config_file, process_mode, monkeypatch):
    from eitaa_bridge.infrastructure.config import BridgeConfigLoader
    from eitaa_bridge.application.account_runtime import EitaaRuntimeRegistry
    from eitaa_bridge.infrastructure.diagnostics import RuntimeLogger, BridgeDiagnosticManager
    from eitaa_bridge.infrastructure.coordinator import CoordinatorDatabase, CoordinatorAppAuth, AppPrincipal
    config = json.loads(config_file.read_text(encoding="utf-8"))
    config["features"] = {"multi_session": {"enabled": True}, "worker_process": {"schema_version": 1, "enabled": process_mode,
        "heartbeat_interval_seconds": 1, "heartbeat_timeout_seconds": 5, "backoff_initial_seconds": 1}, "app_user_auth": {"enabled": True}}
    config_file.write_text(json.dumps(config), encoding="utf-8")
    # All startup/status/stop operations below must remain offline even for the
    # real child executable (no facade is constructed until a provider request).
    app = BridgeApplicationApi(config_file, phone_protector=Protector())
    setup = app.dispatch("POST", "/api/v2/app-auth/setup", body={"username": "worker.admin", "password": "synthetic long password", "display_name": "Worker Admin"}, client_kind="test")
    setup_status = setup.status
    assert setup_status == 201
    token = setup.headers["Set-Cookie"].split(";", 1)[0].split("=", 1)[1]
    def request(method, path, body=None):
        return app.dispatch(method, path, body=body, app_session_token=token, csrf_token=setup.payload["csrf_token"], client_kind="test")
    try:
        account = create_account(request)
        runtime = app._runtime_registry.peek_runtime_for_account(account)
        assert (runtime.client is not None) is process_mode
        status = request("GET", f"/api/v2/messenger-accounts/{account}/auth/status")
        assert status.status == 200
        assert status.payload["has_vault"] is False
        assert not list(config_file.parent.rglob("vault.key*"))
        generation = runtime.worker.generation
        assert request("POST", f"/api/v2/messenger-accounts/{account}/worker/stop").status == 200
        assert request("POST", f"/api/v2/messenger-accounts/{account}/worker/start").status == 200
        replacement = app._runtime_registry.peek_runtime_for_account(account)
        assert replacement.worker.generation > generation
        assert replacement is not runtime
        if process_mode:
            replacement.client.process.kill()
            replacement.client.process.wait(timeout=5)
            deadline = time.monotonic() + 20
            recovered = None
            while time.monotonic() < deadline:
                current = app._runtime_registry.peek_runtime_for_account(account)
                if current is not None and current is not replacement:
                    recovered = current
                    break
                time.sleep(0.1)
            assert recovered is not None
            assert recovered.worker.generation > replacement.worker.generation
            assert request("GET", f"/api/v2/messenger-accounts/{account}/auth/status").status == 200
            assert not list(config_file.parent.rglob("vault.key*"))
    finally:
        app.close()


def test_service_prepare_resolve_and_send_are_account_and_scope_fenced(product):
    app, request = product
    account = create_account(request)
    other = create_account(request, "+10000000002")
    login(request, account)
    credential = request("POST", "/api/v2/service-credentials", {"service_name": "Fixture Service", "allowed_providers": ["bale"],
        "allowed_messenger_account_ids": [account], "scopes": ["contacts.import", "contacts.resolve", "messages.send", "messages.status"]})
    status = credential.status
    assert status == 200
    authorization = "Bearer " + credential.payload["token"]
    def service(path, body, method="POST"):
        return app.dispatch(method, path, body=body, authorization=authorization, correlation_id=uuid4().hex)
    prepare = {"messenger_account_id": account, "provider": "bale", "phone": "+10000000001", "display_name": "OTP Fixture",
               "idempotency_key": "service-prepare-fixture-0001", "confirm": True}
    for _ in range(2):
        result = service("/api/v2/m2m/recipients/prepare", prepare)
        assert result.status == 200
        assert result.payload["peer_reference"]["value"] == "bale:user:43"
    assert OfflineOwner.states[account]["calls"].count("import") == 1
    denied = service("/api/v2/m2m/recipients/prepare", {**prepare, "messenger_account_id": other})
    assert denied.status == 403
    assert OfflineOwner.states[other]["calls"] == []
    sent = service("/api/v2/m2m/messages/send-text", {"messenger_account_id": account, "provider": "bale", "message_type": "otp",
        "peer_reference": {"kind": "dialog", "value": "bale:user:43"}, "text": "synthetic OTP text", "confirm": True,
        "idempotency_key": "service-send-fixture-0001"})
    assert sent.status in {200, 201, 202}
    assert OfflineOwner.states[account]["calls"].count("send") == 1
    unprivileged = request("POST", "/api/v2/service-credentials", {"service_name": "Readonly Fixture", "allowed_providers": ["bale"],
        "allowed_messenger_account_ids": [account], "scopes": ["contacts.resolve"]})
    safe_status = unprivileged.status
    assert safe_status == 200
    denied = app.dispatch("POST", "/api/v2/m2m/recipients/prepare", body={**prepare, "idempotency_key": "service-prepare-denied-0001"},
        authorization="Bearer " + unprivileged.payload["token"], correlation_id=uuid4().hex)
    assert denied.status == 403


def test_second_app_user_cannot_query_or_mutate_the_first_users_bale_account(product):
    app, request = product
    account = create_account(request)
    login(request, account)
    user = request("POST", "/api/v2/app-users", {"username": "second.user", "password": "synthetic second password", "display_name": "Second User", "global_role": "user"})
    status = user.status
    assert status == 201
    session = app.dispatch("POST", "/api/v2/app-auth/login", body={"username": "second.user", "password": "synthetic second password"}, client_kind="test")
    status = session.status
    assert status == 200
    token = session.headers["Set-Cookie"].split(";", 1)[0].split("=", 1)[1]
    for operation, payload in [
        ("contacts/query", {"limit": 20}), ("dialogs/query", {"limit": 20}),
        ("contacts/remove", {"contact_reference": "bale:user:42", "idempotency_key": "second-user-remove-fixture-0001", "confirm": True}),
        ("auth/start", {"confirm": True}),
    ]:
        denied = app.dispatch("POST", f"/api/v2/messenger-accounts/{account}/{operation}", body=payload,
            app_session_token=token, csrf_token=session.payload["csrf_token"], client_kind="test")
        assert denied.status == 403
    assert OfflineOwner.states[account]["calls"] == ["start", "code", "password"]


def test_child_auth_restore_history_and_receipt_replay_after_restart(config_file, monkeypatch):
    import eitaa_bridge.application.process_runtime as process_runtime
    real_popen = process_runtime.subprocess.Popen
    # Inject only in the test child launch; production entrypoint/codec/lifecycle
    # are exercised unchanged and production has no fake-backend configuration.
    script = (
        "import sys; sys.path.insert(0, " + repr(str(Path(__file__).parent)) + "); "
        "from test_bale_main_product import DiskOfflineOwner; "
        "from eitaa_bridge.application.bale_provider_worker import BaleProviderProcessWorker as W; "
        "W.__init__.__kwdefaults__['owner_factory'] = DiskOfflineOwner; "
        "from eitaa_bridge.interfaces.provider_worker import main; raise SystemExit(main())"
    )
    def launch(command, **kwargs):
        if "eitaa_bridge.interfaces.provider_worker" in command and "bale" in command:
            command = [command[0], "-c", script, *command[3:]]
        return real_popen(command, **kwargs)
    monkeypatch.setattr(process_runtime.subprocess, "Popen", launch)
    config = json.loads(config_file.read_text(encoding="utf-8"))
    config["features"] = {"multi_session": {"enabled": True}, "app_user_auth": {"enabled": True},
        "worker_process": {"schema_version": 1, "enabled": True, "heartbeat_interval_seconds": 1, "heartbeat_timeout_seconds": 5}}
    config_file.write_text(json.dumps(config), encoding="utf-8")
    app = BridgeApplicationApi(config_file, phone_protector=Protector())
    setup = app.dispatch("POST", "/api/v2/app-auth/setup", body={"username": "child.admin", "password": "synthetic long password", "display_name": "Child Admin"}, client_kind="test")
    status = setup.status
    assert status == 201
    token = setup.headers["Set-Cookie"].split(";", 1)[0].split("=", 1)[1]
    def request(method, path, body=None):
        return app.dispatch(method, path, body=body, app_session_token=token, csrf_token=setup.payload["csrf_token"], client_kind="test")
    try:
        account = create_account(request)
        base = login(request, account)
        send = {"peer_reference": "bale:user:42", "peer_kind": "private", "text": "child fixture", "idempotency_key": "child-restart-send-0001", "confirm": True}
        assert request("POST", f"{base}/messages/send-text", send).status == 201
        first = app._runtime_registry.peek_runtime_for_account(account)
        assert first.client.process_id != __import__("os").getpid()
        assert request("POST", f"{base}/worker/stop").status == 200
        assert request("POST", f"{base}/worker/start").status == 200
        second = app._runtime_registry.peek_runtime_for_account(account)
        assert second.worker.generation > first.worker.generation
        # A fresh application has no in-memory receipt cache. Both the protected
        # synthetic vault and the durable claim must survive application restart.
        protector = app._app_auth.phone_protector
        app.close()
        app = BridgeApplicationApi(config_file, phone_protector=protector)
        assert request("POST", f"{base}/messages/send-text", send).status == 201
        history = request("POST", f"{base}/history/query", {"peer_reference": "bale:user:42", "peer_kind": "private"})
        assert history.status == 200
        assert len(history.payload["messages"]) == 1
        state = json.loads((config_file.parent / f"synthetic-{account}.json").read_text(encoding="utf-8"))
        assert state["calls"].count("send") == 1
        assert state["calls"].count("start") == 1
        media = request("POST", f"{base}/media/read", {"peer_reference": "bale:user:42", "peer_kind": "private", "message_reference": "bale:message:17", "media_reference": "bale:media:42:17", "variant": "full", "max_bytes": 512 * 1024})
        assert media.status == 200
        content = request("POST", f"{base}/media/content", {"content_reference": media.payload["content_reference"]})
        content_status = content.status
        assert content_status == 200
        assert base64.b64decode(content.payload["data_base64"]) == b"synthetic media"
    finally:
        app.close()


def test_uncertain_send_is_persisted_and_never_retried(product, monkeypatch):
    app, request = product
    account = create_account(request)
    base = login(request, account)
    events = []
    original_emit = app._provider_orchestrator._logger.emit
    def emit(event, **fields):
        if fields.get("operation") in {"messages.send_text", "messages.send_media"}:
            events.append(event)
        return original_emit(event, **fields)
    monkeypatch.setattr(app._provider_orchestrator._logger, "emit", emit)
    async def lost_reply(self, user_id, text):
        self.state["calls"].append("send")
        raise TimeoutError("synthetic private detail must not escape")
    monkeypatch.setattr(OfflineOwner, "send_text", lost_reply)
    payload = {"peer_reference": "bale:user:42", "peer_kind": "private", "text": "uncertain fixture", "idempotency_key": "uncertain-send-fixture-0001", "confirm": True}
    for _ in range(2):
        result = request("POST", f"{base}/messages/send-text", payload)
        assert result.status == 201
        assert result.payload["status"] == "uncertain"
        assert "private detail" not in repr(result.payload)
    assert OfflineOwner.states[account]["calls"].count("send") == 1
    async def lost_media_reply(self, user_id, name, data, *, caption):
        self.state["calls"].append("media_send")
        raise TimeoutError("synthetic media reply lost")
    monkeypatch.setattr(OfflineOwner, "send_file_bytes", lost_media_reply)
    media = {"peer_reference": "bale:user:42", "peer_kind": "private", "filename": "fixture.txt", "data_base64": base64.b64encode(b"fixture").decode(), "idempotency_key": "uncertain-media-fixture-0001", "confirm": True}
    for _ in range(2):
        result = request("POST", f"{base}/messages/send-media", media)
        assert result.status == 200
        assert result.payload["status"] == "uncertain"
    assert OfflineOwner.states[account]["calls"].count("media_send") == 1
    assert "provider_operation_uncertain" in events
    assert "provider_operation_succeeded" not in events


def test_real_http_transport_uses_session_csrf_and_account_fences(product):
    from urllib.request import Request, urlopen
    from urllib.error import HTTPError
    from eitaa_bridge.interfaces.http_api import BridgeApiHttpServer
    app, request = product
    account = create_account(request)
    login(request, account)
    session = app.dispatch("POST", "/api/v2/app-auth/login", body={"username": "product.admin", "password": "synthetic long password"}, client_kind="test")
    status = session.status
    assert status == 200
    import threading
    server = BridgeApiHttpServer(("127.0.0.1", 0), app)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = f"http://127.0.0.1:{server.server_address[1]}/api/v2/messenger-accounts/{account}/dialogs/query"
        headers = {"Content-Type": "application/json", "Cookie": session.headers["Set-Cookie"].split(";", 1)[0], "X-CSRF-Token": session.payload["csrf_token"]}
        with urlopen(Request(url, data=b'{"limit":20}', headers=headers), timeout=10) as response:
            assert response.status == 200
            assert json.load(response)["dialogs"][0]["peer_reference"] == "bale:user:42"
        headers.pop("X-CSRF-Token")
        with pytest.raises(HTTPError) as denied:
            urlopen(Request(url, data=b'{"limit":20}', headers=headers), timeout=10)
        assert denied.value.code == 403
    finally:
        server.shutdown()
        server.server_close()


def test_concurrent_same_key_submits_at_most_once(product):
    from concurrent.futures import ThreadPoolExecutor
    app, request = product
    account = create_account(request)
    base = login(request, account)
    payload = {"peer_reference": "bale:user:42", "peer_kind": "private", "text": "concurrent fixture", "idempotency_key": "concurrent-send-fixture-0001", "confirm": True}
    with ThreadPoolExecutor(max_workers=4) as pool:
        statuses = list(pool.map(lambda _: request("POST", f"{base}/messages/send-text", payload).status, range(4)))
    assert 201 in statuses
    assert all(status in {201, 400, 409} for status in statuses)
    assert OfflineOwner.states[account]["calls"].count("send") == 1
    assert request("POST", f"{base}/messages/send-text", payload).status == 201


def test_restore_transport_failure_keeps_session_state_and_retry_allowed(product, monkeypatch):
    app, request = product
    account = create_account(request)
    base = login(request, account)
    from eitaa_bridge.application.bale_client.api import BaleApiError
    attempts = {"count": 0}
    original_connect = OfflineOwner.connect

    def flaky_connect(self, **kwargs):
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise BaleApiError("Connection failed: synthetic transport outage", code="bale_connect_failed")
        return original_connect(self, **kwargs)

    monkeypatch.setattr(OfflineOwner, "connect", flaky_connect)
    first = request("POST", f"{base}/auth/restore", {"confirm": True})
    assert first.status == 200
    # A transport outage is not proof of session invalidity: the account must
    # keep its state so a later restore attempt stays possible (no invalid latch).
    assert first.payload["reason_code"] == "bale_restore_unavailable"
    assert first.payload["auth_state"] == "authenticated"
    second = request("POST", f"{base}/auth/restore", {"confirm": True})
    assert second.status == 200
    assert second.payload["auth_state"] == "authenticated"
    assert attempts["count"] == 2
    dialogs = request("POST", f"{base}/dialogs/query", {"limit": 10})
    assert dialogs.status == 200


def test_restore_rejected_vault_latches_session_invalid(product, monkeypatch):
    app, request = product
    account = create_account(request)
    base = login(request, account)
    from eitaa_bridge.application.bale_client.api import BaleApiError

    def locked_connect(self, **kwargs):
        raise BaleApiError("Vault passphrase rejected", code="bale_vault_locked")

    monkeypatch.setattr(OfflineOwner, "connect", locked_connect)
    first = request("POST", f"{base}/auth/restore", {"confirm": True})
    assert first.status == 200
    assert first.payload["auth_state"] == "invalid"
    blocked = request("POST", f"{base}/auth/restore", {"confirm": True})
    assert blocked.status != 200


def test_live_updates_capability_has_polling_transport_observation(product):
    app, request = product
    account = create_account(request)
    response = request("GET", f"/api/v2/messenger-accounts/{account}/capabilities")
    assert response.status == 200
    decisions = {item["capability"]: item for item in response.payload["capabilities"]}
    updates = decisions["updates.live"]
    assert updates["status"] == "supported"
    assert updates["reason_code"] == "bale_updates_polling_transport"
    assert updates["constraints_present"] is True


def test_bale_contacts_pagination_501_contacts_and_cursor_bounds(product):
    app, request = product
    account = create_account(request)
    base = login(request, account)
    OfflineOwner.states[account]["contacts"] = {i: f"Synthetic Contact {i}" for i in range(1, 502)}

    seen = []
    cursor = None
    page_count = 0
    while True:
        body = {"limit": 100}
        if cursor is not None:
            body["cursor"] = cursor
        res = request("POST", f"{base}/contacts/query", body)
        assert res.status == 200
        contacts = res.payload["contacts"]
        seen.extend(contacts)
        page_count += 1
        cursor = res.payload.get("next_cursor")
        if cursor is None:
            break
        assert cursor.startswith("offset:")

    assert page_count == 6
    assert len(seen) == 501
    assert len({item["contact_reference"] for item in seen}) == 501
    assert seen[-1]["contact_reference"] == "bale:user:501"

    # Malformed cursor: negative or non-numeric
    bad_cursor = request("POST", f"{base}/contacts/query", {"cursor": "invalid_cursor"})
    assert bad_cursor.status == 400
    assert (bad_cursor.payload.get("code") == "provider_cursor_invalid"
            or bad_cursor.payload.get("error", {}).get("error_code") == "provider_cursor_invalid")

    # Cursor beyond total items returns empty page and next_cursor None
    beyond = request("POST", f"{base}/contacts/query", {"cursor": "offset:600"})
    assert beyond.status == 200
    assert beyond.payload["contacts"] == []
    assert beyond.payload.get("next_cursor") is None

    # Search finds the 501st contact directly
    search = request("POST", f"{base}/contacts/search", {"query": "Contact 501"})
    assert search.status == 200
    assert len(search.payload["contacts"]) == 1
    assert search.payload["contacts"][0]["contact_reference"] == "bale:user:501"


def test_bale_rate_limit_admission_claim_lifecycle_retry_and_payload_conflict(product, monkeypatch):
    from datetime import datetime, timedelta, timezone
    import eitaa_bridge.infrastructure.coordinator.rate_policy as rate_policy

    app, request = product
    account = create_account(request)
    base = login(request, account)

    now = [datetime(2026, 9, 29, 12, 0, tzinfo=timezone.utc)]
    monkeypatch.setattr(rate_policy, "_utc", lambda value: value or now[0])
    policy = rate_policy.AccountExecutionPolicyService(
        app._coordinator, default_capacity=1, default_refill_per_second=1,
    )
    app._provider_orchestrator._execution_policy = policy

    def code(response):
        return response.payload.get("error", {}).get("error_code") or response.payload.get("code")

    # 1. messages.send_text rate limit, payload conflict, and retry
    body = {
        "peer_reference": "bale:user:42",
        "peer_kind": "private",
        "text": "First allowed text",
        "confirm": True,
        "idempotency_key": "bale-rate-allowed-0001",
    }
    first = request("POST", f"{base}/messages/send-text", body)
    assert first.status == 201

    denied_key = "bale-rate-denied-0002"
    denied_body = dict(body, idempotency_key=denied_key, text="Denied initial text")
    denied = request("POST", f"{base}/messages/send-text", denied_body)
    assert denied.status == 429
    assert "Retry-After" in denied.headers
    assert code(denied) == "provider_operation_rate_limited"
    assert OfflineOwner.states[account]["calls"].count("send") == 1
    assert len(app._provider_orchestrator._send_in_progress) == 0

    # Same key with different payload text -> 409 conflict, NO adapter call
    conflict_body = dict(denied_body, text="Changed conflict text")
    conflict = request("POST", f"{base}/messages/send-text", conflict_body)
    assert conflict.status == 409
    assert code(conflict) == "provider_idempotency_payload_mismatch"
    assert OfflineOwner.states[account]["calls"].count("send") == 1

    # Refill bucket: same key with original payload text -> 201 success
    now[0] += timedelta(seconds=10)
    retried = request("POST", f"{base}/messages/send-text", denied_body)
    assert retried.status == 201
    assert OfflineOwner.states[account]["calls"].count("send") == 2

    # Replay of succeeded key without consuming new tokens or calling adapter
    replay = request("POST", f"{base}/messages/send-text", denied_body)
    assert replay.status == 201
    assert OfflineOwner.states[account]["calls"].count("send") == 2

    # 2. contacts.upsert rate limit, payload conflict, and retry
    policy.acquire(messenger_account_id=account, operation_scope="contacts.upsert")
    upsert_body = {
        "identity": "bale:user:444",
        "display_name": "Initial Name",
        "idempotency_key": "bale-upsert-rate-0001",
        "confirm": True,
    }
    denied_upsert = request("POST", f"{base}/contacts/upsert", upsert_body)
    assert denied_upsert.status == 429
    assert "Retry-After" in denied_upsert.headers
    assert 444 not in OfflineOwner.states[account]["contacts"]

    # Different payload with same key -> 409 conflict
    conflict_upsert = request("POST", f"{base}/contacts/upsert", dict(upsert_body, display_name="Different Name"))
    assert conflict_upsert.status == 409
    assert code(conflict_upsert) == "provider_idempotency_payload_mismatch"

    # Refill and retry original -> 201
    now[0] += timedelta(seconds=10)
    retried_upsert = request("POST", f"{base}/contacts/upsert", upsert_body)
    assert retried_upsert.status == 201
    assert 444 in OfflineOwner.states[account]["contacts"]

    # 3. messages.send_media rate limit and payload conflict
    policy.acquire(messenger_account_id=account, operation_scope="messages.send_media")
    media_body = {
        "peer_reference": "bale:user:42",
        "peer_kind": "private",
        "filename": "file.txt",
        "data_base64": base64.b64encode(b"content").decode(),
        "idempotency_key": "bale-media-rate-key-0001",
        "confirm": True,
    }
    denied_media = request("POST", f"{base}/messages/send-media", media_body)
    assert denied_media.status == 429
    assert "Retry-After" in denied_media.headers

    conflict_media = request("POST", f"{base}/messages/send-media", dict(media_body, filename="other.txt"))
    assert conflict_media.status == 409
    assert code(conflict_media) == "provider_idempotency_payload_mismatch"

    now[0] += timedelta(seconds=10)
    retried_media = request("POST", f"{base}/messages/send-media", media_body)
    assert retried_media.status == 200

    # 4. contacts.remove rate limit and payload conflict
    policy.acquire(messenger_account_id=account, operation_scope="contacts.remove")
    remove_body = {
        "contact_reference": "bale:user:42",
        "idempotency_key": "bale-remove-rate-key-0001",
        "confirm": True,
    }
    denied_remove = request("POST", f"{base}/contacts/remove", remove_body)
    assert denied_remove.status == 429
    assert "Retry-After" in denied_remove.headers

    conflict_remove = request("POST", f"{base}/contacts/remove", dict(remove_body, contact_reference="bale:user:43"))
    assert conflict_remove.status == 409
    assert code(conflict_remove) == "provider_idempotency_payload_mismatch"

    now[0] += timedelta(seconds=10)
    retried_remove = request("POST", f"{base}/contacts/remove", remove_body)
    assert retried_remove.status == 200


def test_bale_rate_limit_http_transport_loopback(product, monkeypatch):
    from datetime import datetime, timezone
    from urllib.request import Request, urlopen
    from urllib.error import HTTPError
    from eitaa_bridge.interfaces.http_api import BridgeApiHttpServer
    import eitaa_bridge.infrastructure.coordinator.rate_policy as rate_policy

    app, request = product
    account = create_account(request)
    login(request, account)

    now = [datetime(2026, 9, 29, 12, 0, tzinfo=timezone.utc)]
    monkeypatch.setattr(rate_policy, "_utc", lambda value: value or now[0])
    policy = rate_policy.AccountExecutionPolicyService(
        app._coordinator, default_capacity=1, default_refill_per_second=1,
    )
    app._provider_orchestrator._execution_policy = policy

    policy.acquire(messenger_account_id=account, operation_scope="messages.send_text")

    session = app.dispatch("POST", "/api/v2/app-auth/login", body={"username": "product.admin", "password": "synthetic long password"}, client_kind="test")
    assert session.status == 200

    import threading
    server = BridgeApiHttpServer(("127.0.0.1", 0), app)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = f"http://127.0.0.1:{server.server_address[1]}/api/v2/messenger-accounts/{account}/messages/send-text"
        headers = {
            "Content-Type": "application/json",
            "Cookie": session.headers["Set-Cookie"].split(";", 1)[0],
            "X-CSRF-Token": session.payload["csrf_token"],
        }
        body = json.dumps({
            "peer_reference": "bale:user:42",
            "peer_kind": "private",
            "text": "loopback rate limit test",
            "idempotency_key": "bale-http-rate-key-0001",
            "confirm": True,
        }).encode("utf-8")
        with pytest.raises(HTTPError) as exc_info:
            urlopen(Request(url, data=body, headers=headers), timeout=10)
        assert exc_info.value.code == 429
        assert "Retry-After" in exc_info.value.headers
    finally:
        server.shutdown()
        server.server_close()


def test_bale_attempt_fence_delayed_cleanup_and_terminal_lifecycle(tmp_path):
    """Verify that late cleanup of a prior attempt cannot release or complete
    a newer attempt across text, media, and remove operations, and that terminal
    records reject release and conflicting completion.
    """
    from eitaa_bridge.errors import CoordinatorSchemaError
    from eitaa_bridge.infrastructure.coordinator import (
        CoordinatorDatabase,
        ProtectedPhone,
        ProviderOperationReceiptStore,
    )

    db_path = tmp_path / "coordinator.sqlite3"
    database = CoordinatorDatabase(db_path)
    database.initialize()
    bootstrap = database.bootstrap_legacy_account(
        protected_phone=ProtectedPhone(
            ciphertext=b"synthetic-only",
            key_version=1,
            fingerprint="1" * 64,
            display_hint="+••••••••67",
        ),
        display_name="Synthetic admin",
        backup_name="fixture.zip",
        source_manifest_sha256="a" * 64,
        source_file_count=1,
        source_total_bytes=1,
    )
    account_id = bootstrap.messenger_account_id
    actor_id = bootstrap.app_user_id
    store = ProviderOperationReceiptStore(database)

    operations_to_test = [
        ("messages.send_text", "bale:msg:001", None),
        ("messages.send_media", "bale:msg:002", None),
        ("contacts.remove", "bale:contact:removed:42", False),
    ]

    for op, success_ref, contact_created in operations_to_test:
        identity = dict(
            messenger_account_id=account_id,
            actor_app_user_id=actor_id,
            operation=op,
            idempotency_key=f"fence-key-{op.replace('.', '-')}",
            request_fingerprint=hashlib.sha256(f"payload-{op}".encode()).hexdigest(),
        )

        # 1. Attempt 1 claim
        first = store.claim(
            **identity,
            actor_global_role="admin",
            claim_deadline_unix_ms=4_000_000_000_000,
        )
        assert first.claimed is True
        token_1 = first.receipt.attempt_token
        assert token_1 is not None and token_1.startswith("attempt-")
        assert first.receipt.attempt_generation == 1
        assert first.attempt_token == token_1

        # Release attempt 1 with its valid attempt token
        assert store.release(**identity, attempt_token=token_1) is True

        # Duplicate release of already released claim returns False
        assert store.release(**identity, attempt_token=token_1) is False

        # 2. Attempt 2 claim (same owner, same idempotency key, same fingerprint)
        second = store.claim(
            **identity,
            actor_global_role="admin",
            claim_deadline_unix_ms=4_000_000_000_001,
        )
        assert second.claimed is True
        token_2 = second.receipt.attempt_token
        assert token_2 is not None and token_2.startswith("attempt-")
        assert token_2 != token_1
        assert second.receipt.attempt_generation == 2
        assert second.attempt_token == token_2

        # Stale cleanup from attempt 1 (passing token_1) CANNOT release attempt 2
        stale_release = store.release(**identity, attempt_token=token_1)
        assert stale_release is False

        # Untokened stale release on generation > 1 CANNOT release attempt 2
        untokened_release = store.release(**identity, attempt_token=None)
        assert untokened_release is False

        # Attempt 2 claim remains active and in_progress
        with database._connect() as conn:
            row = conn.execute(
                "SELECT * FROM provider_operation_receipts WHERE messenger_account_id=? AND operation=? AND idempotency_key=?",
                (account_id, op, identity["idempotency_key"]),
            ).fetchone()
        assert row is not None
        assert row["outcome"] == "in_progress"
        assert row["safe_reason_code"] is None
        assert str(row["attempt_token"]) == token_2
        assert int(row["attempt_generation"]) == 2

        # Delayed completion from attempt 1 (passing token_1) MUST fail with attempt mismatch
        with pytest.raises(CoordinatorSchemaError) as exc_info:
            store.complete(
                **identity,
                attempt_token=token_1,
                outcome="succeeded",
                result_reference=success_ref,
                contact_created=contact_created,
                safe_reason_code=None,
            )
        assert getattr(exc_info.value, "code", None) == "provider_receipt_attempt_mismatch"

        # Attempt 2 completion with matching token_2 succeeds
        completed = store.complete(
            **identity,
            attempt_token=token_2,
            outcome="succeeded",
            result_reference=success_ref,
            contact_created=contact_created,
            safe_reason_code=None,
        )
        assert completed.outcome == "succeeded"
        assert completed.result_reference == success_ref
        assert completed.contact_created == contact_created

        # 3. Terminal state protections
        # Attempting to release a terminal completed receipt returns False
        assert store.release(**identity) is False
        assert store.release(**identity, attempt_token=token_2) is False
        assert store.release(**identity, attempt_token=token_1) is False

        # Re-claiming on terminal receipt returns existing record (not claimed)
        reclaim = store.claim(
            **identity,
            actor_global_role="admin",
            claim_deadline_unix_ms=4_000_000_000_002,
        )
        assert reclaim.claimed is False
        assert reclaim.receipt.outcome == "succeeded"

        # Attempting conflicting completion on terminal record fails with result mismatch
        with pytest.raises(CoordinatorSchemaError) as exc_conflict:
            store.complete(
                **identity,
                attempt_token=token_2,
                outcome="succeeded",
                result_reference="bale:other:999",
                contact_created=contact_created,
                safe_reason_code=None,
            )
        assert getattr(exc_conflict.value, "code", None) == "provider_receipt_result_mismatch"

    # 4. Restart and reclaim preserves fence across DB reopens
    identity_restart = dict(
        messenger_account_id=account_id,
        actor_app_user_id=actor_id,
        operation="messages.send_text",
        idempotency_key="fence-restart-key-001",
        request_fingerprint=hashlib.sha256(b"restart-payload").hexdigest(),
    )
    pre_claim = store.claim(**identity_restart, actor_global_role="admin", claim_deadline_unix_ms=4_000_000_000_000)
    pre_token = pre_claim.receipt.attempt_token
    assert store.release(**identity_restart, attempt_token=pre_token) is True

    # Simulate application restart: reopen DB
    database_reopened = CoordinatorDatabase(db_path)
    store_reopened = ProviderOperationReceiptStore(database_reopened)

    # Reclaim after restart increments generation and gives fresh token
    reclaim_after_restart = store_reopened.claim(
        **identity_restart,
        actor_global_role="admin",
        claim_deadline_unix_ms=4_000_000_000_001,
    )
    assert reclaim_after_restart.claimed is True
    assert reclaim_after_restart.receipt.attempt_generation == 2
    assert reclaim_after_restart.receipt.attempt_token != pre_token

    # Pre-restart token cannot release the new claim
    assert store_reopened.release(**identity_restart, attempt_token=pre_token) is False
    assert store_reopened.release(**identity_restart) is False


def test_bale_child_contact_ipc_frame_limit_and_large_address_book(tmp_path):
    """Verify that a large address book (2,000 contacts with 512-character names)
    which overflows the single IPC frame limit (1 MiB) is properly paged across
    the Child process IPC boundary with bounded frames, and that all contacts are reachable.
    """
    from eitaa_bridge.infrastructure.worker_ipc import (
        IPC_MAX_MESSAGE_BYTES,
        IpcEnvelope,
        WorkerIpcCodec,
        WorkerIpcSecretFile,
    )
    from eitaa_bridge.errors import WorkerIpcError

    account_id = str(uuid4())
    secret_dir = tmp_path / "ipc-secret"
    secret_dir.mkdir(parents=True, exist_ok=True)
    material, secret_path = WorkerIpcSecretFile.create(
        secret_dir,
        messenger_account_id=account_id,
        provider="bale",
    )
    codec = WorkerIpcCodec(material)

    # 1. Construct 2,000 synthetic contacts with 512-character names
    contacts_data = {
        i: f"Contact_{i:04d}_" + ("A" * 499)
        for i in range(1, 2001)
    }
    assert len(contacts_data[1]) == 512

    # Verify that returning all 2,000 in a single unpaged list produces a payload > 1 MiB
    raw_contacts_list = [
        {"peer": {"id": k, "type": 1}, "name": v, "local_name": v}
        for k, v in contacts_data.items()
    ]
    raw_unpaged_bytes = json.dumps(raw_contacts_list).encode("utf-8")
    assert len(raw_unpaged_bytes) > IPC_MAX_MESSAGE_BYTES

    # Also verify that encoding an unpaged IPC response envelope directly would raise WorkerIpcError
    dummy_req = IpcEnvelope(
        "request", str(uuid4()), account_id, "bale", "bale.provider.contacts.query",
        int(time.time() * 1000) + 30000, uuid4().hex, {}, "synthetic", "0" * 64,
    )
    with pytest.raises(WorkerIpcError) as exc_large:
        codec.response(dummy_req, {"contacts": raw_contacts_list, "total": 2000})
    assert exc_large.value.code == "ipc_message_too_large"

    # 2. Setup custom owner returning this large address book
    class LargeAddressBookOwner(OfflineOwner):
        states = {}

        def __init__(self, base, account):
            super().__init__(base, account)
            self.state["contacts"] = dict(contacts_data)
            self.state["vault"] = True
            self.list_call_count = 0

        async def list_contacts(self):
            self.list_call_count += 1
            return await super().list_contacts()

    bridge_config = tmp_path / "bridge.json"
    bridge_config.write_text("{}", encoding="utf-8")
    worker = BaleProviderProcessWorker(
        account_id,
        bridge_config,
        owner_factory=LargeAddressBookOwner,
    )
    instance_id = str(uuid4())

    def send_ipc(method, payload):
        full_payload = dict(payload)
        if method not in {"worker.hello", "bale.runtime.start"}:
            full_payload.setdefault("worker_instance_id", instance_id)
            full_payload.setdefault("worker_generation", 1)
            full_payload.setdefault("session_generation", 1)
        req = IpcEnvelope(
            "request", str(uuid4()), account_id, "bale", method,
            int(time.time() * 1000) + 30000, uuid4().hex, full_payload,
            "synthetic", "0" * 64,
        )
        dispatch_res = worker.dispatch(req)
        resp_encoded = codec.response(req, dispatch_res.payload)
        frame_bytes = resp_encoded.encode("utf-8")
        return dispatch_res.payload, len(frame_bytes)

    # Initialize worker lifecycle
    hello_res, _ = send_ipc("worker.hello", {})
    assert hello_res["status"] == "bootstrap_ready"
    start_res, _ = send_ipc("bale.runtime.start", {
        "runtime_record": {
            "provider": "bale", "messenger_account_id": account_id,
            "lifecycle_state": "active", "desired_worker_state": "running",
            "storage_revision": 1, "session_generation": 1,
        },
        "worker_instance_id": instance_id, "worker_generation": 1,
    })
    assert start_res["status"] == "ready"
    restore_res, _ = send_ipc("bale.auth.restore", {})
    assert restore_res["authenticated"] is True

    # The old search response shape put every 512-character name in one IPC
    # frame. Preserve that exact legacy payload as a codec regression witness.
    raw_search = worker._run(
        worker._owner().search_contacts("Contact_"), int(time.time() * 1000) + 30_000,
    )
    legacy_search_contacts = [
        {"peer": item.get("peer"), "name": item.get("name"), "local_name": item.get("local_name")}
        for item in raw_search if isinstance(item, dict)
    ]
    old_search_req = IpcEnvelope(
        "request", str(uuid4()), account_id, "bale", "bale.provider.contacts.search",
        int(time.time() * 1000) + 30_000, uuid4().hex, {}, "synthetic", "0" * 64,
    )
    with pytest.raises(WorkerIpcError) as broad_search_overflow:
        codec.response(old_search_req, {"contacts": legacy_search_contacts})
    assert broad_search_overflow.value.code == "ipc_message_too_large"

    # 3. Query contacts page by page (limit=500) and verify each frame is bounded
    collected = []
    list_calls_before_paging = worker.owner.list_call_count
    cursor = None
    page_count = 0
    while True:
        payload = {"limit": 500}
        if cursor is not None:
            payload["cursor"] = cursor
        page_payload, frame_size = send_ipc("bale.provider.contacts.query", payload)
        # Verify frame is well below 1 MiB limit (< 350 KiB)
        assert frame_size < 350_000
        items = page_payload["contacts"]
        collected.extend(items)
        page_count += 1
        cursor = page_payload.get("next_cursor")
        if not page_payload.get("has_more") or cursor is None:
            break

    assert page_count == 4
    assert len(collected) == 2000
    assert len({item["peer"]["id"] for item in collected}) == 2000
    assert collected[-1]["peer"]["id"] == 2000
    assert worker.owner.list_call_count == list_calls_before_paging + 1  # one full-source read per traversal

    # A new first-page request refreshes the snapshot for external changes.
    worker.owner.state["contacts"][2001] = "External update"
    refreshed, refreshed_size = send_ipc("bale.provider.contacts.query", {"offset": 0, "limit": 1})
    assert refreshed["total"] == 2001
    assert worker.owner.list_call_count == list_calls_before_paging + 2
    assert refreshed_size < 350_000

    # 4. Verify bale.provider.contacts.contains for fast membership without full transfer
    worker.owner.state["contacts"][2002] = "External membership update"
    checks = [(1, True), (1000, True), (2000, True), (2002, True), (9999, False)]
    for check_id, expected in checks:
        contains_payload, frame_size = send_ipc("bale.provider.contacts.contains", {"peer_id": check_id})
        assert contains_payload["exists"] is expected
        assert frame_size < 1000
    assert worker.owner.list_call_count == list_calls_before_paging + 2 + len(checks)

    worker.owner.state["contacts"][1] = "x" * 8193
    with pytest.raises(WorkerIpcError) as oversized_snapshot:
        send_ipc("bale.provider.contacts.query", {"offset": 0, "limit": 1})
    assert oversized_snapshot.value.code == "provider_contact_snapshot_too_large"


def test_bale_product_api_large_address_book_pagination_and_search(product):
    """Verify that BridgeApplicationApi contacts endpoint pages through
    the 2,000 synthetic contacts and search locates contact 2,000.
    """
    app, request = product
    account = create_account(request)
    base = login(request, account)

    contacts_data = {
        i: f"Contact_{i:04d}_" + ("B" * 499)
        for i in range(1, 2001)
    }
    OfflineOwner.states[account]["contacts"] = contacts_data

    # Page 1 with limit=100
    p1 = request("POST", f"{base}/contacts/query", {"limit": 100})
    assert p1.status == 200
    assert len(p1.payload["contacts"]) == 100
    assert p1.payload["next_cursor"] == "offset:100"

    # Search directly finds contact 2000
    search = request("POST", f"{base}/contacts/search", {"query": "Contact_2000"})
    assert search.status == 200
    assert len(search.payload["contacts"]) == 1
    assert search.payload["contacts"][0]["contact_reference"] == "bale:user:2000"


def test_child_process_large_address_book_real_popen_paging_and_last_page(config_file, monkeypatch):
    """Verify that a real OS Child process (spawned via subprocess.Popen) hosting
    a large address book (2,000 synthetic contacts with 512-character names,
    raw unpaged payload > 1.13 MiB) enforces bounded IPC frames (< 350 KiB),
    enables complete traversal across pages to the last page (contact 2,000),
    supports UI pagination (loadContacts + loadMoreContacts), validates cursor/limit,
    maintains two-account isolation, and resolves OTP phone lookups without fetching page 1.
    """
    import os
    import eitaa_bridge.application.process_runtime as process_runtime
    real_popen = process_runtime.subprocess.Popen
    script = (
        "import sys; sys.path.insert(0, " + repr(str(Path(__file__).parent)) + "); "
        "from test_bale_main_product import DiskOfflineOwner; "
        "from eitaa_bridge.application.bale_provider_worker import BaleProviderProcessWorker as W; "
        "W.__init__.__kwdefaults__['owner_factory'] = DiskOfflineOwner; "
        "from eitaa_bridge.interfaces.provider_worker import main; raise SystemExit(main())"
    )
    def launch(command, **kwargs):
        if "eitaa_bridge.interfaces.provider_worker" in command and "bale" in command:
            command = [command[0], "-c", script, *command[3:]]
        return real_popen(command, **kwargs)
    monkeypatch.setattr(process_runtime.subprocess, "Popen", launch)
    config = json.loads(config_file.read_text(encoding="utf-8"))
    config["features"] = {
        "multi_session": {"enabled": True},
        "app_user_auth": {"enabled": True},
        "worker_process": {
            "schema_version": 1,
            "enabled": True,
            "heartbeat_interval_seconds": 1,
            "heartbeat_timeout_seconds": 5,
        },
    }
    config_file.write_text(json.dumps(config), encoding="utf-8")
    app = BridgeApplicationApi(config_file, phone_protector=Protector())
    setup = app.dispatch("POST", "/api/v2/app-auth/setup", body={"username": "child.admin", "password": "synthetic long password", "display_name": "Child Admin"}, client_kind="test")
    assert setup.status == 201
    token = setup.headers["Set-Cookie"].split(";", 1)[0].split("=", 1)[1]
    def request(method, path, body=None):
        return app.dispatch(method, path, body=body, app_session_token=token, csrf_token=setup.payload["csrf_token"], client_kind="test", correlation_id=uuid4().hex)

    try:
        # Create and login Account 1 (large address book)
        account_1 = create_account(request, phone="+10000000001")
        base_1 = login(request, account_1)

        # Create and login Account 2 (isolation check)
        account_2 = create_account(request, phone="+10000000002")
        base_2 = login(request, account_2)

        # Build 2,000 synthetic contacts with 512-character names
        contacts_data = {
            str(i): f"Contact_{i:04d}_" + ("C" * 499)
            for i in range(1, 2001)
        }
        assert len(contacts_data["1"]) == 512

        # Stop workers first before writing synthetic states so close() does not overwrite them
        assert request("POST", f"{base_1}/worker/stop").status == 200
        assert request("POST", f"{base_2}/worker/stop").status == 200

        synthetic_1 = config_file.parent / f"synthetic-{account_1}.json"
        state_1 = json.loads(synthetic_1.read_text(encoding="utf-8"))
        state_1["contacts"] = contacts_data
        state_1["phones"] = {"+10000000001": 42, "+10000002000": 2000}
        synthetic_1.write_text(json.dumps(state_1), encoding="utf-8")

        synthetic_2 = config_file.parent / f"synthetic-{account_2}.json"
        state_2 = json.loads(synthetic_2.read_text(encoding="utf-8"))
        state_2["contacts"] = {"101": "Iso User 101", "102": "Iso User 102"}
        synthetic_2.write_text(json.dumps(state_2), encoding="utf-8")

        # Start workers to launch new child processes reading the updated states
        assert request("POST", f"{base_1}/worker/start").status == 200
        assert request("POST", f"{base_2}/worker/start").status == 200

        rt1 = app._runtime_registry.peek_runtime_for_account(account_1)
        rt2 = app._runtime_registry.peek_runtime_for_account(account_2)
        assert rt1.client.process_id != os.getpid()
        assert rt2.client.process_id != os.getpid()
        assert rt1.client.process_id != rt2.client.process_id

        # Spy on IPC frame sizes across the OS pipe
        frame_sizes = []
        orig_queue = rt1.client._queue_response
        def spy_queue(val):
            if isinstance(val, str):
                frame_sizes.append(len(val.encode("utf-8")))
            return orig_queue(val)
        rt1.client._queue_response = spy_queue

        # 1. Account isolation: Account 2 only sees its own 2 contacts
        res_iso = request("POST", f"{base_2}/contacts/query", {"limit": 100})
        assert res_iso.status == 200
        assert len(res_iso.payload["contacts"]) == 2
        assert res_iso.payload["next_cursor"] is None

        # 2. Malformed cursor and limit validation on Account 1
        err_cur = request("POST", f"{base_1}/contacts/query", {"cursor": "malformed_cursor"})
        assert err_cur.status == 400
        assert (err_cur.payload.get("code") == "provider_cursor_invalid"
                or err_cur.payload.get("error", {}).get("error_code") == "provider_cursor_invalid")

        err_cur_neg = request("POST", f"{base_1}/contacts/query", {"cursor": "offset:-5"})
        assert err_cur_neg.status == 400
        assert (err_cur_neg.payload.get("code") == "provider_cursor_invalid"
                or err_cur_neg.payload.get("error", {}).get("error_code") == "provider_cursor_invalid")

        err_lim = request("POST", f"{base_1}/contacts/query", {"limit": 999})
        assert err_lim.status == 400

        err_lim_zero = request("POST", f"{base_1}/contacts/query", {"limit": 0})
        assert err_lim_zero.status == 400

        # 3. Different page sizes: 100 vs 250
        p100 = request("POST", f"{base_1}/contacts/query", {"limit": 100})
        assert p100.status == 200
        assert len(p100.payload["contacts"]) == 100
        assert p100.payload["next_cursor"] == "offset:100"

        p250 = request("POST", f"{base_1}/contacts/query", {"limit": 250})
        assert p250.status == 200
        assert len(p250.payload["contacts"]) == 250
        assert p250.payload["next_cursor"] == "offset:250"

        # 4. Traversal across all pages with limit=500 (4 pages to reach contact 2,000)
        collected_500 = []
        cursor = None
        page_count = 0
        while True:
            body = {"limit": 500}
            if cursor is not None:
                body["cursor"] = cursor
            res = request("POST", f"{base_1}/contacts/query", body)
            assert res.status == 200
            items = res.payload["contacts"]
            collected_500.extend(items)
            page_count += 1
            cursor = res.payload.get("next_cursor")
            if not cursor:
                break

        assert page_count == 4
        assert len(collected_500) == 2000
        all_refs = [c["contact_reference"] for c in collected_500]
        # Zero duplicate and zero missing
        assert len(set(all_refs)) == 2000
        assert "bale:user:1" in all_refs
        assert "bale:user:2000" in all_refs
        # Last page contact
        assert collected_500[-1]["contact_reference"] == "bale:user:2000"
        assert collected_500[-1]["display_name"].startswith("Contact_2000_")

        # 5. Every single IPC frame across the OS pipe must remain strictly < 350 KiB
        assert len(frame_sizes) > 0
        assert all(size < 350_000 for size in frame_sizes)

        # 6. UI workflow simulation (loadContacts + loadMoreContacts)
        p_init = request("POST", f"{base_1}/contacts/query", {"limit": 100})
        assert p_init.status == 200
        ui_contacts = list(p_init.payload["contacts"])
        ui_cursor = p_init.payload.get("next_cursor")
        while ui_cursor:
            res = request("POST", f"{base_1}/contacts/query", {"limit": 100, "cursor": ui_cursor})
            assert res.status == 200
            existing = {item["contact_reference"] for item in ui_contacts}
            fresh = [item for item in res.payload["contacts"] if item["contact_reference"] not in existing]
            ui_contacts.extend(fresh)
            next_c = res.payload.get("next_cursor")
            ui_cursor = next_c if next_c != ui_cursor else None

        assert len(ui_contacts) == 2000
        assert len({item["contact_reference"] for item in ui_contacts}) == 2000

        # 7. Search for last contact from UI
        search_res = request("POST", f"{base_1}/contacts/search", {"query": "Contact_2000"})
        assert search_res.status == 200
        assert len(search_res.payload["contacts"]) == 1
        assert search_res.payload["contacts"][0]["contact_reference"] == "bale:user:2000"

        # 8. Broad search must page through the Child IPC boundary too. The
        # 2,000 long names overflow the 1 MiB frame when returned at once.
        broad_search = []
        search_cursor = None
        search_pages = 0
        while True:
            body = {"query": "Contact_", "limit": 100}
            if search_cursor:
                body["cursor"] = search_cursor
            res = request("POST", f"{base_1}/contacts/search", body)
            assert res.status == 200
            broad_search.extend(res.payload["contacts"])
            search_pages += 1
            search_cursor = res.payload.get("next_cursor")
            if not search_cursor:
                break
        broad_refs = [item["contact_reference"] for item in broad_search]
        assert search_pages == 20
        assert len(broad_refs) == 2000
        assert len(set(broad_refs)) == 2000
        assert broad_refs[-1] == "bale:user:2000"
        assert all(size < 350_000 for size in frame_sizes)

        # 9. M2M recipient resolution for new number (lookup_phone without fetching page 1)
        credential = request("POST", "/api/v2/service-credentials", {
            "service_name": "OTP Fixture",
            "allowed_providers": ["bale"],
            "allowed_messenger_account_ids": [account_1],
            "scopes": ["contacts.import", "contacts.resolve", "messages.send", "messages.status"],
        })
        assert credential.status == 200
        auth_header = "Bearer " + credential.payload["token"]
        prep = app.dispatch(
            "POST",
            "/api/v2/m2m/recipients/resolve",
            body={
                "messenger_account_id": account_1,
                "provider": "bale",
                "recipients": [{"kind": "phone", "value": "+10000002000"}],
            },
            authorization=auth_header,
            correlation_id=uuid4().hex,
        )
        assert prep.status == 200
        assert prep.payload["results"][0]["status"] == "resolved"
        assert prep.payload["results"][0]["peer_reference"] == "bale:user:2000"
    finally:
        app.close()
