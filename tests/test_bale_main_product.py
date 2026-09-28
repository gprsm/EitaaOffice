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
        assert request("POST", f"{base}/messages/send-text", send).status == 201
        history = request("POST", f"{base}/history/query", {"peer_reference": "bale:user:42", "peer_kind": "private"})
        assert history.status == 200
        assert len(history.payload["messages"]) == 1
        state = json.loads((config_file.parent / f"synthetic-{account}.json").read_text(encoding="utf-8"))
        assert state["calls"].count("send") == 1
        assert state["calls"].count("start") == 1
    finally:
        app.close()


def test_uncertain_send_is_persisted_and_never_retried(product, monkeypatch):
    app, request = product
    account = create_account(request)
    base = login(request, account)
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
