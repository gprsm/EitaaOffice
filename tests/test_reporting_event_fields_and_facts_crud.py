"""Comprehensive CRUD and field-by-field verification test for ReportedEvents and Facts.

Tests every editable field in ReportedEvents individually and in combination,
ensuring zero regression and proper persistence of multiple facts and Jalali/ISO dates.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
import pytest

from eitaa_bridge.reporting.jalali_dates import (
    format_to_jalali_date,
    gregorian_to_jalali,
    jalali_to_gregorian,
    normalize_to_iso_date,
)
from eitaa_bridge.reporting.model import (
    Fact,
    FactValueKind,
    OccasionClass,
    ProgramKind,
    ReportedEvent,
    UnitScope,
    ValueSource,
)
from eitaa_bridge.reporting.store import ReportingStore


@pytest.fixture
def memory_store(tmp_path: Path) -> ReportingStore:
    db_path = tmp_path / "reporting_test.sqlite3"
    return ReportingStore(db_path, acquire_lease=False)


def test_jalali_date_conversion_and_normalization():
    # 27 Mehr 1405 corresponds to 19 October 2026
    gy, gm, gd = jalali_to_gregorian(1405, 7, 27)
    assert (gy, gm, gd) == (2026, 10, 19)

    jy, jm, jd = gregorian_to_jalali(2026, 10, 19)
    assert (jy, jm, jd) == (1405, 7, 27)

    # Normalization from Jalali strings
    assert normalize_to_iso_date("1405/07/27") == "2026-10-19"
    assert normalize_to_iso_date("1405-07-27") == "2026-10-19"
    assert normalize_to_iso_date("1405/07/28") == "2026-10-20"

    # Normalization from ISO strings
    assert normalize_to_iso_date("2026-10-19") == "2026-10-19"
    assert normalize_to_iso_date("2026-10-19 14:30:00") == "2026-10-19"
    assert normalize_to_iso_date("2026-10-19T08:00:00") == "2026-10-19"

    # Formatting to Jalali string
    assert format_to_jalali_date("2026-10-19") == "1405/07/27"


def test_update_event_every_single_editable_field(memory_store: ReportingStore):
    event = ReportedEvent(
        event_id="evt-test-crud-1",
        program_kinds=(ProgramKind.HONOR,),
        occurred_on=date(2026, 10, 1),
        unit=UnitScope.COURTHOUSE,
        unit_name="دادگاه عمومی بهشهر",
        occasion="عنوان اولیه",
        notes="یادداشت اولیه",
        created_by="تستر",
    )
    memory_store.save_event(event)

    etag = memory_store.get_event_etag("evt-test-crud-1")
    assert etag is not None

    # Update every single editable field with new values
    update_payload = {
        "occasion": "تقدیر از رئیس پیشین حوزه قضایی بندپی",
        "macro_category": "workbook_approved",
        "custom_topic": "تکریم مدیران قضایی",
        "macro_indicator": "تکریم و تجلیل از همکاران و خانواده",
        "micro_indicators": ["تجلیل از همکار بازنشسته", "مدیران برتر"],
        "program_kinds": ["honor"],
        "unit": "judicial_domain",
        "unit_name": "بندپی شرقی - دادگاه عمومی بخش",
        "occurred_on": "1405/07/27",  # Jalali date string should normalize to 2026-10-19
        "official_present": True,
        "is_ashura_pilgrimage": False,
        "is_standalone_titled": True,
        "notes": "برگزاری جلسه تجلیل با حضور کلیه قضات و کارکنان اداری",
        "facts": [
            {
                "metric": "honored_count",
                "value": 1.0,
                "unit_of_measure": "نفر",
                "note": "رئیس پیشین",
            },
            {
                "metric": "trip_type_staff",
                "value": 1.0,
                "unit_of_measure": "نفر",
                "note": "همکار پرسنل",
            },
        ],
    }

    new_etag = memory_store.update_event_fields(
        "evt-test-crud-1",
        actor="تستر",
        expected_etag=etag,
        fields=update_payload,
    )
    assert new_etag != etag

    # Retrieve and verify all updated fields
    loaded = memory_store.get_event("evt-test-crud-1")
    assert loaded is not None
    assert loaded.occasion == "تقدیر از رئیس پیشین حوزه قضایی بندپی"
    assert loaded.macro_category == "workbook_approved"
    assert loaded.custom_topic == "تکریم مدیران قضایی"
    assert loaded.macro_indicator == "تکریم و تجلیل از همکاران و خانواده"
    assert loaded.unit == UnitScope.JUDICIAL_DOMAIN
    assert loaded.unit_name == "بندپی شرقی - دادگاه عمومی بخش"
    assert loaded.occurred_on == date(2026, 10, 19)
    assert loaded.official_present is True
    assert loaded.is_ashura_pilgrimage is False
    assert loaded.is_standalone_titled is True
    assert loaded.notes == "برگزاری جلسه تجلیل با حضور کلیه قضات و کارکنان اداری"
    assert loaded.program_kinds == (ProgramKind.HONOR,)

    # Verify micro_indicators in event file projection
    event_file = memory_store.get_event_file("evt-test-crud-1")
    assert event_file is not None
    assert event_file["micro_indicators"] == ["تجلیل از همکار بازنشسته", "مدیران برتر"]

    # Verify both facts are persisted
    facts = loaded.facts
    assert len(facts) == 2
    metrics = {f.metric: f for f in facts}
    assert "honored_count" in metrics
    assert metrics["honored_count"].value == 1.0
    assert "trip_type_staff" in metrics
    assert metrics["trip_type_staff"].value == 1.0


def test_multi_fact_crud_and_preservation(memory_store: ReportingStore):
    event = ReportedEvent(
        event_id="evt-multi-facts-1",
        program_kinds=(ProgramKind.TRIP,),
        occurred_on=date(2026, 8, 10),
        unit=UnitScope.PROVINCIAL_HQ,
        unit_name="ستاد دادگستری کل مازندران",
        occasion="اردوی خانوادگی همکاران",
        created_by="تستر",
    )
    memory_store.save_event(event)
    etag = memory_store.get_event_etag("evt-multi-facts-1")

    # Initial 3 facts
    initial_facts = [
        {"metric": "attendees", "value": 45.0, "unit_of_measure": "نفر"},
        {"metric": "trip_type_staff", "value": 15.0, "unit_of_measure": "نفر"},
        {"metric": "trip_type_family", "value": 30.0, "unit_of_measure": "نفر"},
    ]
    etag = memory_store.update_event_fields(
        "evt-multi-facts-1",
        actor="تستر",
        expected_etag=etag,
        fields={"facts": initial_facts},
    )

    loaded = memory_store.get_event("evt-multi-facts-1")
    assert len(loaded.facts) == 3
    assert {f.metric for f in loaded.facts} == {"attendees", "trip_type_staff", "trip_type_family"}

    # Update facts: delete family, modify staff, add survey score
    updated_facts = [
        {"metric": "attendees", "value": 50.0, "unit_of_measure": "نفر"},
        {"metric": "trip_type_staff", "value": 20.0, "unit_of_measure": "نفر"},
        {"metric": "survey", "value": 18.5, "unit_of_measure": "نمره"},
    ]
    etag = memory_store.update_event_fields(
        "evt-multi-facts-1",
        actor="تستر",
        expected_etag=etag,
        fields={"facts": updated_facts},
    )

    loaded2 = memory_store.get_event("evt-multi-facts-1")
    assert len(loaded2.facts) == 3
    metrics = {f.metric: f.value for f in loaded2.facts}
    assert metrics["attendees"] == 50.0
    assert metrics["trip_type_staff"] == 20.0
    assert metrics["survey"] == 18.5
    assert "trip_type_family" not in metrics


def test_rejects_non_editable_fields(memory_store: ReportingStore):
    event = ReportedEvent(
        event_id="evt-reject-test",
        program_kinds=(ProgramKind.QURAN_CONTEST,),
        occurred_on=date(2026, 7, 1),
        unit=UnitScope.COURTHOUSE,
        unit_name="دادگستری قائمشهر",
        occasion="مسابقه قرآنی",
        created_by="تستر",
    )
    memory_store.save_event(event)
    etag = memory_store.get_event_etag("evt-reject-test")

    with pytest.raises(ValueError, match="fields not editable"):
        memory_store.update_event_fields(
            "evt-reject-test",
            actor="تستر",
            expected_etag=etag,
            fields={"event_id": "malicious_change", "occasion": "عنوان جدید"},
        )


def test_partial_update_preserves_unmodified_fields_and_facts(memory_store: ReportingStore):
    """Delta updates must only modify passed fields without collateral wiping of others."""
    event = ReportedEvent(
        event_id="evt-partial-1",
        program_kinds=(ProgramKind.HONOR,),
        occurred_on=date(2026, 10, 22),
        unit=UnitScope.JUDICIAL_DOMAIN,
        unit_name="دادگستری بهشهر",
        occasion="مراسم تقدیر از کارمندان نمونه دادگستری بهشهر در هفته قوه قضاییه",
        macro_indicator="شاخصه اولیه",
        notes="یادداشت اولیه",
        created_by="تستر",
    )
    memory_store.save_event(event)
    etag = memory_store.get_event_etag("evt-partial-1")

    # Add a fact
    etag = memory_store.update_event_fields(
        "evt-partial-1",
        actor="تستر",
        expected_etag=etag,
        fields={"facts": [{"metric": "honored_count", "value": 5.0, "unit_of_measure": "نفر"}]},
    )

    # Perform partial update changing ONLY macro_indicator
    new_etag = memory_store.update_event_fields(
        "evt-partial-1",
        actor="تستر",
        expected_etag=etag,
        fields={"macro_indicator": "تکریم و تجلیل از همکاران و خانواده"},
    )
    assert new_etag != etag

    # Verify macro_indicator was updated while occurred_on, program_kinds, facts, occasion remain intact!
    loaded = memory_store.get_event("evt-partial-1")
    assert loaded.macro_indicator == "تکریم و تجلیل از همکاران و خانواده"
    assert loaded.occurred_on == date(2026, 10, 22)
    assert loaded.program_kinds == (ProgramKind.HONOR,)
    assert loaded.occasion == "مراسم تقدیر از کارمندان نمونه دادگستری بهشهر در هفته قوه قضاییه"
    assert loaded.unit_name == "دادگستری بهشهر"
    assert len(loaded.facts) == 1
    assert loaded.facts[0].metric == "honored_count"
    assert loaded.facts[0].value == 5.0


def test_update_event_rejects_empty_mandatory_fields(memory_store: ReportingStore):
    """Updating mandatory fields like occurred_on and occasion to empty must be rejected."""
    event = ReportedEvent(
        event_id="evt-mandatory-1",
        program_kinds=(ProgramKind.HONOR,),
        occurred_on=date(2026, 10, 22),
        unit=UnitScope.COURTHOUSE,
        unit_name="دادگستری ساری",
        occasion="عنوان معتبر",
        created_by="تستر",
    )
    memory_store.save_event(event)
    etag = memory_store.get_event_etag("evt-mandatory-1")

    # Reject empty occurred_on
    with pytest.raises(ValueError, match="occurred_on"):
        memory_store.update_event_fields(
            "evt-mandatory-1",
            actor="تستر",
            expected_etag=etag,
            fields={"occurred_on": ""},
        )

    with pytest.raises(ValueError, match="occurred_on"):
        memory_store.update_event_fields(
            "evt-mandatory-1",
            actor="تستر",
            expected_etag=etag,
            fields={"occurred_on": "   "},
        )

    # Reject empty occasion
    with pytest.raises(ValueError, match="occasion"):
        memory_store.update_event_fields(
            "evt-mandatory-1",
            actor="تستر",
            expected_etag=etag,
            fields={"occasion": ""},
        )

    # Empty unit defaults to provincial_hq
    new_etag = memory_store.update_event_fields(
        "evt-mandatory-1",
        actor="تستر",
        expected_etag=etag,
        fields={"unit": ""},
    )
    assert memory_store.get_event("evt-mandatory-1").unit == UnitScope.PROVINCIAL_HQ


def test_get_and_list_events_crash_resilience_on_corrupt_db_records(memory_store: ReportingStore):
    """Corrupted legacy rows with empty occurred_on or non-standard program_kinds must not crash store."""
    # Directly inject corrupted row into SQLite to simulate bad database state
    with memory_store._connect() as conn:
        conn.execute(
            """
            INSERT INTO reported_events (
                event_id, program_kinds_json, occurred_on, unit, unit_name,
                occasion, occasion_class, official_present, is_standalone_titled,
                duration_minutes, prior_announcement, had_reception, is_ashura_pilgrimage,
                contains_inner_contest, notes, created_at, created_by, campaign,
                review_status, version, registered_by_id, registered_by_name,
                reviewed_by_id, reviewed_by_name, reviewed_at, review_notes,
                revision_count, defects_json, macro_category, custom_topic,
                macro_indicator, micro_indicators_json
            ) VALUES (
                'evt-corrupt-row', '["80406"]', '', 'courthouse', 'واحد تست',
                'رویداد با تاریخ خالی', NULL, 0, 1,
                NULL, 0, 0, 0,
                0, 'تست تاب‌آوری', '2026-10-22T08:00:00Z', 'تستر', '',
                'draft', 1, '', '',
                '', '', NULL, '',
                0, '[]', 'workbook_approved', '',
                '', '[]'
            )
            """
        )
        conn.commit()

    # get_event must NOT crash with ValueError: Invalid isoformat string
    event = memory_store.get_event("evt-corrupt-row")
    assert event is not None
    assert event.event_id == "evt-corrupt-row"
    assert isinstance(event.occurred_on, date)
    assert event.program_kinds == (ProgramKind.HONOR,)

    # list_events must NOT crash
    all_events = memory_store.list_events()
    assert any(e.event_id == "evt-corrupt-row" for e in all_events)


def test_ashura_pilgrimage_auto_derivation_from_micro_indicators_and_text(memory_store: ReportingStore):
    """Micro-indicator containing 'عاشورا' or Ashura text must auto-derive is_ashura_pilgrimage."""
    from eitaa_bridge.application.reporting_api_v3 import _build_event_payload

    # 1. Payload with micro_indicators containing 'عاشورا'
    p1 = {
        "event_id": "evt-ashura-auto-1",
        "occurred_on": "2026-10-24",
        "unit": "judicial_domain",
        "unit_name": "دادگستری نور",
        "topic": "مراسم هفتگی",
        "micro_indicators": ["قرائت زیارت عاشورا (C12)"],
    }
    ev1 = _build_event_payload(p1, store=memory_store)
    assert ev1.is_ashura_pilgrimage is True

    # 2. Payload with text mentioning زیارت عاشورا
    p2 = {
        "event_id": "evt-ashura-auto-2",
        "occurred_on": "2026-10-24",
        "unit": "judicial_domain",
        "unit_name": "چهاردانگه",
        "topic": "برگزاری مراسم پر فیض زیارت عاشورا",
        "micro_indicators": [],
    }
    ev2 = _build_event_payload(p2, store=memory_store)
    assert ev2.is_ashura_pilgrimage is True

    # 3. Explicit False must be respected
    p3 = {
        "event_id": "evt-ashura-auto-3",
        "occurred_on": "2026-10-24",
        "unit": "judicial_domain",
        "unit_name": "دادگستری بابل",
        "topic": "مراسم زیارت عاشورا",
        "is_ashura_pilgrimage": False,
    }
    ev3 = _build_event_payload(p3, store=memory_store)
    assert ev3.is_ashura_pilgrimage is False

    # 4. Updating micro_indicators via update_event_fields auto-toggles is_ashura_pilgrimage
    base_event = ReportedEvent(
        event_id="evt-ashura-update-1",
        program_kinds=(ProgramKind.CEREMONY,),
        occurred_on=date(2026, 10, 24),
        unit=UnitScope.JUDICIAL_DOMAIN,
        unit_name="دادگستری نور",
        occasion="مراسم فرهنگی",
        is_ashura_pilgrimage=False,
    )
    memory_store.save_event(base_event)
    etag = memory_store.get_event_etag("evt-ashura-update-1")
    assert memory_store.get_event("evt-ashura-update-1").is_ashura_pilgrimage is False

    memory_store.update_event_fields(
        "evt-ashura-update-1",
        actor="tester",
        expected_etag=etag,
        fields={"micro_indicators": ["قرائت زیارت عاشورا"]},
    )
    updated_ev = memory_store.get_event("evt-ashura-update-1")
    assert updated_ev.is_ashura_pilgrimage is True


def test_delete_document_physical_file_cleanup_and_id_flexibility(memory_store: ReportingStore, tmp_path: Path):
    """Deleting a document must physically remove its storage_ref file and support media_id matching."""
    event_id = "evt-doc-del-test"
    ev = ReportedEvent(
        event_id=event_id,
        program_kinds=(ProgramKind.CEREMONY,),
        occurred_on=date(2026, 10, 24),
        unit=UnitScope.JUDICIAL_DOMAIN,
        unit_name="دادگستری نور",
        occasion="رویداد تست سند",
    )
    memory_store.save_event(ev)

    # Create dummy physical file
    doc_file = tmp_path / "test_photo.jpg"
    doc_file.write_bytes(b"\xff\xd8\xff\xe0" + b"dummy image content" * 100)
    assert doc_file.exists()

    # Attach document
    doc_info = memory_store.attach_document(
        event_id=event_id,
        document_id="doc-uuid-1234",
        media_id="channel_6015778_30743_30039444340.jpg",
        sha256="dummy_sha256",
        kind="photo",
        size_bytes=len(doc_file.read_bytes()),
        display_order=1,
        is_cover=True,
        added_by="tester",
        storage_ref=str(doc_file),
    )
    assert doc_info["document_id"] == "doc-uuid-1234"

    # Delete by media_id (or document_id)
    deleted = memory_store.delete_document(event_id, "channel_6015778_30743_30039444340.jpg", actor="tester")
    assert deleted is True

    # Assert physical file is removed from disk
    assert not doc_file.exists(), "Physical file must be deleted upon document deletion"


def test_find_merge_candidates_prioritized_ranking_hierarchy(memory_store: ReportingStore):
    """Smart merge candidate ranking must prioritize:
    1. Macro indicator match
    2. Micro indicators similarity degree
    3. Judicial unit match
    """
    target = ReportedEvent(
        event_id="evt-target-ranking",
        program_kinds=(ProgramKind.HONOR,),
        occurred_on=date(2026, 10, 24),
        unit=UnitScope.JUDICIAL_DOMAIN,
        unit_name="دادگستری نور",
        occasion="مراسم تکریم و تجلیل",
        macro_indicator="تجلیل و تکریم از کارکنان",
        micro_indicators=["تکریم بازنشستگان", "اهدای لوح تقدیر"],
    )
    memory_store.save_event(target)

    # Cand A: Matches Macro (Priority 1), partial micro, different unit
    cand_a = ReportedEvent(
        event_id="evt-cand-a",
        program_kinds=(ProgramKind.HONOR,),
        occurred_on=date(2026, 10, 24),
        unit=UnitScope.JUDICIAL_DOMAIN,
        unit_name="دادگستری ساری",
        occasion="مراسم تجلیل اداری",
        macro_indicator="تجلیل و تکریم از کارکنان",
        micro_indicators=["تکریم بازنشستگان"],
    )
    memory_store.save_event(cand_a)

    # Cand B: Different Macro, identical micros and unit
    cand_b = ReportedEvent(
        event_id="evt-cand-b",
        program_kinds=(ProgramKind.QURAN_CONTEST,),
        occurred_on=date(2026, 10, 24),
        unit=UnitScope.JUDICIAL_DOMAIN,
        unit_name="دادگستری نور",
        occasion="مسابقات قرآنی",
        macro_indicator="برگزاری مسابقات قرآنی",
        micro_indicators=["تکریم بازنشستگان", "اهدای لوح تقدیر"],
    )
    memory_store.save_event(cand_b)

    # Cand C: Matches Macro (Priority 1) + 100% micro match (Priority 2) + Same Unit (Priority 3)
    cand_c = ReportedEvent(
        event_id="evt-cand-c",
        program_kinds=(ProgramKind.HONOR,),
        occurred_on=date(2026, 10, 24),
        unit=UnitScope.JUDICIAL_DOMAIN,
        unit_name="دادگستری نور",
        occasion="مراسم تکریم همکاران",
        macro_indicator="تجلیل و تکریم از کارکنان",
        micro_indicators=["تکریم بازنشستگان", "اهدای لوح تقدیر"],
    )
    memory_store.save_event(cand_c)

    candidates = memory_store.find_merge_candidates("evt-target-ranking", limit=10)
    candidate_ids = [c["event_id"] for c in candidates]

    # Cand C must be #1 (matches all 3 priorities)
    assert candidate_ids[0] == "evt-cand-c"

    # Cand A must be #2 because Macro Indicator is Priority 1, outranking Cand B (no macro match)
    assert candidate_ids[1] == "evt-cand-a"

    # Cand B must be #3
    assert candidate_ids[2] == "evt-cand-b"




