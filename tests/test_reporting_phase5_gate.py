"""Gate tests for Unified Reporting Phase 5: Assistant and Scoped Feedback.

Verifies:
1. Conservative suggester behavior: abstains on ambiguous text (never blind-guesses).
2. Rule explainability and provenance: rule_version, rule_name, and signal details.
3. Scoped feedback recording, listing, and revocation.
4. Scoped alias lifecycle, namespace isolation, and role authorization.
5. v3 API dispatch integration for assistant feedback and aliases.
"""

from __future__ import annotations

import pytest
from pathlib import Path

from eitaa_bridge.reporting import ReportingStore
from eitaa_bridge.reporting.suggester import ReportingSuggester
from eitaa_bridge.reporting.service import ReportingService
from eitaa_bridge.application.api import BridgeApplicationApi


@pytest.fixture
def store(tmp_path: Path) -> ReportingStore:
    return ReportingStore(tmp_path / "test_reporting_p5.sqlite3", acquire_lease=False)


@pytest.fixture
def api(config_file: Path) -> BridgeApplicationApi:
    return BridgeApplicationApi(config_file)


class TestPhase5SuggesterConservative:
    """Verifies that ReportingSuggester adheres to Strategy §7 & §9.5."""

    def test_suggester_abstains_on_ambiguous_text(self) -> None:
        suggester = ReportingSuggester()
        # Generic text with no explicit keywords for any program
        ambiguous_text = "جلسه اداری داخلی پیرامون بررسی امور جاری برگزار گردید."
        sugg = suggester.analyze(
            candidate_id="cand-ambig-1",
            text=ambiguous_text,
            matched_programs=(),
            dialog_label="",
        )

        assert sugg.is_abstain is True
        assert sugg.recommended_program == "unknown"
        assert sugg.confidence == 0.0
        assert sugg.rule_name == "rule_abstain"
        assert "Abstain" in sugg.reasoning
        assert sugg.provenance["is_abstain"] is True
        assert sugg.provenance["rule_version"] == "1.0"

    def test_suggester_ashura_and_official_presence_rule_c12_and_b9(self) -> None:
        suggester = ReportingSuggester()
        text = (
            "مراسم پرفیض قرائت زیارت عاشورا با حضور حجت‌الاسلام والمسلمین اکبری "
            "رئیس کل دادگستری استان مازندران در نمازخانه دادگستری کل با حضور ۱۵۰ نفر همکار برگزار شد."
        )
        sugg = suggester.analyze(
            candidate_id="cand-ashura-1",
            text=text,
            matched_programs=(),
            dialog_label="کانال رسمی دادگستری",
        )

        assert sugg.is_ashura_pilgrimage is True
        assert sugg.official_present_suggested is True
        assert sugg.recommended_program == "ceremonies"
        assert sugg.confidence >= 0.90
        assert sugg.rule_name == "rule_c12_ashura"
        assert sugg.extracted_attendees == 150
        assert sugg.provenance["is_ashura"] is True
        assert sugg.provenance["official_present"] is True

    def test_suggester_scoped_alias_matching_and_isolation(self) -> None:
        suggester = ReportingSuggester()
        alias_prayer = {
            "alias_text": "همایش اقامه نماز",
            "canonical_target": "prayer",
            "target_type": "program",
            "weight": 0.92,
            "status": "active",
        }

        # 1. Matches active scoped alias
        text = "همایش اقامه نماز کارکنان در سالن اجتماعات برگزار شد."
        sugg = suggester.analyze(
            candidate_id="cand-alias-1",
            text=text,
            scoped_aliases=(alias_prayer,),
        )
        assert sugg.recommended_program == "prayer"
        assert sugg.confidence == 0.92
        assert sugg.rule_name == "rule_scoped_alias"
        assert "همایش اقامه نماز" in sugg.reasoning

        # 2. Inactive/revoked alias does not match -> falls back or abstains
        revoked_alias = {**alias_prayer, "status": "revoked"}
        ambig_text = "همایش اقامه نماز جلسه عمومی"
        sugg_revoked = suggester.analyze(
            candidate_id="cand-alias-2",
            text="جلسه عمومی بدون نشانه",
            scoped_aliases=(revoked_alias,),
        )
        assert sugg_revoked.is_abstain is True
        assert sugg_revoked.recommended_program == "unknown"


    def test_suggester_enforces_alias_scope_isolation(self) -> None:
        suggester = ReportingSuggester()
        unit_alias = {
            "alias_text": "جلسه هم‌اندیشی",
            "canonical_target": "honor",
            "target_type": "program",
            "scope_kind": "unit",
            "scope_target": "دادگستری ساری",
            "weight": 0.9,
            "status": "active",
        }
        program_alias = {
            "alias_text": "کارگاه آموزشی",
            "canonical_target": "trip",
            "target_type": "program",
            "scope_kind": "program",
            "scope_target": "contest",
            "weight": 0.9,
            "status": "active",
        }
        local_alias = {
            "alias_text": "مراسم افتتاح",
            "canonical_target": "ceremonies",
            "target_type": "program",
            "scope_kind": "local",
            "scope_target": "cand-local-77",
            "weight": 0.9,
            "status": "active",
        }

        # Unit-scoped alias without unit evidence in the text -> abstain, no pollution
        sugg = suggester.analyze("c1", "جلسه هم‌اندیشی برگزار شد", scoped_aliases=(unit_alias,))
        assert sugg.is_abstain is True
        assert sugg.recommended_program == "unknown"

        # Unit evidence present -> alias applies
        sugg = suggester.analyze(
            "c2", "جلسه هم‌اندیشی در دادگستری ساری برگزار شد", scoped_aliases=(unit_alias,)
        )
        assert sugg.recommended_program == "honor"
        assert sugg.rule_name == "rule_scoped_alias"

        # Program-scoped alias only fires when the indexer matched that program
        sugg = suggester.analyze("c3", "کارگاه آموزشی برگزار شد", scoped_aliases=(program_alias,))
        assert sugg.is_abstain is True
        sugg = suggester.analyze(
            "c4", "کارگاه آموزشی برگزار شد", matched_programs=("contest",), scoped_aliases=(program_alias,)
        )
        assert sugg.recommended_program == "trip"

        # Local-scoped alias applies only to its own candidate
        sugg = suggester.analyze("cand-local-77", "مراسم افتتاح برگزار شد", scoped_aliases=(local_alias,))
        assert sugg.recommended_program == "ceremonies"
        sugg = suggester.analyze("cand-other", "مراسم افتتاح برگزار شد", scoped_aliases=(local_alias,))
        assert sugg.is_abstain is True


class TestPhase5ServiceAliasScopeWiring:
    """Service-level injection must not leak scoped aliases into unrelated contexts."""

    def test_service_scoped_alias_isolation(self, store: ReportingStore) -> None:
        store.add_scoped_alias(
            alias_text="جلسه هم‌اندیشی",
            canonical_target="honor",
            target_type="program",
            approved_by="supervisor-1",
            scope_kind="unit",
            scope_target="دادگستری ساری",
            weight=0.9,
        )
        service = ReportingService(store=store)

        unrelated = service.suggest_candidate_review(
            "cand-iso-1", text="جلسه هم‌اندیشی برگزار شد"
        )
        assert unrelated.is_abstain is True
        assert unrelated.recommended_program == "unknown"

        related = service.suggest_candidate_review(
            "cand-iso-2", text="جلسه هم‌اندیشی در دادگستری ساری برگزار شد"
        )
        assert related.recommended_program == "honor"
        assert related.rule_name == "rule_scoped_alias"


class TestPhase5StoreFeedbackAndAliases:
    """Verifies ReportingStore assistant feedback and scoped aliases operations."""

    def test_feedback_record_list_and_revoke_lifecycle(self, store: ReportingStore) -> None:
        rec = store.record_assistant_feedback(
            candidate_id="cand-test-1",
            actor="operator-1",
            action="correct",
            scope_kind="unit",
            scope_target="دادگستری ساری",
            suggested_program="ceremonies",
            chosen_program="prayer",
            notes="جلسه اقامه نماز بود نه مراسم عمومی",
        )
        assert rec["feedback_id"].startswith("afb-")
        assert rec["action"] == "correct"
        assert rec["chosen_program"] == "prayer"

        # List feedback
        active_list = store.list_assistant_feedback(candidate_id="cand-test-1")
        assert len(active_list) == 1
        assert active_list[0]["feedback_id"] == rec["feedback_id"]
        assert active_list[0]["revoked_at"] is None

        # Revoke feedback
        store.revoke_assistant_feedback(rec["feedback_id"], actor="auditor-1")

        # Excluded when not including revoked
        active_after = store.list_assistant_feedback(candidate_id="cand-test-1", include_revoked=False)
        assert len(active_after) == 0

        # Included when include_revoked=True
        all_after = store.list_assistant_feedback(candidate_id="cand-test-1", include_revoked=True)
        assert len(all_after) == 1
        assert all_after[0]["revoked_by"] == "auditor-1"

    def test_scoped_alias_creation_and_revocation(self, store: ReportingStore) -> None:
        alias = store.add_scoped_alias(
            alias_text="تکریم بازنشستگان دادگستری",
            canonical_target="honor",
            target_type="program",
            approved_by="supervisor-1",
            scope_kind="unit",
            scope_target="دادگستری بابل",
            weight=0.95,
        )
        assert alias["alias_id"].startswith("alias-")
        assert alias["status"] == "active"

        # List active
        active_aliases = store.list_scoped_aliases(scope_kind="unit", status="active")
        assert any(a["alias_id"] == alias["alias_id"] for a in active_aliases)

        # Revoke
        store.revoke_scoped_alias(alias["alias_id"], actor="admin-1")
        revoked_aliases = store.list_scoped_aliases(status="revoked")
        assert any(a["alias_id"] == alias["alias_id"] for a in revoked_aliases)

    def test_global_alias_requires_approval(self, store: ReportingStore) -> None:
        with pytest.raises(ValueError, match="global aliases require explicit approval"):
            store.add_scoped_alias(
                alias_text="تست",
                canonical_target="ceremonies",
                target_type="program",
                approved_by="",
                scope_kind="global",
            )


class TestPhase5ApiDispatchIntegration:
    """Verifies HTTP / dispatch routing for assistant endpoints."""

    def test_assistant_feedback_and_alias_endpoints(self, api: BridgeApplicationApi) -> None:
        # Bootstrap admin roles for testing
        api.dispatch("POST", "/api/v3/reporting/users/roles", body={"user_id": "central_staff", "roles": ["admin", "editor", "approver"]})

        # 1. Record feedback
        fb_resp = api.dispatch(
            "POST",
            "/api/v3/reporting/assistant/feedback",
            body={
                "candidate_id": "cand-api-1",
                "action": "accept",
                "scope_kind": "local",
                "suggested_program": "trip",
                "chosen_program": "trip",
            },
        )
        assert fb_resp.status == 201
        assert fb_resp.payload["ok"] is True
        fb_id = fb_resp.payload["feedback_id"]

        # 2. List feedback
        list_resp = api.dispatch("GET", "/api/v3/reporting/assistant/feedback")
        assert list_resp.status == 200
        assert any(f["feedback_id"] == fb_id for f in list_resp.payload["feedback"])

        # 3. Revoke feedback
        rev_resp = api.dispatch("POST", f"/api/v3/reporting/assistant/feedback/{fb_id}/revoke")
        assert rev_resp.status == 200
        assert rev_resp.payload["ok"] is True

        # 4. Add alias
        alias_resp = api.dispatch(
            "POST",
            "/api/v3/reporting/assistant/aliases",
            body={
                "alias_text": "جشن تکلیف فرزندان دادگستری",
                "canonical_target": "prayer",
                "target_type": "program",
                "scope_kind": "program",
            },
        )
        assert alias_resp.status == 201
        assert alias_resp.payload["ok"] is True
        alias_id = alias_resp.payload["alias_id"]

        # 5. List aliases
        aliases_list_resp = api.dispatch("GET", "/api/v3/reporting/assistant/aliases")
        assert aliases_list_resp.status == 200
        assert any(a["alias_id"] == alias_id for a in aliases_list_resp.payload["aliases"])

        # 6. Revoke alias
        alias_rev_resp = api.dispatch("POST", f"/api/v3/reporting/assistant/aliases/{alias_id}/revoke")
        assert alias_rev_resp.status == 200
        assert alias_rev_resp.payload["ok"] is True

    def test_global_alias_via_api_requires_admin_role(self, tmp_path: Path) -> None:
        from eitaa_bridge.application import reporting_api_v3 as v3

        store = ReportingStore(tmp_path / "role_gate.sqlite3")
        store.set_user_roles("editor_user", {"editor"}, actor="bootstrap")
        editor_roles = store.get_user_roles("editor_user")

        payload = {
            "alias_text": "الیاس سراسری آزمونی",
            "canonical_target": "ceremonies",
            "target_type": "program",
            "scope_kind": "global",
        }
        status, body, _ = v3.dispatch(
            store, "editor_user", editor_roles,
            "POST", "/api/v3/reporting/assistant/aliases", payload,
        )
        assert status == 403

        status, body, _ = v3.dispatch(
            store, "chief", ["admin", "editor", "approver"],
            "POST", "/api/v3/reporting/assistant/aliases", payload,
        )
        assert status == 201
        assert body["ok"] is True
