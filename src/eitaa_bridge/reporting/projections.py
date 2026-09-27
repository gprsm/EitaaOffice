"""Projection layer: official documents rendered from the shell (F-088).

The 1405 workbook sheet and the provincial visit worksheet are two views of
the same store. This module assembles the visit-worksheet prayer row (ترویج
نماز) and the per-section dossier, carrying provenance references and gap
lists so an agent (or a human) can compile the «پروندهٔ بازدید استانی» with
every number traceable to a plan item, event id, or entity fact.

Registry entity facts here are aggregated to counts only — person-level data
never leaves the store through projections.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

from .metrics import (
    ASSESSMENT_INSTRUMENT_1405,
    COUNCIL_SESSIONS_MANDATE_CHOICE,
    MetricDictionary,
    METRIC_DICTIONARY,
)
from .model import ReportedEvent
from .plans import PRAYER_PLAN_1405, PlanItem, realization_report
from .registry import EntityFact, ImamRecord, UnitRecord, latest_choice_fact

VISIT_WORKSHEET_PRAYER_TITLE = "ترویج نماز"


@dataclass(slots=True)
class ProjectionCell:
    label: str
    value: object
    refs: tuple[str, ...] = ()
    note: str = ""

    def as_dict(self) -> dict[str, object]:
        return {"label": self.label, "value": self.value, "refs": list(self.refs), "note": self.note}


@dataclass(slots=True)
class VisitWorksheetPrayerRow:
    """The ترویج نماز row of the provincial visit worksheet, phase-1 scope."""

    cells: list[ProjectionCell] = field(default_factory=list)
    realization: list[dict[str, object]] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        return {
            "row": VISIT_WORKSHEET_PRAYER_TITLE,
            "cells": [c.as_dict() for c in self.cells],
            "realization": self.realization,
            "gaps": list(self.gaps),
        }


def _unit_facts_for(
    facts: Sequence[EntityFact],
    unit: UnitRecord,
    period: str,
) -> list[EntityFact]:
    ref = f"unit:{unit.name}"
    return [
        f
        for f in facts
        if f.entity_type == "unit" and f.entity_id == ref and f.period == period
    ]


def council_compliance(
    facts: Sequence[EntityFact],
    units: Sequence[UnitRecord],
    *,
    period: str,
    dictionary: MetricDictionary = METRIC_DICTIONARY,
) -> dict[str, object]:
    """شورای اقامه نماز vs the دستورالعمل band (design doc §8).

    Returns counts of compliant / non-compliant / unknown units plus the
    unknown unit names so the dossier can name the monitoring gap.
    """
    threshold_rank = dictionary.get("council_sessions_band").choice_rank(COUNCIL_SESSIONS_MANDATE_CHOICE)
    compliant: list[str] = []
    non_compliant: list[str] = []
    unknown: list[str] = []
    for unit in units:
        unit_facts = _unit_facts_for(facts, unit, period)
        latest = latest_choice_fact(unit_facts, "council_sessions_band")
        if latest is None:
            unknown.append(unit.name)
            continue
        rank = dictionary.get("council_sessions_band").choice_rank(latest.text_value)
        (compliant if rank >= threshold_rank else non_compliant).append(unit.name)
    return {
        "compliant": compliant,
        "non_compliant": non_compliant,
        "unknown": unknown,
        "mandate_choice": COUNCIL_SESSIONS_MANDATE_CHOICE,
        "refs": ("plan:prayer-1405-council",),
    }


def rooyesh_javaneh_stats(
    events: Sequence[ReportedEvent],
    *,
    campaign_tag: str = "رویش جوانه ها",
) -> ProjectionCell:
    """رویش جوانه‌ها (جشن نومکلفان): مراسم، شرکت‌کنندگان، تکریم‌شوندگان."""
    tagged = [e for e in events if campaign_tag in (getattr(e, "campaign", "") or "")]
    ceremonies = len(tagged)
    attendees = 0.0
    honored = 0.0
    refs: list[str] = []
    for event in tagged:
        refs.append(event.event_id)
        for fact in event.facts:
            if fact.metric == "attendees":
                attendees += fact.value
            if fact.metric == "honored_count":
                honored += fact.value
    return ProjectionCell(
        label="طرح رویش جوانه‌ها (جشن نومکلفان)",
        value={"ceremonies": ceremonies, "attendees": attendees, "honored": honored},
        refs=tuple(refs),
    )


def build_visit_worksheet_prayer_row(
    *,
    events: Sequence[ReportedEvent],
    units: Sequence[UnitRecord],
    facts: Sequence[EntityFact],
    imams: Sequence[ImamRecord] = (),
    plan_items: Sequence[PlanItem] = PRAYER_PLAN_1405,
    period: str = "1405",
    dictionary: MetricDictionary = METRIC_DICTIONARY,
) -> VisitWorksheetPrayerRow:
    """Assemble the visit-worksheet prayer row from plan + events + facts."""
    row = VisitWorksheetPrayerRow()

    council = council_compliance(facts, units, period=period, dictionary=dictionary)
    row.cells.append(
        ProjectionCell(
            label="تشکیل و جلسات شورای اقامه نماز (بر اساس وضعیت‌سنجی)",
            value={
                "مطابق دستورالعمل": len(council["compliant"]),
                "کمتر از حد دستورالعمل": len(council["non_compliant"]),
                "بدون داده": len(council["unknown"]),
            },
            refs=tuple(council["refs"]),
        )
    )

    no_venue_imam = _venues_without_active_imam(facts, units, imams, period=period)
    row.cells.append(
        ProjectionCell(
            label="وضعیت نمازخانه‌ها و ائمه جماعت",
            value={
                "واحد بدون دادهٔ امام جماعت": len(no_venue_imam["no_imam_data"]),
                "واحد با امام جماعت": len(no_venue_imam["with_imam"]),
            },
            refs=tuple(no_venue_imam["refs"]),
        )
    )

    row.cells.append(rooyesh_javaneh_stats(events))

    row.realization = realization_report(plan_items, events, scope="provincial_hq")
    for item_report in row.realization:
        if item_report["gap"]:
            row.gaps.append(
                f"{item_report['title']}: {item_report['done']:.0f} از {item_report['target']:.0f} (شکاف {item_report['gap']:.0f})"
            )
        if item_report["needs_confirmation"]:
            row.gaps.append(f"{item_report['title']}: ردیف ترکیبی فرم بومی نیازمند تأیید انسانی")
    if council["unknown"]:
        row.gaps.append(f"وضعیت‌سنجی جلسات شورا برای {len(council['unknown'])} حوزه ثبت نشده است")
    return row


def _venues_without_active_imam(
    facts: Sequence[EntityFact],
    units: Sequence[UnitRecord],
    imams: Sequence[ImamRecord],
    *,
    period: str,
) -> dict[str, object]:
    with_imam: list[str] = []
    no_imam_data: list[str] = []
    refs: list[str] = []
    imams_by_unit = {imam.unit_id for imam in imams if imam.status == "employed"}
    for unit in units:
        unit_facts = _unit_facts_for(facts, unit, period)
        latest = latest_choice_fact(unit_facts, "imam_source")
        if latest is None and unit.unit_id not in imams_by_unit:
            no_imam_data.append(unit.name)
            continue
        if (latest is not None and latest.text_value != "none") or unit.unit_id in imams_by_unit:
            with_imam.append(unit.name)
            refs.append(f"unit:{unit.name}")
        else:
            no_imam_data.append(unit.name)
            refs.append(f"unit:{unit.name}")
    return {"with_imam": with_imam, "no_imam_data": no_imam_data, "refs": tuple(refs)}


def build_prayer_dossier(
    *,
    events: Sequence[ReportedEvent],
    units: Sequence[UnitRecord],
    facts: Sequence[EntityFact],
    imams: Sequence[ImamRecord] = (),
    plan_items: Sequence[PlanItem] = PRAYER_PLAN_1405,
    period: str = "1405",
) -> dict[str, object]:
    """The visit dossier section: visit row + instrument metadata (no PII)."""
    visit_row = build_visit_worksheet_prayer_row(
        events=events,
        units=units,
        facts=facts,
        imams=imams,
        plan_items=plan_items,
        period=period,
    )
    return {
        "period": period,
        "instrument": ASSESSMENT_INSTRUMENT_1405.instrument_id,
        "instrument_version": ASSESSMENT_INSTRUMENT_1405.version,
        "unit_count": len(units),
        "visit_worksheet_row": visit_row.as_dict(),
        "privacy_note": "این پرونده فقط شمارش‌های تجمیعی دارد؛ دادهٔ شخصی رجیستری از پروجکشن خارج نمی‌شود.",
    }
