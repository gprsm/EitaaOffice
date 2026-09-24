"""Multi-criteria Eitaa message indexer for the 1405 reporting core.

Monitors configured channels/groups, splits messages into three intent
classes, and maps event-report messages onto the seven workbook programs.

Intent classes (user mandate, SRC-USER-IR-008):
- ``event_report``: a real cultural activity happened -> feeds the reporting
  core as an ``EventCandidate``.
- ``informational``: announcements, invitations, ads, links, greetings that
  describe or promote something without asserting an executed activity.
- ``promotional``: marketing/propaganda style text with no activity content.

The classifier is deliberately conservative (abstain -> informational) and
every decision carries matched-evidence so the central staff can review,
confirm or override. Nothing here decides eligibility of honor events.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import re
from typing import Any, Iterable, Mapping, Sequence

from .eitaa_extraction import _normalize
from .model import OccasionClass, ProgramKind

INDEXER_VERSION = "eitaa-intent-indexer-v1"

DEFAULT_MONITOR_TARGETS: tuple[str, ...] = (
    "مدیریت امور فرهنگی دادگستری",
    "رابطان فرهنگی دادگستری",
)


class MessageIntent:
    EVENT_REPORT = "event_report"
    INFORMATIONAL = "informational"
    PROMOTIONAL = "promotional"


class ScoreWeights:
    EXECUTION_MARKER = 3.0
    PROGRAM_HINT = 2.0
    ATTENDEE_NUMBER = 2.0
    UNIT_HINT = 1.0
    OCCASION_HINT = 1.0
    FUTURE_ANNOUNCEMENT = -2.5
    AD_NO_ACTIVITY = -2.0
    LINK_ONLY = -1.5


_EXECUTION_MARKERS: tuple[str, ...] = (
    "برگزار شد", "برگزاری شد", "برگزار گردید", "برگزاری گردید",
    "انجام شد", "انجام گرفت", "اقدام شد", "اقدام گردید",
    "اجرا شد", "اجرا گردید", "به انجام رسید", "داشتیم", "صورت گرفت",
    "برگزار شد بعنوان", "بازدید انجام", "زیارت انجام", "مصوب شد", "نصب شد", "توزیع شد", "اهدای", "اهداء شد",
)

_FUTURE_MARKERS: tuple[str, ...] = (
    "خواهد شد", "برگزار میشود", "برگزار خواهد شد", "دعوت میشوید",
    "دعوت می شوید", "منتظر حضور", "ثبتنام", "ثبت نام", "مهلت",
    "تا ساعت", "لینک ثبت", "اطلاعیه شماره", "جشنواره پیش رو",
    "به مناسبت برگزار میشود", "به مناسبت خواهد شد",
)

_AD_MARKERS: tuple[str, ...] = (
    "فروش", "تخفیف", "خرید", "دانلود کنید", "کلیک کنید", "عضویت",
    "کانال ما را", "به کانال", "پیام بدهید", "همکاری در فروش",
)

_UNIT_MARKERS: tuple[str, ...] = (
    "دادگستری", "ستاد", "اداره", "مدیریت کل", "معاونت",
    "حوزه قضایی", "قضایی", "شهرستان", "دفتر", "سیمرغ",
    "کلانتری", "آموزش و کار", "پرونده", "دادیاری", "کارشناسی",
)

_OCCASION_KEYWORDS: tuple[tuple[OccasionClass, tuple[str, ...]], ...] = (
    (OccasionClass.RELIGIOUS, ("محرم", "صفر", "ربیع", "مولودی", "ولادت", "شهادت", "وفات", "غدیر", "عید فطر", "عید قربان", "هفته وحدت", "زیارت", "عاشورا", "تسلیت", "تولد", "امام", "دعای توسل")),
    (OccasionClass.REVOLUTIONARY, ("۲۲ بهمن", "22 بهمن", "انقلاب", "۱۳ آبان", "13 آبان", "پیروزی", "اسلامی", "بهمن", "آزادی", "هفته دفاع مقدس", "دفاع مقدس", "شهدای خدمت", "یادواره شهدا")),
    (OccasionClass.NATIONAL, ("هفته", "روز کارگر", "روز دختر", "روز عصای سفید", "روز خانواده", "میلاد", "روز زن", "روز مرد", "روز کارمند", "روز ارباب رجوع", "هفته دولت")),
)

_PROGRAM_HINTS: tuple[tuple[ProgramKind, tuple[str, ...]], ...] = (
    (ProgramKind.TRIP, ("اردو", "زیارتی", "بازدید")),
    (ProgramKind.QURAN_CONTEST, ("قرآنی", "قرآن")),
    (ProgramKind.CONTEST, ("مسابقه", "مسابقات", "مسابقهای", "رقابت", "جشنواره")),
    (ProgramKind.CEREMONY, ("مراسم", "مناسبت", "مولودی", "یادبود", "هفته", "همایش", "نشست", "دیدار", "موکب", "ایستگاه صلواتی")),
    (ProgramKind.PRAYER, ("نماز", "جماعت", "تکلیف", "نمازخانه", "شورای اقامه نماز", "ستاد اقامه نماز", "خادمین نماز", "بین الصلاتین", "احکام")),
    (ProgramKind.HONOR, ("تکریم", "تجلیل", "بازنشسته", "تقدیر", "لوح تقدیر", "لوح سپاس", "ایثارگر", "جانباز", "همکار نمونه")),
    (ProgramKind.CUSTOMER_CARE, ("ارباب رجوع", "رضایت", "مشتری", "میز خدمت", "ملاقات مردمی", "دیدار مردمی")),
    (ProgramKind.CHARTER, ("منشور", "اخلاق", "الگوی تعالی", "سلامت اداری", "صیانت", "رفتار حرفه ای")),
)

_ADMIN_CRIME_MARKERS: tuple[str, ...] = (
    "دستگیری", "بازداشت", "کشف جرم", "قاچاق", "مواد مخدر", "سارق",
    "اجرای احکام", "کیفرخواست", "قتل", "قصاص", "سامانه ثنا", "مزایده",
)

_ATTENDEE_RE = re.compile(r"([۰-۹0-9]{1,6})\s*(?:نفر|شخص|کاربر|شرکت[‌ ]?کننده|مدعو)")
_MEDIA_PHOTO_RE = re.compile(r"عکس|تصاویر|فیلم|گالری")
_MONTH_RE = re.compile(
    r"(فروردین|اردیبهشت|خرداد|تیر|مرداد|شهریور|مهر|آبان|آذر|دی|بهمن|اسفند)"
)
_DATE_RE = re.compile(r"(\d{1,2}\s*(?:فروردین|اردیبهشت|خرداد|تیر|مرداد|شهریور|مهر|آبان|آذر|دی|بهمن|اسفند))|(\d{4}[/\-]\d{1,2}[/\-]\d{1,2})")
_URL_RE = re.compile(r"https?://|t\.me/|eitaa\.")


@dataclass(slots=True)
class IndexDecision:
    """One scored decision for one message; reviewable end to end."""

    message_ref: str
    dialog_label: str
    intent: str
    score: float
    matched_programs: tuple[str, ...] = ()
    matched_execution: tuple[str, ...] = ()
    matched_future: tuple[str, ...] = ()
    matched_ad: tuple[str, ...] = ()
    unit_hints: tuple[str, ...] = ()
    occasion_class: OccasionClass | None = None
    occasion_matched: str = ""
    attendee_count: int | None = None
    date_hint: str | None = None
    has_media_mention: bool = False
    index_version: str = INDEXER_VERSION
    indexed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def is_event_report(self) -> bool:
        return self.intent == MessageIntent.EVENT_REPORT

    def evidence(self) -> dict[str, Any]:
        return {
            "message_ref": self.message_ref,
            "dialog": self.dialog_label,
            "intent": self.intent,
            "score": round(self.score, 2),
            "matched_programs": list(self.matched_programs),
            "execution_markers": list(self.matched_execution),
            "future_markers": list(self.matched_future),
            "ad_markers": list(self.matched_ad),
            "unit_hints": list(self.unit_hints),
            "occasion_class": self.occasion_class.value if self.occasion_class else None,
            "occasion_matched": self.occasion_matched,
            "attendee_count": self.attendee_count,
            "date_hint": self.date_hint,
        }


class EitaaIntentIndexer:
    """Scores messages into intent classes with visible evidence."""

    version = INDEXER_VERSION

    def __init__(self, *, execution_markers: Iterable[str] = (), future_markers: Iterable[str] = ()) -> None:
        self._execution = tuple(execution_markers) or _EXECUTION_MARKERS
        self._future = tuple(future_markers) or _FUTURE_MARKERS

    def _unit_hints(self, text: str) -> tuple[str, ...]:
        return tuple(marker for marker in _UNIT_MARKERS if marker in text)

    def _occasion(self, text: str) -> tuple[OccasionClass | None, str]:
        for occ_class, keywords in _OCCASION_KEYWORDS:
            for keyword in keywords:
                if keyword in text:
                    return occ_class, keyword
        return None, ""

    def classify(
        self,
        text: str,
        *,
        message_ref: str = "",
        dialog_label: str = "",
    ) -> IndexDecision:
        normalized = _normalize(text)
        if not normalized:
            decision = IndexDecision(
                message_ref=message_ref,
                dialog_label=dialog_label,
                intent=MessageIntent.INFORMATIONAL,
                score=0.0,
            )
            return decision

        score = 0.0
        matched_execution = tuple(marker for marker in self._execution if marker in normalized)
        score += ScoreWeights.EXECUTION_MARKER * len(matched_execution)

        program_hits: list[ProgramKind] = []
        matched_programs: list[str] = []
        for kind, hints in _PROGRAM_HINTS:
            hits = [hint for hint in hints if hint in normalized]
            if hits:
                program_hits.append(kind)
                matched_programs.append(kind.value)
        score += ScoreWeights.PROGRAM_HINT * len(program_hits)

        attendee_count: int | None = None
        attendee_match = _ATTENDEE_RE.search(normalized)
        if attendee_match:
            try:
                attendee_count = int(attendee_match.group(1))
                score += ScoreWeights.ATTENDEE_NUMBER
            except ValueError:
                attendee_count = None

        unit_hints = self._unit_hints(normalized)
        score += ScoreWeights.UNIT_HINT * len(unit_hints)

        occasion_class, occasion_matched = self._occasion(normalized)
        if occasion_class is not None:
            score += ScoreWeights.OCCASION_HINT

        matched_future = tuple(marker for marker in self._future if marker in normalized)
        score += ScoreWeights.FUTURE_ANNOUNCEMENT * len(matched_future)

        matched_ad = tuple(marker for marker in _AD_MARKERS if marker in normalized)
        score += ScoreWeights.AD_NO_ACTIVITY * len(matched_ad)

        stripped = _URL_RE.sub("", normalized).strip(" .!،:؛-")
        has_link_only = bool(_URL_RE.search(normalized)) and len(stripped) < 40
        if has_link_only:
            score += ScoreWeights.LINK_ONLY

        matched_crime = tuple(marker for marker in _ADMIN_CRIME_MARKERS if marker in normalized)
        if matched_crime and not program_hits:
            score -= 4.0

        has_media_mention = bool(_MEDIA_PHOTO_RE.search(normalized))
        date_hint = None
        date_match = _DATE_RE.search(normalized)
        if date_match:
            date_hint = date_match.group(0)

        has_activity_signal = bool(matched_execution) or (attendee_count is not None) or has_media_mention
        if score >= 3.0 and has_activity_signal and (program_hits or occasion_class is not None):
            intent = MessageIntent.EVENT_REPORT
        elif matched_ad and not has_activity_signal:
            intent = MessageIntent.PROMOTIONAL
        else:
            intent = MessageIntent.INFORMATIONAL

        return IndexDecision(
            message_ref=message_ref,
            dialog_label=dialog_label,
            intent=intent,
            score=score,
            matched_programs=tuple(matched_programs),
            matched_execution=matched_execution,
            matched_future=matched_future,
            matched_ad=matched_ad,
            unit_hints=unit_hints,
            occasion_class=occasion_class,
            occasion_matched=occasion_matched,
            attendee_count=attendee_count,
            date_hint=date_hint,
            has_media_mention=has_media_mention,
        )

    def candidate_from_decision(self, decision: IndexDecision) -> Any | None:
        """Bridge an event-report decision into the reporting core."""

        if not decision.is_event_report:
            return None
        kinds = tuple(
            ProgramKind(value) for value in decision.matched_programs
        )
        if not kinds:
            kinds = (ProgramKind.CEREMONY,)
        from .eitaa_extraction import EventCandidate, EitaaCandidateExtractor
        import hashlib

        digest = hashlib.sha1(decision.message_ref.encode("utf-8")).hexdigest()[:10]
        candidate = EventCandidate(
            event_key=f"eitaa-index:{digest}",
            suggested_kinds=kinds,
            matched_keywords={},
            extracted_attendees=decision.attendee_count,
            extracted_date=decision.date_hint,
            occasion_class=decision.occasion_class,
            is_ashura_pilgrimage="عاشورا" in decision.occasion_matched and "زیارت" in decision.occasion_matched,
            sender_hint=decision.dialog_label,
            source_message_refs=(decision.message_ref,) if decision.message_ref else (),
            confidence_note=f"intent={decision.intent}; score={decision.score:.1f}; index={self.version}",
        )
        return candidate


def index_dialog_batch(
    indexer: EitaaIntentIndexer,
    messages: Sequence[tuple[str, str, str]],
) -> list[IndexDecision]:
    """Classify ``(message_ref, dialog_label, text)`` tuples in one pass."""

    return [
        indexer.classify(text, message_ref=ref, dialog_label=dialog)
        for ref, dialog, text in messages
    ]
