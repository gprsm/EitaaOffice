#!/usr/bin/env python3
"""Isolated reporting v5 migration rehearsal and reconciliation checker.

Performs isolated v5 migration against a temporary copy of reporting.sqlite3,
evaluates reconciliation metrics, tests repeatability and constraint enforcement,
and rehearses rollback if requested. Never modifies the source database.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import gc
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile
from typing import Any
import uuid

# Ensure project src is in module search path
REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from eitaa_bridge.reporting.store import REPORTING_SCHEMA_VERSION, ReportingStore

TABLES_TO_CHECK: tuple[str, ...] = (
    "reported_events",
    "event_facts",
    "entity_facts",
    "wp_post_links",
    "filled_forms",
    "event_candidates",
    "index_decisions",
    "reporting_message_witnesses",
    "reporting_event_witness_links",
    "reporting_review_queue",
    "event_documents",
)


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    default_source = Path(__file__).resolve().parents[1] / "data" / "reporting" / "reporting.sqlite3"
    default_workdir = Path(tempfile.gettempdir()) / "eitaa_reporting_v5_check"

    parser = argparse.ArgumentParser(
        description="Isolated reporting v5 migration rehearsal and reconciliation checker.",
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=default_source,
        help="Path to source reporting SQLite database (read-only).",
    )
    parser.add_argument(
        "--workdir",
        type=Path,
        default=default_workdir,
        help="Working directory for isolated database copy and reports.",
    )
    parser.add_argument(
        "--rollback-rehearse",
        action="store_true",
        help="Perform rollback rehearsal using snapshot copy and verify integrity.",
    )
    return parser.parse_args()


def compute_sha256(path: Path) -> str:
    """Compute SHA-256 digest of a file in chunks."""
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def connect_readonly(db_path: Path) -> sqlite3.Connection:
    """Open a read-only SQLite connection using URI."""
    uri = f"file:{db_path.resolve().as_posix()}?mode=ro"
    return sqlite3.connect(uri, uri=True, timeout=30.0)


def table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    """Check if a table exists in the SQLite database."""
    cur = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    )
    return cur.fetchone() is not None


def get_schema_versions(conn: sqlite3.Connection) -> list[int]:
    """Retrieve ordered list of applied schema versions."""
    if not table_exists(conn, "reporting_schema"):
        return []
    cur = conn.execute("SELECT version FROM reporting_schema ORDER BY version ASC")
    return [int(row[0]) for row in cur.fetchall()]


def get_table_counts(conn: sqlite3.Connection) -> dict[str, int | None]:
    """Count rows for each tracked table, returning None if table does not exist."""
    counts: dict[str, int | None] = {}
    for table in TABLES_TO_CHECK:
        if not table_exists(conn, table):
            counts[table] = None
        else:
            cur = conn.execute(f"SELECT COUNT(*) FROM {table}")
            counts[table] = int(cur.fetchone()[0])
    return counts


def get_reconciliation_metrics(conn: sqlite3.Connection) -> dict[str, int]:
    """Compute domain reconciliation metrics after migration."""
    broken_primary_links = 0
    if table_exists(conn, "reported_events") and table_exists(conn, "reporting_event_witness_links"):
        query = """
            SELECT COUNT(*)
            FROM reported_events e
            LEFT JOIN reporting_event_witness_links l
                ON e.event_id = l.event_id
                AND l.role = 'primary'
                AND l.detached_at IS NULL
            WHERE l.link_id IS NULL
        """
        cur = conn.execute(query)
        broken_primary_links = int(cur.fetchone()[0])

    witnesses_without_account = 0
    if table_exists(conn, "reporting_message_witnesses"):
        query = "SELECT COUNT(*) FROM reporting_message_witnesses WHERE messenger_account = ''"
        cur = conn.execute(query)
        witnesses_without_account = int(cur.fetchone()[0])

    media_checksum_count = 0
    if table_exists(conn, "event_documents"):
        query = "SELECT COUNT(*) FROM event_documents"
        cur = conn.execute(query)
        media_checksum_count = int(cur.fetchone()[0])

    return {
        "broken_primary_links": broken_primary_links,
        "witnesses_without_account": witnesses_without_account,
        "media_checksum_count": media_checksum_count,
    }


def verify_unique_constraints(db_path: Path) -> bool:
    """Verify unique constraint on witness identity using an isolated rolled-back transaction."""
    conn = sqlite3.connect(str(db_path.resolve()), timeout=30.0)
    conn.isolation_level = None  # Autocommit mode to allow explicit BEGIN / ROLLBACK
    enforced = False
    try:
        conn.execute("BEGIN TRANSACTION")
        now_ts = datetime.now(timezone.utc).isoformat()
        test_id_1 = f"test-constraint-1-{uuid.uuid4().hex[:8]}"
        test_id_2 = f"test-constraint-2-{uuid.uuid4().hex[:8]}"
        conn.execute(
            """
            INSERT INTO reporting_message_witnesses
            (witness_id, provider, messenger_account, peer_id, message_id, created_at)
            VALUES (?, 'eitaa', '', 'x', '1', ?)
            """,
            (test_id_1, now_ts),
        )
        try:
            conn.execute(
                """
                INSERT INTO reporting_message_witnesses
                (witness_id, provider, messenger_account, peer_id, message_id, created_at)
                VALUES (?, 'eitaa', '', 'x', '1', ?)
                """,
                (test_id_2, now_ts),
            )
            enforced = False
        except sqlite3.IntegrityError:
            enforced = True
        finally:
            conn.execute("ROLLBACK")
    except Exception:
        try:
            conn.execute("ROLLBACK")
        except Exception:
            pass
        raise
    finally:
        conn.close()
    return enforced


def write_json_report(workdir: Path, data: dict[str, Any]) -> Path:
    """Write sanitized JSON reconciliation report."""
    report_path = workdir / "reconciliation_report.json"
    with report_path.open("w", encoding="utf-8") as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)
    return report_path


def write_markdown_report(workdir: Path, data: dict[str, Any]) -> Path:
    """Write Persian markdown summary reconciliation report without absolute paths or identifiers."""
    report_path = workdir / "reconciliation_report.md"
    lines: list[str] = [
        f"# گزارش تطبیق مهاجرت ایزوله نسخه {REPORTING_SCHEMA_VERSION} (Reconciliation Report)",
        "",
        "## جدول شمارش رکوردهای پایگاه داده",
        "",
        "| جدول | قبل | بعد | بازگشایی | وضعیت تطابق |",
        "| :--- | :---: | :---: | :---: | :---: |",
    ]

    table_data = data.get("tables", {})
    for table_name, counts in table_data.items():
        b = str(counts.get("before")) if counts.get("before") is not None else "-"
        a = str(counts.get("after")) if counts.get("after") is not None else "-"
        r = str(counts.get("reopen")) if counts.get("reopen") is not None else "-"
        status = "تطابق دارد" if counts.get("after") == counts.get("reopen") else "عدم تطابق"
        lines.append(f"| {table_name} | {b} | {a} | {r} | {status} |")

    lines.append("")
    lines.append("## سنجه‌های تطبیق و سلامت (Reconciliation Metrics)")
    lines.append("")
    metrics = data.get("reconciliation_metrics", {})
    broken = metrics.get("broken_primary_links", 0)
    no_acc = metrics.get("witnesses_without_account", 0)
    enforced = "enforced: true" if metrics.get("unique_constraints_enforced") else "enforced: false"
    media = metrics.get("media_checksum_count", 0)

    lines.append(f"- **پیوندهای شکسته (رویدادهای بدون پیوند اصلی فعال):** {broken}")
    lines.append(f"- **شواهد بدون حساب (messenger_account = ''):** {no_acc}")
    lines.append(f"- **وضعیت قیود یکتایی (Unique Constraints):** {enforced}")
    lines.append(f"- **چک‌سام رسانه (event_documents):** {media}")
    lines.append("")
    lines.append("## تکرارپذیری (Repeatability)")
    lines.append("")
    repeatability = data.get("repeatability", {})
    rep_status = repeatability.get("status", "FAIL")
    v5_rows = repeatability.get("v5_row_count", 0)
    counts_matched = "تایید شد" if repeatability.get("counts_match") else "عدم تطابق"

    lines.append(f"- **تطابق شمارش بعد از بازگشایی مجدد (Reopen == After):** {counts_matched}")
    lines.append(f"- **تعداد رکوردهای نسخه {REPORTING_SCHEMA_VERSION} در reporting_schema:** {v5_rows}")
    lines.append(f"- **نتیجه تکرارپذیری:** {rep_status}")
    lines.append("")
    lines.append("## تمرین بازگشت (Rollback Rehearsal)")
    lines.append("")
    rollback = data.get("rollback_rehearsal", {})
    if rollback.get("executed"):
        rb_sha = "تایید شد" if rollback.get("sha256_match") else "عدم تطابق"
        rb_ver = "تایید شد" if rollback.get("versions_match") else "عدم تطابق"
        rb_res = rollback.get("status", "FAIL")
        lines.append("- **اجرای تمرین بازگشت:** انجام شد")
        lines.append(f"- **تطابق هش SHA-256 فایل با اسنپ‌شات:** {rb_sha}")
        lines.append(f"- **تطابق نسخه‌های اسکیما با اسنپ‌شات:** {rb_ver}")
        lines.append(f"- **نتیجه تمرین بازگشت:** {rb_res}")
    else:
        lines.append("- **اجرای تمرین بازگشت:** انجام نشد (پرچم --rollback-rehearse ارسال نشده است)")

    lines.append("")
    lines.append("## نتیجه نهایی")
    lines.append("")
    overall = data.get("overall_status", "FAIL")
    lines.append(f"وضعیت کلی: **{overall}**")
    lines.append("")

    with report_path.open("w", encoding="utf-8") as stream:
        stream.write("\n".join(lines))
    return report_path


def main() -> None:
    """Orchestrate isolated v5 migration, verification, and reporting."""
    args = parse_args()
    source: Path = args.source
    workdir: Path = args.workdir
    rollback_rehearse: bool = args.rollback_rehearse

    # Step 2a: Check source existence
    if not source.exists():
        sys.stderr.write(f"Error: Source database file not found: {source}\n")
        sys.exit(2)

    # Step 2a: Read BEFORE counts via read-only URI without making adjacent backup
    conn_before = connect_readonly(source)
    try:
        before_versions = get_schema_versions(conn_before)
        before_counts = get_table_counts(conn_before)
    finally:
        conn_before.close()

    # Step 2b: Create workdir and copy source to isolated.sqlite3
    workdir.mkdir(parents=True, exist_ok=True)
    isolated_db = workdir / "isolated.sqlite3"
    shutil.copy2(source, isolated_db)

    # Step 2c: Create rollback snapshot and capture sha256 + schema versions
    snapshot_path = workdir / "isolated.sqlite3.snapshot"
    shutil.copy2(isolated_db, snapshot_path)
    snapshot_sha256 = compute_sha256(snapshot_path)

    conn_snap = connect_readonly(snapshot_path)
    try:
        snapshot_versions = get_schema_versions(conn_snap)
    finally:
        conn_snap.close()

    # Step 2d: Apply migration via ReportingStore instance
    store = ReportingStore(isolated_db)
    del store
    gc.collect()

    conn_after = connect_readonly(isolated_db)
    try:
        after_counts = get_table_counts(conn_after)
        after_versions = get_schema_versions(conn_after)
        recon_metrics = get_reconciliation_metrics(conn_after)
    finally:
        conn_after.close()

    constraints_enforced = verify_unique_constraints(isolated_db)

    # Step 2e: Repeatability check (reopen store on same file)
    store_reopen = ReportingStore(isolated_db)
    del store_reopen
    gc.collect()

    conn_reopen = connect_readonly(isolated_db)
    try:
        reopen_counts = get_table_counts(conn_reopen)
        reopen_versions = get_schema_versions(conn_reopen)
        cur = conn_reopen.execute(
            "SELECT COUNT(*) FROM reporting_schema WHERE version = ?",
            (REPORTING_SCHEMA_VERSION,),
        )
        v5_row_count = int(cur.fetchone()[0])
    finally:
        conn_reopen.close()

    repeatability_counts_match = (after_counts == reopen_counts)
    repeatability_passed = repeatability_counts_match and (v5_row_count == 1)

    # Step 2f: Rollback rehearsal if requested
    rollback_data: dict[str, Any] = {
        "executed": rollback_rehearse,
        "passed": None,
        "status": "SKIPPED",
    }
    rollback_passed = True

    if rollback_rehearse:
        gc.collect()
        shutil.copy2(snapshot_path, isolated_db)
        for suffix in ("-wal", "-shm", "-journal"):
            wal_file = workdir / f"isolated.sqlite3{suffix}"
            wal_file.unlink(missing_ok=True)

        conn_rb = connect_readonly(isolated_db)
        try:
            rb_versions = get_schema_versions(conn_rb)
        finally:
            conn_rb.close()

        rb_sha256 = compute_sha256(isolated_db)
        sha256_match = (rb_sha256 == snapshot_sha256)
        versions_match = (rb_versions == snapshot_versions)
        rollback_passed = sha256_match and versions_match

        rollback_data = {
            "executed": True,
            "passed": rollback_passed,
            "status": "PASS" if rollback_passed else "FAIL",
            "sha256_match": sha256_match,
            "versions_match": versions_match,
            "snapshot_sha256": snapshot_sha256,
            "rollback_sha256": rb_sha256,
            "snapshot_versions": snapshot_versions,
            "rollback_versions": rb_versions,
        }

    # Step 2g: Generate sanitized reports
    overall_passed = (
        repeatability_counts_match
        and (v5_row_count == 1)
        and constraints_enforced
        and rollback_passed
    )

    tables_summary: dict[str, dict[str, int | None]] = {}
    for tbl in TABLES_TO_CHECK:
        tables_summary[tbl] = {
            "before": before_counts.get(tbl),
            "after": after_counts.get(tbl),
            "reopen": reopen_counts.get(tbl),
        }

    report_payload: dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source_basename": source.name,
        "schema_versions": {
            "before": before_versions,
            "after": after_versions,
            "reopen": reopen_versions,
        },
        "tables": tables_summary,
        "reconciliation_metrics": {
            "broken_primary_links": recon_metrics["broken_primary_links"],
            "witnesses_without_account": recon_metrics["witnesses_without_account"],
            "unique_constraints_enforced": constraints_enforced,
            "media_checksum_count": recon_metrics["media_checksum_count"],
        },
        "repeatability": {
            "passed": repeatability_passed,
            "status": "PASS" if repeatability_passed else "FAIL",
            "counts_match": repeatability_counts_match,
            "v5_row_count": v5_row_count,
        },
        "rollback_rehearsal": rollback_data,
        "overall_status": "PASS" if overall_passed else "FAIL",
    }

    json_report_path = write_json_report(workdir, report_payload)
    md_report_path = write_markdown_report(workdir, report_payload)

    # Step 2h: Print status and exit
    status_label = "PASS" if overall_passed else "FAIL"
    print(f"{status_label}: {json_report_path.resolve()} | {md_report_path.resolve()}")
    sys.exit(0 if overall_passed else 1)


if __name__ == "__main__":
    main()
