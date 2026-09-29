/**
 * ماژول مستقل و کلاس‌بندی‌شده محاسبات و نمایش تاریخ‌های شمسی در فرانت‌اند
 * JalaliDate Utility Class (F-097 / TASK-02)
 */

export type JalaliTriple = [number, number, number] // [سال, ماه, روز]

export class JalaliDate {
  private static readonly FA_DIGITS = ['۰', '۱', '۲', '۳', '۴', '۵', '۶', '۷', '۸', '۹']
  private static readonly AR_DIGITS = ['٠', '١', '٢', '٣', '٤', '٥', '٦', '٧', '٨', '٩']

  public static readonly MONTH_NAMES = [
    'فروردین', 'اردیبهشت', 'خرداد', 'تیر', 'مرداد', 'شهریور',
    'مهر', 'آبان', 'آذر', 'دی', 'بهمن', 'اسفند',
  ]

  /** تبدیل اعداد به ارقام فارسی */
  public static faNum(v: number | string | null | undefined): string {
    if (v === null || v === undefined || v === '') return ''
    return String(v).replace(/\d/g, (d) => this.FA_DIGITS[Number(d)])
  }

  /** نرمال‌سازی ارقام فارسی/عربی به انگلیسی */
  public static normalizeDigits(v: string | null | undefined): string {
    if (!v) return ''
    let s = String(v)
    for (let i = 0; i < 10; i++) {
      s = s.replaceAll(this.FA_DIGITS[i], String(i)).replaceAll(this.AR_DIGITS[i], String(i))
    }
    return s.trim()
  }

  /** بررسی سال کبیسه شمسی */
  public static isLeapYear(jy: number): boolean {
    const mod = jy % 33
    return [1, 5, 9, 13, 17, 22, 26, 30].includes(mod)
  }

  /** تبدیل میلادی به شمسی [jy, jm, jd] */
  public static gregorianToJalali(gy: number, gm: number, gd: number): JalaliTriple {
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
    const jd = 1 + (days < 186 ? days % 31 : (days - 186) % 30)
    return [jy, jm, jd]
  }

  /** تبدیل شمسی به میلادی [gy, gm, gd] */
  public static jalaliToGregorian(jy: number, jm: number, jd: number): [number, number, number] {
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

  /**
   * نمایش کاملاً یکپارچه و استاندارد تاریخ شمسی با ارقام فارسی
   * ورودی می‌تواند تاریخ میلادی ISO، تایم‌استمپ وردپرس، شناسه رویداد، یا تاریخ شمسی باشد.
   * خروجی مثال: ۱۴۰۵/۰۶/۱۶
   */
  public static format(value: string | number | Date | null | undefined, fallback = '—'): string {
    if (value === null || value === undefined || value === '') return fallback

    // شیء Date استاندارد
    if (value instanceof Date) {
      if (isNaN(value.getTime())) return fallback
      const [jy, jm, jd] = this.gregorianToJalali(value.getFullYear(), value.getMonth() + 1, value.getDate())
      return this.faNum(`${jy}/${String(jm).padStart(2, '0')}/${String(jd).padStart(2, '0')}`)
    }

    const str = String(value).trim()
    if (!str) return fallback

    const clean = this.normalizeDigits(str)

    // ۱. بررسی رشته شمسی موجود (مثلاً 1405/06/16 یا 1405-06-16)
    const jm = /^(1[34]\d{2})[\/\-](\d{1,2})[\/\-](\d{1,2})/.exec(clean)
    if (jm) {
      return this.faNum(`${jm[1]}/${jm[2].padStart(2, '0')}/${jm[3].padStart(2, '0')}`)
    }

    // ۲. استخراج تاریخ از شناسه رویداد (مانند ev-14050614-30474 یا ev-man-14050614-...)
    const idM = /ev-(?:man-)?(1[34]\d{2})(\d{2})(\d{2})-/.exec(clean)
    if (idM) {
      return this.faNum(`${idM[1]}/${idM[2]}/${idM[3]}`)
    }

    // ۳. تبدیل تاریخ میلادی ISO (YYYY-MM-DD یا YYYY-MM-DD HH:MM:SS)
    const gm = /^(\d{4})[\/\-](\d{1,2})[\/\-](\d{1,2})/.exec(clean)
    if (gm) {
      const gy = Number(gm[1])
      const gMonth = Number(gm[2])
      const gd = Number(gm[3])
      if (gy > 1900 && gy < 2200 && gMonth >= 1 && gMonth <= 12 && gd >= 1 && gd <= 31) {
        const [jy, jm, jd] = this.gregorianToJalali(gy, gMonth, gd)
        return this.faNum(`${jy}/${String(jm).padStart(2, '0')}/${String(jd).padStart(2, '0')}`)
      }
    }

    return this.faNum(str)
  }

  /** تاریخ امروز به صورت جلالی [y, m, d] */
  public static today(): JalaliTriple {
    const d = new Date()
    return this.gregorianToJalali(d.getFullYear(), d.getMonth() + 1, d.getDate())
  }

  /** تاریخ امروز به صورت رشته شمسی */
  public static todayString(): string {
    return this.format(new Date())
  }
}

/** تابع کمکی سریع برای فراخوانی مستقیم */
export const faDate = (v: string | number | Date | null | undefined, fallback?: string): string =>
  JalaliDate.format(v, fallback)
