"""Orchestrates the full reporting pipeline: Eitaa → events → forms → export.

This is the single entry point the office staff uses. Everything flows
through human gates: candidates from Eitaa are suggestions, aggregation runs
over staff-confirmed events, and export is blocked while star cells are
unresolved (the final human pass on the Excel copy).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
import hashlib
from pathlib import Path
from typing import Any, Mapping, Sequence

from .aggregate import ProvincialAggregator, aggregate_program_report, build_traceability_manifest, ProgramReport
from .eitaa_extraction import EitaaCandidateExtractor, EventCandidate
from .excel_export import ASHURA_ANNEX_SHEET_NAME, export_unified_report, star_cell_report, TEMPLATE_VERSION
from .rules import RULES_VERSION
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
    OccasionClass,
    ProgramId,
    ProgramKind,
    ReportedEvent,
    UnitScope,
    ValueSource,
)
from .monitor import EitaaReportMonitor, MonitorResult
from .plans import Mandate
from .rules import CountingRuleEngine, RULES_VERSION
from .store import ReportingStore


@dataclass(slots=True)
class ReportingService:
    """Pipeline facade over the reporting core with optional persistent storage."""

    engine: CountingRuleEngine = field(default_factory=CountingRuleEngine)
    aggregator: ProvincialAggregator = field(default_factory=ProvincialAggregator)
    extractor: EitaaCandidateExtractor = field(default_factory=EitaaCandidateExtractor)
    indexer: EitaaIntentIndexer = field(default_factory=EitaaIntentIndexer)
    monitor: EitaaReportMonitor = field(default_factory=EitaaReportMonitor)
    store: ReportingStore | None = None

    # -- Level 1: Eitaa candidates -----------------------------------------
    def candidates_from_message(self, text: str, *, message_ref: str = "", sender_hint: str = "") -> EventCandidate | None:
        return self.extractor.extract(text, message_ref=message_ref, sender_hint=sender_hint)

    def index_message(self, text: str, *, message_ref: str = "", dialog_label: str = "") -> IndexDecision:
        """Multi-criteria scoring against the seven evaluation programs."""

        return self.indexer.classify(text, message_ref=message_ref, dialog_label=dialog_label)

    def scan_texts(self, messages: Sequence[tuple[str, str, str]]) -> MonitorResult:
        """Batch monitoring entry point (works for Eitaa and Bale alike)."""

        return self.monitor.scan_texts(messages)

    def scan_and_record_texts(self, messages: Sequence[tuple[str, str, str]], *, dialog_label: str = "") -> MonitorResult:
        """Scan messages and persist decisions and candidate events into the store."""
        result = self.monitor.scan_texts(messages)
        if self.store is not None:
            for decision in result.decisions:
                self.store.record_decision(decision)
            for candidate in result.candidates:
                self.store.save_candidate(candidate, dialog_label=dialog_label)
        return result

    def scan_provider_once(self, core: Any, *, limit_per_dialog: int = 50, timeout_seconds: float = 30.0) -> MonitorResult:
        """Scan configured dialogs through a live ``eitaa_core`` runtime with safety timeout."""

        return self.monitor.scan_once(core, limit_per_dialog=limit_per_dialog, timeout_seconds=timeout_seconds)

    def scan_and_record_provider(self, core: Any, *, limit_per_dialog: int = 50, timeout_seconds: float = 30.0) -> MonitorResult:
        """Scan configured dialogs via live runtime and persist decisions into store with safety timeout."""
        result = self.monitor.scan_once(core, limit_per_dialog=limit_per_dialog, timeout_seconds=timeout_seconds)
        if self.store is not None:
            for decision in result.decisions:
                self.store.record_decision(decision)
            for candidate in result.candidates:
                self.store.save_candidate(candidate)
        return result

    def list_review_candidates(self, *, status: str | None = "pending", limit: int = 100) -> list[dict[str, Any]]:
        """List candidates currently in the review queue."""
        if self.store is None:
            return []
        return self.store.list_candidates(status=status, limit=limit)

    def approve_candidate_to_event(
        self,
        candidate_id: str,
        *,
        event_id: str,
        occurred_on: date,
        unit: UnitScope = UnitScope.PROVINCIAL_HQ,
        unit_name: str = "",
        official_present: bool | None = None,
        staff_member: str = "",
        program_kinds: Sequence[ProgramKind | str] | None = None,
        attendee_count: float | None = None,
        is_ashura_pilgrimage: bool | None = None,
        is_standalone_titled: bool = True,
        occasion_class: OccasionClass | str | None = None,
        dimension_facts: Mapping[str, Any] | None = None,
        notes: str = "",
    ) -> ReportedEvent | None:
        """Approve an event candidate, creating a confirmed ReportedEvent in store."""
        if self.store is None:
            return None
        candidate_dict = self.store.get_candidate(candidate_id)
        if not candidate_dict:
            return None

        if program_kinds:
            kinds = tuple(ProgramKind(k) if isinstance(k, str) else k for k in program_kinds)
        else:
            kinds = tuple(ProgramKind(k) for k in candidate_dict["suggested_kinds"])

        if is_ashura_pilgrimage is not None:
            ashura_flag = bool(is_ashura_pilgrimage)
        else:
            ashura_flag = bool(candidate_dict["is_ashura_pilgrimage"])

        if ashura_flag:
            occ_cls = None
        elif occasion_class is not None:
            occ_cls = OccasionClass(occasion_class) if isinstance(occasion_class, str) else occasion_class
        else:
            occ_cls = (
                OccasionClass(candidate_dict["occasion_class"])
                if candidate_dict.get("occasion_class")
                else None
            )

        event = ReportedEvent(
            event_id=event_id,
            program_kinds=kinds,
            occurred_on=occurred_on,
            unit=unit,
            unit_name=unit_name,
            occasion_class=occ_cls,
            is_ashura_pilgrimage=ashura_flag,
            official_present=official_present,
            is_standalone_titled=is_standalone_titled,
            notes=notes,
            created_by=staff_member,
        )

        chosen_attendees = attendee_count if attendee_count is not None else candidate_dict.get("extracted_attendees")
        source_refs = tuple(candidate_dict.get("source_message_refs") or ())
        if chosen_attendees is not None and float(chosen_attendees) >= 0:
            event.add_fact(
                Fact(
                    metric="attendees",
                    value=float(chosen_attendees),
                    value_kind=FactValueKind.REPORTED_BY_UNIT,
                    source=ValueSource.MANUAL if attendee_count is not None else ValueSource.EITAA,
                    evidence_refs=source_refs,
                    created_by=staff_member,
                    note="تأیید شده در کارتابل رویدادها",
                )
            )
            if ashura_flag:
                event.add_fact(
                    Fact(
                        metric="ashura_pilgrimage_attendees",
                        value=float(chosen_attendees),
                        value_kind=FactValueKind.REPORTED_BY_UNIT,
                        source=ValueSource.MANUAL if attendee_count is not None else ValueSource.EITAA,
                        evidence_refs=source_refs,
                        created_by=staff_member,
                        note="شرکت‌کنندگان زیارت عاشورا",
                    )
                )

        if ashura_flag:
            event.add_fact(
                Fact(
                    metric="ashura_pilgrimage_count",
                    value=1.0,
                    value_kind=FactValueKind.REPORTED_BY_UNIT,
                    source=ValueSource.MANUAL,
                    evidence_refs=source_refs,
                    created_by=staff_member,
                )
            )

        if dimension_facts:
            for metric, val in dimension_facts.items():
                if val is True or (isinstance(val, (int, float)) and val > 0):
                    num_val = 1.0 if isinstance(val, bool) else float(val)
                    event.add_fact(
                        Fact(
                            metric=str(metric),
                            value=num_val,
                            value_kind=FactValueKind.REPORTED_BY_UNIT,
                            source=ValueSource.MANUAL,
                            evidence_refs=source_refs,
                            created_by=staff_member,
                        )
                    )

        self.store.save_event(event)
        self.store.approve_candidate(candidate_id, event_id=event.event_id, reviewed_by=staff_member)
        return event

    def create_manual_event(
        self,
        *,
        event_id: str,
        program_kinds: Sequence[ProgramKind | str],
        occurred_on: date,
        unit: UnitScope = UnitScope.PROVINCIAL_HQ,
        unit_name: str = "",
        official_present: bool | None = None,
        attendee_count: float | None = None,
        is_ashura_pilgrimage: bool = False,
        is_standalone_titled: bool = True,
        occasion_class: OccasionClass | str | None = None,
        dimension_facts: Mapping[str, Any] | None = None,
        notes: str = "",
        staff_member: str = "",
    ) -> ReportedEvent:
        """Create a new confirmed ReportedEvent directly with sheet-specific dimensions."""
        if self.store is None:
            raise RuntimeError("Reporting store is not initialized.")

        kinds = tuple(ProgramKind(k) if isinstance(k, str) else k for k in program_kinds)
        ashura_flag = bool(is_ashura_pilgrimage)
        if ashura_flag:
            occ_cls = None
        elif occasion_class is not None:
            occ_cls = OccasionClass(occasion_class) if isinstance(occasion_class, str) else occasion_class
        else:
            occ_cls = None

        event = ReportedEvent(
            event_id=event_id,
            program_kinds=kinds,
            occurred_on=occurred_on,
            unit=unit,
            unit_name=unit_name,
            occasion_class=occ_cls,
            is_ashura_pilgrimage=ashura_flag,
            official_present=official_present,
            is_standalone_titled=is_standalone_titled,
            notes=notes,
            created_by=staff_member,
        )

        if attendee_count is not None and float(attendee_count) >= 0:
            event.add_fact(
                Fact(
                    metric="attendees",
                    value=float(attendee_count),
                    value_kind=FactValueKind.REPORTED_BY_UNIT,
                    source=ValueSource.MANUAL,
                    created_by=staff_member,
                    note="ثبت دستی در کارتابل",
                )
            )
            if ashura_flag:
                event.add_fact(
                    Fact(
                        metric="ashura_pilgrimage_attendees",
                        value=float(attendee_count),
                        value_kind=FactValueKind.REPORTED_BY_UNIT,
                        source=ValueSource.MANUAL,
                        created_by=staff_member,
                        note="شرکت‌کنندگان زیارت عاشورا",
                    )
                )

        if ashura_flag:
            event.add_fact(
                Fact(
                    metric="ashura_pilgrimage_count",
                    value=1.0,
                    value_kind=FactValueKind.REPORTED_BY_UNIT,
                    source=ValueSource.MANUAL,
                    created_by=staff_member,
                )
            )

        if dimension_facts:
            for metric, val in dimension_facts.items():
                if val is True or (isinstance(val, (int, float)) and val > 0):
                    num_val = 1.0 if isinstance(val, bool) else float(val)
                    event.add_fact(
                        Fact(
                            metric=str(metric),
                            value=num_val,
                            value_kind=FactValueKind.REPORTED_BY_UNIT,
                            source=ValueSource.MANUAL,
                            created_by=staff_member,
                        )
                    )

        self.store.save_event(event)
        return event

    def reject_candidate(self, candidate_id: str, *, staff_member: str = "", reason: str = "") -> bool:
        """Reject an event candidate from entering the reporting pipeline."""
        if self.store is None:
            return False
        self.store.reject_candidate(candidate_id, reviewed_by=staff_member, reason=reason)
        return True

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

    def definitions(self, *, include_narrative: bool = False) -> tuple[QuestionnaireDefinition, ...]:
        if include_narrative:
            from .forms import EXTENDED_FORMS
            return EXTENDED_FORMS
        return ALL_FORMS

    def aggregate(self, events: Sequence[ReportedEvent]) -> dict[str, ProgramReport]:
        return self.aggregator.aggregate(events)

    def program_report(self, program_id: ProgramId, events: Sequence[ReportedEvent]) -> ProgramReport:
        return aggregate_program_report(program_id, events, engine=self.engine)

    def human_gate_questions(self, program_id: ProgramId) -> tuple[str, ...]:
        return FORMS_BY_PROGRAM[program_id.value].human_gate_keys()

    # -- Export --------------------------------------------------------------
    WORDPRESS_EXPORT_OPT_IN_KEY = "wordpress_export_opt_in"

    def wordpress_export_opt_in(self) -> bool:
        """WordPress is a flagged one-way export adapter; default OFF (phase 4)."""
        if self.store is None:
            return False
        return bool(self.store.get_config().get(self.WORDPRESS_EXPORT_OPT_IN_KEY, False))

    def set_wordpress_export_opt_in(self, enabled: bool) -> None:
        if self.store is None:
            raise RuntimeError("wordpress export opt-in requires a reporting store")
        self.store.set_config({self.WORDPRESS_EXPORT_OPT_IN_KEY: bool(enabled)})

    def ensure_wordpress_export_allowed(self) -> None:
        """Guard for any WP publisher: refuse unless the opt-in flag is on.

        WordPress being unreachable or disabled must never block native
        registration or Excel export (strategy section 9, phase-4 gate).
        """
        if not self.wordpress_export_opt_in():
            raise PermissionError(
                "wordpress export adapter is opt-in and currently disabled"
            )

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
        traceability: Mapping[str, Any] | None = None,
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
            traceability=traceability,
        )

    def pre_export_blockers(self, filled_forms: Mapping[str, FilledForm]) -> dict[str, list[str]]:
        definitions = [FORMS_BY_PROGRAM[pid.value] for pid in ProgramId if pid.value in filled_forms]
        if not definitions:
            definitions = list(ALL_FORMS)
        return star_cell_report(definitions, filled_forms)

    # -- Persistence helpers -------------------------------------------------
    def save_filled_form(self, form: FilledForm, *, updated_by: str = "") -> None:
        """Persist answers of a completed or partially-filled form."""
        if self.store is not None:
            self.store.save_filled_form(form, updated_by=updated_by)

    def load_filled_forms(self) -> dict[str, FilledForm]:
        """Load all saved filled forms from persistent storage."""
        if self.store is not None:
            return self.store.list_filled_forms()
        return {}

    def get_stored_events(self, *, limit: int = 100) -> list[ReportedEvent]:
        """Load confirmed events from persistent storage."""
        if self.store is not None:
            return self.store.list_events(limit=limit)
        return []

    def export_with_audit(
        self,
        events: Sequence[ReportedEvent] | None = None,
        filled_forms: Mapping[str, FilledForm] | None = None,
        destination: Path | None = None,
        *,
        province_name: str = "",
        report_period: str = "۱۴۰۵",
        template_root: Path | None = None,
        allow_unresolved_star: bool = False,
        exported_by: str = "",
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> Path:
        """Export unified report and record audit trail with SHA-256 hash.

        ``date_from``/``date_to`` (ISO ``YYYY-MM-DD``) restrict the export to
        a time window (بازهٔ زمانی). Within a window the aggregates are
        recomputed from that window's events and the period-wide saved forms
        are deliberately excluded, so a subrange never inherits whole-period
        totals. Without a window the full store and saved forms are used.
        """
        evs = list(events) if events is not None else self.get_stored_events(limit=1_000_000)
        if date_from or date_to:
            d_from = date.fromisoformat(date_from) if date_from else None
            d_to = date.fromisoformat(date_to) if date_to else None
            evs = [
                event
                for event in evs
                if (d_from is None or event.occurred_on >= d_from)
                and (d_to is None or event.occurred_on <= d_to)
            ]
            forms: dict[str, FilledForm] = {}
        else:
            forms = dict(filled_forms) if filled_forms is not None else self.load_filled_forms()
        dest = destination or Path("unified_report_1405.xlsx")
        manifest = build_traceability_manifest(evs)
        out_path = self.export(
            evs,
            forms,
            dest,
            province_name=province_name,
            report_period=report_period,
            template_root=template_root,
            allow_unresolved_star=allow_unresolved_star,
            traceability=manifest,
        )
        if self.store is not None and out_path.exists():
            file_sha = hashlib.sha256(out_path.read_bytes()).hexdigest()
            self.store.record_export(
                export_path=out_path,
                file_sha256=file_sha,
                report_period=report_period,
                province_name=province_name,
                total_events=len(evs),
                exported_by=exported_by,
                template_version=TEMPLATE_VERSION,
                rules_version=RULES_VERSION,
                traceability=manifest,
                wp_opt_in=self.wordpress_export_opt_in(),
            )
        return out_path

    def suggest_candidate_review(
        self,
        candidate_id: str,
        text: str = "",
        *,
        dialog_label: str = "",
    ) -> Any:
        """Run intelligent privacy-safe agent suggestion on a candidate."""
        from .suggester import ReportingSuggester

        cand_info = None
        if self.store is not None:
            cands = self.store.list_candidates(status=None)
            for c in cands:
                if c.get("candidate_id") == candidate_id:
                    cand_info = c
                    break

        matched_progs: list[str] = []
        attendees: int | None = None
        label = dialog_label

        if cand_info:
            matched_progs = cand_info.get("matched_programs") or []
            attendees = cand_info.get("attendee_count")
            if not label:
                label = cand_info.get("dialog_label") or ""

        suggester = ReportingSuggester()
        return suggester.analyze(
            candidate_id=candidate_id,
            text=text,
            matched_programs=matched_progs,
            existing_attendees=attendees,
            dialog_label=label,
        )

    # -- Mandates (اسناد بالادستی و مستندات ابلاغی) ----------------------------
    def list_mandates(self, *, program_code: str | None = None) -> list[Mandate]:
        if self.store is None:
            return []
        return self.store.list_mandates(program_code=program_code)

    def save_mandate(self, mandate: Mandate) -> None:
        if self.store is None:
            raise RuntimeError("Reporting store is not initialized.")
        self.store.save_mandate(mandate)

    def delete_mandate(self, mandate_id: str) -> bool:
        if self.store is None:
            raise RuntimeError("Reporting store is not initialized.")
        return self.store.delete_mandate(mandate_id)

    # -- Questionnaire definitions projection (F-095) ------------------------
    def form_definitions(self) -> list[dict[str, Any]]:
        """Projected form definitions (شرح عملیاتی/موازین/ساختار هر شیت)."""
        if self.store is None:
            return []
        return self.store.list_form_definitions()

    def form_definition(self, program_code: str) -> dict[str, Any] | None:
        if self.store is None:
            return None
        return self.store.get_form_definition(program_code)


