/**
 * موتور دورهٔ زمانی شمسی (F-097): دوماهه/چهارماهه/شش‌ماهه/سال + بازهٔ سفارشی
 * مرجع واحد همهٔ نقاط گزارش‌دهی سامانه — خروجی همیشه جفت ISO میلادی + برچسب فارسی.
 */

export type Jalali = [number, number, number] // سال/ماه/روز

export interface PeriodSelection {
  /** شناسهٔ پیش‌فرض یا 'custom' */
  presetId: string
  year: number
  /** شمسی [y,m,d] */
  fromJalali: Jalali
  toJalali: Jalali
  /** برچسب فارسی کامل برای نمایش و هدر اکسل */
  label: string
}

const FA_MONTHS = [
  'فروردین', 'اردیبهشت', 'خرداد', 'تیر', 'مرداد', 'شهریور',
  'مهر', 'آبان', 'آذر', 'دی', 'بهمن', 'اسفند',
]

const MONTH_LENGTHS = (jy: number): number[] =>
  Array.from({ length: 12 }, (_, m) => (m < 6 ? 31 : m < 11 ? 30 : jalaliLeap(jy) ? 30 : 29))

export function jalaliLeap(jy: number): boolean {
  const mod = jy % 33
  return [1, 5, 9, 13, 17, 22, 26, 30].includes(mod)
}

/** الگوریتم جلالی→میلادی (هم‌ارز Helpers.php) */
export function jalaliToGregorian(jy: number, jm: number, jd: number): [number, number, number] {
  jy += 1595
  let days =
    -355668 + 365 * jy + Math.floor(jy / 33) * 8 + Math.floor(((jy % 33) + 3) / 4) + jd +
    (jm < 7 ? (jm - 1) * 31 : (jm - 7) * 30 + 186)
  let gy = 400 * Math.floor(days / 146097)
  days %= 146097
  if (days > 36524) {
    gy += 100 * Math.floor(--days / 36524)
    days %= 36524
    if (days >= 365) days++
  }
  gy += 4 * Math.floor(days / 1461)
  days %= 1461
  if (days > 365) {
    gy += Math.floor(--days / 365)
    days %= 365
  }
  let gd = days + 1
  const leap = (gy % 4 === 0 && gy % 100 !== 0) || gy % 400 === 0
  const salM = [0, 31, leap ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
  let gm = 0
  for (; gm < 13 && gd > salM[gm]; gm++) gd -= salM[gm]
  return [gy, gm, gd]
}

/** میلادی→جلالی (هم‌ارز Helpers.php) */
export function gregorianToJalali(gy: number, gm: number, gd: number): Jalali {
  const gDm = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
  const gy2 = gm > 2 ? gy + 1 : gy
  let days =
    355666 + 365 * gy + Math.floor((gy2 + 3) / 4) - Math.floor((gy2 + 99) / 100) +
    Math.floor((gy2 + 399) / 400) + gd + gDm[gm - 1]
  let jy = -1595 + 33 * Math.floor(days / 12053)
  days %= 12053
  jy += 4 * Math.floor(days / 1461)
  days %= 1461
  if (days > 365) {
    jy += Math.floor((days - 1) / 365)
    days = (days - 1) % 365
  }
  const jm = days < 186 ? 1 + Math.floor(days / 31) : 7 + Math.floor((days - 186) / 30)
  const jd = 1 + (days < 186 ? days % 31 : (days - 186) % 31)
  return [jy, jm, jd]
}

export const faNum = (v: number | string): string =>
  String(v).replace(/\d/g, (d) => '۰۱۲۳۴۵۶۷۸۹'[Number(d)])

export const faCode = (code: string): string =>
  code === '80403-A' ? 'پیوست ۸۰۴۰۳' : faNum(code)

/** تاریخ شمسی → ISO میلادی برای فیلترهای API */
export function jalaliToIso([jy, jm, jd]: Jalali): string {
  const [gy, gm, gd] = jalaliToGregorian(jy, jm, jd)
  return `${String(gy).padStart(4, '0')}-${String(gm).padStart(2, '0')}-${String(gd).padStart(2, '0')}`
}

export function isoToJalali(iso: string): Jalali | null {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso)
  if (!m) return null
  return gregorianToJalali(Number(m[1]), Number(m[2]), Number(m[3]))
}

/** نمایش شمسی یک تاریخ ISO (۱۴۰۵/۰۵/۰۱) */
export function faDate(iso: string | null | undefined): string {
  const j = iso ? isoToJalali(iso) : null
  return j ? faNum(`${j[0]}/${String(j[1]).padStart(2, '0')}/${String(j[2]).padStart(2, '0')}`) : '—'
}

export interface PeriodPreset {
  id: string
  label: string
  fromMonth: number
  toMonth: number
}

/** پیش‌فرض‌های رسمی دوره‌ها برای یک سال شمسی */
export function periodPresets(year: number): PeriodPreset[] {
  const b = (id: string, n: string, m1: number, m2: number): PeriodPreset => ({
    id, label: `دوماههٔ ${n} — ${FA_MONTHS[m1 - 1]} و ${FA_MONTHS[m2 - 1]}`, fromMonth: m1, toMonth: m2,
  })
  const q = (id: string, n: string, m1: number, m2: number): PeriodPreset => ({
    id, label: `چهارماههٔ ${n} — ${FA_MONTHS[m1 - 1]} تا ${FA_MONTHS[m2 - 1]}`, fromMonth: m1, toMonth: m2,
  })
  const h = (id: string, n: string, m1: number, m2: number): PeriodPreset => ({
    id, label: `شش‌ماههٔ ${n} — ${FA_MONTHS[m1 - 1]} تا ${FA_MONTHS[m2 - 1]}`, fromMonth: m1, toMonth: m2,
  })
  return [
    { id: 'year', label: `سال کامل ${faNum(year)}`, fromMonth: 1, toMonth: 12 },
    h('h1', 'اول', 1, 6),
    h('h2', 'دوم', 7, 12),
    q('q1', 'اول', 1, 4),
    q('q2', 'دوم', 5, 8),
    q('q3', 'سوم', 9, 12),
    b('b1', 'اول', 1, 2),
    b('b2', 'دوم', 3, 4),
    b('b3', 'سوم', 5, 6),
    b('b4', 'چهارم', 7, 8),
    b('b5', 'پنجم', 9, 10),
    b('b6', 'ششم', 11, 12),
  ]
}

const lastDayOf = (jy: number, jm: number): number => MONTH_LENGTHS(jy)[jm - 1]

export function presetSelection(year: number, presetId: string): PeriodSelection {
  const preset = periodPresets(year).find((p) => p.id === presetId) ?? periodPresets(year)[10]
  const fromJalali: Jalali = [year, preset.fromMonth, 1]
  const toJalali: Jalali = [year, preset.toMonth, lastDayOf(year, preset.toMonth)]
  return { presetId: preset.id, year, fromJalali, toJalali, label: `${preset.label} ${faNum(year)}` }
}

export function customSelection(year: number, fromJalali: Jalali, toJalali: Jalali): PeriodSelection {
  const l = (j: Jalali) => `${faNum(j[0])}/${faNum(String(j[1]).padStart(2, '0'))}/${faNum(String(j[2]).padStart(2, '0'))}`
  return {
    presetId: 'custom',
    year,
    fromJalali,
    toJalali,
    label: `بازهٔ سفارشی ${l(fromJalali)} تا ${l(toJalali)}`,
  }
}

/** دورهٔ پیش‌فرض سامانه: دوماههٔ سوم (مرداد–شهریور) سال جاری گزارش */
export function defaultSelection(year = 1405): PeriodSelection {
  return presetSelection(year, 'b3')
}

export const jalaliMonthNames = FA_MONTHS
