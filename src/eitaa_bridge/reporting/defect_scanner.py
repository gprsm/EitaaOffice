"""Automated defect scanning & quality gate engine for reporting workflow.

Detects rule violations, missing evidence, unverified metrics, and procedural
omissions (e.g. Rule 23 judiciary attribution, missing attendees, invalid dates)
before manager approval and export.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Sequence

from .model import ProgramKind, ReportedEvent, UnitScope


@dataclass(slots=True, frozen=True)
class DefectItem:
    defect_code: str
    severity: str  # "blocker" | "warning" | "info"
    title: str
    description: str
    field_name: str

    def to_dict(self) -> dict[str, str]:
        return {
            "defect_code": self.defect_code,
            "severity": self.severity,
            "title": self.title,
            "description": self.description,
            "field_name": self.field_name,
        }


def scan_event_defects(
    event: ReportedEvent,
    *,
    witnesses_count: int = 0,
    documents_count: int = 0,
) -> list[DefectItem]:
    """Scan an event and return all identified defects and quality warnings."""
    defects: list[DefectItem] = []

    # Rule 1: Missing Attendees for collective programs
    collective_kinds = {
        ProgramKind.CEREMONY,
        ProgramKind.CONTEST,
        ProgramKind.QURAN_CONTEST,
        ProgramKind.TRIP,
        ProgramKind.PRAYER,
        ProgramKind.TRAINING_COURSE,
    }
    is_collective = any(k in collective_kinds for k in event.program_kinds)
    attendee_facts = [f for f in event.facts if f.metric == "attendees"]
    total_attendees = sum(f.value for f in attendee_facts) if attendee_facts else 0.0

    if is_collective and total_attendees <= 0:
        defects.append(
            DefectItem(
                defect_code="missing_attendees",
                severity="warning" if ProgramKind.PRAYER in event.program_kinds else "blocker",
                title="عدم ثبت آمار مخاطبان",
                description="برای برنامه‌های جمعی، مسابقات و مراسم‌ها، ثبت تعداد شرکت‌کنندگان الزامی است.",
                field_name="attendee_count",
            )
        )

    # Rule 2: Date validity (not future, reasonable past)
    today = date.today()
    if event.occurred_on > today:
        defects.append(
            DefectItem(
                defect_code="future_event_date",
                severity="blocker",
                title="تاریخ وقوع در آینده",
                description=f"تاریخ وقوع ({event.occurred_on.isoformat()}) نمی‌تواند جلوتر از امروز باشد.",
                field_name="occurred_on",
            )
        )
    elif (today - event.occurred_on).days > 400:
        defects.append(
            DefectItem(
                defect_code="outdated_event_date",
                severity="warning",
                title="تاریخ وقوع قدیمی",
                description="تاریخ وقوع بیش از یک سال گذشته است و نیازمند بررسی تطبیق سال مالی است.",
                field_name="occurred_on",
            )
        )

    # Rule 3: Missing Witness/Evidence
    facts_with_evidence = any(bool(f.evidence_refs) for f in event.facts)
    has_evidence = (witnesses_count > 0) or bool(event.evidence) or facts_with_evidence or (documents_count > 0)
    if not has_evidence:
        defects.append(
            DefectItem(
                defect_code="missing_witness",
                severity="blocker",
                title="عدم پیوند به شاهد یا مستند رسمی",
                description="رویداد فاقد هرگونه پیوند به پیام مستند یا فایل پیوست است.",
                field_name="witnesses",
            )
        )

    # Rule 4: Ambiguous Judiciary Hosting (Rule 23)
    judiciary_keywords = ("دادگستری", "قضایی", "شعبه", "شورای حل اختلاف", "دادگاه", "دادسرا", "قوه قضائیه")
    text_corpus = f"{event.unit_name} {event.occasion} {event.notes}"
    has_judiciary_mention = any(kw in text_corpus for kw in judiciary_keywords)
    if (
        event.unit in (UnitScope.PROVINCIAL_HQ, UnitScope.JUDICIAL_DOMAIN)
        and not event.unit_name.strip()
        and not has_judiciary_mention
    ):
        defects.append(
            DefectItem(
                defect_code="ambiguous_judiciary_hosting",
                severity="warning",
                title="عدم تصریح عنوان واحد قضایی میزبان (ماده ۲۳)",
                description="برای ثبت رویداد، نام حوزه قضایی یا ستاد برگزارکننده باید مشخص گردد.",
                field_name="unit_name",
            )
        )

    # Rule 5: Standalone titled event without occasion
    if event.is_standalone_titled and not event.occasion.strip():
        defects.append(
            DefectItem(
                defect_code="missing_occasion",
                severity="warning",
                title="رویداد دارای عنوان مستقل فاقد مناسبت",
                description="رویدادهای دارای عنوان مستقل باید مناسبت مربوطه (ملی/مذهبی/انقلابی) را مشخص کنند.",
                field_name="occasion",
            )
        )

    # Rule 6: Missing media/documents (Info)
    if documents_count == 0 and not event.evidence:
        defects.append(
            DefectItem(
                defect_code="missing_media_attachment",
                severity="info",
                title="نبود تصویر یا پیوست مستند",
                description="افزودن تصویر یا پوستر برنامه به پرونده جهت اعتباربخشی گزارش پیشنهاد می‌شود.",
                field_name="documents",
            )
        )

    # Rule 7: Missing official presence for honor / customer care (Rule B9 / C8)
    if any(k in (ProgramKind.HONOR, ProgramKind.CUSTOMER_CARE) for k in event.program_kinds):
        if event.official_present is not True:
            defects.append(
                DefectItem(
                    defect_code="unconfirmed_official_presence",
                    severity="warning",
                    title="عدم تأیید حضور مقام قضایی / رئیس‌کل (قاعده B9/C8)",
                    description="مطابق کاربرگ تکریم و تجلیل و تشویق ارباب رجوع، احراز حضور رئیس‌کل یا مقام قضایی استان جهت شمارش آماری در کاربرگ الزامی است.",
                    field_name="official_present",
                )
            )

    return defects
