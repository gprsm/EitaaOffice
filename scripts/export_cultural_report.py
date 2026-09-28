#!/usr/bin/env python3
"""Export cultural report Excel spreadsheet with safety timeout."""
from __future__ import annotations

import argparse
import json
import sys
import threading
import time
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


def run_export(
    db_path: Path,
    out_path: Path,
    province: str = "مازندران",
    period: str = "مرداد و شهریور ۱۴۰۵",
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
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
            )
            result["success"] = True
            result["path"] = str(out_file)
            result["size"] = out_file.stat().st_size
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
        default=ROOT / "data" / "reporting" / "reports" / "گزارش_فرهنگی_مرداد_شهریور_۱۴۰۵.xlsx",
        help="Destination Excel path",
    )
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_SECONDS, help="Timeout in seconds")
    args = parser.parse_args()

    res = run_export(args.db, args.out, timeout_seconds=args.timeout)
    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0 if res.get("success") else 1


if __name__ == "__main__":
    sys.exit(main())
