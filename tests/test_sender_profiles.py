"""P1 sender profile tests: per-service, per-intent pinned senders.

Every fixture here is synthetic; nothing touches bridge.json, operational
data or any live provider. The tests assert server-side enforcement of the
sender profile (a hand-picked account_id can never bypass it), versioned
atomic writes with revision control, honest unavailability reporting and the
documented migration policy for data that has no profile configured yet.
"""

from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import threading

import pytest

import eitaa_bridge.application.api as api_module
from eitaa_bridge.application.api import BridgeApplicationApi
from eitaa_bridge.infrastructure.coordinator import (
    CoordinatorAppAuth,
    CoordinatorDatabase,
    ProtectedPhone,
    StaticSubjectFingerprinter,
)
from eitaa_bridge.infrastructure.coordinator.sender_profiles import (
    SenderProfileError,
    ServiceSenderProfileStore,
)
from eitaa_bridge.providers.contracts import ProviderSendStatus

_DATABASE_PATH_PART = ("data", "coordinator", "coordinator.sqlite3")

_BRIDGE_JSON_BEFORE_SENDS: bytes | None = None


def _enable_features(config_file: Path) -> None:
    payload = json.loads(config_file.read_text(encoding="utf-8"))
    payload["features"] = {
        "multi_session": {"enabled": True},
        "app_user_auth": {
            "enabled": True,
            "self_registration_enabled": True,
            "idle_timeout_minutes": 525_600,
            "absolute_timeout_hours": 8_760,
            "max_failed_attempts": 5,
            "lockout_minutes": 15,
        },
    }
    config_file.write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )


def _prepared_api(config_file: Path, monkeypatch) -> tuple[BridgeApplicationApi, str]:
    _enable_features(config_file)
    database_path = config_file.parent.joinpath(*_DATABASE_PATH_PART)
    account_summary = CoordinatorDatabase(database_path).bootstrap_legacy_account(
        protected_phone=ProtectedPhone(
            ciphertext=b"protected-phone",
            key_version=1,
            fingerprint="b" * 64,
            display_hint="+••••••••67",
        ),
        display_name="Initial administrator",
        backup_name="verified.zip",
        source_manifest_sha256="a" * 64,
        source_file_count=1,
        source_total_bytes=1,
    )
    auth = CoordinatorAppAuth(
        database_path,
        fingerprinter=StaticSubjectFingerprinter(b"sender-profile-test-subject"),
    )
    monkeypatch.setattr(
        api_module,
        "CoordinatorAppAuth",
        lambda _database_path, *, policy: auth,
    )
    api = BridgeApplicationApi(config_file)
    return api, account_summary.messenger_account_id


def _cookie_token(response) -> str:
    cookie = response.headers["Set-Cookie"]
    name, token = cookie.split(";", 1)[0].split("=", 1)
    assert name == "eitaa_bridge_app_session"
    return token


def _setup_admin(api: BridgeApplicationApi) -> tuple[str, str]:
    setup = api.dispatch(
        "POST",
        "/api/v2/app-auth/setup",
        body={
            "username": "local.admin",
            "password": "correct horse battery staple",
            "display_name": "مدیر آزمون",
        },
        client_kind="test",
    )
    assert setup.status == 201, setup.payload
    return _cookie_token(setup), setup.payload["csrf_token"]


def _login(api: BridgeApplicationApi) -> tuple[str, str]:
    login = api.dispatch(
        "POST",
        "/api/v2/app-auth/login",
        body={"username": "local.admin", "password": "correct horse battery staple"},
        client_kind="test",
    )
    assert login.status == 200, login.payload
    return _cookie_token(login), login.payload["csrf_token"]


def _onboard_account(
    api: BridgeApplicationApi,
    token: str,
    csrf: str,
    *,
    provider: str,
    phone: str,
    label: str,
) -> str:
    response = api.dispatch(
        "POST",
        "/api/v2/messenger-accounts",
        body={"provider": provider, "phone": phone, "label": label},
        app_session_token=token,
        csrf_token=csrf,
    )
    assert response.status == 201, response.payload
    return response.payload["account"]["messenger_account_id"]


def _issue_credential(
    api: BridgeApplicationApi,
    token: str,
    csrf: str,
    name: str,
    account_ids: list[str],
    providers: list[str],
    *,
    scopes: list[str] | None = None,
) -> dict:
    response = api.dispatch(
        "POST",
        "/api/v2/service-credentials",
        body={
            "service_name": name,
            "description": "P1 sender profile fixture",
            "allowed_providers": providers,
            "allowed_messenger_account_ids": account_ids,
            "scopes": scopes if scopes else [
                "messages.send", "messages.status",
                "contacts.resolve", "contacts.import",
            ],
        },
        app_session_token=token,
        csrf_token=csrf,
    )
    assert response.status == 200, response.payload
    return {
        "credential": response.payload["credential"],
        "token": response.payload["token"],
    }


def _pin_profile(api: BridgeApplicationApi, token: str, csrf: str, body: dict):
    return api.dispatch(
        "PUT",
        "/api/v2/service-sender-profiles",
        body=body,
        app_session_token=token,
        csrf_token=csrf,
    )


def _profile_body(
    credential_id: str,
    intent: str,
    provider: str,
    account_id: str,
    *,
    enabled: bool = True,
    expected_revision: int | None = None,
) -> dict:
    body: dict = {
        "service_credential_id": credential_id,
        "intent": intent,
        "provider": provider,
        "messenger_account_id": account_id,
        "enabled": enabled,
    }
    if expected_revision is not None:
        body["expected_revision"] = expected_revision
    return body


def _m2m_send(api: BridgeApplicationApi, svc_token: str, **body_overrides):
    body = {
        "intent": "otp",
        "peer_reference": {"kind": "dialog", "value": "user:123"},
        "text": "hello",
        "idempotency_key": "1234567890123456",
        "confirm": True,
    }
    body.update(body_overrides)
    return api.dispatch(
        "POST",
        "/api/v2/m2m/messages/send-text",
        body=body,
        authorization=f"Bearer {svc_token}",
        correlation_id="req-12345678-1234-1234-1234-123456789012",
    )


def _list_profiles(api: BridgeApplicationApi, token: str) -> list[dict]:
    response = api.dispatch(
        "GET",
        "/api/v2/service-sender-profiles",
        app_session_token=token,
    )
    assert response.status == 200, response.payload
    return response.payload["profiles"]


class CountingOrchestrator:
    """Fake send path: records which account each request was routed to."""

    def __init__(self):
        self.sent_accounts: list[str] = []

    async def send_text(self, actor, messenger_account_id, correlation_id, deadline_unix_ms, request):
        self.sent_accounts.append(str(messenger_account_id))
        receipt = type("Receipt", (), {})()
        receipt.status = ProviderSendStatus.SUCCEEDED
        receipt.message_reference = "synthetic-ref"
        receipt.safe_reason_code = None
        return receipt


@pytest.fixture()
def two_services(config_file, monkeypatch):
    """Admin session, two eitaa accounts, one bale account and two services.

    Service A owns both eitaa accounts; service B owns the bale account.
    """
    api, first_eitaa_account = _prepared_api(config_file, monkeypatch)
    token, csrf = _setup_admin(api)
    second_eitaa_account = _onboard_account(
        api, token, csrf,
        provider="eitaa", phone="+989120000002", label="ارسال‌کننده دوم",
    )
    bale_account = _onboard_account(
        api, token, csrf,
        provider="bale", phone="+989120000003", label="حساب بله آزمون",
    )
    service_a = _issue_credential(
        api, token, csrf, "service-a",
        [first_eitaa_account, second_eitaa_account], ["eitaa"],
    )
    service_b = _issue_credential(api, token, csrf, "service-b", [bale_account], ["bale"])
    return {
        "api": api,
        "token": token,
        "csrf": csrf,
        "first_eitaa_account": first_eitaa_account,
        "second_eitaa_account": second_eitaa_account,
        "bale_account": bale_account,
        "service_a": service_a["credential"],
        "service_a_token": service_a["token"],
        "service_b": service_b["credential"],
        "service_b_token": service_b["token"],
        "database_path": config_file.parent.joinpath(*_DATABASE_PATH_PART),
    }


def test_two_services_pin_save_reload_and_send_to_pinned_account(two_services):
    api = two_services["api"]
    token, csrf = two_services["token"], two_services["csrf"]

    created_a = api.dispatch(
        "PUT",
        "/api/v2/service-sender-profiles",
        body=_profile_body(
            two_services["service_a"]["id"], "otp", "eitaa",
            two_services["first_eitaa_account"],
        ),
        app_session_token=token,
        csrf_token=csrf,
    )
    assert created_a.status == 200, created_a.payload
    pin_a = created_a.payload["profile"]
    assert pin_a["intent"] == "otp"
    assert pin_a["provider"] == "eitaa"
    assert pin_a["messenger_account_id"] == two_services["first_eitaa_account"]
    assert pin_a["revision"] == 1
    assert pin_a["enabled"] is True

    created_b = api.dispatch(
        "PUT",
        "/api/v2/service-sender-profiles",
        body=_profile_body(
            two_services["service_b"]["id"], "otp", "bale",
            two_services["bale_account"],
        ),
        app_session_token=token,
        csrf_token=csrf,
    )
    assert created_b.status == 200, created_b.payload
    assert created_b.payload["profile"]["provider"] == "bale"

    # Reload: both services keep independent pins, per intent.
    profiles = _list_profiles(api, token)
    pins = {
        (profile["service_credential_id"], profile["intent"]): profile
        for profile in profiles
    }
    assert pins[(two_services["service_a"]["id"], "otp")]["messenger_account_id"] \
        == two_services["first_eitaa_account"]
    assert pins[(two_services["service_b"]["id"], "otp")]["messenger_account_id"] \
        == two_services["bale_account"]

    # A fake send through each profile reaches exactly its pinned account.
    orchestrator = CountingOrchestrator()
    api._provider_orchestrator = orchestrator
    response_a = _m2m_send(api, two_services["service_a_token"], sender_profile_id=pin_a["id"])
    assert response_a.status == 200, response_a.payload
    assert response_a.payload["delivery_status"] == "provider_succeeded"
    response_b = _m2m_send(
        api, two_services["service_b_token"],
        sender_profile_id=created_b.payload["profile"]["id"],
        peer_reference={"kind": "dialog", "value": "bale:user:77"},
    )
    assert response_b.status == 200, response_b.payload
    assert orchestrator.sent_accounts == [
        two_services["first_eitaa_account"],
        two_services["bale_account"],
    ]


def test_rejected_requests_never_reach_the_send_path(two_services):
    api = two_services["api"]
    token, csrf = two_services["token"], two_services["csrf"]
    pin = api.dispatch(
        "PUT",
        "/api/v2/service-sender-profiles",
        body=_profile_body(
            two_services["service_a"]["id"], "otp", "eitaa",
            two_services["first_eitaa_account"],
        ),
        app_session_token=token,
        csrf_token=csrf,
    ).payload["profile"]

    orchestrator = CountingOrchestrator()
    api._provider_orchestrator = orchestrator

    # 1. An account outside the credential allowlist is refused by the fence
    #    (the notification intent has no pin, so the credential fence answers).
    outside = _m2m_send(
        api, two_services["service_a_token"],
        intent="notification", messenger_account_id="0" * 36,
    )
    assert outside.status == 403
    assert outside.payload["code"] == "m2m_account_not_allowed"

    # 2. Another service's profile id is not usable by this service.
    other = _m2m_send(api, two_services["service_b_token"], sender_profile_id=pin["id"])
    assert other.status == 400
    assert other.payload["code"] == "sender_not_configured"

    # 3. A credential without the send scope is refused outright.
    scopeless = _issue_credential(
        api, token, csrf, "scopeless",
        [two_services["first_eitaa_account"]], ["eitaa"],
        scopes=["messages.status"],
    )
    scopeless_response = _m2m_send(
        api, scopeless["token"], messenger_account_id=two_services["first_eitaa_account"],
    )
    assert scopeless_response.status == 403
    assert scopeless_response.payload["code"] == "m2m_scope_insufficient"

    # 4. The admin cannot pin a provider outside the credential fence.
    rejected = api.dispatch(
        "PUT",
        "/api/v2/service-sender-profiles",
        body=_profile_body(
            two_services["service_a"]["id"], "otp", "bale",
            two_services["bale_account"],
        ),
        app_session_token=token,
        csrf_token=csrf,
    )
    assert rejected.status == 400
    assert rejected.payload["error"]["error_code"] == "m2m_provider_not_allowed"

    # 5. An unknown provider string is rejected before any account write.
    unknown_provider = api.dispatch(
        "PUT",
        "/api/v2/service-sender-profiles",
        body=_profile_body(
            two_services["service_a"]["id"], "otp", "telegram",
            two_services["first_eitaa_account"],
        ),
        app_session_token=token,
        csrf_token=csrf,
    )
    assert unknown_provider.status == 400
    assert unknown_provider.payload["error"]["error_code"] == "sender_profile_provider_unknown"

    # Nothing was sent: every rejection happened before the send path.
    assert orchestrator.sent_accounts == []


def test_profile_pins_block_account_id_bypass(two_services):
    api = two_services["api"]
    token, csrf = two_services["token"], two_services["csrf"]
    api.dispatch(
        "PUT",
        "/api/v2/service-sender-profiles",
        body=_profile_body(
            two_services["service_a"]["id"], "otp", "eitaa",
            two_services["first_eitaa_account"],
        ),
        app_session_token=token,
        csrf_token=csrf,
    )

    orchestrator = CountingOrchestrator()
    api._provider_orchestrator = orchestrator

    # A hand-picked account_id can never bypass the pinned sender.
    bypass = _m2m_send(
        api, two_services["service_a_token"],
        messenger_account_id=two_services["second_eitaa_account"],
        intent="otp",
    )
    assert bypass.status == 409
    assert bypass.payload["code"] == "sender_profile_mismatch"
    assert orchestrator.sent_accounts == []

    # The pinned account itself remains usable through the legacy field.
    legacy = _m2m_send(
        api, two_services["service_a_token"],
        messenger_account_id=two_services["first_eitaa_account"],
    )
    assert legacy.status == 200
    assert orchestrator.sent_accounts == [two_services["first_eitaa_account"]]


def test_revision_control_and_account_unavailable(two_services):
    api = two_services["api"]
    token, csrf = two_services["token"], two_services["csrf"]
    service_a_id = two_services["service_a"]["id"]

    # Creating while claiming an existing revision is stale, never applied.
    stale_create = api.dispatch(
        "PUT",
        "/api/v2/service-sender-profiles",
        body=_profile_body(
            service_a_id, "otp", "eitaa", two_services["first_eitaa_account"],
            expected_revision=1,
        ),
        app_session_token=token,
        csrf_token=csrf,
    )
    assert stale_create.status == 409
    assert stale_create.payload["error"]["error_code"] == "stale_revision"

    pinned = api.dispatch(
        "PUT",
        "/api/v2/service-sender-profiles",
        body=_profile_body(
            service_a_id, "otp", "eitaa", two_services["first_eitaa_account"],
        ),
        app_session_token=token,
        csrf_token=csrf,
    ).payload["profile"]
    assert pinned["revision"] == 1

    # An update without a revision is refused, never silently applied.
    missing_revision = api.dispatch(
        "PUT",
        "/api/v2/service-sender-profiles",
        body=_profile_body(
            service_a_id, "otp", "eitaa", two_services["second_eitaa_account"],
        ),
        app_session_token=token,
        csrf_token=csrf,
    )
    assert missing_revision.status == 400
    assert missing_revision.payload["error"]["error_code"] == "sender_profile_revision_required"

    # Editor one wins revision 2; editor two still holds revision 1 and is
    # told the revision is stale instead of overwriting the winner.
    first_update = api.dispatch(
        "PUT",
        "/api/v2/service-sender-profiles",
        body=_profile_body(
            service_a_id, "otp", "eitaa",
            two_services["second_eitaa_account"], expected_revision=1,
        ),
        app_session_token=token,
        csrf_token=csrf,
    )
    assert first_update.status == 200, first_update.payload
    assert first_update.payload["profile"]["revision"] == 2

    loser_token, loser_csrf = _login(api)
    loser = api.dispatch(
        "PUT",
        "/api/v2/service-sender-profiles",
        body=_profile_body(
            service_a_id, "otp", "eitaa",
            two_services["first_eitaa_account"], expected_revision=1,
        ),
        app_session_token=loser_token,
        csrf_token=loser_csrf,
    )
    assert loser.status == 409
    assert loser.payload["error"]["error_code"] == "stale_revision"

    # Archiving the pinned account makes the profile honestly unavailable.
    with sqlite3.connect(two_services["database_path"]) as connection:
        connection.execute(
            "UPDATE messenger_accounts SET lifecycle_state='archived' WHERE id=?",
            (two_services["second_eitaa_account"],),
        )
        connection.commit()
    profiles = _list_profiles(api, token)
    assert all(profile["account_available"] is False for profile in profiles)

    orchestrator = CountingOrchestrator()
    api._provider_orchestrator = orchestrator
    unavailable = _m2m_send(
        api, two_services["service_a_token"], sender_profile_id=pinned["id"],
    )
    assert unavailable.status == 409
    assert unavailable.payload["code"] == "account_unavailable"
    assert orchestrator.sent_accounts == []


def test_legacy_data_without_profile_keeps_explicit_contract(two_services):
    api = two_services["api"]
    global _BRIDGE_JSON_BEFORE_SENDS
    bridge_json = two_services["database_path"].parent.parent.parent / "bridge.json"
    _BRIDGE_JSON_BEFORE_SENDS = (
        bridge_json.read_bytes() if bridge_json.exists() else None
    )


    # No profile is configured: the legacy explicit account contract keeps
    # working (documented migration policy).
    orchestrator = CountingOrchestrator()
    api._provider_orchestrator = orchestrator
    legacy = _m2m_send(
        api, two_services["service_a_token"],
        messenger_account_id=two_services["second_eitaa_account"],
    )
    assert legacy.status == 200, legacy.payload
    assert orchestrator.sent_accounts == [two_services["second_eitaa_account"]]

    # A request with neither profile nor explicit account is refused; no
    # first-in-list or most-recently-used account is picked silently.
    unconfigured = _m2m_send(api, two_services["service_a_token"])
    assert unconfigured.status == 400
    assert unconfigured.payload["code"] == "sender_not_configured"
    assert orchestrator.sent_accounts == [two_services["second_eitaa_account"]]

    # No operational artefact was modified and nothing was sent implicitly.
    bridge_json = two_services["database_path"].parent.parent.parent / "bridge.json"
    if bridge_json.exists():
        # The bridge configuration snapshot that existed before these
        # requests is byte-identical: profile work never touches it.
        assert bridge_json.read_bytes() == _BRIDGE_JSON_BEFORE_SENDS
    assert orchestrator.sent_accounts == [two_services["second_eitaa_account"]]


def test_sender_profile_store_unit_behavior(config_file, monkeypatch):
    api, account_id = _prepared_api(config_file, monkeypatch)
    token, csrf = _setup_admin(api)
    me = api.dispatch("GET", "/api/v2/app-auth/me", app_session_token=token)
    admin_app_user_id = me.payload["principal"]["app_user_id"]
    service = _issue_credential(api, token, csrf, "unit-service", [account_id], ["eitaa"])
    credential_id = service["credential"]["id"]

    store = ServiceSenderProfileStore(api._coordinator)
    created = store.upsert_profile(
        credential_id, "notification", "eitaa", account_id,
        enabled=True, expected_revision=None, actor_app_user_id=admin_app_user_id,
    )
    assert created.revision == 1
    assert created.enabled is True

    updated = store.upsert_profile(
        credential_id, "notification", "eitaa", account_id,
        enabled=False, expected_revision=1, actor_app_user_id=admin_app_user_id,
    )
    assert updated.revision == 2
    assert updated.enabled is False
    assert updated.id == created.id

    with pytest.raises(SenderProfileError) as conflict:
        store.upsert_profile(
            credential_id, "notification", "eitaa", account_id,
            enabled=True, expected_revision=1, actor_app_user_id=admin_app_user_id,
        )
    assert conflict.value.code == "stale_revision"

    # A disabled profile is not an enabled pin for the bypass guard.
    assert store.try_get_enabled_profile(credential_id, "notification") is None

    store.delete_profile(created.id)
    assert store.get_profile(created.id) is None
    with pytest.raises(SenderProfileError):
        store.delete_profile(created.id)

    assert store.account_available("0" * 36) is False


def test_real_http_transport_enforces_sender_profile_contract(two_services):
    import urllib.request

    from eitaa_bridge.interfaces.http_api import BridgeApiHttpServer

    api = two_services["api"]
    token, csrf = two_services["token"], two_services["csrf"]
    pin = api.dispatch(
        "PUT",
        "/api/v2/service-sender-profiles",
        body=_profile_body(
            two_services["service_a"]["id"], "otp", "eitaa",
            two_services["first_eitaa_account"],
        ),
        app_session_token=token,
        csrf_token=csrf,
    ).payload["profile"]

    orchestrator = CountingOrchestrator()
    api._provider_orchestrator = orchestrator

    server = BridgeApiHttpServer(("127.0.0.1", 0), api)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = f"http://127.0.0.1:{server.server_address[1]}/api/v2/m2m/messages/send-text"
        body = json.dumps({
            "sender_profile_id": pin["id"],
            "intent": "otp",
            "peer_reference": {"kind": "dialog", "value": "user:123"},
            "text": "hello",
            "idempotency_key": "1234567890123456",
            "confirm": True,
        }).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {two_services['service_a_token']}",
                "X-Request-Id": "req-12345678-1234-1234-1234-123456789012",
            },
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            payload = json.load(response)
        assert response.status == 200
        assert payload["delivery_status"] == "provider_succeeded"
        assert orchestrator.sent_accounts == [two_services["first_eitaa_account"]]
        # No secret material in the response payload.
        serialized = json.dumps(payload)
        assert "eb_svc_" not in serialized
        assert "+9891" not in serialized

        # A stale revision over the admin surface is a 409, not an overwrite.
        stale = api.dispatch(
            "PUT",
            "/api/v2/service-sender-profiles",
            body=_profile_body(
                two_services["service_a"]["id"], "otp", "eitaa",
                two_services["second_eitaa_account"], expected_revision=99,
            ),
            app_session_token=token,
            csrf_token=csrf,
        )
        assert stale.status == 409
        assert stale.payload["error"]["error_code"] == "stale_revision"
    finally:
        server.shutdown()
        server.server_close()
