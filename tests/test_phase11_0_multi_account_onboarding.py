from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import hashlib
import hmac
import json
from pathlib import Path
import sqlite3
from uuid import UUID, uuid4

import eitaa_bridge.application.api as api_module
import pytest
from eitaa_bridge.application.api import APP_USER_SESSION_COOKIE, BridgeApplicationApi
from eitaa_bridge.infrastructure.coordinator import (
    AppPrincipal,
    CoordinatorAppAuth,
    CoordinatorDatabase,
    ProtectedPhone,
    StaticSubjectFingerprinter,
)


class FakePhoneProtector:
    """Deterministic test double; never writes its input anywhere."""

    def __init__(self) -> None:
        self._key = b"phase-11-phone-protector-test-key"
        self.calls = 0

    def protect(self, canonical_e164: str) -> ProtectedPhone:
        self.calls += 1
        encoded = canonical_e164.encode("utf-8")
        return ProtectedPhone(
            ciphertext=b"fake-ciphertext:" + hashlib.sha256(encoded).digest(),
            key_version=1,
            fingerprint=hmac.new(self._key, encoded, hashlib.sha256).hexdigest(),
            display_hint="+••••••••" + canonical_e164[-2:],
        )


def _bootstrap(database: CoordinatorDatabase):
    return database.bootstrap_legacy_account(
        protected_phone=ProtectedPhone(
            ciphertext=b"legacy-protected-phone",
            key_version=1,
            fingerprint="7" * 64,
            display_hint="+••••••••11",
        ),
        display_name="Phase 11 owner",
        backup_name="verified.zip",
        source_manifest_sha256="6" * 64,
        source_file_count=4,
        source_total_bytes=4096,
    )


def _actor(result) -> AppPrincipal:
    return AppPrincipal(
        app_user_id=result.app_user_id,
        display_name="Phase 11 owner",
        global_role="admin",
        session_id=str(uuid4()),
        client_kind="test",
    )


def _enable_features(config_file: Path, account_id: str) -> None:
    payload = json.loads(config_file.read_text(encoding="utf-8"))
    payload["features"] = {
        "multi_session": {
            "enabled": True,
            "legacy_default_messenger_account_id": account_id,
        },
        "app_user_auth": {
            "enabled": True,
            "idle_timeout_minutes": 30,
            "absolute_timeout_hours": 12,
            "max_failed_attempts": 5,
            "lockout_minutes": 15,
        },
    }
    config_file.write_text(json.dumps(payload), encoding="utf-8")


def _cookie_token(response) -> str:
    cookie = response.headers["Set-Cookie"].split(";", 1)[0]
    name, token = cookie.split("=", 1)
    assert name == APP_USER_SESSION_COOKIE
    return token


def test_same_user_can_create_multiple_accounts_and_retry_is_idempotent(tmp_path):
    database = CoordinatorDatabase(tmp_path / "coordinator.sqlite3")
    legacy = _bootstrap(database)
    protector = FakePhoneProtector()
    auth = CoordinatorAppAuth(
        database.path,
        fingerprinter=StaticSubjectFingerprinter(b"phase-11-subject-secret"),
        phone_protector=protector,
    )

    first = auth.onboard_messenger_account(
        _actor(legacy),
        provider="eitaa",
        canonical_phone="+989120000012",
        label="ایتا دوم",
        request_id="a" * 12,
    )
    restarted_auth = CoordinatorAppAuth(
        database.path,
        fingerprinter=StaticSubjectFingerprinter(b"phase-11-subject-secret"),
        phone_protector=protector,
    )
    retry = restarted_auth.onboard_messenger_account(
        _actor(legacy),
        provider="eitaa",
        canonical_phone="+989120000012",
        label="برچسب نادیده در تکرار",
        request_id="b" * 12,
    )

    assert first.created is True
    assert retry.created is False
    assert retry.messenger_account_id == first.messenger_account_id
    assert UUID(first.messenger_account_id).version == 4
    cards = auth.list_messenger_accounts(_actor(legacy))
    assert len(cards) == 2
    assert {card["phone_hint"] for card in cards} == {"+••••••••11", "+••••••••12"}
    with sqlite3.connect(database.path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM phone_accounts").fetchone()[0] == 2
        assert connection.execute("SELECT COUNT(*) FROM messenger_accounts").fetchone()[0] == 2
        assert connection.execute(
            "SELECT COUNT(*) FROM audit_events WHERE action='messenger_account.onboarding.created'"
        ).fetchone()[0] == 1
        assert connection.execute(
            "SELECT COUNT(*) FROM audit_events WHERE action='messenger_account.onboarding.reused'"
        ).fetchone()[0] == 1
    raw_database = database.path.read_bytes()
    assert b"+989120000012" not in raw_database


def test_racing_same_owner_requests_create_exactly_one_account(tmp_path):
    database = CoordinatorDatabase(tmp_path / "coordinator.sqlite3")
    legacy = _bootstrap(database)
    protector = FakePhoneProtector()

    def create(request_id: str):
        auth = CoordinatorAppAuth(
            database.path,
            fingerprinter=StaticSubjectFingerprinter(b"phase-11-race-secret"),
            phone_protector=protector,
        )
        return auth.onboard_messenger_account(
            _actor(legacy),
            provider="eitaa",
            canonical_phone="+989120000013",
            label="Race account",
            request_id=request_id,
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(create, ("c" * 12, "d" * 12)))
    assert {item.messenger_account_id for item in results}.__len__() == 1
    assert sorted(item.created for item in results) == [False, True]
    with sqlite3.connect(database.path) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM messenger_accounts WHERE label='Race account'"
        ).fetchone()[0] == 1


def test_other_user_cannot_claim_identity_and_response_does_not_enumerate(tmp_path):
    database = CoordinatorDatabase(tmp_path / "coordinator.sqlite3")
    legacy = _bootstrap(database)
    protector = FakePhoneProtector()
    auth = CoordinatorAppAuth(
        database.path,
        fingerprinter=StaticSubjectFingerprinter(b"phase-11-isolation-secret"),
        phone_protector=protector,
    )
    auth.onboard_messenger_account(
        _actor(legacy),
        provider="eitaa",
        canonical_phone="+989120000014",
        label=None,
    )
    other_id = str(uuid4())
    now = "2026-08-13T00:00:00.000+00:00"
    with sqlite3.connect(database.path) as connection:
        connection.execute(
            "INSERT INTO app_users(id,display_name,global_role,status,created_at,updated_at) VALUES(?,?,'user','active',?,?)",
            (other_id, "Other user", now, now),
        )
        connection.commit()
    other = AppPrincipal(other_id, "Other user", "user", str(uuid4()), "test")
    try:
        auth.onboard_messenger_account(
            other,
            provider="eitaa",
            canonical_phone="+989120000014",
            label=None,
        )
    except Exception as exc:
        assert getattr(exc, "code", None) == "messenger_account_identity_unavailable"
        assert "exist" not in str(exc).lower()
    else:
        raise AssertionError("cross-owner identity claim was accepted")
    assert auth.list_messenger_accounts(other) == []
    with sqlite3.connect(database.path) as connection:
        rejected = connection.execute(
            "SELECT phone_account_id,messenger_account_id,safe_metadata_json FROM audit_events WHERE action='messenger_account.onboarding.rejected'"
        ).fetchone()
    assert rejected[0] is None and rejected[1] is None
    assert "fingerprint" not in rejected[2]


def test_api_rejects_client_owned_ids_paths_and_unconfigured_provider(config_file, monkeypatch):
    database = CoordinatorDatabase(
        config_file.parent / "data" / "coordinator" / "coordinator.sqlite3"
    )
    legacy = _bootstrap(database)
    _enable_features(config_file, legacy.messenger_account_id)
    protector = FakePhoneProtector()
    auth = CoordinatorAppAuth(
        database.path,
        fingerprinter=StaticSubjectFingerprinter(b"phase-11-api-secret"),
        phone_protector=protector,
    )
    monkeypatch.setattr(api_module, "CoordinatorAppAuth", lambda _path, *, policy: auth)
    api = BridgeApplicationApi(config_file)
    try:
        setup = api.dispatch(
            "POST",
            "/api/v2/app-auth/setup",
            body={
                "username": "phase11.admin",
                "password": "correct horse battery staple",
                "display_name": "Phase 11 admin",
            },
            client_kind="test",
        )
        token = _cookie_token(setup)
        csrf = setup.payload["csrf_token"]
        capabilities = api.dispatch(
            "GET",
            f"/api/v2/messenger-accounts/{legacy.messenger_account_id}/capabilities",
            app_session_token=token,
        )
        assert capabilities.status == 200
        assert capabilities.payload["provider"] == "eitaa"
        capability_states = {
            item["capability"]: item["status"]
            for item in capabilities.payload["capabilities"]
        }
        assert capability_states["contacts.write"] == "supported"
        forbidden = api.dispatch(
            "POST",
            "/api/v2/messenger-accounts",
            body={
                "provider": "eitaa",
                "phone": "+989120000015",
                "messenger_account_id": str(uuid4()),
                "session_path": "C:/private/session.json",
            },
            app_session_token=token,
            csrf_token=csrf,
        )
        assert forbidden.status == 400
        assert forbidden.payload["error"]["error_code"] == "messenger_account_onboarding_fields_rejected"
        unknown = api.dispatch(
            "POST",
            "/api/v2/messenger-accounts",
            body={"provider": "unknown_provider", "phone": "+989120000015"},
            app_session_token=token,
            csrf_token=csrf,
        )
        assert unknown.status == 400
        assert unknown.payload["error"]["error_code"] == "provider_onboarding_unavailable"
        assert protector.calls == 0
    finally:
        api.close()


def test_public_onboarding_rejects_token_identity_before_phone_protection(
    config_file,
    monkeypatch,
):
    database = CoordinatorDatabase(
        config_file.parent / "data" / "coordinator" / "coordinator.sqlite3"
    )
    legacy = _bootstrap(database)
    _enable_features(config_file, legacy.messenger_account_id)
    protector = FakePhoneProtector()
    auth = CoordinatorAppAuth(
        database.path,
        fingerprinter=StaticSubjectFingerprinter(b"phase-11-token-boundary-secret"),
        phone_protector=protector,
    )
    monkeypatch.setattr(api_module, "CoordinatorAppAuth", lambda _path, *, policy: auth)
    api = BridgeApplicationApi(config_file)
    try:
        setup = api.dispatch(
            "POST",
            "/api/v2/app-auth/setup",
            body={
                "username": "phase11.tokenboundary",
                "password": "correct horse battery staple",
                "display_name": "Phase 11 token boundary",
            },
            client_kind="test",
        )
        response = api.dispatch(
            "POST",
            "/api/v2/messenger-accounts",
            body={
                "provider": "eitaa",
                "token": "7" * 6 + ":" + "x" * 24,
                "label": "unsupported identity",
            },
            app_session_token=_cookie_token(setup),
            csrf_token=setup.payload["csrf_token"],
        )
        if response.status != 400 or response.payload["error"]["error_code"] != (
            "messenger_account_onboarding_fields_rejected"
        ):
            pytest.fail(
                "Public onboarding accepted a token-shaped identity field.",
                pytrace=False,
            )
        if protector.calls:
            pytest.fail(
                "Rejected token-shaped identity reached phone protection.",
                pytrace=False,
            )
    finally:
        api.close()


def test_api_onboarding_returns_safe_card_and_runtime_log_has_no_phone(config_file, monkeypatch):
    database = CoordinatorDatabase(
        config_file.parent / "data" / "coordinator" / "coordinator.sqlite3"
    )
    legacy = _bootstrap(database)
    _enable_features(config_file, legacy.messenger_account_id)
    protector = FakePhoneProtector()
    auth = CoordinatorAppAuth(
        database.path,
        fingerprinter=StaticSubjectFingerprinter(b"phase-11-api-log-secret"),
        phone_protector=protector,
    )
    monkeypatch.setattr(api_module, "CoordinatorAppAuth", lambda _path, *, policy: auth)
    api = BridgeApplicationApi(config_file)
    phone = "+989120000016"
    try:
        setup = api.dispatch(
            "POST",
            "/api/v2/app-auth/setup",
            body={
                "username": "phase11.logadmin",
                "password": "correct horse battery staple",
                "display_name": "Phase 11 log admin",
            },
            client_kind="test",
        )
        token = _cookie_token(setup)
        created = api.dispatch(
            "POST",
            "/api/v2/messenger-accounts",
            body={"provider": "eitaa", "phone": phone, "label": "حساب کاری"},
            app_session_token=token,
            csrf_token=setup.payload["csrf_token"],
            correlation_id="e" * 12,
        )
        assert created.status == 201
        assert created.payload["account"]["phone_hint"] == "+••••••••16"
        assert created.payload["account"]["auth_state"] == "absent"
    finally:
        api.close()
    log_text = (config_file.parent / "runtime" / "logs" / "application.jsonl").read_text(
        encoding="utf-8"
    )
    assert phone not in log_text
    assert "messenger_account_onboarding_succeeded" in log_text
    assert "ciphertext" not in log_text
