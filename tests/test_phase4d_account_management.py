from __future__ import annotations

import importlib.util
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import sqlite3
import sys
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import uuid4
from zipfile import ZipFile

import pytest

import eitaa_bridge.application.account_runtime as runtime_module
import eitaa_bridge.application.api as api_module
from eitaa_bridge.application.account_runtime import AccountWorkerLease
from eitaa_bridge.application.api import APP_USER_SESSION_COOKIE, BridgeApplicationApi
from eitaa_bridge.errors import CoordinatorSchemaError, EitaaRuntimeError
from eitaa_bridge.infrastructure.coordinator import (
    CoordinatorAppAuth,
    CoordinatorDatabase,
    ProtectedPhone,
    StaticSubjectFingerprinter,
)
from eitaa_bridge.infrastructure.diagnostics import RuntimeLogger
from eitaa_bridge.interfaces.http_api import BridgeApiHttpServer


def _bootstrap(database: CoordinatorDatabase):
    return database.bootstrap_legacy_account(
        protected_phone=ProtectedPhone(
            ciphertext=b"protected-phone",
            key_version=1,
            fingerprint="a" * 64,
            display_hint="+••••••••53",
        ),
        display_name="Initial administrator",
        backup_name="verified.zip",
        source_manifest_sha256="b" * 64,
        source_file_count=1,
        source_total_bytes=1,
    )


def _add_account(database: CoordinatorDatabase, *, suffix: str = "67") -> str:
    account_id = str(uuid4())
    phone_id = str(uuid4())
    now = "2026-08-02T00:00:00.000+00:00"
    with sqlite3.connect(database.path) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute(
            """
            INSERT INTO phone_accounts(
                id,phone_ciphertext,phone_key_version,phone_fingerprint,
                display_hint,status,created_at,updated_at
            ) VALUES(?,?,1,?,?,'active',?,?)
            """,
            (phone_id, b"protected-second", suffix * 32, f"+••••••••{suffix}", now, now),
        )
        connection.execute(
            """
            INSERT INTO messenger_accounts(
                id,phone_account_id,provider,label,lifecycle_state,
                desired_worker_state,capability_revision,created_at,updated_at
            ) VALUES(?,?,'eitaa','Second Eitaa','created','stopped',0,?,?)
            """,
            (account_id, phone_id, now, now),
        )
        connection.execute(
            """
            INSERT INTO messenger_session_metadata(
                messenger_account_id,auth_state,session_generation,storage_revision,
                last_auth_transition_at,safe_reason_code,created_at,updated_at
            ) VALUES(?,'absent',1,1,?,'test_account_created',?,?)
            """,
            (account_id, now, now, now),
        )
        connection.commit()
    return account_id


def _add_user_membership(
    database: CoordinatorDatabase,
    *,
    creator_id: str,
    phone_account_id: str,
    role: str,
) -> str:
    user_id = str(uuid4())
    now = "2026-08-02T00:00:00.000+00:00"
    with sqlite3.connect(database.path) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute(
            """
            INSERT INTO app_users(id,display_name,global_role,status,created_at,updated_at)
            VALUES(?,'Scoped user','user','active',?,?)
            """,
            (user_id, now, now),
        )
        connection.execute(
            """
            INSERT INTO phone_account_memberships(
                id,app_user_id,phone_account_id,role,status,created_by_app_user_id,
                created_at,updated_at
            ) VALUES(?,?,?,?, 'active',?,?,?)
            """,
            (str(uuid4()), user_id, phone_account_id, role, creator_id, now, now),
        )
        connection.commit()
    return user_id


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


def test_exact_phone_membership_controls_account_visibility_and_operation(tmp_path):
    database = CoordinatorDatabase(tmp_path / "coordinator.sqlite3")
    first = _bootstrap(database)
    second_id = _add_account(database)
    operator_id = _add_user_membership(
        database,
        creator_id=first.app_user_id,
        phone_account_id=first.phone_account_id,
        role="operator",
    )
    visible = database.list_accessible_messenger_accounts(
        app_user_id=operator_id,
        global_role="user",
    )
    assert [item["messenger_account_id"] for item in visible] == [
        first.messenger_account_id
    ]
    assert visible[0]["permissions"]["operate"] is True
    with pytest.raises(CoordinatorSchemaError) as denied:
        database.require_messenger_account_access(
            second_id,
            app_user_id=operator_id,
            global_role="user",
            operation="operate",
        )
    assert denied.value.code == "messenger_account_access_denied"

    with sqlite3.connect(database.path) as connection:
        connection.execute(
            "UPDATE phone_account_memberships SET role='viewer' WHERE app_user_id=?",
            (operator_id,),
        )
        connection.commit()
    viewer = database.list_accessible_messenger_accounts(
        app_user_id=operator_id,
        global_role="user",
    )[0]
    assert viewer["permissions"] == {
        "view": True,
        "operate": False,
        "manage_worker": False,
    }


def test_api_lists_starts_selects_isolates_and_stops_accounts(
    config_file,
    monkeypatch,
):
    database = CoordinatorDatabase(
        config_file.parent / "data" / "coordinator" / "coordinator.sqlite3"
    )
    first = _bootstrap(database)
    second_id = _add_account(database)
    _enable_features(config_file, first.messenger_account_id)
    auth = CoordinatorAppAuth(
        database.path,
        fingerprinter=StaticSubjectFingerprinter(b"phase-4d-subject-secret"),
    )
    monkeypatch.setattr(
        api_module,
        "CoordinatorAppAuth",
        lambda _database_path, *, policy: auth,
    )
    api = BridgeApplicationApi(config_file)
    try:
        setup = api.dispatch(
            "POST",
            "/api/v2/app-auth/setup",
            body={
                "username": "phase4d.admin",
                "password": "correct horse battery staple",
                "display_name": "Phase 4D admin",
            },
            client_kind="test",
        )
        token = _cookie_token(setup)
        csrf = setup.payload["csrf_token"]
        listed = api.dispatch(
            "GET",
            "/api/v2/messenger-accounts",
            app_session_token=token,
        )
        assert listed.status == 200
        assert {item["messenger_account_id"] for item in listed.payload["accounts"]} == {
            first.messenger_account_id,
            second_id,
        }
        bale_payload = listed.payload["provider_adapters"]["bale"]
        assert bale_payload["provider"] == "bale"
        assert bale_payload["configured"] is False
        assert bale_payload["runtime_enabled"] is False
        assert bale_payload["onboarding_enabled"] is False
        assert bale_payload["auth_steps"] == []
        assert bale_payload["implementation_state"] == "implemented"
        assert bale_payload["capabilities"] == []
        assert bale_payload["reason_code"] == "provider_adapter_not_configured"

        for account_id in (first.messenger_account_id, second_id):
            started = api.dispatch(
                "POST",
                f"/api/v2/messenger-accounts/{account_id}/worker/start",
                app_session_token=token,
                csrf_token=csrf,
            )
            assert started.status == 200
            assert started.payload["worker"]["runtime_state"] == "ready"

        first_runtime = api._runtime_registry.runtime_for_account(
            first.messenger_account_id
        )
        second_runtime = api._runtime_registry.runtime_for_account(second_id)
        first_runtime.background_tasks["first"] = {"task_id": "first", "status": "completed"}
        second_runtime.background_tasks["second"] = {"task_id": "second", "status": "completed"}
        with ThreadPoolExecutor(max_workers=2) as pool:
            first_future = pool.submit(
                api.dispatch,
                "GET",
                "/api/v1/background/status",
                app_session_token=token,
                messenger_account_id=first.messenger_account_id,
            )
            second_future = pool.submit(
                api.dispatch,
                "GET",
                "/api/v1/background/status",
                app_session_token=token,
                messenger_account_id=second_id,
            )
            first_status = first_future.result()
            second_status = second_future.result()
        assert {item["task_id"] for item in first_status.payload["tasks"]} == {"first"}
        assert {item["task_id"] for item in second_status.payload["tasks"]} == {"second"}

        first_media = first_runtime.ownership.core.media_directory / "first.jpg"
        second_media = second_runtime.ownership.core.media_directory / "second.jpg"
        first_media.parent.mkdir(parents=True, exist_ok=True)
        second_media.parent.mkdir(parents=True, exist_ok=True)
        first_media.write_bytes(b"first")
        second_media.write_bytes(b"second")
        first_context = api._request_runtime.set(first_runtime)
        try:
            first_token = api.register_media_cache_file(first_media, "image/jpeg")
            api._auth_challenge = "first-challenge"
        finally:
            api._request_runtime.reset(first_context)
        second_context = api._request_runtime.set(second_runtime)
        try:
            second_token = api.register_media_cache_file(second_media, "image/jpeg")
            assert api._auth_challenge is None
            api._auth_challenge = "second-challenge"
        finally:
            api._request_runtime.reset(second_context)
        assert api.resolve_media_cache_file(
            first_token,
            messenger_account_id=second_id,
        ) is None
        assert api.resolve_media_cache_file(
            second_token,
            messenger_account_id=first.messenger_account_id,
        ) is None
        assert first_runtime.auth_challenge == "first-challenge"
        assert second_runtime.auth_challenge == "second-challenge"

        server = BridgeApiHttpServer(
            ("127.0.0.1", 0),
            api,
            upload_root=config_file.parent / "runtime" / "uploads",
        )
        server_thread = threading.Thread(target=server.serve_forever, daemon=True)
        server_thread.start()
        try:
            host, port = server.server_address
            base = f"http://{host}:{port}"
            selected_media = Request(
                base + f"/api/v1/media-cache/{first_token}",
                headers={
                    "Cookie": f"{APP_USER_SESSION_COOKIE}={token}",
                    "X-Eitaa-Client-Kind": "electron",
                },
            )
            with urlopen(selected_media, timeout=5) as response:
                assert response.read() == b"first"
            wrong_media = Request(
                base
                + f"/api/v1/media-cache/{first_token}"
                + f"?messenger_account_id={second_id}",
                headers={
                    "Cookie": f"{APP_USER_SESSION_COOKIE}={token}",
                    "X-Eitaa-Client-Kind": "electron",
                },
            )
            with pytest.raises(HTTPError) as missing:
                urlopen(wrong_media, timeout=5)
            assert missing.value.code == 400
            upload = Request(
                base + "/api/v1/files/upload",
                data=b"account-two-upload",
                method="POST",
                headers={
                    "Content-Type": "application/octet-stream",
                    "Cookie": f"{APP_USER_SESSION_COOKIE}={token}",
                    "X-CSRF-Token": csrf,
                    "X-Eitaa-Client-Kind": "electron",
                    "X-Eitaa-Messenger-Account": second_id,
                    "X-Eitaa-Filename": "second.txt",
                },
            )
            with urlopen(upload, timeout=5) as response:
                uploaded = json.loads(response.read().decode("utf-8"))
            uploaded_path = Path(uploaded["path"])
            assert uploaded_path.read_bytes() == b"account-two-upload"
            uploaded_path.relative_to(
                config_file.parent
                / "runtime"
                / "accounts"
                / second_id
                / "cache"
                / "uploads"
            )
        finally:
            server.shutdown()
            server.server_close()
            server_thread.join(timeout=3)

        for runtime, expected_id in (
            (first_runtime, first.messenger_account_id),
            (second_runtime, second_id),
        ):
            events = [
                json.loads(line)
                for line in runtime.ownership.worker_log_file.read_text(
                    encoding="utf-8"
                ).splitlines()
            ]
            assert events
            assert all(
                event["fields"]["messenger_account_id"] == expected_id
                for event in events
            )

        stopped = api.dispatch(
            "POST",
            f"/api/v2/messenger-accounts/{second_id}/worker/stop",
            app_session_token=token,
            csrf_token=csrf,
        )
        assert stopped.status == 200
        record = database.messenger_account_runtime(second_id)
        assert (record.lifecycle_state, record.desired_worker_state) == (
            "paused",
            "stopped",
        )

        with sqlite3.connect(database.path) as connection:
            audit_request_ids = {
                str(row[0])
                for row in connection.execute(
                    """
                    SELECT request_id FROM audit_events
                    WHERE action='messenger_account.worker.start_requested'
                    """
                ).fetchall()
            }
        application_events = [
            json.loads(line)
            for line in (
                config_file.parent / "runtime" / "logs" / "application.jsonl"
            ).read_text(encoding="utf-8").splitlines()
        ]
        start_request_ids = {
            item["fields"]["request_id"]
            for item in application_events
            if item["fields"].get("path", "").endswith("/worker/start")
        }
        assert start_request_ids
        assert start_request_ids.issubset(audit_request_ids)
        worker_start_request_ids: set[str] = set()
        for account_id in (first.messenger_account_id, second_id):
            worker_log = (
                config_file.parent
                / "runtime"
                / "accounts"
                / account_id
                / "logs"
                / "worker.jsonl"
            )
            worker_start_request_ids.update(
                event["fields"]["request_id"]
                for event in (
                    json.loads(line)
                    for line in worker_log.read_text(encoding="utf-8").splitlines()
                )
                if event["event"] == "eitaa_runtime_started"
            )
        assert worker_start_request_ids
        assert worker_start_request_ids.issubset(audit_request_ids)
    finally:
        api.close()


def test_worker_lease_recovers_only_a_confirmed_dead_owner(tmp_path, monkeypatch):
    account_id = str(uuid4())
    lock = tmp_path / "worker.lock"
    stale_lease = str(uuid4())
    lock.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "messenger_account_id": account_id,
                "provider": "eitaa",
                "lease_id": stale_lease,
                "process_id": 424242,
                "session_generation": 1,
                "storage_revision": 1,
                "acquired_at": "2026-08-02T00:00:00.000+00:00",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(runtime_module, "_process_is_alive", lambda _pid: False)
    acquired = AccountWorkerLease.acquire(
        lock,
        account_id,
        session_generation=1,
        storage_revision=1,
    )
    try:
        assert acquired.recovered_stale_archive is not None
        assert acquired.recovered_stale_archive.is_file()
        assert acquired.recovered_stale_archive.name.startswith("worker.lock.stale.")
    finally:
        acquired.release()

    lock.write_text("not-json", encoding="utf-8")
    with pytest.raises(EitaaRuntimeError) as malformed:
        AccountWorkerLease.acquire(
            lock,
            account_id,
            session_generation=1,
            storage_revision=1,
        )
    assert malformed.value.code == "eitaa_worker_lease_recovery_unsafe"
    assert lock.read_text(encoding="utf-8") == "not-json"


def test_worker_lease_recovers_when_pid_was_reused_by_a_non_worker(
    tmp_path,
    monkeypatch,
):
    account_id = str(uuid4())
    lock = tmp_path / "worker.lock"
    stale_lease = str(uuid4())
    lock.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "messenger_account_id": account_id,
                "provider": "eitaa",
                "lease_id": stale_lease,
                "process_id": 424242,
                "session_generation": 1,
                "storage_revision": 1,
                "acquired_at": "2026-08-02T00:00:00.000+00:00",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(runtime_module, "_process_is_alive", lambda _pid: True)
    monkeypatch.setattr(
        runtime_module,
        "_process_executable_name",
        lambda _pid: "svchost.exe",
        raising=False,
    )

    acquired = AccountWorkerLease.acquire(
        lock,
        account_id,
        session_generation=1,
        storage_revision=1,
    )
    try:
        assert acquired.recovered_stale_archive is not None
        assert acquired.recovered_stale_archive.is_file()
    finally:
        acquired.release()


def test_worker_process_identity_matches_the_current_python_runtime():
    executable_name = runtime_module._process_executable_name(os.getpid())

    assert executable_name is not None
    assert executable_name.casefold() == Path(sys.executable).name.casefold()
    assert runtime_module._process_owns_worker(os.getpid(), alive=True) is True


def test_worker_registry_recovers_when_active_pid_was_reused_by_a_non_worker(
    monkeypatch,
):
    account_id = str(uuid4())
    worker_id = str(uuid4())
    recovered: list[tuple[str, int, str | None]] = []

    class _Coordinator:
        @staticmethod
        def active_worker_instance(selected_id):
            assert selected_id == account_id
            return type(
                "ActiveWorker",
                (),
                {"worker_instance_id": worker_id, "process_id": 424242},
            )()

        @staticmethod
        def recover_dead_worker_instance(
            selected_worker_id,
            *,
            expected_process_id,
            request_id,
            reason_code,
        ):
            recovered.append(
                (
                    selected_worker_id,
                    expected_process_id,
                    request_id,
                    reason_code,
                )
            )

    registry = object.__new__(runtime_module.EitaaRuntimeRegistry)
    registry._coordinator = _Coordinator()
    monkeypatch.setattr(runtime_module, "_process_is_alive", lambda _pid: True)
    monkeypatch.setattr(
        runtime_module,
        "_process_executable_name",
        lambda _pid: "svchost.exe",
        raising=False,
    )

    registry._prepare_worker_start(account_id, request_id="pid-reuse-recovery")

    assert recovered == [
        (
            worker_id,
            424242,
            "pid-reuse-recovery",
            "worker_process_pid_reused",
        )
    ]


def test_coordinator_audits_pid_reuse_recovery_with_a_distinct_reason(tmp_path):
    database = CoordinatorDatabase(tmp_path / "coordinator.sqlite3")
    account = _bootstrap(database)
    _, worker = database.request_worker_start(
        account.messenger_account_id,
        process_id=424242,
        actor_app_user_id=None,
        actor_global_role=None,
        request_id="pid-reuse-start",
    )
    database.mark_worker_ready(worker.worker_instance_id)

    database.recover_dead_worker_instance(
        worker.worker_instance_id,
        expected_process_id=424242,
        request_id="pid-reuse-recovery",
        reason_code="worker_process_pid_reused",
    )

    recovered = database.worker_instances(account.messenger_account_id)[-1]
    assert recovered.runtime_state == "crashed"
    assert recovered.safe_reason_code == "worker_process_pid_reused"
    with sqlite3.connect(database.path) as connection:
        audit = connection.execute(
            """
            SELECT reason_code FROM audit_events
            WHERE action='messenger_account.worker.dead_process_recovered'
              AND request_id='pid-reuse-recovery'
            """
        ).fetchone()
    assert audit == ("worker_process_pid_reused",)


def test_account_support_bundle_redacts_and_excludes_private_state(tmp_path, monkeypatch):
    root = tmp_path / "installation"
    scripts = root / "scripts"
    scripts.mkdir(parents=True)
    account_id = str(uuid4())
    (root / "bridge.json").write_text(
        json.dumps({"password": "do-not-include", "phone": "+989121234567"}),
        encoding="utf-8",
    )
    (root / ".env").write_text("TOKEN=do-not-include", encoding="utf-8")
    session = root / "data" / "accounts" / account_id / "provider" / "session.json"
    session.parent.mkdir(parents=True)
    session.write_text("private-session", encoding="utf-8")
    log = root / "runtime" / "accounts" / account_id / "logs" / "worker.jsonl"
    log.parent.mkdir(parents=True)
    log.write_text(
        json.dumps({"phone": "+989121234567", "token": "A" * 40}) + "\n",
        encoding="utf-8",
    )
    source = Path(__file__).parents[1] / "scripts" / "create_diagnostics_bundle.py"
    scripts_root = str(source.parent)
    sys.path.insert(0, scripts_root)
    try:
        spec = importlib.util.spec_from_file_location("phase4d_bundle", source)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(scripts_root)
    output = tmp_path / "support.zip"
    monkeypatch.setattr(module, "project_root", lambda: root)
    monkeypatch.setattr(module, "load_version", lambda _root: "test")
    monkeypatch.setattr(module, "run_doctor", lambda _root: "doctor-safe")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "create_diagnostics_bundle.py",
            "--output",
            str(output),
            "--messenger-account-id",
            account_id,
        ],
    )
    assert module.main() == 0
    with ZipFile(output) as archive:
        names = set(archive.namelist())
        combined = "\n".join(
            archive.read(name).decode("utf-8", errors="replace")
            for name in names
        )
    assert "account/logs/worker.jsonl" in names
    assert "manifest.json" in names
    assert not any("session" in name.lower() for name in names)
    assert "private-session" not in combined
    assert "+989121234567" not in combined
    assert "A" * 40 not in combined
    assert account_id in combined


def test_account_runtime_log_rotates_redacts_and_keeps_immutable_context(tmp_path):
    account_id = str(uuid4())
    other_id = str(uuid4())
    path = tmp_path / "worker.jsonl"
    logger = RuntimeLogger(
        path,
        max_bytes=350,
        backup_count=2,
        context_fields={
            "messenger_account_id": account_id,
            "provider": "eitaa",
        },
    )
    for index in range(40):
        logger.emit(
            "rotation_test",
            fields={
                "index": index,
                "messenger_account_id": other_id,
                "phone": "+989121234567",
                "token": "sensitive-token-value",
            },
        )
    logger.close()
    files = [path, path.with_name(path.name + ".1"), path.with_name(path.name + ".2")]
    existing = [item for item in files if item.is_file()]
    assert len(existing) >= 2
    combined = "\n".join(item.read_text(encoding="utf-8") for item in existing)
    assert "+989121234567" not in combined
    assert "sensitive-token-value" not in combined
    assert other_id not in combined
    assert account_id in combined
