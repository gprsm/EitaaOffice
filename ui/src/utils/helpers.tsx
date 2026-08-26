import { toast } from '../MaterialToast'
import SyncRounded from '@mui/icons-material/SyncRounded'
import { scopedStorageKey } from '../lib/api'
import { Box, Button, ButtonBase, CircularProgress, IconButton, Popover, Stack, ToggleButton, ToggleButtonGroup, Tooltip, Typography } from '@mui/material'
import CalendarMonthRounded from '@mui/icons-material/CalendarMonthRounded'
import ChevronLeftRounded from '@mui/icons-material/ChevronLeftRounded'
import ChevronRightRounded from '@mui/icons-material/ChevronRightRounded'
import { useEffect, useMemo, useRef, useState } from 'react'
import { stableMessageKey } from '../lib/scrollMath'
import type { DialogItem, DisplayKind, MessageItem, PeerType, Term, IndexPrediction } from '../lib/types'

export const TEMPORAL_YEAR_OFFSET = 3_000_000_000
export const TEMPORAL_MONTH_OFFSET = 3_100_000_000
export const PERSIAN_MONTHS = ['فروردین', 'اردیبهشت', 'خرداد', 'تیر', 'مرداد', 'شهریور', 'مهر', 'آبان', 'آذر', 'دی', 'بهمن', 'اسفند']
export const LOCALIZED_LOGIN_CODE_DIGITS = '۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩'

export function normalizeLoginCodeInput(value: string) {
  return value
    .normalize('NFKC')
    .replace(/[۰-۹٠-٩]/g, digit => String(LOCALIZED_LOGIN_CODE_DIGITS.indexOf(digit) % 10))
    .replace(/[\s\u200c\u200e\u200f\u202a-\u202e\u2066-\u2069]/g, '')
}

export const messageKey = (dialog: DialogItem, message: MessageItem) => stableMessageKey(dialog.peer_key, message.id)
export const titleFor = (dialog: DialogItem | null) => dialog?.peer.title || (dialog?.peer.username ? `@${dialog.peer.username}` : dialog ? `گفتگو ${dialog.peer.id}` : 'گفتگو')
export const displayKindLabel = (kind: DisplayKind) => kind === 'channel' ? 'کانال' : kind === 'group' ? 'گروه' : 'شخصی'

export type CategoryTreeRow = { term: Term; depth: number }

export function categoryTree(terms: Term[]): CategoryTreeRow[] {
  const byId = new Map(terms.map(term => [term.id, term]))
  const children = new Map<number, Term[]>()
  const roots: Term[] = []
  const compare = (a: Term, b: Term) => a.name.localeCompare(b.name, 'fa')

  for (const term of terms) {
    const parentId = term.parent_id || null
    if (!parentId || parentId === term.id || !byId.has(parentId)) roots.push(term)
    else children.set(parentId, [...(children.get(parentId) || []), term])
  }
  roots.sort(compare)
  children.forEach(items => items.sort(compare))

  const rows: CategoryTreeRow[] = []
  const visited = new Set<number>()
  const append = (term: Term, depth: number) => {
    if (visited.has(term.id)) return
    visited.add(term.id)
    rows.push({ term, depth })
    for (const child of children.get(term.id) || []) append(child, depth + 1)
  }
  roots.forEach(term => append(term, 0))
  terms.filter(term => !visited.has(term.id)).sort(compare).forEach(term => append(term, 0))
  return rows
}

export const STORAGE = {
  siteKey: 'eitaa-bridge.ui.site-key',
  peerKey: 'eitaa-bridge.ui.peer-key',
  tab: 'eitaa-bridge.ui.dialog-tab',
  syncTimes: 'eitaa-bridge.ui.message-sync-times',
  terms: 'eitaa-bridge.ui.wordpress-terms',
  indexAliases: 'eitaa-bridge.ui.content-index-aliases',
  indexNames: 'eitaa-bridge.ui.content-index-names',
  customIndexes: 'eitaa-bridge.ui.custom-indexes',
  mediaDisplay: 'eitaa-bridge.ui.media-display',
}

export function readStored<T>(key: string, fallback: T): T {
  try {
    const raw = window.localStorage.getItem(scopedStorageKey(key))
    return raw ? JSON.parse(raw) as T : fallback
  } catch { return fallback }
}

export function writeStored(key: string, value: unknown) {
  try { window.localStorage.setItem(scopedStorageKey(key), JSON.stringify(value)) } catch { /* best effort */ }
}

export const REMOTE_MESSAGE_TTL_MS = 2 * 60 * 1000
export const AUTO_NEWER_TTL_MS = 45 * 1000
export const TERM_CACHE_TTL_MS = 10 * 60 * 1000
export const mediaUrl = (value?: string) => {
  if (!value || !/^\/api\/v1\/media-cache\/[0-9a-f]{32}$/.test(value)) return ''
  return window.location.protocol === 'file:' ? `eitaa-media://bridge${value}` : value
}
export const JALALI_DAY_LABEL_FORMATTER = new Intl.DateTimeFormat('fa-IR-u-ca-persian', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })
export const JALALI_DAY_KEY_FORMATTER = new Intl.DateTimeFormat('en-US-u-ca-persian', { year: 'numeric', month: '2-digit', day: '2-digit' })

export function parseSourceKey(value: string) {
  const [peerType, peerId, messageId] = value.split(':')
  return { peerType: peerType as PeerType, peerId: Number(peerId), messageId: Number(messageId), peerKey: `${peerType}:${peerId}` }
}

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
      evidence: ['تاریخ پیام'],
      accepted: true,
    },
    {
      label_id: TEMPORAL_MONTH_OFFSET + year * 100 + month,
      label_name: `${PERSIAN_MONTHS[month - 1]} ${year.toLocaleString('fa-IR', { useGrouping: false })}`,
      score: 1,
      evidence: ['تاریخ پیام'],
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
  j = j + div(div(4 * jdn + 183187720, 146097) * 3, 4) * 4 - 3908
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
  return d2g(j2d(jy, jm, jd))
}

export function parseJalaliDate(value: string) {
  const normalized = value.replace(/[۰-۹]/g, char => String('۰۱۲۳۴۵۶۷۸۹'.indexOf(char))).trim()
  const match = normalized.match(/^(\d{4})[\/-](\d{1,2})[\/-](\d{1,2})$/)
  if (!match) return null
  const jy = Number(match[1]); const jm = Number(match[2]); const jd = Number(match[3])
  if (jm < 1 || jm > 12 || jd < 1 || jd > 31 || (jm > 6 && jd > 30)) return null
  const result = jalaliToGregorian(jy, jm, jd)
  const local = new Date(result.gy, result.gm - 1, result.gd, 0, 0, 0, 0)
  return Number.isNaN(local.getTime()) ? null : local
}

export function jalaliParts(value = new Date()) {
  const parts = new Intl.DateTimeFormat('en-US-u-ca-persian', { year: 'numeric', month: 'numeric', day: 'numeric' }).formatToParts(value)
  const read = (type: string) => Number(parts.find(item => item.type === type)?.value || 0)
  return { year: read('year'), month: read('month'), day: read('day') }
}

export function jalaliYmd(year: number, month: number, day: number) {
  return `${year}/${String(month).padStart(2, '0')}/${String(day).padStart(2, '0')}`
}

export function jalaliMonthLength(year: number, month: number) {
  if (month <= 6) return 31
  if (month <= 11) return 30
  return parseJalaliDate(jalaliYmd(year, 12, 30)) ? 30 : 29
}

export const jalaliMonths = ['فروردین', 'اردیبهشت', 'خرداد', 'تیر', 'مرداد', 'شهریور', 'مهر', 'آبان', 'آذر', 'دی', 'بهمن', 'اسفند']
export const jalaliWeekdays = ['ش', 'ی', 'د', 'س', 'چ', 'پ', 'ج']

export function JalaliDatePicker(props: {
  value: string
  mode: 'day' | 'from'
  disabled?: boolean
  busy?: boolean
  onMode: (mode: 'day' | 'from') => void
  onSelect: (value: string, mode: 'day' | 'from', forceSync?: boolean) => void
  onClear: () => void
}) {
  const now = useMemo(() => jalaliParts(), [])
  const parsed = props.value.match(/^(\d{4})\/(\d{2})\/(\d{2})$/)
  const [open, setOpen] = useState(false)
  const [year, setYear] = useState(parsed ? Number(parsed[1]) : now.year)
  const [month, setMonth] = useState(parsed ? Number(parsed[2]) : now.month)
  const root = useRef<HTMLDivElement | null>(null)
  useEffect(() => {
    const close = (event: MouseEvent) => { if (root.current && !root.current.contains(event.target as Node)) setOpen(false) }
    const key = (event: KeyboardEvent) => { if (event.key === 'Escape') setOpen(false) }
    document.addEventListener('mousedown', close); window.addEventListener('keydown', key)
    return () => { document.removeEventListener('mousedown', close); window.removeEventListener('keydown', key) }
  }, [])
  const first = parseJalaliDate(jalaliYmd(year, month, 1))
  const offset = first ? (first.getDay() + 1) % 7 : 0
  const days = Array.from({ length: jalaliMonthLength(year, month) }, (_, index) => index + 1)
  const moveMonth = (delta: number) => {
    let nextMonth = month + delta; let nextYear = year
    if (nextMonth < 1) { nextMonth = 12; nextYear -= 1 }
    if (nextMonth > 12) { nextMonth = 1; nextYear += 1 }
    setMonth(nextMonth); setYear(nextYear)
  }
  return <Box ref={root} sx={{ display: 'inline-flex' }}>
    <Tooltip title={props.value ? `فیلتر تاریخ ${props.value}` : 'انتخاب تاریخ شمسی'}>
      <Button
        size="small"
        variant={props.value ? 'contained' : 'text'}
        disabled={props.disabled}
        onClick={() => setOpen(value => !value)}
        startIcon={props.busy ? <CircularProgress size={18} color="inherit" /> : <CalendarMonthRounded fontSize="small" />}
        aria-haspopup="dialog"
        aria-expanded={open}
      >{props.value || <Box component="span" sx={{ display: { xs: 'none', sm: 'inline' } }}>تاریخ</Box>}</Button>
    </Tooltip>
    <Popover
      open={open}
      anchorEl={root.current}
      onClose={() => setOpen(false)}
      anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      transformOrigin={{ vertical: 'top', horizontal: 'center' }}
      slotProps={{ paper: { sx: { width: 'min(92vw, 340px)', p: 1.5, borderRadius: 3 } } }}
    >
      <Stack spacing={1.25} onClick={event => event.stopPropagation()}>
        <ToggleButtonGroup exclusive fullWidth size="small" value={props.mode} onChange={(_event, value) => value && props.onMode(value)} aria-label="دامنه تاریخ">
          <ToggleButton value="day">فقط همان روز</ToggleButton>
          <ToggleButton value="from">از این تاریخ به بعد</ToggleButton>
        </ToggleButtonGroup>
        <Stack direction="row" alignItems="center" justifyContent="space-between">
          <IconButton onClick={() => moveMonth(1)} aria-label="ماه بعد"><ChevronRightRounded /></IconButton>
          <Typography fontWeight={850}>{jalaliMonths[month - 1]} {year.toLocaleString('fa-IR', { useGrouping: false })}</Typography>
          <IconButton onClick={() => moveMonth(-1)} aria-label="ماه قبل"><ChevronLeftRounded /></IconButton>
        </Stack>
        <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: 0.25, textAlign: 'center' }}>
          {jalaliWeekdays.map(day => <Typography key={day} variant="caption" color="text.secondary" sx={{ py: 0.5 }}>{day}</Typography>)}
          {Array.from({ length: offset }).map((_, index) => <Box key={`empty-${index}`} />)}
          {days.map(day => {
            const value = jalaliYmd(year, month, day)
            const selected = value === props.value
            const isToday = year === now.year && month === now.month && day === now.day
            return <ButtonBase
              key={day}
              onClick={() => { props.onSelect(value, props.mode); setOpen(false) }}
              sx={{ aspectRatio: '1', borderRadius: '50%', bgcolor: selected ? 'primary.main' : 'transparent', color: selected ? 'primary.contrastText' : 'text.primary', border: isToday && !selected ? 1 : 0, borderColor: 'primary.main', fontSize: '0.85rem', '&:hover': { bgcolor: selected ? 'primary.dark' : 'action.hover' } }}
            >{day.toLocaleString('fa-IR')}</ButtonBase>
          })}
        </Box>
        <Stack direction="column" spacing={1}>
            <Button size="small" variant="outlined" color="primary" onClick={() => { if (props.value) { props.onSelect(props.value, props.mode, true); setOpen(false); } else { toast.warning('ابتدا یک روز را در تقویم انتخاب کنید') } }} startIcon={<SyncRounded />}>همگام‌سازی عمیق از تاریخ انتخاب شده</Button>
            <Stack direction="row" justifyContent="space-between">
          <Button size="small" onClick={() => { setYear(now.year); setMonth(now.month) }}>امروز</Button>
          {props.value && <Button size="small" color="error" onClick={() => { props.onClear(); setOpen(false) }}>پاک‌کردن فیلتر</Button>}
        </Stack>
          </Stack>
      </Stack>
    </Popover>
  </Box>
}

