import base64
import json
from datetime import date, datetime
from pathlib import Path
import pytest

from eitaa_bridge.reporting import (
    Fact,
    FactValueKind,
    UnitScope,
    ProgramId,
    ReportedEvent,
    ValueSource,
)
from eitaa_bridge.reporting.store import ReportingStore
from eitaa_bridge.application.reporting_api_v3 import dispatch


@pytest.fixture
def store(tmp_path: Path) -> ReportingStore:
    db_file = tmp_path / "test_dossier.db"
    return ReportingStore(db_file)


def _make_event(
    event_id: str,
    title: str = "اردوی فرهنگی مشهد",
    program: str = "trip",
    unit: str = "ساری - دادگستری",
    occurred: date = date(2026, 7, 10),
    micro_indicators: list[str] = None,
    attendees: float = 50.0,
) -> ReportedEvent:
    now = datetime(2026, 7, 10, 10, 0, 0)
    return ReportedEvent(
        event_id=event_id,
        program_kinds=(ProgramId(program),),
        occurred_on=occurred,
        unit=UnitScope.JUDICIAL_DOMAIN,
        unit_name=unit,
        occasion=title,
        official_present=True,
        macro_category="workbook_approved",
        custom_topic="",
        macro_indicator="برگزاری اردوهای فرهنگی زیارتی",
        micro_indicators=micro_indicators or ["اردوی سه روزه مشهد", "همایش فرهنگی خانواده"],
        notes="گزارش کامل برنامه به همراه عکس‌ها.",
        facts=(
            Fact(
                metric="attendees",
                value=attendees,
                value_kind=FactValueKind.OBSERVED,
                unit_of_measure="count",
                scope="province",
                evidence_refs=(),
                source=ValueSource.MANUAL,
                created_at=now,
            ),
        ),
        created_at=now,
        created_by="operator1",
        registered_by_id="user_123",
        registered_by_name="کارشناس امور فرهنگی",
        review_status="needs_review",
    )


def test_cascade_delete_event(store: ReportingStore):
    ev = _make_event("ev-del-1")
    store.save_event(ev)

    # Link witness
    store.link_witness(
        event_id="ev-del-1",
        peer_id="peer_100",
        message_id="999",
        actor="tester",
    )

    # Upload document
    store.upload_and_attach_document(
        "ev-del-1",
        filename="trip_photo.jpg",
        content_bytes=b"fake-image-bytes",
        is_cover=True,
        added_by="tester",
    )

    # Check that records exist
    f = store.get_event_file("ev-del-1")
    assert f is not None
    assert len(f["witnesses"]) == 1
    assert len(f["documents"]) == 1
    assert len(f["facts"]) == 1

    # Cascade delete via dispatch DELETE /api/v3/reporting/events/ev-del-1
    res = dispatch(store, "tester", {"editor"}, "DELETE", "/api/v3/reporting/events/ev-del-1")
    assert res is not None
    status, payload, _ = res
    assert status == 200
    assert payload["ok"] is True
    assert payload["deleted"] is True

    # Verify event is completely gone
    assert store.get_event_file("ev-del-1") is None

    # Verify witness link was unblocked so message 999 can be linked to another event
    ev2 = _make_event("ev-del-2")
    store.save_event(ev2)
    new_link = store.link_witness(
        event_id="ev-del-2",
        peer_id="peer_100",
        message_id="999",
        actor="tester",
    )
    assert new_link["link_id"].startswith("wl-")
    f2 = store.get_event_file("ev-del-2")
    assert len(f2["witnesses"]) == 1
    assert str(f2["witnesses"][0]["message_id"]) == "999"


def test_documents_upload_cover_view_and_delete(store: ReportingStore):
    ev = _make_event("ev-doc-1")
    store.save_event(ev)

    raw_bytes = b"PDF-FILE-SAMPLE-CONTENT-FOR-TESTING"
    b64_content = base64.b64encode(raw_bytes).decode("ascii")

    # 1. Upload via POST /api/v3/reporting/events/ev-doc-1/documents/upload
    res = dispatch(
        store,
        "tester",
        {"editor"},
        "POST",
        "/api/v3/reporting/events/ev-doc-1/documents/upload",
        payload={
            "filename": "survey_results.pdf",
            "content_base64": b64_content,
            "kind": "pdf",
            "is_cover": False,
        },
    )
    assert res is not None
    status, payload, _ = res
    assert status == 201
    assert payload["ok"] is True
    doc_id = payload["document"]["document_id"]
    assert payload["document"]["size_bytes"] == len(raw_bytes)

    # 2. View / stream document via GET /documents/{doc_id}/view
    view_res = dispatch(
        store,
        "tester",
        {"editor"},
        "GET",
        f"/api/v3/reporting/events/ev-doc-1/documents/{doc_id}/view",
    )
    assert view_res is not None
    v_status, v_payload, _ = view_res
    assert v_status == 200
    assert v_payload["ok"] is True
    assert v_payload["content_base64"] == b64_content
    assert v_payload["mime_type"] == "application/pdf"

    # 3. Set cover via POST /documents/{doc_id}/cover
    cov_res = dispatch(
        store,
        "tester",
        {"editor"},
        "POST",
        f"/api/v3/reporting/events/ev-doc-1/documents/{doc_id}/cover",
        payload={"is_cover": True},
    )
    assert cov_res is not None
    c_status, c_payload, _ = cov_res
    assert c_status == 200
    assert c_payload["is_cover"] is True

    # 4. Delete document via DELETE /documents/{doc_id}
    del_res = dispatch(
        store,
        "tester",
        {"editor"},
        "DELETE",
        f"/api/v3/reporting/events/ev-doc-1/documents/{doc_id}",
    )
    assert del_res is not None
    d_status, d_payload, _ = del_res
    assert d_status == 200
    assert d_payload["deleted"] is True

    # Check document is removed from event file
    file = store.get_event_file("ev-doc-1")
    assert len(file["documents"]) == 0


def test_smart_merge_candidates_and_merging(store: ReportingStore):
    # Target event: Trip in Sari
    ev1 = _make_event(
        "ev-target",
        title="اردوی زیارتی مشهد همکاران",
        program="trip",
        unit="ساری - دادگستری",
        occurred=date(2026, 7, 10),
        micro_indicators=["اردوی مشهد", "همایش خانواده"],
    )
    store.save_event(ev1)

    # Candidate 1: High match (same unit, same program, common micro indicator, same date)
    ev2 = _make_event(
        "ev-cand-1",
        title="اردوی تابستانه مشهد مقدس",
        program="trip",
        unit="ساری - دادگستری",
        occurred=date(2026, 7, 10),
        micro_indicators=["اردوی مشهد", "بخش ویژه فرزندآوری"],
    )
    store.save_event(ev2)

    # Candidate 2: Low match (different unit, contest program, different date)
    ev3 = _make_event(
        "ev-cand-2",
        title="مسابقات قرآن کریم",
        program="contest",
        unit="بابل - دادسرا",
        occurred=date(2026, 8, 20),
        micro_indicators=["مسابقات حفظ قرآن"],
    )
    store.save_event(ev3)

    # 1. Fetch merge candidates for ev-target
    cand_res = dispatch(
        store,
        "tester",
        {"editor"},
        "GET",
        "/api/v3/reporting/events/ev-target/merge-candidates",
    )
    assert cand_res is not None
    status, payload, _ = cand_res
    assert status == 200
    candidates = payload["candidates"]
    assert len(candidates) >= 1
    # First candidate should be ev-cand-1 with high score
    assert candidates[0]["event_id"] == "ev-cand-1"
    assert candidates[0]["score"] >= 80
    assert any("مشترک" in r for r in candidates[0]["reasons"])

    # 2. Upload doc to ev-cand-1 before merging
    store.upload_and_attach_document(
        "ev-cand-1",
        filename="cand_photo.jpg",
        content_bytes=b"cand-image-bytes",
        added_by="tester",
    )

    # 3. Execute merge: merge ev-cand-1 into ev-target
    merge_res = dispatch(
        store,
        "tester",
        {"editor"},
        "POST",
        "/api/v3/reporting/events/ev-target/merge",
        payload={"source_event_id": "ev-cand-1"},
    )
    assert merge_res is not None
    m_status, m_payload, _ = merge_res
    assert m_status == 200
    assert m_payload["target_event_id"] == "ev-target"

    # Verify target has combined micro-indicators
    tgt_file = store.get_event_file("ev-target")
    assert "اردوی مشهد" in tgt_file["micro_indicators"]
    assert "بخش ویژه فرزندآوری" in tgt_file["micro_indicators"]
    assert "همایش خانواده" in tgt_file["micro_indicators"]
    # Document should be transferred
    assert len(tgt_file["documents"]) >= 1

    # Verify source event was deleted
    assert store.get_event_file("ev-cand-1") is None


def test_unit_baselines_and_statistical_normalization(store: ReportingStore):
    unit_id = "نکا - دادگستری"
    # 1. Save unit baseline: 100 staff, 2.5 multiplier
    base_res = dispatch(
        store,
        "tester",
        {"editor"},
        "POST",
        f"/api/v3/reporting/units/{unit_id}/baseline",
        payload={
            "staff_count": 100,
            "family_multiplier": 2.5,
            "imams_count": 2,
            "prayer_rooms_count": 1,
            "honored_count": 5,
            "notes": "کادر اداری و قضایی شهرستان نکا",
        },
    )
    assert base_res is not None
    b_status, b_payload, _ = base_res
    assert b_status == 200
    assert b_payload["baseline"]["staff_count"] == 100

    # 2. Record normal event: 40 attendees in Neka
    ev_normal = _make_event(
        "ev-norm-1",
        title="اردوی زیارتی قم همکاران نکا",
        unit=unit_id,
        attendees=40.0,
    )
    store.save_event(ev_normal)

    norm_res = dispatch(
        store,
        "tester",
        {"editor"},
        "GET",
        "/api/v3/reporting/events/ev-norm-1/normalization",
    )
    assert norm_res is not None
    n_status, n_payload, _ = norm_res
    assert n_status == 200
    assert n_payload["reported_attendees"] == 40
    assert n_payload["attendance_rate_staff_pct"] == 40.0
    assert n_payload["has_anomalies"] is False

    # 3. Record anomalous event: 550 attendees (more than 5x total staff of 100)
    ev_anomaly = _make_event(
        "ev-norm-2",
        title="اردوی تفریحی جنگل با آمار غیرعادی",
        unit=unit_id,
        attendees=550.0,
    )
    store.save_event(ev_anomaly)

    anom_res = dispatch(
        store,
        "tester",
        {"editor"},
        "GET",
        "/api/v3/reporting/events/ev-norm-2/normalization",
    )
    assert anom_res is not None
    a_status, a_payload, _ = anom_res
    assert a_status == 200
    assert a_payload["has_anomalies"] is True
    assert len(a_payload["anomalies"]) > 0


def test_multi_event_dossier_bundle_export(store: ReportingStore):
    # Create 2 trip events
    ev1 = _make_event("ev-bnd-1", title="اردوی خانوادگی مشهد ۱")
    ev2 = _make_event("ev-bnd-2", title="اردوی زیارتی قم ۲")
    store.save_event(ev1)
    store.save_event(ev2)

    # Attach documents
    store.upload_and_attach_document(
        "ev-bnd-1",
        filename="mashhad_bus_invoice.pdf",
        content_bytes=b"sample-invoice-bytes",
        is_cover=False,
        added_by="tester",
    )
    store.upload_and_attach_document(
        "ev-bnd-1",
        filename="mashhad_group_photo.jpg",
        content_bytes=b"sample-photo-bytes",
        is_cover=True,
        added_by="tester",
    )
    store.upload_and_attach_document(
        "ev-bnd-2",
        filename="qom_survey_results.xlsx",
        content_bytes=b"sample-survey-bytes",
        is_cover=False,
        added_by="tester",
    )

    # Call export-dossier-bundle
    res = dispatch(
        store,
        "tester",
        {"editor"},
        "POST",
        "/api/v3/reporting/events/export-dossier-bundle",
        payload={"search": "اردوی"},
    )
    assert res is not None
    status, payload, _ = res
    assert status == 200
    assert payload["total_events"] == 2
    assert payload["total_documents"] == 3
    assert payload["file_name"].endswith(".zip")
    assert Path(payload["path"]).exists()

    # Verify zip contents
    import zipfile
    with zipfile.ZipFile(payload["path"], "r") as zf:
        namelist = zf.namelist()
        assert "خلاصه_آماری_رویدادها.xlsx" in namelist
        assert any("mashhad_group_photo" in n for n in namelist)
        assert any("qom_survey_results" in n for n in namelist)


def test_update_event_all_dossier_fields(store: ReportingStore):
    ev = _make_event("ev-patch-all-1", title="عنوان اولیه رویداد", unit="ساری - دادگستری")
    store.save_event(ev)

    file_before = store.get_event_file("ev-patch-all-1")
    assert file_before is not None
    etag_before = file_before["etag"]

    # Call PUT /api/v3/reporting/events/ev-patch-all-1 matching what ReportEventDetailModal sends
    res = dispatch(
        store,
        "editor_user",
        {"editor"},
        "PUT",
        "/api/v3/reporting/events/ev-patch-all-1",
        payload={
            "if_match": etag_before,
            "fields": {
                "occasion": "عنوان اصلاح شده رویداد فرهنگی",
                "macro_category": "workbook_approved",
                "custom_topic": "موضوع خاص سفارشی",
                "macro_indicator": "شاخص کلان اصلاح شده",
                "micro_indicators": ["شاخصه جزئی جدید ۱", "شاخصه جزئی جدید ۲"],
                "program_kinds": ["trip", "cultural"],
                "unit": "central_hq",
                "unit_name": "ستاد مرکزی استان",
                "occurred_on": "2026-07-15",
                "official_present": 1,
                "is_ashura_pilgrimage": 1,
                "notes": "یادداشت‌های به‌روزرسانی شده و تکمیلی رویداد",
                "facts": [
                    {
                        "metric": "attendees",
                        "value": 120,
                        "value_kind": "observed",
                        "unit_of_measure": "count",
                        "scope": "province",
                        "note": "حضور واقعی ثبت شده",
                    },
                    {
                        "metric": "family_members",
                        "value": 85,
                        "value_kind": "exact",  # should safely normalize to observed
                        "unit_of_measure": "count",
                        "scope": "province",
                    },
                ],
            },
        },
    )
    assert res is not None
    status, payload, _ = res
    assert status == 200
    assert payload["event_id"] == "ev-patch-all-1"
    new_etag = payload["etag"]
    assert new_etag != etag_before

    # Verify event file contents after update
    file_after = store.get_event_file("ev-patch-all-1")
    assert file_after is not None
    assert file_after["occasion"] == "عنوان اصلاح شده رویداد فرهنگی"
    assert file_after["macro_indicator"] == "شاخص کلان اصلاح شده"
    assert file_after["custom_topic"] == "موضوع خاص سفارشی"
    assert file_after["unit"] == "central_hq"
    assert file_after["unit_name"] == "ستاد مرکزی استان"
    assert file_after["occurred_on"] == "2026-07-15"
    assert file_after["notes"] == "یادداشت‌های به‌روزرسانی شده و تکمیلی رویداد"
    assert "شاخصه جزئی جدید ۱" in file_after["micro_indicators"]
    assert "trip" in file_after["program_kinds"]
    assert len(file_after["facts"]) == 2

