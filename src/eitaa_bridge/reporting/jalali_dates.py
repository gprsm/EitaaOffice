"""Jalali (Solar Hijri) calendar utilities and conversion algorithms.

Deterministic, zero-dependency mathematical algorithms for Persian Solar Hijri
calendar conversions, leap year calculations, and bidirectional string formatting.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

JALALI_MONTH_NAMES = (
    "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
    "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند",
)

PERSIAN_DIGITS = "۰۱۲۳۴۵۶۷۸۹"
ARABIC_DIGITS = "٠١٢٣٤٥٦٧٨٩"


def to_latin_digits(s: str) -> str:
    """Convert Persian and Arabic numerals to Latin ASCII digits."""
    if not s:
        return ""
    trans = str.maketrans(
        "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
        "01234567890123456789",
    )
    return str(s).translate(trans)


def _div(a: int, b: int) -> int:
    return int(a / b)


def _mod(a: int, b: int) -> int:
    return a - int(a / b) * b


def _jal_cal(jy: int) -> tuple[int, int, int]:
    breaks = (
        -61, 9, 38, 199, 426, 686, 756, 818, 1111, 1181, 1210,
        1635, 2060, 2097, 2192, 2262, 2324, 2394, 2456, 3178,
    )
    gy = jy + 621
    leap_j = -14
    jp = breaks[0]
    jump = 0
    for i in range(1, len(breaks)):
        jm = breaks[i]
        jump = jm - jp
        if jy < jm:
            break
        leap_j += _div(jump, 33) * 8 + _div(_mod(jump, 33), 4)
        jp = jm
    n = jy - jp
    leap_j += _div(n, 33) * 8 + _div(_mod(n, 33) + 3, 4)
    if _mod(jump, 33) == 4 and jump - n == 4:
        leap_j += 1
    leap_g = _div(gy, 4) - _div((_div(gy, 100) + 1) * 3, 4) - 150
    march = 20 + leap_j - leap_g
    leap = _mod(_mod(n + 1, 33) - 1, 4)
    if leap == -1:
        leap = 4
    return leap, gy, march


def _g2d(gy: int, gm: int, gd: int) -> int:
    d = _div((gy + _div(gm - 8, 6) + 100100) * 1461, 4)
    d += _div(153 * _mod(gm + 9, 12) + 2, 5) + gd - 34840408
    d = d - _div(_div(gy + 100100 + _div(gm - 8, 6), 100) * 3, 4) + 752
    return d


def _d2g(jdn: int) -> tuple[int, int, int]:
    j = 4 * jdn + 139361631
    j += _div(_div(4 * jdn + 183187720, 146097) * 3, 4) * 4 - 3908
    i = _div(_mod(j, 1461), 4) * 5 + 308
    gd = _div(_mod(i, 153), 5) + 1
    gm = _mod(_div(i, 153), 12) + 1
    gy = _div(j, 1461) - 100100 + _div(8 - gm, 6)
    return gy, gm, gd


def _j2d(jy: int, jm: int, jd: int) -> int:
    _, gy, march = _jal_cal(jy)
    return _g2d(gy, 3, march) + (jm - 1) * 31 - _div(jm, 7) * (jm - 7) + jd - 1


def _d2j(jdn: int) -> tuple[int, int, int]:
    gy, _, _ = _d2g(jdn)
    jy = gy - 621
    _, _, march = _jal_cal(jy)
    jdn1f = _g2d(gy, 3, march)
    k = jdn - jdn1f
    if k >= 0:
        if k <= 185:
            return jy, 1 + _div(k, 31), 1 + _mod(k, 31)
        k -= 186
    else:
        jy -= 1
        _, _, march = _jal_cal(jy)
        jdn1f = _g2d(gy, 3, march)
        k = jdn - jdn1f - 186
    return jy, 7 + _div(k, 30), 1 + _mod(k, 30)


def jalali_to_gregorian(jy: int, jm: int, jd: int) -> tuple[int, int, int]:
    """Convert Jalali (year, month, day) to Gregorian (year, month, day)."""
    return _d2g(_j2d(jy, jm, jd))


def gregorian_to_jalali(gy: int, gm: int, gd: int) -> tuple[int, int, int]:
    """Convert Gregorian (year, month, day) to Jalali (year, month, day)."""
    return _d2j(_g2d(gy, gm, gd))


def is_jalali_leap(jy: int) -> bool:
    """Return True if Jalali year is a leap year (366 days)."""
    leap, _, _ = _jal_cal(jy)
    return leap == 0


def jalali_month_length(jy: int, jm: int) -> int:
    """Return number of days in the specified Jalali year and month."""
    if jm <= 6:
        return 31
    if jm <= 11:
        return 30
    return 30 if is_jalali_leap(jy) else 29


def normalize_to_iso_date(val: Any) -> str:
    """Normalize input date to ISO Gregorian string YYYY-MM-DD.

    Accepts:
    - ISO strings: "2026-10-19", "2026-10-19T10:00:00"
    - Jalali strings: "1405/07/27", "1405-07-27", "1405/07/28"
    - datetime.date or datetime.datetime objects
    """
    if not val:
        return date.today().isoformat()
    if isinstance(val, (date, datetime)):
        return val.strftime("%Y-%m-%d")

    s = to_latin_digits(str(val)).strip()
    if not s:
        return date.today().isoformat()

    # Strip time if present
    if " " in s:
        s = s.split(" ")[0].strip()
    if "T" in s:
        s = s.split("T")[0].strip()

    s = s.replace("/", "-")
    parts = s.split("-")
    if len(parts) == 3:
        try:
            y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
            if y < 1600:
                # Solar Hijri / Jalali
                gy, gm, gd = jalali_to_gregorian(y, m, d)
                return f"{gy:04d}-{gm:02d}-{gd:02d}"
            # Gregorian
            return f"{y:04d}-{m:02d}-{d:02d}"
        except Exception:
            pass

    try:
        return date.fromisoformat(s).isoformat()
    except Exception:
        return date.today().isoformat()


def format_to_jalali_date(val: Any, separator: str = "/") -> str:
    """Convert input date (ISO string or date object) to standard Jalali YYYY/MM/DD."""
    if not val:
        val = date.today()
    if isinstance(val, (date, datetime)):
        jy, jm, jd = gregorian_to_jalali(val.year, val.month, val.day)
        return f"{jy:04d}{separator}{jm:02d}{separator}{jd:02d}"

    s = to_latin_digits(str(val)).strip()
    if not s:
        val = date.today()
        jy, jm, jd = gregorian_to_jalali(val.year, val.month, val.day)
        return f"{jy:04d}{separator}{jm:02d}{separator}{jd:02d}"

    if " " in s:
        s = s.split(" ")[0].strip()
    if "T" in s:
        s = s.split("T")[0].strip()

    s = s.replace("/", "-")
    parts = s.split("-")
    if len(parts) == 3:
        try:
            y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
            if y >= 1600:
                jy, jm, jd = gregorian_to_jalali(y, m, d)
                return f"{jy:04d}{separator}{jm:02d}{separator}{jd:02d}"
            return f"{y:04d}{separator}{m:02d}{separator}{d:02d}"
        except Exception:
            pass

    try:
        d_obj = date.fromisoformat(s)
        jy, jm, jd = gregorian_to_jalali(d_obj.year, d_obj.month, d_obj.day)
        return f"{jy:04d}{separator}{jm:02d}{separator}{jd:02d}"
    except Exception:
        today = date.today()
        jy, jm, jd = gregorian_to_jalali(today.year, today.month, today.day)
        return f"{jy:04d}{separator}{jm:02d}{separator}{jd:02d}"
