"""Integration tests for Bale account onboarding and lifecycle management."""

from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path
import sqlite3
from uuid import uuid4

import pytest

import eitaa_bridge.application.api as api_module
from eitaa_bridge.application.api import APP_USER_SESSION_COOKIE, BridgeApplicationApi
from eitaa_bridge.infrastructure.config import BridgeConfigLoader
from eitaa_bridge.infrastructure.coordinator import (
    AppPrincipal,
    CoordinatorAppAuth,
    CoordinatorDatabase,
    ProtectedPhone,
    StaticSubjectFingerprinter,
)
from eitaa_bridge.providers.registry import default_provider_registry


class FakePhoneProtector:
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
            ciphertext=b"phase11-protected",
            key_version=1,
            fingerprint="9" * 64,
            display_hint="+masked81",
        ),
        display_name="Admin User",
        backup_name="verified.zip",
        source_manifest_sha256="6" * 64,
        source_file_count=4,
        source_total_bytes=4096,
    )


def _actor(result) -> AppPrincipal:
    return AppPrincipal(
        app_user_id=result.app_user_id,
        display_name="Admin User",
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


def test_bale_account_can_be_onboarded_in_coordinator(tmp_path: Path) -> None:
    database = CoordinatorDatabase(tmp_path / "coordinator.sqlite3")
    legacy = _bootstrap(database)
    protector = FakePhoneProtector()
    auth = CoordinatorAppAuth(
        database.path,
        fingerprinter=StaticSubjectFingerprinter(b"phase-11-subject-secret"),
        phone_protector=protector,
    )

    registry = default_provider_registry()
    database.reconcile_provider_registrations(registry.persistence_catalog())
    result = auth.onboard_messenger_account(
        _actor(legacy),
        provider="bale",
        canonical_phone="+989123456789",
        label="حساب شخصی بله",
        request_id="test-req-1",
    )

    assert result.provider == "bale"
    assert result.lifecycle_state == "created"
    assert result.auth_state == "absent"
    assert result.created is True
    assert result.phone_account_created is True
    assert result.membership_created is True

    with sqlite3.connect(database.path) as connection:
        row = connection.execute(
            "SELECT label, lifecycle_state, desired_worker_state FROM messenger_accounts WHERE id=?",
            (result.messenger_account_id,),
        ).fetchone()
        assert row is not None
        assert row[0] == "حساب شخصی بله"
        assert row[1] == "created"
        assert row[2] == "stopped"

    # Idempotent re-onboarding
    retry = auth.onboard_messenger_account(
        _actor(legacy),
        provider="bale",
        canonical_phone="+989123456789",
        label="برچسب دیگر",
        request_id="test-req-2",
    )
    assert retry.created is False
    assert retry.messenger_account_id == result.messenger_account_id

    # Verify reconciliation with provider registry
    assert registry.registration("bale").manifest.configured is True
    assert registry.registration("bale").manifest.onboarding_enabled is True


def test_bale_account_api_onboarding_and_capabilities(config_file: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    database = CoordinatorDatabase(
        config_file.parent / "data" / "coordinator" / "coordinator.sqlite3"
    )
    legacy = _bootstrap(database)
    _enable_features(config_file, legacy.messenger_account_id)
    protector = FakePhoneProtector()
    auth = CoordinatorAppAuth(
        database.path,
        fingerprinter=StaticSubjectFingerprinter(b"phase-11-api-bale-secret"),
        phone_protector=protector,
    )
    monkeypatch.setattr(api_module, "CoordinatorAppAuth", lambda _path, *, policy: auth)
    api = BridgeApplicationApi(config_file)
    phone = "+989129876543"

    try:
        # 1. Setup app user
        setup = api.dispatch(
            "POST",
            "/api/v2/app-auth/setup",
            body={
                "username": "bale.admin",
                "password": "correct horse battery staple",
                "display_name": "Bale Admin User",
            },
            client_kind="test",
        )
        assert setup.status == 201
        token = _cookie_token(setup)
        csrf = setup.payload["csrf_token"]

        # 2. Onboard Bale account
        created = api.dispatch(
            "POST",
            "/api/v2/messenger-accounts",
            body={"provider": "bale", "phone": phone, "label": "حساب بله سازمانی"},
            app_session_token=token,
            csrf_token=csrf,
            correlation_id="c" * 12,
        )
        assert created.status == 201
        bale_account = created.payload["account"]
        assert bale_account["provider"] == "bale"
        assert bale_account["label"] == "حساب بله سازمانی"
        assert bale_account["phone_hint"] == "+••••••••43"
        assert bale_account["auth_state"] == "absent"
        assert bale_account["lifecycle_state"] == "created"
        bale_account_id = bale_account["messenger_account_id"]

        # 3. List accounts should now contain Bale account
        listed = api.dispatch(
            "GET",
            "/api/v2/messenger-accounts",
            app_session_token=token,
        )
        assert listed.status == 200
        account_ids = [acc["messenger_account_id"] for acc in listed.payload["accounts"]]
        assert bale_account_id in account_ids

        # 4. Check capabilities for Bale account
        caps = api.dispatch(
            "GET",
            f"/api/v2/messenger-accounts/{bale_account_id}/capabilities",
            app_session_token=token,
        )
        assert caps.status == 200
        cap_map = {item["capability"]: item["status"] for item in caps.payload["capabilities"]}
        assert cap_map["dialogs.read"] == "supported"
        assert cap_map["history.read"] == "supported"
        assert cap_map["messages.send"] == "supported"
        assert cap_map["media.read"] == "supported"
        assert cap_map["contacts.read"] == "supported"
        assert cap_map["contacts.write"] == "supported"

        # 5. Idempotent re-onboarding returns 200 and existing account
        reused = api.dispatch(
            "POST",
            "/api/v2/messenger-accounts",
            body={"provider": "bale", "phone": phone, "label": "حساب بله سازمانی"},
            app_session_token=token,
            csrf_token=csrf,
        )
        assert reused.status == 200
        assert reused.payload["account"]["messenger_account_id"] == bale_account_id
    finally:
        api.close()
