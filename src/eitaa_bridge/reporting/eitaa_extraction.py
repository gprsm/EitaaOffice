"""Level-1 bridge: turn Eitaa message texts into reporting candidates.

This module connects the existing Eitaa content-index/classifier world to the
reporting core. It never decides eligibility (Q-IR-011): human-gate facts are
produced as unanswered prompts, and every candidate carries provenance back
to the originating message so the human review pass can verify or reject.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import re
from typing import Any, Mapping, Sequence

from .model import (
    FactValueKind,
    OccasionClass,
    ProgramKind,
    ValueSource,
)

EXTRACTION_VERSION = "eitaa-candidate-extractor-v1"

_DIGITS = {"۰": "0", "۱": "1", "۲": "2", "۳": "3", "۴": "4", "۵": "5", "۶": "6", "۷": "7", "۸": "8", "۹": "9"}

_PROGRAM_KEYWORDS: tuple[tuple[ProgramKind, tuple[str, ...]], ...] = (
    (ProgramKind.TRIP, ("اردو", "زیارتی", "زیرت")),
    (ProgramKind.QURAN_CONTEST, ("قرآنی", "قرآن")),
    (ProgramKind.CONTEST, ("مسابقه", "مسابقات", "رقابت")),
    (
        ProgramKind.CEREMONY,
        (
            "مراسم",
            "مناسبت",
            "مولودی",
            "ولادت",
            "شهادت",
            "وفات",
            "هفته",
            "یادبود",
            "تجلیل از",
            "زیارت عاشورا",  # ashura pilgrimage is a ceremony-family activity (C12)
        ),
    ),
    (ProgramKind.PRAYER, ("نماز", "جشن تکلیف", "تکلیف", "امام جماعت", "ائمه جماعت")),
    (ProgramKind.HONOR, ("تکریم", "تجلیل", "بازنشستگان", "مفاخر")),
    (ProgramKind.CUSTOMER_CARE, ("ارباب رجوع", "رضایت ارباب رجوع", "تشویق")),
    (ProgramKind.CHARTER, ("منشور", "اخلاقی")),
)

_OCCASION_CLASSES: tuple[tuple[OccasionClass, tuple[str, ...]], ...] = (
    (OccasionClass.RELIGIOUS, ("مذهبی", "مولودی", "ولادت", "شهادت", "وفات", "محرم", "رمضان", "عید فطر", "عید قربان", "نوروز امام")),
    (OccasionClass.REVOLUTIONARY, ("انقلابی", "۲۲ بهمن", "22 بهمن", "اسفند", "پیروزی", "انقلاب")),
    (OccasionClass.NATIONAL, ("ملی", "ملی=", "کارگر", "میلاد", "روز دختر", "روز عصای سفید", "هفته وحدت")),
)

_ASHURA_RE = re.compile(r"زیارت\s*عاشورا|عاشورا")
_COUNT_RE = re.compile(r"([۰-۹0-9]{1,6})\s*(?:نفر|شخص|کاربر|شرکت[‌ ]?کننده)")
_DATE_RE = re.compile(r"(\d{4}[/\-]\d{1,2}[/\-]\d{1,2})|(\d{1,2}\s*(?:فروردین|اردیبهشت|خرداد|تیر|مرداد|شهریور|مهر|آبان|آذر|دی|بهمن|اسفند)\s*(?:\s*\d{1,2})?)")


def _normalize(text: str) -> str:
    normalized = text
    for persian, latin in _DIGITS.items():
        normalized = normalized.replace(persian, latin)
    return normalized.replace("ي", "ی").replace("ك", "ک").replace("\u200c", " ").strip()


@dataclass(slots=True)
class EventCandidate:
    """A suggested event extracted from one or more Eitaa messages."""

    event_key: str
    suggested_kinds: tuple[ProgramKind, ...]
    matched_keywords: dict[str, list[str]] = field(default_factory=dict)
    extracted_attendees: int | None = None
    extracted_date: str | None = None
    occasion_class: OccasionClass | None = None
    is_ashura_pilgrimage: bool = False
    sender_hint: str = ""
    source_message_refs: tuple[str, ...] = ()
    extracted_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    confidence_note: str = ""

    def to_prepared_event_fields(self) -> dict[str, Any]:
        return {
            "program_kinds": list(self.suggested_kinds),
            "occasion_class": self.occasion_class,
            "is_ashura_pilgrimage": self.is_ashura_pilgrimage,
            "attendees_hint": self.extracted_attendees,
            "date_hint": self.extracted_date,
            "evidence_refs": list(self.source_message_refs),
        }


class EitaaCandidateExtractor:
    """Conservative, keyword-based extractor; abstains when unsure."""

    version = EXTRACTION_VERSION

    def __init__(self, extra_keywords: Mapping[ProgramKind, Sequence[str]] | None = None) -> None:
        self._keywords: dict[ProgramKind, tuple[str, ...]] = {kind: kws for kind, kws in _PROGRAM_KEYWORDS}
        if extra_keywords:
            for kind, kws in extra_keywords.items():
                existing = self._keywords.get(kind, ())
                self._keywords[kind] = existing + tuple(kws)

    def extract(self, text: str, *, message_ref: str = "", sender_hint: str = "") -> EventCandidate | None:
        normalized = _normalize(text)
        if not normalized:
            return None

        matched: dict[str, list[str]] = {}
        kinds: list[ProgramKind] = []
        for kind, keywords in self._keywords.items():
            hits = [kw for kw in keywords if kw in normalized]
            if hits:
                kinds.append(kind)
                matched[kind.value] = hits
        if not kinds:
            return None

        attendees: int | None = None
        count_match = _COUNT_RE.search(normalized)
        if count_match:
            try:
                attendees = int(count_match.group(1))
            except ValueError:
                attendees = None

        date_match = _DATE_RE.search(normalized)

        occasion_class: OccasionClass | None = None
        for occ_class, keywords in _OCCASION_CLASSES:
            if any(kw in normalized for kw in keywords):
                occasion_class = occ_class
                break

        is_ashura = bool(_ASHURA_RE.search(normalized)) and "عاشورا" in normalized

        return EventCandidate(
            event_key=f"eitaa:{message_ref or 'unreferenced'}",
            suggested_kinds=tuple(kinds),
            matched_keywords=matched,
            extracted_attendees=attendees,
            extracted_date=date_match.group(0) if date_match else None,
            occasion_class=occasion_class if not is_ashura else None,
            is_ashura_pilgrimage=is_ashura and any(kw in normalized for kw in ("زیارت", "زیرت")),
            sender_hint=sender_hint,
            source_message_refs=(message_ref,) if message_ref else (),
            confidence_note="keyword-candidate; human review required",
        )

    def to_candidate_facts(self, candidate: EventCandidate) -> list[dict[str, Any]]:
        """Suggested fact payloads for the reporting core; all unverified."""

        facts: list[dict[str, Any]] = []
        if candidate.extracted_attendees is not None:
            facts.append(
                {
                    "metric": "attendees",
                    "value": candidate.extracted_attendees,
                    "value_kind": FactValueKind.REPORTED_BY_UNIT.value,
                    "source": ValueSource.EITAA.value,
                    "evidence_refs": list(candidate.source_message_refs),
                    "note": "auto-extracted from Eitaa message; requires human review",
                }
            )
        return facts
