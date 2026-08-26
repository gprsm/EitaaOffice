from __future__ import annotations

from scripts.refresh_project_docs import REPORT_GROUPS, ROOT, build_reports_index


def test_stabilization_reports_are_in_generated_report_index() -> None:
    groups = {
        title: directory.relative_to(ROOT).as_posix()
        for title, directory in REPORT_GROUPS
    }

    assert groups["گزارش‌های تثبیت"] == "docs/reports/stabilization"

    report_index = build_reports_index()
    assert "G00_TRACEABILITY_BASELINE_REPORT_2026-08-25.md" in report_index
    assert "G01_DOCUMENTATION_INTEGRITY_REPORT_2026-08-25.md" in report_index
