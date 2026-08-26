from __future__ import annotations

import json
from pathlib import Path

import eitaa_bridge.application.api as api_module
from eitaa_bridge.application.api import APP_USER_SESSION_COOKIE, BridgeApplicationApi
from eitaa_bridge.infrastructure.coordinator import (
    CoordinatorAppAuth,
    CoordinatorDatabase,
    ProtectedPhone,
    StaticSubjectFingerprinter,
)


def _enable(config_file: Path) -> None:
    payload = json.loads(config_file.read_text(encoding="utf-8"))
    payload["features"] = {
        "multi_session": {"enabled": False},
        "app_user_auth": {
            "enabled": True,
            "idle_timeout_minutes": 30,
            "absolute_timeout_hours": 12,
            "max_failed_attempts": 5,
            "lockout_minutes": 15,
        },
    }
    config_file.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _token(response) -> str:
    cookie = response.headers["Set-Cookie"].split(";", 1)[0]
    name, token = cookie.split("=", 1)
    assert name == APP_USER_SESSION_COOKIE
    return token


def _api(config_file: Path, monkeypatch) -> BridgeApplicationApi:
    _enable(config_file)
    database_path = config_file.parent / "data" / "coordinator" / "coordinator.sqlite3"
    CoordinatorDatabase(database_path).bootstrap_legacy_account(
        protected_phone=ProtectedPhone(
            ciphertext=b"phase9-protected-phone",
            key_version=1,
            fingerprint="9" * 64,
            display_hint="+••••••••67",
        ),
        display_name="Initial administrator",
        backup_name="verified.zip",
        source_manifest_sha256="8" * 64,
        source_file_count=1,
        source_total_bytes=1,
    )
    auth = CoordinatorAppAuth(
        database_path,
        fingerprinter=StaticSubjectFingerprinter(b"phase9-subject-secret"),
    )
    monkeypatch.setattr(
        api_module,
        "CoordinatorAppAuth",
        lambda _database_path, *, policy: auth,
    )
    return BridgeApplicationApi(config_file)


def test_admin_manages_masked_phone_memberships_sessions_and_shared_wordpress(
    config_file, monkeypatch
):
    monkeypatch.setenv("TEST_WP_USERNAME", "editor")
    monkeypatch.setenv("TEST_WP_APP_PASSWORD", "server-only-password")
    api = _api(config_file, monkeypatch)
    try:
        setup = api.dispatch(
            "POST",
            "/api/v2/app-auth/setup",
            body={
                "username": "phase9.admin",
                "password": "correct horse battery staple",
                "display_name": "مدیر فاز نه",
            },
            client_kind="test",
        )
        admin_token = _token(setup)
        admin_csrf = setup.payload["csrf_token"]
        created = api.dispatch(
            "POST",
            "/api/v2/app-users",
            app_session_token=admin_token,
            csrf_token=admin_csrf,
            body={
                "username": "phase9.viewer",
                "password": "a safe viewer password",
                "display_name": "مشاهده‌گر فاز نه",
                "global_role": "user",
            },
        )
        assert created.status == 201
        viewer_id = created.payload["user"]["app_user_id"]

        phone_accounts = api.dispatch(
            "GET", "/api/v2/phone-accounts", app_session_token=admin_token
        )
        assert phone_accounts.status == 200
        card = phone_accounts.payload["phone_accounts"][0]
        phone_id = card["phone_account_id"]
        assert card["phone_hint"] == "+••••••••67"
        encoded = json.dumps(phone_accounts.payload, ensure_ascii=False)
        assert "phase9-protected-phone" not in encoded
        assert "phone_ciphertext" not in encoded
        assert "phone_fingerprint" not in encoded

        granted = api.dispatch(
            "POST",
            f"/api/v2/phone-accounts/{phone_id}/memberships",
            app_session_token=admin_token,
            csrf_token=admin_csrf,
            body={"app_user_id": viewer_id, "role": "viewer", "status": "active"},
        )
        assert granted.status == 200
        assert granted.payload["membership"]["role"] == "viewer"

        integrations = api.dispatch(
            "GET", "/api/v2/app-integrations", app_session_token=admin_token
        )
        assert integrations.status == 200
        assert integrations.payload["can_manage"] is True
        wordpress = integrations.payload["integrations"][0]
        assert set(wordpress) == {
            "integration_id",
            "integration_type",
            "integration_key",
            "display_name",
            "status",
        }
        assert "password" not in json.dumps(wordpress).lower()

        disabled = api.dispatch(
            "POST",
            f"/api/v2/app-integrations/{wordpress['integration_id']}/update",
            app_session_token=admin_token,
            csrf_token=admin_csrf,
            body={"status": "disabled"},
        )
        assert disabled.status == 200
        assert disabled.payload["integration"]["status"] == "disabled"

        logout = api.dispatch(
            "POST",
            "/api/v2/app-auth/logout",
            app_session_token=admin_token,
            csrf_token=admin_csrf,
        )
        assert logout.status == 200
        viewer_login = api.dispatch(
            "POST",
            "/api/v2/app-auth/login",
            body={"username": "phase9.viewer", "password": "a safe viewer password"},
            client_kind="test",
        )
        viewer_token = _token(viewer_login)
        viewer_csrf = viewer_login.payload["csrf_token"]
        accounts = api.dispatch(
            "GET", "/api/v2/messenger-accounts", app_session_token=viewer_token
        )
        assert len(accounts.payload["accounts"]) == 1
        assert accounts.payload["accounts"][0]["permissions"]["view"] is True
        assert accounts.payload["accounts"][0]["permissions"]["operate"] is False
        hidden_integration = api.dispatch(
            "GET", "/api/v2/app-integrations", app_session_token=viewer_token
        )
        assert hidden_integration.payload["integrations"] == []

        viewer_logout = api.dispatch(
            "POST",
            "/api/v2/app-auth/logout",
            app_session_token=viewer_token,
            csrf_token=viewer_csrf,
        )
        assert viewer_logout.status == 200
        admin_login = api.dispatch(
            "POST",
            "/api/v2/app-auth/login",
            body={
                "username": "phase9.admin",
                "password": "correct horse battery staple",
            },
            client_kind="test",
        )
        admin_token = _token(admin_login)
        admin_csrf = admin_login.payload["csrf_token"]
        owner = next(
            item
            for item in api.dispatch(
                "GET", "/api/v2/phone-accounts", app_session_token=admin_token
            ).payload["phone_accounts"][0]["memberships"]
            if item["role"] == "owner" and item["status"] == "active"
        )
        last_owner = api.dispatch(
            "POST",
            f"/api/v2/phone-accounts/{phone_id}/memberships",
            app_session_token=admin_token,
            csrf_token=admin_csrf,
            body={
                "app_user_id": owner["app_user_id"],
                "role": "owner",
                "status": "revoked",
            },
        )
        assert last_owner.status == 403
        assert last_owner.payload["error"]["error_code"] == "phone_account_last_owner_required"

        revoked = api.dispatch(
            "POST",
            f"/api/v2/app-users/{viewer_id}/revoke-sessions",
            app_session_token=admin_token,
            csrf_token=admin_csrf,
        )
        assert revoked.status == 200
        audit = api.dispatch(
            "GET",
            "/api/v2/audit?action_prefix=phone_account.membership.&limit=20",
            app_session_token=admin_token,
        )
        assert audit.status == 200
        assert audit.payload["events"]
        assert "phase9-protected-phone" not in json.dumps(audit.payload)
    finally:
        api.close()


def test_non_admin_cannot_manage_phone_memberships(config_file, monkeypatch):
    monkeypatch.setenv("TEST_WP_USERNAME", "editor")
    monkeypatch.setenv("TEST_WP_APP_PASSWORD", "server-only-password")
    api = _api(config_file, monkeypatch)
    try:
        setup = api.dispatch(
            "POST",
            "/api/v2/app-auth/setup",
            body={
                "username": "phase9.admin",
                "password": "correct horse battery staple",
                "display_name": "مدیر",
            },
            client_kind="test",
        )
        token = _token(setup)
        csrf = setup.payload["csrf_token"]
        created = api.dispatch(
            "POST",
            "/api/v2/app-users",
            app_session_token=token,
            csrf_token=csrf,
            body={
                "username": "phase9.user",
                "password": "a safe ordinary password",
                "display_name": "کاربر",
                "global_role": "user",
            },
        )
        viewer_id = created.payload["user"]["app_user_id"]
        phone_id = api.dispatch(
            "GET", "/api/v2/phone-accounts", app_session_token=token
        ).payload["phone_accounts"][0]["phone_account_id"]
        api.dispatch(
            "POST",
            f"/api/v2/phone-accounts/{phone_id}/memberships",
            app_session_token=token,
            csrf_token=csrf,
            body={"app_user_id": viewer_id, "role": "operator", "status": "active"},
        )
        api.dispatch(
            "POST", "/api/v2/app-auth/logout", app_session_token=token, csrf_token=csrf
        )
        login = api.dispatch(
            "POST",
            "/api/v2/app-auth/login",
            body={"username": "phase9.user", "password": "a safe ordinary password"},
            client_kind="test",
        )
        user_token = _token(login)
        denied = api.dispatch(
            "GET", "/api/v2/phone-accounts", app_session_token=user_token
        )
        assert denied.status == 403
        assert denied.payload["error"]["error_code"] == "app_auth_admin_required"
    finally:
        api.close()
