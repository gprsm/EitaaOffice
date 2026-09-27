"""Mandate layer and approved program plans (F-075 / design doc §3, §10).

The chain is: ابلاغ (mandate) ← بخش (section) ← طرح (campaign) ← رویداد ←
فکت/مدرک. A mandate is a first-class entity (circulars, correspondences,
laws, policies) that sections and events can reference. A PlanItem is one
row of the approved annual plan (the فرم بومی pattern): a sub-program with a
strategy, a type (central-mandated / provincial-native / innovative) and
numeric targets per scope. Realization = conditional events ÷ target.

Plan targets follow the فرم بومی ۱۴۰۵ prayer sheet. Rows the source form
merged (ردیف ۲: جماعت + تجهیز نمازخانه + تامین ائمه جماعات) are encoded with
``needs_confirmation=True`` so the operator splits or confirms them — the
system never hardcodes an unverifiable split as truth.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Sequence

from .model import ReportedEvent

PLAN_PERIOD_DEFAULT = "1405"

PLAN_TYPES = frozenset({"central_mandated", "provincial_native", "innovative"})
TARGET_SCOPES = frozenset({"provincial_hq", "judicial_domains"})


@dataclass(slots=True)
class Mandate:
    mandate_id: str
    kind: str  # circular | correspondence | law | policy | transformation_doc
    title: str
    number: str = ""
    issued_on: str = ""  # jalali date as printed on the document, e.g. "۱۵/۱/۱۴۰۰"
    document_ref: str = ""
    notes: str = ""

    def validate(self) -> None:
        if not self.mandate_id.strip() or not self.title.strip():
            raise ValueError("Mandate id and title cannot be empty.")
        if self.kind not in {"circular", "correspondence", "law", "policy", "transformation_doc"}:
            raise ValueError(f"Unknown mandate kind: {self.kind!r}")


@dataclass(slots=True)
class PlanItem:
    """One approved sub-program with numeric targets per scope."""

    plan_id: str
    period: str = PLAN_PERIOD_DEFAULT
    section: str = "prayer"
    strategy: str = ""
    title: str = ""
    plan_type: str = "central_mandated"
    targets: Mapping[str, float] = field(default_factory=dict)  # scope → count
    campaign_tag: str = ""  # links events to this item (طرح dimension)
    mandate_ids: tuple[str, ...] = ()
    needs_confirmation: bool = False
    notes: str = ""

    def validate(self) -> None:
        if not self.plan_id.strip() or not self.title.strip():
            raise ValueError("Plan id and title cannot be empty.")
        if self.plan_type not in PLAN_TYPES:
            raise ValueError(f"Unknown plan type: {self.plan_type!r}")
        if set(self.targets) - TARGET_SCOPES:
            raise ValueError(f"Unknown target scopes: {sorted(set(self.targets) - TARGET_SCOPES)}")
        for scope, value in self.targets.items():
            if value < 0:
                raise ValueError(f"Target for {scope!r} cannot be negative.")

    def target_for(self, scope: str) -> float:
        return float(self.targets.get(scope, 0.0))


# ---------------------------------------------------------------------------
# فرم بومی ۱۴۰۵ — programs of the prayer section (three strategies, eleven
# items). Values transcribed from the source form; the merged second row is
# flagged for operator confirmation instead of being guessed.
# ---------------------------------------------------------------------------

PRAYER_PLAN_1405: tuple[PlanItem, ...] = (
    PlanItem(
        plan_id="prayer-1405-council",
        strategy="مدیریتی - تمهیدی",
        title="تشکیل شورای اقامه نماز و برگزاری جلسات",
        plan_type="central_mandated",
        targets={"provincial_hq": 4, "judicial_domains": 16},
        campaign_tag="شورای اقامه نماز",
        mandate_ids=("mnd-staff-agreement-1405",),
    ),
    PlanItem(
        plan_id="prayer-1405-jammat",
        strategy="مدیریتی - تمهیدی",
        title="اقامه نماز جماعت",
        plan_type="central_mandated",
        targets={"provincial_hq": 11, "judicial_domains": 11},
        campaign_tag="اقامه نماز جماعت",
        needs_confirmation=True,
        notes="ردیف ۲ فرم بومی ترکیبی است (جماعت + تجهیز نمازخانه + تامین ائمه جماعات با ۱۵/۱۵ شهرستانی)؛ تفکیک دقیق با تأیید انسانی بسته می‌شود.",
        mandate_ids=("mnd-staff-agreement-1405",),
    ),
    PlanItem(
        plan_id="prayer-1405-venue-imams",
        strategy="مدیریتی - تمهیدی",
        title="تامین و تجهیز نمازخانه و تامین ائمه جماعات",
        plan_type="central_mandated",
        targets={"provincial_hq": 11, "judicial_domains": 15},
        campaign_tag="تجهیز نمازخانه",
        needs_confirmation=True,
        notes="همان ردیف ترکیبی ردیف ۲ فرم بومی؛ تا تأیید انسانی مقادیر تقریبی‌اند.",
        mandate_ids=("mnd-staff-agreement-1405",),
    ),
    PlanItem(
        plan_id="prayer-1405-bumi-announcement",
        strategy="مدیریتی - تمهیدی",
        title="ابلاغ طرح بومی سازی",
        plan_type="central_mandated",
        targets={"provincial_hq": 1, "judicial_domains": 0},
        campaign_tag="طرح بومی سازی",
        mandate_ids=("mnd-staff-agreement-1405",),
    ),
    PlanItem(
        plan_id="prayer-1405-honoring",
        strategy="مدیریتی - تمهیدی",
        title="تقدیر و تجلیل (واحد نمونه، فعال و خادم، ایده و تجارب)",
        plan_type="central_mandated",
        targets={"provincial_hq": 8, "judicial_domains": 4},
        campaign_tag="تقدیر و تجلیل نماز",
        mandate_ids=("mnd-staff-agreement-1405",),
    ),
    PlanItem(
        plan_id="prayer-1405-monitoring",
        strategy="آموزشی - پژوهشی",
        title="نظارت، گزارشگیری و ارزیابی عملکرد",
        plan_type="central_mandated",
        targets={"provincial_hq": 5, "judicial_domains": 8},
        campaign_tag="نظارت و ارزیابی نماز",
        mandate_ids=("mnd-staff-agreement-1405",),
    ),
    PlanItem(
        plan_id="prayer-1405-course-asrar",
        strategy="آموزشی - پژوهشی",
        title="دوره آموزشی اسرار و احکام نماز",
        plan_type="central_mandated",
        targets={"provincial_hq": 1, "judicial_domains": 0},
        campaign_tag="دوره اسرار و احکام نماز",
        mandate_ids=("mnd-staff-agreement-1405",),
    ),
    PlanItem(
        plan_id="prayer-1405-course-culture",
        strategy="آموزشی - پژوهشی",
        title="دوره آموزشی فرهنگ اقامه نماز",
        plan_type="central_mandated",
        targets={"provincial_hq": 1, "judicial_domains": 0},
        campaign_tag="دوره فرهنگ اقامه نماز",
        mandate_ids=("mnd-staff-agreement-1405",),
    ),
    PlanItem(
        plan_id="prayer-1405-course-family",
        strategy="آموزشی - پژوهشی",
        title="پیگیری تصویب دوره آموزشی خانواده منتظر",
        plan_type="central_mandated",
        targets={"provincial_hq": 0, "judicial_domains": 0},
        campaign_tag="دوره خانواده منتظر",
        mandate_ids=("mnd-staff-agreement-1405",),
    ),
    PlanItem(
        plan_id="prayer-1405-contest",
        strategy="تبلیغی - ترویجی",
        title="مسابقات نماز و مهدویت",
        plan_type="central_mandated",
        targets={"provincial_hq": 1, "judicial_domains": 0},
        campaign_tag="مسابقات نماز و مهدویت",
        mandate_ids=("mnd-staff-agreement-1405",),
    ),
    PlanItem(
        plan_id="prayer-1405-rooyesh",
        strategy="تبلیغی - ترویجی",
        title="رویش جوانه ها (جشن تکلیف)",
        plan_type="central_mandated",
        targets={"provincial_hq": 1, "judicial_domains": 0},
        campaign_tag="رویش جوانه ها",
        mandate_ids=("mnd-staff-agreement-1405",),
    ),
    PlanItem(
        plan_id="prayer-1405-cyberspace",
        strategy="تبلیغی - ترویجی",
        title="استفاده از بسترهای فضای مجازی",
        plan_type="central_mandated",
        targets={"provincial_hq": 1, "judicial_domains": 4},
        campaign_tag="فضای مجازی نماز",
        mandate_ids=("mnd-staff-agreement-1405",),
    ),
)

PRAYER_MANDATE_1405 = Mandate(
    mandate_id="mnd-staff-agreement-1405",
    kind="circular",
    title="توافق مشترک اداره کل و ستاد اقامه نماز استان — برنامه‌های بومی ۱۴۰۵ ترویج و توسعه فرهنگ اقامه نماز",
    number="",
    issued_on="1405",
    notes="مبنا: مفاد آیین‌نامه ترویج فرهنگ نماز (هیئت وزیران) و بخشنامه ۱۱۱۷۱۷/۰۱/۱ مورخ ۱۵/۱/۱۴۰۰ طرح بومی‌سازی؛ طبق نکتهٔ ۲ فرم، شاخص‌های نظارت تابع شاخص‌های مصوب دستگاه مرکزی است.",
)

PRAYER_PLAN_ITEM_INDEX: dict[str, PlanItem] = {item.plan_id: item for item in PRAYER_PLAN_1405}


def campaign_events(events: Sequence[ReportedEvent], campaign_tag: str, *, period: str = PLAN_PERIOD_DEFAULT) -> list[ReportedEvent]:
    """Events tagged with a campaign (the ``ReportedEvent.campaign`` dimension).

    A single event may serve several campaigns; tags are ``|``-separated.
    Period slicing is the caller's concern (store queries filter by year).
    """
    return [e for e in events if campaign_tag and campaign_tag in _campaign_tags(e)]


def _campaign_tags(event: ReportedEvent) -> tuple[str, ...]:
    campaign = getattr(event, "campaign", "") or ""
    tags = [t.strip() for t in campaign.split("|") if t.strip()]
    return tuple(tags)


def realization_ratio(
    item: PlanItem,
    events: Sequence[ReportedEvent],
    *,
    scope: str = "provincial_hq",
) -> dict[str, float]:
    """تحقق = conditional events tagged with the campaign ÷ approved target."""
    item.validate()
    done = len(campaign_events(events, item.campaign_tag))
    target = item.target_for(scope)
    ratio = (done / target) if target else 0.0
    return {"done": float(done), "target": target, "ratio": round(min(ratio, 1.0), 4) if target else 0.0}


def realization_report(
    items: Sequence[PlanItem],
    events: Sequence[ReportedEvent],
    *,
    scope: str = "provincial_hq",
) -> list[dict[str, object]]:
    """Per-item realization with gap and confirmation flags for the dossier."""
    report: list[dict[str, object]] = []
    for item in items:
        stats = realization_ratio(item, events, scope=scope)
        report.append(
            {
                "plan_id": item.plan_id,
                "title": item.title,
                "strategy": item.strategy,
                "plan_type": item.plan_type,
                "campaign_tag": item.campaign_tag,
                "done": stats["done"],
                "target": stats["target"],
                "ratio": stats["ratio"],
                "needs_confirmation": item.needs_confirmation,
                "gap": float(max(stats["target"] - stats["done"], 0.0)),
            }
        )
    return report
