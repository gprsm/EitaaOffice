"""WordPress post ↔ event link layer (F-088 §2, the missing WP connection).

Each exported WordPress post is one real-world event bundle: ``post.html``
plus featured and content images. This module parses those bundles,
classifies them into an office section by keyword, and keeps the link to the
imported ``ReportedEvent``. Matching is deliberately conservative: a post is
linked to an event only when the operator confirms it or the auto-match ran
with full evidence; everything else stays ``candidate``/``unmatched``.

Paths stored here are corpus-relative evidence references (never absolute
machine paths) so they remain meaningful without leaking the local layout.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
import html as html_module
import re
from pathlib import Path

WP_MATCH_STATUSES = frozenset({"unmatched", "auto", "candidate", "confirmed"})


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(slots=True)
class WpPostLink:
    """A WordPress post and its link state to the event corpus."""

    link_id: str
    post_slug: str = ""
    title: str = ""
    source_ref: str = ""  # corpus-relative path, e.g. "report-corpus:new/.../post.html"
    section: str = ""  # office section id (sections.py)
    published_on: date | None = None
    event_id: str = ""  # empty until linked to a ReportedEvent
    match_status: str = "unmatched"
    confidence: float = 0.0
    note: str = ""
    created_at: datetime = field(default_factory=_utc_now)

    def validate(self) -> None:
        # link_id may be empty here: the store assigns one on insert.
        if self.match_status not in WP_MATCH_STATUSES:
            raise ValueError(f"Unknown match status: {self.match_status!r}")


# ---------------------------------------------------------------------------
# Section classification by keyword — mirrors the indexer's program keyword
# tuples and adds the visit-worksheet-only topics (F-088 §4).
# ---------------------------------------------------------------------------

SECTION_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "prayer",
        ("نماز", "جماعت", "تکلیف", "نمازخانه", "اقامه نماز", "ستاد اقامه نماز",
         "خادمین نماز", "بین الصلاتین", "بین‌الصلاتین", "نومکلف", "رویش جوانه"),
    ),
    (
        "trip",
        ("اردو", "زیارتی", "کربلا", "مشهد مقدس", "عتبات", "سفر زیارتی"),
    ),
    (
        "contest",
        ("مسابقه", "مسابقات", "قرآن و عترت", "داوری", "برندگان", "فوتسال", "واليبال"),
    ),
    (
        "ceremonies",
        ("مراسم", "جشن", "جشنواره", "گرامیداشت", "گرامیداشت", "بزرگداشت", "ختم",
         "سالگرد", "غبارروبی", "غبار روبی", "محرم", "صفر", "فاطمیه", "فاتحیه",
         "دهه فجر", "خبر شهید", "اربعین", "اسکان", "زائران", "موبل", "موكب",
         "میز خدمت", "میزخدمت", "فضاسازی", "هفته قوه", "رهبر شهید", "شهدای دادگستری"),
    ),
    (
        "honor",
        ("تقدیر", "تجلیل", "تکریم", "کارمند نمونه", "بازنشست", "مفاخر", "پیشکسوت"),
    ),
    (
        "customer_care",
        ("ارباب رجوع", "رضایت ارباب", "تسریع در امور"),
    ),
    (
        "charter",
        ("منشور", "اخلاق حرفه", "کارگاه اخلاق", "توانمندسازی اخلاق"),
    ),
    (
        "training_courses",
        ("دوره آموزشی", "کارگاه آموزشی", "جهاد تبیین", "نشست آموزشی", "همایش آموزشی",
         "خانواده مهدوی", "رابطین فرهنگی", "روابط فرهنگی"),
    ),
    (
        "content_production",
        ("تیزر", "موشن گرافی", "موشن‌گرافی", "فیلم کوتاه", "کلیپ", "نماهنگ",
         "پوستر", "طراحی پوستر", "پیامک"),
    ),
    (
        "counseling",
        ("مشاوره", "ازدواج مجردین", "مشاور تحصیلی"),
    ),
    (
        "education_services",
        ("استعدادیابی", "رتبه های برتر", "رتبه‌های برتر", "فرزندان برتر", "خدمات تحصیلی"),
    ),
    (
        "external_collaboration",
        ("صداوسیما", "رادیو", "تلویزیون", "ارشاد", "اوقاف", "تبلیغات اسلامی",
         "کتابخانه", "حوزه علمیه", "برون سازمانی"),
    ),
)


def classify_section(title: str, body: str = "") -> tuple[str, float]:
    """Keyword classification of a post into an office section.

    Returns ``(section_id, confidence)``; confidence reflects how many
    distinct keywords matched (capped at 0.95 — machine classification is
    never certain, the operator can confirm).
    """
    text = f"{title} {body}"
    best_section, best_hits = "", 0
    for section_id, keywords in SECTION_KEYWORDS:
        hits = sum(1 for kw in keywords if kw in text)
        if hits > best_hits:
            best_section, best_hits = section_id, hits
    if not best_hits:
        return ("", 0.0)
    confidence = min(0.6 + 0.15 * (best_hits - 1), 0.95)
    return (best_section, round(confidence, 2))


# ---------------------------------------------------------------------------
# post.html parsing — the export bundles are static WordPress renderings.
# ---------------------------------------------------------------------------

_DATE_PATTERNS = (
    # 1405/03/25, ۱۴۰۵/۰۳/۲۵ (ASCII and Persian digits, / or -)
    re.compile(r"[01۴۰۱۲۳۴۵۶۷۸۹/:-]{0,1}[0-9۰-۹]{4}[/\-.][0-9۰-۹]{1,2}[/\-.][0-9۰-۹]{1,2}"),
)

_PERSIAN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")


def parse_post_bundle(path: Path) -> dict[str, str]:
    """Extract title, text body and image count from an exported post bundle.

    Returns keys: ``title``, ``body`` (flattened text, trimmed), ``slug``
    (parent directory name). Never raises on malformed HTML — returns what
    it could read.
    """
    result = {"title": "", "body": "", "slug": path.parent.name}
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return result
    title_match = re.search(r"<title>(.*?)</title>", raw, re.S) or re.search(
        r"<h1[^>]*>(.*?)</h1>", raw, re.S
    )
    if title_match:
        result["title"] = html_module.unescape(re.sub(r"<[^>]+>", " ", title_match.group(1))).strip()
    body_text = re.sub(r"<script.*?</script>|<style.*?</style>", " ", raw, flags=re.S)
    body_text = re.sub(r"<[^>]+>", " ", body_text)
    body_text = html_module.unescape(body_text)
    body_text = re.sub(r"\s+", " ", body_text).strip()
    result["body"] = body_text[:4000]
    return result


def extract_jalali_date(text: str) -> date | None:
    """Best-effort jalali date extraction (1405/xx/xx shapes) → gregorian date.

    Uses a fixed jalali→gregorian conversion for 1404–1406 without external
    dependencies. Returns None when no plausible date is found.
    """
    if not text:
        return None
    match = _DATE_PATTERNS[0].search(text)
    if not match:
        return None
    digits = match.group(0).translate(_PERSIAN_DIGITS)
    numbers = re.findall(r"\d+", digits)
    if len(numbers) < 3:
        return None
    try:
        year, month, day = (int(n) for n in numbers[:3])
    except ValueError:  # pragma: no cover - regex guards this
        return None
    if not (1403 <= year <= 1407 and 1 <= month <= 12 and 1 <= day <= 31):
        return None
    return jalali_to_gregorian(year, month, day)


def jalali_to_gregorian(jy: int, jm: int, jd: int) -> date:
    """Standard jalaali→gregorian conversion (jalaali algorithm, 1300-1500)."""
    jy += 1595
    days = -355668 + (365 * jy) + ((jy // 33) * 8) + (((jy % 33) + 3) // 4) + jd
    if jm < 7:
        days += (jm - 1) * 31
    else:
        days += ((jm - 7) * 30) + 186
    gy = 400 * (days // 146097)
    days %= 146097
    if days > 36524:
        days -= 1
        gy += 100 * (days // 36524)
        days %= 36524
        if days >= 365:
            days += 1
    gy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        gy += (days - 1) // 365
        days = (days - 1) % 365
    gd = days + 1
    leap = (gy % 4 == 0 and gy % 100 != 0) or (gy % 400 == 0)
    month_lengths = [31, 29 if leap else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    gm = 1
    for length in month_lengths:
        if gd <= length:
            break
        gd -= length
        gm += 1
    return date(gy, gm, gd)
