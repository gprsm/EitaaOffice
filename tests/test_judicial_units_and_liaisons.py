"""Tests for Judicial Units (حوزه‌های قضایی، شهرستان‌ها) and Cultural Liaisons (رابطین فرهنگی)."""

from __future__ import annotations

from pathlib import Path
import pytest

from eitaa_bridge.application import reporting_api_v3 as v3
from eitaa_bridge.reporting.registry import LiaisonRecord, UnitRecord
from eitaa_bridge.reporting.store import ReportingStore


def _make_store(tmp_path: Path) -> ReportingStore:
    return ReportingStore(tmp_path / "test_units.sqlite3")


def test_schema_migration_and_seed_defaults(tmp_path: Path) -> None:
    store = _make_store(tmp_path)
    units = store.list_units()
    counties = store.list_counties()
    liaisons = store.list_liaisons()

    # Must seed canonical 38 units across 33 Mazandaran judicial domains
    assert len(units) == 38
    assert len(counties) == 33
    assert "ساری" in counties
    assert "بابل" in counties
    assert "قائمشهر" in counties
    assert "نور" in counties
    assert "چمستان" in counties

    # Check that ساری has its 4 judicial units (HQ + 3 units)
    sari_units = store.list_units(county="ساری")
    sari_types = {u.unit_type for u in sari_units}
    assert "اداره کل" in sari_types
    assert "دادگستری" in sari_types
    assert "دادسرا" in sari_types
    assert "شورای حل اختلاف" in sari_types

    # Check that بابل has two units (دادگستری و دادسرا)
    babol_units = store.list_units(county="بابل")
    assert {u.unit_type for u in babol_units} == {"دادگستری", "دادسرا"}

    # Check that قائمشهر has two units (دادگستری و دادسرا)
    qaem_units = store.list_units(county="قائمشهر")
    assert {u.unit_type for u in qaem_units} == {"دادگستری", "دادسرا"}

    # Must seed default liaisons
    assert len(liaisons) >= 5
    liaison_names = {l.full_name for l in liaisons}
    assert "قاسمی شورابی" in liaison_names
    assert "دیوسالار" in liaison_names
    assert "مهدوی" in liaison_names
    assert "احسانی" in liaison_names
    assert "حمید سعیدی" in liaison_names


def test_units_crud(tmp_path: Path) -> None:
    store = _make_store(tmp_path)

    # 1. Create a custom unit
    new_unit = UnitRecord(
        unit_id="unit-test-1",
        name="ساری - مجتمع قضایی تجاری",
        county="ساری",
        unit_type="مجتمع قضایی تجاری",
        display_name="ساری - مجتمع قضایی تجاری",
        kind="judicial_domain",
        notes="واحد ویژه امور بازرگانی",
    )
    saved = store.save_unit(new_unit)
    assert saved.unit_id == "unit-test-1"

    # 2. Retrieve
    retrieved = store.get_unit("unit-test-1")
    assert retrieved is not None
    assert retrieved.county == "ساری"
    assert retrieved.display_name == "ساری - مجتمع قضایی تجاری"

    # 3. Update
    retrieved.notes = "به‌روزرسانی یادداشت"
    updated = store.save_unit(retrieved)
    assert updated.notes == "به‌روزرسانی یادداشت"

    # 4. Delete
    deleted = store.delete_unit("unit-test-1")
    assert deleted is True
    assert store.get_unit("unit-test-1") is None


def test_liaisons_crud(tmp_path: Path) -> None:
    store = _make_store(tmp_path)
    sari_hq = store.find_unit_by_name("ساری - اداره کل")
    assert sari_hq is not None

    # 1. Create liaison
    liaison = LiaisonRecord(
        liaison_id="liaison-custom-1",
        unit_id=sari_hq.unit_id,
        full_name="علی محمدی",
        eitaa_username="ali_mohammadi",
        eitaa_user_id="11223344",
        sender_key="u:11223344",
        phone="09110000000",
        match_keywords="محمدی,ستاد",
        notes="کارشناس فرهنگی ستاد",
    )
    saved = store.save_liaison(liaison)
    assert saved.liaison_id == "liaison-custom-1"

    # 2. Retrieve & List
    retrieved = store.get_liaison("liaison-custom-1")
    assert retrieved is not None
    assert retrieved.full_name == "علی محمدی"
    assert retrieved.eitaa_username == "ali_mohammadi"

    unit_liaisons = store.list_liaisons(unit_id=sari_hq.unit_id)
    assert any(l.liaison_id == "liaison-custom-1" for l in unit_liaisons)

    # 3. Delete
    deleted = store.delete_liaison("liaison-custom-1")
    assert deleted is True
    assert store.get_liaison("liaison-custom-1") is None


def test_resolve_liaison_and_unit(tmp_path: Path) -> None:
    store = _make_store(tmp_path)

    # 1. Resolve by username
    l1, u1 = store.resolve_liaison_and_unit(username="ghasemi_sho")
    assert l1 is not None
    assert l1.full_name == "قاسمی شورابی"
    assert u1 is not None
    assert u1.display_name == "ساری - اداره کل"

    # 2. Resolve by full_name
    l2, u2 = store.resolve_liaison_and_unit(full_name="دیوسالار")
    assert l2 is not None
    assert l2.full_name == "دیوسالار"
    assert u2 is not None
    assert "نور" in u2.display_name

    # 3. Resolve by keyword in text
    l3, u3 = store.resolve_liaison_and_unit(text="گزارش ارسالی از مهدوی رابط فرهنگی شهرستان")
    assert l3 is not None
    assert l3.full_name == "مهدوی"
    assert u3 is not None
    assert "سوادکوه" in u3.display_name

    # 4. Fallback: match unit directly from text if no liaison matched
    l4, u4 = store.resolve_liaison_and_unit(text="برگزاری مراسم زیارت عاشورا در دادگستری کلاردشت")
    assert l4 is None
    assert u4 is not None
    assert "کلاردشت" in u4.display_name


def test_v3_api_units_and_liaisons(tmp_path: Path) -> None:
    store = _make_store(tmp_path)

    # 1. GET /api/v3/reporting/units
    status, payload, _ = v3.dispatch(store, "staff", ["editor"], "GET", "/api/v3/reporting/units")
    assert status == 200
    assert payload["ok"] is True
    assert len(payload["units"]) > 0
    assert len(payload["counties"]) > 0

    # 2. POST /api/v3/reporting/units
    status, payload, _ = v3.dispatch(
        store, "staff", ["editor"], "POST", "/api/v3/reporting/units",
        payload={
            "county": "نور",
            "unit_type": "دادگاه ویژه تجاری",
            "kind": "judicial_domain",
        },
    )
    assert status == 200
    assert payload["ok"] is True
    created_unit = payload["unit"]
    assert created_unit["display_name"] == "نور - دادگاه ویژه تجاری"
    unit_id = created_unit["unit_id"]

    # 3. GET /api/v3/reporting/liaisons
    status, payload, _ = v3.dispatch(store, "staff", ["editor"], "GET", "/api/v3/reporting/liaisons")
    assert status == 200
    assert payload["ok"] is True
    assert len(payload["liaisons"]) > 0

    # 4. POST /api/v3/reporting/liaisons
    status, payload, _ = v3.dispatch(
        store, "staff", ["editor"], "POST", "/api/v3/reporting/liaisons",
        payload={
            "unit_id": unit_id,
            "full_name": "سهراب سپهری",
            "eitaa_username": "sohrab_s",
            "phone": "09111112233",
            "match_keywords": "سپهری,سهراب",
        },
    )
    assert status == 200
    assert payload["ok"] is True
    created_liaison = payload["liaison"]
    assert created_liaison["full_name"] == "سهراب سپهری"
    assert created_liaison["unit_display_name"] == "نور - دادگاه ویژه تجاری"
    liaison_id = created_liaison["liaison_id"]

    # 5. POST /api/v3/reporting/liaisons/resolve
    status, payload, _ = v3.dispatch(
        store, "staff", ["editor"], "POST", "/api/v3/reporting/liaisons/resolve",
        payload={"username": "sohrab_s"},
    )
    assert status == 200
    assert payload["matched"] is True
    assert payload["liaison"]["full_name"] == "سهراب سپهری"
    assert payload["unit"]["display_name"] == "نور - دادگاه ویژه تجاری"

    # 6. DELETE /api/v3/reporting/liaisons/{id}
    status, payload, _ = v3.dispatch(
        store, "staff", ["editor"], "DELETE", f"/api/v3/reporting/liaisons/{liaison_id}"
    )
    assert status == 200
    assert payload["ok"] is True

    # 7. DELETE /api/v3/reporting/units/{id}
    status, payload, _ = v3.dispatch(
        store, "staff", ["editor"], "DELETE", f"/api/v3/reporting/units/{unit_id}"
    )
    assert status == 200
    assert payload["ok"] is True


def test_v3_api_post_delete_fallback(tmp_path: Path) -> None:
    """Ensure POST .../delete works as an alternative fallback for restricted environments."""
    store = _make_store(tmp_path)

    # 1. Create a unit
    u_stat, u_pay, _ = v3.dispatch(
        store, "staff", ["editor"], "POST", "/api/v3/reporting/units",
        payload={"county": "چالوس", "unit_type": "دادگاه تجدیدنظر", "kind": "judicial_domain"},
    )
    assert u_stat == 200
    u_id = u_pay["unit"]["unit_id"]

    # 2. Create a liaison for that unit
    l_stat, l_pay, _ = v3.dispatch(
        store, "staff", ["editor"], "POST", "/api/v3/reporting/liaisons",
        payload={"unit_id": u_id, "full_name": "رابط تستی چالوس"},
    )
    assert l_stat == 200
    l_id = l_pay["liaison"]["liaison_id"]

    # 3. Delete liaison via POST .../delete
    post_l_stat, post_l_pay, _ = v3.dispatch(
        store, "staff", ["editor"], "POST", f"/api/v3/reporting/liaisons/{l_id}/delete"
    )
    assert post_l_stat == 200
    assert post_l_pay["ok"] is True
    assert store.get_liaison(l_id) is None

    # 4. Delete unit via POST .../delete
    post_u_stat, post_u_pay, _ = v3.dispatch(
        store, "staff", ["editor"], "POST", f"/api/v3/reporting/units/{u_id}/delete"
    )
    assert post_u_stat == 200
    assert post_u_pay["ok"] is True
    assert store.get_unit(u_id) is None


def test_unit_deletion_cascades_liaisons(tmp_path: Path) -> None:
    """Ensure deleting a judicial unit automatically cleans up any attached liaisons."""
    store = _make_store(tmp_path)

    u_stat, u_pay, _ = v3.dispatch(
        store, "staff", ["editor"], "POST", "/api/v3/reporting/units",
        payload={"county": "رامسر", "unit_type": "شورای ویژه", "kind": "judicial_domain"},
    )
    assert u_stat == 200
    u_id = u_pay["unit"]["unit_id"]

    l_stat, l_pay, _ = v3.dispatch(
        store, "staff", ["editor"], "POST", "/api/v3/reporting/liaisons",
        payload={"unit_id": u_id, "full_name": "رابط رامسری ۱"},
    )
    assert l_stat == 200
    l_id = l_pay["liaison"]["liaison_id"]

    # Delete the unit
    del_stat, del_pay, _ = v3.dispatch(
        store, "staff", ["editor"], "DELETE", f"/api/v3/reporting/units/{u_id}"
    )
    assert del_stat == 200
    assert del_pay["ok"] is True

    # Both unit and attached liaison must be deleted
    assert store.get_unit(u_id) is None
    assert store.get_liaison(l_id) is None


def test_http_api_handler_has_do_delete() -> None:
    """Ensure the HTTP adapter implements do_DELETE so HTTP clients do not receive 501."""
    from eitaa_bridge.interfaces.http_api import _ApiHandler

    assert hasattr(_ApiHandler, "do_DELETE")
    assert callable(getattr(_ApiHandler, "do_DELETE"))


def test_author_liaison_assignment_and_lookup_api(tmp_path: Path) -> None:
    """Test assigning an author directly from message metadata, looking them up, and unlinking."""
    store = _make_store(tmp_path)
    sari_units = store.list_units(county="ساری")
    assert len(sari_units) > 0
    target_unit = sari_units[0]

    # 1. Lookup when not assigned yet
    status, payload, _ = v3.dispatch(
        store, "staff", ["editor"], "GET", "/api/v3/reporting/liaisons/lookup",
        query={"sender_key": "u:998877", "username": "test_author", "full_name": "نویسنده تستی"}
    )
    assert status == 200
    assert payload["matched"] is False
    assert payload["liaison"] is None

    # 2. Assign author as liaison via API
    assign_stat, assign_pay, _ = v3.dispatch(
        store, "staff", ["editor"], "POST", "/api/v3/reporting/liaisons/assign-author",
        payload={
            "unit_id": target_unit.unit_id,
            "full_name": "نویسنده تستی",
            "sender_key": "u:998877",
            "eitaa_username": "test_author",
            "eitaa_user_id": "998877",
            "phone": "09121112233",
            "notes": "رابط تستی معرفی شده از پیام",
        }
    )
    assert assign_stat == 200
    assert assign_pay["ok"] is True
    assert assign_pay["liaison"]["full_name"] == "نویسنده تستی"
    assert assign_pay["liaison"]["unit_id"] == target_unit.unit_id
    assert assign_pay["liaison"]["phone"] == "09121112233"
    assert assign_pay["liaison"]["unit_display_name"] == target_unit.display_name

    # 3. Lookup again by sender_key
    stat2, pay2, _ = v3.dispatch(
        store, "staff", ["editor"], "GET", "/api/v3/reporting/liaisons/lookup",
        query={"sender_key": "u:998877"}
    )
    assert stat2 == 200
    assert pay2["matched"] is True
    assert pay2["liaison"]["full_name"] == "نویسنده تستی"
    assert pay2["unit"]["unit_id"] == target_unit.unit_id

    # 4. Get profile analytics
    prof_stat, prof_pay, _ = v3.dispatch(
        store, "staff", ["editor"], "GET", "/api/v3/reporting/liaisons/profile",
        query={"sender_key": "u:998877"}
    )
    assert prof_stat == 200
    assert prof_pay["ok"] is True
    profile = prof_pay["profile"]
    assert profile["liaison_name"] == "نویسنده تستی"
    assert profile["is_liaison"] is True
    assert profile["display_title"] == f"نویسنده تستی - حوزه قضایی {target_unit.display_name}"
    assert "messages_count" in profile
    assert "reports_count" in profile
    assert "topic_frequency" in profile
    assert "unit_total_reports" in profile

    # 5. Unlink author liaison
    unlink_stat, unlink_pay, _ = v3.dispatch(
        store, "staff", ["editor"], "POST", "/api/v3/reporting/liaisons/unlink-author",
        payload={"sender_key": "u:998877"}
    )
    assert unlink_stat == 200
    assert unlink_pay["unlinked"] is True

    # 6. Lookup after unlink must be unmatched
    stat3, pay3, _ = v3.dispatch(
        store, "staff", ["editor"], "GET", "/api/v3/reporting/liaisons/lookup",
        query={"sender_key": "u:998877"}
    )
    assert stat3 == 200
    assert pay3["matched"] is False


def test_macro_and_micro_indicators_api(tmp_path: Path) -> None:
    """Test Macro indicators retrieval, and Micro indicators CRUD."""
    store = _make_store(tmp_path)

    # 1. Macro indicators: must return 9 canonical items
    status, payload, _ = v3.dispatch(
        store, "staff", ["viewer"], "GET", "/api/v3/reporting/indicators/macro"
    )
    assert status == 200
    assert payload["ok"] is True
    assert len(payload["macro_indicators"]) == 9
    assert "غیر برنامه‌ای" in payload["macro_indicators"]
    assert "برگزاری مراسم در مناسبت‌های ملی، مذهبی و انقلابی" in payload["macro_indicators"]

    # 2. Micro indicators listing (seeded with initial indicators)
    status2, payload2, _ = v3.dispatch(
        store, "staff", ["viewer"], "GET", "/api/v3/reporting/indicators/micro"
    )
    assert status2 == 200
    assert payload2["ok"] is True
    assert len(payload2["micro_indicators"]) >= 10

    # 3. Create a new micro indicator
    status3, payload3, _ = v3.dispatch(
        store, "staff", ["editor"], "POST", "/api/v3/reporting/indicators/micro",
        payload={"title": "مسابقه کتابخوانی نهج‌البلاغه", "category": "مسابقات", "color": "#0284c7"}
    )
    assert status3 == 201
    assert payload3["ok"] is True
    ind_id = payload3["indicator"]["indicator_id"]
    assert payload3["indicator"]["title"] == "مسابقه کتابخوانی نهج‌البلاغه"

    # 4. Update the micro indicator
    status4, payload4, _ = v3.dispatch(
        store, "staff", ["editor"], "PUT", f"/api/v3/reporting/indicators/micro/{ind_id}",
        payload={"title": "مسابقه کتابخوانی نهج‌البلاغه ویژه رمضان"}
    )
    assert status4 == 200
    assert payload4["indicator"]["title"] == "مسابقه کتابخوانی نهج‌البلاغه ویژه رمضان"

    # 5. Delete the micro indicator
    status5, payload5, _ = v3.dispatch(
        store, "staff", ["editor"], "DELETE", f"/api/v3/reporting/indicators/micro/{ind_id}"
    )
    assert status5 == 200
    assert payload5["deleted"] is True


def test_message_indicators_and_splits_api(tmp_path: Path) -> None:
    """Test assigning macro & micro indicators to messages, and message split controls."""
    store = _make_store(tmp_path)
    peer_key = "channel:10012345"

    # 1. Assign indicators to messages 101, 102
    status, payload, _ = v3.dispatch(
        store, "staff", ["editor"], "POST", "/api/v3/reporting/indicators/messages/assign",
        payload={
            "peer_key": peer_key,
            "message_ids": [101, 102],
            "macro_indicator": "ترویج و توسعه فرهنگ اقامه نماز",
            "micro_indicators": ["نماز جماعت", "زیارت عاشورا"],
        }
    )
    assert status == 200
    assert payload["ok"] is True
    assert payload["macro_indicator"] == "ترویج و توسعه فرهنگ اقامه نماز"
    assert "نماز جماعت" in payload["micro_indicators"]

    # 2. Get message indicators
    stat2, pay2, _ = v3.dispatch(
        store, "staff", ["viewer"], "GET", "/api/v3/reporting/indicators/messages",
        query={"peer_key": peer_key, "message_ids": "101,102,103"}
    )
    assert stat2 == 200
    indicators = pay2["indicators"]
    assert "101" in indicators
    assert indicators["101"]["macro_indicator"] == "ترویج و توسعه فرهنگ اقامه نماز"
    assert "نماز جماعت" in indicators["101"]["micro_indicators"]
    assert "103" not in indicators

    # 3. Message splits: detach message 102
    stat3, pay3, _ = v3.dispatch(
        store, "staff", ["editor"], "POST", "/api/v3/reporting/splits",
        payload={"peer_key": peer_key, "detached_ids": [102]}
    )
    assert stat3 == 200
    assert 102 in pay3["detached_message_ids"]

    # 4. Get splits
    stat4, pay4, _ = v3.dispatch(
        store, "staff", ["viewer"], "GET", "/api/v3/reporting/splits",
        query={"peer_key": peer_key}
    )
    assert stat4 == 200
    assert 102 in pay4["detached_message_ids"]

    # 5. Re-unify message 102
    stat5, pay5, _ = v3.dispatch(
        store, "staff", ["editor"], "POST", "/api/v3/reporting/splits",
        payload={"peer_key": peer_key, "unified_ids": [102]}
    )
    assert stat5 == 200
    assert 102 not in pay5["detached_message_ids"]


def test_sync_liaison_to_eitaa_contact(tmp_path: Path) -> None:
    store = _make_store(tmp_path)
    babol_unit = store.find_unit_by_name("بابل - دادگستری")
    assert babol_unit is not None

    liaison = LiaisonRecord(
        liaison_id="liaison-babol-1",
        unit_id=babol_unit.unit_id,
        full_name="حامد باباجانی",
        eitaa_username="hamed_babajani",
        phone="09112223344",
    )
    store.save_liaison(liaison)

    # 1. Sync liaison to Eitaa contact
    res = store.sync_liaison_to_eitaa_contact(liaison.liaison_id)
    assert res["ok"] is True
    assert res["full_name"] == "حامد باباجانی"
    assert res["unit_display_name"] == "بابل - دادگستری"
    assert res["contact_display_name"] == "حامد باباجانی - رابط فرهنگی بابل - دادگستری"
    assert res["first_name"] == "حامد باباجانی"
    assert res["last_name"] == "- رابط فرهنگی بابل - دادگستری"
    assert res["phone"] == "+989112223344"

    # Verify in SQLiteContactStore
    from eitaa_bridge.infrastructure.contact_store import SQLiteContactStore
    contacts_db = tmp_path / "contacts.sqlite3"
    assert contacts_db.exists()
    c_store = SQLiteContactStore(contacts_db)
    found = c_store.get_contacts([res["local_contact_id"]])
    assert len(found) == 1
    assert found[0]["first_name"] == "حامد باباجانی"
    assert found[0]["last_name"] == "- رابط فرهنگی بابل - دادگستری"


def test_api_v3_sync_eitaa_contact_routes(tmp_path: Path) -> None:
    store = _make_store(tmp_path)
    sari_unit = store.find_unit_by_name("ساری - دادگستری")
    assert sari_unit is not None

    liaison = LiaisonRecord(
        liaison_id="liaison-sari-test",
        unit_id=sari_unit.unit_id,
        full_name="محمد علیزاده",
        eitaa_username="m_alizadeh",
        phone="09121112233",
    )
    store.save_liaison(liaison)

    # 1. POST single sync route
    status, payload, _ = v3.dispatch(
        store, "staff", ["editor"], "POST",
        f"/api/v3/reporting/liaisons/{liaison.liaison_id}/sync-eitaa-contact",
        payload={"phone": "09121112233"}
    )
    assert status == 200
    assert payload["ok"] is True
    assert payload["contact_display_name"] == "محمد علیزاده - رابط فرهنگی ساری - دادگستری"

    # 2. POST bulk sync route
    status_all, payload_all, _ = v3.dispatch(
        store, "staff", ["editor"], "POST",
        "/api/v3/reporting/liaisons/sync-all-eitaa-contacts",
    )
    assert status_all == 200
    assert payload_all["ok"] is True
    assert payload_all["synced_count"] >= 1


def test_fact_unit_of_measure_persian_and_custom_validation() -> None:
    from eitaa_bridge.reporting.model import Fact, FactValueKind

    # 1. Standard Persian units must pass validation
    for uom in ["نفر", "جلسه", "عدد", "ساعت", "میلیون ریال", "درصد", "count", "text", "currency", "percent"]:
        fact = Fact(metric="attendees", value=50.0, value_kind=FactValueKind.VERIFIED, unit_of_measure=uom)
        fact.validate()

    # 2. Empty metric must fail
    with pytest.raises(ValueError, match="Fact metric cannot be empty"):
        Fact(metric="   ", value=10.0, value_kind=FactValueKind.VERIFIED, unit_of_measure="نفر").validate()

    # 3. Negative value must fail
    with pytest.raises(ValueError, match="Fact value cannot be negative"):
        Fact(metric="attendees", value=-5.0, value_kind=FactValueKind.VERIFIED, unit_of_measure="نفر").validate()

    # 4. Empty unit of measure must fail
    with pytest.raises(ValueError, match="Fact unit of measure cannot be empty"):
        Fact(metric="attendees", value=10.0, value_kind=FactValueKind.VERIFIED, unit_of_measure="   ").validate()


def test_resolve_liaison_prevents_false_author_attribution_from_message_body(tmp_path: Path) -> None:
    store = _make_store(tmp_path)

    # 1. Message mentions "سوادکوه" in the news text, but sender is unknown.
    # Must NOT assign liaison Mahdavi as the author!
    # Must infer the unit as Savadkuh court, but keep liaison None.
    l, u = store.resolve_liaison_and_unit(
        sender_key="",
        username="",
        full_name="",
        text="برگزاری مسابقات سراسری قرآن در دادگستری سوادکوه با شکوه فراوان انجام شد.",
    )
    assert l is None, "Should not attribute liaison Mahdavi to message body mentioning Savadkuh"
    assert u is not None
    assert "سوادکوه" in u.display_name

    # 2. Message mentions "مهدویت" (contains substring 'مهدوی').
    # Must NOT falsely match liaison Mahdavi.
    l2, u2 = store.resolve_liaison_and_unit(
        sender_key="",
        username="",
        full_name="",
        text="مراسم معنوی دعای ندبه و تبیین مبانی مهدویت در نمازخانه برگزار گردید.",
    )
    assert l2 is None

    # 3. Message mentions "احساس" (contains substring 'احسا').
    # Must NOT falsely match liaison Ehsani.
    l3, u3 = store.resolve_liaison_and_unit(
        sender_key="",
        username="",
        full_name="",
        text="ایجاد احساس آرامش و همدلی در میان کارکنان دستگاه قضایی.",
    )
    assert l3 is None

    # 4. Explicit liaison mention in text (prefixed with 'رابط فرهنگی:')
    # Must correctly resolve liaison Mahdavi
    l4, u4 = store.resolve_liaison_and_unit(
        sender_key="",
        username="",
        full_name="",
        text="گزارش مراسم هفتگی زیارت عاشورا\nرابط فرهنگی: مهدوی",
    )
    assert l4 is not None
    assert l4.full_name == "مهدوی"
    assert u4 is not None
    assert "سوادکوه" in u4.display_name


def test_resolve_liaison_sender_key_normalization_and_prefixes(tmp_path: Path) -> None:
    """Ensure resolve_liaison_and_unit handles user:, u:, and bare numeric sender keys robustly."""
    store = _make_store(tmp_path)
    unit = store.find_unit_by_name("ساری - اداره کل")
    assert unit is not None

    # Liaison stored with sender_key = 'user:56970569'
    liaison = LiaisonRecord(
        liaison_id="liaison-saeedi-test",
        unit_id=unit.unit_id,
        full_name="حمید سعیدی",
        sender_key="user:56970569",
        eitaa_user_id="",
    )
    store.save_liaison(liaison)

    # 1. Resolve with exact sender_key 'user:56970569'
    l1, u1 = store.resolve_liaison_and_unit(sender_key="user:56970569")
    assert l1 is not None
    assert l1.full_name == "حمید سعیدی"
    assert u1 is not None

    # 2. Resolve with bare numeric id '56970569'
    l2, u2 = store.resolve_liaison_and_unit(sender_key="56970569")
    assert l2 is not None
    assert l2.full_name == "حمید سعیدی"

    # 3. Resolve with 'u:56970569' prefix
    l3, u3 = store.resolve_liaison_and_unit(sender_key="u:56970569")
    assert l3 is not None
    assert l3.full_name == "حمید سعیدی"

    # 4. Resolve via API dispatch
    status, payload, _ = v3.dispatch(
        store, "staff", ["editor"], "POST", "/api/v3/reporting/liaisons/resolve",
        payload={"sender_key": "user:56970569"},
    )
    assert status == 200
    assert payload["matched"] is True
    assert payload["liaison"]["full_name"] == "حمید سعیدی"


def test_resolve_hamid_saeedi_from_text_header(tmp_path: Path) -> None:
    """Ensure message #30743 scenario: author Arman with Saeedi text header resolves to Hamid Saeedi and Chahardangeh."""
    store = _make_store(tmp_path)
    text = "حمید سعیدی - حوزه قضایی چهاردانگه - دادگاه عمومی بخش\nبرگزاری مراسم قرائت زیارت عاشورا"
    liaison, unit = store.resolve_liaison_and_unit(full_name="Arman", text=text)
    assert liaison is not None
    assert liaison.full_name == "حمید سعیدی"
    assert unit is not None
    assert unit.display_name == "چهاردانگه - دادگاه عمومی بخش"
    assert unit.kind == "judicial_domain"

    # Also via API dispatch
    status, payload, _ = v3.dispatch(
        store, "staff", ["editor"], "POST", "/api/v3/reporting/liaisons/resolve",
        payload={"full_name": "Arman", "text": text},
    )
    assert status == 200
    assert payload["matched"] is True
    assert payload["liaison"]["full_name"] == "حمید سعیدی"
    assert payload["unit"]["display_name"] == "چهاردانگه - دادگاه عمومی بخش"
