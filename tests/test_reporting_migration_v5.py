"""Migration v5 tests: witness layer, typed facts, review lifecycle (phase 1 of the unified reporting strategy)."""

from __future__ import annotations

from datetime import date
from pathlib import Path
import sqlite3
import subprocess
import sys
import pytest

from eitaa_bridge.reporting import ReportingStore
from eitaa_bridge.reporting.model import (
    Fact,
    FactValueKind,
    ProgramKind,
    ReportedEvent,
    UnitScope,
    ValueSource,
)


@pytest.fixture
def store(tmp_path: Path) -> ReportingStore:
    db_file = tmp_path / "test_reporting_v5.db"
    return ReportingStore(db_file)


def _make_event(event_id: str = "evt-test-1") -> ReportedEvent:
    """Helper to construct a minimal ReportedEvent instance for tests."""
    return ReportedEvent(
        event_id=event_id,
        program_kinds=(ProgramKind.CEREMONY,),
        occurred_on=date(2026, 6, 15),
        unit=UnitScope.JUDICIAL_DOMAIN,
        unit_name="Test Judicial Unit",
        created_by="test-suite",
    )


def test_v5_schema_objects_created(store: ReportingStore) -> None:
    # Check that new v5 tables exist
    expected_tables = {
        "reporting_message_witnesses",
        "reporting_event_witness_links",
        "reporting_review_queue",
        "event_documents",
    }
    with sqlite3.connect(store.db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        existing_tables = {row[0] for row in cursor.fetchall()}
        for table in expected_tables:
            assert table in existing_tables, f"Table '{table}' not found in schema"

        # Check column review_status on reported_events
        cursor.execute("PRAGMA table_info(reported_events)")
        reported_events_cols = {row[1] for row in cursor.fetchall()}
        assert "review_status" in reported_events_cols

        # Check columns value_type and value_decimal on event_facts
        cursor.execute("PRAGMA table_info(event_facts)")
        event_facts_cols = {row[1] for row in cursor.fetchall()}
        assert "value_type" in event_facts_cols
        assert "value_decimal" in event_facts_cols

        # Check columns value_type and value_decimal on entity_facts
        cursor.execute("PRAGMA table_info(entity_facts)")
        entity_facts_cols = {row[1] for row in cursor.fetchall()}
        assert "value_type" in entity_facts_cols
        assert "value_decimal" in entity_facts_cols

        # Check version 5 in reporting_schema
        cursor.execute("SELECT version FROM reporting_schema")
        versions = cursor.fetchall()
        assert versions == [(5,)], f"Expected [(5,)], got {versions}"


def test_witness_identity_unique(store: ReportingStore) -> None:
    with sqlite3.connect(store.db_path) as conn:
        # Insert initial witness
        conn.execute(
            """
            INSERT INTO reporting_message_witnesses (
                witness_id, provider, messenger_account, peer_id, message_id, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("w1", "eitaa", "", "p1", "m1", "2026-06-15T10:00:00Z"),
        )
        conn.commit()

        # Duplicate identity with different witness_id should fail
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """
                INSERT INTO reporting_message_witnesses (
                    witness_id, provider, messenger_account, peer_id, message_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                ("w2", "eitaa", "", "p1", "m1", "2026-06-15T10:00:00Z"),
            )
            conn.commit()

        # Same peer/message but distinct messenger_account should succeed
        conn.execute(
            """
            INSERT INTO reporting_message_witnesses (
                witness_id, provider, messenger_account, peer_id, message_id, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("w3", "eitaa", "acc1", "p1", "m1", "2026-06-15T10:00:00Z"),
        )
        conn.commit()


def test_single_active_primary_link(store: ReportingStore) -> None:
    event1 = _make_event("evt-link-1")
    event2 = _make_event("evt-link-2")
    store.save_event(event1)
    store.save_event(event2)

    with sqlite3.connect(store.db_path) as conn:
        # Raw insert witness w1
        conn.execute(
            """
            INSERT INTO reporting_message_witnesses (
                witness_id, provider, messenger_account, peer_id, message_id, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("w1", "eitaa", "", "p1", "m1", "2026-06-15T10:00:00Z"),
        )

        # Primary link to event1
        conn.execute(
            """
            INSERT INTO reporting_event_witness_links (
                link_id, event_id, witness_id, role, linked_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            ("l1", event1.event_id, "w1", "primary", "2026-06-15T10:00:00Z"),
        )
        conn.commit()

        # Second active primary link for same witness w1 should raise IntegrityError
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """
                INSERT INTO reporting_event_witness_links (
                    link_id, event_id, witness_id, role, linked_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                ("l2", event2.event_id, "w1", "primary", "2026-06-15T10:05:00Z"),
            )
            conn.commit()

        # Supporting link to event2 should succeed
        conn.execute(
            """
            INSERT INTO reporting_event_witness_links (
                link_id, event_id, witness_id, role, linked_at, note
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("l3", event2.event_id, "w1", "supporting", "2026-06-15T10:06:00Z", "reason"),
        )
        conn.commit()

        # Detach l1
        conn.execute(
            "UPDATE reporting_event_witness_links SET detached_at = ? WHERE link_id = ?",
            ("2026-06-15T10:10:00Z", "l1"),
        )
        conn.commit()

        # Detach the active supporting link too — one active (event, witness) pair only
        conn.execute(
            "UPDATE reporting_event_witness_links SET detached_at = ? WHERE link_id = ?",
            ("2026-06-15T10:12:00Z", "l3"),
        )
        conn.commit()

        # Primary link to event2 should now succeed
        conn.execute(
            """
            INSERT INTO reporting_event_witness_links (
                link_id, event_id, witness_id, role, linked_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            ("l4", event2.event_id, "w1", "primary", "2026-06-15T10:15:00Z"),
        )
        conn.commit()


def test_legacy_backfill_creates_review_items(tmp_path: Path) -> None:
    db_file = tmp_path / "legacy_backfill.db"
    store = ReportingStore(db_file)

    # Raw insert legacy event without specifying review_status (uses default needs_review)
    with sqlite3.connect(store.db_path) as conn:
        conn.execute(
            """
            INSERT INTO reported_events (
                event_id, program_kinds_json, occurred_on, unit, unit_name, created_at, created_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            ("ev-legacy-x", '["trip"]', "2026-06-15", "judicial_domain", "Test Unit", "2026-06-15T00:00:00Z", "test-suite"),
        )
        conn.commit()

    # Re-instantiate store to trigger legacy backfill logic
    store2 = ReportingStore(db_file)

    with sqlite3.connect(store2.db_path) as conn:
        row = conn.execute(
            "SELECT queue_id, item_type, status FROM reporting_review_queue WHERE queue_id = ?",
            ("rq-legacy-ev-legacy-x",),
        ).fetchone()
        assert row is not None, "Expected review queue item for legacy event was not found"
        assert row[0] == "rq-legacy-ev-legacy-x"
        assert row[1] == "legacy_event_review"
        assert row[2] == "open"

    # Re-instantiate again and verify idempotency (still exactly one row)
    store3 = ReportingStore(db_file)
    with sqlite3.connect(store3.db_path) as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM reporting_review_queue WHERE queue_id = ?",
            ("rq-legacy-ev-legacy-x",),
        ).fetchone()[0]
        assert count == 1, f"Expected exactly 1 review item, got {count}"


def test_new_event_is_draft_and_resave_preserves_status(store: ReportingStore) -> None:
    event = _make_event("evt-draft-test")
    store.save_event(event)

    with sqlite3.connect(store.db_path) as conn:
        status = conn.execute(
            "SELECT review_status FROM reported_events WHERE event_id = ?",
            ("evt-draft-test",),
        ).fetchone()[0]
        assert status == "draft"

        # Update status to approved directly via raw SQL
        conn.execute(
            "UPDATE reported_events SET review_status = 'approved' WHERE event_id = ?",
            ("evt-draft-test",),
        )
        conn.commit()

    # Re-save the same event
    store.save_event(event)

    # Ensure status was preserved and not overwritten to draft
    with sqlite3.connect(store.db_path) as conn:
        status_after = conn.execute(
            "SELECT review_status FROM reported_events WHERE event_id = ?",
            ("evt-draft-test",),
        ).fetchone()[0]
        assert status_after == "approved"


def test_typed_fact_columns_defaults(store: ReportingStore) -> None:
    event = _make_event("evt-fact-test")
    fact = Fact(
        metric="attendees",
        value=75.0,
        value_kind=FactValueKind.VERIFIED,
        source=ValueSource.EITAA,
    )
    event.add_fact(fact)
    store.save_event(event)

    with sqlite3.connect(store.db_path) as conn:
        row = conn.execute(
            "SELECT value_type, value_decimal FROM event_facts WHERE event_id = ? AND metric = ?",
            ("evt-fact-test", "attendees"),
        ).fetchone()
        assert row is not None, "Fact row not found in event_facts"
        assert row[0] == "unknown"
        assert row[1] is None


def test_isolated_migration_script_rollback(tmp_path: Path) -> None:
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "migrate_reporting_v5_isolated.py"
    src = tmp_path / "test_src.db"
    workdir = tmp_path / "work"

    # Setup test source database: create schema via ReportingStore, insert legacy event, then strip v5 objects
    store = ReportingStore(src)
    with sqlite3.connect(store.db_path) as conn:
        conn.execute(
            """
            INSERT INTO reported_events (
                event_id, program_kinds_json, occurred_on, unit, unit_name, created_at, created_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            ("ev-legacy-rollback", '["trip"]', "2026-06-15", "judicial_domain", "Test Unit", "2026-06-15T00:00:00Z", "test-suite"),
        )
        conn.execute("DELETE FROM reporting_schema WHERE version = 5")
        conn.execute("DROP TABLE IF EXISTS reporting_message_witnesses")
        conn.execute("DROP TABLE IF EXISTS reporting_event_witness_links")
        conn.execute("DROP TABLE IF EXISTS reporting_review_queue")
        conn.execute("DROP TABLE IF EXISTS event_documents")
        conn.commit()

    cmd = [
        sys.executable,
        str(script_path),
        "--rollback-rehearse",
        "--source",
        str(src),
        "--workdir",
        str(workdir),
    ]
    proc = subprocess.run(cmd, capture_output=True, timeout=120)
    stdout = proc.stdout.decode("utf-8", errors="replace")
    stderr = proc.stderr.decode("utf-8", errors="replace")

    assert proc.returncode == 0, (
        f"Migration script failed with exit code {proc.returncode}.\n"
        f"STDOUT:\n{stdout}\n"
        f"STDERR:\n{stderr}"
    )

    report_file = workdir / "reconciliation_report.md"
    assert report_file.exists(), (
        f"Expected reconciliation report file was not found at {report_file}.\n"
        f"STDOUT:\n{stdout}\n"
        f"STDERR:\n{stderr}"
    )
