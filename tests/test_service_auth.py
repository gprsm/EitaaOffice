"""Tests for M2M service authentication and authorization boundaries."""

from __future__ import annotations

import json
from pathlib import Path
import pytest

import eitaa_bridge.application.api as api_module
from eitaa_bridge.application.api import APP_USER_SESSION_COOKIE, BridgeApplicationApi
from eitaa_bridge.infrastructure.coordinator import (
    CoordinatorAppAuth,
    CoordinatorDatabase,
    ProtectedPhone,
    StaticSubjectFingerprinter,
)


def _enable_app_auth(config_file: Path) -> None:
    payload = json.loads(config_file.read_text(encoding="utf-8"))
    payload["features"] = {
        "multi_session": {"enabled": False},
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
    _enable_app_auth(config_file)
    database_path = config_file.parent / "data" / "coordinator" / "coordinator.sqlite3"
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
        fingerprinter=StaticSubjectFingerprinter(b"api-test-subject-secret"),
    )
    monkeypatch.setattr(
        api_module,
        "CoordinatorAppAuth",
        lambda _database_path, *, policy: auth,
    )
    api = BridgeApplicationApi(config_file)
    messenger_account_id = account_summary.messenger_account_id
    return api, messenger_account_id


def _cookie_token(response) -> str:
    cookie = response.headers["Set-Cookie"]
    first = cookie.split(";", 1)[0]
    name, token = first.split("=", 1)
    assert name == APP_USER_SESSION_COOKIE
    assert token
    return token


def _setup_admin(api: BridgeApplicationApi) -> tuple[str, str]:
    setup = api.dispatch(
        "POST",
        "/api/v2/app-auth/setup",
        body={
            "username": "local.admin",
            "password": "correct horse battery staple",
            "display_name": "مدیر محلی",
        },
        client_kind="test",
    )
    assert setup.status == 201
    return _cookie_token(setup), setup.payload["csrf_token"]


def test_service_token_happy_path(config_file, monkeypatch):
    api, messenger_account_id = _prepared_api(config_file, monkeypatch)
    token, csrf = _setup_admin(api)

    # 1. Create a service credential as admin
    resp = api.dispatch(
        "POST",
        "/api/v2/service-credentials",
        body={
            "service_name": "exam-service",
            "description": "Integration with education system",
            "allowed_providers": ["eitaa"],
            "allowed_messenger_account_ids": [messenger_account_id],
            "scopes": ["messages.send"],
        },
        app_session_token=token,
        csrf_token=csrf,
    )
    assert resp.status == 200
    assert resp.payload["ok"] is True
    svc_token = resp.payload["token"]
    assert svc_token.startswith("eb_svc_")

    # 2. List credentials as admin
    listed = api.dispatch(
        "GET",
        "/api/v2/service-credentials",
        app_session_token=token,
    )
    assert listed.status == 200
    assert any(c["service_name"] == "exam-service" for c in listed.payload["credentials"])

    # 3. Use the token on the M2M endpoint
    m2m_resp = api.dispatch(
        "POST",
        "/api/v2/m2m/messages/send-text",
        body={
            "messenger_account_id": messenger_account_id,
            "message_type": "notice",
            "peer_reference": {"kind": "phone", "value": "+989000000000"},
            "text": "Hello exam",
            "idempotency_key": "1234567890123456",
            "confirm": True,
        },
        authorization=f"Bearer {svc_token}",
        correlation_id="req-12345678-1234-1234-1234-123456789012",
    )
    # Auth, scope, account fencing and validation all passed; the request is
    # honestly refused only because a raw phone is not a resolvable peer.
    assert m2m_resp.status == 409
    assert m2m_resp.payload["code"] == "m2m_recipient_unresolved"


def test_service_token_wrong_account(config_file, monkeypatch):
    api, messenger_account_id = _prepared_api(config_file, monkeypatch)
    token, csrf = _setup_admin(api)

    resp = api.dispatch(
        "POST",
        "/api/v2/service-credentials",
        body={
            "service_name": "restricted-service",
            "description": "Wrong account test",
            "allowed_providers": ["eitaa"],
            "allowed_messenger_account_ids": ["00000000-0000-0000-0000-000000000001"],
            "scopes": ["messages.send"],
        },
        app_session_token=token,
        csrf_token=csrf,
    )
    svc_token = resp.payload["token"]

    m2m_resp = api.dispatch(
        "POST",
        "/api/v2/m2m/messages/send-text",
        body={
            "messenger_account_id": messenger_account_id,
            "message_type": "notice",
            "peer_reference": {"kind": "phone", "value": "+989000000000"},
            "text": "Hello",
            "idempotency_key": "1234567890123456",
            "confirm": True,
        },
        authorization=f"Bearer {svc_token}",
        correlation_id="req-12345678-1234-1234-1234-123456789012",
    )
    assert m2m_resp.status == 403
    assert m2m_resp.payload["code"] == "m2m_account_not_allowed"


def test_service_token_wrong_scope(config_file, monkeypatch):
    api, messenger_account_id = _prepared_api(config_file, monkeypatch)
    token, csrf = _setup_admin(api)

    resp = api.dispatch(
        "POST",
        "/api/v2/service-credentials",
        body={
            "service_name": "resolve-only-service",
            "description": "Resolve only",
            "allowed_providers": ["eitaa"],
            "allowed_messenger_account_ids": [messenger_account_id],
            "scopes": ["contacts.resolve"],
        },
        app_session_token=token,
        csrf_token=csrf,
    )
    svc_token = resp.payload["token"]

    m2m_resp = api.dispatch(
        "POST",
        "/api/v2/m2m/messages/send-text",
        body={
            "messenger_account_id": messenger_account_id,
            "message_type": "notice",
            "peer_reference": {"kind": "phone", "value": "+989000000000"},
            "text": "Hello",
            "idempotency_key": "1234567890123456",
            "confirm": True,
        },
        authorization=f"Bearer {svc_token}",
        correlation_id="req-12345678-1234-1234-1234-123456789012",
    )
    assert m2m_resp.status == 403
    assert m2m_resp.payload["code"] == "m2m_scope_insufficient"


def test_service_token_revocation_and_rotation(config_file, monkeypatch):
    api, messenger_account_id = _prepared_api(config_file, monkeypatch)
    token, csrf = _setup_admin(api)

    resp = api.dispatch(
        "POST",
        "/api/v2/service-credentials",
        body={
            "service_name": "rotatable-service",
            "description": "Rotate test",
            "allowed_providers": ["eitaa"],
            "allowed_messenger_account_ids": [messenger_account_id],
            "scopes": ["messages.send"],
        },
        app_session_token=token,
        csrf_token=csrf,
    )
    cred_id = resp.payload["credential"]["id"]
    old_token = resp.payload["token"]

    # Rotate
    rotated = api.dispatch(
        "POST",
        f"/api/v2/service-credentials/{cred_id}/rotate",
        app_session_token=token,
        csrf_token=csrf,
    )
    assert rotated.status == 200
    new_token = rotated.payload["token"]
    assert new_token != old_token

    # Old token fails
    old_m2m = api.dispatch(
        "POST",
        "/api/v2/m2m/messages/send-text",
        body={
            "messenger_account_id": messenger_account_id,
            "message_type": "notice",
            "peer_reference": {"kind": "phone", "value": "+989000000000"},
            "text": "Hello",
            "idempotency_key": "1234567890123456",
            "confirm": True,
        },
        authorization=f"Bearer {old_token}",
        correlation_id="req-12345678-1234-1234-1234-123456789012",
    )
    assert old_m2m.status == 401

    # Revoke
    revoked = api.dispatch(
        "POST",
        f"/api/v2/service-credentials/{cred_id}/revoke",
        app_session_token=token,
        csrf_token=csrf,
    )
    assert revoked.status == 200

    # New token also fails after revocation
    new_m2m = api.dispatch(
        "POST",
        "/api/v2/m2m/messages/send-text",
        body={
            "messenger_account_id": messenger_account_id,
            "message_type": "notice",
            "peer_reference": {"kind": "phone", "value": "+989000000000"},
            "text": "Hello",
            "idempotency_key": "1234567890123456",
            "confirm": True,
        },
        authorization=f"Bearer {new_token}",
        correlation_id="req-12345678-1234-1234-1234-123456789012",
    )
    assert new_m2m.status == 401


def test_service_token_missing_request_id(config_file, monkeypatch):
    api, messenger_account_id = _prepared_api(config_file, monkeypatch)
    token, csrf = _setup_admin(api)

    resp = api.dispatch(
        "POST",
        "/api/v2/service-credentials",
        body={
            "service_name": "req-id-service",
            "description": "Req ID test",
            "allowed_providers": ["eitaa"],
            "allowed_messenger_account_ids": [messenger_account_id],
            "scopes": ["messages.send"],
        },
        app_session_token=token,
        csrf_token=csrf,
    )
    svc_token = resp.payload["token"]

    # Direct inner dispatch without request_id
    m2m_resp = api._dispatch_inner(
        "POST",
        "/api/v2/m2m/messages/send-text",
        body={"text": "hi"},
        authorization=f"Bearer {svc_token}",
        request_id=None,
    )
    assert m2m_resp.status == 400
    assert m2m_resp.payload["error"]["error_code"] == "m2m_request_id_missing"


def test_service_token_body_size(config_file, monkeypatch):
    api, messenger_account_id = _prepared_api(config_file, monkeypatch)
    token, csrf = _setup_admin(api)

    resp = api.dispatch(
        "POST",
        "/api/v2/service-credentials",
        body={
            "service_name": "size-test-service",
            "description": "Size test",
            "allowed_providers": ["eitaa"],
            "allowed_messenger_account_ids": [messenger_account_id],
            "scopes": ["messages.send"],
        },
        app_session_token=token,
        csrf_token=csrf,
    )
    svc_token = resp.payload["token"]

    # Body larger than 64KB
    large_body = {"text": "A" * 70_000}
    m2m_resp = api.dispatch(
        "POST",
        "/api/v2/m2m/messages/send-text",
        body=large_body,
        authorization=f"Bearer {svc_token}",
        correlation_id="req-12345678-1234-1234-1234-123456789012",
    )
    assert m2m_resp.status == 400
    assert m2m_resp.payload["error"]["error_code"] == "m2m_request_too_large"


def test_admin_api_rejects_non_admin_and_service_tokens(config_file, monkeypatch):
    api, messenger_account_id = _prepared_api(config_file, monkeypatch)
    token, csrf = _setup_admin(api)

    # Register normal user
    normal_reg = api.dispatch(
        "POST",
        "/api/v2/app-auth/register",
        body={
            "username": "normal.user",
            "password": "correct horse battery staple",
            "display_name": "کاربر عادی",
        },
        client_kind="test",
    )
    assert normal_reg.status == 201
    normal_token = _cookie_token(normal_reg)
    normal_csrf = normal_reg.payload["csrf_token"]

    # Normal user cannot create service credentials
    rejected = api.dispatch(
        "POST",
        "/api/v2/service-credentials",
        body={
            "service_name": "unauthorized-service",
            "description": "Test",
            "allowed_providers": ["eitaa"],
            "allowed_messenger_account_ids": [messenger_account_id],
            "scopes": ["messages.send"],
        },
        app_session_token=normal_token,
        csrf_token=normal_csrf,
    )
    assert rejected.status == 403
    assert rejected.payload["error"]["error_code"] == "app_auth_admin_required"

    # Service token cannot access admin API
    svc_create = api.dispatch(
        "POST",
        "/api/v2/service-credentials",
        body={
            "service_name": "legit-service",
            "description": "Test",
            "allowed_providers": ["eitaa"],
            "allowed_messenger_account_ids": [messenger_account_id],
            "scopes": ["messages.send"],
        },
        app_session_token=token,
        csrf_token=csrf,
    )
    svc_token = svc_create.payload["token"]

    svc_forbidden = api.dispatch(
        "GET",
        "/api/v2/service-credentials",
        authorization=f"Bearer {svc_token}",
        correlation_id="req-12345678-1234-1234-1234-123456789012",
    )
    assert svc_forbidden.status == 401
