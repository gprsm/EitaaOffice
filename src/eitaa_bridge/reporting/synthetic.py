"""Believable synthetic survey data generation (F-090 follow-up).

The owner's standing decision (recorded in F-088 §7 and the questionnaire
model §G): where a survey was genuinely not conducted, the system may
produce *plausible* survey aggregates so the reporting pipeline stays
exercisable — but every generated value carries ``synthetic_placeholder``
and is structurally barred from verified statistics (ADR-42 export gate).

Generation is deterministic per event id (hash-seeded), so re-running never
invents different numbers for the same event, and regeneration is auditable.
Nothing here touches real respondents: the respondent themes pool is a fixed
benign set written for this purpose.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from .metrics import METRIC_DICTIONARY
from .model import Fact, FactValueKind, ValueSource

SYNTHETIC_GENERATOR = "synthetic-survey-v1"

# Fixed benign comment themes for the virtual survey sheet — deliberately
# generic so no real respondent voice is ever simulated.
_THEMES_POSITIVE = (
    "برگزاری منظم و به‌موقع برنامه",
    "هماهنگی مناسب ستاد با حوزه‌های قضایی",
    "رضایت از کیفیت اجرا و پذیرایی",
    "استقبال مطلوب همکاران و خانواده‌ها",
    "اطلاع‌رسانی کافی پیش از برنامه",
)
_THEMES_IMPROVE = (
    "افزایش ظرفیت پذیرایی در برنامه‌های پراستقبال",
    "تنوع بیشتر در برنامهٔ جنبی",
    "بهبود فضای برگزاری در روزهای گرم",
)


@dataclass(slots=True)
class SyntheticSurvey:
    """A generated survey aggregate for one event."""

    event_id: str
    respondents: int
    satisfaction_percent: float
    theme_positive: str
    theme_improvement: str
    seed_note: str

    def as_facts(self) -> list[Fact]:
        """Facts carrying ``synthetic_placeholder`` — never export-ready."""
        facts = [
            Fact(
                metric="survey_respondents",
                value=float(self.respondents),
                value_kind=FactValueKind.SYNTHETIC_PLACEHOLDER,
                unit_of_measure="count",
                source=ValueSource.DERIVED,
                note=f"{SYNTHETIC_GENERATOR}: {self.seed_note}",
            ),
            Fact(
                metric="survey_satisfaction",
                value=self.satisfaction_percent,
                value_kind=FactValueKind.SYNTHETIC_PLACEHOLDER,
                unit_of_measure="percent",
                source=ValueSource.DERIVED,
                note=f"{SYNTHETIC_GENERATOR}: {self.seed_note}",
            ),
            Fact(
                metric="survey_theme_positive",
                value=0.0,
                value_kind=FactValueKind.SYNTHETIC_PLACEHOLDER,
                unit_of_measure="text",
                source=ValueSource.DERIVED,
                note=f"{SYNTHETIC_GENERATOR}: {self.theme_positive}",
            ),
            Fact(
                metric="survey_theme_improvement",
                value=0.0,
                value_kind=FactValueKind.SYNTHETIC_PLACEHOLDER,
                unit_of_measure="text",
                source=ValueSource.DERIVED,
                note=f"{SYNTHETIC_GENERATOR}: {self.theme_improvement}",
            ),
        ]
        for fact in facts:
            fact.validate()
        return facts


def _seed_of(event_id: str) -> int:
    digest = hashlib.sha256(f"{SYNTHETIC_GENERATOR}:{event_id}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


def generate_survey(event_id: str, *, scale: str = "normal") -> SyntheticSurvey:
    """Deterministic, believable survey aggregates for one event.

    ``scale`` shifts the ranges: ``small`` for unit-level programs, ``normal``
    for provincial ones — the numbers stay inside what such programs plausibly
    produce, per the owner's "فیک اما قابل باور" instruction.
    """
    seed = _seed_of(event_id)
    if scale == "small":
        respondents = 12 + (seed % 21)          # 12..32
        satisfaction = 61 + (seed >> 8) % 30    # 61..90
    else:
        respondents = 18 + (seed % 38)          # 18..55
        satisfaction = 64 + (seed >> 8) % 32    # 64..95
    positive = _THEMES_POSITIVE[(seed >> 16) % len(_THEMES_POSITIVE)]
    improvement = _THEMES_IMPROVE[(seed >> 24) % len(_THEMES_IMPROVE)]
    return SyntheticSurvey(
        event_id=event_id,
        respondents=respondents,
        satisfaction_percent=float(satisfaction),
        theme_positive=positive,
        theme_improvement=improvement,
        seed_note=f"seed={seed % 10_000}; scale={scale}",
    )


def event_has_survey(facts) -> bool:
    """Whether any real (export-ready or estimated) survey fact already exists.

    Synthetic placeholders do NOT count as existing surveys — regenerating
    over a placeholder is allowed; over real data never.
    """
    for fact in facts:
        if fact.metric in {"survey_respondents", "survey_satisfaction"}:
            if fact.value_kind is not FactValueKind.SYNTHETIC_PLACEHOLDER:
                return True
    return False


def validate_survey_metric(value: float, metric: str) -> None:
    """Guard: satisfaction stays a percent, respondents a plausible count."""
    definition = METRIC_DICTIONARY.get(metric)
    if not definition.accepts(value):
        raise ValueError(f"Value {value!r} invalid for {metric}")
