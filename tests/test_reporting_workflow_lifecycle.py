"""Comprehensive adversarial test suite for reporting workflow lifecycle,
automated defect scanning, staff task delegation, and 360-degree scorecard.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import pytest

from eitaa_bridge.application.api import BridgeApplicationApi
from eitaa_bridge.reporting import (
    Fact,
    FactValueKind,
    ProgramKind,
    ReportedEvent,
    ReportingStore,
    UnitScope,
    ValueSource,
)
from eitaa_bridge.reporting.defect_scanner import DefectItem, scan_event_defects
from eitaa_bridge.reporting.store import ReportingStoreError


# ==============================================================================
# Fixtures
# ==============================================================================

@pytest.fixture
def store(tmp_path: Path) -> ReportingStore:
    db_file = tmp_path / "test_reporting_workflow.db"
    return ReportingStore(db_file)


@pytest.fixture
def reporting_api(config_file: Path, monkeypatch) -> BridgeApplicationApi:
    monkeypatch.setenv("TEST_WP_USERNAME", "editor")
    monkeypatch.setenv("TEST_WP_APP_PASSWORD", "password")
    api = BridgeApplicationApi(config_file)
    api._reporting_store.set_user_roles(
        "central_staff", {"editor", "approver", "admin"}, actor="bootstrap"
    )
    return api


# ==============================================================================
# 1. Defect Scanner Engine Tests
# ==============================================================================

class TestDefectScannerEngine:
    def test_rule1_missing_attendees_for_collective_programs(self) -> None:
        today = date.today()
        # Collective program: Ceremony with no attendee fact
        ceremony_event = ReportedEvent(
            event_id="evt-ceremony",
            program_kinds=(ProgramKind.CEREMONY,),
            occurred_on=today,
            unit=UnitScope.PROVINCIAL_HQ,
            unit_name="دادگستری کل استان مازندران",
        )
        defects = scan_event_defects(ceremony_event, witnesses_count=1)
        attendee_defects = [d for d in defects if d.defect_code == "missing_attendees"]
        assert len(attendee_defects) == 1
        assert attendee_defects[0].severity == "blocker"
        assert attendee_defects[0].field_name == "attendee_count"

        # Prayer program: warning severity instead of blocker
        prayer_event = ReportedEvent(
            event_id="evt-prayer",
            program_kinds=(ProgramKind.PRAYER,),
            occurred_on=today,
            unit=UnitScope.PROVINCIAL_HQ,
            unit_name="نمازخانه دادگستری",
        )
        p_defects = scan_event_defects(prayer_event, witnesses_count=1)
        p_att = [d for d in p_defects if d.defect_code == "missing_attendees"]
        assert len(p_att) == 1
        assert p_att[0].severity == "warning"

        # When attendees fact is added with value > 0 -> no defect
        prayer_with_attendees = ReportedEvent(
            event_id="evt-prayer-valid",
            program_kinds=(ProgramKind.PRAYER,),
            occurred_on=today,
            unit=UnitScope.PROVINCIAL_HQ,
            unit_name="نمازخانه دادگستری",
        )
        prayer_with_attendees.add_fact(
            Fact(
                metric="attendees",
                value=45.0,
                value_kind=FactValueKind.VERIFIED,
                source=ValueSource.EITAA,
            )
        )
        clean_defects = scan_event_defects(prayer_with_attendees, witnesses_count=1)
        assert not any(d.defect_code == "missing_attendees" for d in clean_defects)

    def test_rule2_date_validity(self) -> None:
        today = date.today()
        # Future date: Blocker
        future_event = ReportedEvent(
            event_id="evt-future",
            program_kinds=(ProgramKind.CUSTOMER_CARE,),
            occurred_on=today + timedelta(days=5),
            unit=UnitScope.PROVINCIAL_HQ,
            unit_name="دادگستری",
        )
        f_defects = scan_event_defects(future_event, witnesses_count=1)
        assert any(d.defect_code == "future_event_date" and d.severity == "blocker" for d in f_defects)

        # Outdated date (> 400 days): Warning
        outdated_event = ReportedEvent(
            event_id="evt-outdated",
            program_kinds=(ProgramKind.CUSTOMER_CARE,),
            occurred_on=today - timedelta(days=450),
            unit=UnitScope.PROVINCIAL_HQ,
            unit_name="دادگستری",
        )
        o_defects = scan_event_defects(outdated_event, witnesses_count=1)
        assert any(d.defect_code == "outdated_event_date" and d.severity == "warning" for d in o_defects)

        # Normal recent date: No date defect
        valid_event = ReportedEvent(
            event_id="evt-valid-date",
            program_kinds=(ProgramKind.CUSTOMER_CARE,),
            occurred_on=today - timedelta(days=10),
            unit=UnitScope.PROVINCIAL_HQ,
            unit_name="دادگستری",
        )
        v_defects = scan_event_defects(valid_event, witnesses_count=1)
        assert not any("date" in d.defect_code for d in v_defects)

    def test_rule3_missing_witness_and_evidence(self) -> None:
        today = date.today()
        # No witnesses, no documents, no evidence refs
        event = ReportedEvent(
            event_id="evt-no-witness",
            program_kinds=(ProgramKind.HONOR,),
            occurred_on=today,
            unit=UnitScope.PROVINCIAL_HQ,
            unit_name="دادگستری کل",
        )
        defects = scan_event_defects(event, witnesses_count=0, documents_count=0)
        assert any(d.defect_code == "missing_witness" and d.severity == "blocker" for d in defects)

        # Satisfied by witnesses_count > 0
        defects_with_witness = scan_event_defects(event, witnesses_count=1, documents_count=0)
        assert not any(d.defect_code == "missing_witness" for d in defects_with_witness)

        # Satisfied by documents_count > 0
        defects_with_doc = scan_event_defects(event, witnesses_count=0, documents_count=1)
        assert not any(d.defect_code == "missing_witness" for d in defects_with_doc)

        # Satisfied by event.evidence
        event_with_evidence = ReportedEvent(
            event_id="evt-ev",
            program_kinds=(ProgramKind.HONOR,),
            occurred_on=today,
            unit=UnitScope.PROVINCIAL_HQ,
            unit_name="دادگستری کل",
            evidence=("https://eitaa.com/msg/123",),
        )
        defects_ev = scan_event_defects(event_with_evidence, witnesses_count=0, documents_count=0)
        assert not any(d.defect_code == "missing_witness" for d in defects_ev)

        # Satisfied by fact evidence_refs
        event_with_fact_ev = ReportedEvent(
            event_id="evt-fact-ev",
            program_kinds=(ProgramKind.HONOR,),
            occurred_on=today,
            unit=UnitScope.PROVINCIAL_HQ,
            unit_name="دادگستری کل",
        )
        event_with_fact_ev.add_fact(
            Fact(
                metric="honorees",
                value=5.0,
                value_kind=FactValueKind.VERIFIED,
                evidence_refs=("msg-999",),
            )
        )
        defects_fe = scan_event_defects(event_with_fact_ev, witnesses_count=0, documents_count=0)
        assert not any(d.defect_code == "missing_witness" for d in defects_fe)

    def test_rule4_ambiguous_judiciary_hosting(self) -> None:
        today = date.today()
        # Provincial scope with empty unit name and no judiciary mention in text
        event = ReportedEvent(
            event_id="evt-ambiguous",
            program_kinds=(ProgramKind.HONOR,),
            occurred_on=today,
            unit=UnitScope.PROVINCIAL_HQ,
            unit_name="",
            notes="برگزاری تجلیل در سالن اجتماعات",
        )
        defects = scan_event_defects(event, witnesses_count=1)
        assert any(d.defect_code == "ambiguous_judiciary_hosting" and d.severity == "warning" for d in defects)

        # Resolved by having explicit unit_name
        event.unit_name = "دادگستری کل استان"
        defects_ok = scan_event_defects(event, witnesses_count=1)
        assert not any(d.defect_code == "ambiguous_judiciary_hosting" for d in defects_ok)

    def test_rule5_standalone_titled_occasion(self) -> None:
        today = date.today()
        # Standalone titled event without occasion
        event = ReportedEvent(
            event_id="evt-standalone",
            program_kinds=(ProgramKind.CONTEST,),
            occurred_on=today,
            unit=UnitScope.JUDICIAL_DOMAIN,
            unit_name="دادگستری بابل",
            is_standalone_titled=True,
            occasion="",
        )
        defects = scan_event_defects(event, witnesses_count=1)
        assert any(d.defect_code == "missing_occasion" and d.severity == "warning" for d in defects)

        # With occasion provided
        event.occasion = "گرامیداشت هفته دفاع مقدس"
        defects_ok = scan_event_defects(event, witnesses_count=1)
        assert not any(d.defect_code == "missing_occasion" for d in defects_ok)

    def test_rule6_media_attachment_info(self) -> None:
        today = date.today()
        event = ReportedEvent(
            event_id="evt-media",
            program_kinds=(ProgramKind.HONOR,),
            occurred_on=today,
            unit=UnitScope.JUDICIAL_DOMAIN,
            unit_name="دادگستری",
        )
        defects = scan_event_defects(event, witnesses_count=1, documents_count=0)
        assert any(d.defect_code == "missing_media_attachment" and d.severity == "info" for d in defects)

        # With document attached -> info defect goes away
        defects_with_doc = scan_event_defects(event, witnesses_count=1, documents_count=1)
        assert not any(d.defect_code == "missing_media_attachment" for d in defects_with_doc)

    def test_defect_item_to_dict(self) -> None:
        item = DefectItem(
            defect_code="test_code",
            severity="blocker",
            title="عنوان آزمایشی",
            description="شرح نقص",
            field_name="test_field",
        )
        d = item.to_dict()
        assert d == {
            "defect_code": "test_code",
            "severity": "blocker",
            "title": "عنوان آزمایشی",
            "description": "شرح نقص",
            "field_name": "test_field",
        }


# ==============================================================================
# 2. Store Workflow, Status Transitions, and Audit Tests
# ==============================================================================

class TestReportingStoreWorkflow:
    def test_workflow_fields_roundtrip(self, store: ReportingStore) -> None:
        today = date.today()
        reviewed_time = datetime(2026, 10, 12, 10, 0, tzinfo=timezone.utc)
        event = ReportedEvent(
            event_id="evt-wf-1",
            program_kinds=(ProgramKind.CEREMONY,),
            occurred_on=today,
            unit=UnitScope.PROVINCIAL_HQ,
            unit_name="دادگستری کل",
            review_status="needs_review",
            registered_by_id="staff-mohsan",
            registered_by_name="محسن رضایی",
            reviewed_by_id="mgr-alavi",
            reviewed_by_name="مدیر علوی",
            reviewed_at=reviewed_time,
            review_notes="نیازمند بازبینی تعداد شرکت‌کنندگان",
            revision_count=1,
            defects_json='[{"defect_code": "missing_attendees", "severity": "blocker"}]',
        )
        store.save_event(event)

        loaded = store.get_event("evt-wf-1")
        assert loaded is not None
        assert loaded.event_id == "evt-wf-1"
        assert loaded.review_status == "needs_review"
        assert loaded.registered_by_id == "staff-mohsan"
        assert loaded.registered_by_name == "محسن رضایی"
        assert loaded.reviewed_by_id == "mgr-alavi"
        assert loaded.reviewed_by_name == "مدیر علوی"
        assert loaded.reviewed_at == reviewed_time
        assert loaded.review_notes == "نیازمند بازبینی تعداد شرکت‌کنندگان"
        assert loaded.revision_count == 1
        assert "missing_attendees" in loaded.defects_json

        # List events check
        all_events = store.list_events()
        assert any(e.event_id == "evt-wf-1" and e.registered_by_id == "staff-mohsan" for e in all_events)

    def test_status_transitions_and_revision_cycle(self, store: ReportingStore) -> None:
        today = date.today()
        event = ReportedEvent(
            event_id="evt-lifecycle-1",
            program_kinds=(ProgramKind.CEREMONY,),
            occurred_on=today,
            unit=UnitScope.PROVINCIAL_HQ,
            unit_name="دادگستری کل",
            review_status="needs_review",
            registered_by_id="staff-1",
            registered_by_name="کارمند اول",
        )
        store.save_event(event)

        # 1. Manager requests revision
        store.transition_event_status(
            "evt-lifecycle-1",
            action="request_revision",
            actor="مدیر سیستم",
            reason="تعداد حاضرین نامشخص است",
            actor_id="mgr-1",
            actor_name="مدیر سیستم",
        )
        updated = store.get_event("evt-lifecycle-1")
        assert updated is not None
        assert updated.review_status == "needs_review"
        assert updated.revision_count == 1
        assert updated.review_notes == "تعداد حاضرین نامشخص است"
        assert updated.reviewed_by_id == "mgr-1"
        assert updated.reviewed_by_name == "مدیر سیستم"

        # 2. Manager approves
        store.transition_event_status(
            "evt-lifecycle-1",
            action="approve",
            actor="مدیر سیستم",
            reason="نواقص برطرف گردید",
            actor_id="mgr-1",
            actor_name="مدیر سیستم",
        )
        approved = store.get_event("evt-lifecycle-1")
        assert approved is not None
        assert approved.review_status == "approved"
        assert approved.revision_count == 1
        assert approved.review_notes == "نواقص برطرف گردید"

        # 3. Manager requests revision again from approved state
        store.transition_event_status(
            "evt-lifecycle-1",
            action="request_revision",
            actor="مدیر سیستم",
            reason="مجدداً نقص کشف شد",
            actor_id="mgr-1",
            actor_name="مدیر سیستم",
        )
        re_revised = store.get_event("evt-lifecycle-1")
        assert re_revised is not None
        assert re_revised.review_status == "needs_review"
        assert re_revised.revision_count == 2

        # 4. Invalid transition: from draft to request_revision
        draft_event = ReportedEvent(
            event_id="evt-draft-1",
            program_kinds=(ProgramKind.PRAYER,),
            occurred_on=today,
            unit=UnitScope.PROVINCIAL_HQ,
            unit_name="دادگستری",
            review_status="draft",
        )
        store.save_event(draft_event)

        with pytest.raises(ReportingStoreError) as exc_info:
            store.transition_event_status(
                "evt-draft-1",
                action="request_revision",
                actor="مدیر",
                reason="خطا",
            )
        assert "not allowed from status draft" in str(exc_info.value)

    def test_audit_diff_compliance(self, store: ReportingStore) -> None:
        today = date.today()
        event = ReportedEvent(
            event_id="evt-audit-strict",
            program_kinds=(ProgramKind.CONTEST,),
            occurred_on=today,
            unit=UnitScope.PROVINCIAL_HQ,
            unit_name="دادگستری",
            review_status="needs_review",
        )
        store.save_event(event)

        store.transition_event_status(
            "evt-audit-strict",
            action="request_revision",
            actor="مدیر ۱",
            reason="رفع ایراد",
            actor_id="mgr-1",
            actor_name="مدیر ۱",
        )

        audit_entries = store.get_event_audit("evt-audit-strict")
        assert len(audit_entries) >= 1
        last_entry = audit_entries[-1]
        # Diff must strictly only contain permitted keys
        allowed_diff_keys = {"from", "to", "reason"}
        assert set(last_entry["diff"].keys()).issubset(allowed_diff_keys)
        assert last_entry["actor"] == "مدیر ۱"

    def test_staff_reporting_stats_aggregation(self, store: ReportingStore) -> None:
        today = date.today()

        # Staff 1: 3 events (2 approved: 1 FTR, 1 reworked; 1 needs_review)
        store.save_event(
            ReportedEvent(
                event_id="evt-s1-1",
                program_kinds=(ProgramKind.CEREMONY,),
                occurred_on=today,
                unit=UnitScope.PROVINCIAL_HQ,
                unit_name="دادگستری",
                review_status="approved",
                registered_by_id="staff-1",
                registered_by_name="علی اکبری",
                revision_count=0,  # First-time right
            )
        )
        store.save_event(
            ReportedEvent(
                event_id="evt-s1-2",
                program_kinds=(ProgramKind.CONTEST,),
                occurred_on=today,
                unit=UnitScope.PROVINCIAL_HQ,
                unit_name="دادگستری",
                review_status="approved",
                registered_by_id="staff-1",
                registered_by_name="علی اکبری",
                revision_count=2,  # Reworked
            )
        )
        store.save_event(
            ReportedEvent(
                event_id="evt-s1-3",
                program_kinds=(ProgramKind.PRAYER,),
                occurred_on=today,
                unit=UnitScope.PROVINCIAL_HQ,
                unit_name="دادگستری",
                review_status="needs_review",
                registered_by_id="staff-1",
                registered_by_name="علی اکبری",
                revision_count=1,
            )
        )

        # Staff 2: 2 events (1 approved FTR, 1 conflict)
        store.save_event(
            ReportedEvent(
                event_id="evt-s2-1",
                program_kinds=(ProgramKind.TRIP,),
                occurred_on=today,
                unit=UnitScope.PROVINCIAL_HQ,
                unit_name="دادگستری",
                review_status="approved",
                registered_by_id="staff-2",
                registered_by_name="حسین حسینی",
                revision_count=0,  # First-time right
            )
        )
        store.save_event(
            ReportedEvent(
                event_id="evt-s2-2",
                program_kinds=(ProgramKind.HONOR,),
                occurred_on=today,
                unit=UnitScope.PROVINCIAL_HQ,
                unit_name="دادگستری",
                review_status="conflict",
                registered_by_id="staff-2",
                registered_by_name="حسین حسینی",
                revision_count=0,
            )
        )

        raw_stats = store.get_staff_reporting_stats()
        stats = {s["staff_id"]: s for s in raw_stats}
        assert "staff-1" in stats
        assert "staff-2" in stats

        s1 = stats["staff-1"]
        assert s1["staff_id"] == "staff-1"
        assert s1["staff_name"] == "علی اکبری"
        assert s1["total_reports"] == 3
        assert s1["approved_reports"] == 2
        assert s1["first_time_approved"] == 1
        assert s1["revision_required_reports"] == 2
        assert s1["approval_rate"] == 66.7
        assert s1["first_time_right_rate"] == 50.0

        s2 = stats["staff-2"]
        assert s2["staff_id"] == "staff-2"
        assert s2["total_reports"] == 2
        assert s2["approved_reports"] == 1
        assert s2["first_time_approved"] == 1
        assert s2["revision_required_reports"] == 0
        assert s2["approval_rate"] == 50.0
        assert s2["first_time_right_rate"] == 100.0


# ==============================================================================
# 3. API & Real-Time Orchestration Tests
# ==============================================================================

class TestReportingWorkflowApiAndScorecard:
    def test_api_defects_scan_endpoint(self, reporting_api: BridgeApplicationApi) -> None:
        # Create an event via v3 event draft creation
        create_resp = reporting_api.dispatch(
            "POST",
            "/api/v3/reporting/events",
            body={
                "program_kinds": ["ceremony"],
                "occurred_on": date.today().isoformat(),
                "unit": "provincial_hq",
                "unit_name": "دادگستری کل",
                "notes": "برگزاری مراسم",
                "registered_by_id": "staff-test",
                "registered_by_name": "کارمند آزمایشی",
            },
        )
        assert create_resp.status == 201
        event_id = create_resp.payload["event_id"]

        # 1. GET defects
        get_defects_resp = reporting_api.dispatch(
            "GET",
            f"/api/v3/reporting/events/{event_id}/defects",
        )
        assert get_defects_resp.status == 200
        assert get_defects_resp.payload["ok"] is True
        defects = get_defects_resp.payload["defects"]
        defect_codes = [d["defect_code"] for d in defects]
        assert "missing_attendees" in defect_codes
        assert "missing_witness" in defect_codes

        # 2. POST defects (re-scan)
        post_defects_resp = reporting_api.dispatch(
            "POST",
            f"/api/v3/reporting/events/{event_id}/defects",
        )
        assert post_defects_resp.status == 200
        assert post_defects_resp.payload["ok"] is True
        assert post_defects_resp.payload["defects_count"] >= 2

    def test_api_request_revision_and_auto_task_delegation(self, reporting_api: BridgeApplicationApi) -> None:
        # 1. Create candidate and approve to event
        scan_resp = reporting_api.dispatch(
            "POST",
            "/api/v2/reporting/scan",
            body={
                "messages": [
                    ["msg-rev-1", "رابطان فرهنگی دادگستری", "مراسم سالگرد با حضور ۹۰ نفر در دادگستری نور برگزار شد"],
                ]
            },
        )
        assert scan_resp.status == 200
        cand_resp = reporting_api.dispatch("GET", "/api/v2/reporting/candidates?status=pending")
        candidates = cand_resp.payload["candidates"]
        assert len(candidates) >= 1
        cand_id = candidates[0]["candidate_id"]

        approve_resp = reporting_api.dispatch(
            "POST",
            f"/api/v2/reporting/candidates/{cand_id}/review",
            body={
                "action": "approve",
                "event_id": "api-approved-evt-1",
                "occurred_on": date.today().isoformat(),
                "unit": "judicial_domain",
                "unit_name": "دادگستری نور",
                "staff_member": "staff-reza",
                "registered_by_id": "staff-reza",
                "registered_by_name": "رضا محمدی",
            },
        )
        assert approve_resp.status == 200
        event_id = approve_resp.payload["event_id"]

        # 2. Manager requests revision
        rev_resp = reporting_api.dispatch(
            "POST",
            f"/api/v3/reporting/events/{event_id}/request-revision",
            body={
                "notes": "عکس‌های مراسم و آمار نهایی ضمیمه گردد",
                "actor_id": "mgr-chief",
                "actor_name": "رئیس ارزشیابی",
            },
        )
        assert rev_resp.status == 200
        assert rev_resp.payload["ok"] is True

        get_evt = reporting_api.dispatch("GET", f"/api/v3/reporting/events/{event_id}")
        assert get_evt.status == 200
        evt_data = get_evt.payload["event"]
        assert evt_data["revision_count"] == 1
        assert evt_data["review_notes"] == "عکس‌های مراسم و آمار نهایی ضمیمه گردد"
        assert evt_data["reviewed_by_id"] == "mgr-chief"

        # 3. Verify task was automatically created in content_index_store
        tasks_resp = reporting_api.dispatch(
            "GET",
            "/api/v2/staff/tasks?assigned_to=staff-reza",
        )
        assert tasks_resp.status == 200
        tasks = tasks_resp.payload["tasks"]
        matching_tasks = [t for t in tasks if t["defect_type"] == "report_defect_resolution" and t.get("event_id") == event_id]
        assert len(matching_tasks) == 1
        defect_task = matching_tasks[0]
        assert defect_task["assigned_to_user_id"] == "staff-reza"
        assert defect_task["status"] == "open"
        assert defect_task["priority"] == "high"

        # 4. Manager approves the event -> defect task should automatically resolve
        app_resp = reporting_api.dispatch(
            "POST",
            f"/api/v3/reporting/events/{event_id}/approve",
            body={
                "actor": "رئیس ارزشیابی",
                "actor_id": "mgr-chief",
                "actor_name": "رئیس ارزشیابی",
                "reason": "ضمائم اصلاح شد",
            },
        )
        assert app_resp.status == 200
        assert app_resp.payload["ok"] is True

        # Check tasks again
        tasks_after = reporting_api.dispatch(
            "GET",
            "/api/v2/staff/tasks?assigned_to=staff-reza",
        ).payload["tasks"]
        task_after = next(t for t in tasks_after if t["task_id"] == defect_task["task_id"])
        assert task_after["status"] == "resolved"

    def test_composite_360_scorecard(self, reporting_api: BridgeApplicationApi) -> None:
        # Populate indexing action for staff-kian in content_index_store
        reporting_api._content_index_store.initialize()
        reporting_api._content_index_store.add_feedback(
            site_key="default",
            source_key="channel:12345:100",
            label_id=1,
            label_name="فرهنگی",
            decision="accept",
            peer_type="channel",
            peer_id="12345",
            message_id=100,
            operator_id="staff-kian",
            operator_name="کیان پیروز",
            operator_role="staff",
        )

        # Create report event registered by staff-kian and approved
        create_resp = reporting_api.dispatch(
            "POST",
            "/api/v3/reporting/events",
            body={
                "program_kinds": ["ceremony"],
                "occurred_on": date.today().isoformat(),
                "unit": "provincial_hq",
                "unit_name": "دادگستری کل",
                "registered_by_id": "staff-kian",
                "registered_by_name": "کیان پیروز",
                "facts": [
                    {
                        "metric": "attendees",
                        "value": 150.0,
                        "value_kind": "verified",
                    }
                ],
            },
        )
        assert create_resp.status == 201
        evt_id = create_resp.payload["event_id"]

        # Link a primary witness so the event has full documentary backing
        wit_resp = reporting_api.dispatch(
            "POST",
            f"/api/v3/reporting/events/{evt_id}/witnesses",
            body={
                "peer_id": "12345",
                "message_id": "100",
                "role": "primary",
            },
        )
        assert wit_resp.status == 201

        # Transition draft -> needs_review
        sub_resp = reporting_api.dispatch(
            "POST",
            f"/api/v3/reporting/events/{evt_id}/submit-review",
        )
        assert sub_resp.status == 200

        approve_resp = reporting_api.dispatch(
            "POST",
            f"/api/v3/reporting/events/{evt_id}/approve",
            body={
                "actor": "مدیر سیستم",
                "actor_id": "mgr-1",
                "actor_name": "مدیر سیستم",
                "reason": "تایید نهایی گزارش",
            },
        )
        assert approve_resp.status == 200

        # Fetch staff performance
        perf_resp = reporting_api.dispatch("GET", "/api/v2/staff/performance")
        assert perf_resp.status == 200
        payload = perf_resp.payload
        assert payload["ok"] is True
        summary = payload["summary"]
        assert "total_reports" in summary
        assert "approved_reports" in summary
        assert "average_composite_score" in summary

        staff_list = payload["staff"]
        kian_entry = next((s for s in staff_list if s["operator_id"] == "staff-kian"), None)
        assert kian_entry is not None
        assert kian_entry["total_reports"] >= 1
        assert kian_entry["approved_reports"] >= 1
        assert kian_entry["report_approval_rate"] == 100.0
        assert kian_entry["composite_score"] > 0.0
        # Accuracy score for indexing is 100%, reporting approval is 100%, FTR is 100%
        assert kian_entry["composite_score"] >= 85.0

    def test_adversarial_create_event_with_facts_clears_defects(self, reporting_api: BridgeApplicationApi) -> None:
        """Adversarial test: creating a collective event with facts must persist facts and clear missing_attendees defect."""
        create_resp = reporting_api.dispatch(
            "POST",
            "/api/v3/reporting/events",
            body={
                "program_kinds": ["ceremony"],
                "occurred_on": date.today().isoformat(),
                "unit": "provincial_hq",
                "unit_name": "ستاد مرکزی",
                "registered_by_id": "staff-sara",
                "registered_by_name": "سارا رضایی",
                "facts": [
                    {"metric": "attendees", "value": 85.0, "value_kind": "verified", "unit_of_measure": "count"}
                ],
            },
        )
        assert create_resp.status == 201
        evt_id = create_resp.payload["event_id"]

        # Verify fact was persisted in store
        ev = reporting_api._reporting_store.get_event(evt_id)
        assert ev is not None
        assert len(ev.facts) == 1
        assert ev.facts[0].metric == "attendees"
        assert ev.facts[0].value == 85.0

        # Verify defects scanner recognizes the attendees fact
        defects_resp = reporting_api.dispatch("GET", f"/api/v3/reporting/events/{evt_id}/defects")
        assert defects_resp.status == 200
        defect_codes = [d["defect_code"] for d in defects_resp.payload["defects"]]
        assert "missing_attendees" not in defect_codes

    def test_adversarial_approval_gate_blocks_on_defects(self, reporting_api: BridgeApplicationApi) -> None:
        """Adversarial test: approver cannot approve an event with blockers without explicit force_approve."""
        # Create flawed event (ceremony with 0 attendees and no evidence)
        create_resp = reporting_api.dispatch(
            "POST",
            "/api/v3/reporting/events",
            body={
                "program_kinds": ["ceremony"],
                "occurred_on": date.today().isoformat(),
                "unit": "provincial_hq",
                "unit_name": "ستاد",
                "registered_by_id": "staff-ali",
            },
        )
        evt_id = create_resp.payload["event_id"]

        # Transition to needs_review
        reporting_api.dispatch("POST", f"/api/v3/reporting/events/{evt_id}/submit-review")

        # Standard approve should be blocked with 422
        blocked_resp = reporting_api.dispatch(
            "POST",
            f"/api/v3/reporting/events/{evt_id}/approve",
            body={"reason": "تلاش برای تأیید کورکورانه"},
        )
        assert blocked_resp.status == 422
        assert blocked_resp.payload["ok"] is False
        assert blocked_resp.payload["error"]["error_code"] == "approval_blocked_by_defects"
        blockers = blocked_resp.payload["error"]["safe_context"]["blockers"]
        assert len(blockers) >= 1
        assert any(b["defect_code"] in {"missing_attendees", "missing_evidence"} for b in blockers)

        # Event remains in needs_review
        ev = reporting_api._reporting_store.get_event(evt_id)
        assert ev.review_status == "needs_review"

        # Force approve with explicit manager reason succeeds
        force_resp = reporting_api.dispatch(
            "POST",
            f"/api/v3/reporting/events/{evt_id}/approve",
            body={
                "force_approve": True,
                "reason": "تأیید استثنایی با دستور معاونت فرهنگی با وجود نقص مدارک",
                "actor_id": "mgr-chief",
                "actor_name": "معاونت فرهنگی",
            },
        )
        assert force_resp.status == 200
        ev_after = reporting_api._reporting_store.get_event(evt_id)
        assert ev_after.review_status == "approved"

    def test_adversarial_staff_performance_includes_task_only_staff(self, reporting_api: BridgeApplicationApi) -> None:
        """Adversarial test: staff member who only works on tasks appears in performance scorecard with correct metrics."""
        cis = reporting_api._content_index_store
        cis.initialize()

        # Create task assigned to task-only operator
        task = cis.create_task(
            title="اصلاح مستندات پرونده رویداد ۸۰۴۰۳",
            defect_type="missing_evidence",
            assigned_to_user_id="operator-taskonly",
            created_by_user_id="mgr-1",
        )
        task_id = task["task_id"]

        # Check performance before resolving
        perf_resp1 = reporting_api.dispatch("GET", "/api/v2/staff/performance")
        assert perf_resp1.status == 200
        staff_list1 = perf_resp1.payload["staff"]
        taskonly_entry = next((s for s in staff_list1 if s["operator_id"] == "operator-taskonly"), None)
        assert taskonly_entry is not None
        assert taskonly_entry["assigned_tasks"] == 1
        assert taskonly_entry["resolved_tasks"] == 0
        assert taskonly_entry["task_resolution_rate"] == 0.0

        # Resolve the task
        cis.resolve_task(
            task_id=task_id,
            resolution_notes="مستندات پیام بارگذاری و پیوند شد",
            user_id="operator-taskonly",
        )

        # Check performance after resolving
        perf_resp2 = reporting_api.dispatch("GET", "/api/v2/staff/performance")
        staff_list2 = perf_resp2.payload["staff"]
        taskonly_entry2 = next((s for s in staff_list2 if s["operator_id"] == "operator-taskonly"), None)
        assert taskonly_entry2 is not None
        assert taskonly_entry2["assigned_tasks"] == 1
        assert taskonly_entry2["resolved_tasks"] == 1
        assert taskonly_entry2["task_resolution_rate"] == 100.0
        assert taskonly_entry2["composite_score"] > 0.0

    def test_adversarial_list_events_filtering(self, reporting_api: BridgeApplicationApi) -> None:
        """Adversarial test: list_events properly filters by review_status and registered_by_id."""
        store = reporting_api._reporting_store

        # Create 2 events with different authors and statuses
        ev1 = ReportedEvent(
            event_id="evt-filter-1",
            program_kinds=(ProgramKind.HONOR,),
            occurred_on=date.today(),
            unit=UnitScope.PROVINCIAL_HQ,
            unit_name="واحد ۱",
            registered_by_id="staff-user-alpha",
            review_status="draft",
        )
        ev2 = ReportedEvent(
            event_id="evt-filter-2",
            program_kinds=(ProgramKind.PRAYER,),
            occurred_on=date.today(),
            unit=UnitScope.PROVINCIAL_HQ,
            unit_name="واحد ۲",
            registered_by_id="staff-user-beta",
            review_status="needs_review",
        )
        store.save_event(ev1)
        store.save_event(ev2)

        # Filter by review_status
        drafts = store.list_events(review_status="draft")
        assert any(e.event_id == "evt-filter-1" for e in drafts)
        assert not any(e.event_id == "evt-filter-2" for e in drafts)

        needs_rev = store.list_events(review_status="needs_review")
        assert any(e.event_id == "evt-filter-2" for e in needs_rev)
        assert not any(e.event_id == "evt-filter-1" for e in needs_rev)

        # Filter by registered_by_id
        alpha_events = store.list_events(registered_by_id="staff-user-alpha")
        assert any(e.event_id == "evt-filter-1" for e in alpha_events)
        assert not any(e.event_id == "evt-filter-2" for e in alpha_events)

        # Via GET /api/v3/reporting/events API endpoint with query string in URL
        api_filter_resp = reporting_api.dispatch(
            "GET",
            "/api/v3/reporting/events?review_status=needs_review&registered_by_id=staff-user-beta",
        )
        assert api_filter_resp.status == 200
        events_json = api_filter_resp.payload["events"]
        assert any(e["event_id"] == "evt-filter-2" for e in events_json)
        assert not any(e["event_id"] == "evt-filter-1" for e in events_json)
