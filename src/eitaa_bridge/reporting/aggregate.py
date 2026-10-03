"""Provincial aggregation: events + facts -> one workbook row per program.

The main row is always the whole-province aggregate (provincial HQ plus all
judicial domains). Per-unit and per-event detail is preserved in the annex
breakdown so the aggregate can always be re-derived from evidence.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from .model import FactValueKind, ProgramId, ReportedEvent, UnitScope
from .rules import RULES_VERSION, CountingRuleEngine


@dataclass(slots=True)
class ProgramReport:
    program_id: ProgramId
    counts: dict[str, int] = field(default_factory=dict)
    attendees_total: int = 0
    ashura_pilgrimage_count: int = 0
    ashura_pilgrimage_attendees: int = 0
    breakdown_by_unit: dict[str, dict[str, int]] = field(default_factory=dict)
    excluded: list[dict[str, str]] = field(default_factory=list)
    value_kind_warnings: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "program_id": self.program_id.value,
            "counts": dict(self.counts),
            "attendees_total": self.attendees_total,
            "ashura_pilgrimage_count": self.ashura_pilgrimage_count,
            "ashura_pilgrimage_attendees": self.ashura_pilgrimage_attendees,
            "breakdown_by_unit": {unit: dict(m) for unit, m in self.breakdown_by_unit.items()},
            "excluded": list(self.excluded),
            "value_kind_warnings": list(self.value_kind_warnings),
        }


def _exportable(fact_value_kind: FactValueKind) -> bool:
    return fact_value_kind in {FactValueKind.VERIFIED, FactValueKind.OBSERVED, FactValueKind.REPORTED_BY_UNIT}


def aggregate_program_report(
    program_id: ProgramId,
    events: Sequence[ReportedEvent],
    *,
    engine: CountingRuleEngine | None = None,
) -> ProgramReport:
    engine = engine or CountingRuleEngine()
    report = ProgramReport(program_id=program_id)

    for event in events:
        shares = engine.classify(event)
        share = next((s for s in shares if s.program_id is program_id), None)
        if share is None:
            continue

        unit_label = event.unit_name or ("ستاد استانی" if event.unit is UnitScope.PROVINCIAL_HQ else event.unit.value)

        if event.is_ashura_pilgrimage and program_id is ProgramId.CEREMONIES:
            # C12 + Q-IR-005: separate annex metric, never in the main count.
            report.ashura_pilgrimage_count += 1
            for fact in event.facts:
                if fact.metric == "attendees" and _exportable(fact.value_kind):
                    report.ashura_pilgrimage_attendees += int(fact.value)
            report.excluded.append(
                {"event_id": event.event_id, "reason": "ashura_pilgrimage_separate_annex_c12"}
            )
            continue

        if not share.counts:
            report.excluded.append({"event_id": event.event_id, "reason": share.reason})
            continue

        kind_key = event.program_kinds[0].value if len(event.program_kinds) == 1 else "combined"
        report.counts[kind_key] = report.counts.get(kind_key, 0) + 1
        if program_id is ProgramId.CEREMONIES and event.occasion_class is not None:
            class_key = f"ceremony_{event.occasion_class.value}"
            report.counts[class_key] = report.counts.get(class_key, 0) + 1

        unit_bucket = report.breakdown_by_unit.setdefault(unit_label, {})
        unit_bucket["events"] = unit_bucket.get("events", 0) + 1

        for fact in event.facts:
            if fact.metric == "attendees":
                if _exportable(fact.value_kind):
                    report.attendees_total += int(fact.value)
                    unit_bucket["attendees"] = unit_bucket.get("attendees", 0) + int(fact.value)
                else:
                    report.value_kind_warnings.append(
                        f"{event.event_id}: attendees value_kind={fact.value_kind.value} excluded from verified aggregate"
                    )

    return report


class ProvincialAggregator:
    """Aggregates all programs at once; the unified view over the seven forms."""

    def __init__(self, engine: CountingRuleEngine | None = None) -> None:
        self.engine = engine or CountingRuleEngine()
        self.rules_version = RULES_VERSION

    def aggregate(
        self,
        events: Sequence[ReportedEvent],
        program_ids: Sequence[ProgramId] | None = None,
    ) -> dict[str, ProgramReport]:
        targets = list(program_ids) if program_ids else list(ProgramId)
        reports: dict[str, ProgramReport] = {}
        for program_id in targets:
            reports[program_id.value] = aggregate_program_report(program_id, events, engine=self.engine)
        return reports

    def unified_summary(self, events: Sequence[ReportedEvent]) -> dict[str, Any]:
        reports = self.aggregate(events)
        return {
            "rules_version": self.rules_version,
            "programs": {pid: report.as_dict() for pid, report in reports.items()},
            "totals": {
                "events_considered": len(events),
                "total_excluded": sum(len(report.excluded) for report in reports.values()),
            },
        }


def build_traceability_manifest(
    events: Sequence[ReportedEvent],
    *,
    engine: CountingRuleEngine | None = None,
) -> dict[str, Any]:
    """Per-program contributing event ids for official-export traceability.

    Mirrors ``aggregate_program_report`` counting so every exported number
    traces back to its events (strategy section 3). Embedded in the workbook
    traceability sheet and in ``report_exports.traceability_json``.
    """
    engine = engine or CountingRuleEngine()
    programs: dict[str, dict[str, Any]] = {}
    excluded: list[dict[str, str]] = []
    for event in events:
        shares = engine.classify(event)
        if not shares:
            excluded.append({"event_id": event.event_id, "reason": "no_program_share"})
        for share in shares:
            program = programs.setdefault(
                share.program_id.value,
                {"count": 0, "event_ids": [], "attendees_total": 0, "attendee_event_ids": []},
            )
            if event.is_ashura_pilgrimage and share.program_id is ProgramId.CEREMONIES:
                excluded.append({"event_id": event.event_id, "reason": "ashura_pilgrimage_separate_annex_c12"})
                continue
            if not share.counts:
                excluded.append({"event_id": event.event_id, "reason": share.reason})
                continue
            program["count"] += 1
            program["event_ids"].append(event.event_id)
            for fact in event.facts:
                if fact.metric == "attendees" and _exportable(fact.value_kind):
                    program["attendees_total"] += int(fact.value)
                    if event.event_id not in program["attendee_event_ids"]:
                        program["attendee_event_ids"].append(event.event_id)
    return {"programs": programs, "excluded": excluded}
