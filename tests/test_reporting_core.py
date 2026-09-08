"""Tests for the 1405 reporting core: rules, aggregation, forms, gates, export."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from eitaa_bridge.reporting import (
    ALL_FORMS,
    FORMS_BY_PROGRAM,
    Fact,
    FactValueKind,
    OccasionClass,
    ProgramId,
    ProgramKind,
    Program,
    ReportedEvent,
    ReportingService,
    UnitScope,
    ValueSource,
    export_unified_report,
)
from eitaa_bridge.reporting.aggregate import aggregate_program_report
from eitaa_bridge.reporting.eitaa_extraction import EitaaCandidateExtractor
from eitaa_bridge.reporting.excel_export import (
    ASHURA_ANNEX_SHEET_NAME,
    TemplateNotFoundError,
    UnresolvedStarCellsError,
    find_template,
)
from eitaa_bridge.reporting.forms import prefill_form
from eitaa_bridge.reporting.model import CANONICAL_PROGRAMS, PROGRAM_CODES
from eitaa_bridge.reporting.rules import CountingRuleEngine, RULES_VERSION


def _event(**kwargs) -> ReportedEvent:
    defaults = dict(
        event_id="evt-1",
        program_kinds=(ProgramKind.CEREMONY,),
        occurred_on=date(2026, 5, 1),
        unit=UnitScope.JUDICIAL_DOMAIN,
        unit_name="سوادکوه شمالی",
    )
    defaults.update(kwargs)
    return ReportedEvent(**defaults)


def _fact(metric: str = "attendees", value: int = 40, kind: FactValueKind = FactValueKind.VERIFIED) -> Fact:
    return Fact(metric=metric, value=value, value_kind=kind)


# --------------------------------------------------------------------------
# Model and program registry
# --------------------------------------------------------------------------


class TestProgramRegistry:
    def test_seven_canonical_programs(self) -> None:
        assert len(CANONICAL_PROGRAMS) == 7

    def test_ceremonies_code_is_user_mandate_80403(self) -> None:
        ceremonies = next(p for p in CANONICAL_PROGRAMS if p.program_id is ProgramId.CEREMONIES)
        assert ceremonies.code == "80403"

    def test_codes_unique(self) -> None:
        codes = [program.code for program in CANONICAL_PROGRAMS]
        assert len(codes) == len(set(codes))
        assert set(codes) <= set(PROGRAM_CODES)

    def test_programs_validate(self) -> None:
        for program in CANONICAL_PROGRAMS:
            program.validate()

    def test_workbook_sheets_covered(self) -> None:
        sheets = {program.workbook_sheet for program in CANONICAL_PROGRAMS}
        assert "مراسم  مذهبی" in sheets  # double space preserved as in template
        assert len(sheets) == 7


# --------------------------------------------------------------------------
# Counting rules (workbook footnotes)
# --------------------------------------------------------------------------


class TestCountingRules:
    def test_regular_ceremony_counts(self) -> None:
        engine = CountingRuleEngine()
        assert engine.ceremony_countable(_event()) is True

    def test_ashura_pilgrimage_excluded_from_main_count(self) -> None:
        engine = CountingRuleEngine()
        event = _event(is_ashura_pilgrimage=True)
        assert engine.ceremony_countable(event) is False

    def test_inner_contest_classified_to_contests_program(self) -> None:
        engine = CountingRuleEngine()
        event = _event(
            program_kinds=(ProgramKind.CEREMONY, ProgramKind.CONTEST),
            contains_inner_contest=True,
        )
        shares = engine.classify(event)
        by_program = {share.program_id: share for share in shares}
        assert by_program[ProgramId.CEREMONIES].counts is True
        assert by_program[ProgramId.CONTEST].counts is True

    def test_session_requires_all_three_conditions(self) -> None:
        engine = CountingRuleEngine()
        assert engine.session_valid(_event(duration_minutes=45, prior_announcement=True, had_reception=True)) is True
        assert engine.session_valid(_event(duration_minutes=30, prior_announcement=True, had_reception=True)) is False
        assert engine.session_valid(_event(duration_minutes=45, prior_announcement=False, had_reception=True)) is False
        assert engine.session_valid(_event(duration_minutes=45, prior_announcement=True, had_reception=False)) is False
        assert engine.session_valid(_event()) is False

    def test_honor_requires_official_presence_and_standalone_title(self) -> None:
        engine = CountingRuleEngine()
        base = dict(program_kinds=(ProgramKind.HONOR,))
        assert engine.classify(_event(**base, official_present=True, is_standalone_titled=True))[0].counts is True
        assert engine.classify(_event(**base, official_present=None))[0].counts is False
        assert engine.classify(_event(**base, official_present=False))[0].counts is False
        assert engine.classify(_event(**base, official_present=True, is_standalone_titled=False))[0].counts is False

    def test_customer_care_requires_official_presence(self) -> None:
        engine = CountingRuleEngine()
        base = dict(program_kinds=(ProgramKind.CUSTOMER_CARE,))
        assert engine.classify(_event(**base, official_present=True))[0].counts is True
        assert engine.classify(_event(**base, official_present=None))[0].counts is False

    def test_export_gate_blocks_estimated_and_synthetic(self) -> None:
        engine = CountingRuleEngine()
        assert engine.export_gate(FactValueKind.VERIFIED) is True
        assert engine.export_gate(FactValueKind.OBSERVED) is True
        assert engine.export_gate(FactValueKind.REPORTED_BY_UNIT) is True
        assert engine.export_gate(FactValueKind.ESTIMATED) is False
        assert engine.export_gate(FactValueKind.SYNTHETIC_PLACEHOLDER) is False

    def test_rules_are_versioned(self) -> None:
        assert RULES_VERSION == "workbook-1405-rules-v1"


# --------------------------------------------------------------------------
# Aggregation
# --------------------------------------------------------------------------


class TestAggregation:
    def test_province_aggregate_counts_events(self) -> None:
        events = [_event(event_id="a"), _event(event_id="b", unit=UnitScope.PROVINCIAL_HQ)]
        report = aggregate_program_report(ProgramId.CEREMONIES, events)
        assert report.counts.get("ceremony") == 2

    def test_occasion_class_breakdown(self) -> None:
        events = [
            _event(event_id="n", occasion_class=OccasionClass.NATIONAL),
            _event(event_id="r", occasion_class=OccasionClass.RELIGIOUS),
            _event(event_id="r2", occasion_class=OccasionClass.RELIGIOUS),
        ]
        report = aggregate_program_report(ProgramId.CEREMONIES, events)
        assert report.counts["ceremony_national"] == 1
        assert report.counts["ceremony_religious"] == 2

    def test_ashura_goes_to_annex_not_main_count(self) -> None:
        events = [
            _event(event_id="main"),
            _event(event_id="ash", is_ashura_pilgrimage=True),
        ]
        events[1].add_fact(_fact(value=120))
        report = aggregate_program_report(ProgramId.CEREMONIES, events)
        assert report.counts.get("ceremony") == 1
        assert report.ashura_pilgrimage_count == 1
        assert report.ashura_pilgrimage_attendees == 120
        assert any(item["reason"] == "ashura_pilgrimage_separate_annex_c12" for item in report.excluded)

    def test_excluded_events_do_not_count(self) -> None:
        events = [_event(event_id="x", program_kinds=(ProgramKind.HONOR,), official_present=None)]
        report = aggregate_program_report(ProgramId.HONOR, events)
        assert report.counts.get("honor") is None
        assert report.excluded[0]["reason"] == "official_presence_unconfirmed_b9"

    def test_attendees_aggregate_only_exportable_values(self) -> None:
        events = [_event(event_id="a"), _event(event_id="b")]
        events[0].add_fact(_fact(value=30, kind=FactValueKind.VERIFIED))
        events[1].add_fact(_fact(value=50, kind=FactValueKind.ESTIMATED))
        report = aggregate_program_report(ProgramId.CEREMONIES, events)
        assert report.attendees_total == 30
        assert len(report.value_kind_warnings) == 1

    def test_breakdown_by_unit_preserved_for_annex(self) -> None:
        events = [
            _event(event_id="a", unit_name="سوادکوه شمالی"),
            _event(event_id="b", unit=UnitScope.PROVINCIAL_HQ, unit_name=""),
        ]
        report = aggregate_program_report(ProgramId.CEREMONIES, events)
        assert report.breakdown_by_unit["سوادکوه شمالی"]["events"] == 1
        assert report.breakdown_by_unit["ستاد استانی"]["events"] == 1

    def test_unified_summary_covers_all_programs(self) -> None:
        service = ReportingService()
        summary = service.aggregator.unified_summary([_event()])
        assert set(summary["programs"]) == {pid.value for pid in ProgramId}


# --------------------------------------------------------------------------
# Forms: definitions, prefill, star/human gates
# --------------------------------------------------------------------------


class TestForms:
    def test_seven_forms_with_unique_programs(self) -> None:
        assert len(ALL_FORMS) == 7
        assert len(FORMS_BY_PROGRAM) == 7
        for form in ALL_FORMS:
            form.validate()

    def test_prefill_autocomputes_attendees_from_events(self) -> None:
        events = [_event(event_id="a"), _event(event_id="b")]
        events[0].add_fact(_fact(value=30))
        events[1].add_fact(_fact(value=20))
        form = prefill_form(FORMS_BY_PROGRAM["ceremonies"], events)
        assert form.answers["attendees"].value == 50

    def test_prefill_prefers_exportable_facts(self) -> None:
        events = [_event(event_id="a")]
        events[0].add_fact(_fact(value=10, kind=FactValueKind.ESTIMATED))
        events[0].add_fact(_fact(value=30, kind=FactValueKind.VERIFIED))
        form = prefill_form(FORMS_BY_PROGRAM["ceremonies"], events)
        assert form.answers["attendees"].value == 30

    def test_prefill_leaves_human_gates_empty(self) -> None:
        events = [_event(event_id="a", program_kinds=(ProgramKind.HONOR,), official_present=True)]
        form = prefill_form(FORMS_BY_PROGRAM["honor"], events)
        assert "official_present" not in form.answers
        assert "standalone_titled" not in form.answers

    def test_star_keys_reported_unresolved(self) -> None:
        # No facts attached: every star question except header context stays open.
        form = prefill_form(FORMS_BY_PROGRAM["ceremonies"], [_event()])
        missing = form.unresolved_star_keys(FORMS_BY_PROGRAM["ceremonies"])
        assert "ceremony_religious" in missing
        assert "ceremony_national" in missing
        assert "attendees" in missing

        # With an attendees fact, the auto-derived answer resolves that star cell.
        event = _event(event_id="with-fact")
        event.add_fact(_fact(value=35))
        form2 = prefill_form(FORMS_BY_PROGRAM["ceremonies"], [event])
        missing2 = form2.unresolved_star_keys(FORMS_BY_PROGRAM["ceremonies"])
        assert "attendees" not in missing2
        assert "ceremony_religious" in missing2

    def test_ashura_questions_present_in_ceremonies_form(self) -> None:
        definition = FORMS_BY_PROGRAM["ceremonies"]
        keys = {question.key for question in definition.questions}
        assert {"ashura_pilgrimage_count", "ashura_pilgrimage_attendees"} <= keys


# --------------------------------------------------------------------------
# Eitaa extraction (Level 1)
# --------------------------------------------------------------------------


class TestEitaaExtraction:
    def test_extracts_ceremony_candidate_with_attendees(self) -> None:
        extractor = EitaaCandidateExtractor()
        candidate = extractor.extract(
            "مراسم عزاداری محرم با حضور ۱۲۰ نفر در سوادکوه شمالی برگزار شد",
            message_ref="eitaa:1001:55",
        )
        assert candidate is not None
        assert ProgramKind.CEREMONY in candidate.suggested_kinds
        assert candidate.extracted_attendees == 120
        assert candidate.occasion_class is OccasionClass.RELIGIOUS

    def test_ashura_pilgrimage_detected(self) -> None:
        extractor = EitaaCandidateExtractor()
        candidate = extractor.extract("زیارت عاشورا در ستاد استانی با ۴۰ نفر برگزار گردید", message_ref="eitaa:1:2")
        assert candidate is not None
        assert candidate.is_ashura_pilgrimage is True
        assert candidate.occasion_class is None  # ashura never carries occasion class

    def test_honor_and_contest_multi_kind(self) -> None:
        extractor = EitaaCandidateExtractor()
        candidate = extractor.extract("مراسم تکریم با مسابقه قرآنی همراه بود", message_ref="r:1")
        assert ProgramKind.HONOR in candidate.suggested_kinds
        assert ProgramKind.QURAN_CONTEST in candidate.suggested_kinds

    def test_unrelated_message_abstains(self) -> None:
        extractor = EitaaCandidateExtractor()
        assert extractor.extract("یک نکته درباره تعویض ساعت امروز اطلاعیه شد", message_ref="x:1") is None

    def test_service_event_from_candidate_keeps_provenance(self) -> None:
        service = ReportingService()
        candidate = service.candidates_from_message(
            "اردوی زیارتی کارکنان با ۶۵ نفر انجام شد", message_ref="eitaa:7:9"
        )
        assert candidate is not None
        event = service.event_from_candidate(
            candidate,
            event_id="evt-trip-1",
            occurred_on=date(2026, 4, 12),
        )
        assert event.facts[0].source is ValueSource.EITAA
        assert event.facts[0].evidence_refs == ("eitaa:7:9",)
        assert event.facts[0].value_kind is FactValueKind.REPORTED_BY_UNIT


# --------------------------------------------------------------------------
# Excel export
# --------------------------------------------------------------------------


class TestExcelExport:
    def test_find_template(self) -> None:
        template = find_template()
        assert template.exists()
        assert template.name.endswith(".xlsx")

    def test_template_not_found_raises(self, tmp_path: Path) -> None:
        with pytest.raises(TemplateNotFoundError):
            find_template(tmp_path)

    def test_export_blocks_on_unresolved_star_cells(self, tmp_path: Path) -> None:
        service = ReportingService()
        events = [_event(event_id="a")]
        with pytest.raises(UnresolvedStarCellsError) as excinfo:
            service.export(events, filled_forms={}, destination=tmp_path / "out.xlsx")
        assert excinfo.value.blockers

    def test_export_writes_copy_and_preserves_original(self, tmp_path: Path) -> None:
        import hashlib
        import openpyxl

        template = find_template()
        before = hashlib.sha256(template.read_bytes()).hexdigest()

        service = ReportingService()
        events = [_event(event_id="a", occasion_class=OccasionClass.RELIGIOUS)]
        events[0].add_fact(_fact(value=80))
        ashura = _event(event_id="ash", is_ashura_pilgrimage=True)
        ashura.add_fact(_fact(value=55))
        all_events = events + [ashura]

        # Human pass fills every star question for ceremonies.
        form = service.prefill(ProgramId.CEREMONIES, all_events, context={"province": "مازندران"})
        definition = FORMS_BY_PROGRAM["ceremonies"]
        for key in definition.star_keys():
            if key not in form.answers:
                form.set(key, 1, value_kind=FactValueKind.VERIFIED)
        form.set("ceremony_religious", 1, value_kind=FactValueKind.VERIFIED)
        # Ashura attendees (55) must not leak into the main attendee total (80).
        form.set("attendees", 80, value_kind=FactValueKind.VERIFIED)
        form.set("ashura_pilgrimage_count", 1, value_kind=FactValueKind.VERIFIED)
        form.set("ashura_pilgrimage_attendees", 55, value_kind=FactValueKind.VERIFIED)

        destination = tmp_path / "report_copy.xlsx"
        service.export(
            all_events,
            {"ceremonies": form},
            destination,
            province_name="مازندران",
            allow_unresolved_star=True,  # only ceremonies is in scope for this export
        )

        assert destination.exists()
        after = hashlib.sha256(template.read_bytes()).hexdigest()
        assert before == after  # original never touched

        exported = openpyxl.load_workbook(destination)
        sheet = exported["مراسم  مذهبی"]
        assert sheet["E8"].value == 1  # religious count
        assert sheet["G8"].value == 80  # attendees
        assert ASHURA_ANNEX_SHEET_NAME in exported.sheetnames
        annex = exported[ASHURA_ANNEX_SHEET_NAME]
        assert annex["A4"].value == 1
        assert annex["B4"].value == 55

    def test_export_allow_unresolved_flag_writes_anyway(self, tmp_path: Path) -> None:
        service = ReportingService()
        destination = tmp_path / "partial.xlsx"
        path = service.export(
            [_event(event_id="a")],
            filled_forms={},
            destination=destination,
            allow_unresolved_star=True,
        )
        assert path.exists()
