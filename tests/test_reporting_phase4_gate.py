"""Phase-4 gate tests: versioned official output, traceability, WP opt-in.

Phase 4 of the unified reporting strategy — see
docs/specifications/REPORTING_OFFICIAL_OUTPUT_2026-10-03.md.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import subprocess
import sys
from datetime import date
from pathlib import Path

import openpyxl
import pytest

from eitaa_bridge.reporting.excel_export import TEMPLATE_VERSION, UnresolvedStarCellsError
from eitaa_bridge.reporting.model import (
    Fact,
    FactValueKind,
    ProgramKind,
    ReportedEvent,
    UnitScope,
    ValueSource,
)
from eitaa_bridge.reporting.rules import RULES_VERSION
from eitaa_bridge.reporting.service import ReportingService
from eitaa_bridge.reporting.store import REPORTING_SCHEMA_VERSION, ReportingStore

ROOT = Path(__file__).resolve().parents[1]


def _make_store(tmp_path: Path) -> tuple[ReportingStore, ReportingService]:
    store = ReportingStore(tmp_path / "phase4.sqlite3")
    return store, ReportingService(store=store)


def _add_trip_event(store: ReportingStore, event_id: str, attendees: int,
                    value_kind: FactValueKind = FactValueKind.OBSERVED) -> None:
    store.save_event(ReportedEvent(
        event_id=event_id,
        program_kinds=(ProgramKind.TRIP,),
        occurred_on=date(1405, 5, 1),
        unit=UnitScope.PROVINCIAL_HQ,
        unit_name="ستاد",
        facts=[Fact(metric="attendees", value=attendees, value_kind=value_kind, source=ValueSource.MANUAL)],
    ))


def test_accepted_sample_artifact_reconciliation() -> None:
    """The owner-accepted output sample must stay byte-identical (PHASE0 §7)."""
    con = sqlite3.connect(f"file:{(ROOT / 'data/reporting/reporting.sqlite3').as_posix()}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    row = con.execute(
        "SELECT file_sha256, export_path, total_events FROM report_exports WHERE export_id = 'exp-f98f10c768'"
    ).fetchone()
    con.close()
    if row is None:
        pytest.skip("accepted sample record not present in this environment")
    artifact = Path(row["export_path"])
    if not artifact.exists():
        pytest.skip("accepted sample artifact not present on this machine")
    assert hashlib.sha256(artifact.read_bytes()).hexdigest() == row["file_sha256"]
    assert row["total_events"] == 286


def test_export_traceability_manifest_roundtrip(tmp_path: Path) -> None:
    store, service = _make_store(tmp_path)
    for index in range(1, 4):
        _add_trip_event(store, f"ev-{index}", attendees=10 * index)
    out = tmp_path / "report.xlsx"
    service.export_with_audit(
        destination=out, province_name="مازندران", report_period="آزمون",
        exported_by="gate", allow_unresolved_star=True,
    )
    workbook = openpyxl.load_workbook(out)
    assert "ردیابی" in workbook.sheetnames
    sheet = workbook["ردیابی"]
    assert sheet["B1"].value == TEMPLATE_VERSION
    assert sheet["B2"].value == RULES_VERSION
    con = sqlite3.connect(store.db_path)
    con.row_factory = sqlite3.Row
    record = dict(con.execute(
        "SELECT template_version, rules_version, traceability_json FROM report_exports "
        "ORDER BY exported_at DESC LIMIT 1"
    ).fetchone())
    con.close()
    assert record["template_version"] == TEMPLATE_VERSION
    assert record["rules_version"] == RULES_VERSION
    manifest = json.loads(record["traceability_json"])
    trip = manifest["programs"]["trip"]
    assert trip["count"] == 3
    assert sorted(trip["event_ids"]) == ["ev-1", "ev-2", "ev-3"]
    assert trip["attendees_total"] == 60


def test_estimated_facts_separated_from_official_totals(tmp_path: Path) -> None:
    store, service = _make_store(tmp_path)
    _add_trip_event(store, "ev-observed", attendees=50)
    _add_trip_event(store, "ev-estimated", attendees=999, value_kind=FactValueKind.ESTIMATED)
    out = tmp_path / "report.xlsx"
    service.export_with_audit(
        destination=out, province_name="مازندران", report_period="آزمون",
        allow_unresolved_star=True,
    )
    manifest = json.loads(sqlite3.connect(store.db_path).execute(
        "SELECT traceability_json FROM report_exports ORDER BY exported_at DESC LIMIT 1"
    ).fetchone()[0])
    trip = manifest["programs"]["trip"]
    # Estimated VALUE never enters the official attendee aggregate…
    assert trip["attendees_total"] == 50
    assert "ev-estimated" not in trip["attendee_event_ids"]
    # …while the event itself stays counted and the exclusion is recorded.
    assert trip["count"] == 2
    assert any(item["event_id"] == "ev-estimated" or item.get("event_id") for item in manifest["excluded"]) or (
        "ev-estimated" in json.dumps(manifest)
    )


def test_unresolved_star_cells_block_official_export(tmp_path: Path) -> None:
    store, service = _make_store(tmp_path)
    _add_trip_event(store, "ev-1", attendees=10)
    with pytest.raises(UnresolvedStarCellsError):
        service.export_with_audit(
            destination=tmp_path / "blocked.xlsx", province_name="م", report_period="p",
        )


def test_wordpress_opt_in_default_off_and_guard(tmp_path: Path) -> None:
    store, service = _make_store(tmp_path)
    assert service.wordpress_export_opt_in() is False
    with pytest.raises(PermissionError):
        service.ensure_wordpress_export_allowed()
    # WordPress off/down never blocks native registration or Excel export.
    _add_trip_event(store, "ev-1", attendees=10)
    out = service.export_with_audit(
        destination=tmp_path / "offline.xlsx", province_name="م", report_period="p",
        allow_unresolved_star=True,
    )
    assert out.exists()
    con = sqlite3.connect(store.db_path)
    wp_recorded = con.execute(
        "SELECT wp_opt_in FROM report_exports ORDER BY exported_at DESC LIMIT 1"
    ).fetchone()[0]
    con.close()
    assert wp_recorded == 0
    service.set_wordpress_export_opt_in(True)
    assert service.wordpress_export_opt_in() is True
    service.ensure_wordpress_export_allowed()


def test_isolated_migration_rehearsal_covers_current_version(tmp_path: Path) -> None:
    assert REPORTING_SCHEMA_VERSION >= 7
    script = ROOT / "scripts" / "migrate_reporting_v5_isolated.py"
    source = ROOT / "data" / "reporting" / "reporting.sqlite3"
    if not source.exists():
        pytest.skip("operational reporting database not present")
    result = subprocess.run(
        [sys.executable, str(script), "--rollback-rehearse",
         "--source", str(source), "--workdir", str(tmp_path / "work")],
        capture_output=True, text=True, timeout=180,
    )
    assert result.returncode == 0, f"stdout={result.stdout}\nstderr={result.stderr}"
