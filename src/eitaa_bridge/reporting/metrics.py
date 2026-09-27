"""Versioned metric dictionary for the reporting section shell (F-088).

Every quantitative claim in the shell must resolve to a metric defined here.
A metric carries its unit, optional ordered choices, the entity kinds it can
attach to, and its aggregation rule. Workbook columns and visit-worksheet
cells are computed projections of these metrics, never the storage model.
Text that cannot be normalized to a coded choice stays in ``note`` fields and
goes through the normalization candidate queue (``store``); raw free text is
never silently promoted to a coded fact.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Mapping

METRIC_DICTIONARY_VERSION = "prayer-metrics-v1"

UNITS = frozenset({"count", "currency", "percent", "text", "choice"})

# Entity kinds a fact may attach to (ADR-61: facts attach to events AND to
# registry entities such as units, venues and imams).
ENTITY_KINDS = frozenset({"event", "unit", "venue", "imam", "nomokalaf"})

AGGREGATIONS = frozenset({"sum", "average", "latest", "none"})


@dataclass(slots=True, frozen=True)
class MetricDefinition:
    key: str
    label: str
    unit: str = "count"
    applies_to: frozenset[str] = frozenset({"event"})
    aggregate: str = "sum"
    choices: tuple[str, ...] = ()
    ordinal: bool = False  # choices are ordered low→high and rank-comparable

    def validate(self) -> None:
        if not self.key.strip():
            raise ValueError("Metric key cannot be empty.")
        if self.unit not in UNITS:
            raise ValueError(f"Unknown unit: {self.unit!r}")
        if not self.applies_to <= ENTITY_KINDS:
            raise ValueError(f"Unknown entity kinds: {sorted(self.applies_to - ENTITY_KINDS)}")
        if self.aggregate not in AGGREGATIONS:
            raise ValueError(f"Unknown aggregation rule: {self.aggregate!r}")
        if (self.unit == "choice" or self.choices) and not self.choices:
            raise ValueError(f"Metric {self.key!r} requires choices for choice values.")
        if self.choices and self.ordinal and len(self.choices) < 2:
            raise ValueError(f"Ordinal metric {self.key!r} needs at least two ordered choices.")

    def choice_rank(self, value: str) -> int:
        """Rank of a coded choice for ordinal comparison (threshold checks)."""
        if not self.ordinal or value not in self.choices:
            raise ValueError(f"{value!r} is not an ordinal choice of {self.key!r}.")
        return self.choices.index(value)

    def accepts(self, value: object) -> bool:
        if self.unit == "choice":
            return isinstance(value, str) and value in self.choices
        if self.unit == "text":
            return isinstance(value, str)
        if self.unit in {"count", "currency", "percent"}:
            return isinstance(value, (int, float)) and not isinstance(value, bool)
        return False


class MetricDictionary:
    """Versioned registry of metric definitions."""

    version = METRIC_DICTIONARY_VERSION

    def __init__(self, metrics: Iterable[MetricDefinition] = ()) -> None:
        self._metrics: dict[str, MetricDefinition] = {}
        for metric in metrics:
            self.register(metric)

    def register(self, metric: MetricDefinition) -> None:
        metric.validate()
        if metric.key in self._metrics:
            raise ValueError(f"Duplicate metric key: {metric.key!r}")
        self._metrics[metric.key] = metric

    def get(self, key: str) -> MetricDefinition:
        try:
            return self._metrics[key]
        except KeyError as exc:  # pragma: no cover - message clarity only
            raise KeyError(f"Unknown metric: {key!r}") from exc

    def __contains__(self, key: str) -> bool:
        return key in self._metrics

    def __len__(self) -> int:
        return len(self._metrics)

    def all(self) -> tuple[MetricDefinition, ...]:
        return tuple(self._metrics.values())

    def validate_value(self, key: str, value: object) -> None:
        metric = self.get(key)
        if not metric.accepts(value):
            raise ValueError(f"Value {value!r} is not valid for metric {key!r} ({metric.unit}).")


# ---------------------------------------------------------------------------
# Deep-dimension event metrics for the prayer section (design doc §7):
# cost is document-first, surveys aggregate, innovations are knowledge items.
# ---------------------------------------------------------------------------

PRAYER_EVENT_METRICS: tuple[MetricDefinition, ...] = (
    MetricDefinition(key="reception_cost", label="هزینهٔ پذیرایی", unit="currency", applies_to=frozenset({"event"})),
    MetricDefinition(key="financial_docs_present", label="مستندات مالی موجود است", unit="count", applies_to=frozenset({"event"})),
    MetricDefinition(
        key="survey_respondents",
        label="تعداد پاسخ‌دهندگان نظرسنجی",
        unit="count",
        applies_to=frozenset({"event"}),
        aggregate="sum",
    ),
    MetricDefinition(
        key="survey_satisfaction",
        label="درصد رضایت نظرسنجی",
        unit="percent",
        applies_to=frozenset({"event"}),
        aggregate="average",
    ),
    MetricDefinition(
        key="innovation_item",
        label="شرح ابتکار",
        unit="text",
        applies_to=frozenset({"event"}),
        aggregate="none",
    ),
)


# ---------------------------------------------------------------------------
# وضعیت‌سنجی نمازخانه‌ها (design doc §8): the first survey instrument. Coded
# choices mirror the bands observed in the 1405 questionnaire; fields whose
# answers arrive as free text map to a code through the normalization queue.
# ---------------------------------------------------------------------------

@dataclass(slots=True, frozen=True)
class InstrumentField:
    """One question of a periodic assessment instrument.

    ``source_column`` is the spreadsheet column of the 1405 وضعیت‌سنجی file so
    imports can be traced back to the physical document. Fields that arrive as
    free text (``normalization="candidate"``) never become facts directly.
    """

    metric: MetricDefinition
    source_column: str = ""
    normalization: str = "coded"  # coded | candidate | note_only
    entity_kind: str = "unit"


INSTRUMENT_ASSESSMENT_1405_VERSION = "assessment-1405-v1"

_ASSESSMENT_FIELDS: tuple[InstrumentField, ...] = (
    InstrumentField(
        MetricDefinition(
            key="cultural_liaison_present",
            label="وجود رابط فرهنگی",
            unit="choice",
            applies_to=frozenset({"unit"}),
            choices=("present", "absent"),
            aggregate="latest",
        ),
        source_column="D",
    ),
    InstrumentField(
        MetricDefinition(
            key="jammat_frequency",
            label="تواتر برگزاری نماز جماعت",
            unit="choice",
            applies_to=frozenset({"unit"}),
            choices=("daily", "occasional", "never"),
            ordinal=True,
            aggregate="latest",
        ),
        source_column="E",
    ),
    InstrumentField(
        MetricDefinition(
            key="jammat_avg_attendees",
            label="میانگین نمازگزاران جماعت",
            unit="count",
            applies_to=frozenset({"unit"}),
            aggregate="average",
        ),
        source_column="F",
    ),
    InstrumentField(
        MetricDefinition(
            key="imam_source",
            label="منبع امام جماعت",
            unit="choice",
            applies_to=frozenset({"unit"}),
            choices=("none", "staff_cleric", "invited_external"),
            aggregate="latest",
        ),
        source_column="L",
    ),
    InstrumentField(
        MetricDefinition(
            key="between_prayers_program",
            label="برنامهٔ احکام/حدیث بین‌الصلاتین",
            unit="choice",
            applies_to=frozenset({"unit"}),
            choices=("held", "not_held"),
            aggregate="latest",
        ),
        source_column="O",
    ),
    InstrumentField(
        MetricDefinition(
            key="azan_broadcast",
            label="پخش اذان",
            unit="choice",
            applies_to=frozenset({"unit", "venue"}),
            choices=("regular", "sometimes", "none"),
            ordinal=True,
            aggregate="latest",
        ),
        source_column="R",
    ),
    InstrumentField(
        MetricDefinition(
            key="azan_method",
            label="نحوهٔ پخش اذان",
            unit="choice",
            applies_to=frozenset({"unit", "venue"}),
            choices=("speaker", "radio", "live_carrier"),
            aggregate="latest",
        ),
        source_column="S",
    ),
    InstrumentField(
        MetricDefinition(
            key="council_sessions_band",
            label="بازهٔ جلسات شورای اقامه نماز",
            unit="choice",
            applies_to=frozenset({"unit"}),
            # ascending: the mandate threshold is the top band (design doc §8).
            choices=("none", "once_a_year", "two_to_three", "four_to_six"),
            ordinal=True,
            aggregate="latest",
        ),
        source_column="U",
    ),
    InstrumentField(
        MetricDefinition(
            key="venue_carpet",
            label="فرش نمازخانه",
            unit="choice",
            applies_to=frozenset({"unit", "venue"}),
            choices=("prayer_carpet", "regular_carpet"),
            aggregate="latest",
        ),
        source_column="W",
    ),
    InstrumentField(
        MetricDefinition(
            key="venue_seals_state",
            label="وضعیت مهرهای نمازخانه",
            unit="choice",
            applies_to=frozenset({"unit", "venue"}),
            choices=("clean", "needs_replacement"),
            aggregate="latest",
        ),
        source_column="X",
    ),
    InstrumentField(
        MetricDefinition(
            key="venue_quran_supply",
            label="کفایت قرآن و مفاتیح",
            unit="choice",
            applies_to=frozenset({"unit", "venue"}),
            choices=("sufficient", "insufficient"),
            aggregate="latest",
        ),
        source_column="Y",
    ),
    InstrumentField(
        MetricDefinition(
            key="venue_facilities_state",
            label="وضعیت امکانات نمازخانه",
            unit="choice",
            applies_to=frozenset({"unit", "venue"}),
            choices=("good", "partially_incomplete"),
            aggregate="latest",
        ),
        source_column="Z",
    ),
    # Free-text fields of the source questionnaire: reason/explanation pairs
    # and qualitative judgements. They are notes by default; coding them is a
    # human-approved normalization decision.
    InstrumentField(
        MetricDefinition(
            key="jammat_absence_reason",
            label="دلیل عدم برگزاری جماعت",
            unit="text",
            applies_to=frozenset({"unit"}),
            aggregate="none",
        ),
        source_column="G",
        normalization="note_only",
    ),
    InstrumentField(
        MetricDefinition(
            key="jammat_occasional_reason",
            label="دلیل برگزاری گاه‌گاه جماعت",
            unit="text",
            applies_to=frozenset({"unit"}),
            aggregate="none",
        ),
        source_column="I",
        normalization="note_only",
    ),
    InstrumentField(
        MetricDefinition(
            key="chief_participation",
            label="حضور رئیس حوزه در نماز جماعت",
            unit="text",
            applies_to=frozenset({"unit"}),
            aggregate="none",
        ),
        source_column="K",
        normalization="candidate",
    ),
    InstrumentField(
        MetricDefinition(
            key="imam_public_satisfaction",
            label="رضایت عمومی از امام جماعت",
            unit="text",
            applies_to=frozenset({"unit"}),
            aggregate="none",
        ),
        source_column="M",
        normalization="candidate",
    ),
    InstrumentField(
        MetricDefinition(
            key="council_absence_reason",
            label="دلیل عدم برگزاری جلسهٔ شورا",
            unit="text",
            applies_to=frozenset({"unit"}),
            aggregate="none",
        ),
        source_column="V",
        normalization="note_only",
    ),
    InstrumentField(
        MetricDefinition(
            key="venue_facilities_gaps",
            label="اقلام ناقص نمازخانه",
            unit="text",
            applies_to=frozenset({"unit", "venue"}),
            aggregate="none",
        ),
        source_column="AA",
        normalization="note_only",
    ),
)


@dataclass(slots=True, frozen=True)
class AssessmentInstrument:
    """A periodic questionnaire that harvests facts about several entities."""

    instrument_id: str
    title: str
    version: str
    fields: tuple[InstrumentField, ...]

    def validate(self) -> None:
        if not self.instrument_id.strip():
            raise ValueError("Instrument id cannot be empty.")
        keys = [f.metric.key for f in self.fields]
        if len(keys) != len(set(keys)):
            raise ValueError("Duplicate metric keys in instrument fields.")
        for f in self.fields:
            f.metric.validate()

    def field_by_metric(self, key: str) -> InstrumentField | None:
        return next((f for f in self.fields if f.metric.key == key), None)

    def field_by_column(self, column: str) -> InstrumentField | None:
        return next((f for f in self.fields if f.source_column == column), None)


ASSESSMENT_INSTRUMENT_1405 = AssessmentInstrument(
    instrument_id="prayer_status_assessment",
    title="وضعیت‌سنجی اقامه نماز حوزه‌های قضایی",
    version=INSTRUMENT_ASSESSMENT_1405_VERSION,
    fields=_ASSESSMENT_FIELDS,
)

METRIC_DICTIONARY = MetricDictionary([f.metric for f in _ASSESSMENT_FIELDS] + list(PRAYER_EVENT_METRICS))

# Council-session mandate threshold: the 1405 دستورالعمل expects the top band
# ("4 تا 6 جلسه در سال"). Realization/monitoring compares against this rank.
COUNCIL_SESSIONS_MANDATE_CHOICE = "four_to_six"

# Deterministic normalizers for the coded fields of the 1405 وضعیت‌سنجی file.
# Keys are substrings of the observed free answers; first match wins. Entries
# here cover the recurring exact wordings — anything else becomes a candidate.
CODED_FIELD_NORMALIZERS: Mapping[str, tuple[tuple[str, str], ...]] = {
    "cultural_liaison_present": (("رابط فرهنگی هستم", "present"), ("رابط فرهنگی نیستم", "absent")),
    "jammat_frequency": (
        ("همه روزه", "daily"),
        ("گاهی از اوقات", "occasional"),
        ("نمی شود", "never"),
        ("نمی‌شود", "never"),
    ),
    "imam_source": (
        ("نداریم", "none"),
        ("شاغل در دستگاه", "staff_cleric"),
        ("مدعو", "invited_external"),
    ),
    "between_prayers_program": (("اجرا می شود", "held"), ("اجرا نمی شود", "not_held"), ("اجرا نمی‌شود", "not_held")),
    "azan_broadcast": (("بله به صورت مرتب", "regular"), ("گاهی پخش می شود", "sometimes"), ("گاهی پخش می‌شود", "sometimes")),
    "azan_method": (("حلقومی", "live_carrier"), ("رادیویی", "radio"), ("صوتی", "speaker")),
    "council_sessions_band": (
        ("مطابق دستورالعمل", "four_to_six"),
        ("4 تا 6", "four_to_six"),
        ("۴ تا ۶", "four_to_six"),
        ("2 تا 3", "two_to_three"),
        ("۲ تا ۳", "two_to_three"),
        ("فقط یکبار", "once_a_year"),
        ("فقط یک بار", "once_a_year"),
    ),
    "venue_carpet": (("سجاده ای", "prayer_carpet"), ("سجاده‌ای", "prayer_carpet"), ("فرش عادی", "regular_carpet")),
    "venue_seals_state": (("کثیف", "needs_replacement"), ("تمیز", "clean")),
    "venue_quran_supply": (("نداریم", "insufficient"), ("کافی", "sufficient")),
    "venue_facilities_state": (("ناقص", "partially_incomplete"), ("مناسب هست", "good")),
}


def normalize_coded_value(metric_key: str, raw_text: str) -> str | None:
    """Deterministically map observed wording to a coded choice, else None."""
    text = raw_text.strip()
    if not text:
        return None
    for needle, code in CODED_FIELD_NORMALIZERS.get(metric_key, ()):
        if needle in text:
            return code
    return None
