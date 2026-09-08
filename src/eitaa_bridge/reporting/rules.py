"""Counting rules transcribed from the 1405 workbook footnotes.

Rules are versioned via ``RULES_VERSION``; changing a rule bumps the version
so provincial metrics stay reproducible (questionnaire model, section H).

Sources (workbook cells):
- ``مراسم  مذهبی!C12``: Ashura pilgrimage is excluded from the main ceremony
  count but must be reported separately with its own annex.
- ``مراسم  مذهبی!C15``: a contest held during a ceremony counts under the
  contests program, not under ceremonies.
- ``مراسم  مذهبی!C16``: between-prayers speeches are not a session; a session
  requires >30 minutes, prior announcement and reception.
- ``تکریم و تجلیل!B9/B10``: an honor ceremony counts only when the Chief
  Justice of the province or the highest provincial official attended, and the
  ceremony must be standalone with an explicit honor title.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .model import (
    FactValueKind,
    OccasionClass,
    ProgramId,
    ProgramKind,
    ReportedEvent,
)

RULES_VERSION = "workbook-1405-rules-v1"


@dataclass(slots=True, frozen=True)
class ProgramShare:
    """Which workbook programs an event feeds, and whether it counts there."""

    program_id: ProgramId
    counts: bool
    reason: str


def classify_event_programs(event: ReportedEvent) -> tuple[ProgramShare, ...]:
    shares: list[ProgramShare] = []

    for kind in event.program_kinds:
        if kind is ProgramKind.CEREMONY:
            if event.is_ashura_pilgrimage:
                # C12: excluded from the main ceremony statistics; the
                # aggregator still surfaces it as a separate annex metric.
                shares.append(ProgramShare(ProgramId.CEREMONIES, counts=False, reason="ashura_pilgrimage_excluded_c12"))
            else:
                shares.append(ProgramShare(ProgramId.CEREMONIES, counts=True, reason="ceremony_counts"))
        elif kind in (ProgramKind.CONTEST, ProgramKind.QURAN_CONTEST):
            shares.append(ProgramShare(ProgramId.CONTEST, counts=True, reason="contest_counts"))
        elif kind is ProgramKind.TRIP:
            shares.append(ProgramShare(ProgramId.TRIP, counts=True, reason="trip_counts"))
        elif kind is ProgramKind.PRAYER:
            shares.append(ProgramShare(ProgramId.PRAYER, counts=True, reason="prayer_activity_counts"))
        elif kind is ProgramKind.HONOR:
            if event.official_present is not True:
                shares.append(ProgramShare(ProgramId.HONOR, counts=False, reason="official_presence_unconfirmed_b9"))
            elif not event.is_standalone_titled:
                shares.append(ProgramShare(ProgramId.HONOR, counts=False, reason="not_standalone_titled_b10"))
            else:
                shares.append(ProgramShare(ProgramId.HONOR, counts=True, reason="honor_counts"))
        elif kind is ProgramKind.CUSTOMER_CARE:
            if event.official_present is not True:
                shares.append(ProgramShare(ProgramId.CUSTOMER_CARE, counts=False, reason="official_presence_unconfirmed_c8"))
            else:
                shares.append(ProgramShare(ProgramId.CUSTOMER_CARE, counts=True, reason="customer_care_counts"))
        elif kind is ProgramKind.CHARTER:
            shares.append(ProgramShare(ProgramId.CHARTER, counts=True, reason="charter_action_counts"))

    return tuple(shares)


def is_valid_session(event: ReportedEvent) -> bool:
    """C16: >30 minutes, prior announcement, and reception are all required."""

    if event.duration_minutes is None:
        return False
    return event.duration_minutes > 30 and event.prior_announcement and event.had_reception


class CountingRuleEngine:
    """Applies workbook rules over events; never guesses human decisions.

    Eligibility of honor/customer-care events is not inferred from photos or
    messages: the ``official_present`` flag is answered by the human operator
    at entry time (Q-IR-011) and the engine only enforces the consequence.
    """

    version = RULES_VERSION

    def classify(self, event: ReportedEvent) -> tuple[ProgramShare, ...]:
        event.validate()
        return classify_event_programs(event)

    def ceremony_countable(self, event: ReportedEvent) -> bool:
        if ProgramKind.CEREMONY not in event.program_kinds:
            return False
        return any(share.counts for share in classify_event_programs(event) if share.program_id is ProgramId.CEREMONIES)

    def session_valid(self, event: ReportedEvent) -> bool:
        return is_valid_session(event)

    def ashura_annex_events(self, events: Sequence[ReportedEvent]) -> list[ReportedEvent]:
        return [event for event in events if event.is_ashura_pilgrimage]

    def occasion_class_of(self, event: ReportedEvent) -> OccasionClass | None:
        return event.occasion_class

    def export_gate(self, fact_value_kind: FactValueKind) -> bool:
        """ADR-42: estimated/synthetic values never reach verified exports."""

        return fact_value_kind in {FactValueKind.VERIFIED, FactValueKind.OBSERVED, FactValueKind.REPORTED_BY_UNIT}
