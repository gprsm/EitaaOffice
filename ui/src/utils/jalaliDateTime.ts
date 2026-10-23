/**
 * Robust Jalali (Persian Solar Hijri) date & time utilities.
 * 
 * Solves browser/Intl locale discrepancies (e.g. "07/24/1405 AP") by strictly
 * extracting numeric parts and formatting as standardized ISO-like Jalali strings:
 * - Date: YYYY/MM/DD
 * - Time: HH:mm
 * - DateTime: YYYY/MM/DD HH:mm
 */

export const JALALI_MONTH_NAMES = [
  'فروردین', 'اردیبهشت', 'خرداد', 'تیر', 'مرداد', 'شهریور',
  'مهر', 'آبان', 'آذر', 'دی', 'بهمن', 'اسفند'
]

export const JALALI_WEEKDAYS_SHORT = ['ش', 'ی', 'د', 'س', 'چ', 'پ', 'ج']
export const JALALI_WEEKDAYS_LONG = [
  'شنبه', 'یک‌شنبه', 'دوشنبه', 'سه‌شنبه', 'چهارشنبه', 'پنج‌شنبه', 'جمعه'
]

const PERSIAN_DIGITS = ['۰', '۱', '۲', '۳', '۴', '۵', '۶', '۷', '۸', '۹']
const ARABIC_DIGITS = ['٠', '١', '٢', '٣', '٤', '٥', '٦', '٧', '٨', '٩']

export function toLatinDigits(str: string): string {
  if (!str) return ''
  return str
    .replace(/[۰-۹]/g, c => String(PERSIAN_DIGITS.indexOf(c)))
    .replace(/[٠-٩]/g, c => String(ARABIC_DIGITS.indexOf(c)))
}

export function toPersianDigits(num: number | string): string {
  return String(num).replace(/[0-9]/g, c => PERSIAN_DIGITS[Number(c)])
}

/**
 * Extract Jalali date parts accurately from any Date using formatToParts.
 */
export function jalaliParts(value: Date | string | number = new Date()): {
  year: number
  month: number
  day: number
  hour: number
  minute: number
  second: number
  dayOfWeek: number
} {
  const dateObj = value instanceof Date ? value : new Date(value)
  if (Number.isNaN(dateObj.getTime())) {
    const fallback = new Date()
    return jalaliParts(fallback)
  }

  const formatter = new Intl.DateTimeFormat('en-US-u-ca-persian', {
    year: 'numeric',
    month: 'numeric',
    day: 'numeric',
    hour: 'numeric',
    minute: 'numeric',
    second: 'numeric',
    hour12: false,
  })

  const parts = formatter.formatToParts(dateObj)
  const getPart = (type: string) => {
    const found = parts.find(p => p.type === type)
    return found ? Number(found.value) : 0
  }

  // getDay(): 0 is Sunday, 6 is Saturday.
  // Persian week starts on Saturday (index 0).
  const gregorianDay = dateObj.getDay()
  const jalaliDayOfWeek = (gregorianDay + 1) % 7

  return {
    year: getPart('year'),
    month: getPart('month'),
    day: getPart('day'),
    hour: dateObj.getHours(),
    minute: dateObj.getMinutes(),
    second: dateObj.getSeconds(),
    dayOfWeek: jalaliDayOfWeek,
  }
}

/**
 * Returns strictly YYYY/MM/DD (e.g. 1405/07/24).
 * Completely avoids US-style "07/24/1405 AP".
 */
export function formatJalaliDate(value: Date | string | number): string {
  const p = jalaliParts(value)
  const y = String(p.year).padStart(4, '0')
  const m = String(p.month).padStart(2, '0')
  const d = String(p.day).padStart(2, '0')
  return `${y}/${m}/${d}`
}

/**
 * Alias for formatJalaliDate, ensuring system-wide compatibility with existing code.
 */
export function jalaliDayKey(value: Date | string | number): string {
  return formatJalaliDate(value)
}

/**
 * Returns strictly HH:mm (e.g. 17:20).
 */
export function formatJalaliTime(value: Date | string | number): string {
  const dateObj = value instanceof Date ? value : new Date(value)
  if (Number.isNaN(dateObj.getTime())) return '00:00'
  const hh = String(dateObj.getHours()).padStart(2, '0')
  const mm = String(dateObj.getMinutes()).padStart(2, '0')
  return `${hh}:${mm}`
}

/**
 * Returns strictly YYYY/MM/DD HH:mm (e.g. 1405/07/24 17:20).
 */
export function formatJalaliDateTime(value: Date | string | number): string {
  return `${formatJalaliDate(value)} ${formatJalaliTime(value)}`
}

/**
 * Returns human-readable Persian date label, e.g. "۲۴ مهر ۱۴۰۵ · ساعت ۱۷:۲۰"
 */
export function jalaliDateTimeLabel(value: Date | string | number): string {
  const p = jalaliParts(value)
  const monthName = JALALI_MONTH_NAMES[p.month - 1] || ''
  const weekdayName = JALALI_WEEKDAYS_LONG[p.dayOfWeek] || ''
  const timeStr = formatJalaliTime(value)
  return `${weekdayName}، ${p.day} ${monthName} ${p.year} · ساعت ${timeStr}`
}

/**
 * Returns human-readable Persian day label, e.g. "۲۴ مهر ۱۴۰۵"
 */
export function jalaliDayLabel(value: Date | string | number): string {
  const p = jalaliParts(value)
  const monthName = JALALI_MONTH_NAMES[p.month - 1] || ''
  return `${p.day} ${monthName} ${p.year}`
}

/**
 * Mathematical conversion algorithms from Jalali to Gregorian.
 */
const div = (a: number, b: number) => Math.trunc(a / b)
const mod = (a: number, b: number) => a - Math.trunc(a / b) * b

export function jalCal(jy: number) {
  const breaks = [-61, 9, 38, 199, 426, 686, 756, 818, 1111, 1181, 1210, 1635, 2060, 2097, 2192, 2262, 2324, 2394, 2456, 3178]
  const gy = jy + 621
  let leapJ = -14
  let jp = breaks[0]
  let jump = 0
  for (let i = 1; i < breaks.length; i += 1) {
    const jm = breaks[i]
    jump = jm - jp
    if (jy < jm) break
    leapJ += div(jump, 33) * 8 + div(mod(jump, 33), 4)
    jp = jm
  }
  const n = jy - jp
  leapJ += div(n, 33) * 8 + div(mod(n, 33) + 3, 4)
  if (mod(jump, 33) === 4 && jump - n === 4) leapJ += 1
  const leapG = div(gy, 4) - div((div(gy, 100) + 1) * 3, 4) - 150
  const march = 20 + leapJ - leapG
  let leap = mod(mod(n + 1, 33) - 1, 4)
  if (leap === -1) leap = 4
  return { leap, gy, march }
}

export function g2d(gy: number, gm: number, gd: number) {
  let d = div((gy + div(gm - 8, 6) + 100100) * 1461, 4)
  d += div(153 * mod(gm + 9, 12) + 2, 5) + gd - 34840408
  d = d - div(div(gy + 100100 + div(gm - 8, 6), 100) * 3, 4) + 752
  return d
}

export function d2g(jdn: number) {
  let j = 4 * jdn + 139361631
  j += div(div(4 * jdn + 183187720, 146097) * 3, 4) * 4 - 3908
  const i = div(mod(j, 1461), 4) * 5 + 308
  const gd = div(mod(i, 153), 5) + 1
  const gm = mod(div(i, 153), 12) + 1
  const gy = div(j, 1461) - 100100 + div(8 - gm, 6)
  return { gy, gm, gd }
}

export function j2d(jy: number, jm: number, jd: number) {
  const r = jalCal(jy)
  return g2d(r.gy, 3, r.march) + (jm - 1) * 31 - div(jm, 7) * (jm - 7) + jd - 1
}

export function d2j(jdn: number): { jy: number; jm: number; jd: number } {
  const { gy } = d2g(jdn)
  let jy = gy - 621
  let r = jalCal(jy)
  let jdn1f = g2d(gy, 3, r.march)
  let k = jdn - jdn1f
  if (k >= 0) {
    if (k <= 185) {
      return { jy, jm: 1 + div(k, 31), jd: 1 + mod(k, 31) }
    } else {
      k -= 186
    }
  } else {
    jy -= 1
    r = jalCal(jy)
    jdn1f = g2d(r.gy, 3, r.march)
    k = jdn - jdn1f - 186
  }
  return { jy, jm: 7 + div(k, 30), jd: 1 + mod(k, 30) }
}

export function gregorianToJalali(gy: number, gm: number, gd: number): { jy: number; jm: number; jd: number } {
  return d2j(g2d(gy, gm, gd))
}

export function jalaliToGregorian(jy: number, jm: number, jd: number) {
  return d2g(j2d(jy, jm, jd))
}

export function jalaliMonthLength(year: number, month: number): number {
  if (month <= 6) return 31
  if (month <= 11) return 30
  const r = jalCal(year)
  return r.leap === 0 ? 30 : 29
}

/**
 * Parses Jalali string formatted as "YYYY/MM/DD" or "YYYY-MM-DD", or ISO date into a Date.
 */
export function parseJalaliDate(value: string): Date | null {
  if (!value) return null
  const latin = toLatinDigits(value).trim()
  const match = latin.match(/^(\d{4})[\/-](\d{1,2})[\/-](\d{1,2})$/)
  if (!match) return null

  const jy = Number(match[1])
  const jm = Number(match[2])
  const jd = Number(match[3])

  // If year is > 1600, it is an ISO Gregorian date
  if (jy > 1600) {
    if (jm < 1 || jm > 12 || jd < 1 || jd > 31) return null
    return new Date(jy, jm - 1, jd, 0, 0, 0, 0)
  }

  if (jm < 1 || jm > 12 || jd < 1 || jd > 31) return null
  if (jm > 6 && jd > 30) return null
  if (jm === 12 && jd > jalaliMonthLength(jy, 12)) return null

  const g = jalaliToGregorian(jy, jm, jd)
  return new Date(g.gy, g.gm - 1, g.gd, 0, 0, 0, 0)
}

/**
 * Parses Jalali string formatted as "YYYY/MM/DD HH:mm" or "YYYY/MM/DD" into a Date.
 */
export function parseJalaliDateTime(value: string): Date | null {
  if (!value) return null
  const latin = toLatinDigits(value).trim()
  const match = latin.match(/^(\d{4})[\/-](\d{1,2})[\/-](\d{1,2})(?:[\sT]+(\d{1,2}):(\d{1,2})(?::(\d{1,2}))?)?$/)
  if (!match) return null

  const jy = Number(match[1])
  const jm = Number(match[2])
  const jd = Number(match[3])
  const hour = match[4] ? Number(match[4]) : 0
  const minute = match[5] ? Number(match[5]) : 0
  const second = match[6] ? Number(match[6]) : 0

  if (hour < 0 || hour > 23 || minute < 0 || minute > 59 || second < 0 || second > 59) return null

  // If year is > 1600, it is an ISO Gregorian date
  if (jy > 1600) {
    if (jm < 1 || jm > 12 || jd < 1 || jd > 31) return null
    return new Date(jy, jm - 1, jd, hour, minute, second, 0)
  }

  if (jm < 1 || jm > 12 || jd < 1 || jd > 31) return null
  if (jm > 6 && jd > 30) return null
  if (jm === 12 && jd > jalaliMonthLength(jy, 12)) return null

  const g = jalaliToGregorian(jy, jm, jd)
  return new Date(g.gy, g.gm - 1, g.gd, hour, minute, second, 0)
}

/**
 * Formats year, month, day into standard "YYYY/MM/DD" string.
 */
export function jalaliYmd(year: number, month: number, day: number): string {
  return `${year}/${String(month).padStart(2, '0')}/${String(day).padStart(2, '0')}`
}

/**
 * Converts any date representation (ISO date string, Date object, or Jalali string)
 * to a standardized Jalali date string "YYYY/MM/DD".
 */
export function toJalaliString(value: Date | string | number | null | undefined): string {
  if (!value) return ''
  if (value instanceof Date) {
    const j = gregorianToJalali(value.getFullYear(), value.getMonth() + 1, value.getDate())
    return jalaliYmd(j.jy, j.jm, j.jd)
  }
  const latin = toLatinDigits(String(value)).trim()
  if (!latin) return ''
  const clean = latin.split(/[\sT]/)[0].replace(/-/g, '/')
  const match = clean.match(/^(\d{4})\/(\d{1,2})\/(\d{1,2})$/)
  if (!match) return latin
  const y = Number(match[1])
  const m = Number(match[2])
  const d = Number(match[3])
  if (y > 1600) {
    const j = gregorianToJalali(y, m, d)
    return jalaliYmd(j.jy, j.jm, j.jd)
  }
  return jalaliYmd(y, m, d)
}

/**
 * Converts any date representation (Jalali string, ISO string) to standard ISO Gregorian "YYYY-MM-DD".
 */
export function toIsoDateString(value: string | null | undefined): string {
  if (!value) return ''
  const latin = toLatinDigits(String(value)).trim()
  if (!latin) return ''
  const clean = latin.split(/[\sT]/)[0].replace(/\//g, '-')
  const match = clean.match(/^(\d{4})-(\d{1,2})-(\d{1,2})$/)
  if (!match) return latin
  const y = Number(match[1])
  const m = Number(match[2])
  const d = Number(match[3])
  if (y <= 1600) {
    const g = jalaliToGregorian(y, m, d)
    return `${g.gy}-${String(g.gm).padStart(2, '0')}-${String(g.gd).padStart(2, '0')}`
  }
  return `${y}-${String(m).padStart(2, '0')}-${String(d).padStart(2, '0')}`
}

