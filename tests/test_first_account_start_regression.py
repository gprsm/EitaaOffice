"""Regression F-068: first onboarding must survive restart and allow Start.

On the RC5 delivery the first admin creates an Eitaa account that stays in
``created/stopped`` until an explicit worker Start.  Two contracts broke on
the customer machine and must stay fixed:

1. ``worker/start`` on a ``created`` account must not fail with
   ``eitaa_runtime_account_not_runnable``; the explicit Start is exactly the
   operation that promotes the account to active/running.
2. A restart with only created/paused accounts must boot the API like a
   clean install instead of dying with
   ``multi_session_legacy_default_required``.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from eitaa_bridge.application.api import BridgeApplicationApi
from eitaa_bridge.application.account_runtime import EitaaRuntimeRegistry
from eitaa_bridge.errors import EitaaRuntimeError
from eitaa_bridge.infrastructure.coordinator.app_auth import CoordinatorAppAuth
from eitaa_bridge.infrastructure.coordinator.store import CoordinatorDatabase
from eitaa_bridge.interfaces.http_api import BridgeApiHttpServer


def _write_rc5_config(config_file: Path) -> None:
    payload = json.loads(config_file.read_text(encoding="utf-8"))
    payload["deployment"] = {
        "schema_version": 1,
        "mode": "desktop_loopback",
        "bind": {"host": "127.0.0.1", "port": 8765},
        "allowed_hosts": ["127.0.0.1:8765", "localhost:8765"],
        "allowed_origins": ["http://127.0.0.1:8765", "http://localhost:8765"],
        "allowed_private_client_cidrs": ["127.0.0.0/8", "::1/128"],
        "cleartext_http_risk_acknowledgement": None,
        "private_lan_only_acknowledgement": None,
        "bootstrap_admin_loopback_only": True,
        "same_origin_only": True,
        "remote_messenger_auth": {
            "enabled": False,
            "cleartext_http_risk_acknowledgement": None,
        },
    }
    payload["features"] = {
        "app_user_auth": {
            "enabled": True,
            "self_registration_enabled": True,
            "idle_timeout_minutes": 525600,
            "absolute_timeout_hours": 8760,
            "max_failed_attempts": 5,
            "lockout_minutes": 15,
        },
        "multi_session": {
            "enabled": True,
            "legacy_default_messenger_account_id": None,
        },
        "worker_process": {
            "schema_version": 1,
            "enabled": True,
            "startup_timeout_seconds": 15,
            "request_timeout_seconds": 60,
            "heartbeat_interval_seconds": 5,
            "heartbeat_timeout_seconds": 15,
            "heartbeat_failure_threshold": 3,
            "restart_window_seconds": 300,
            "max_restarts": 3,
            "backoff_initial_seconds": 2,
            "backoff_max_seconds": 60,
            "quarantine_seconds": 300,
        },
    }
    config_file.write_text(json.dumps(payload), encoding="utf-8")


def _api(config_file: Path) -> BridgeApplicationApi:
    api = BridgeApplicationApi(config_file)
    assert api.config.features.multi_session.enabled
    assert api.config.features.worker_process.enabled
    return api


def _register_admin_and_account(
    config_file: Path,
    *,
    phone: str = "+98911000000",
) -> tuple[BridgeApplicationApi, str, str, str, str]:
    """Return (api, app_user_id, token, csrf, messenger_account_id)."""

    api = _api(config_file)
    dispatch = api.dispatch

    setup = dispatch(
        "POST",
        "/api/v2/app-auth/setup",
        body={
            "username": "admin",
            "password": "AdminPass123!",
            "display_name": "F068",
        },
        client_kind="test",
    )
    assert setup.status in (200, 201), setup.payload
    app_user_id = setup.payload["principal"]["app_user_id"]
    csrf = setup.payload["csrf_token"]
    token = setup.headers["Set-Cookie"].split(";", 1)[0].split("=", 1)[1]

    created = dispatch(
        "POST",
        "/api/v2/messenger-accounts",
        body={"provider": "eitaa", "phone": phone, "label": "F068 test"},
        app_session_token=token,
        csrf_token=csrf,
    )
    assert created.status == 201, created.payload
    account = created.payload["account"]
    assert account["lifecycle_state"] == "created"
    assert account["desired_worker_state"] == "stopped"
    account_id = account["messenger_account_id"]
    return api, app_user_id, token, csrf, account_id


def test_worker_start_on_created_account_is_startable_not_rejected(
    config_file: Path,
) -> None:
    _write_rc5_config(config_file)
    api, _app_user_id, _token, _csrf, account_id = _register_admin_and_account(config_file)

    # The UI button posts exactly this route; on the delivered RC5 build it
    # returned eitaa_runtime_account_not_runnable for a created account.
    response = api.dispatch(
        "POST",
        f"/api/v2/messenger-accounts/{account_id}/worker/start",
        body={},
        app_session_token=_token,
        csrf_token=_csrf,
    )
    # Without a spawned worker process the start may legitimately fail for
    # infrastructure reasons, but never with the not-runnable lifecycle code.
    if response.status != 200:
        error = response.payload.get("error", {})
        assert error.get("error_code") != "eitaa_runtime_account_not_runnable", response.payload
    else:
        account = response.payload["account"]
        assert account["lifecycle_state"] == "active"
        assert account["desired_worker_state"] == "running"

    api.close()


def test_registry_start_account_accepts_created_account(config_file: Path) -> None:
    _write_rc5_config(config_file)
    api, app_user_id, _token, _csrf, account_id = _register_admin_and_account(config_file)
    try:
        registry: EitaaRuntimeRegistry = api._runtime_registry
        # RED before the fix: eitaa_runtime_account_not_runnable.
        try:
            runtime, worker = registry.start_account(
                account_id,
                actor_app_user_id=app_user_id,
                actor_global_role="admin",
                request_id=None,
            )
            # The child worker spawns for real in this environment; whatever
            # happened, the lifecycle transition must have been recorded.
            record = registry.coordinator.messenger_account_runtime(account_id)
            assert record.lifecycle_state == "active"
            assert record.desired_worker_state == "running"
        except EitaaRuntimeError as exc:
            assert exc.code != "eitaa_runtime_account_not_runnable", exc.safe_context
    finally:
        api.close()


def test_api_boot_with_only_created_account_survives_restart(config_file: Path) -> None:
    _write_rc5_config(config_file)
    api, _app_user_id, _token, _csrf, account_id = _register_admin_and_account(config_file)
    # Simulate the user closing the app: the DB now has one created account
    # and no active one.
    api.close()

    # RED before the fix: multi_session_legacy_default_required killed boot.
    restarted = BridgeApplicationApi(config_file)
    try:
        assert restarted.app_user_auth_enabled
        coordinator = restarted._runtime_registry.coordinator
        record = coordinator.messenger_account_runtime(account_id)
        assert record.lifecycle_state == "created"
    finally:
        restarted.close()


def test_api_boot_with_only_paused_account_survives_restart(config_file: Path) -> None:
    _write_rc5_config(config_file)
    api, _app_user_id, _token, _csrf, account_id = _register_admin_and_account(config_file)
    coordinator: CoordinatorDatabase = api._runtime_registry.coordinator
    # A stopped worker pauses the account; restart in that state must also boot.
    coordinator.complete_worker_stop(
        account_id,
        worker_instance_id=None,
        reason_code="worker_stop_completed",
        pause_account=True,
    )
    api.close()

    restarted = BridgeApplicationApi(config_file)
    try:
        coordinator = restarted._runtime_registry.coordinator
        record = coordinator.messenger_account_runtime(account_id)
        assert record.lifecycle_state == "paused"
    finally:
        restarted.close()


def test_disabled_account_start_still_fails_closed(config_file: Path) -> None:
    _write_rc5_config(config_file)
    api, _app_user_id, _token, _csrf, account_id = _register_admin_and_account(config_file)
    try:
        coordinator: CoordinatorDatabase = api._runtime_registry.coordinator
        with coordinator._connect() as connection:
            connection.execute(
                "UPDATE messenger_accounts SET lifecycle_state='disabled' WHERE id=?",
                (account_id,),
            )
            connection.commit()
        registry: EitaaRuntimeRegistry = api._runtime_registry
        try:
            registry.start_account(
                account_id,
                actor_app_user_id=_app_user_id,
                actor_global_role="admin",
                request_id=None,
            )
            raise AssertionError("disabled account must not start")
        except EitaaRuntimeError as exc:
            assert exc.code in {
                "eitaa_runtime_account_not_runnable",
                "worker_lifecycle_blocked",
            }
    finally:
        api.close()


def test_api_boot_after_successful_start_survives_restart(config_file: Path) -> None:
    """F-068 continuation: boot after the account became active must not die.

    The registry used to crash with multi_session_legacy_default_required
    because no legacy default account is configured on a clean install even
    after the first explicit Start succeeded.
    """

    _write_rc5_config(config_file)
    api, app_user_id, _token, _csrf, account_id = _register_admin_and_account(config_file)
    try:
        registry: EitaaRuntimeRegistry = api._runtime_registry
        runtime, _worker = registry.start_account(
            account_id,
            actor_app_user_id=app_user_id,
            actor_global_role="admin",
            request_id=None,
        )
        record = registry.coordinator.messenger_account_runtime(account_id)
        assert record.lifecycle_state == "active"
        assert record.desired_worker_state == "running"
    finally:
        api.close()

    # RED before the continuation fix: multi_session_legacy_default_required.
    restarted = BridgeApplicationApi(config_file)
    try:
        coordinator = restarted._runtime_registry.coordinator
        record = coordinator.messenger_account_runtime(account_id)
        assert record.lifecycle_state == "active"
        assert record.desired_worker_state == "running"
    finally:
        restarted.close()
