"""Tests for Master Baseline Banks and Registry APIs in reporting phase 2."""
import pytest
from pathlib import Path

from eitaa_bridge.reporting.store import ReportingStore
from eitaa_bridge.application.reporting_api_v3 import dispatch


@pytest.fixture
def test_store(tmp_path: Path) -> ReportingStore:
    db_path = tmp_path / "test_baseline_banks.db"
    return ReportingStore(db_path)


def test_unit_baselines_crud_and_listing(test_store: ReportingStore):
    # 1. Save baseline for Neka
    status, payload, _ = dispatch(
        test_store, "test_admin", ["editor", "admin"], "POST",
        "/api/v3/reporting/units/%D9%86%DA%A9%D8%A7%20-%20%D8%AF%D8%A7%D8%AF%DA%AF%D8%B3%D8%AA%D8%B1%DB%8C/baseline",
        {"staff_count": 85, "family_multiplier": 3.2, "imams_count": 2, "prayer_rooms_count": 1, "honored_count": 5, "notes": "دادگستری نکا"}
    )
    assert status == 200
    assert payload["ok"] is True
    assert payload["baseline"]["staff_count"] == 85
    assert payload["baseline"]["imams_count"] == 2

    # 2. Get baseline
    status, payload, _ = dispatch(
        test_store, "test_admin", ["editor", "admin"], "GET",
        "/api/v3/reporting/units/%D9%86%DA%A9%D8%A7%20-%20%D8%AF%D8%A7%D8%AF%DA%AF%D8%B3%D8%AA%D8%B1%DB%8C/baseline",
        {}
    )
    assert status == 200
    assert payload["baseline"]["staff_count"] == 85
    assert payload["baseline"]["family_multiplier"] == 3.2

    # 3. List all baselines
    status, payload, _ = dispatch(
        test_store, "test_admin", ["editor", "admin"], "GET",
        "/api/v3/reporting/units/baselines",
        {}
    )
    assert status == 200
    assert len(payload["baselines"]) >= 1
    assert any(b["unit_id"] == "نکا - دادگستری" for b in payload["baselines"])


def test_imams_crud(test_store: ReportingStore):
    units = test_store.list_units()
    unit = units[0]

    # 1. Create imam
    status, payload, _ = dispatch(
        test_store, "test_admin", ["editor", "admin"], "POST",
        "/api/v3/reporting/imams",
        {
            "imam_id": "imam_test_1",
            "unit_id": unit.unit_id,
            "full_name": "حجت‌الاسلام حسینی",
            "position": "امام جماعت ظهر و عصر",
            "source_kind": "staff_cleric",
            "status": "employed",
            "personnel_no": "112233",
            "notes": "روحانی پرسنل"
        }
    )
    assert status == 200
    assert payload["ok"] is True
    assert payload["imam"]["full_name"] == "حجت‌الاسلام حسینی"

    # 2. List imams
    status, payload, _ = dispatch(
        test_store, "test_admin", ["editor", "admin"], "GET",
        "/api/v3/reporting/imams",
        {"unit_id": unit.unit_id}
    )
    assert status == 200
    assert len(payload["imams"]) == 1
    assert payload["imams"][0]["full_name"] == "حجت‌الاسلام حسینی"

    # 3. Delete imam
    status, payload, _ = dispatch(
        test_store, "test_admin", ["editor", "admin"], "DELETE",
        "/api/v3/reporting/imams/imam_test_1",
        {}
    )
    assert status == 200
    assert payload["deleted"] is True

    # 4. List after delete
    status, payload, _ = dispatch(
        test_store, "test_admin", ["editor", "admin"], "GET",
        "/api/v3/reporting/imams",
        {"unit_id": unit.unit_id}
    )
    assert len(payload["imams"]) == 0


def test_venues_crud(test_store: ReportingStore):
    units = test_store.list_units()
    unit = units[0]

    # 1. Create venue
    status, payload, _ = dispatch(
        test_store, "test_admin", ["editor", "admin"], "POST",
        "/api/v3/reporting/venues",
        {
            "venue_id": "venue_test_1",
            "unit_id": unit.unit_id,
            "name": "نمازخانه مرکزی دادگستری",
            "notes": "ظرفیت ۱۲۰ نفر"
        }
    )
    assert status == 200
    assert payload["venue"]["name"] == "نمازخانه مرکزی دادگستری"

    # 2. List venues
    status, payload, _ = dispatch(
        test_store, "test_admin", ["editor", "admin"], "GET",
        "/api/v3/reporting/venues",
        {"unit_id": unit.unit_id}
    )
    assert len(payload["venues"]) == 1

    # 3. Delete venue
    status, payload, _ = dispatch(
        test_store, "test_admin", ["editor", "admin"], "DELETE",
        "/api/v3/reporting/venues/venue_test_1",
        {}
    )
    assert status == 200
    assert payload["deleted"] is True


def test_persons_crud(test_store: ReportingStore):
    # 1. Create employee person
    status, payload, _ = dispatch(
        test_store, "test_admin", ["editor", "admin"], "POST",
        "/api/v3/reporting/persons",
        {
            "person_id": "person_emp_1",
            "kind": "employee",
            "full_name": "علی رضایی",
            "personnel_no": "998877",
            "national_id": "2160000000",
            "phone": "09111111111",
            "unit_id": "نکا - دادگستری",
            "notes": "کارشناس فرهنگی و رابط تقدیرشده"
        }
    )
    assert status == 200
    assert payload["person"]["full_name"] == "علی رضایی"

    # 2. List persons
    status, payload, _ = dispatch(
        test_store, "test_admin", ["editor", "admin"], "GET",
        "/api/v3/reporting/persons",
        {"kind": "employee"}
    )
    assert len(payload["persons"]) == 1

    # 3. Delete person
    status, payload, _ = dispatch(
        test_store, "test_admin", ["editor", "admin"], "DELETE",
        "/api/v3/reporting/persons/person_emp_1",
        {}
    )
    assert status == 200
    assert payload["deleted"] is True
