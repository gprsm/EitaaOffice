"""Tests for Official Cultural Program Catalog (کاتالوگ سرفصل‌های برنامه‌های فرهنگی)

Verifies:
1. Unified schema with multi-year lifecycle (`valid_from_year`, `valid_to_year`, `is_active` soft-deprecation).
2. Canonical seed data (8 official programs + 00000 غیر برنامه‌ای).
3. Preservation of historical data: soft-deactivating a program never deletes historical records.
4. Dynamic derivation of Macro Indicators from the active program catalog.
5. API v3 endpoints (/api/v3/reporting/catalog/programs and /toggle-active).
"""

from __future__ import annotations

from pathlib import Path
import pytest

from eitaa_bridge.application import reporting_api_v3 as v3
from eitaa_bridge.reporting.store import ReportingStore


def _make_store(tmp_path: Path) -> ReportingStore:
    return ReportingStore(tmp_path / "test_catalog.sqlite3")


def test_program_catalog_schema_and_canonical_seed(tmp_path: Path) -> None:
    store = _make_store(tmp_path)
    programs = store.list_program_catalog(include_inactive=True)

    # 8 official cultural programs + 1 unprogrammed (00000)
    assert len(programs) >= 9

    codes = {p["program_code"]: p for p in programs}
    assert "80501" in codes
    assert "80403" in codes
    assert "80406" in codes
    assert "80402" in codes
    assert "80401" in codes
    assert "80601" in codes
    assert "80202" in codes
    assert "80301" in codes
    assert "00000" in codes

    # Check prayer program details
    prayer = codes["80501"]
    assert "نماز" in prayer["title"]
    assert "نماز" in prayer["workbook_sheet"]
    assert prayer["valid_from_year"] in (1403, 1404)
    assert prayer["valid_to_year"] is None
    assert prayer["is_active"] == 1

    # Check unprogrammed
    unprog = codes["00000"]
    assert unprog["title"] == "غیر برنامه‌ای"
    assert unprog["is_active"] == 1


def test_program_catalog_lifecycle_and_soft_deprecation(tmp_path: Path) -> None:
    store = _make_store(tmp_path)

    # Initially, 80401 (اردو) is active
    initial_active = {p["program_code"] for p in store.list_program_catalog(include_inactive=False)}
    assert "80401" in initial_active

    # Soft-deprecate program 80401 (e.g., discontinued in next planning cycle)
    toggled = store.toggle_program_active("80401", False)
    assert toggled is not None
    assert toggled["is_active"] == 0

    # It must disappear from the active catalog
    active_codes = {p["program_code"] for p in store.list_program_catalog(include_inactive=False)}
    assert "80401" not in active_codes

    # But it must remain fully visible in the comprehensive catalog (preserving historical reports)
    all_codes = {p["program_code"] for p in store.list_program_catalog(include_inactive=True)}
    assert "80401" in all_codes

    # Re-activating brings it back
    reactivated = store.toggle_program_active("80401", True)
    assert reactivated is not None
    assert reactivated["is_active"] == 1
    assert "80401" in {p["program_code"] for p in store.list_program_catalog(include_inactive=False)}


def test_program_catalog_multi_year_validity(tmp_path: Path) -> None:
    store = _make_store(tmp_path)

    # Insert a program valid only in years 1406 to 1408
    store.save_program_catalog_item(
        program_code="80901",
        title="برنامه آزمایشی آینده",
        canonical_macro="برنامه آزمایشی آینده",
        kind="operational",
        workbook_sheet="آزمایشی",
        valid_from_year=1406,
        valid_to_year=1408,
        is_active=True,
        display_order=90,
        description="برنامه آینده",
    )

    # Query for year 1405: must NOT be included
    year_1405 = {p["program_code"] for p in store.list_program_catalog(year=1405)}
    assert "80901" not in year_1405

    # Query for year 1406: MUST be included
    year_1406 = {p["program_code"] for p in store.list_program_catalog(year=1406)}
    assert "80901" in year_1406

    # Query for year 1408: MUST be included
    year_1408 = {p["program_code"] for p in store.list_program_catalog(year=1408)}
    assert "80901" in year_1408

    # Query for year 1409: expired, must NOT be included
    year_1409 = {p["program_code"] for p in store.list_program_catalog(year=1409)}
    assert "80901" not in year_1409


def test_save_program_catalog_item_upsert(tmp_path: Path) -> None:
    store = _make_store(tmp_path)

    # Update description of 80501
    store.save_program_catalog_item(
        program_code="80501",
        title="ترویج و توسعه فرهنگ اقامه نماز جماعات",
        canonical_macro="ترویج و توسعه فرهنگ اقامه نماز",
        kind="prayer",
        workbook_sheet="نماز جماعات",
        valid_from_year=1404,
        valid_to_year=None,
        is_active=True,
        display_order=10,
        description="برگزاری نماز اول وقت و برنامه‌های محراب",
    )

    fetched = store.get_program_by_code("80501")
    assert fetched is not None
    assert fetched["title"] == "ترویج و توسعه فرهنگ اقامه نماز جماعات"
    assert fetched["workbook_sheet"] == "نماز جماعات"
    assert fetched["description"] == "برگزاری نماز اول وقت و برنامه‌های محراب"


def test_list_macro_indicators_dynamic_catalog(tmp_path: Path) -> None:
    store = _make_store(tmp_path)

    # Get initial macro indicators
    macros = store.list_macro_indicators()
    assert len(macros) >= 9
    assert "ترویج و توسعه فرهنگ اقامه نماز" in macros

    # Deactivating 80501 removes its macro from the dynamic list
    store.toggle_program_active("80501", False)
    macros_after = store.list_macro_indicators()
    assert "ترویج و توسعه فرهنگ اقامه نماز" not in macros_after

    # Reactivating brings it back
    store.toggle_program_active("80501", True)
    macros_restored = store.list_macro_indicators()
    assert "ترویج و توسعه فرهنگ اقامه نماز" in macros_restored


def test_api_v3_program_catalog_endpoints(tmp_path: Path) -> None:
    store = _make_store(tmp_path)

    # 1. GET /api/v3/reporting/catalog/programs
    status, payload, _ = v3.dispatch(
        store, "staff", ["viewer"], "GET", "/api/v3/reporting/catalog/programs"
    )
    assert status == 200
    assert payload["ok"] is True
    assert len(payload["programs"]) >= 9

    # 2. POST /api/v3/reporting/catalog/programs/toggle-active
    status2, payload2, _ = v3.dispatch(
        store, "staff", ["editor"], "POST", "/api/v3/reporting/catalog/programs/toggle-active",
        payload={"program_code": "80401", "is_active": False},
    )
    assert status2 == 200
    assert payload2["ok"] is True
    assert payload2["program"]["is_active"] == 0

    # 3. Verify GET without include_inactive excludes 80401
    status3, payload3, _ = v3.dispatch(
        store, "staff", ["viewer"], "GET", "/api/v3/reporting/catalog/programs"
    )
    assert status3 == 200
    active_codes = [p["program_code"] for p in payload3["programs"]]
    assert "80401" not in active_codes

    # 4. Verify GET with include_inactive=1 includes 80401
    status4, payload4, _ = v3.dispatch(
        store, "staff", ["viewer"], "GET", "/api/v3/reporting/catalog/programs",
        query={"include_inactive": "1"},
    )
    assert status4 == 200
    all_codes = [p["program_code"] for p in payload4["programs"]]
    assert "80401" in all_codes

    # 5. POST /api/v3/reporting/catalog/programs (Create custom program)
    status5, payload5, _ = v3.dispatch(
        store, "staff", ["editor"], "POST", "/api/v3/reporting/catalog/programs",
        payload={
            "program_code": "80888",
            "title": "نوآوری‌های دیجیتال فرهنگی",
            "canonical_macro": "نوآوری‌های دیجیتال فرهنگی",
            "kind": "operational",
            "workbook_sheet": "فناوری",
            "valid_from_year": 1405,
            "is_active": True,
            "display_order": 88,
            "description": "تولیدات هوش مصنوعی و نرم‌افزارهای فرهنگی",
        },
    )
    assert status5 == 201
    assert payload5["ok"] is True
    assert payload5["program"]["program_code"] == "80888"

    # 6. GET /api/v3/reporting/indicators/macro
    status6, payload6, _ = v3.dispatch(
        store, "staff", ["viewer"], "GET", "/api/v3/reporting/indicators/macro"
    )
    assert status6 == 200
    assert payload6["ok"] is True
    assert "نوآوری‌های دیجیتال فرهنگی" in payload6["macro_indicators"]
