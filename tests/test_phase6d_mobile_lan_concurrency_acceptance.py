from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import hashlib
import hmac
import json
import os
from pathlib import Path
import threading
from urllib.parse import urlsplit
from urllib.request import urlopen

from eitaa_bridge.application.api import ApiResponse, BridgeApplicationApi
from eitaa_bridge.infrastructure.coordinator import (
    AppAuthPolicy,
    CoordinatorAppAuth,
    CoordinatorDatabase,
    PasswordHasher,
    ProtectedPhone,
    StaticSubjectFingerprinter,
)
from eitaa_bridge.infrastructure.coordinator.app_auth import PasswordMaterial
from eitaa_bridge.interfaces.http_api import BridgeApiHttpServer


class FastTestPasswordHasher(PasswordHasher):
    iterations = 600_000

    @staticmethod
    def _digest(password: str, salt: bytes) -> bytes:
        return hashlib.sha256(bytes(salt) + password.encode("utf-8")).digest()

    def hash_password(self, password: str) -> PasswordMaterial:
        if len(password) < 12:
            return super().hash_password(password)
        salt = os.urandom(16)
        return PasswordMaterial(salt, self._digest(password, salt), self.iterations)

    def verify_password(
        self,
        password: str,
        *,
        salt: bytes,
        expected_digest: bytes,
        iterations: int,
    ) -> bool:
        del iterations
        return hmac.compare_digest(
            self._digest(password, salt),
            bytes(expected_digest),
        )

    def dummy_material(self) -> PasswordMaterial:
        salt = b"d" * 16
        return PasswordMaterial(
            salt,
            self._digest("dummy-password-value", salt),
            self.iterations,
        )


def _protected_phone() -> ProtectedPhone:
    return ProtectedPhone(
        ciphertext=b"phase6d-protected-phone",
        key_version=1,
        fingerprint="d" * 64,
        display_hint="+**********67",
    )


def _read_json(url: str) -> dict[str, object]:
    with urlopen(url, timeout=5) as response:
        assert response.status == 200
        return json.loads(response.read().decode("utf-8"))


def test_threaded_http_accepts_parallel_clients_and_health_stays_responsive(
    config_file,
    monkeypatch,
):
    monkeypatch.setenv("TEST_WP_USERNAME", "editor")
    monkeypatch.setenv("TEST_WP_APP_PASSWORD", "password")
    api = BridgeApplicationApi(config_file)
    original_dispatch = api.dispatch
    simultaneous = threading.Barrier(2)
    slow_entered = threading.Event()
    release_slow = threading.Event()

    def instrumented_dispatch(method: str, path: str, **kwargs):
        selected = urlsplit(path).path
        if selected == "/api/v1/phase6d-concurrency-probe":
            simultaneous.wait(timeout=5)
            return ApiResponse(
                200,
                {"ok": True, "worker_thread": threading.get_ident()},
            )
        if selected == "/api/v1/phase6d-slow-probe":
            slow_entered.set()
            if not release_slow.wait(timeout=5):
                return ApiResponse(503, {"ok": False, "reason": "test_timeout"})
            return ApiResponse(200, {"ok": True, "released": True})
        return original_dispatch(method, path, **kwargs)

    api.dispatch = instrumented_dispatch  # type: ignore[method-assign]
    server = BridgeApiHttpServer(("127.0.0.1", 0), api)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    try:
        host, port = server.server_address
        base = f"http://{host}:{port}"
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(
                _read_json,
                base + "/api/v1/phase6d-concurrency-probe",
            )
            second = pool.submit(
                _read_json,
                base + "/api/v1/phase6d-concurrency-probe",
            )
            results = [first.result(timeout=6), second.result(timeout=6)]
        assert len({item["worker_thread"] for item in results}) == 2

        with ThreadPoolExecutor(max_workers=2) as pool:
            slow = pool.submit(_read_json, base + "/api/v1/phase6d-slow-probe")
            assert slow_entered.wait(timeout=3)
            health = pool.submit(_read_json, base + "/api/v1/health")
            assert health.result(timeout=3)["status"] == "alive"
            release_slow.set()
            assert slow.result(timeout=3)["released"] is True
    finally:
        release_slow.set()
        server.shutdown()
        server.server_close()
        api.close()
        server_thread.join(timeout=3)


def test_parallel_app_user_sessions_remain_isolated(tmp_path):
    database_path = tmp_path / "coordinator.sqlite3"
    database = CoordinatorDatabase(database_path)
    database.bootstrap_legacy_account(
        protected_phone=_protected_phone(),
        display_name="Initial administrator",
        backup_name="verified.zip",
        source_manifest_sha256="a" * 64,
        source_file_count=1,
        source_total_bytes=1,
    )
    auth = CoordinatorAppAuth(
        database_path,
        fingerprinter=StaticSubjectFingerprinter(b"phase6d-session-subject-secret"),
        password_hasher=FastTestPasswordHasher(),
        policy=AppAuthPolicy(
            idle_timeout_minutes=30,
            absolute_timeout_hours=12,
            max_failed_attempts=5,
            lockout_minutes=15,
        ),
    )
    admin = auth.bootstrap_admin(
        username="local.admin",
        password="correct horse battery staple",
        display_name="Local administrator",
        client_kind="browser",
    )
    admin_session = auth.authorize(admin.token)
    created = auth.create_user(
        admin_session.principal,
        username="ordinary.user",
        password="an ordinary local password",
        display_name="Ordinary user",
        global_role="user",
    )
    ordinary = auth.authenticate(
        username="ordinary.user",
        password="an ordinary local password",
        client_kind="browser",
    )

    def authorize(index: int) -> tuple[str, str]:
        issued = admin if index % 2 == 0 else ordinary
        session = auth.authorize(
            issued.token,
            csrf_token=issued.csrf_token,
            require_csrf=True,
            request_id=f"phase6d-{index}",
        )
        return session.principal.app_user_id, session.principal.session_id

    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(authorize, range(24)))

    admin_results = results[0::2]
    user_results = results[1::2]
    assert {item[0] for item in admin_results} == {admin.principal.app_user_id}
    assert {item[1] for item in admin_results} == {admin.principal.session_id}
    assert {item[0] for item in user_results} == {str(created["app_user_id"])}
    assert {item[1] for item in user_results} == {ordinary.principal.session_id}
    assert admin.principal.session_id != ordinary.principal.session_id
    assert admin.csrf_token != ordinary.csrf_token


def test_browser_transport_retries_only_safe_reads_and_keeps_auth_in_memory():
    root = Path(__file__).resolve().parents[1]
    main = (root / "ui" / "src" / "main.tsx").read_text(encoding="utf-8")
    client = (root / "ui" / "src" / "lib" / "api.ts").read_text(
        encoding="utf-8"
    )
    connection = (root / "ui" / "src" / "ConnectionStatus.tsx").read_text(
        encoding="utf-8"
    )

    assert "credentials: 'same-origin'" in main
    assert "const attempts = method === 'GET' ? 2 : 1" in main
    assert "error instanceof SyntaxError" in main
    assert main.count("fetch('/api/v1/files/upload'") == 1
    assert "فایل دوباره ارسال نشده است" in main
    assert "CLIENT_CONNECTIVITY_CHANGED_EVENT" in connection
    assert "probeReadiness" in connection
    assert "appCsrfToken" in client
    assert "localStorage.setItem" not in client
    assert "sessionStorage" not in client


def test_phone_shell_is_viewport_driven_touch_safe_and_keeps_more_menu_reachable():
    root = Path(__file__).resolve().parents[1]
    app = ((root / "ui" / "src" / "App.tsx").read_text(encoding="utf-8") + (root / "ui" / "src" / "utils" / "helpers.tsx").read_text(encoding="utf-8"))
    navigation = (root / "ui" / "src" / "WorkspaceNavigation.tsx").read_text(encoding="utf-8")
    theme = (root / "ui" / "src" / "theme.ts").read_text(encoding="utf-8")

    assert "'(max-width:599px), (max-width:899px) and (orientation:landscape) and (max-height:599px)'" in app
    assert "data-presentation-shell" in app
    assert "navigator.userAgent" not in app
    assert 'aria-label="منوی بیشتر"' in navigation
    assert "height: '100dvh'" in app
    assert "minHeight: '100svh'" in app
    assert "env(safe-area-inset-bottom)" in navigation
    assert "BottomNavigation" in navigation and "BottomNavigationAction" in navigation
    assert "minHeight: 44" in theme
    assert "className=" not in app + navigation


def test_local_ui_state_is_scoped_by_app_user_and_messenger_account():
    root = Path(__file__).resolve().parents[1]
    client = (root / "ui" / "src" / "lib" / "api.ts").read_text(
        encoding="utf-8"
    )
    app_user = (root / "ui" / "src" / "AppUserGate.tsx").read_text(
        encoding="utf-8"
    )
    app = ((root / "ui" / "src" / "App.tsx").read_text(encoding="utf-8") + (root / "ui" / "src" / "utils" / "helpers.tsx").read_text(encoding="utf-8"))
    quick_send = (root / "ui" / "src" / "QuickSendBar.tsx").read_text(
        encoding="utf-8"
    )
    runtime_patch = (root / "ui" / "src" / "ui33-runtime-patch.js").read_text(
        encoding="utf-8"
    )

    assert "user-${storageAppUserId}.account-${selectedMessengerAccountId" in client
    assert "document.documentElement.dataset.clientStorageScope" in client
    assert "setAppUserStorageScope(status.principal.app_user_id)" in app_user
    assert "localStorage.getItem(scopedStorageKey(key))" in app
    assert "scopedStorageKey(`eitaa-bridge.quick-send.${peerKey}`)" in quick_send
    assert "eitaa-bridge:client-storage-scope-changed" in runtime_patch
    assert "localStorage.getItem(scopedKey(key))" in runtime_patch
