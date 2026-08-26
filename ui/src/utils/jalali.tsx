import { Box, Button, IconButton, Menu, Stack, Typography } from '@mui/material'
import ChevronLeftRounded from '@mui/icons-material/ChevronLeftRounded'
import ChevronRightRounded from '@mui/icons-material/ChevronRightRounded'
import { useState } from 'react'

export const TEMPORAL_YEAR_OFFSET = 3_000_000_000
export const TEMPORAL_MONTH_OFFSET = 3_100_000_000

export type IndexPrediction = {
  label_id: number
  label_name: string
  score: number
  evidence: string[]
  accepted: boolean
}

const PERSIAN_MONTHS = ['فروردین', 'اردیبهشت', 'خرداد', 'تیر', 'مرداد', 'شهریور', 'مهر', 'آبان', 'آذر', 'دی', 'بهمن', 'اسفند']

const JALALI_DAY_LABEL_FORMATTER = new Intl.DateTimeFormat('fa-IR-u-ca-persian', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })
const JALALI_DAY_KEY_FORMATTER = new Intl.DateTimeFormat('en-US-u-ca-persian', { year: 'numeric', month: '2-digit', day: '2-digit' })

export function jalaliDayLabel(value: string) {
  try { return JALALI_DAY_LABEL_FORMATTER.format(new Date(value)) }
  catch { return value }
}

export function jalaliDayKey(value: string) {
  try { return JALALI_DAY_KEY_FORMATTER.format(new Date(value)) }
  catch { return value.slice(0, 10) }
}

export function temporalIndexPredictions(value: string): IndexPrediction[] {
  const [yearText, monthText] = jalaliDayKey(value).split('/')
  const year = Number(yearText)
  const month = Number(monthText)
  if (!Number.isInteger(year) || !Number.isInteger(month) || month < 1 || month > 12) return []
  return [
    {
      label_id: TEMPORAL_YEAR_OFFSET + year,
      label_name: `سال ${year.toLocaleString('fa-IR', { useGrouping: false })}`,
      score: 1,
      evidence: ['زمان ارسال پیام'],
      accepted: true,
    },
    {
      label_id: TEMPORAL_MONTH_OFFSET + year * 100 + month,
      label_name: `${PERSIAN_MONTHS[month - 1]} ${year.toLocaleString('fa-IR', { useGrouping: false })}`,
      score: 1,
      evidence: ['زمان ارسال پیام'],
      accepted: true,
    },
  ]
}

export const div = (a: number, b: number) => Math.trunc(a / b)
export const mod = (a: number, b: number) => a - Math.trunc(a / b) * b

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

export function jalaliToGregorian(jy: number, jm: number, jd: number) {
  const g = d2g(j2d(jy, jm, jd))
  return new Date(Date.UTC(g.gy, g.gm - 1, g.gd))
}

export function parseJalaliDate(value: string) {
  const parts = value.split('/').map(Number)
  if (parts.length !== 3 || parts.some(isNaN)) return null
  return jalaliToGregorian(parts[0], parts[1], parts[2])
}

export function jalaliParts(value = new Date()) {
  const gy = value.getFullYear()
  const gm = value.getMonth() + 1
  const gd = value.getDate()
  let jm = 0
  let jd = 0
  let gy2 = gy
  let leap = 0
  let march = 0
  let remain = 0
  let jy = gy - 621
  const r = jalCal(jy)
  const jdn = g2d(gy, gm, gd)
  let jdn1f = g2d(gy2, 3, r.march)
  let k = jdn - jdn1f
  if (k >= 0) {
    if (k <= 185) {
      jm = 1 + div(k, 31)
      jd = mod(k, 31) + 1
      return { jy, jm, jd }
    } else {
      k -= 186
    }
  } else {
    jy -= 1
    k += 179
    if (r.leap === 1) k += 1
  }
  jm = 7 + div(k, 30)
  jd = mod(k, 30) + 1
  return { jy, jm, jd }
}

export function jalaliYmd(year: number, month: number, day: number) {
  return `${year.toString().padStart(4, '0')}/${month.toString().padStart(2, '0')}/${day.toString().padStart(2, '0')}`
}

export function jalaliMonthLength(year: number, month: number) {
  if (month <= 6) return 31
  if (month <= 11) return 30
  if (jalCal(year).leap === 0) return 30
  return 29
}

export function JalaliDatePicker(props: {
  value: string | null
  onChange: (value: string | null) => void
  disabled?: boolean
  label?: string
}) {
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null)
  const open = Boolean(anchorEl)
  const handleClick = (event: React.MouseEvent<HTMLButtonElement>) => { setAnchorEl(event.currentTarget) }
  const handleClose = () => { setAnchorEl(null) }

  const today = jalaliParts(new Date())
  const selectedParts = props.value ? props.value.split('/').map(Number) : [today.jy, today.jm, today.jd]
  const [viewYear, setViewYear] = useState(selectedParts[0])
  const [viewMonth, setViewMonth] = useState(selectedParts[1])

  const daysInMonth = jalaliMonthLength(viewYear, viewMonth)
  const firstDayOfWeek = jalaliToGregorian(viewYear, viewMonth, 1).getDay()
  const offset = (firstDayOfWeek + 1) % 7 // offset for saturday start
  const days = Array.from({ length: daysInMonth }, (_, i) => i + 1)

  const handlePrev = () => {
    if (viewMonth === 1) { setViewMonth(12); setViewYear(viewYear - 1) }
    else setViewMonth(viewMonth - 1)
  }
  const handleNext = () => {
    if (viewMonth === 12) { setViewMonth(1); setViewYear(viewYear + 1) }
    else setViewMonth(viewMonth + 1)
  }
  const handleSelect = (day: number) => {
    props.onChange(jalaliYmd(viewYear, viewMonth, day))
    handleClose()
  }

  return <>
    <Button
      variant="outlined"
      onClick={handleClick}
      disabled={props.disabled}
      sx={{ justifyContent: 'flex-start', color: props.value ? 'text.primary' : 'text.secondary' }}
    >
      {props.value ? props.value : (props.label || 'انتخاب تاریخ')}
    </Button>
    <Menu anchorEl={anchorEl} open={open} onClose={handleClose}>
      <Stack sx={{ p: 2, minWidth: 260 }}>
        <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ mb: 2 }}>
          <IconButton onClick={handlePrev} size="small"><ChevronRightRounded /></IconButton>
          <Typography fontWeight={600}>{PERSIAN_MONTHS[viewMonth - 1]} {viewYear.toLocaleString('fa-IR', { useGrouping: false })}</Typography>
          <IconButton onClick={handleNext} size="small"><ChevronLeftRounded /></IconButton>
        </Stack>
        <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: 0.5, textAlign: 'center', mb: 1 }}>
          {['ش', 'ی', 'د', 'س', 'چ', 'پ', 'ج'].map(d => <Typography key={d} variant="caption" color="text.secondary">{d}</Typography>)}
        </Box>
        <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: 0.5 }}>
          {Array.from({ length: offset }).map((_, i) => <Box key={`empty-${i}`} />)}
          {days.map(day => {
            const isSelected = props.value === jalaliYmd(viewYear, viewMonth, day)
            return <IconButton
              key={day}
              onClick={() => handleSelect(day)}
              size="small"
              sx={{
                width: 32, height: 32, fontSize: '0.875rem',
                ...(isSelected && { bgcolor: 'primary.main', color: 'primary.contrastText', '&:hover': { bgcolor: 'primary.dark' } })
              }}
            >
              {day.toLocaleString('fa-IR')}
            </IconButton>
          })}
        </Box>
      </Stack>
    </Menu>
  </>
}
