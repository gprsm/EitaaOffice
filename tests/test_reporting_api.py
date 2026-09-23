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
