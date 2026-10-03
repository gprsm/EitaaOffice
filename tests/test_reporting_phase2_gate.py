"""Gate tests for reporting phase 2: transactional core, ETag concurrency, and RBAC."""

from __future__ import annotations

from datetime import date
from pathlib import Path
import sqlite3

import pytest

from eitaa_bridge.application import reporting_api_v3 as v3
from eitaa_bridge.reporting.model import ProgramKind, ReportedEvent, UnitScope
from eitaa_bridge.reporting.store import (
    EventNotFoundError,
    ReportingStore,
    WitnessConflictError,
)


def _make_store(tmp_path: Path) -> ReportingStore:
    return ReportingStore(tmp_path / "gate.sqlite3")


def _bootstrap(store: ReportingStore) -> list[str]:
    store.set_user_roles("boss", {"editor", "approver", "admin"}, actor="bootstrap")
    return store.get_user_roles("boss")


def test_full_lifecycle_with_etag(tmp_path: Path) -> None:
    # 1. Draft creation via v3.dispatch returning 201 and initial etag
    store = _make_store(tmp_path)
    roles = _bootstrap(store)

    create_payload = {
        "program_kinds": ["ceremony"],
        "unit_name": "دادگستری کل",
        "occasion": "مراسم میلاد",
        "notes": "یادداشت اولیه",
    }
    status, body, _ = v3.dispatch(
        store, "boss", roles, "POST", "/api/v3/reporting/events", create_payload
    )
    assert status == 201
    assert body["ok"] is True
    event_id = body["event_id"]
    initial_etag = body["etag"]
    assert bool(initial_etag)

    # 2. PUT /events/{id} with correct If-Match yields 200 and a new etag
    update_payload = {
        "if_match": initial_etag,
        "fields": {"occasion": "مراسم میلاد با سعادت"},
    }
    status, body, _ = v3.dispatch(
        store, "boss", roles, "PUT", f"/api/v3/reporting/events/{event_id}", update_payload
    )
    assert status == 200
    assert body["ok"] is True
    new_etag = body["etag"]
    assert new_etag != initial_etag

    # 3. Repeated PUT with stale etag yields 409 conflict and current_etag == new_etag
    stale_payload = {
        "if_match": initial_etag,
        "fields": {"occasion": "تغییر منقضی"},
    }
    status, body, _ = v3.dispatch(
        store, "boss", roles, "PUT", f"/api/v3/reporting/events/{event_id}", stale_payload
    )
    assert status == 409
    assert body["ok"] is False
    # Uniform v3 error contract: details live in error.safe_context
    assert body["error"]["safe_context"]["current_etag"] == new_etag

    # 4. GET /events/{id} yields 200 with review_status == "draft" and event.etag == new_etag
    status, body, _ = v3.dispatch(
        store, "boss", roles, "GET", f"/api/v3/reporting/events/{event_id}"
    )
    assert status == 200
    assert body["ok"] is True
    event = body["event"]
    assert event["review_status"] == "draft"
    assert event["etag"] == new_etag


def test_two_concurrent_users_same_message(tmp_path: Path) -> None:
    # Two witnesses from different accounts with identical (peer_id, message_id) succeed
    store = _make_store(tmp_path)
    _bootstrap(store)

    event1 = ReportedEvent(
        event_id="evt-gate-u1",
        program_kinds=(ProgramKind.CEREMONY,),
        occurred_on=date(1405, 1, 1),
        unit=UnitScope.PROVINCIAL_HQ,
        unit_name="واحد اول",
    )
    event2 = ReportedEvent(
        event_id="evt-gate-u2",
        program_kinds=(ProgramKind.CEREMONY,),
        occurred_on=date(1405, 1, 1),
        unit=UnitScope.PROVINCIAL_HQ,
        unit_name="واحد دوم",
    )
    event3 = ReportedEvent(
        event_id="evt-gate-u3",
        program_kinds=(ProgramKind.CEREMONY,),
        occurred_on=date(1405, 1, 1),
        unit=UnitScope.PROVINCIAL_HQ,
        unit_name="واحد سوم",
    )
    store.create_event_draft(event1, actor="user-a")
    store.create_event_draft(event2, actor="user-b")
    store.create_event_draft(event3, actor="user-c")

    link1 = store.link_witness(
        event1.event_id,
        peer_id="p1",
        message_id="999",
        messenger_account="accA",
        role="primary",
        actor="user-a",
    )
    link2 = store.link_witness(
        event2.event_id,
        peer_id="p1",
        message_id="999",
        messenger_account="accB",
        role="primary",
        actor="user-b",
    )
    assert link1["witness_id"] != link2["witness_id"]

    # Linking the same witness with account 'accA' as primary to a third event fails with WitnessConflictError
    with pytest.raises(WitnessConflictError):
        store.link_witness(
            event3.event_id,
            peer_id="p1",
            message_id="999",
            messenger_account="accA",
            role="primary",
            actor="user-a",
        )


def test_conflict_resolution_requires_approver_role(tmp_path: Path) -> None:
    # Role gate enforcement: user with only 'editor' role gets 403 on approve, 'approver' gets 200
    store = _make_store(tmp_path)
    _bootstrap(store)

    store.set_user_roles("editor_user", {"editor"}, actor="boss")
    store.set_user_roles("approver_user", {"approver"}, actor="boss")
    editor_roles = store.get_user_roles("editor_user")
    approver_roles = store.get_user_roles("approver_user")

    event = ReportedEvent(
        event_id="evt-gate-roles",
        program_kinds=(ProgramKind.CEREMONY,),
        occurred_on=date(1405, 1, 1),
        unit=UnitScope.PROVINCIAL_HQ,
        unit_name="واحد بازبینی",
    )
    store.create_event_draft(event, actor="editor_user")

    # Transition to needs_review first (editor is allowed to submit_review)
    status_submit, _, _ = v3.dispatch(
        store,
        "editor_user",
        editor_roles,
        "POST",
        f"/api/v3/reporting/events/{event.event_id}/submit-review",
        {},
    )
    assert status_submit == 200

    # User with only editor role attempts POST .../approve -> 403
    status_ed, body_ed, _ = v3.dispatch(
        store,
        "editor_user",
        editor_roles,
        "POST",
        f"/api/v3/reporting/events/{event.event_id}/approve",
        {},
    )
    assert status_ed == 403
    assert body_ed["ok"] is False

    # User with approver role attempts POST .../approve -> 200
    status_app, body_app, _ = v3.dispatch(
        store,
        "approver_user",
        approver_roles,
        "POST",
        f"/api/v3/reporting/events/{event.event_id}/approve",
        {},
    )
    assert status_app == 200
    assert body_app["ok"] is True


def test_rollback_on_witness_link_failure(tmp_path: Path) -> None:
    # Simulated mid-operation crash: verify event absence, link fails, no orphan witness row left
    store = _make_store(tmp_path)
    _bootstrap(store)

    missing_event_id = "evt-nonexistent-crash"
    assert store.get_event_file(missing_event_id) is None

    with pytest.raises(EventNotFoundError):
        store.link_witness(
            missing_event_id,
            peer_id="p-crash",
            message_id="m-crash",
            messenger_account="accCrash",
            actor="tester",
        )

    with store._connect() as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM reporting_message_witnesses WHERE peer_id = ? AND message_id = ?",
            ("p-crash", "m-crash"),
        ).fetchone()[0]
        assert count == 0


def test_review_queue_lifecycle(tmp_path: Path) -> None:
    # Witness linked without messenger_account creates deterministic queue item resolved via store API
    store = _make_store(tmp_path)
    _bootstrap(store)

    event = ReportedEvent(
        event_id="evt-gate-queue",
        program_kinds=(ProgramKind.CEREMONY,),
        occurred_on=date(1405, 1, 1),
        unit=UnitScope.PROVINCIAL_HQ,
        unit_name="واحد صف بررسی",
    )
    store.create_event_draft(event, actor="tester")

    result = store.link_witness(
        event.event_id,
        peer_id="p-queue",
        message_id="m-queue",
        messenger_account="",
        actor="tester",
    )
    witness_id = result["witness_id"]
    expected_queue_id = f"rq-witness-{witness_id}"

    # Item is present in review queue
    items = store.list_review_queue(item_type="witness_missing_account")
    queue_ids = [item["queue_id"] for item in items]
    assert expected_queue_id in queue_ids

    # First resolve succeeds
    resolved_first = store.resolve_review_item(
        expected_queue_id,
        actor="reviewer",
        decision="resolved",
    )
    assert resolved_first is True

    # Second resolve returns False because status is no longer open
    resolved_second = store.resolve_review_item(
        expected_queue_id,
        actor="reviewer",
        decision="resolved",
    )
    assert resolved_second is False


def test_audit_trail_records_actions(tmp_path: Path) -> None:
    # Actions (create_draft, update, submit_review, witness.link.primary) are logged with valid diffs
    store = _make_store(tmp_path)
    _bootstrap(store)

    event = ReportedEvent(
        event_id="evt-gate-audit",
        program_kinds=(ProgramKind.CEREMONY,),
        occurred_on=date(1405, 1, 1),
        unit=UnitScope.PROVINCIAL_HQ,
        unit_name="واحد ردپای ممیزی",
    )
    event_id, etag1 = store.create_event_draft(event, actor="actor-creator")
    etag2 = store.update_event_fields(
        event_id,
        actor="actor-updater",
        expected_etag=etag1,
        fields={"notes": "یادداشت اصلاحی"},
    )
    etag3 = store.transition_event_status(
        event_id,
        action="submit_review",
        actor="actor-submitter",
    )
    assert bool(etag2) and bool(etag3)

    store.link_witness(
        event_id,
        peer_id="peer-audit",
        message_id="msg-audit",
        messenger_account="accAudit",
        role="primary",
        actor="actor-linker",
    )

    audit_records = store.get_event_audit(event_id)
    assert len(audit_records) >= 4

    action_map = {record["action"]: record for record in audit_records}
    assert "event.create_draft" in action_map
    assert action_map["event.create_draft"]["actor"] == "actor-creator"

    assert "event.update" in action_map
    assert action_map["event.update"]["actor"] == "actor-updater"

    assert "event.submit_review" in action_map
    assert action_map["event.submit_review"]["actor"] == "actor-submitter"

    assert "witness.link.primary" in action_map
    assert action_map["witness.link.primary"]["actor"] == "actor-linker"

    # Verify no diff contains user fields and only allowed keys are present
    allowed_diff_keys = {"event_id", "changed", "from", "to", "reason", "witness_id", "role"}
    for record in audit_records:
        diff = record["diff"]
        assert set(diff.keys()).issubset(allowed_diff_keys)
        assert "user" not in diff


def test_witness_identity_unique_index_enforced(tmp_path: Path) -> None:
    # Direct SQL insertion tests unique index with COALESCE(messenger_account, '')
    store = _make_store(tmp_path)
    _bootstrap(store)

    # First insertion with empty messenger_account
    with store._connect() as conn:
        conn.execute(
            """
            INSERT INTO reporting_message_witnesses (
                witness_id, provider, messenger_account, peer_id, message_id, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("w-gate-idx-1", "eitaa", "", "p1", "m1", "2026-10-03T12:00:00Z"),
        )

    # Duplicate insertion fails with sqlite3.IntegrityError
    with pytest.raises(sqlite3.IntegrityError):
        with store._connect() as conn:
            conn.execute(
                """
                INSERT INTO reporting_message_witnesses (
                    witness_id, provider, messenger_account, peer_id, message_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                ("w-gate-idx-2", "eitaa", "", "p1", "m1", "2026-10-03T12:00:00Z"),
            )

    # Distinct messenger_account succeeds due to COALESCE index
    with store._connect() as conn:
        conn.execute(
            """
            INSERT INTO reporting_message_witnesses (
                witness_id, provider, messenger_account, peer_id, message_id, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("w-gate-idx-3", "eitaa", "a1", "p1", "m1", "2026-10-03T12:00:00Z"),
        )
        count = conn.execute("SELECT COUNT(*) FROM reporting_message_witnesses").fetchone()[0]
        assert count == 2
