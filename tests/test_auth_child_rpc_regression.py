"""E2E regression: v1 auth routes must work over the process Child RPC.

Reproduces the delivery failure where a clean install activated the
worker-process feature, the first worker Start succeeded, and the very
next v1 auth route failed with
"This API route has not been migrated to a DTO-based Child RPC."
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from eitaa_bridge.application.api import BridgeApplicationApi
from eitaa_bridge.infrastructure.coordinator import (
    CoordinatorDatabase,
    WindowsDpapiPhoneProtector,
)
from eitaa_bridge.infrastructure.config import BridgeConfigLoader


def _write_config(root: Path, default_account_id: str) -> Path:
    payload = {
        "schema_version": 1,
        "default_site_key": "test-site",
        "bridge": {
            "diagnostics_root": "diagnostics/bridge",
            "diagnostics_enabled": False,
        },
        "features": {
            "multi_session": {
                "enabled": True,
                "legacy_default_messenger_account_id": default_account_id,
            },
            "worker_process": {
                "schema_version": 1,
                "enabled": True,
                "startup_timeout_seconds": 15,
                "request_timeout_seconds": 30,
                "heartbeat_interval_seconds": 5,
                "heartbeat_timeout_seconds": 15,
                "heartbeat_failure_threshold": 3,
                "restart_window_seconds": 300,
                "max_restarts": 3,
                "backoff_initial_seconds": 2,
                "backoff_max_seconds": 60,
                "quarantine_seconds": 300,
            },
            "app_user_auth": {"enabled": False},
        },
        "core": {
            "session_file": ".eitaa_session.json",
            "database_file": "data/eitaa_messages.sqlite3",
            "media_directory": "data/media",
            "diagnostics_root": "diagnostics/core",
            "diagnostics_enabled": False,
            "timeout_seconds": 23,
        },
        "wordpress_sites": [
            {
                "site_key": "test-site",
                "base_url": "https://example.test",
                "default_status": "draft",
                "default_category_id": None,
                "verify_tls": True,
                "username_env": "TEST_WP_USER",
                "application_password_env": "TEST_WP_PASSWORD",
            }
        ],
    }
    path = root / "bridge.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


@pytest.fixture
def process_api(tmp_path: Path):
    coordinator_root = tmp_path / "data" / "coordinator"
    database = CoordinatorDatabase(coordinator_root / "coordinator.sqlite3")
    protector = WindowsDpapiPhoneProtector(coordinator_root / "identity.key.dpapi")
    account = database.bootstrap_legacy_account(
        protected_phone=protector.protect("+989120000001"),
        display_name="Regression Admin",
        backup_name="verified-x.zip",
        source_manifest_sha256="a" * 64,
        source_file_count=1,
        source_total_bytes=1,
    )
    with sqlite3.connect(database.path) as connection:
        connection.execute(
            """
            UPDATE messenger_accounts
            SET lifecycle_state='active', desired_worker_state='running'
            WHERE id=?
            """,
            (account.messenger_account_id,),
        )
    config_path = _write_config(tmp_path, account.messenger_account_id)
    BridgeConfigLoader.load(config_path)
    api = BridgeApplicationApi(config_path)
    try:
        yield api, account
    finally:
        api.close()


def test_auth_status_serves_through_child_process(process_api):
    api, account = process_api
    response = api.dispatch("GET", "/api/v1/auth/status")
    assert response.status == 200
    body = response.payload
    assert body["ok"] is True
    assert body["authenticated"] is False
    assert body["session_present"] is False
    assert body["fresh_login_available"] is True
    assert body["messenger_account_id"] == account.messenger_account_id


def test_request_code_executes_in_child_not_gate(process_api):
    api, _ = process_api
    response = api.dispatch(
        "POST",
        "/api/v1/auth/request-code",
        body={"phone": ""},
    )
    payload = response.payload
    # The regression: the gate error must never appear again on auth routes.
    assert payload.get("error", {}).get("error_code") != (
        "eitaa_process_operation_ipc_required"
    )
    assert response.status in {200, 400}
    if response.status == 200:
        assert payload["step"] == "code"
        assert payload["challenge"]["challenge_id"]


def test_submit_code_routes_to_child_challenge_flow(process_api):
    api, _ = process_api
    response = api.dispatch(
        "POST",
        "/api/v1/auth/submit-code",
        body={
            "challenge_id": "00000000-0000-4000-8000-000000000000",
            "code": "12345",
        },
    )
    assert response.status in {200, 400}
    assert response.payload.get("error", {}).get("error_code") != (
        "eitaa_process_operation_ipc_required"
    )


def test_submit_password_routes_to_child_challenge_flow(process_api):
    api, _ = process_api
    response = api.dispatch(
        "POST",
        "/api/v1/auth/submit-password",
        body={
            "challenge_id": "00000000-0000-4000-8000-000000000000",
            "password": "x",
        },
    )
    assert response.status in {200, 400}
    assert response.payload.get("error", {}).get("error_code") != (
        "eitaa_process_operation_ipc_required"
    )


def test_reset_local_session_confirmed(process_api):
    api, _ = process_api
    response = api.dispatch(
        "POST",
        "/api/v1/auth/reset-local-session",
        body={"confirm": True},
    )
    assert response.status == 200
    assert response.payload["login_ready"] is True


def test_logout_completes_through_child(process_api):
    api, _ = process_api
    response = api.dispatch("POST", "/api/v1/auth/logout")
    assert response.status == 200
    assert response.payload["ok"] is True


def test_unmigrated_v1_routes_remain_gated(process_api):
    api, _ = process_api
    response = api.dispatch("GET", "/api/v1/capabilities")
    assert response.status == 400
    assert response.payload["error"]["error_code"] == (
        "eitaa_process_operation_ipc_required"
    )
