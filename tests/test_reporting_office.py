"""Phase A/B tests: section registry, person registry, WP link layer,
synthetic surveys, workbook metric dictionary and the narrative form."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from eitaa_bridge.reporting import (
    METRIC_DICTIONARY,
    NARRATIVE_REPORT_FORM,
    OFFICE_SECTIONS,
    PersonRecord,
    ReportingStore,
    SECTIONS_BY_CODE,
    SyntheticSurvey,
    UnitScope,
    ValueSource,
    WpPostLink,
    classify_section,
    event_has_survey,
    extract_jalali_date,
    generate_survey,
    jalali_to_gregorian,
    parse_post_bundle,
    section_for_code,
    section_for_kind,
)


@pytest.fixture
def store(tmp_path: Path) -> ReportingStore:
    return ReportingStore(tmp_path / "office.db")


class TestSectionRegistry:
    def test_twelve_sections_seeded(self, store: ReportingStore) -> None:
        sections = store.list_sections()
        assert len(sections) == 12
        by_id = {s["section_id"] for s in sections}
        assert {"trip", "contest", "ceremonies", "prayer", "honor",
                "customer_care", "charter"} <= by_id
        assert {"training_courses", "content_production", "counseling",
                "education_services", "external_collaboration"} <= by_id

    def test_code_and_kind_lookup(self) -> None:
        assert section_for_code("80501").section_id == "prayer"
        assert section_for_code("99999") is None
        assert section_for_kind("trip").section_id == "trip"
        assert section_for_kind("prayer").section_id == "prayer"

    def test_operator_can_add_topic(self, store: ReportingStore) -> None:
        store.upsert_section(
            section_id="volunteer_program", title="برنامهٔ داوطلبانهٔ تازه",
            source="visit_worksheet", visit_label="برنامهٔ داوطلبانهٔ تازه",
        )
        sections = store.list_sections()
        assert any(s["section_id"] == "volunteer_program" for s in sections)

    def test_codebook_conflict_is_documented(self) -> None:
        # The visit worksheet prints 80403 for contests while the workbook
        # prints 80403 for ceremonies (ADR-61): the internal id is the truth.
        assert SECTIONS_BY_CODE["80403"].section_id == "ceremonies"


class TestPersonRegistry:
    def test_employee_roundtrip_and_version(self, store: ReportingStore) -> None:
        person = PersonRecord(
            person_id="p1", kind="employee", full_name="کارمند آزمایشی",
            personnel_no="11112222", unit_id="unit-a",
        )
        store.save_person(person)
        person.phone = "09110000000"
        store.save_person(person)
        loaded = store.list_persons(kind="employee")
        assert len(loaded) == 1
        assert loaded[0].version == 2
        assert loaded[0].phone == "09110000000"

    def test_family_requires_related_employee(self) -> None:
        with pytest.raises(ValueError, match="personnel number"):
            PersonRecord(person_id="f1", kind="family", full_name="فرزند آزمایشی").validate()
        child = PersonRecord(
            person_id="f2", kind="family", full_name="فرزند آزمایشی",
            relation="child", related_personnel_no="11112222",
        )
        child.validate()

    def test_family_lookup(self, store: ReportingStore) -> None:
        store.save_person(PersonRecord(person_id="e1", kind="employee",
                                       full_name="کارمند آزمایشی", personnel_no="11112222"))
        store.save_person(PersonRecord(person_id="c1", kind="family",
                                       full_name="فرزند الف", relation="child",
                                       related_personnel_no="11112222"))
        store.save_person(PersonRecord(person_id="c2", kind="family",
                                       full_name="همسر", relation="spouse",
                                       related_personnel_no="99999999"))
        family = store.person_family("11112222")
        assert len(family) == 1
        assert family[0].relation == "child"


class TestWpLinkLayer:
    def test_classify_sections(self) -> None:
        assert classify_section("برگزاری جشن تکلیف نومکلفان")[0] == "prayer"
        assert classify_section("اردوی زیارتی مشهد مقدس")[0] == "trip"
        assert classify_section("کارگاه اخلاق حرفه‌ای")[0] in {"charter", "training_courses"}
        assert classify_section("متن بی‌ربط")[0] == ""

    def test_jalali_conversion(self) -> None:
        # 1405/01/01 == 2026-03-21 (Nowruz 1405)
        assert jalali_to_gregorian(1405, 1, 1) == date(2026, 3, 21)
        assert jalali_to_gregorian(1405, 7, 1) == date(2026, 9, 23)

    def test_extract_date_from_text(self) -> None:
        assert extract_jalali_date("تاریخ برگزاری: 1405/03/25 در سالن") == date(2026, 6, 15)
        assert extract_jalali_date("بدون تاریخ") is None
        assert extract_jalali_date("تاریخ ۱۴۰۵/۰۵/۱۰") is not None

    def test_parse_post_bundle(self, tmp_path: Path) -> None:
        post_dir = tmp_path / "001-جشن-تکلیف"
        post_dir.mkdir()
        (post_dir / "post.html").write_text(
            "<html><head><title>جشن تکلیف حوزه مرکزی</title></head>"
            "<body><h1>جشن تکلیف حوزه مرکزی</h1><p>تاریخ: ۱۴۰۵/۰۲/۱۵</p></body></html>",
            encoding="utf-8",
        )
        parsed = parse_post_bundle(post_dir / "post.html")
        assert "جشن تکلیف" in parsed["title"]
        assert parsed["slug"].startswith("001-")
        section, confidence = classify_section(parsed["title"], parsed["body"])
        assert section == "prayer" and confidence >= 0.6

    def test_link_dedup_and_event_attachment(self, store: ReportingStore) -> None:
        link = WpPostLink(
            link_id="", post_slug="001-jashn-taklif", title="جشن تکلیف",
            source_ref="report-corpus:new/posts/001/post.html",
            section="prayer", published_on=date(2026, 6, 1),
        )
        first_id = store.save_wp_link(link)
        second_id = store.save_wp_link(link)
        assert first_id == second_id
        store.link_wp_post_to_event(first_id, "ev-1")
        links = store.list_wp_links()
        assert links[0]["event_id"] == "ev-1"
        assert links[0]["match_status"] == "confirmed"
        with pytest.raises(Exception, match="Invalid link status"):
            store.link_wp_post_to_event(first_id, "ev-2", match_status="bogus")


class TestSyntheticSurveys:
    def test_deterministic_generation(self) -> None:
        first = generate_survey("ev-100")
        second = generate_survey("ev-100")
        assert first.respondents == second.respondents
        assert first.satisfaction_percent == second.satisfaction_percent
        other = generate_survey("ev-101")
        assert (first.respondents, first.satisfaction_percent) != (
            other.respondents, other.satisfaction_percent
        )

    def test_synthetic_facts_never_export_ready(self) -> None:
        survey = generate_survey("ev-100")
        facts = survey.as_facts()
        assert len(facts) == 4
        for fact in facts:
            assert fact.value_kind.value == "synthetic_placeholder"
            assert not fact.is_export_ready()
            assert "synthetic-survey" in fact.note

    def test_event_has_survey_ignores_placeholders(self) -> None:
        survey = generate_survey("ev-100")
        assert not event_has_survey(survey.as_facts())

    def test_ranges_are_believable(self) -> None:
        from eitaa_bridge.reporting import validate_survey_metric

        for seed_id in (f"ev-{i}" for i in range(50)):
            s = generate_survey(seed_id)
            assert 12 <= s.respondents <= 55
            assert 61 <= s.satisfaction_percent <= 95
            validate_survey_metric(s.satisfaction_percent, "survey_satisfaction")


class TestWorkbookMetrics:
    def test_all_workbook_columns_registered(self) -> None:
        expected = {
            "trip_count", "attendees", "vehicle_count", "insurance_count",
            "contest_count", "quran_attendees", "ceremony_national",
            "ceremony_religious", "ceremony_revolutionary", "nominee_count",
            "imam_bank_count", "honoree_count", "correspondence_count",
            "board_count", "republish_count",
        }
        assert expected <= set(METRIC_DICTIONARY.all().__class__ and
                               {m.key for m in METRIC_DICTIONARY.all()})

    def test_dictionary_size_grew(self) -> None:
        assert len(METRIC_DICTIONARY) >= 80


class TestNarrativeForm:
    def test_narrative_form_maps_to_facts(self) -> None:
        keys = {q.key for q in NARRATIVE_REPORT_FORM.questions}
        assert {"narrative_title", "narrative_mandate_basis", "narrative_actions",
                "narrative_results", "narrative_obstacles", "narrative_proposals",
                "narrative_evidence", "narrative_allocated_budget",
                "narrative_spent_budget", "narrative_finance_notes"} == keys
        auto_map = {q.key: q.auto_from for q in NARRATIVE_REPORT_FORM.questions if q.auto_from}
        assert auto_map["narrative_obstacles"] == "program_obstacles"
        assert auto_map["narrative_spent_budget"] == "spent_budget"

    def test_narrative_form_prefills_from_section_facts(self) -> None:
        from eitaa_bridge.reporting import EntityFact, FilledForm
        from eitaa_bridge.reporting.forms import prefill_form

        # build a fake event-shaped fact carrier: prefill_form works over
        # ReportedEvent facts, so wrap section facts into a light shim.
        class _Shim:
            def __init__(self, facts):
                self.facts = facts

        facts = [
            EntityFact(fact_id="n1", entity_type="section", entity_id="section:prayer",
                       metric="program_obstacles", text_value="کمبود بودجه",
                       unit_of_measure="text"),
            EntityFact(fact_id="n2", entity_type="section", entity_id="section:prayer",
                       metric="allocated_budget", value=120_000_000.0,
                       unit_of_measure="currency"),
        ]
        shim = _Shim([
            type("F", (), {
                "metric": f.metric,
                "value": f.text_value if f.unit_of_measure == "text" else f.value,
                "value_kind": type("VK", (), {"value": f.value_kind})(),
                "source": type("S", (), {"value": f.source.value})(),
                "is_export_ready": lambda self: True,
            })()
            for f in facts
        ])
        filled = prefill_form(NARRATIVE_REPORT_FORM, [shim])
        assert filled.answers["narrative_obstacles"].value == "کمبود بودجه"
        assert filled.answers["narrative_allocated_budget"].value == 120_000_000.0

    def test_prefill_narrative_form_direct(self) -> None:
        from eitaa_bridge.reporting import EntityFact
        from eitaa_bridge.reporting.forms import prefill_narrative_form

        facts = [
            EntityFact(fact_id="n1", entity_type="section", entity_id="section:prayer",
                       metric="program_obstacles", text_value="کمبود زمان",
                       unit_of_measure="text"),
            EntityFact(fact_id="n2", entity_type="section", entity_id="section:prayer",
                       metric="allocated_budget", value=50_000_000.0,
                       unit_of_measure="currency"),
        ]
        filled = prefill_narrative_form("prayer", facts, title="توسعه نماز", mandate_basis="سند تحول")
        assert filled.answers["narrative_title"].value == "توسعه نماز"
        assert filled.answers["narrative_mandate_basis"].value == "سند تحول"
        assert filled.answers["narrative_obstacles"].value == "کمبود زمان"
        assert filled.answers["narrative_allocated_budget"].value == 50_000_000.0
