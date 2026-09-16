"""End-to-end integration tests for Bale provider operations via BridgeApplicationApi."""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
import hashlib
import hmac
import json
from pathlib import Path
import sqlite3
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

import eitaa_bridge.application.api as api_module
from eitaa_bridge.application.api import APP_USER_SESSION_COOKIE, BridgeApplicationApi
from eitaa_bridge.application.bale_provider_adapter import BaleProviderApplicationAdapter
from eitaa_bridge.infrastructure.coordinator import (
    AppPrincipal,
    CoordinatorAppAuth,
    CoordinatorDatabase,
    ProtectedPhone,
    StaticSubjectFingerprinter,
)
from eitaa_bridge.application.bale_client.api import BaleApiError
from eitaa_bridge.providers.contracts import (
    ProviderCapability,
    ProviderDialogPage,
    ProviderMessagePage,
    ProviderPeerReference,
    ProviderSendStatus,
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


@pytest.fixture
def setup_bale_app(config_file: Path, monkeypatch: pytest.MonkeyPatch):
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

    setup = api.dispatch(
        "POST",
        "/api/v2/app-auth/setup",
        body={
            "username": "bale.tester",
            "password": "correct horse battery staple",
            "display_name": "Bale Tester",
        },
        client_kind="test",
    )
    assert setup.status == 201
    token = _cookie_token(setup)
    csrf = setup.payload["csrf_token"]

    created = api.dispatch(
        "POST",
        "/api/v2/messenger-accounts",
        body={"provider": "bale", "phone": "+989123456780", "label": "حساب بله تستی"},
        app_session_token=token,
        csrf_token=csrf,
    )
    assert created.status == 201
    bale_account_id = created.payload["account"]["messenger_account_id"]

    return api, token, csrf, bale_account_id


def test_bale_contacts_query_and_upsert(setup_bale_app) -> None:
    api, token, csrf, bale_account_id = setup_bale_app

    mock_client = MagicMock()
    mock_client.list_contacts = AsyncMock(
        return_value=[
            {
                "peer": {"id": 1001, "type": 1},
                "name": "محسن دوست",
                "username": "mohsen_bale",
                "is_bot": False,
                "access_hash": 12345,
            },
            {
                "peer": {"id": 1002, "type": 1},
                "name": "همکار",
                "username": None,
                "is_bot": False,
                "access_hash": 67890,
            },
        ]
    )
    mock_client.add_contact_by_phone = AsyncMock(
        return_value={
            "phone": 989120000099,
            "matched": True,
            "users": [{"id": 1003, "name": "مخاطب جدید"}],
        }
    )

    with patch.object(BaleProviderApplicationAdapter, "_ensure_api", return_value=mock_client):
        # 1. Query contacts
        response = api.dispatch(
            "POST",
            f"/api/v2/messenger-accounts/{bale_account_id}/contacts/query",
            body={"limit": 20},
            app_session_token=token,
            csrf_token=csrf,
        )
        assert response.status == 200
        payload = response.payload
        assert payload["ok"] is True
        assert payload["provider"] == "bale"
        contacts = payload["contacts"]
        assert len(contacts) == 2
        assert contacts[0]["contact_reference"] == "1001"
        assert contacts[0]["display_name"] == "محسن دوست"
        assert contacts[0]["identity_hint"] == "mohsen_bale"
        assert contacts[1]["display_name"] == "همکار"

        # 2. Upsert contact
        upsert_res = api.dispatch(
            "POST",
            f"/api/v2/messenger-accounts/{bale_account_id}/contacts/upsert",
            body={
                "identity": "+989120000099",
                "display_name": "مخاطب جدید",
                "idempotency_key": "test-bale-upsert-01",
                "confirm": True,
            },
            app_session_token=token,
            csrf_token=csrf,
        )
        assert upsert_res.status == 201
        assert upsert_res.payload["ok"] is True
        assert upsert_res.payload["contact_reference"] == "1003"
        assert upsert_res.payload["created"] is True


def test_bale_dialogs_and_history_query(setup_bale_app) -> None:
    api, token, csrf, bale_account_id = setup_bale_app

    mock_client = MagicMock()
    mock_client.list_dialogs = AsyncMock(
        return_value=[
            {
                "peer": {"id": 2001, "type": 1},
                "title": "دوست بله",
                "unread_count": 0,
                "last_message": {
                    "id": 5001,
                    "date": 1720000000,
                    "text": None,  # F-073 null text test
                },
            },
            {
                "peer": {"id": 2002, "type": 2},
                "title": "گروه توسعه",
                "unread_count": 5,
                "last_message": {
                    "id": 5002,
                    "date": 1720001000,
                    "text": "سلام تیم",
                },
            },
        ]
    )
    mock_client.read_history = AsyncMock(
        return_value=[
            {
                "id": 5001,
                "date": 1720000000,
                "text": "اولین پیام تاریخچه",
                "sender_id": 2001,
                "out": False,
            },
            {
                "id": 5002,
                "date": 1720001000,
                "text": "پاسخ من",
                "sender_id": 9999,
                "out": True,
            },
        ]
    )

    with patch.object(BaleProviderApplicationAdapter, "_ensure_api", return_value=mock_client):
        # 1. Dialogs query
        d_res = api.dispatch(
            "POST",
            f"/api/v2/messenger-accounts/{bale_account_id}/dialogs/query",
            body={"limit": 50},
            app_session_token=token,
            csrf_token=csrf,
        )
        assert d_res.status == 200
        dialogs = d_res.payload["dialogs"]
        assert len(dialogs) == 2
        assert dialogs[0]["peer_reference"] == "2001"
        assert dialogs[0]["peer_kind"] == "private"
        assert dialogs[0]["title"] == "دوست بله"
        assert dialogs[0]["unread_count"] == 0
        assert dialogs[1]["peer_reference"] == "2002"
        assert dialogs[1]["peer_kind"] == "group"
        assert dialogs[1]["unread_count"] == 5

        # 2. History query
        h_res = api.dispatch(
            "POST",
            f"/api/v2/messenger-accounts/{bale_account_id}/history/query",
            body={
                "peer_reference": "2001",
                "peer_kind": "private",
                "limit": 20,
            },
            app_session_token=token,
            csrf_token=csrf,
        )
        assert h_res.status == 200
        messages = h_res.payload["messages"]
        assert len(messages) == 2
        assert messages[0]["message_reference"] == "5001"
        assert messages[0]["text"] == "اولین پیام تاریخچه"
        assert messages[0]["sender_reference"] == "2001"
        assert messages[1]["message_reference"] == "5002"
        assert messages[1]["sender_reference"] == "9999"


def test_bale_send_text_success_and_access_denied(setup_bale_app) -> None:
    api, token, csrf, bale_account_id = setup_bale_app

    mock_client = MagicMock()
    mock_client.send_text = AsyncMock(
        return_value={"id": 7001, "date": 1720002000}
    )

    with patch.object(BaleProviderApplicationAdapter, "_ensure_api", return_value=mock_client):
        # 1. Successful send
        send_res = api.dispatch(
            "POST",
            f"/api/v2/messenger-accounts/{bale_account_id}/messages/send-text",
            body={
                "peer_reference": "2001",
                "peer_kind": "private",
                "text": "پیام از Bridge به بله",
                "idempotency_key": "test-bale-send-01",
                "confirm": True,
            },
            app_session_token=token,
            csrf_token=csrf,
        )
        assert send_res.status == 201
        assert send_res.payload["ok"] is True
        assert send_res.payload["status"] == "succeeded"
        assert send_res.payload["message_reference"] == "7001"

    # 2. Access denied scenario
    mock_denied_client = MagicMock()
    mock_denied_client.send_text = AsyncMock(
        side_effect=BaleApiError("Access denied", code="bale_access_denied")
    )
    with patch.object(BaleProviderApplicationAdapter, "_ensure_api", return_value=mock_denied_client):
        denied_res = api.dispatch(
            "POST",
            f"/api/v2/messenger-accounts/{bale_account_id}/messages/send-text",
            body={
                "peer_reference": "9999",
                "peer_kind": "channel",
                "text": "پیام به کانال بدون دسترسی",
                "idempotency_key": "test-bale-send-02",
                "confirm": True,
            },
            app_session_token=token,
            csrf_token=csrf,
        )
        assert denied_res.status == 201
        assert denied_res.payload["status"] == "uncertain"
        assert denied_res.payload["safe_reason_code"] == "bale_access_denied"
