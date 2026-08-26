from __future__ import annotations

import hashlib
import json
from uuid import uuid4

from eitaa_bridge.infrastructure.coordinator import (
    CoordinatorDatabase,
    SafeCoordinatorAuditService,
)


def _hash(payload: dict[str, object]) -> str:
    canonical = json.dumps(
        payload,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def test_historical_null_request_id_contract_can_precede_current_events(tmp_path):
    database = CoordinatorDatabase(tmp_path / "coordinator.sqlite3")
    database.initialize()
    event_id = str(uuid4())
    occurred_at = "2026-08-13T00:00:00.000+00:00"
    metadata_json = '{"source":"historical"}'
    legacy_payload = {
        "id": event_id,
        "schema_version": 1,
        "at": occurred_at,
        "actor_type": "system",
        "actor_app_user_id": None,
        "actor_global_role": None,
        "action": "migration.legacy.verified",
        "target_type": "migration_run",
        "target_id": None,
        "phone_account_id": None,
        "messenger_account_id": None,
        "provider": None,
        "result": "succeeded",
        "reason_code": None,
        "safe_metadata_json": metadata_json,
        "previous_event_hash": None,
    }
    legacy_hash = _hash(legacy_payload)
    with database._connect() as connection:
        connection.execute(
            """
            INSERT INTO audit_events(
                id,schema_version,at,actor_type,actor_app_user_id,actor_global_role,
                action,target_type,target_id,phone_account_id,messenger_account_id,
                provider,result,reason_code,request_id,safe_metadata_json,
                previous_event_hash,event_hash
            ) VALUES(?,1,?,'system',NULL,NULL,'migration.legacy.verified',
                     'migration_run',NULL,NULL,NULL,NULL,'succeeded',NULL,NULL,?,NULL,?)
            """,
            (event_id, occurred_at, metadata_json, legacy_hash),
        )
        CoordinatorDatabase._append_audit(
            connection,
            actor_type="system",
            actor_app_user_id=None,
            actor_global_role=None,
            action="worker.started",
            target_type="worker_instance",
            target_id=None,
            phone_account_id=None,
            messenger_account_id=None,
            provider=None,
            result="succeeded",
            reason_code=None,
            safe_metadata={},
        )
        connection.commit()

    report = SafeCoordinatorAuditService(database).verify_chain()
    assert report.valid is True
    assert report.event_count == 2


def test_non_null_request_id_cannot_use_legacy_omission(tmp_path):
    database = CoordinatorDatabase(tmp_path / "coordinator.sqlite3")
    database.initialize()
    event_id = str(uuid4())
    request_id = str(uuid4())
    occurred_at = "2026-08-13T00:00:00.000+00:00"
    legacy_payload = {
        "id": event_id,
        "schema_version": 1,
        "at": occurred_at,
        "actor_type": "system",
        "actor_app_user_id": None,
        "actor_global_role": None,
        "action": "worker.started",
        "target_type": "worker_instance",
        "target_id": None,
        "phone_account_id": None,
        "messenger_account_id": None,
        "provider": None,
        "result": "succeeded",
        "reason_code": None,
        "safe_metadata_json": "{}",
        "previous_event_hash": None,
    }
    with database._connect() as connection:
        connection.execute(
            """
            INSERT INTO audit_events(
                id,schema_version,at,actor_type,action,target_type,result,request_id,
                safe_metadata_json,event_hash
            ) VALUES(?,1,?,'system','worker.started','worker_instance','succeeded',?,'{}',?)
            """,
            (event_id, occurred_at, request_id, _hash(legacy_payload)),
        )
        connection.commit()

    assert SafeCoordinatorAuditService(database).verify_chain().valid is False
