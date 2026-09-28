from __future__ import annotations

import asyncio
import sqlite3
import time
from uuid import uuid4

import pytest

from eitaa_bridge.application.provider_capabilities import (
    ProviderCapabilityService,
    provider_capability_for_route,
)
from eitaa_bridge.errors import CoordinatorSchemaError, ProviderExtensionError
from eitaa_bridge.infrastructure.contact_store import (
    ContactMutationContext,
    SQLiteContactStore,
)
from eitaa_bridge.infrastructure.coordinator import (
    CoordinatorDatabase,
    PersistentOperationJobService,
    ProtectedPhone,
    SafeCoordinatorAuditService,
)
from eitaa_bridge.infrastructure.coordinator.schema import (
    COORDINATOR_SCHEMA_VERSION,
    SCHEMA_CHECKSUMS,
    SCHEMA_V1_SQL,
    SCHEMA_V2_SQL,
    SCHEMA_V3_SQL,
    SCHEMA_V4_SQL,
    SCHEMA_V5_SQL,
)
from eitaa_bridge.providers import (
    ProviderAccountContext,
    ProviderCapability,
    ProviderOperationContext,
    ProviderPeerReference,
    ProviderSendStatus,
    ProviderSendTextRequest,
    default_provider_registry,
)
from eitaa_bridge.providers.testing import (
    InMemoryProviderSessionStore,
    verify_provider_adapter_contract,
)


def _bootstrap(database: CoordinatorDatabase):
    return database.bootstrap_legacy_account(
        protected_phone=ProtectedPhone(
            ciphertext=b"phase11b1-protected",
            key_version=1,
            fingerprint="8" * 64,
            display_hint="+masked81",
        ),
        display_name="Phase 11-B1 administrator",
        backup_name="verified.zip",
        source_manifest_sha256="9" * 64,
        source_file_count=1,
        source_total_bytes=1,
    )


def _add_fake_account(database: CoordinatorDatabase):
    owner = _bootstrap(database)
    registry = default_provider_registry()
    database.reconcile_provider_registrations(
        registry.persistence_catalog(include_test=True)
    )
    account_id, phone_id, membership_id = str(uuid4()), str(uuid4()), str(uuid4())
    now = "2026-08-13T12:00:00.000+00:00"
    with sqlite3.connect(database.path) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute(
            """INSERT INTO phone_accounts(
                id,phone_ciphertext,phone_key_version,phone_fingerprint,display_hint,
                status,created_at,updated_at
            ) VALUES(?,?,1,?,?,'active',?,?)""",
            (phone_id, b"fake-protected", "7" * 64, "+masked82", now, now),
        )
        connection.execute(
            """INSERT INTO phone_account_memberships(
                id,app_user_id,phone_account_id,role,status,created_by_app_user_id,
                created_at,updated_at
            ) VALUES(?,?,?,'owner','active',?,?,?)""",
            (membership_id, owner.app_user_id, phone_id, owner.app_user_id, now, now),
        )
        connection.execute(
            """INSERT INTO messenger_accounts(
                id,phone_account_id,provider,label,lifecycle_state,desired_worker_state,
                capability_revision,created_at,updated_at
            ) VALUES(?,?,'fake','Offline Fake','created','stopped',0,?,?)""",
            (account_id, phone_id, now, now),
        )
        connection.execute(
            """INSERT INTO messenger_session_metadata(
                messenger_account_id,auth_state,session_generation,storage_revision,
                last_auth_transition_at,safe_reason_code,created_at,updated_at
            ) VALUES(?,'authenticated',1,1,?,'fake_session',?,?)""",
            (account_id, now, now, now),
        )
        connection.commit()
    return owner, account_id, phone_id, registry


def test_schema5_migrates_to_registry_schema_without_manual_rewrite(tmp_path):
    path = tmp_path / "coordinator-v5.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.executescript(
            "BEGIN IMMEDIATE;\n"
            + SCHEMA_V1_SQL
            + f"\nINSERT INTO schema_migrations VALUES(1,'{SCHEMA_CHECKSUMS[1]}','now');\n"
            + SCHEMA_V2_SQL
            + f"\nINSERT INTO schema_migrations VALUES(2,'{SCHEMA_CHECKSUMS[2]}','now');\n"
            + SCHEMA_V3_SQL
            + f"\nINSERT INTO schema_migrations VALUES(3,'{SCHEMA_CHECKSUMS[3]}','now');\n"
            + SCHEMA_V4_SQL
            + f"\nINSERT INTO schema_migrations VALUES(4,'{SCHEMA_CHECKSUMS[4]}','now');\n"
            + SCHEMA_V5_SQL
            + f"\nINSERT INTO schema_migrations VALUES(5,'{SCHEMA_CHECKSUMS[5]}','now');\n"
            + "PRAGMA user_version=5;\nCOMMIT;"
        )

    CoordinatorDatabase(path).initialize()

    with sqlite3.connect(path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == COORDINATOR_SCHEMA_VERSION == 10
        assert {row[0] for row in connection.execute("SELECT provider FROM provider_registrations")} == {"eitaa", "bale"}
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        assert connection.execute("PRAGMA quick_check").fetchone()[0] == "ok"


def test_registry_persistence_is_generic_and_fake_is_product_hidden(tmp_path):
    database = CoordinatorDatabase(tmp_path / "coordinator.sqlite3")
    database.initialize()
    registry = default_provider_registry()
    assert {item["provider"] for item in registry.persistence_catalog()} == {"eitaa", "bale"}
    assert {item["provider"] for item in registry.persistence_catalog(include_test=True)} == {"eitaa", "bale", "fake"}

    result = database.reconcile_provider_registrations(
        registry.persistence_catalog(include_test=True)
    )
    assert result["created"] == 1
    assert database.provider_registration("fake").runtime_enabled is True
    assert "fake" not in registry.descriptor_catalog()

    with sqlite3.connect(database.path) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """INSERT INTO messenger_accounts(
                    id,phone_account_id,provider,lifecycle_state,desired_worker_state,
                    created_at,updated_at
                ) VALUES(?,?,'unregistered','created','stopped','now','now')""",
                (str(uuid4()), str(uuid4())),
            )


def test_fake_provider_adapter_runs_full_offline_typed_contract():
    registry = default_provider_registry()
    registration = registry.registration("fake")
    account = ProviderAccountContext(
        messenger_account_id=str(uuid4()),
        phone_account_id=str(uuid4()),
        provider="fake",
        storage_revision=1,
        session_generation=1,
    )
    adapter = registry.create_adapter("fake", account, InMemoryProviderSessionStore())
    report = verify_provider_adapter_contract(
        adapter,
        expected_manifest=registration.manifest,
    )
    assert report.safe_payload()["adapter_shape_valid"] is True
    context = ProviderOperationContext(
        account=account,
        correlation_id="a" * 32,
        deadline_unix_ms=int(time.time() * 1000) + 30_000,
    )
    dialogs = asyncio.run(adapter.list_dialogs(context, cursor=None, limit=10))
    history = asyncio.run(
        adapter.load_history(
            context,
            peer=ProviderPeerReference("fake:dialog:1", "private"),
            cursor=None,
            limit=10,
        )
    )
    receipt = asyncio.run(
        adapter.send_text(
            context,
            ProviderSendTextRequest(
                ProviderPeerReference("fake:dialog:1", "private"),
                "synthetic only",
                "offline-fake-idempotency-0001",
            ),
        )
    )
    assert len(dialogs.dialogs) == len(history.messages) == 1
    assert receipt.status is ProviderSendStatus.SUCCEEDED


def test_capability_service_merges_observations_but_cannot_escalate_manifest(tmp_path):
    database = CoordinatorDatabase(tmp_path / "coordinator.sqlite3")
    _, account_id, _, registry = _add_fake_account(database)
    now = "2026-08-13T12:00:00.000+00:00"
    with sqlite3.connect(database.path) as connection:
        connection.execute(
            """INSERT INTO messenger_capabilities(
                messenger_account_id,capability,status,reason_code,constraints_json,
                revision,observed_at
            ) VALUES(?,?,'restricted','fake_policy','{}',1,?)""",
            (account_id, "dialogs.read", now),
        )
        connection.execute(
            """INSERT INTO messenger_capabilities(
                messenger_account_id,capability,status,reason_code,constraints_json,
                revision,observed_at
            ) VALUES(?,?,'supported','spoofed','{}',1,?)""",
            (account_id, "media.read", now),
        )
        connection.commit()
    service = ProviderCapabilityService(database, registry)
    snapshot = service.snapshot(account_id)
    assert snapshot.decision(ProviderCapability.DIALOGS_READ).status == "restricted"
    assert snapshot.decision(ProviderCapability.MEDIA_READ).status == "unsupported"
    assert service.require(account_id, ProviderCapability.MESSAGES_SEND).status == "supported"
    with pytest.raises(ProviderExtensionError) as rejected:
        service.require(account_id, ProviderCapability.MEDIA_READ)
    assert rejected.value.code == "provider_capability_unavailable"


def test_fake_account_worker_jobs_audit_and_provider_scope_are_generic(tmp_path):
    database = CoordinatorDatabase(tmp_path / "coordinator.sqlite3")
    owner, account_id, _, _ = _add_fake_account(database)
    runtime, worker = database.request_worker_start(
        account_id,
        process_id=4321,
        actor_app_user_id=owner.app_user_id,
        actor_global_role="admin",
        request_id=str(uuid4()),
    )
    assert runtime.provider == "fake" and worker.runtime_state == "starting"
    job = PersistentOperationJobService(database).create_job(
        actor_app_user_id=owner.app_user_id,
        actor_global_role="admin",
        messenger_account_id=account_id,
        operation="fake.execute",
        idempotency_key="fake-generic-job-0001",
        safe_payload_ref="fake:payload:1",
    ).job
    with sqlite3.connect(database.path) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        with pytest.raises(sqlite3.IntegrityError, match="operation_job_provider_scope_mismatch"):
            connection.execute(
                "UPDATE operation_jobs SET provider='eitaa' WHERE id=?",
                (job.job_id,),
            )
    page = SafeCoordinatorAuditService(database).query(
        app_user_id=owner.app_user_id,
        global_role="admin",
        provider="fake",
    )
    assert page.events
    assert {event.provider for event in page.events} == {"fake"}


def test_contact_schema2_migration_and_fake_bindings_preserve_account_isolation(tmp_path):
    legacy = tmp_path / "legacy-contacts.sqlite3"
    account_a, account_b = str(uuid4()), str(uuid4())
    with sqlite3.connect(legacy) as connection:
        connection.executescript(
            """
            CREATE TABLE contacts(contact_id INTEGER PRIMARY KEY);
            INSERT INTO contacts(contact_id) VALUES(1);
            CREATE TABLE contact_account_bindings (
                binding_id TEXT PRIMARY KEY,
                contact_id INTEGER NOT NULL REFERENCES contacts(contact_id) ON DELETE CASCADE,
                messenger_account_id TEXT NOT NULL,
                provider TEXT NOT NULL CHECK(provider IN ('eitaa','bale')),
                provider_subject_fingerprint TEXT,
                reachability TEXT NOT NULL DEFAULT 'unknown',
                safe_reason_code TEXT,
                last_resolved_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                created_by_app_user_id TEXT,
                updated_by_app_user_id TEXT,
                UNIQUE(messenger_account_id,provider,contact_id)
            );
            INSERT INTO contact_account_bindings VALUES(
                'legacy-binding',1,'legacy-account','eitaa',NULL,'unknown',NULL,NULL,
                'now','now',NULL,NULL
            );
            PRAGMA user_version=2;
            """
        )
    migrated = SQLiteContactStore(legacy)
    migrated.initialize()
    with sqlite3.connect(legacy) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 3
        assert connection.execute("SELECT binding_id FROM contact_account_bindings").fetchone()[0] == "legacy-binding"
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []

    store = SQLiteContactStore(tmp_path / "contacts.sqlite3")
    store.reconcile_provider_registrations(
        default_provider_registry().persistence_catalog(include_test=True)
    )
    contact = store.upsert_contact({"first_name": "Synthetic", "phones": ["09120000091"]})
    actor = str(uuid4())
    first = store.record_account_binding(
        contact_id=contact["id"],
        messenger_account_id=account_a,
        provider="fake",
        provider_user_id="opaque-test-subject-A",
        context=ContactMutationContext(actor, account_a, "fake"),
    )
    second = store.record_account_binding(
        contact_id=contact["id"],
        messenger_account_id=account_b,
        provider="fake",
        provider_user_id="opaque-test-subject-B",
        context=ContactMutationContext(actor, account_b, "fake"),
    )
    assert first["binding_id"] != second["binding_id"]
    selected = store.selected_account_bindings(
        [contact["id"]], messenger_account_id=account_a, provider="fake"
    )
    assert selected[contact["id"]]["binding_id"] == first["binding_id"]
    raw = store.path.read_bytes()
    assert b"opaque-test-subject-A" not in raw and b"opaque-test-subject-B" not in raw


@pytest.mark.parametrize(
    ("method", "path", "expected"),
    [
        ("POST", "/api/v1/dialogs/list", ProviderCapability.DIALOGS_READ),
        ("POST", "/api/v1/dialogs/avatar", ProviderCapability.MEDIA_READ),
        ("POST", "/api/v1/messages/list", ProviderCapability.HISTORY_READ),
        ("POST", "/api/v1/messages/send", ProviderCapability.MESSAGES_SEND),
        ("POST", "/api/v1/messages/media-preview", ProviderCapability.MEDIA_READ),
        ("POST", "/api/v1/eitaa-contacts/list", ProviderCapability.CONTACTS_READ),
        ("POST", "/api/v1/eitaa-contacts/add", ProviderCapability.CONTACTS_WRITE),
        ("POST", "/api/v1/contacts/add-to-messenger/start", ProviderCapability.CONTACTS_WRITE),
    ],
)
def test_provider_backed_routes_have_explicit_capabilities(method, path, expected):
    assert provider_capability_for_route(method, path) is expected


def test_provider_filters_and_bindings_reject_unregistered_values(tmp_path):
    database = CoordinatorDatabase(tmp_path / "coordinator.sqlite3")
    owner = _bootstrap(database)
    audit = SafeCoordinatorAuditService(database)
    with pytest.raises(CoordinatorSchemaError) as rejected:
        audit.query(
            app_user_id=owner.app_user_id,
            global_role="admin",
            provider="unknown_provider",
        )
    assert rejected.value.code == "audit_provider_invalid"

    store = SQLiteContactStore(tmp_path / "contacts.sqlite3")
    contact = store.upsert_contact({"first_name": "Synthetic", "phones": ["09120000092"]})
    with pytest.raises(ValueError, match="not registered"):
        store.record_account_binding(
            contact_id=contact["id"],
            messenger_account_id=str(uuid4()),
            provider="unknown_provider",
        )
