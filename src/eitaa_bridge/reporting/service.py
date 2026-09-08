"""Orchestrates the full reporting pipeline: Eitaa → events → forms → export.

This is the single entry point the office staff uses. Everything flows
through human gates: candidates from Eitaa are suggestions, aggregation runs
over staff-confirmed events, and export is blocked while star cells are
unresolved (the final human pass on the Excel copy).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Mapping, Sequence

from .aggregate import ProvincialAggregator, aggregate_program_report, ProgramReport
from .eitaa_extraction import EitaaCandidateExtractor, EventCandidate
from .excel_export import ASHURA_ANNEX_SHEET_NAME, export_unified_report, star_cell_report
from .forms import (
    ALL_FORMS,
    FORMS_BY_PROGRAM,
    FilledForm,
    QuestionnaireDefinition,
    prefill_form,
)
from .indexer import DEFAULT_MONITOR_TARGETS, EitaaIntentIndexer, IndexDecision, MessageIntent
from .model import (
    Fact,
    FactValueKind,
    ProgramId,
    ProgramKind,
    ReportedEvent,
    UnitScope,
    ValueSource,
)
from .monitor import EitaaReportMonitor, MonitorResult
from .rules import CountingRuleEngine, RULES_VERSION


@dataclass(slots=True)
class ReportingService:
    """Stateless pipeline facade over the reporting core."""

    engine: CountingRuleEngine = field(default_factory=CountingRuleEngine)
    aggregator: ProvincialAggregator = field(default_factory=ProvincialAggregator)
    extractor: EitaaCandidateExtractor = field(default_factory=EitaaCandidateExtractor)
    indexer: EitaaIntentIndexer = field(default_factory=EitaaIntentIndexer)
    monitor: EitaaReportMonitor = field(default_factory=EitaaReportMonitor)

    # -- Level 1: Eitaa candidates -----------------------------------------
    def candidates_from_message(self, text: str, *, message_ref: str = "", sender_hint: str = "") -> EventCandidate | None:
        return self.extractor.extract(text, message_ref=message_ref, sender_hint=sender_hint)

    def index_message(self, text: str, *, message_ref: str = "", dialog_label: str = "") -> IndexDecision:
        """Multi-criteria scoring against the seven evaluation programs."""

        return self.indexer.classify(text, message_ref=message_ref, dialog_label=dialog_label)

    def scan_texts(self, messages: Sequence[tuple[str, str, str]]) -> MonitorResult:
        """Batch monitoring entry point (works for Eitaa and Bale alike)."""

        return self.monitor.scan_texts(messages)

    def scan_provider_once(self, core: Any, *, limit_per_dialog: int = 50) -> MonitorResult:
        """Scan configured dialogs through a live ``eitaa_core`` runtime."""

        return self.monitor.scan_once(core, limit_per_dialog=limit_per_dialog)

    def event_from_candidate(
        self,
        candidate: EventCandidate,
        *,
        event_id: str,
        occurred_on: date,
        unit: UnitScope = UnitScope.PROVINCIAL_HQ,
        unit_name: str = "",
        official_present: bool | None = None,
        staff_member: str = "",
    ) -> ReportedEvent:
        """Promote a candidate into a staff-owned event.

        ``official_present`` is deliberately an explicit human answer
        (Q-IR-011): the service never defaults it to True.
        """

        event = ReportedEvent(
            event_id=event_id,
            program_kinds=candidate.suggested_kinds,
            occurred_on=occurred_on,
            unit=unit,
            unit_name=unit_name,
            occasion_class=candidate.occasion_class,
            is_ashura_pilgrimage=candidate.is_ashura_pilgrimage,
            official_present=official_present,
        )
        if candidate.extracted_attendees is not None:
            event.add_fact(
                Fact(
                    metric="attendees",
                    value=candidate.extracted_attendees,
                    value_kind=FactValueKind.REPORTED_BY_UNIT,
                    source=ValueSource.EITAA,
                    evidence_refs=candidate.source_message_refs,
                    created_by=staff_member,
                    note="auto-extracted from Eitaa; awaiting staff confirmation",
                )
            )
        return event

    # -- Level 3: forms and aggregation -------------------------------------
    def prefill(self, program_id: ProgramId, events: Sequence[ReportedEvent], *, context: Mapping[str, str] | None = None) -> FilledForm:
        definition = FORMS_BY_PROGRAM[program_id.value]
        return prefill_form(definition, events, context=context)

    def definitions(self) -> tuple[QuestionnaireDefinition, ...]:
        return ALL_FORMS

    def aggregate(self, events: Sequence[ReportedEvent]) -> dict[str, ProgramReport]:
        return self.aggregator.aggregate(events)

    def program_report(self, program_id: ProgramId, events: Sequence[ReportedEvent]) -> ProgramReport:
        return aggregate_program_report(program_id, events, engine=self.engine)

    def human_gate_questions(self, program_id: ProgramId) -> tuple[str, ...]:
        return FORMS_BY_PROGRAM[program_id.value].human_gate_keys()

    # -- Export --------------------------------------------------------------
    def export(
        self,
        events: Sequence[ReportedEvent],
        filled_forms: Mapping[str, FilledForm],
        destination: Path,
        *,
        province_name: str = "",
        report_period: str = "۱۴۰۵",
        template_root: Path | None = None,
        allow_unresolved_star: bool = False,
    ) -> Path:
        unified = self.aggregate(events)
        ashura_events = [event for event in events if event.is_ashura_pilgrimage]
        return export_unified_report(
            unified,
            {key: form for key, form in filled_forms.items()},
            destination,
            template_root=template_root,
            province_name=province_name,
            report_period=report_period,
            allow_unresolved_star=allow_unresolved_star,
            ashura_events=ashura_events,
        )

    def pre_export_blockers(self, filled_forms: Mapping[str, FilledForm]) -> dict[str, list[str]]:
        definitions = [FORMS_BY_PROGRAM[pid.value] for pid in ProgramId if pid.value in filled_forms]
        if not definitions:
            definitions = list(ALL_FORMS)
        return star_cell_report(definitions, filled_forms)
