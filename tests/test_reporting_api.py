"""API endpoint tests for reporting core, candidate reviews, forms, and exports."""

from __future__ import annotations

from datetime import date
from pathlib import Path
import pytest

from eitaa_bridge.application.api import BridgeApplicationApi


@pytest.fixture
def reporting_api(config_file: Path, monkeypatch) -> BridgeApplicationApi:
    monkeypatch.setenv("TEST_WP_USERNAME", "editor")
    monkeypatch.setenv("TEST_WP_APP_PASSWORD", "password")
    return BridgeApplicationApi(config_file)


class TestReportingConfigEndpoints:
    def test_get_and_put_reporting_config(self, reporting_api: BridgeApplicationApi) -> None:
        get_resp = reporting_api.dispatch("GET", "/api/v2/reporting/config")
        assert get_resp.status == 200
        assert get_resp.payload["ok"] is True
        assert "config" in get_resp.payload
        assert "targets" in get_resp.payload
        assert len(get_resp.payload["targets"]) >= 2

        # Update configuration and add target
        put_resp = reporting_api.dispatch(
            "PUT",
            "/api/v2/reporting/config",
            body={
                "config": {"province_name": "سمنان", "report_period": "۱۴۰۶"},
                "targets": [
                    {
                        "label": "کانال قضایی سمنان",
                        "match_keywords": ["قضایی", "فرهنگی"],
                        "enabled": True,
                    }
                ],
            },
        )
        assert put_resp.status == 200
        assert put_resp.payload["config"]["province_name"] == "سمنان"
        labels = [t["label"] for t in put_resp.payload["targets"]]
        assert "کانال قضایی سمنان" in labels


class TestReportingScanAndCandidateWorkflow:
    def test_scan_texts_and_review_flow(self, reporting_api: BridgeApplicationApi) -> None:
        # Scan explicit messages
        scan_resp = reporting_api.dispatch(
            "POST",
            "/api/v2/reporting/scan",
            body={
                "messages": [
                    ["msg-api-1", "رابطان فرهنگی دادگستری", "مراسم سالگرد با حضور ۹۰ نفر در دادگستری نور برگزار شد"],
                    ["msg-api-2", "مدیریت امور فرهنگی دادگستری", "فراخوان ثبت نام مسابقات در ماه آینده منتشر میشود"],
                ]
            },
        )
        assert scan_resp.status == 200
        assert scan_resp.payload["ok"] is True
        res = scan_resp.payload["result"]
        assert res["scanned"] == 2
        assert res["event_reports"] == 1
        assert res["informational"] == 1

        # List candidates
        cand_resp = reporting_api.dispatch("GET", "/api/v2/reporting/candidates?status=pending")
        assert cand_resp.status == 200
        candidates = cand_resp.payload["candidates"]
        assert len(candidates) == 1
        cand_id = candidates[0]["candidate_id"]
        assert candidates[0]["extracted_attendees"] == 90

        # Approve candidate
        approve_resp = reporting_api.dispatch(
            "POST",
            f"/api/v2/reporting/candidates/{cand_id}/review",
            body={
                "action": "approve",
                "event_id": "api-approved-evt-1",
                "occurred_on": "2026-06-20",
                "unit": "judicial_domain",
                "unit_name": "دادگستری نور",
                "official_present": True,
            },
        )
        assert approve_resp.status == 200
        assert approve_resp.payload["status"] == "approved"
        assert approve_resp.payload["event_id"] == "api-approved-evt-1"

        # Candidate queue should now be empty of pending
        pending_resp = reporting_api.dispatch("GET", "/api/v2/reporting/candidates?status=pending")
        assert len(pending_resp.payload["candidates"]) == 0

        # Event should now appear in events list
        events_resp = reporting_api.dispatch("GET", "/api/v2/reporting/events")
        assert events_resp.status == 200
        events = events_resp.payload["events"]
        assert len(events) >= 1
        matched = next(e for e in events if e["event_id"] == "api-approved-evt-1")
        assert matched["unit_name"] == "دادگستری نور"
        assert matched["official_present"] is True

    def test_reject_candidate_flow(self, reporting_api: BridgeApplicationApi) -> None:
        reporting_api.dispatch(
            "POST",
            "/api/v2/reporting/scan",
            body={
                "messages": [
                    ["msg-api-rej", "رابطان فرهنگی دادگستری", "مراسم تکریم و تجلیل از همکاران با حضور ۳۰ نفر برگزار گردید"],
                ]
            },
        )
        cand_resp = reporting_api.dispatch("GET", "/api/v2/reporting/candidates?status=pending")
        cand_id = cand_resp.payload["candidates"][0]["candidate_id"]

        reject_resp = reporting_api.dispatch(
            "POST",
            f"/api/v2/reporting/candidates/{cand_id}/review",
            body={"action": "reject", "reason": "غیرمرتبط با برنامه‌های هفت‌گانه"},
        )
        assert reject_resp.status == 200
        assert reject_resp.payload["status"] == "rejected"

    def test_suggest_candidate_endpoint(self, reporting_api: BridgeApplicationApi) -> None:
        reporting_api.dispatch(
            "POST",
            "/api/v2/reporting/scan",
            body={
                "messages": [
                    ["msg-api-sug", "ستاد دادگستری کل", "قرائت زیارت عاشورا با حضور ۵۰ نفر برگزار گردید و پذیرایی شد"],
                ]
            },
        )
        cand_resp = reporting_api.dispatch("GET", "/api/v2/reporting/candidates?status=pending")
        cand_id = cand_resp.payload["candidates"][0]["candidate_id"]

        sug_resp = reporting_api.dispatch(
            "POST",
            f"/api/v2/reporting/candidates/{cand_id}/suggest",
            body={"text": "قرائت زیارت عاشورا با حضور ۵۰ نفر برگزار گردید و پذیرایی شد"},
        )
        assert sug_resp.status == 200
        assert sug_resp.payload["ok"] is True
        suggestion = sug_resp.payload["suggestion"]
        assert suggestion["is_ashura_pilgrimage"] is True
        assert suggestion["extracted_attendees"] == 50
        assert suggestion["star_field_hints"]["reception"] == 1


class TestReportingFormsAndExportEndpoints:
    def test_forms_list_get_and_save(self, reporting_api: BridgeApplicationApi) -> None:
        # List all forms
        forms_resp = reporting_api.dispatch("GET", "/api/v2/reporting/forms")
        assert forms_resp.status == 200
        assert forms_resp.payload["ok"] is True
        forms = forms_resp.payload["forms"]
        assert len(forms) == 7

        # Get specific ceremony form
        ceremony_resp = reporting_api.dispatch("GET", "/api/v2/reporting/forms/ceremonies")
        assert ceremony_resp.status == 200
        assert ceremony_resp.payload["form"]["program_id"] == "ceremonies"

        # Save answers for ceremony form
        save_resp = reporting_api.dispatch(
            "PUT",
            "/api/v2/reporting/forms/ceremonies",
            body={
                "answers": {
                    "province": "مازندران",
                    "report_period": "۱۴۰۵",
                    "row_scope": "جمع کل استان",
                    "ceremony_count": 10,
                    "attendees": 500,
                }
            },
        )
        assert save_resp.status == 200
        assert save_resp.payload["program_id"] == "ceremonies"

    def test_export_endpoint_blockers_and_audit(self, reporting_api: BridgeApplicationApi, tmp_path: Path) -> None:
        dest_file = tmp_path / "api_export.xlsx"

        # Without allow_unresolved_star, export should block on star cells
        block_resp = reporting_api.dispatch(
            "POST",
            "/api/v2/reporting/export",
            body={
                "destination": str(dest_file),
                "province_name": "مازندران",
                "report_period": "۱۴۰۵",
                "allow_unresolved_star": False,
            },
        )
        assert block_resp.status == 400
        assert block_resp.payload["error"]["code"] == "unresolved_star_cells"

        # With allow_unresolved_star=True, export succeeds and logs audit
        ok_resp = reporting_api.dispatch(
            "POST",
            "/api/v2/reporting/export",
            body={
                "destination": str(dest_file),
                "province_name": "مازندران",
                "report_period": "۱۴۰۵",
                "allow_unresolved_star": True,
            },
        )
        assert ok_resp.status == 200
        assert ok_resp.payload["ok"] is True
        assert dest_file.exists()

        # Check export audit records
        exports_resp = reporting_api.dispatch("GET", "/api/v2/reporting/exports")
        assert exports_resp.status == 200
        assert len(exports_resp.payload["exports"]) >= 1

    def test_office_wp_link_and_unlink(self, reporting_api: BridgeApplicationApi) -> None:
        store = reporting_api._reporting_store
        from eitaa_bridge.reporting import WpPostLink
        link = WpPostLink(
            link_id="wpl-test-1",
            post_slug="test-slug",
            title="پست تستی",
            section="prayer",
            match_status="unmatched",
        )
        store.save_wp_link(link)

        # 1. Link with section
        resp = reporting_api.dispatch(
            "POST",
            "/api/v3/office/wp-links/wpl-test-1/link",
            body={"section": "prayer"},
        )
        assert resp.status == 200
        assert resp.payload["ok"] is True
        loaded = store.list_wp_links(section="prayer")
        assert len(loaded) == 1
        assert loaded[0]["match_status"] == "confirmed"

        # 2. Unlink
        resp_unlink = reporting_api.dispatch(
            "POST",
            "/api/v3/office/wp-links/wpl-test-1/unlink",
            body={},
        )
        assert resp_unlink.status == 200
        loaded_unlinked = store.list_wp_links()
        assert loaded_unlinked[0]["match_status"] == "unmatched"
        assert loaded_unlinked[0]["event_id"] == ""

    def test_approve_candidate_with_sheet_dimensions(self, reporting_api: BridgeApplicationApi) -> None:
        # Scan one trip candidate
        scan_resp = reporting_api.dispatch(
            "POST",
            "/api/v2/reporting/scan",
            body={
                "messages": [
                    ["msg-trip-1", "کانال اردوها", "برگزاری اردوی زیارتی مشهد مقدس با حضور ۴۵ نفر از خانواده ها"],
                ]
            },
        )
        assert scan_resp.status == 200
        cand_resp = reporting_api.dispatch("GET", "/api/v2/reporting/candidates?status=pending")
        cand_id = cand_resp.payload["candidates"][0]["candidate_id"]

        # Approve with trip-specific sheet dimensions
        approve_resp = reporting_api.dispatch(
            "POST",
            f"/api/v2/reporting/candidates/{cand_id}/review",
            body={
                "action": "approve",
                "program_id": "trip",
                "event_id": "evt-trip-dynamic-1",
                "occurred_on": "2026-07-15",
                "unit": "judicial_domain",
                "unit_name": "سوادکوه",
                "attendee_count": 45,
                "dimension_facts": {
                    "trip_type_family": 1,
                    "insurance_count": 1,
                    "vehicle_count": 2,
                    "reception_count": 1,
                },
                "notes": "اردوی خانوادگی مشهد با وسیله نقلیه و بیمه کامل",
            },
        )
        assert approve_resp.status == 200
        assert approve_resp.payload["status"] == "approved"

        # Check stored event facts
        events_resp = reporting_api.dispatch("GET", "/api/v2/reporting/events")
        created_evt = next(e for e in events_resp.payload["events"] if e["event_id"] == "evt-trip-dynamic-1")
        fact_metrics = {f["metric"]: f["value"] for f in created_evt["facts"]}
        assert fact_metrics["attendees"] == 45
        assert fact_metrics["trip_type_family"] == 1
        assert fact_metrics["insurance_count"] == 1
        assert fact_metrics["vehicle_count"] == 2

    def test_create_manual_event_with_sheet_dimensions(self, reporting_api: BridgeApplicationApi) -> None:
        # Create manual contest event with specific dimensions
        resp = reporting_api.dispatch(
            "POST",
            "/api/v2/reporting/events",
            body={
                "program_id": "contest",
                "occurred_on": "2026-08-10",
                "unit": "provincial_hq",
                "unit_name": "ستاد مرکزی",
                "attendee_count": 120,
                "dimension_facts": {
                    "quran_attendees": 120,
                    "quran_staff": 1,
                    "quran_awards": 10,
                },
                "notes": "مسابقات سراسری قرآن کریم مرحله استانی",
            },
        )
        assert resp.status == 201
        assert resp.payload["ok"] is True
        evt_id = resp.payload["event_id"]

        events_resp = reporting_api.dispatch("GET", "/api/v2/reporting/events")
        created_evt = next(e for e in events_resp.payload["events"] if e["event_id"] == evt_id)
        fact_metrics = {f["metric"]: f["value"] for f in created_evt["facts"]}
        assert fact_metrics["attendees"] == 120
        assert fact_metrics["quran_attendees"] == 120
        assert fact_metrics["quran_awards"] == 10

    def test_forms_operational_description_and_program_codes(self, reporting_api: BridgeApplicationApi) -> None:
        resp = reporting_api.dispatch("GET", "/api/v2/reporting/forms")
        assert resp.status == 200
        forms = resp.payload["forms"]
        trip = next(f for f in forms if f["program_id"] == "trip")
        assert trip["program_code"] == "80401"
        assert trip["title"] == "80401 - اردو"
        assert "برگزاری اردوهای فرهنگی" in trip["operational_description"]
        assert len(trip["monitoring_criteria"]) >= 3
        assert "سند تحول" in trip["policy_framework"] or "رفاهی" in trip["policy_framework"]

    def test_mandate_crud_endpoints(self, reporting_api: BridgeApplicationApi) -> None:
        # 1. List initial canonical mandates
        resp = reporting_api.dispatch("GET", "/api/v2/reporting/mandates")
        assert resp.status == 200
        mandates = resp.payload["mandates"]
        assert len(mandates) >= 8
        trip_mnd = next(m for m in mandates if m["program_code"] == "80401")
        assert "اردو" in trip_mnd["title"]

        # 2. Filter by program_code
        filtered = reporting_api.dispatch("GET", "/api/v2/reporting/mandates?program_code=80401")
        assert filtered.status == 200
        assert all(m["program_code"] == "80401" for m in filtered.payload["mandates"])

        # 3. Create a custom mandate
        create_resp = reporting_api.dispatch(
            "POST",
            "/api/v2/reporting/mandates",
            body={
                "program_code": "80401",
                "kind": "circular",
                "title": "بخشنامه جدید استانی اردوهای پاییزه",
                "number": "۱۴۰۵/ب/۱۰",
                "issued_on": "۱۴۰۵/۰۷/۰۱",
                "document_ref": "دبیرخانه ستاد فرهنگی",
                "notes": "الزام برگزاری اردوی یک‌روزه کوهنوردی",
            },
        )
        assert create_resp.status == 201
        new_id = create_resp.payload["mandate"]["mandate_id"]

        # 4. Verify in list
        filtered2 = reporting_api.dispatch("GET", "/api/v2/reporting/mandates?program_code=80401")
        assert any(m["mandate_id"] == new_id for m in filtered2.payload["mandates"])

        # 5. Delete mandate
        del_resp = reporting_api.dispatch("DELETE", f"/api/v2/reporting/mandates/{new_id}")
        assert del_resp.status == 200
        assert del_resp.payload["ok"] is True

    def test_extended_forms_and_narrative_form_crud(self, reporting_api: BridgeApplicationApi) -> None:
        # 1. List with ?all=1 returns 8 forms including 80000 narrative
        resp = reporting_api.dispatch("GET", "/api/v2/reporting/forms?all=1")
        assert resp.status == 200
        forms = resp.payload["forms"]
        assert len(forms) == 8
        narrative = next(f for f in forms if f["program_code"] == "80000")
        assert narrative["program_id"] == "narrative"
        assert "گزارش عملکرد" in narrative["title"]

        # 2. Save narrative form
        save_resp = reporting_api.dispatch(
            "PUT",
            "/api/v2/reporting/forms/narrative",
            body={"answers": {"narrative_title": "اقدام تحولی نمونه", "narrative_allocated_budget": 50000000}},
        )
        assert save_resp.status == 200
        assert save_resp.payload["ok"] is True

        # 3. Get narrative form
        get_resp = reporting_api.dispatch("GET", "/api/v2/reporting/forms/narrative")
        assert get_resp.status == 200
        q_map = {q["key"]: q["current_value"] for q in get_resp.payload["form"]["questions"]}
        assert q_map["narrative_title"] == "اقدام تحولی نمونه"
        assert q_map["narrative_allocated_budget"] == 50000000


