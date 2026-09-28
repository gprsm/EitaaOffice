#!/usr/bin/env python3
"""Export cultural report Excel spreadsheet with safety timeout.

Supports an optional time window (بازهٔ زمانی): ``--from-date``/``--to-date``
restrict the workbook to events inside the window; aggregates are recomputed
from that window only and period-wide saved forms are excluded so a subrange
never inherits whole-period totals (F-095).
"""
from __future__ import annotations

import argparse
import json
import sys
import threading
from datetime import date
from pathlib import Path

# Ensure UTF-8 output on Windows
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
    try:
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from eitaa_bridge.reporting.service import ReportingService
from eitaa_bridge.reporting.store import ReportingStore

DEFAULT_TIMEOUT_SECONDS = 45.0
DEFAULT_OUT_NAME = "گزارش_فرهنگی_مرداد_شهریور_۱۴۰۵.xlsx"


def run_export(
    db_path: Path,
    out_path: Path,
    province: str = "مازندران",
    period: str = "مرداد و شهریور ۱۴۰۵",
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    date_from: str = "",
    date_to: str = "",
) -> dict[str, object]:
    result: dict[str, object] = {"success": False}
    error_container: list[Exception] = []

    def _target():
        try:
            store = ReportingStore(db_path)
            service = ReportingService(store=store)
            out_file = service.export_with_audit(
                destination=out_path,
                province_name=province,
                report_period=period,
                allow_unresolved_star=True,
                exported_by="cultural_portal",
                date_from=date_from or None,
                date_to=date_to or None,
            )
            result["success"] = True
            result["path"] = str(out_file)
            result["filename"] = out_file.name
            result["size"] = out_file.stat().st_size
            result["date_from"] = date_from
            result["date_to"] = date_to
            result["period"] = period
        except Exception as exc:
            error_container.append(exc)

    worker = threading.Thread(target=_target, daemon=True)
    worker.start()
    worker.join(timeout=timeout_seconds)

    if worker.is_alive():
        result["error"] = f"Export operation timed out after {timeout_seconds}s; aborted to prevent infinite hang."
        result["timed_out"] = True
        return result

    if error_container:
        result["error"] = str(error_container[0])
        return result

    return result


def _parse_iso_date(value: str, flag: str) -> str:
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError as exc:
        raise SystemExit(f"خطا: مقدار {flag} باید تاریخ میلادی ISO به شکل YYYY-MM-DD باشد ({value!r}).") from exc


def main() -> int:
    parser = argparse.ArgumentParser(description="Export official 1405 cultural report Excel file.")
    parser.add_argument(
        "--db",
        type=Path,
        default=ROOT / "data" / "reporting" / "reporting.sqlite3",
        help="Path to reporting.sqlite3 database",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Destination Excel path (default: reports dir, suffixed with the window when ranged)",
    )
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_SECONDS, help="Timeout in seconds")
    parser.add_argument(
        "--from-date",
        dest="from_date",
        default="",
        help="Window start, ISO gregorian YYYY-MM-DD (events on/after this day)",
    )
    parser.add_argument(
        "--to-date",
        dest="to_date",
        default="",
        help="Window end, ISO gregorian YYYY-MM-DD (events on/before this day)",
    )
    parser.add_argument(
        "--period-label",
        dest="period_label",
        default="",
        help="Human-readable jalali label printed on the report (e.g. «۱۴۰۵/۰۵/۰۱ تا ۱۴۰۵/۰۵/۳۱»)",
    )
    args = parser.parse_args()

    date_from = _parse_iso_date(args.from_date, "--from-date") if args.from_date else ""
    date_to = _parse_iso_date(args.to_date, "--to-date") if args.to_date else ""
    if date_from and date_to and date_from > date_to:
        raise SystemExit("خطا: ابتدای بازهٔ زمانی نمی‌تواند بعد از پایان آن باشد.")

    out_path = args.out
    if out_path is None:
        reports_dir = ROOT / "data" / "reporting" / "reports"
        if date_from or date_to:
            # Filesystem-safe name: ISO dates carry no slashes.
            span = "_تا_".join(part for part in (date_from, date_to) if part)
            out_path = reports_dir / f"گزارش_فرهنگی_{span}.xlsx"
        else:
            out_path = reports_dir / DEFAULT_OUT_NAME

    period_label = args.period_label or (
        " تا ".join(part for part in (date_from, date_to) if part)
        if (date_from or date_to)
        else "مرداد و شهریور ۱۴۰۵"
    )

    res = run_export(
        args.db,
        out_path,
        timeout_seconds=args.timeout,
        date_from=date_from,
        date_to=date_to,
        period=period_label,
    )
    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0 if res.get("success") else 1


if __name__ == "__main__":
    sys.exit(main())
