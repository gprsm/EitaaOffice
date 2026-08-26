from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import sqlite3
import time
from uuid import uuid4

import eitaa_bridge.application.api as api_module
from eitaa_bridge.application.api import APP_USER_SESSION_COOKIE, BridgeApplicationApi
from eitaa_bridge.infrastructure.contact_store import (
    CONTACT_SCHEMA,
    ContactMutationContext,
    SQLiteContactStore,
)
from eitaa_bridge.infrastructure.coordinator import (
    CoordinatorAppAuth,
    CoordinatorDatabase,
    ProtectedPhone,
    StaticSubjectFingerprinter,
)


def _context(user: str, account: str | None = None) -> ContactMutationContext:
    return ContactMutationContext(
        actor_app_user_id=user,
        messenger_account_id=account,
        provider="eitaa" if account else None,
        request_id=str(uuid4()),
    )


def _legacy_v1_database(path: Path) -> None:
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE contacts (
                contact_id INTEGER PRIMARY KEY AUTOINCREMENT,
                first_name TEXT NOT NULL DEFAULT '', last_name TEXT NOT NULL DEFAULT '',
                username TEXT NOT NULL DEFAULT '', eitaa_user_id INTEGER,
                access_hash TEXT NOT NULL DEFAULT '', organization TEXT NOT NULL DEFAULT '',
                notes TEXT NOT NULL DEFAULT '', source TEXT NOT NULL DEFAULT 'manual',
                sendable INTEGER NOT NULL DEFAULT 1, opt_out INTEGER NOT NULL DEFAULT 0,
                last_resolved_at TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                archived_at TEXT
            );
            CREATE UNIQUE INDEX idx_contacts_eitaa_user
                ON contacts(eitaa_user_id) WHERE eitaa_user_id IS NOT NULL;
            CREATE TABLE contact_phones (
                phone_id INTEGER PRIMARY KEY AUTOINCREMENT,
                contact_id INTEGER NOT NULL REFERENCES contacts(contact_id) ON DELETE CASCADE,
                normalized_phone TEXT NOT NULL UNIQUE, label TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            );
            CREATE TABLE contact_categories (
                category_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL COLLATE NOCASE UNIQUE,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            );
            CREATE TABLE contact_category_members (
                contact_id INTEGER NOT NULL REFERENCES contacts(contact_id) ON DELETE CASCADE,
                category_id INTEGER NOT NULL REFERENCES contact_categories(category_id) ON DELETE CASCADE,
                PRIMARY KEY(contact_id,category_id)
            );
            INSERT INTO contacts(
                first_name,created_at,updated_at
            ) VALUES('Legacy','2026-01-01T00:00:00+00:00','2026-01-01T00:00:00+00:00');
            INSERT INTO contact_phones(contact_id,normalized_phone,created_at)
                VALUES(1,'+989121111111','2026-01-01T00:00:00+00:00');
            PRAGMA user_version=1;
            """
        )


def test_v1_contact_database_is_backed_up_and_migrated_without_data_loss(tmp_path):
    path = tmp_path / "contacts.sqlite3"
    _legacy_v1_database(path)
    store = SQLiteContactStore(path)
    store.initialize()

    assert len(list(tmp_path.glob("contacts.schema1.*.bak.sqlite3"))) == 1
    assert store.list_contacts()[0]["phones"] == ["+989121111111"]
    with sqlite3.connect(path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == CONTACT_SCHEMA
        columns = {row[1] for row in connection.execute("PRAGMA table_info(contacts)")}
        assert {"created_by_app_user_id", "updated_by_app_user_id", "revision"} <= columns


def test_shared_merge_records_actor_categories_and_tamper_evident_audit(tmp_path):
    store = SQLiteContactStore(tmp_path / "contacts.sqlite3")
    first_user, second_user = str(uuid4()), str(uuid4())
    first_category = store.save_category(name="First", context=_context(first_user))
    second_category = store.save_category(name="Second", context=_context(second_user))
    first = store.upsert_contact(
        {
            "first_name": "First name",
            "phones": ["09121234567"],
            "category_ids": [first_category["id"]],
        },
        context=_context(first_user),
    )
    updated = store.upsert_contact(
        {
            "first_name": "Updated name",
            "phones": ["0098 912 123 4567"],
            "category_ids": [second_category["id"]],
        },
        duplicate_policy="update",
        category_policy="merge",
        context=_context(second_user),
    )

    assert updated["id"] == first["id"]
    assert updated["created_by_app_user_id"] == first_user
    assert updated["updated_by_app_user_id"] == second_user
    assert {item["name"] for item in updated["categories"]} == {"First", "Second"}
    assert store.verify_audit_chain() is True
    events = store.list_audit_events(contact_id=first["id"])
    assert {event["actor_app_user_id"] for event in events} == {first_user, second_user}
    with sqlite3.connect(store.path) as connection:
        audit_json = "\n".join(
            row[0]
            for row in connection.execute(
                "SELECT safe_metadata_json FROM contact_audit_events"
            )
        )
    assert "09121234567" not in audit_json
    assert "+989121234567" not in audit_json


def test_multi_phone_bridge_merges_existing_records_and_is_concurrency_safe(tmp_path):
    path = tmp_path / "contacts.sqlite3"
    store = SQLiteContactStore(path)
    first = store.upsert_contact({"first_name": "A", "phones": ["09120000001"]})
    second = store.upsert_contact({"first_name": "B", "phones": ["09120000002"]})
    merged = store.upsert_contact(
        {"phones": ["09120000001", "09120000002"]},
        duplicate_policy="update",
        category_policy="merge",
    )
    assert merged["id"] == min(first["id"], second["id"])
    assert len(store.list_contacts()) == 1

    def concurrent_upsert(index: int) -> int:
        local = SQLiteContactStore(path)
        return int(
            local.upsert_contact(
                {"first_name": f"Concurrent {index}", "phones": ["09350000000"]},
                duplicate_policy="update",
            )["id"]
        )

    with ThreadPoolExecutor(max_workers=4) as pool:
        ids = set(pool.map(concurrent_upsert, range(8)))
    assert len(ids) == 1
    assert len(store.list_contacts()) == 2
    assert store.verify_audit_chain() is True


def test_provider_identity_bindings_are_account_scoped_and_do_not_leak(tmp_path):
    store = SQLiteContactStore(tmp_path / "contacts.sqlite3")
    account_a, account_b = str(uuid4()), str(uuid4())
    contact = store.upsert_contact({"first_name": "Shared", "phones": ["09123334444"]})
    binding_a = store.record_account_binding(
        contact_id=contact["id"], messenger_account_id=account_a,
        provider="eitaa", provider_user_id=101, context=_context(str(uuid4()), account_a),
    )
    binding_b = store.record_account_binding(
        contact_id=contact["id"], messenger_account_id=account_b,
        provider="eitaa", provider_user_id=202, context=_context(str(uuid4()), account_b),
    )
    assert binding_a["binding_id"] != binding_b["binding_id"]
    assert store.selected_account_bindings(
        [contact["id"]], messenger_account_id=account_a, provider="eitaa"
    )[contact["id"]]["binding_id"] == binding_a["binding_id"]
    assert store.find_contacts_by_eitaa_identity(
        eitaa_user_ids=[101], messenger_account_id=account_b
    ) == ()
    assert store.find_contacts_by_eitaa_identity(
        eitaa_user_ids=[202], messenger_account_id=account_b
    )[0]["id"] == contact["id"]
    assert store.get_contacts([contact["id"]])[0]["eitaa_user_id"] is None


def _bootstrap(database: CoordinatorDatabase):
    return database.bootstrap_legacy_account(
        protected_phone=ProtectedPhone(
            ciphertext=b"protected-phone", key_version=1,
            fingerprint="a" * 64, display_hint="+masked53",
        ),
        display_name="Initial administrator", backup_name="verified.zip",
        source_manifest_sha256="b" * 64, source_file_count=1, source_total_bytes=1,
    )


def _add_account(database: CoordinatorDatabase) -> tuple[str, str]:
    account_id, phone_id = str(uuid4()), str(uuid4())
    now = "2026-08-02T00:00:00.000+00:00"
    with sqlite3.connect(database.path) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute(
            """INSERT INTO phone_accounts(
                id,phone_ciphertext,phone_key_version,phone_fingerprint,
                display_hint,status,created_at,updated_at
            ) VALUES(?,?,1,?,?,'active',?,?)""",
            (phone_id, b"protected-second", "c" * 64, "+masked67", now, now),
        )
        connection.execute(
            """INSERT INTO messenger_accounts(
                id,phone_account_id,provider,label,lifecycle_state,desired_worker_state,
                capability_revision,created_at,updated_at
            ) VALUES(?,?,'eitaa','Second','created','stopped',0,?,?)""",
            (account_id, phone_id, now, now),
        )
        connection.execute(
            """INSERT INTO messenger_session_metadata(
                messenger_account_id,auth_state,session_generation,storage_revision,
                last_auth_transition_at,safe_reason_code,created_at,updated_at
            ) VALUES(?,'absent',1,1,?,'test_created',?,?)""",
            (account_id, now, now, now),
        )
        connection.commit()
    return account_id, phone_id


def _enable_features(config_file: Path, account_id: str) -> None:
    payload = json.loads(config_file.read_text(encoding="utf-8"))
    payload["features"] = {
        "multi_session": {
            "enabled": True,
            "legacy_default_messenger_account_id": account_id,
        },
        "app_user_auth": {"enabled": True},
    }
    config_file.write_text(json.dumps(payload), encoding="utf-8")


def _cookie(response) -> str:
    name, token = response.headers["Set-Cookie"].split(";", 1)[0].split("=", 1)
    assert name == APP_USER_SESSION_COOKIE
    return token


def _wait_job(api: BridgeApplicationApi, job_id: str, token: str, account_id: str):
    for _ in range(500):
        response = api.dispatch(
            "GET", f"/api/v1/contacts/import/status?job_id={job_id}",
            app_session_token=token, messenger_account_id=account_id,
        )
        if response.payload["job"]["state"] not in {"queued", "running", "cancelling"}:
            return response.payload["job"]
        time.sleep(0.01)
    raise AssertionError("contact handoff did not finish")


def test_two_app_users_share_directory_but_remote_handoff_uses_selected_account(
    config_file, monkeypatch
):
    database = CoordinatorDatabase(
        config_file.parent / "data" / "coordinator" / "coordinator.sqlite3"
    )
    first = _bootstrap(database)
    second_account_id, second_phone_id = _add_account(database)
    _enable_features(config_file, first.messenger_account_id)
    auth = CoordinatorAppAuth(
        database.path,
        fingerprinter=StaticSubjectFingerprinter(b"phase-five-subject-secret"),
    )
    monkeypatch.setattr(
        api_module, "CoordinatorAppAuth", lambda _database_path, *, policy: auth
    )
    api = BridgeApplicationApi(config_file)
    try:
        setup = api.dispatch(
            "POST", "/api/v2/app-auth/setup",
            body={
                "username": "phase5.admin", "password": "admin password for phase five",
                "display_name": "Phase 5 admin",
            }, client_kind="test",
        )
        admin_token, admin_csrf = _cookie(setup), setup.payload["csrf_token"]
        created_user = api.dispatch(
            "POST", "/api/v2/app-users", app_session_token=admin_token,
            csrf_token=admin_csrf, client_kind="test",
            body={
                "username": "phase5.user", "password": "ordinary password for phase five",
                "display_name": "Phase 5 user", "global_role": "user",
            },
        ).payload["user"]
        now = "2026-08-02T00:00:00.000+00:00"
        with sqlite3.connect(database.path) as connection:
            connection.execute(
                """INSERT INTO phone_account_memberships(
                    id,app_user_id,phone_account_id,role,status,created_by_app_user_id,
                    created_at,updated_at
                ) VALUES(?,?,?,'operator','active',?,?,?)""",
                (str(uuid4()), created_user["app_user_id"], second_phone_id,
                 first.app_user_id, now, now),
            )
            connection.commit()
        login = api.dispatch(
            "POST", "/api/v2/app-auth/login",
            body={"username": "phase5.user", "password": "ordinary password for phase five"},
            client_kind="test",
        )
        user_token, user_csrf = _cookie(login), login.payload["csrf_token"]

        for account_id in (first.messenger_account_id, second_account_id):
            started = api.dispatch(
                "POST", f"/api/v2/messenger-accounts/{account_id}/worker/start",
                app_session_token=admin_token, csrf_token=admin_csrf,
            )
            assert started.status == 200

        created = api.dispatch(
            "POST", "/api/v1/contacts/upsert",
            app_session_token=admin_token, csrf_token=admin_csrf,
            messenger_account_id=first.messenger_account_id,
            body={"contact": {"first_name": "Shared person", "phones": ["09124445566"]}},
        )
        assert created.status == 200
        contact_id = created.payload["contact"]["id"]
        # Simulate a pre-Phase-5 legacy provider identity still present in the
        # shared row; multi-account responses must not expose it.
        api._contact_store.upsert_contact(
            {"id": contact_id, "eitaa_user_id": 987654, "access_hash": "legacy-secret"},
            duplicate_policy="update",
        )
        shared = api.dispatch(
            "POST", "/api/v1/contacts/list", app_session_token=user_token,
            csrf_token=user_csrf, messenger_account_id=second_account_id, body={},
        )
        assert [item["id"] for item in shared.payload["contacts"]] == [contact_id]
        assert shared.payload["shared_directory"] is True
        assert shared.payload["contacts"][0]["eitaa_user_id"] is None
        assert shared.payload["contacts"][0]["access_hash_present"] is False
        poisoned = api.dispatch(
            "POST", "/api/v1/contacts/upsert", app_session_token=user_token,
            csrf_token=user_csrf, messenger_account_id=second_account_id,
            body={
                "contact": {
                    "first_name": "Rejected", "phones": ["09121110000"],
                    "eitaa_user_id": 123, "access_hash": "must-not-be-written",
                }
            },
        )
        assert poisoned.status == 400
        assert poisoned.payload["error"]["error_code"] == "api_contact_provider_identity_not_writable"

        updated = api.dispatch(
            "POST", "/api/v1/contacts/upsert", app_session_token=user_token,
            csrf_token=user_csrf, messenger_account_id=second_account_id,
            body={
                "duplicate_policy": "update",
                "contact": {"first_name": "Updated by user", "phones": ["00989124445566"]},
            },
        )
        assert updated.payload["contact"]["created_by_app_user_id"] == first.app_user_id
        assert updated.payload["contact"]["updated_by_app_user_id"] == created_user["app_user_id"]
        audit = api.dispatch(
            "POST", "/api/v1/contacts/audit", app_session_token=user_token,
            csrf_token=user_csrf, messenger_account_id=second_account_id,
            body={"contact_id": contact_id},
        )
        assert audit.payload["chain_valid"] is True
        assert first.messenger_account_id not in json.dumps(audit.payload)

        used_accounts: list[str | None] = []

        def fake_add(payload):
            used_accounts.append(api._runtime.ownership.messenger_account_id)
            return {"ok": True, "contact_added": True, "contact": {"user_id": 1}}

        monkeypatch.setattr(api, "_eitaa_contacts_add", fake_add)
        for token, csrf, account_id in (
            (admin_token, admin_csrf, first.messenger_account_id),
            (user_token, user_csrf, second_account_id),
        ):
            handoff = api.dispatch(
                "POST", "/api/v1/contacts/add-to-messenger/start",
                app_session_token=token, csrf_token=csrf, messenger_account_id=account_id,
                body={"site_key": "medical-site", "contact_ids": [contact_id]},
            )
            assert handoff.status == 202
            assert _wait_job(api, handoff.payload["job"]["job_id"], token, account_id)["state"] == "completed"
        assert used_accounts == [first.messenger_account_id, second_account_id]

        forged = api.dispatch(
            "POST", "/api/v1/contacts/add-to-messenger/start",
            app_session_token=user_token, csrf_token=user_csrf,
            messenger_account_id=second_account_id,
            body={
                "site_key": "medical-site", "contact_ids": [contact_id],
                "messenger_account_id": first.messenger_account_id,
            },
        )
        assert forged.status == 400
        assert forged.payload["error"]["error_code"] == "api_contact_target_account_not_trusted"
    finally:
        api.close()
