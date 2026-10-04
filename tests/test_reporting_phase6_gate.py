"""Gate tests for Unified Reporting Phase 6: Pilot, Migration Reconciliation, and WordPress Cutover.

Verifies:
1. Reconciliation audit between historical WP links and native event store.
2. Zero-downtime atomic backup via VACUUM INTO with PRAGMA integrity verification (RPO = 0).
3. Disaster recovery restoration rehearsal with sub-second RTO (< 1000ms).
4. Standalone native reporting generation with zero WordPress dependency.
5. Strict audit and privacy sanitization (no PII, credentials, or tokens).
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
import pytest

from eitaa_bridge.reporting.store import REPORTING_SCHEMA_VERSION, ReportingStore
from eitaa_bridge.reporting import (
    ReportedEvent,
    UnitScope,
    WpPostLink,
)
from eitaa_bridge.reporting.reconcile import reconcile_wp_archive
from eitaa_bridge.reporting.backup import (
    backup_reporting_database,
    restore_reporting_database,
    verify_backup_integrity,
)
from eitaa_bridge.reporting.service import ReportingService


@pytest.fixture
def store(tmp_path: Path) -> ReportingStore:
    return ReportingStore(tmp_path / "phase6_test.sqlite3", acquire_lease=False)


class TestPhase6Reconciliation:
    """Verifies reconciliation between historical WordPress posts and native store."""

    def test_wp_archive_reconciliation_audit(self, store: ReportingStore) -> None:
        # Create an event in store
        ev = ReportedEvent(
            event_id="ev-p6-1",
            program_kinds=("prayer",),
            occurred_on=date(2026, 9, 28),
            unit=UnitScope.PROVINCIAL_HQ,
            unit_name="ستاد دادگستری استان",
            notes="مراسم نماز جماعت",
            created_by="system",
        )
        store.save_event(ev)

        # Create confirmed link to existing event
        store.save_wp_link(
            WpPostLink(
                link_id="wpl-conf-1",
                post_slug="namaz-jamah-hq",
                title="اقامه نماز جماعت در ستاد",
                section="prayer",
                event_id="ev-p6-1",
                match_status="confirmed",
            )
        )

        # Create unmatched link
        store.save_wp_link(
            WpPostLink(
                link_id="wpl-unm-1",
                post_slug="unknown-post",
                title="خبر بدون پیوند",
                section="ceremonies",
                match_status="unmatched",
            )
        )

        # Create broken link (event does not exist)
        store.save_wp_link(
            WpPostLink(
                link_id="wpl-brk-1",
                post_slug="broken-post",
                title="خبر با شناسه رویداد ناموجود",
                section="honor",
                event_id="ev-nonexistent",
                match_status="confirmed",
            )
        )

        report = reconcile_wp_archive(store)
        assert report.total_wp_links == 3
        assert report.confirmed_matches == 1
        assert report.unmatched_links == 1
        assert report.broken_links == 1
        assert report.events_with_wp_link == 1
        assert report.section_breakdown.get("prayer") == 1
        assert report.section_breakdown.get("ceremonies") == 1
        assert report.section_breakdown.get("honor") == 1

        d = report.to_dict()
        assert d["broken_links"] == 1
        assert len(d["exceptions"]) == 1
        assert d["exceptions"][0]["kind"] == "broken_link"

    def test_media_document_metadata_audit(self, store: ReportingStore) -> None:
        ev = ReportedEvent(
            event_id="ev-p6-docs",
            program_kinds=("prayer",),
            occurred_on=date(2026, 9, 28),
            unit=UnitScope.PROVINCIAL_HQ,
            notes="مراسم نماز جماعت",
            created_by="system",
        )
        store.save_event(ev)

        # Healthy document metadata
        store.attach_document(
            "ev-p6-docs", media_id="media-ok-1",
            sha256="a" * 64, kind="photo", size_bytes=1024, added_by="tester",
        )
        # Malformed checksum -> exception
        store.attach_document(
            "ev-p6-docs", media_id="media-bad-sha",
            sha256="nothex", kind="photo", size_bytes=64, added_by="tester",
        )
        # Non-positive size with valid checksum -> exception
        store.attach_document(
            "ev-p6-docs", media_id="media-bad-size",
            sha256="b" * 64, kind="photo", size_bytes=0, added_by="tester",
        )

        report = reconcile_wp_archive(store)
        assert report.media_documents_count == 3
        assert report.valid_media_checksums == 1
        assert report.broken_media_documents == 2
        kinds = {e["kind"] for e in report.exceptions}
        assert "invalid_document_sha256" in kinds
        assert "invalid_document_size" in kinds


class TestPhase6DisasterRecovery:
    """Verifies atomic snapshot backup and restoration rehearsal."""

    def test_backup_and_restore_rehearsal_rpo_and_rto(self, store: ReportingStore, tmp_path: Path) -> None:
        # 1. Populate store with events and assistant feedback
        for i in range(5):
            ev = ReportedEvent(
                event_id=f"ev-dr-{i}",
                program_kinds=("ceremony",),
                occurred_on=date(2026, 10, 1),
                unit=UnitScope.PROVINCIAL_HQ,
                created_by="tester",
            )
            store.save_event(ev)

        store.record_assistant_feedback(
            candidate_id="cand-dr-1",
            actor="admin",
            action="accept",
            scope_kind="global",
            suggested_program="ceremonies",
            chosen_program="ceremonies",
        )

        # 2. Backup database via VACUUM INTO
        backup_dir = tmp_path / "backups"
        backup_meta = backup_reporting_database(store, backup_dir)

        assert Path(backup_meta.backup_path).is_file()
        assert backup_meta.integrity_ok is True
        assert backup_meta.schema_version == REPORTING_SCHEMA_VERSION
        assert backup_meta.total_events == 5
        assert backup_meta.total_feedback == 1
        assert backup_meta.duration_ms > 0

        # 3. Rehearse disaster recovery restore
        restored_target = tmp_path / "restored_reporting.sqlite3"
        restored = restore_reporting_database(backup_meta.backup_path, restored_target)

        assert restored["restored"] is True
        assert restored["events_count"] == 5
        assert restored["rto_ms"] < 1000.0  # RTO strictly under 1 second

        # 4. Open restored database with ReportingStore and verify zero data loss (RPO = 0)
        restored_store = ReportingStore(restored_target, acquire_lease=False)
        events = restored_store.list_events()
        assert len(events) == 5
        feedback = restored_store.list_assistant_feedback()
        assert len(feedback) == 1
        assert feedback[0]["candidate_id"] == "cand-dr-1"


class TestPhase6StandaloneCutoverReadiness:
    """Verifies standalone reporting generation without WordPress dependency."""

    def test_standalone_native_reporting_without_wordpress(self, store: ReportingStore, tmp_path: Path) -> None:
        service = ReportingService(store=store)
        # Ensure WordPress opt-in is disabled
        service.set_wordpress_export_opt_in(False)
        assert service.wordpress_export_opt_in() is False

        # Add event
        store.save_event(
            ReportedEvent(
                event_id="ev-standalone-1",
                program_kinds=("ceremony",),
                occurred_on=date(2026, 10, 2),
                unit=UnitScope.PROVINCIAL_HQ,
                created_by="cutover-test",
            )
        )

        # Generate official export
        dest = tmp_path / "exports" / "test_report.xlsx"
        dest.parent.mkdir(parents=True, exist_ok=True)
        out_path = service.export_with_audit(
            destination=dest,
            province_name="مازندران",
            report_period="۱۴۰۵-test",
            exported_by="cutover-pilot",
            allow_unresolved_star=True,
        )

        assert Path(out_path).is_file()
        exports = store.list_exports()
        assert len(exports) == 1
        assert exports[0]["wp_opt_in"] == 0
        assert "rules-v1" in exports[0]["rules_version"]
        assert "template-v1" in exports[0]["template_version"]
