import { FormEvent, ReactNode, useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { useVirtualizer } from '@tanstack/react-virtual'
import { toast } from 'react-toastify'
import { Alert, Box, Button, ButtonBase, CircularProgress, Dialog, DialogContent, Paper, Skeleton, Stack, TextField, Typography, useMediaQuery, useTheme } from '@mui/material'
import { api, query } from './lib/api'
import { albumCaption, buildAlbumLookup } from './lib/groupedMedia'
import type { MediaAlbum } from './lib/groupedMedia'
import { anchorScrollTop, appendedMessagesAfterTail, estimateMessageRowSize, isNearBottom, mergeMessagesById, shouldAutoFollow, stableMessageKey, updateTopPaginationGate } from './lib/scrollMath'
import type { MessageScrollMemory, ScrollAnchor, TopPaginationGate } from './lib/scrollMath'
import type { CompositionRecord, ContentIndexJob, ContentIndexResult, DialogItem, DisplayKind, IndexPrediction, MessageItem, MessageUsage, PeerType, Site, Term } from './lib/types'
import { ContactDirectoryModal } from './ContactDirectoryModal'
import { QuickSendBar } from './QuickSendBar'
import { useColorMode } from './theme'
import { MaterialIndexWorkbench } from './MaterialIndexWorkbench'
import { MessageIndexEditor } from './MessageIndexEditor'
import { loadDialogAvatar, peekDialogAvatar } from './lib/avatarLoader'
import { LoginAppearanceProvider, LoginAppearanceSettingsPanel, LoginSurface } from './LoginExperience'

type AuthStatus = { authenticated: boolean; session_present: boolean; password_pending: boolean; session_error?: boolean; session_error_code?: string; session_error_type?: string; fresh_login_available?: boolean; remote_warning?: boolean; remote_error_type?: string; remote_error_code?: number | string }
type Tab = 'all' | 'channel' | 'group' | 'personal' | 'favorite'
type BulkMode = 'members' | 'numbers' | 'invite'
type ComposerResult = Record<string, any>
type IndexWorkbenchTab = 'index' | 'display'
type IndexDefinitionKind = 'wordpress-category' | 'wordpress-tag' | 'custom'
type IndexDefinition = {
  id: number
  name: string
  aliases: string[]
  kind: IndexDefinitionKind
  wordpressCategoryId?: number | null
}

const WORDPRESS_TAG_INDEX_OFFSET = 1_000_000_000
const CUSTOM_INDEX_OFFSET = 2_000_000_000
const TEMPORAL_YEAR_OFFSET = 3_000_000_000
const TEMPORAL_MONTH_OFFSET = 3_100_000_000
const PERSIAN_MONTHS = ['فروردین', 'اردیبهشت', 'خرداد', 'تیر', 'مرداد', 'شهریور', 'مهر', 'آبان', 'آذر', 'دی', 'بهمن', 'اسفند']

const messageKey = (dialog: DialogItem, message: MessageItem) => stableMessageKey(dialog.peer_key, message.id)
const titleFor = (dialog: DialogItem | null) => dialog?.peer.title || (dialog?.peer.username ? `@${dialog.peer.username}` : dialog ? `گفتگو ${dialog.peer.id}` : 'گفتگو')
const displayKindLabel = (kind: DisplayKind) => kind === 'channel' ? 'کانال' : kind === 'group' ? 'گروه' : 'شخصی'

type CategoryTreeRow = { term: Term; depth: number }

function categoryTree(terms: Term[]): CategoryTreeRow[] {
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

const STORAGE = {
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

function readStored<T>(key: string, fallback: T): T {
  try {
    const raw = window.localStorage.getItem(key)
    return raw ? JSON.parse(raw) as T : fallback
  } catch { return fallback }
}

function writeStored(key: string, value: unknown) {
  try { window.localStorage.setItem(key, JSON.stringify(value)) } catch { /* best effort */ }
}

const REMOTE_MESSAGE_TTL_MS = 2 * 60 * 1000
const AUTO_NEWER_TTL_MS = 45 * 1000
const TERM_CACHE_TTL_MS = 10 * 60 * 1000
const LOCAL_MEDIA_BASE = 'http://127.0.0.1:8765'
const mediaUrl = (value?: string) => value ? `${LOCAL_MEDIA_BASE}${value}` : ''
const MESSAGE_DATE_FORMATTER = new Intl.DateTimeFormat('fa-IR', { hour: '2-digit', minute: '2-digit', month: 'short', day: 'numeric' })
const JALALI_DAY_LABEL_FORMATTER = new Intl.DateTimeFormat('fa-IR-u-ca-persian', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })
const JALALI_DAY_KEY_FORMATTER = new Intl.DateTimeFormat('en-US-u-ca-persian', { year: 'numeric', month: '2-digit', day: '2-digit' })

function parseSourceKey(value: string) {
  const [peerType, peerId, messageId] = value.split(':')
  return { peerType: peerType as PeerType, peerId: Number(peerId), messageId: Number(messageId), peerKey: `${peerType}:${peerId}` }
}

function formatDate(value: string) {
  try { return MESSAGE_DATE_FORMATTER.format(new Date(value)) }
  catch { return value }
}

function jalaliDayLabel(value: string) {
  try { return JALALI_DAY_LABEL_FORMATTER.format(new Date(value)) }
  catch { return value }
}

function jalaliDayKey(value: string) {
  try { return JALALI_DAY_KEY_FORMATTER.format(new Date(value)) }
  catch { return value.slice(0, 10) }
}

function temporalIndexPredictions(value: string): IndexPrediction[] {
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

const div = (a: number, b: number) => Math.trunc(a / b)
const mod = (a: number, b: number) => a - Math.trunc(a / b) * b

function jalCal(jy: number) {
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

function g2d(gy: number, gm: number, gd: number) {
  let d = div((gy + div(gm - 8, 6) + 100100) * 1461, 4)
  d += div(153 * mod(gm + 9, 12) + 2, 5) + gd - 34840408
  d = d - div(div(gy + 100100 + div(gm - 8, 6), 100) * 3, 4) + 752
  return d
}

function d2g(jdn: number) {
  let j = 4 * jdn + 139361631
  j = j + div(div(4 * jdn + 183187720, 146097) * 3, 4) * 4 - 3908
  const i = div(mod(j, 1461), 4) * 5 + 308
  const gd = div(mod(i, 153), 5) + 1
  const gm = mod(div(i, 153), 12) + 1
  const gy = div(j, 1461) - 100100 + div(8 - gm, 6)
  return { gy, gm, gd }
}

function j2d(jy: number, jm: number, jd: number) {
  const r = jalCal(jy)
  return g2d(r.gy, 3, r.march) + (jm - 1) * 31 - div(jm, 7) * (jm - 7) + jd - 1
}

function jalaliToGregorian(jy: number, jm: number, jd: number) {
  return d2g(j2d(jy, jm, jd))
}

function parseJalaliDate(value: string) {
  const normalized = value.replace(/[۰-۹]/g, char => String('۰۱۲۳۴۵۶۷۸۹'.indexOf(char))).trim()
  const match = normalized.match(/^(\d{4})[\/-](\d{1,2})[\/-](\d{1,2})$/)
  if (!match) return null
  const jy = Number(match[1]); const jm = Number(match[2]); const jd = Number(match[3])
  if (jm < 1 || jm > 12 || jd < 1 || jd > 31 || (jm > 6 && jd > 30)) return null
  const result = jalaliToGregorian(jy, jm, jd)
  const local = new Date(result.gy, result.gm - 1, result.gd, 0, 0, 0, 0)
  return Number.isNaN(local.getTime()) ? null : local
}

function jalaliParts(value = new Date()) {
  const parts = new Intl.DateTimeFormat('en-US-u-ca-persian', { year: 'numeric', month: 'numeric', day: 'numeric' }).formatToParts(value)
  const read = (type: string) => Number(parts.find(item => item.type === type)?.value || 0)
  return { year: read('year'), month: read('month'), day: read('day') }
}

function jalaliYmd(year: number, month: number, day: number) {
  return `${year}/${String(month).padStart(2, '0')}/${String(day).padStart(2, '0')}`
}

function jalaliMonthLength(year: number, month: number) {
  if (month <= 6) return 31
  if (month <= 11) return 30
  return parseJalaliDate(jalaliYmd(year, 12, 30)) ? 30 : 29
}

const jalaliMonths = ['فروردین', 'اردیبهشت', 'خرداد', 'تیر', 'مرداد', 'شهریور', 'مهر', 'آبان', 'آذر', 'دی', 'بهمن', 'اسفند']
const jalaliWeekdays = ['ش', 'ی', 'د', 'س', 'چ', 'پ', 'ج']

function JalaliDatePicker(props: {
  value: string
  mode: 'day' | 'from'
  disabled?: boolean
  busy?: boolean
  onMode: (mode: 'day' | 'from') => void
  onSelect: (value: string, mode: 'day' | 'from') => void
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
  return <div className="jalali-picker" ref={root}>
    <button className={`btn btn-sm btn-ghost calendar-button ${props.value ? 'active' : ''}`} disabled={props.disabled} onClick={() => setOpen(value => !value)} title={props.value ? `فیلتر تاریخ ${props.value}` : 'انتخاب تاریخ شمسی'}>
      {props.busy ? <span className="loading loading-dots loading-xs" /> : <Icon name="calendar" size={20} />}
      {props.value && <span>{props.value}</span>}
    </button>
    {open && <div className="jalali-popover card" onClick={event => event.stopPropagation()}>
      <div className="date-mode tabs tabs-box">
        <button type="button" role="tab" aria-selected={props.mode === 'day'} className={`tab ${props.mode === 'day' ? 'active' : ''}`} onClick={() => props.onMode('day')}>فقط همان روز</button>
        <button type="button" role="tab" aria-selected={props.mode === 'from'} className={`tab ${props.mode === 'from' ? 'active' : ''}`} onClick={() => props.onMode('from')}>از این تاریخ به بعد</button>
      </div>
      <div className="calendar-month-head">
        <button onClick={() => moveMonth(1)} aria-label="ماه بعد">‹</button>
        <strong>{jalaliMonths[month - 1]} {year}</strong>
        <button onClick={() => moveMonth(-1)} aria-label="ماه قبل">›</button>
      </div>
      <div className="calendar-grid weekdays">{jalaliWeekdays.map(day => <span key={day}>{day}</span>)}</div>
      <div className="calendar-grid days">
        {Array.from({ length: offset }).map((_, index) => <span key={`empty-${index}`} />)}
        {days.map(day => {
          const value = jalaliYmd(year, month, day)
          const isToday = year === now.year && month === now.month && day === now.day
          return <button key={day} className={`${value === props.value ? 'selected' : ''} ${isToday ? 'today' : ''}`} onClick={() => { props.onSelect(value, props.mode); setOpen(false) }}>{day.toLocaleString('fa-IR')}</button>
        })}
      </div>
      <div className="calendar-actions">
        <button className="btn btn-sm btn-ghost" onClick={() => { setYear(now.year); setMonth(now.month) }}>امروز</button>
        {props.value && <button className="btn btn-sm btn-ghost" onClick={() => { props.onClear(); setOpen(false) }}>پاک‌کردن فیلتر</button>}
      </div>
    </div>}
  </div>
}

function initials(title: string) {
  const clean = title.trim()
  return clean ? clean.slice(0, 2) : 'ا'
}

function DialogAvatar({ dialog, siteKey, small = false }: { dialog: DialogItem | null; siteKey: string; small?: boolean }) {
  const ref = useRef<HTMLDivElement>(null)
  const [src, setSrc] = useState<string | null | undefined>(() => dialog ? peekDialogAvatar(siteKey, dialog.peer_key) : null)
  useEffect(() => { setSrc(dialog ? peekDialogAvatar(siteKey, dialog.peer_key) : null) }, [dialog?.peer_key, siteKey])
  useEffect(() => {
    const element = ref.current
    if (!element || !dialog || !siteKey || src !== undefined) return
    let active = true
    const observer = new IntersectionObserver(entries => {
      if (!entries.some(entry => entry.isIntersecting)) return
      observer.disconnect()
      void loadDialogAvatar(siteKey, dialog.peer_key)
        .then(value => { if (active) setSrc(value) })
        .catch(() => { if (active) setSrc(null) })
    }, { rootMargin: '220px' })
    observer.observe(element)
    return () => { active = false; observer.disconnect() }
  }, [dialog, siteKey, src])
  return <div ref={ref} className={`avatar ${small ? 'small' : ''}`}>
    {src === undefined
      ? <Skeleton variant="circular" animation="wave" width="100%" height="100%" />
      : src
        ? <img src={src} alt={titleFor(dialog)} loading="lazy" decoding="async" />
        : initials(titleFor(dialog))}
  </div>
}

function TitleBar() {
  const [maximized, setMaximized] = useState(false)
  useEffect(() => {
    void window.eitaaDesktop.windowControls.isMaximized().then(setMaximized)
    return window.eitaaDesktop.windowControls.onMaximized(setMaximized)
  }, [])
  return <header className="desktop-titlebar">
    <div className="titlebar-caption"><span className="titlebar-logo">EB</span><b>Eitaa Bridge</b></div>
    <div className="window-controls">
      <button title="کمینه" onClick={() => void window.eitaaDesktop.windowControls.minimize()}>—</button>
      <button title={maximized ? 'بازگردانی' : 'بیشینه'} onClick={() => void window.eitaaDesktop.windowControls.toggleMaximize()}>{maximized ? '❐' : '□'}</button>
      <button className="window-close" title="بستن" onClick={() => void window.eitaaDesktop.windowControls.close()}>×</button>
    </div>
  </header>
}

function makeCompositionKey() {
  const stamp = new Date().toISOString().replace(/[-:TZ.]/g, '').slice(0, 14)
  return `ui-${stamp}-${Math.random().toString(36).slice(2, 8)}`
}

type IconName = 'menu' | 'all' | 'channel' | 'group' | 'personal' | 'favorite' | 'settings' | 'plus' | 'refresh' | 'wordpress' | 'logout' | 'search' | 'close' | 'more' | 'excel' | 'bulk' | 'calendar' | 'filter'

function Icon({ name, size = 21 }: { name: IconName; size?: number }) {
  const common = { width: size, height: size, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 1.9, strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const, 'aria-hidden': true }
  if (name === 'menu') return <svg {...common}><path d="M4 7h16M4 12h16M4 17h16" /></svg>
  if (name === 'all') return <svg {...common}><path d="M21 15a4 4 0 0 1-4 4H8l-5 3 1.7-5.1A7 7 0 0 1 3 12V8a5 5 0 0 1 5-5h8a5 5 0 0 1 5 5z" /></svg>
  if (name === 'channel') return <svg {...common}><path d="m3 11 15-6v14L3 13z" /><path d="M8 14v5" /></svg>
  if (name === 'group') return <svg {...common}><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" /><circle cx="9" cy="7" r="4" /><path d="M22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75" /></svg>
  if (name === 'personal') return <svg {...common}><circle cx="12" cy="8" r="4" /><path d="M4 21a8 8 0 0 1 16 0" /></svg>
  if (name === 'favorite') return <svg {...common}><path d="m12 3 2.8 5.7 6.2.9-4.5 4.4 1.1 6.2-5.6-2.9-5.6 2.9 1.1-6.2L3 9.6l6.2-.9z" /></svg>
  if (name === 'settings') return <svg {...common}><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.7 1.7 0 0 0 .34 1.88l.06.06-2.83 2.83-.06-.06A1.7 1.7 0 0 0 15 19.4a1.7 1.7 0 0 0-1 .6 1.7 1.7 0 0 0-.4 1.1V21H9.6v-.09A1.7 1.7 0 0 0 8.5 19.4a1.7 1.7 0 0 0-1.88.34l-.06.06-2.83-2.83.06-.06A1.7 1.7 0 0 0 4.6 15a1.7 1.7 0 0 0-.6-1 1.7 1.7 0 0 0-1.1-.4H3V9.6h.09A1.7 1.7 0 0 0 4.6 8.5a1.7 1.7 0 0 0-.34-1.88l-.06-.06 2.83-2.83.06.06A1.7 1.7 0 0 0 9 4.6a1.7 1.7 0 0 0 1-.6 1.7 1.7 0 0 0 .4-1.1V3h4v.09A1.7 1.7 0 0 0 15.5 4.6a1.7 1.7 0 0 0 1.88-.34l.06-.06 2.83 2.83-.06.06A1.7 1.7 0 0 0 19.4 9c.2.36.5.7.9.9.33.18.7.28 1.1.28H21v4h-.09A1.7 1.7 0 0 0 19.4 15z" /></svg>
  if (name === 'plus') return <svg {...common}><path d="M12 5v14M5 12h14" /></svg>
  if (name === 'refresh') return <svg {...common}><path d="M20 6v5h-5M4 18v-5h5" /><path d="M18.5 9A7 7 0 0 0 6.2 6.2L4 9M5.5 15A7 7 0 0 0 17.8 17.8L20 15" /></svg>
  if (name === 'wordpress') return <svg {...common}><circle cx="12" cy="12" r="9" /><path d="M7.5 8.5 11 17l2.2-5.5M14.2 8.5 17 17M6 8.5h3M13 8.5h3" /></svg>
  if (name === 'logout') return <svg {...common}><path d="M10 17l5-5-5-5M15 12H3" /><path d="M14 3h5a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-5" /></svg>
  if (name === 'search') return <svg {...common}><circle cx="11" cy="11" r="7" /><path d="m20 20-4-4" /></svg>
  if (name === 'close') return <svg {...common}><path d="m6 6 12 12M18 6 6 18" /></svg>
  if (name === 'more') return <svg {...common}><circle cx="12" cy="5" r="1" fill="currentColor" stroke="none" /><circle cx="12" cy="12" r="1" fill="currentColor" stroke="none" /><circle cx="12" cy="19" r="1" fill="currentColor" stroke="none" /></svg>
  if (name === 'excel') return <svg {...common}><path d="M4 3h10l6 6v12H4z" /><path d="M14 3v6h6M8 13l4 5M12 13l-4 5" /></svg>
  if (name === 'calendar') return <svg {...common}><rect x="3" y="5" width="18" height="16" rx="2" /><path d="M16 3v4M8 3v4M3 10h18" /></svg>
  if (name === 'filter') return <svg {...common}><path d="M4 6h16M7 12h10M10 18h4" /></svg>
  return <svg {...common}><path d="M4 20V10M10 20V4M16 20v-7M22 20H2" /></svg>
}

function MaterialLegacyDialog({ children, close, locked = false, maxWidth = 'md' }: { children: ReactNode; close: () => void; locked?: boolean; maxWidth?: 'sm' | 'md' | 'lg' | 'xl' }) {
  const theme = useTheme()
  const fullScreen = useMediaQuery(theme.breakpoints.down('sm'))
  return <Dialog open fullScreen={fullScreen} fullWidth maxWidth={maxWidth} onClose={locked ? undefined : close}>
    <DialogContent className="material-legacy-dialog-content" sx={{ p: { xs: 1, sm: 1.5 }, bgcolor: 'background.default' }}>
      {children}
    </DialogContent>
  </Dialog>
}

export default function App() {
  const [status, setStatus] = useState<AuthStatus | null>(null)
  const [fatal, setFatal] = useState('')
  const [forceFreshLogin, setForceFreshLogin] = useState(false)
  const [loginEpoch, setLoginEpoch] = useState(0)
  const refreshStatus = useCallback(async () => {
    setFatal('')
    try {
      const next = await api<AuthStatus & { ok: true }>('GET', '/api/v1/auth/status')
      setStatus(next)
      if (next.authenticated) setForceFreshLogin(false)
    } catch (error) { setFatal(error instanceof Error ? error.message : 'سرویس محلی در دسترس نیست.') }
  }, [])
  const beginFreshLogin = useCallback(() => {
    setFatal(''); setForceFreshLogin(true); setLoginEpoch(value => value + 1)
    setStatus({ authenticated: false, session_present: false, password_pending: false, fresh_login_available: true })
  }, [])
  const handleAuthenticated = useCallback(async () => { setForceFreshLogin(false); await refreshStatus() }, [refreshStatus])
  useEffect(() => { void refreshStatus() }, [refreshStatus])
  let content: ReactNode
  if (fatal) content = <StartupError message={fatal} retry={refreshStatus} />
  else if (!status) content = <Splash />
  else if (forceFreshLogin) content = <LoginGate key={`fresh-login-${loginEpoch}`} onAuthenticated={handleAuthenticated} />
  else if (!status.authenticated && status.session_present && status.session_error) content = <SessionRecovery status={status} retry={refreshStatus} onFreshLogin={beginFreshLogin} />
  else if (!status.authenticated) content = <LoginGate key={`login-${loginEpoch}`} onAuthenticated={handleAuthenticated} />
  else {
    const sessionWarning = status.remote_warning
      ? `نشست محلی باز شد، اما بررسی ارتباط با ایتا موفق نبود${status.remote_error_type ? ` (${status.remote_error_type})` : ''}. همگام‌سازی را دوباره امتحان کنید.`
      : undefined
    content = <Workspace onLogout={refreshStatus} sessionWarning={sessionWarning} />
  }
  return <LoginAppearanceProvider><Box className="desktop-shell">{content}</Box></LoginAppearanceProvider>
}

function Splash() {
  return <LoginSurface><Box className="splash" sx={{ display: 'grid', placeItems: 'center', minHeight: 260 }}>
    <Stack alignItems="center" spacing={2}>
      <Box className="brand-mark">EB</Box>
      <Typography variant="h5">Eitaa Bridge</Typography>
      <CircularProgress size={32} aria-label="در حال آماده‌سازی" />
    </Stack>
  </Box></LoginSurface>
}
function StartupError({ message, retry }: { message: string; retry: () => void }) {
  return <LoginSurface><Stack spacing={2} alignItems="stretch">
    <Box className="brand-mark" alignSelf="center">!</Box>
    <Typography variant="h5" textAlign="center">راه‌اندازی انجام نشد</Typography>
    <Alert severity="error">{message}</Alert>
    <Button variant="contained" onClick={retry}>تلاش دوباره</Button>
  </Stack></LoginSurface>
}

function SessionRecovery({ status, retry, onFreshLogin }: { status: AuthStatus; retry: () => Promise<void> | void; onFreshLogin: () => void }) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const startFreshLogin = async () => {
    if (!confirm('نشست فعلی فقط بایگانی شود و صفحه ورود تازه باز شود؟ فایل پشتیبان حذف نخواهد شد.')) return
    setBusy(true); setError('')
    try {
      await api<{ login_ready?: boolean }>('POST', '/api/v1/auth/reset-local-session', { confirm: true })
      onFreshLogin()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'بایگانی نشست ناموفق بود.')
      setBusy(false)
    }
  }
  return <LoginSurface><Stack spacing={2}>
    <Box className="brand-mark" alignSelf="center">!</Box>
    <Typography variant="h5" textAlign="center">نشست ایتا موجود است</Typography>
    <Typography color="text.secondary">برنامه نشست شما را حذف نکرده است، اما هسته نتوانست آن را باز کند. این حالت می‌تواند موقت باشد یا فایل نشست واقعاً نامعتبر شده باشد.</Typography>
    <Alert severity="warning">کد: {status.session_error_code || 'auth_session_open_failed'}{status.session_error_type ? ` — ${status.session_error_type}` : ''}</Alert>
    {error && <Alert severity="error">{error}</Alert>}
    <Button variant="contained" disabled={busy} onClick={retry}>بررسی دوباره نشست</Button>
    {status.fresh_login_available !== false && <Button variant="outlined" disabled={busy} onClick={() => void startFreshLogin()}>
      {busy ? 'در حال بایگانی…' : 'بایگانی نشست و ورود تازه'}
    </Button>}
    <Typography variant="caption" color="text.secondary">ورود تازه فقط با انتخاب صریح شما آغاز می‌شود و فایل قبلی با پسوند .bak نگه داشته خواهد شد.</Typography>
  </Stack></LoginSurface>
}

function LoginGate({ onAuthenticated }: { onAuthenticated: () => Promise<void> | void }) {
  const [step, setStep] = useState<'phone' | 'code' | 'password'>('phone')
  const [phone, setPhone] = useState('+98')
  const phoneInputRef = useRef<HTMLInputElement | null>(null)
  const [code, setCode] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [hint, setHint] = useState('')
  useEffect(() => {
    if (step === 'phone') window.setTimeout(() => phoneInputRef.current?.focus(), 0)
  }, [step])
  const submit = async (event: FormEvent) => {
    event.preventDefault(); setBusy(true); setError('')
    try {
      if (step === 'phone') {
        const result = await api<any>('POST', '/api/v1/auth/request-code', { phone })
        setHint(`کد از طریق ${result.challenge?.delivery_type || 'ایتا'} ارسال شد.`); setStep('code')
      } else if (step === 'code') {
        const result = await api<any>('POST', '/api/v1/auth/submit-code', { code })
        if (result.step === 'password') { setHint('رمز دوم حساب را وارد کنید.'); setStep('password') }
        else await onAuthenticated()
      } else { await api('POST', '/api/v1/auth/submit-password', { password }); await onAuthenticated() }
    } catch (e) { setError(e instanceof Error ? e.message : 'ورود ناموفق بود.') }
    finally { setBusy(false) }
  }
  return <LoginSurface><Box component="form" className="login-form" onSubmit={submit} noValidate>
    <Stack spacing={2.25}>
      <Box className="login-provider-pill"><span>EB</span><b>حساب ایتا</b></Box>
      <Box>
        <Typography variant="h5" component="h2">ورود امن به ایتا</Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mt: .75, lineHeight: 1.9 }}>
          کد ورود فقط برای ساخت Session محلی استفاده می‌شود و اطلاعات گفتگو پیش از احراز هویت نمایش داده نخواهد شد.
        </Typography>
      </Box>
      <Box className="login-step-track" aria-label="مراحل ورود">
        {(['phone', 'code', 'password'] as const).map((item, index) => <Box
          key={item}
          className={`${step === item ? 'active' : ''} ${(['phone', 'code', 'password'] as const).indexOf(step) > index ? 'done' : ''}`}
        >
          <span>{(index + 1).toLocaleString('fa-IR')}</span>
          <small>{item === 'phone' ? 'شماره' : item === 'code' ? 'کد' : 'رمز دوم'}</small>
        </Box>)}
      </Box>
      {step === 'phone' && <TextField inputRef={phoneInputRef} label="شماره تلفن ایتا" type="tel" name="phone" dir="ltr" autoComplete="tel" value={phone} onChange={e => setPhone(e.target.value)} placeholder="+98912…" slotProps={{ htmlInput: { inputMode: 'tel', spellCheck: false, dir: 'ltr' } }} helperText="شماره را با کد کشور وارد کنید؛ نمونه: ‎+98912…" />}
      {step === 'code' && <TextField label="کد یک‌بارمصرف" dir="ltr" autoFocus value={code} onChange={e => setCode(e.target.value)} autoComplete="one-time-code" slotProps={{ htmlInput: { dir: 'ltr', inputMode: 'numeric' } }} />}
      {step === 'password' && <TextField label="رمز دوم حساب" type="password" autoFocus value={password} onChange={e => setPassword(e.target.value)} autoComplete="current-password" />}
      <Box aria-live="polite">{hint && <Alert severity="info">{hint}</Alert>}{error && <Alert severity="error">{error}</Alert>}</Box>
      <Button type="submit" size="large" variant="contained" disabled={busy} startIcon={busy ? <CircularProgress size={18} color="inherit" /> : undefined}>
        {busy ? 'در حال بررسی…' : step === 'phone' ? 'دریافت کد ورود' : 'ادامه ورود'}
      </Button>
      {step !== 'phone' && <Button type="button" variant="text" onClick={() => { setStep('phone'); setCode(''); setPassword(''); setHint('') }}>ورود با شماره‌ای دیگر</Button>}
      <Typography variant="caption" color="text.secondary" textAlign="center" sx={{ lineHeight: 1.8 }}>
        نسخهٔ فعلی یک حساب فعال را باز می‌کند؛ پشتیبانی چندحسابی واقعی فقط با Session و Scheduler مستقل برای هر حساب فعال خواهد شد.
      </Typography>
    </Stack>
  </Box></LoginSurface>
}

function Workspace({ onLogout, sessionWarning }: { onLogout: () => void; sessionWarning?: string }) {
  const { resolvedMode } = useColorMode()
  const [sites, setSites] = useState<Site[]>([])
  const [siteKey, setSiteKey] = useState('')
  const [dialogs, setDialogs] = useState<DialogItem[]>([])
  const [dialog, setDialog] = useState<DialogItem | null>(null)
  const [messages, setMessages] = useState<MessageItem[]>([])
  const [tab, setTab] = useState<Tab>(() => readStored<Tab>(STORAGE.tab, 'all'))
  const [dialogSearch, setDialogSearch] = useState('')
  const [messageSearch, setMessageSearch] = useState('')
  const [jalaliFrom, setJalaliFrom] = useState('')
  const [dateMode, setDateMode] = useState<'day' | 'from'>('from')
  const [dateRange, setDateRange] = useState<{ from: string; to: string } | null>(null)
  const [loadingDateRange, setLoadingDateRange] = useState(false)
  const [loadingDialogs, setLoadingDialogs] = useState(false)
  const [syncingDialogs, setSyncingDialogs] = useState(false)
  const [loadingMessages, setLoadingMessages] = useState(false)
  const [selectedKeys, setSelectedKeys] = useState<string[]>([])
  const [selectionMode, setSelectionMode] = useState(false)
  const [activeUsage, setActiveUsage] = useState<{ message: MessageItem; usage: MessageUsage } | null>(null)
  const [categories, setCategories] = useState<Term[]>([])
  const [tags, setTags] = useState<Term[]>([])
  const [media, setMedia] = useState<Record<string, string | null>>({})
  const [fullMedia, setFullMedia] = useState<Record<string, string | null>>({})
  const mediaCacheRef = useRef<Record<string, string | null>>({})
  const fullMediaCacheRef = useRef<Record<string, string | null>>({})
  const mediaRequestsRef = useRef<Set<string>>(new Set())
  const fullMediaRequestsRef = useRef<Set<string>>(new Set())
  useEffect(() => { mediaCacheRef.current = media }, [media])
  useEffect(() => { fullMediaCacheRef.current = fullMedia }, [fullMedia])
  const [mediaViewer, setMediaViewer] = useState<{ key: string; title: string } | null>(null)
  const [composerOpen, setComposerOpen] = useState(false)
  const [chatsOpen, setChatsOpen] = useState(false)
  const [communityOpen, setCommunityOpen] = useState(false)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [bulkOpen, setBulkOpen] = useState(false)
  const [bulkMode, setBulkMode] = useState<BulkMode>('members')
  const [bulkMemberIds, setBulkMemberIds] = useState<number[]>([])
  const [bulkInitialNumbers, setBulkInitialNumbers] = useState<string[]>([])
  const [membersOpen, setMembersOpen] = useState(false)
  const [railMenuOpen, setRailMenuOpen] = useState(false)
  const [manualOpen, setManualOpen] = useState(false)
  const [contactsOpen, setContactsOpen] = useState(false)
  const [mediaDisplay, setMediaDisplay] = useState<'dynamic' | 'framed'>(() => readStored<'dynamic' | 'framed'>(STORAGE.mediaDisplay, 'dynamic'))
  const [dialogMenuKey, setDialogMenuKey] = useState<string | null>(null)
  const [contentFiltersOpen, setContentFiltersOpen] = useState(false)
  const [indexWorkbenchTab, setIndexWorkbenchTab] = useState<IndexWorkbenchTab>('index')
  const [showWordPressUsed, setShowWordPressUsed] = useState(true)
  const [selectedIndexLabel, setSelectedIndexLabel] = useState<number | null>(null)
  const [selectedSenderKey, setSelectedSenderKey] = useState<string | null>(null)
  const [contentIndexResults, setContentIndexResults] = useState<Record<number, ContentIndexResult>>({})
  const [contentIndexLabels, setContentIndexLabels] = useState<Array<{ id: number; name: string }>>([])
  const [contentIndexJob, setContentIndexJob] = useState<ContentIndexJob | null>(null)
  const [contentIndexAliases, setContentIndexAliases] = useState<Record<number, string[]>>({})
  const [contentIndexNames, setContentIndexNames] = useState<Record<number, string>>({})
  const [customIndexes, setCustomIndexes] = useState<IndexDefinition[]>([])
  const [indexKeywordCategoryId, setIndexKeywordCategoryId] = useState<number | null>(null)
  const [indexNameDraft, setIndexNameDraft] = useState('')
  const [indexKeywordDraft, setIndexKeywordDraft] = useState('')
  const [customIndexName, setCustomIndexName] = useState('')
  const [customIndexKeywords, setCustomIndexKeywords] = useState('')
  const [customIndexCategoryId, setCustomIndexCategoryId] = useState<number | null>(null)
  const [indexEditor, setIndexEditor] = useState<{ message: MessageItem; messageIds: number[]; selectedIds: number[] } | null>(null)
  const [savingIndexEditor, setSavingIndexEditor] = useState(false)
  const [dateJump, setDateJump] = useState<{ messageId: number; epoch: number } | null>(null)
  const activeSite = useMemo(() => sites.find(site => site.site_key === siteKey), [sites, siteKey])
  const wordpressAvailable = useMemo(() => sites.some(site => site.credentials_configured), [sites])
  const viewportPageSize = useMemo(() => Math.max(20, Math.min(80, Math.ceil(window.innerHeight / 90) + 10)), [])
  const lastReadRef = useRef<Record<string, number>>({})
  const syncTimesRef = useRef<Record<string, number>>(readStored<Record<string, number>>(STORAGE.syncTimes, {}))
  const newerCheckRef = useRef<Record<string, number>>({})
  const dialogsLoadedRef = useRef(false)
  const activeMessagePeerRef = useRef<string | null>(null)
  const messageScrollMemoryRef = useRef<Map<string, MessageScrollMemory>>(new Map())
  const messageCacheRef = useRef<Map<string, MessageItem[]>>(new Map())
  const [composerDocked, setComposerDocked] = useState(() => window.matchMedia('(min-width: 1500px)').matches)
  const [chatsDocked, setChatsDocked] = useState(() => window.matchMedia('(min-width: 821px)').matches)
  useEffect(() => {
    const composerQuery = window.matchMedia('(min-width: 1500px)')
    const chatsQuery = window.matchMedia('(min-width: 821px)')
    const update = () => {
      setComposerDocked(composerQuery.matches); setChatsDocked(chatsQuery.matches)
      if (composerQuery.matches) setComposerOpen(false)
      if (chatsQuery.matches) setChatsOpen(false)
    }
    update(); composerQuery.addEventListener('change', update); chatsQuery.addEventListener('change', update)
    return () => { composerQuery.removeEventListener('change', update); chatsQuery.removeEventListener('change', update) }
  }, [])
  useEffect(() => {
    if (sessionWarning) toast.warn(sessionWarning, { toastId: 'session-remote-warning' })
  }, [sessionWarning])
  useEffect(() => { writeStored(STORAGE.tab, tab) }, [tab])
  useEffect(() => { writeStored(STORAGE.mediaDisplay, mediaDisplay) }, [mediaDisplay])
  useEffect(() => { if (siteKey) writeStored(STORAGE.siteKey, siteKey) }, [siteKey])
  useEffect(() => { if (dialog) writeStored(STORAGE.peerKey, dialog.peer_key) }, [dialog?.peer_key])

  const openBulk = useCallback((mode: BulkMode, memberIds: number[] = [], numbers: string[] = []) => {
    setBulkMode(mode)
    setBulkMemberIds(memberIds)
    setBulkInitialNumbers(numbers)
    setBulkOpen(true)
  }, [])

  const applyDialogs = useCallback((items: DialogItem[]) => {
    setDialogs(items)
    setDialog(current => {
      const storedPeer = readStored<string>(STORAGE.peerKey, '')
      const selected = current
        ? items.find(item => item.peer_key === current.peer_key) || current
        : items.find(item => item.peer_key === storedPeer) || items[0] || null
      if (selected) writeStored(STORAGE.peerKey, selected.peer_key)
      return selected
    })
  }, [])

  const selectDialog = useCallback((selected: DialogItem) => {
    // Commit the selected peer and its cached message window in the same React
    // batch. This prevents a transient render where the new dialog is paired
    // with the previous dialog's messages, which would corrupt scroll memory.
    activeMessagePeerRef.current = selected.peer_key
    setMessages(messageCacheRef.current.get(selected.peer_key) || [])
    setSelectedKeys([])
    setSelectionMode(false)
    setActiveUsage(null)
    setContentIndexResults({})
    setContentIndexLabels([])
    setSelectedIndexLabel(null)
    setSelectedSenderKey(null)
    setContentIndexJob(null)
    setIndexEditor(null)
    setDateJump(null)
    setContentFiltersOpen(false)
    setDialog(selected)
    setChatsOpen(false)
  }, [])

  const loadSites = useCallback(async () => {
    const response = await api<{ sites: Site[]; default_site_key: string }>('GET', '/api/v1/sites')
    setSites(response.sites)
    setSiteKey(current => {
      const stored = readStored<string>(STORAGE.siteKey, '')
      const candidate = current || stored || response.default_site_key
      const candidateSite = response.sites.find(site => site.site_key === candidate)
      const readySite = response.sites.find(site => site.credentials_configured)
      const selected = candidateSite?.credentials_configured
        ? candidateSite.site_key
        : readySite?.site_key || candidateSite?.site_key || response.default_site_key
      writeStored(STORAGE.siteKey, selected)
      return selected
    })
  }, [])

  const syncDialogs = useCallback(async (options?: { silent?: boolean }) => {
    if (!siteKey || syncingDialogs) return
    const previousCount = dialogs.length
    setSyncingDialogs(true)
    try {
      const started = await api<{ job: { job_id: string; state: string } }>('POST', '/api/v1/dialogs/sync/start', { site_key: siteKey, page_size: 100, max_pages: 100 })
      let job: any = started.job
      for (let attempt = 0; attempt < 600 && ['queued', 'running'].includes(job.state); attempt += 1) {
        await new Promise(resolve => window.setTimeout(resolve, 750))
        const status = await api<{ job: any }>('GET', query('/api/v1/dialogs/sync/status', { job_id: job.job_id }))
        job = status.job
      }
      if (job.state === 'failed') throw new Error(job.error?.message || 'همگام‌سازی گفتگوها ناموفق بود.')
      if (job.state !== 'completed') throw new Error('همگام‌سازی گفتگوها بیش از حد طول کشید؛ سرویس همچنان فعال است.')
      const response = job.result as { dialogs: DialogItem[]; sync: { completed: boolean; warning_codes: string[]; pages_fetched: number; server_total_count?: number | null; remote_unique_count?: number; duplicate_count?: number; skipped_unusable_count?: number; counts_by_kind?: Record<string, number> } }
      applyDialogs(response.dialogs)
      const warnings = response.sync.warning_codes || []
      const added = Math.max(0, response.dialogs.length - previousCount)
      if (!options?.silent) {
        const remote = response.sync.remote_unique_count ?? response.dialogs.length
        const total = response.sync.server_total_count
        const skipped = response.sync.skipped_unusable_count || 0
        const summary = total ? `${remote} گفتگوی قابل استفاده از ${total} مورد سرور در ${response.sync.pages_fetched} صفحه` : `${remote} گفتگو در ${response.sync.pages_fetched} صفحه`
        const actionableWarnings = warnings.filter(code => !code.includes('unusable_peer_missing_access_hash') && !code.startsWith('stabilization_restart:'))
        if (actionableWarnings.length || !response.sync.completed) toast.warning(`همگام‌سازی واقعاً ناقص ماند: ${summary}`)
        else toast.success(`${summary} کامل شد${skipped ? `؛ ${skipped} گفتگوی حذف‌شده یا غیرقابل استفاده کنار گذاشته شد` : ''}${added ? `؛ ${added} مورد جدید` : ''}`)
      }
    } catch (e) { toast.error(e instanceof Error ? e.message : 'همگام‌سازی گفتگوها ناموفق بود.') }
    finally { setSyncingDialogs(false) }
  }, [siteKey, syncingDialogs, dialogs.length, applyDialogs])

  const loadDialogs = useCallback(async () => {
    if (!siteKey) return
    setLoadingDialogs(true)
    try {
      const response = await api<{ dialogs: DialogItem[]; sync?: { deferred?: boolean } }>('POST', '/api/v1/dialogs/list', { site_key: siteKey, refresh_if_empty: true })
      applyDialogs(response.dialogs)
      if (!response.dialogs.length && response.sync?.deferred) {
        await syncDialogs()
      }
    } catch (e) { toast.error(e instanceof Error ? e.message : 'دریافت گفتگوها ناموفق بود.') }
    finally { setLoadingDialogs(false) }
  }, [siteKey, applyDialogs, syncDialogs])

  const loadTerms = useCallback(async (force = false) => {
    if (!siteKey || !activeSite?.credentials_configured) {
      setCategories([]); setTags([])
      return
    }
    const allCached = readStored<Record<string, { at: number; categories: Term[]; tags: Term[] }>>(STORAGE.terms, {})
    const cached = allCached[siteKey]
    if (cached) { setCategories(cached.categories); setTags(cached.tags) }
    if (!force && cached && Date.now() - cached.at < TERM_CACHE_TTL_MS) return
    try {
      const [c, t] = await Promise.all([
        api<{ terms: Term[] }>('GET', query('/api/v1/wordpress/categories', { site_key: siteKey, per_page: 100 })),
        api<{ terms: Term[] }>('GET', query('/api/v1/wordpress/tags', { site_key: siteKey, per_page: 100 })),
      ])
      setCategories(c.terms); setTags(t.terms)
      writeStored(STORAGE.terms, { ...allCached, [siteKey]: { at: Date.now(), categories: c.terms, tags: t.terms } })
    } catch (e) {
      if (!cached) toast.error(e instanceof Error ? e.message : 'دریافت دسته‌ها و کلمات کلیدی ناموفق بود.')
      else toast.warning('دسته‌ها و کلمات کلیدی از حافظه محلی نمایش داده شدند؛ تازه‌سازی وردپرس فعلاً ناموفق بود.')
    }
  }, [siteKey, activeSite?.credentials_configured])

  const listMessages = useCallback(async (selected: DialogItem, beforeId?: number, limit = viewportPageSize) => {
    const response = await api<{ messages: MessageItem[] }>('POST', '/api/v1/messages/list', { site_key: siteKey, peer_file: selected.peer_file, limit, before_id: beforeId })
    return [...response.messages].reverse()
  }, [siteKey, viewportPageSize])

  const markDialogRead = useCallback(async (selected: DialogItem, maxId: number, remainingUnreadCount: number) => {
    if (!siteKey || maxId < 1 || lastReadRef.current[selected.peer_key] === maxId) return
    lastReadRef.current[selected.peer_key] = maxId
    try {
      await api('POST', '/api/v1/messages/read/enqueue', {
        site_key: siteKey,
        peer_file: selected.peer_file,
        max_id: maxId,
        remaining_unread_count: remainingUnreadCount,
      })
      // The UI does not optimistically rewrite unread counters. The API updates
      // both Eitaa and the local snapshots only after the server accepts the RPC.
      window.setTimeout(() => { void loadDialogs() }, 4200)
    } catch {
      delete lastReadRef.current[selected.peer_key]
      toast.warning('ثبت خوانده‌شدن در صف انجام نشد؛ نمایش پیام‌ها ادامه دارد.')
    }
  }, [siteKey, loadDialogs])

  const rememberMessageSync = useCallback((peerKey: string) => {
    syncTimesRef.current = { ...syncTimesRef.current, [peerKey]: Date.now() }
    writeStored(STORAGE.syncTimes, syncTimesRef.current)
  }, [])

  const rememberDialogMessages = useCallback((peerKey: string, items: MessageItem[]) => {
    const cache = messageCacheRef.current
    cache.delete(peerKey)
    cache.set(peerKey, items)
    while (cache.size > 8) {
      const oldestKey = cache.keys().next().value as string | undefined
      if (!oldestKey) break
      cache.delete(oldestKey)
      messageScrollMemoryRef.current.delete(oldestKey)
    }
  }, [])

  const refreshLocalMessages = useCallback(async (selected: DialogItem, limit?: number) => {
    const unreadCount = Math.max(0, selected.unread_count || 0)
    const selectedLimit = limit ?? Math.min(500, Math.max(viewportPageSize, unreadCount + 15))
    const loaded = await listMessages(selected, undefined, selectedLimit)
    const cached = messageCacheRef.current.get(selected.peer_key) || []
    const merged = mergeMessagesById(cached, loaded)
    rememberDialogMessages(selected.peer_key, merged)
    if (activeMessagePeerRef.current === selected.peer_key) setMessages(merged)
    return merged
  }, [listMessages, rememberDialogMessages, viewportPageSize])

  const syncDialogMessages = useCallback(async (selected: DialogItem, options?: { force?: boolean; silent?: boolean; local?: MessageItem[] }) => {
    const lastSync = syncTimesRef.current[selected.peer_key] || 0
    if (!options?.force && Date.now() - lastSync < REMOTE_MESSAGE_TTL_MS) return options?.local || []
    const unreadCount = Math.max(0, selected.unread_count || 0)
    const initialLimit = Math.min(500, Math.max(viewportPageSize, unreadCount + 15))
    const local = options?.local || []
    const newestLocalId = local.length ? local[local.length - 1].id : 0
    const remoteAhead = Boolean(selected.top_message_id && selected.top_message_id > newestLocalId)
    const pages = !local.length ? Math.max(1, Math.min(20, Math.ceil(initialLimit / 25))) : remoteAhead || unreadCount > 0 ? Math.max(1, Math.min(6, Math.ceil(Math.max(unreadCount, viewportPageSize) / 50))) : 1
    setLoadingMessages(true)
    try {
      await api('POST', '/api/v1/messages/sync', {
        site_key: siteKey,
        peer_file: selected.peer_file,
        pages,
        page_size: Math.min(100, Math.max(25, initialLimit)),
        offset_id: 0,
        stop_when_unchanged: true,
      })
      rememberMessageSync(selected.peer_key)
      let loaded = await listMessages(selected, undefined, initialLimit)
      const readBoundary = selected.read_inbox_max_id || 0
      for (let attempt = 0; attempt < 4 && readBoundary > 0 && loaded.length && loaded[0].id > readBoundary && loaded.length < 500; attempt += 1) {
        const oldest = loaded[0].id
        await api('POST', '/api/v1/messages/sync', {
          site_key: siteKey,
          peer_file: selected.peer_file,
          pages: 1,
          page_size: 100,
          offset_id: oldest,
          stop_when_unchanged: false,
        })
        const expanded = await listMessages(selected, undefined, Math.min(500, loaded.length + 100))
        if (expanded.length <= loaded.length) break
        loaded = expanded
      }
      const merged = mergeMessagesById(local, loaded)
      rememberDialogMessages(selected.peer_key, merged)
      if (activeMessagePeerRef.current === selected.peer_key) {
        setMessages(current => mergeMessagesById(current, loaded))
      }
      return merged
    } catch (e) {
      if (!options?.silent) toast.warning(e instanceof Error ? e.message : 'تازه‌سازی پیام‌ها ناموفق بود؛ نسخه ذخیره‌شده نمایش داده می‌شود.')
      return local
    } finally { setLoadingMessages(false) }
  }, [listMessages, rememberDialogMessages, rememberMessageSync, siteKey, viewportPageSize])

  const loadDialogMessages = useCallback(async (selected: DialogItem) => {
    activeMessagePeerRef.current = selected.peer_key
    const cached = messageCacheRef.current.get(selected.peer_key) || []
    setMessages(cached); setSelectedKeys([]); setSelectionMode(false); setActiveUsage(null); setDateRange(null); setJalaliFrom(''); setLoadingMessages(true)
    try {
      const local = await refreshLocalMessages(selected, cached.length ? Math.min(5000, Math.max(viewportPageSize, cached.length)) : undefined)
      setLoadingMessages(false)
      const newestLocalId = local.length ? local[local.length - 1].id : 0
      const lastSync = syncTimesRef.current[selected.peer_key] || 0
      const remoteAhead = Boolean(selected.top_message_id && selected.top_message_id > newestLocalId)
      const unreadMissing = selected.unread_count > local.filter(message => !message.outgoing && message.id > (selected.read_inbox_max_id || 0)).length
      const shouldSync = !local.length || remoteAhead || unreadMissing || Date.now() - lastSync >= REMOTE_MESSAGE_TTL_MS
      if (shouldSync) void syncDialogMessages(selected, { silent: Boolean(local.length), local })
    } catch (e) {
      setLoadingMessages(false)
      toast.error(e instanceof Error ? e.message : 'خواندن حافظه محلی پیام‌ها ناموفق بود.')
    }
  }, [refreshLocalMessages, syncDialogMessages])

  useEffect(() => { void loadSites() }, [loadSites])
  useEffect(() => {
    if (!siteKey || dialogsLoadedRef.current) return
    dialogsLoadedRef.current = true
    void loadDialogs()
  }, [siteKey, loadDialogs])
  useEffect(() => { if (siteKey) void loadTerms() }, [siteKey, loadTerms])
  useEffect(() => {
    if (!siteKey) {
      setContentIndexAliases({})
      setContentIndexNames({})
      setCustomIndexes([])
      setIndexKeywordCategoryId(null)
      setIndexNameDraft('')
      setIndexKeywordDraft('')
      return
    }
    setContentIndexAliases(readStored<Record<number, string[]>>(`${STORAGE.indexAliases}.${siteKey}`, {}))
    setContentIndexNames(readStored<Record<number, string>>(`${STORAGE.indexNames}.${siteKey}`, {}))
    setCustomIndexes(readStored<IndexDefinition[]>(`${STORAGE.customIndexes}.${siteKey}`, []))
    setIndexKeywordCategoryId(null)
    setIndexNameDraft('')
    setIndexKeywordDraft('')
  }, [siteKey])
  const indexDefinitions = useMemo<IndexDefinition[]>(() => {
    const categoryDefinitions = categories.map(item => ({
      id: item.id,
      name: contentIndexNames[item.id] || item.name,
      aliases: contentIndexAliases[item.id] || [],
      kind: 'wordpress-category' as const,
      wordpressCategoryId: item.id,
    }))
    const tagDefinitions = tags.map(item => {
      const id = WORDPRESS_TAG_INDEX_OFFSET + item.id
      return {
        id,
        name: contentIndexNames[id] || item.name,
        aliases: contentIndexAliases[id] || [],
        kind: 'wordpress-tag' as const,
        wordpressCategoryId: null,
      }
    })
    return [...categoryDefinitions, ...customIndexes, ...tagDefinitions]
  }, [categories, contentIndexAliases, contentIndexNames, customIndexes, tags])
  useEffect(() => {
    if (!indexDefinitions.length) {
      setIndexKeywordCategoryId(null)
      setIndexNameDraft('')
      setIndexKeywordDraft('')
      return
    }
    const selectedId = indexKeywordCategoryId && indexDefinitions.some(item => item.id === indexKeywordCategoryId)
      ? indexKeywordCategoryId
      : indexDefinitions[0].id
    const selectedDefinition = indexDefinitions.find(item => item.id === selectedId)
    if (selectedId !== indexKeywordCategoryId) setIndexKeywordCategoryId(selectedId)
    setIndexNameDraft(selectedDefinition?.name || '')
    setIndexKeywordDraft((selectedDefinition?.aliases || []).join('، '))
  }, [indexDefinitions, indexKeywordCategoryId])
  useEffect(() => { if (dialog && siteKey) void loadDialogMessages(dialog) }, [dialog?.peer_key]) // eslint-disable-line react-hooks/exhaustive-deps

  const loadOlder = useCallback(async () => {
    if (!dialog || loadingMessages || !messages.length) return 0
    const selected = dialog
    setLoadingMessages(true)
    try {
      const oldest = messages[0].id
      let older = await listMessages(selected, oldest)
      if (!older.length) {
        await api('POST', '/api/v1/messages/sync', { site_key: siteKey, peer_file: selected.peer_file, pages: 1, page_size: viewportPageSize, offset_id: oldest, stop_when_unchanged: false })
        rememberMessageSync(selected.peer_key)
        older = await listMessages(selected, oldest)
      }
      if (activeMessagePeerRef.current !== selected.peer_key) return 0
      const currentIds = new Set(messages.map(message => message.id))
      const added = older.filter(message => !currentIds.has(message.id)).length
      setMessages(current => {
        const merged = mergeMessagesById(current, older)
        rememberDialogMessages(selected.peer_key, merged)
        return merged
      })
      return added
    } catch (e) { toast.error(e instanceof Error ? e.message : 'بازیابی پیام‌های قدیمی‌تر ناموفق بود.'); return 0 }
    finally { setLoadingMessages(false) }
  }, [dialog, listMessages, loadingMessages, messages, rememberDialogMessages, rememberMessageSync, siteKey, viewportPageSize])

  const loadNewer = useCallback(async (force = false) => {
    if (!dialog || loadingMessages) return
    const previous = newerCheckRef.current[dialog.peer_key] || 0
    if (!force && Date.now() - previous < AUTO_NEWER_TTL_MS) return
    newerCheckRef.current[dialog.peer_key] = Date.now()
    const current = messages
    await syncDialogMessages(dialog, { force, silent: !force, local: current })
    if (force) toast.success('پیام‌های جدید بررسی و حافظه محلی به‌روز شد.')
  }, [dialog, loadingMessages, messages, syncDialogMessages])

  const loadFromJalaliDate = useCallback(async (selectedValue?: string, selectedMode?: 'day' | 'from') => {
    if (!dialog || !siteKey) return
    const value = selectedValue || jalaliFrom
    const mode = selectedMode || dateMode
    const start = parseJalaliDate(value)
    if (!start) { toast.warning('تاریخ شمسی انتخاب‌شده معتبر نیست.'); return }
    const now = new Date()
    if (start > now) { toast.warning('تاریخ انتخاب‌شده در آینده است.'); return }
    const selectedDayEnd = new Date(start.getFullYear(), start.getMonth(), start.getDate() + 1, 0, 0, 0, -1)
    let end = mode === 'day' ? selectedDayEnd : now
    setJalaliFrom(value); setDateMode(mode); setLoadingDateRange(true)
    try {
      let request = {
        site_key: siteKey,
        peer_file: dialog.peer_file,
        date_from: start.toISOString(),
        date_to: end.toISOString(),
        limit: 5000,
      }
      let response = await api<{ messages: MessageItem[] }>('POST', '/api/v1/messages/list', request)
      let source = 'حافظه محلی'
      if (!response.messages.length) {
        await api('POST', '/api/v1/messages/date-range/sync', {
          site_key: siteKey,
          peer_file: dialog.peer_file,
          date_from: start.toISOString(),
          date_to: end.toISOString(),
          pages: 100,
          page_size: 100,
        })
        response = await api<{ messages: MessageItem[] }>('POST', '/api/v1/messages/list', request)
        source = 'سرور ایتا و حافظه محلی'
      }
      // In "day" mode an empty day must not strand the user.  Continue from
      // that midnight and target the earliest stored message after it.
      if (!response.messages.length && mode === 'day') {
        end = now
        request = { ...request, date_to: end.toISOString() }
        response = await api<{ messages: MessageItem[] }>('POST', '/api/v1/messages/list', request)
        if (!response.messages.length) {
          await api('POST', '/api/v1/messages/date-range/sync', {
            site_key: siteKey,
            peer_file: dialog.peer_file,
            date_from: start.toISOString(),
            date_to: end.toISOString(),
            pages: 100,
            page_size: 100,
          })
          response = await api<{ messages: MessageItem[] }>('POST', '/api/v1/messages/list', request)
          source = 'سرور ایتا و حافظه محلی'
        }
      }
      const chronological = [...response.messages].sort((left, right) => (
        new Date(left.date).getTime() - new Date(right.date).getTime() || left.id - right.id
      ))
      setMessages(chronological)
      setDateRange({ from: start.toISOString(), to: end.toISOString() })
      if (chronological.length) {
        setDateJump(current => ({ messageId: chronological[0].id, epoch: (current?.epoch || 0) + 1 }))
        const exactDay = jalaliDayKey(chronological[0].date) === jalaliDayKey(start.toISOString())
        toast.success(`${chronological.length} پیام از ${source} بارگذاری شد؛ روی ${exactDay ? 'اولین پیام تاریخ انتخابی' : 'اولین پیام پس از تاریخ انتخابی'} قرار گرفت.`)
      } else {
        setDateJump(null)
        toast.info('در تاریخ انتخابی یا پس از آن پیامی در محدودهٔ قابل بازیابی یافت نشد.')
      }
    } catch (e) { toast.error(e instanceof Error ? e.message : 'بازیابی پیام‌ها بر اساس تاریخ ناموفق بود.') }
    finally { setLoadingDateRange(false) }
  }, [dialog, siteKey, jalaliFrom, dateMode])

  const clearDateRange = useCallback(async () => {
    if (!dialog) return
    setDateRange(null); setJalaliFrom(''); setDateJump(null)
    setLoadingMessages(true)
    try { await refreshLocalMessages(dialog) }
    finally { setLoadingMessages(false) }
  }, [dialog, refreshLocalMessages])

  const refreshCurrentLocalView = useCallback(async () => {
    if (!dialog || !siteKey) return
    // وردپرس writes can update only local usage/publication metadata. Refresh
    // exactly the current local view without invoking Eitaa and without collapsing
    // an already expanded or date-filtered message list back to the first page.
    if (dateRange) {
      const response = await api<{ messages: MessageItem[] }>('POST', '/api/v1/messages/list', {
        site_key: siteKey,
        peer_file: dialog.peer_file,
        date_from: dateRange.from,
        date_to: dateRange.to,
        limit: Math.max(100, messages.length),
      })
      setMessages([...response.messages].reverse())
      return
    }
    await refreshLocalMessages(dialog, Math.min(5000, Math.max(viewportPageSize, messages.length)))
  }, [dateRange, dialog, messages.length, refreshLocalMessages, siteKey, viewportPageSize])


  const markWordPressSourcesUsed = useCallback((sourceKeys: string[], publication: { composition_key: string; post_id: number; post_url?: string | null; status: string; title: string }) => {
    const targets = new Set(sourceKeys)
    const applyUsage = (peerKey: string, items: MessageItem[]) => items.map(message => {
      const key = stableMessageKey(peerKey, message.id)
      if (!targets.has(key)) return message
      const composition = {
        composition_key: publication.composition_key,
        post_id: publication.post_id,
        post_url: publication.post_url || null,
        status: publication.status,
        title: publication.title,
        updated_at: new Date().toISOString(),
      }
      const compositions = [composition, ...message.usage.compositions.filter(item => item.composition_key !== publication.composition_key)]
      return {
        ...message,
        usage: {
          ...message.usage,
          used: true,
          usage_state: 'used' as const,
          stale: false,
          publication_status: 'published',
          external_post_id: String(publication.post_id),
          external_url: publication.post_url || null,
          compositions,
        },
      }
    })

    const cachedEntries = [...messageCacheRef.current.entries()]
    for (const [peerKey, items] of cachedEntries) {
      if (!sourceKeys.some(key => key.startsWith(`${peerKey}:`))) continue
      rememberDialogMessages(peerKey, applyUsage(peerKey, items))
    }
    if (dialog) setMessages(current => applyUsage(dialog.peer_key, current))
  }, [dialog, rememberDialogMessages])

  const loadMedia = useCallback(async (message: MessageItem) => {
    if (!dialog) return
    const key = messageKey(dialog, message)
    if (key in mediaCacheRef.current || mediaRequestsRef.current.has(key)) return
    mediaRequestsRef.current.add(key)
    mediaCacheRef.current[key] = null
    setMedia(current => key in current ? current : ({ ...current, [key]: null }))
    try {
      const response = await api<{ media_url?: string; data_url?: string }>('POST', '/api/v1/messages/media-preview', {
        site_key: siteKey,
        peer_file: dialog.peer_file,
        message_id: message.id,
        quality: 'thumbnail',
      })
      const resolved = response.media_url ? mediaUrl(response.media_url) : response.data_url || ''
      mediaCacheRef.current[key] = resolved
      setMedia(current => ({ ...current, [key]: resolved }))
    } catch {
      mediaCacheRef.current[key] = ''
      setMedia(current => ({ ...current, [key]: '' }))
    } finally {
      mediaRequestsRef.current.delete(key)
    }
  }, [dialog, siteKey])

  const openFullMedia = useCallback(async (message: MessageItem) => {
    if (!dialog) return
    const key = messageKey(dialog, message)
    setMediaViewer({ key, title: `تصویر پیام #${message.id}` })
    if (key in fullMediaCacheRef.current || fullMediaRequestsRef.current.has(key)) return
    fullMediaRequestsRef.current.add(key)
    fullMediaCacheRef.current[key] = null
    setFullMedia(current => key in current ? current : ({ ...current, [key]: null }))
    try {
      const response = await api<{ media_url?: string; data_url?: string }>('POST', '/api/v1/messages/media-preview', {
        site_key: siteKey,
        peer_file: dialog.peer_file,
        message_id: message.id,
        quality: 'full',
        max_bytes: 128 * 1024 * 1024,
      })
      const resolved = response.media_url ? mediaUrl(response.media_url) : response.data_url || ''
      fullMediaCacheRef.current[key] = resolved
      setFullMedia(current => ({ ...current, [key]: resolved }))
    } catch (e) {
      fullMediaCacheRef.current[key] = ''
      setFullMedia(current => ({ ...current, [key]: '' }))
      toast.error(e instanceof Error ? e.message : 'دریافت تصویر اصلی ناموفق بود.')
    } finally {
      fullMediaRequestsRef.current.delete(key)
    }
  }, [dialog, siteKey])

  const loadContentIndexResults = useCallback(async (selected: DialogItem) => {
    try {
      const response = await api<{
        results: ContentIndexResult[]
        labels: Array<{ id: number; name: string }>
      }>('POST', '/api/v1/messages/index/results', {
        site_key: siteKey,
        peer_file: selected.peer_file,
        limit: 5_000,
      })
      setContentIndexResults(Object.fromEntries(response.results.map(item => [item.message_id, item])))
      setContentIndexLabels(response.labels)
      setSelectedIndexLabel(current => current && response.labels.some(item => item.id === current) ? current : null)
    } catch {
      setContentIndexResults({})
      setContentIndexLabels([])
    }
  }, [siteKey])

  useEffect(() => {
    if (!dialog || !siteKey) return
    void loadContentIndexResults(dialog)
  }, [dialog?.peer_key, siteKey, loadContentIndexResults]) // eslint-disable-line react-hooks/exhaustive-deps

  const startContentIndex = useCallback(async () => {
    if (!dialog) return
    if (!indexDefinitions.length) {
      toast.error('حداقل یک دستهٔ وردپرس، کلمهٔ کلیدی وردپرس یا ایندکس پیشنهادی بسازید.')
      return
    }
    try {
      const byId = new Map(categories.map(item => [item.id, item]))
      const prioritized = [
        ...indexDefinitions.filter(item => item.kind === 'wordpress-category'),
        ...indexDefinitions.filter(item => item.kind === 'custom'),
        ...indexDefinitions.filter(item => item.kind === 'wordpress-tag'),
      ]
      const labels = prioritized.slice(0, 200).map(item => ({
        id: item.id,
        name: item.name,
        aliases: [...new Set([
          ...(item.kind === 'wordpress-category' && byId.get(item.id)?.parent_id && byId.get(byId.get(item.id)!.parent_id!)
            ? [byId.get(byId.get(item.id)!.parent_id!)!.name]
            : []),
          ...item.aliases,
        ])],
      }))
      if (prioritized.length > labels.length) {
        toast.warning(`به‌دلیل سقف محاسباتی، ${labels.length.toLocaleString('fa-IR')} ایندکس با اولویت دسته‌ها و ایندکس‌های پیشنهادی بررسی می‌شود.`)
      }
      const started = await api<{ job: ContentIndexJob }>('POST', '/api/v1/messages/index/start', {
        site_key: siteKey,
        peer_file: dialog.peer_file,
        labels,
        max_messages: 5_000,
      })
      let job = started.job
      setContentIndexJob(job)
      for (let attempt = 0; attempt < 3600 && ['queued', 'running', 'cancelling'].includes(job.state); attempt += 1) {
        await new Promise(resolve => window.setTimeout(resolve, 1000))
        const status = await api<{ job: ContentIndexJob }>('GET', query('/api/v1/messages/index/status', { job_id: job.job_id }))
        job = status.job
        setContentIndexJob(job)
      }
      if (job.state === 'failed') throw new Error(job.error?.message || 'ایندکس‌گذاری محلی ناموفق بود.')
      await loadContentIndexResults(dialog)
      const progress = job.progress || {}
      if (job.state === 'cancelled') {
        toast.info(`ایندکس‌گذاری لغو شد؛ ${progress.processed_messages || 0} پیام بررسی شده باقی ماند.`)
      } else {
        toast.success(`${progress.processed_messages || 0} پیام بررسی و ${progress.indexed_messages || 0} پیام برچسب‌گذاری شد.`)
        if (progress.cold_start) toast.warning('مدل هنوز در حالت شروع سرد است؛ نمونه‌های دسته‌بندی‌شدهٔ بیشتری لازم است.')
        if (progress.truncated) toast.warning('به سقف ۵٬۰۰۰ پیام رسید؛ نتیجه فقط بخشی از تاریخچه است.')
      }
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'ایندکس‌گذاری محلی ناموفق بود.')
    }
  }, [categories, dialog, indexDefinitions, loadContentIndexResults, siteKey])

  const saveIndexKeywords = useCallback(() => {
    if (!siteKey || indexKeywordCategoryId === null) return
    const name = indexNameDraft.trim()
    if (!name || name.length > 200) {
      toast.error('نام نمایشی ایندکس باید بین ۱ تا ۲۰۰ نویسه باشد.')
      return
    }
    const aliases = [...new Set(
      indexKeywordDraft
        .split(/[،,;\n]/)
        .map(item => item.trim())
        .filter(Boolean),
    )].slice(0, 50)
    if (aliases.some(item => item.length > 200)) {
      toast.error('هر واژه یا عبارت راهنما باید حداکثر ۲۰۰ نویسه باشد.')
      return
    }
    setContentIndexAliases(current => {
      const next = { ...current, [indexKeywordCategoryId]: aliases }
      writeStored(`${STORAGE.indexAliases}.${siteKey}`, next)
      return next
    })
    setContentIndexNames(current => {
      const next = { ...current, [indexKeywordCategoryId]: name }
      writeStored(`${STORAGE.indexNames}.${siteKey}`, next)
      return next
    })
    setCustomIndexes(current => {
      const next = current.map(item => item.id === indexKeywordCategoryId
        ? { ...item, name, aliases, wordpressCategoryId: customIndexCategoryId }
        : item)
      writeStored(`${STORAGE.customIndexes}.${siteKey}`, next)
      return next
    })
    setIndexNameDraft(name)
    setIndexKeywordDraft(aliases.join('، '))
    toast.success('نام محلی، نگاشت و واژه‌های راهنما ذخیره شدند و در اجرای بعدی به‌کار می‌روند.')
  }, [customIndexCategoryId, indexKeywordCategoryId, indexKeywordDraft, indexNameDraft, siteKey])

  const addCustomIndex = useCallback(() => {
    if (!siteKey) return
    const name = customIndexName.trim()
    if (!name || name.length > 200) {
      toast.error('برای ایندکس پیشنهادی یک نام معتبر وارد کنید.')
      return
    }
    if (indexDefinitions.some(item => item.name.trim().toLocaleLowerCase('fa') === name.toLocaleLowerCase('fa'))) {
      toast.error('ایندکسی با این نام وجود دارد.')
      return
    }
    const aliases = [...new Set(customIndexKeywords.split(/[،,;\n]/).map(item => item.trim()).filter(Boolean))].slice(0, 50)
    if (aliases.some(item => item.length > 200)) {
      toast.error('هر واژه یا عبارت راهنما باید حداکثر ۲۰۰ نویسه باشد.')
      return
    }
    const id = Math.max(CUSTOM_INDEX_OFFSET, ...customIndexes.map(item => item.id)) + 1
    const created: IndexDefinition = {
      id,
      name,
      aliases,
      kind: 'custom',
      wordpressCategoryId: customIndexCategoryId,
    }
    setCustomIndexes(current => {
      const next = [...current, created]
      writeStored(`${STORAGE.customIndexes}.${siteKey}`, next)
      return next
    })
    setCustomIndexName('')
    setCustomIndexKeywords('')
    setCustomIndexCategoryId(null)
    setIndexKeywordCategoryId(null)
    setIndexNameDraft('')
    setIndexKeywordDraft('')
    toast.success('ایندکس پیشنهادی محلی ساخته شد.')
  }, [customIndexCategoryId, customIndexKeywords, customIndexName, customIndexes, indexDefinitions, siteKey])

  const deleteCustomIndex = useCallback((id: number) => {
    if (!siteKey) return
    setCustomIndexes(current => {
      const next = current.filter(item => item.id !== id)
      writeStored(`${STORAGE.customIndexes}.${siteKey}`, next)
      return next
    })
    setSelectedIndexLabel(current => current === id ? null : current)
    setIndexKeywordCategoryId(null)
    setIndexNameDraft('')
    setIndexKeywordDraft('')
    toast.info('ایندکس پیشنهادی حذف شد؛ دسته یا کلمهٔ کلیدی وردپرس حذف نشده است.')
  }, [siteKey])

  const cancelContentIndex = useCallback(async () => {
    if (!contentIndexJob || !['queued', 'running'].includes(contentIndexJob.state)) return
    try {
      const response = await api<{ job: ContentIndexJob }>('POST', '/api/v1/messages/index/cancel', {
        job_id: contentIndexJob.job_id,
      })
      setContentIndexJob(response.job)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'لغو ایندکس‌گذاری ناموفق بود.')
    }
  }, [contentIndexJob])

  const filteredDialogs = useMemo(() => dialogs.filter(item => {
    const matchesTab = tab === 'all' || tab === item.display_kind || (tab === 'favorite' && item.favorite)
    const q = dialogSearch.trim().toLowerCase()
    return matchesTab && (!q || titleFor(item).toLowerCase().includes(q) || (item.peer.username || '').toLowerCase().includes(q) || String(item.peer.id).includes(q))
  }), [dialogs, tab, dialogSearch])
  const visibleDialogs = useMemo(() => filteredDialogs.slice(0, 500), [filteredDialogs])

  const hasContentIndex = contentIndexLabels.length > 0 || Object.keys(contentIndexResults).length > 0
  const indexedMessages = useMemo(() => messages.map(item => ({
    ...item,
    index_predictions: [
      ...(contentIndexResults[item.id]?.predictions || []),
      ...(hasContentIndex ? temporalIndexPredictions(item.date) : []),
    ],
  })), [contentIndexResults, hasContentIndex, messages])

  const messageAlbumLookup = useMemo(() => buildAlbumLookup(indexedMessages), [indexedMessages])

  const filteredMessages = useMemo(() => {
    const q = messageSearch.trim().toLowerCase()
    return indexedMessages.filter(item => {
      const members = messageAlbumLookup.get(item.id)?.messages || [item]
      if (!showWordPressUsed && members.some(member => member.usage.used)) return false
      if (
        selectedIndexLabel !== null
        && !members.some(member => (member.index_predictions || []).some(
          prediction => prediction.label_id === selectedIndexLabel,
        ))
      ) return false
      if (selectedSenderKey !== null && !members.some(member => member.sender_key === selectedSenderKey)) return false
      if (
        q
        && !members.some(member => member.text.toLowerCase().includes(q) || String(member.id).includes(q))
      ) return false
      return true
    })
  }, [indexedMessages, messageAlbumLookup, messageSearch, selectedIndexLabel, selectedSenderKey, showWordPressUsed])

  const indexFilterLabels = useMemo(() => {
    const labels = new Map<number, string>()
    for (const message of indexedMessages) {
      for (const prediction of message.index_predictions || []) labels.set(prediction.label_id, prediction.label_name)
    }
    return [...labels].map(([id, name]) => ({ id, name })).sort((left, right) => left.name.localeCompare(right.name, 'fa'))
  }, [indexedMessages])
  const senderFilterOptions = useMemo(() => (
    [...new Set(indexedMessages.map(item => item.sender_key).filter((value): value is string => Boolean(value)))]
      .sort((left, right) => left.localeCompare(right))
  ), [indexedMessages])
  const contentIndexActive = Boolean(
    contentIndexJob && ['queued', 'running', 'cancelling'].includes(contentIndexJob.state),
  )
  const contentIndexProgress = contentIndexJob?.progress || {}
  const contentIndexPercent = Math.min(
    100,
    Math.round(
      100 * (contentIndexProgress.processed_messages || 0)
      / Math.max(1, contentIndexProgress.target_messages || 0),
    ),
  )

  const selectedMessages = useMemo(() => selectedKeys.map(key => indexedMessages.find(m => dialog && messageKey(dialog, m) === key)).filter(Boolean) as MessageItem[], [selectedKeys, indexedMessages, dialog])
  const suggestedCategoryIds = useMemo(() => {
    const available = new Set(categories.map(item => item.id))
    const mapped = new Map(indexDefinitions.map(item => [item.id, item.wordpressCategoryId || null]))
    const selected = new Set<number>()
    for (const message of selectedMessages) {
      for (const prediction of message.index_predictions || []) {
        const categoryId = available.has(prediction.label_id) ? prediction.label_id : mapped.get(prediction.label_id)
        if (categoryId && available.has(categoryId)) selected.add(categoryId)
      }
    }
    return [...selected]
  }, [categories, indexDefinitions, selectedMessages])

  const saveMessageIndexFeedback = useCallback(async () => {
    if (!dialog || !indexEditor) return
    const editableDefinitions = indexDefinitions.slice(0, 200)
    const selected = new Set(indexEditor.selectedIds)
    const changes = indexEditor.messageIds.flatMap(messageId => {
      const previous = new Set(
        (contentIndexResults[messageId]?.predictions || []).map(item => item.label_id),
      )
      return editableDefinitions
        .filter(item => previous.has(item.id) !== selected.has(item.id))
        .map(item => ({ messageId, definition: item }))
    })
    if (!changes.length) { setIndexEditor(null); return }
    setSavingIndexEditor(true)
    try {
      await Promise.all(changes.map(({ messageId, definition }) => api('POST', '/api/v1/messages/index/feedback', {
        site_key: siteKey,
        peer_file: dialog.peer_file,
        message_id: messageId,
        label_id: definition.id,
        label_name: definition.name,
        decision: selected.has(definition.id) ? 'accept' : 'reject',
      })))
      await loadContentIndexResults(dialog)
      setIndexEditor(null)
      toast.success('اصلاح شما ثبت شد و همین حالا در پیشنهادها و فیلترها اعمال شد.')
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'ثبت اصلاح ایندکس ناموفق بود.')
    } finally {
      setSavingIndexEditor(false)
    }
  }, [contentIndexResults, dialog, indexDefinitions, indexEditor, loadContentIndexResults, siteKey])

  const dialogCounts = useMemo(() => ({
    all: dialogs.length,
    channel: dialogs.filter(item => item.display_kind === 'channel').length,
    group: dialogs.filter(item => item.display_kind === 'group').length,
    personal: dialogs.filter(item => item.display_kind === 'personal').length,
    favorite: dialogs.filter(item => item.favorite).length,
  }), [dialogs])

  const railTabs: Array<{ value: Tab; label: string; icon: IconName; count: number }> = [
    { value: 'all', label: 'همه', icon: 'all', count: dialogCounts.all },
    { value: 'channel', label: 'کانال‌ها', icon: 'channel', count: dialogCounts.channel },
    { value: 'group', label: 'گروه‌ها', icon: 'group', count: dialogCounts.group },
    { value: 'personal', label: 'شخصی', icon: 'personal', count: dialogCounts.personal },
    { value: 'favorite', label: 'منتخب', icon: 'favorite', count: dialogCounts.favorite },
  ]

  const toggleFavorite = async (item: DialogItem) => {
    try {
      const response = await api<{ dialog: DialogItem }>('POST', '/api/v1/dialogs/favorite', { site_key: siteKey, peer_key: item.peer_key, favorite: !item.favorite })
      applyDialogs(dialogs.map(entry => entry.peer_key === item.peer_key ? response.dialog : entry))
    } catch (e) { toast.error(e instanceof Error ? e.message : 'تغییر منتخب ناموفق بود.') }
  }

  const setDisplayKind = async (item: DialogItem, displayKind: DisplayKind) => {
    try {
      const response = await api<{ dialog: DialogItem }>('POST', '/api/v1/dialogs/display-kind', { site_key: siteKey, peer_key: item.peer_key, display_kind: displayKind })
      applyDialogs(dialogs.map(entry => entry.peer_key === item.peer_key ? response.dialog : entry)); setDialogMenuKey(null)
    } catch (e) { toast.error(e instanceof Error ? e.message : 'اصلاح نوع گفتگو ناموفق بود.') }
  }

  const toggleMessage = (message: MessageItem) => {
    if (!dialog) return
    const albumMessages = messageAlbumLookup.get(message.id)?.messages || [message]
    const usedMessage = albumMessages.find(item => item.usage.used)
    if (usedMessage) { setActiveUsage({ message: usedMessage, usage: usedMessage.usage }); setComposerOpen(true); return }
    const keys = albumMessages.map(item => messageKey(dialog, item))
    setSelectedKeys(current => {
      const remove = keys.every(key => current.includes(key))
      return remove ? current.filter(item => !keys.includes(item)) : [...new Set([...current, ...keys])]
    })
    setSelectionMode(true); setComposerOpen(true)
  }

  const clearSelection = () => { setSelectedKeys([]); setSelectionMode(false) }
  const logout = async () => {
    if (!confirm('از حساب ایتا خارج شوید؟')) return
    try { await api('POST', '/api/v1/auth/logout'); await onLogout() }
    catch (e) { toast.error(e instanceof Error ? e.message : 'خروج ناموفق بود.') }
  }

  return <Box className="workspace telegram-workspace" data-theme={resolvedMode} data-media-display={mediaDisplay} onClick={() => { if (dialogMenuKey) setDialogMenuKey(null); if (railMenuOpen) setRailMenuOpen(false) }}>
    <Box component="main" className="telegram-layout">
      <Paper component="nav" square elevation={0} className="app-rail" aria-label="بخش‌های برنامه">
        <Box className="rail-top">
          <ButtonBase className={`rail-menu-button ${railMenuOpen ? 'active' : ''}`} title="منوی برنامه" onClick={event => { event.stopPropagation(); setRailMenuOpen(value => !value) }}><Icon name="menu" size={24} /></ButtonBase>
          {railMenuOpen && <Paper elevation={14} className="app-menu-popover menu card" onClick={event => event.stopPropagation()}>
            <Box className="app-menu-brand"><Box className="brand-mini">EB</Box><Box><strong>Eitaa Bridge</strong><small>{sites.find(site => site.site_key === siteKey)?.base_url || 'سرویس محلی'}</small></Box></Box>
            <Stack spacing={0.25}>
              <Button fullWidth variant="text" sx={{ justifyContent: 'flex-start' }} startIcon={<Icon name="settings" />} onClick={() => { setSettingsOpen(true); setRailMenuOpen(false) }}>تنظیمات و سایت‌ها</Button>
              <Button fullWidth variant="text" sx={{ justifyContent: 'flex-start' }} startIcon={<Icon name="plus" />} onClick={() => { setManualOpen(true); setRailMenuOpen(false) }}>افزودن دستی گفتگو</Button>
              <Button fullWidth variant="text" sx={{ justifyContent: 'flex-start' }} startIcon={<Icon name="refresh" />} disabled={syncingDialogs} onClick={() => { void syncDialogs(); setRailMenuOpen(false) }}>{syncingDialogs ? 'در حال همگام‌سازی…' : 'همگام‌سازی گفتگوها'}</Button>
              <Box className="menu-separator" />
              <Button fullWidth variant="text" sx={{ justifyContent: 'flex-start' }} startIcon={<Icon name="bulk" />} onClick={() => { openBulk(dialog && dialog.display_kind !== 'personal' ? 'members' : 'numbers'); setRailMenuOpen(false) }}>ارسال و دعوت گروهی</Button>
              <Box className="app-theme-status"><span aria-hidden>☾</span><span>تم برنامه: تاریک</span></Box>
              <Box className="menu-separator" />
              <Button fullWidth color="error" variant="text" sx={{ justifyContent: 'flex-start' }} startIcon={<Icon name="logout" />} onClick={() => void logout()}>خروج از حساب</Button>
            </Stack>
          </Paper>}
        </Box>
        <Box className="rail-tabs">
          {railTabs.map(item => <ButtonBase key={item.value} className={`rail-tab ${tab === item.value ? 'active' : ''}`} onClick={() => setTab(item.value)} title={item.label}>
            <span className="rail-icon"><Icon name={item.icon} />{item.count > 0 && <b>{item.count > 999 ? '999+' : item.count}</b>}</span>
            <span>{item.label}</span>
          </ButtonBase>)}
        </Box>
        <Box className="rail-bottom">
          <ButtonBase className={`rail-tab contacts-rail ${contactsOpen ? 'active' : ''}`} onClick={() => setContactsOpen(true)} title="مدیریت مخاطبان ایتا و محلی"><span className="rail-icon"><Icon name="personal" /></span><span>مدیریت مخاطبان</span></ButtonBase>
          <Box className="rail-tab theme-rail" title="تم ثابت تاریک"><span className="rail-icon">☾</span><span>تاریک</span></Box>
          {!composerDocked && !composerOpen && <ButtonBase className="rail-tab wordpress-rail" disabled={!wordpressAvailable} onClick={() => setComposerOpen(true)} title={wordpressAvailable ? 'وردپرس' : 'ابتدا یک سایت وردپرس با دسترسی کامل تعریف کنید'}><span className="rail-icon"><Icon name="wordpress" /></span><span>وردپرس</span></ButtonBase>}
        </Box>
      </Paper>

      <Paper component="aside" square elevation={0} className={`chats-pane ${chatsOpen ? 'drawer-visible' : ''}`}>
        <div className="chat-list-toolbar">
          <div className="search-box"><Icon name="search" size={18} /><input value={dialogSearch} onChange={e => setDialogSearch(e.target.value)} placeholder="جست‌وجو" /></div>
          <button className="toolbar-button" disabled={syncingDialogs} onClick={() => void syncDialogs()} title="همگام‌سازی">{syncingDialogs ? <span className="loading loading-dots loading-sm" /> : <Icon name="refresh" size={19} />}</button>
          <button className="toolbar-button" onClick={() => setManualOpen(true)} title="افزودن دستی"><Icon name="plus" size={20} /></button>
          <button className="toolbar-button close-chats" onClick={() => setChatsOpen(false)} title="بستن"><Icon name="close" size={20} /></button>
        </div>
        <div className="chat-list-caption"><strong>{railTabs.find(item => item.value === tab)?.label}</strong><span>{filteredDialogs.length} گفتگو</span></div>
        {filteredDialogs.length > visibleDialogs.length && <Alert severity="info" sx={{ m: 1, py: 0 }}>برای حفظ سرعت، ۵۰۰ گفت‌وگوی نخست نمایش داده شده است؛ برای موارد دیگر جست‌وجو کنید.</Alert>}
        <div className="dialog-list">
          {loadingDialogs && !dialogs.length && <div className="empty"><span className="loading loading-dots loading-md" /><small>در حال دریافت گفتگوها</small></div>}
          {!loadingDialogs && !filteredDialogs.length && <div className="empty">موردی در این بخش نیست.<br/><button className="btn btn-sm btn-ghost" onClick={() => setManualOpen(true)}>افزودن دستی</button></div>}
          {visibleDialogs.map(item => {
            const active = dialog?.peer_key === item.peer_key
            const secondary = item.peer.username ? `@${item.peer.username}` : item.top_message_id ? `آخرین پیام #${item.top_message_id}` : item.source === 'manual' ? 'افزوده‌شده به‌صورت دستی' : 'گفتگو'
            return <div key={item.peer_key} className={`dialog-row ${active ? 'active' : ''}`} onClick={() => selectDialog(item)}>
              <DialogAvatar dialog={item} siteKey={siteKey} />
              <div className="dialog-main"><strong>{titleFor(item)}</strong><span>{secondary}</span></div>
              <div className="dialog-meta dialog-actions">
                <button className="dialog-more" onClick={e => { e.stopPropagation(); setDialogMenuKey(current => current === item.peer_key ? null : item.peer_key) }} title="بیشتر"><Icon name="more" size={18} /></button>
                <button className={`star ${item.favorite ? 'selected' : ''}`} onClick={e => { e.stopPropagation(); void toggleFavorite(item) }} title="منتخب"><Icon name="favorite" size={17} /></button>
                {item.unread_count > 0 && <b>{item.unread_count > 9999 ? '9999+' : item.unread_count}</b>}
                {dialogMenuKey === item.peer_key && <div className="dialog-menu menu" onClick={e => e.stopPropagation()}>
                  <strong>نمایش در فهرست</strong>
                  {(['channel', 'group', 'personal'] as DisplayKind[]).map(kind => <button key={kind} className={item.display_kind === kind ? 'selected' : ''} onClick={() => void setDisplayKind(item, kind)}>{displayKindLabel(kind)}</button>)}
                </div>}
              </div>
            </div>
          })}
        </div>
      </Paper>

      <Paper component="section" square elevation={0} className="messages-pane">
        <div className="messages-header">
          <div className="chat-identity">
            <button className="toolbar-button mobile-chat-button" onClick={() => setChatsOpen(true)} title="گفتگوها"><Icon name="menu" size={21} /></button>
            <DialogAvatar dialog={dialog} siteKey={siteKey} small />
            <div><h2>{titleFor(dialog)}</h2><small>{dialog ? `${messages.length} پیام ذخیره‌شده` : 'گفتگویی انتخاب نشده'}</small></div>
          </div>
          <div className="messages-tools">
            {selectionMode && <><b>{selectedKeys.length} انتخاب</b><button className="btn btn-sm btn-ghost ghost" onClick={clearSelection}>لغو</button></>}
            <button className="toolbar-button" disabled={!dialog || loadingMessages} onClick={() => void loadNewer(true)} title="بررسی پیام‌های جدید"><Icon name="refresh" size={18} /></button>
            <button className={`toolbar-button ${mediaDisplay === 'dynamic' ? 'active' : ''}`} disabled={!dialog} onClick={() => setMediaDisplay(value => value === 'dynamic' ? 'framed' : 'dynamic')} title={mediaDisplay === 'dynamic' ? 'نمایش عکس در کادر ثابت' : 'نمایش کامل و پویا بر اساس طول عکس'}>{mediaDisplay === 'dynamic' ? '↕' : '▣'}</button>
            <button
              className={`toolbar-button content-filter-toggle ${contentFiltersOpen || !showWordPressUsed || selectedIndexLabel !== null || selectedSenderKey !== null ? 'active' : ''}`}
              disabled={!dialog}
              onClick={event => {
                event.stopPropagation()
                setContentFiltersOpen(value => !value)
              }}
              title="فیلتر و ایندکس محلی"
            ><Icon name="filter" size={19} /></button>
            <div className="jalali-filter">
              <JalaliDatePicker
                value={jalaliFrom}
                mode={dateMode}
                disabled={!dialog || loadingDateRange}
                busy={loadingDateRange}
                onMode={setDateMode}
                onSelect={(value, mode) => void loadFromJalaliDate(value, mode)}
                onClear={() => void clearDateRange()}
              />
            </div>
            <div className="message-search"><Icon name="search" size={17} /><input value={messageSearch} onChange={e => setMessageSearch(e.target.value)} placeholder="جست‌وجوی پیام" /></div>
            {!composerDocked && !composerOpen && <button className="btn btn-primary icon-button composer-toggle" disabled={!wordpressAvailable} onClick={() => setComposerOpen(true)} title={wordpressAvailable ? 'وردپرس' : 'ابتدا سایت وردپرس را در تنظیمات تعریف کنید'}><Icon name="wordpress" size={21} /></button>}
          </div>
        </div>
        {!dialog ? <div className="messages-empty"><div className="brand-mark">EB</div><h2>یک گفتگو را انتخاب کنید</h2></div> : <VirtualMessageList key={dialog.peer_key} dialog={dialog} messages={filteredMessages} media={media} selectedKeys={selectedKeys} selectionMode={selectionMode} loading={loadingMessages} readReceiptsEnabled={!dateRange && !messageSearch.trim() && showWordPressUsed && selectedIndexLabel === null && selectedSenderKey === null} focusMessageId={dateJump?.messageId || null} focusEpoch={dateJump?.epoch || 0} scrollMemory={messageScrollMemoryRef.current} loadMedia={loadMedia} openFullMedia={openFullMedia} toggleMessage={toggleMessage} editIndex={(message, members) => setIndexEditor({ message, messageIds: members.map(item => item.id), selectedIds: [...new Set(members.flatMap(item => (contentIndexResults[item.id]?.predictions || []).map(prediction => prediction.label_id)))] })} loadOlder={loadOlder} loadNewer={loadNewer} markRead={markDialogRead} openUsage={message => { setActiveUsage({ message, usage: message.usage }); setComposerOpen(true) }} />}
        <QuickSendBar siteKey={siteKey} dialog={dialog} onSent={() => loadNewer(true)} />
      </Paper>

      <Paper component="aside" square elevation={0} className={`composer-pane ${composerOpen ? 'drawer-visible' : ''}`}>
        <Composer dialog={dialog} dialogs={dialogs} siteKey={siteKey} sites={sites} setSiteKey={setSiteKey} wordpressReady={Boolean(activeSite?.credentials_configured)} openSettings={() => setSettingsOpen(true)} openBulk={openBulk} openMembers={() => setMembersOpen(true)} selectedMessages={selectedMessages} selectedKeys={selectedKeys} setSelectedKeys={setSelectedKeys} suggestedCategoryIds={suggestedCategoryIds} categories={categories} tags={tags} setTags={setTags} media={media} activeUsage={activeUsage} clearUsage={() => setActiveUsage(null)} close={() => setComposerOpen(false)} communityOpen={communityOpen} setCommunityOpen={setCommunityOpen} onSuccess={refreshCurrentLocalView} markSourcesUsed={markWordPressSourcesUsed} />
      </Paper>
    </Box>
    {settingsOpen && <SettingsModal sites={sites} close={() => setSettingsOpen(false)} onChanged={loadSites} />}
    {bulkOpen && <BulkOperationsModal siteKey={siteKey} dialog={dialog} initialMode={bulkMode} initialMemberIds={bulkMemberIds} initialNumbers={bulkInitialNumbers} close={() => setBulkOpen(false)} />}
    {membersOpen && <CommunityMembersModal siteKey={siteKey} dialog={dialog} close={() => setMembersOpen(false)} openBulk={memberIds => { setMembersOpen(false); openBulk('members', memberIds) }} />}
    {manualOpen && <ManualDialogModal siteKey={siteKey} close={() => setManualOpen(false)} onAdded={item => { applyDialogs([item, ...dialogs.filter(d => d.peer_key !== item.peer_key)]); selectDialog(item); setManualOpen(false) }} />}
    {contactsOpen && <ContactDirectoryModal
      siteKey={siteKey}
      close={() => setContactsOpen(false)}
      handoffTargets={phones => { setContactsOpen(false); openBulk('numbers', [], phones) }}
      handoffContact={contact => {
        if (!contact.peer_file) {
          toast.info('اطلاعات فنی این مخاطب برای گفت‌وگوی مستقیم در دسترس نیست.')
          return
        }
        const existing = dialogs.find(item => item.peer_key === contact.peer_key)
        const target: DialogItem = existing || {
          peer_key: contact.peer_key,
          peer: {
            id: contact.user_id,
            type: 'user',
            title: contact.display_name,
            username: contact.username || null,
            access_hash_present: contact.access_hash_present,
          },
          peer_file: contact.peer_file,
          technical_kind: 'private',
          display_kind: 'personal',
          display_kind_locked: false,
          favorite: false,
          source: 'eitaa-contact',
          top_message_id: 0,
          unread_count: 0,
          unread_mentions_count: 0,
          pinned: false,
          unread_mark: false,
        }
        if (!existing) setDialogs(current => [target, ...current])
        setTab('personal')
        setContactsOpen(false)
        selectDialog(target)
      }}
    />}
    {mediaViewer && <MaterialLegacyDialog close={() => setMediaViewer(null)} maxWidth="xl">
      <div className="media-viewer card material-dialog-surface"><div className="media-viewer-head"><b>{mediaViewer.title}</b><button onClick={() => setMediaViewer(null)}><Icon name="close" /></button></div>
        <div className="media-viewer-body">{fullMedia[mediaViewer.key] === null || fullMedia[mediaViewer.key] === undefined ? <div className="media-viewer-loading"><Skeleton variant="rectangular" animation="wave" width="min(76vw, 920px)" height="min(68vh, 620px)" /><span>در حال دریافت تصویر اصلی از حافظه یا سرور ایتا…</span></div> : fullMedia[mediaViewer.key] ? <img src={fullMedia[mediaViewer.key] || ''} alt={mediaViewer.title} /> : <div className="error-box">تصویر اصلی در دسترس نیست.</div>}</div>
      </div>
    </MaterialLegacyDialog>}
    <MaterialIndexWorkbench
      open={contentFiltersOpen}
      close={() => setContentFiltersOpen(false)}
      tab={indexWorkbenchTab}
      setTab={setIndexWorkbenchTab}
      showWordPressUsed={showWordPressUsed}
      setShowWordPressUsed={setShowWordPressUsed}
      selectedIndexLabel={selectedIndexLabel}
      setSelectedIndexLabel={setSelectedIndexLabel}
      selectedSenderKey={selectedSenderKey}
      setSelectedSenderKey={setSelectedSenderKey}
      indexFilterLabels={indexFilterLabels}
      senderFilterOptions={senderFilterOptions}
      filteredMessageCount={filteredMessages.length}
      contentIndexActive={contentIndexActive}
      contentIndexState={contentIndexJob?.state}
      contentIndexProcessed={Number(contentIndexProgress.processed_messages || 0)}
      contentIndexTarget={Number(contentIndexProgress.target_messages || 0)}
      contentIndexPercent={contentIndexPercent}
      coldStart={Boolean(contentIndexProgress.cold_start)}
      resultCount={Object.keys(contentIndexResults).length}
      canStart={Boolean(dialog && indexDefinitions.length)}
      start={() => void startContentIndex()}
      cancel={() => void cancelContentIndex()}
      definitions={indexDefinitions}
      categories={categories}
      customIndexName={customIndexName}
      setCustomIndexName={setCustomIndexName}
      customIndexCategoryId={customIndexCategoryId}
      customIndexKeywords={customIndexKeywords}
      setCustomIndexKeywords={setCustomIndexKeywords}
      setCustomIndexCategoryId={setCustomIndexCategoryId}
      addCustomIndex={addCustomIndex}
      selectedDefinitionId={indexKeywordCategoryId}
      selectDefinition={id => {
        const definition = indexDefinitions.find(item => item.id === id)
        setIndexKeywordCategoryId(id)
        setIndexNameDraft(definition?.name || '')
        setIndexKeywordDraft((definition?.aliases || []).join('، '))
        setCustomIndexCategoryId(definition?.wordpressCategoryId || null)
      }}
      indexNameDraft={indexNameDraft}
      setIndexNameDraft={setIndexNameDraft}
      indexKeywordDraft={indexKeywordDraft}
      setIndexKeywordDraft={setIndexKeywordDraft}
      saveDefinition={saveIndexKeywords}
      deleteDefinition={deleteCustomIndex}
    />
    {indexEditor && <MessageIndexEditor
      open
      messageLabel={indexEditor.messageIds.length > 1 ? `گالری ${indexEditor.messageIds.length}‌پیامی` : `پیام #${indexEditor.message.id}`}
      definitions={indexDefinitions}
      selectedIds={indexEditor.selectedIds}
      setSelectedIds={selectedIds => setIndexEditor(current => current ? ({ ...current, selectedIds }) : current)}
      saving={savingIndexEditor}
      close={() => setIndexEditor(null)}
      save={() => void saveMessageIndexFeedback()}
    />}
    {((chatsOpen && !chatsDocked) || (composerOpen && !composerDocked)) && <div className="drawer-backdrop visible" onClick={() => { setChatsOpen(false); setComposerOpen(false) }} />}
  </Box>
}

function VirtualMessageList(props: { dialog: DialogItem; messages: MessageItem[]; media: Record<string, string | null>; selectedKeys: string[]; selectionMode: boolean; loading: boolean; readReceiptsEnabled: boolean; focusMessageId: number | null; focusEpoch: number; scrollMemory: Map<string, MessageScrollMemory>; loadMedia: (message: MessageItem) => Promise<void>; openFullMedia: (message: MessageItem) => Promise<void>; toggleMessage: (message: MessageItem) => void; editIndex: (message: MessageItem, members: MessageItem[]) => void; loadOlder: () => Promise<number>; loadNewer: () => Promise<void>; markRead: (dialog: DialogItem, maxId: number, remainingUnreadCount: number) => Promise<void>; openUsage: (message: MessageItem) => void }) {
  const parentRef = useRef<HTMLDivElement>(null)
  const lastScroll = useRef(0)
  const nearBottomRef = useRef(true)
  const topPagination = useRef<TopPaginationGate>({ armed: true, inFlight: false })
  const prependAnchor = useRef<ScrollAnchor | null>(null)
  const programmaticScroll = useRef(false)
  const userInteracted = useRef(false)
  const readTimer = useRef<number | null>(null)
  const scrollFrame = useRef<number | null>(null)
  const positioned = useRef(false)
  const previousTail = useRef<{ peerKey: string; tailId: number | null }>({ peerKey: props.dialog.peer_key, tailId: null })
  const [floatingDate, setFloatingDate] = useState('')
  const memoryKey = props.readReceiptsEnabled ? props.dialog.peer_key : `${props.dialog.peer_key}:filtered`
  const dayKeys = useMemo(() => props.messages.map(message => jalaliDayKey(message.date)), [props.messages])
  const albumLookup = useMemo(() => buildAlbumLookup(props.messages), [props.messages])

  const firstUnreadCandidateIndex = useMemo(() => {
    if (!props.messages.length || props.dialog.unread_count <= 0) return -1
    const exactBoundary = props.dialog.read_inbox_max_id || 0
    if (exactBoundary > 0) {
      const exact = props.messages.findIndex(message => !message.outgoing && message.id > exactBoundary)
      if (exact >= 0) return exact
    }
    return Math.max(0, props.messages.length - Math.min(props.dialog.unread_count, props.messages.length))
  }, [props.dialog.peer_key, props.dialog.read_inbox_max_id, props.dialog.unread_count, props.messages])
  const firstUnreadIndex = useMemo(() => {
    if (firstUnreadCandidateIndex < 0) return -1
    const candidate = props.messages[firstUnreadCandidateIndex]
    const album = candidate ? albumLookup.get(candidate.id) : undefined
    return album ? props.messages.findIndex(message => message.id === album.leader.id) : firstUnreadCandidateIndex
  }, [albumLookup, firstUnreadCandidateIndex, props.messages])

  const virtualizer = useVirtualizer({
    count: props.messages.length,
    getScrollElement: () => parentRef.current,
    getItemKey: index => props.messages[index] ? messageKey(props.dialog, props.messages[index]) : `${props.dialog.peer_key}:missing:${index}`,
    estimateSize: index => {
      let message = props.messages[index]
      if (!message) return 120
      const album = albumLookup.get(message.id)
      if (album && album.leader.id !== message.id) return 0
      const caption = album ? albumCaption(album.messages) : message.text
      if (album) message = { ...message, text: caption, text_length: caption.length }
      const hasDaySeparator = index === 0 || dayKeys[index - 1] !== dayKeys[index]
      return estimateMessageRowSize(message, hasDaySeparator, index === firstUnreadIndex)
    },
    overscan: 5,
    useAnimationFrameWithResizeObserver: true,
  })
  virtualizer.shouldAdjustScrollPositionOnItemSizeChange = (item, _delta, instance) => {
    if (programmaticScroll.current) return false
    const scrollOffset = instance.scrollOffset ?? parentRef.current?.scrollTop ?? 0
    return item.start < scrollOffset + 1
  }

  const persistScrollMemory = useCallback(() => {
    const element = parentRef.current
    if (!element) return
    const firstVisible = virtualizer.getVirtualItems().find(row => row.end > element.scrollTop + 1)
    const message = firstVisible ? props.messages[firstVisible.index] : undefined
    props.scrollMemory.set(memoryKey, {
      anchorKey: message ? messageKey(props.dialog, message) : null,
      anchorOffset: firstVisible ? firstVisible.start - element.scrollTop : 0,
      scrollTop: element.scrollTop,
      nearBottom: isNearBottom(element.scrollHeight, element.scrollTop, element.clientHeight),
    })
  }, [memoryKey, props.dialog, props.messages, props.scrollMemory, virtualizer])

  const restoreMeasuredAnchor = useCallback((key: string, index: number, viewportOffset: number) => {
    const element = parentRef.current
    if (!element) return
    const row = [...element.querySelectorAll<HTMLElement>('.virtual-row')]
      .find(item => item.dataset.messageKey === key)
    if (row) {
      const currentOffset = row.getBoundingClientRect().top - element.getBoundingClientRect().top
      virtualizer.scrollToOffset(element.scrollTop + currentOffset - viewportOffset, { align: 'start' })
      return
    }
    const measuredOffset = virtualizer.getOffsetForIndex(index, 'start')?.[0]
    if (measuredOffset !== undefined) virtualizer.scrollToOffset(anchorScrollTop(measuredOffset, viewportOffset), { align: 'start' })
  }, [virtualizer])

  const scheduleVisibleRead = useCallback((scrollTop: number, scrollingDown: boolean) => {
    if (!props.readReceiptsEnabled || !scrollingDown || !userInteracted.current || firstUnreadIndex < 0 || props.dialog.unread_count <= 0) return
    const element = parentRef.current
    if (!element) return
    const viewportBottom = scrollTop + element.clientHeight - 24
    const visible = virtualizer.getVirtualItems()
      .filter(row => row.index >= firstUnreadIndex && row.start >= scrollTop - 1 && row.end <= viewportBottom)
      .map(row => props.messages[row.index])
      .filter((message): message is MessageItem => Boolean(message) && !message.outgoing)
      .flatMap(message => albumLookup.get(message.id)?.messages || [message])
      .filter(message => !message.outgoing)
    if (!visible.length) return
    const maxId = Math.max(...visible.map(message => message.id))
    const previousBoundary = props.dialog.read_inbox_max_id || 0
    const newlyRead = props.messages.filter(message => !message.outgoing && message.id > previousBoundary && message.id <= maxId).length
    const remaining = Math.max(0, props.dialog.unread_count - newlyRead)
    if (readTimer.current !== null) window.clearTimeout(readTimer.current)
    readTimer.current = window.setTimeout(() => {
      void props.markRead(props.dialog, maxId, remaining)
      readTimer.current = null
    }, 2200)
  }, [albumLookup, firstUnreadIndex, props.dialog, props.markRead, props.messages, props.readReceiptsEnabled, virtualizer])

  useEffect(() => {
    const element = parentRef.current
    if (!element) return
    const markInteraction = () => { userInteracted.current = true }
    const processScroll = () => {
      scrollFrame.current = null
      const current = element.scrollTop
      const scrollingDown = current > lastScroll.current + 0.5
      const firstVisible = virtualizer.getVirtualItems().find(row => row.end > current + 1)
      const firstMessage = firstVisible ? props.messages[firstVisible.index] : undefined
      if (firstMessage) {
        const nextDate = jalaliDayLabel(firstMessage.date)
        setFloatingDate(previous => previous === nextDate ? previous : nextDate)
      }
      nearBottomRef.current = isNearBottom(element.scrollHeight, current, element.clientHeight)
      if (!programmaticScroll.current && props.readReceiptsEnabled) {
        const gateUpdate = updateTopPaginationGate(current, lastScroll.current, topPagination.current)
        topPagination.current = gateUpdate.gate
        if (gateUpdate.shouldRequest) {
          const anchorRow = firstVisible
          const anchorMessage = anchorRow ? props.messages[anchorRow.index] : undefined
          prependAnchor.current = anchorRow && anchorMessage ? { key: messageKey(props.dialog, anchorMessage), viewportOffset: anchorRow.start - current } : null
          topPagination.current = { ...topPagination.current, inFlight: true }
          void props.loadOlder()
            .then(added => { if (added <= 0) prependAnchor.current = null })
            .finally(() => { topPagination.current = { ...topPagination.current, inFlight: false } })
        }
        if (nearBottomRef.current && scrollingDown) void props.loadNewer()
        scheduleVisibleRead(current, scrollingDown)
      }
      lastScroll.current = current
      persistScrollMemory()
    }
    const onScroll = () => {
      if (scrollFrame.current === null) scrollFrame.current = window.requestAnimationFrame(processScroll)
    }
    element.addEventListener('wheel', markInteraction, { passive: true })
    element.addEventListener('touchstart', markInteraction, { passive: true })
    element.addEventListener('pointerdown', markInteraction, { passive: true })
    element.addEventListener('scroll', onScroll, { passive: true })
    return () => {
      element.removeEventListener('wheel', markInteraction)
      element.removeEventListener('touchstart', markInteraction)
      element.removeEventListener('pointerdown', markInteraction)
      element.removeEventListener('scroll', onScroll)
      if (scrollFrame.current !== null) window.cancelAnimationFrame(scrollFrame.current)
    }
  }, [persistScrollMemory, props.dialog, props.loadNewer, props.loadOlder, props.messages, props.readReceiptsEnabled, scheduleVisibleRead, virtualizer])

  useLayoutEffect(() => {
    const anchor = prependAnchor.current
    const element = parentRef.current
    if (!anchor || !element) return
    const anchorIndex = props.messages.findIndex(message => messageKey(props.dialog, message) === anchor.key)
    if (anchorIndex < 0) { prependAnchor.current = null; return }
    programmaticScroll.current = true
    virtualizer.measure()
    let secondFrame = 0
    const firstFrame = window.requestAnimationFrame(() => {
      virtualizer.scrollToIndex(anchorIndex, { align: 'start' })
      secondFrame = window.requestAnimationFrame(() => {
        restoreMeasuredAnchor(anchor.key, anchorIndex, anchor.viewportOffset)
        lastScroll.current = element.scrollTop
        nearBottomRef.current = isNearBottom(element.scrollHeight, element.scrollTop, element.clientHeight)
        prependAnchor.current = null
        persistScrollMemory()
        window.requestAnimationFrame(() => { programmaticScroll.current = false })
      })
    })
    return () => { window.cancelAnimationFrame(firstFrame); if (secondFrame) window.cancelAnimationFrame(secondFrame) }
  }, [persistScrollMemory, props.dialog, props.messages, restoreMeasuredAnchor, virtualizer])

  useLayoutEffect(() => {
    positioned.current = false
    prependAnchor.current = null
    programmaticScroll.current = false
    userInteracted.current = false
    nearBottomRef.current = true
    topPagination.current = { armed: true, inFlight: false }
    previousTail.current = { peerKey: props.dialog.peer_key, tailId: null }
    setFloatingDate('')
    if (readTimer.current !== null) { window.clearTimeout(readTimer.current); readTimer.current = null }
    // Scroll memory is committed by the scroll handler itself. Persisting again
    // during keyed unmount can observe a DOM node already reset to scrollTop=0
    // and overwrite the valid per-dialog anchor.
  }, [props.dialog.peer_key]) // eslint-disable-line react-hooks/exhaustive-deps

  useLayoutEffect(() => {
    if (!props.messages.length || positioned.current) return
    const element = parentRef.current
    if (!element) return
    const remembered = props.scrollMemory.get(memoryKey)
    const rememberedIndex = remembered?.anchorKey ? props.messages.findIndex(message => messageKey(props.dialog, message) === remembered.anchorKey) : -1
    const targetIndex = rememberedIndex >= 0 ? rememberedIndex : firstUnreadIndex > 0 ? firstUnreadIndex - 1 : firstUnreadIndex === 0 ? 0 : props.messages.length - 1
    programmaticScroll.current = true
    let secondFrame = 0
    let completed = false
    const firstFrame = window.requestAnimationFrame(() => {
      virtualizer.scrollToIndex(targetIndex, { align: rememberedIndex >= 0 || firstUnreadIndex >= 0 ? 'start' : 'end' })
      secondFrame = window.requestAnimationFrame(() => {
        if (rememberedIndex >= 0 && remembered) {
          restoreMeasuredAnchor(remembered.anchorKey || '', rememberedIndex, remembered.anchorOffset)
        } else if (remembered && remembered.scrollTop > 0) {
          element.scrollTop = Math.min(remembered.scrollTop, Math.max(0, element.scrollHeight - element.clientHeight))
        }
        lastScroll.current = element.scrollTop
        nearBottomRef.current = isNearBottom(element.scrollHeight, element.scrollTop, element.clientHeight)
        const selected = props.messages[Math.max(0, targetIndex)]
        if (selected) setFloatingDate(jalaliDayLabel(selected.date))
        previousTail.current = { peerKey: props.dialog.peer_key, tailId: props.messages[props.messages.length - 1]?.id ?? null }
        positioned.current = true
        completed = true
        persistScrollMemory()
        window.requestAnimationFrame(() => { programmaticScroll.current = false })
      })
    })
    return () => {
      window.cancelAnimationFrame(firstFrame)
      if (secondFrame) window.cancelAnimationFrame(secondFrame)
      if (!completed) {
        positioned.current = false
        programmaticScroll.current = false
      }
    }
  }, [firstUnreadIndex, memoryKey, persistScrollMemory, props.dialog, props.messages, props.scrollMemory, restoreMeasuredAnchor, virtualizer])

  useLayoutEffect(() => {
    if (!props.focusMessageId || !props.focusEpoch) return
    const element = parentRef.current
    const targetIndex = props.messages.findIndex(message => message.id === props.focusMessageId)
    if (!element || targetIndex < 0) return
    positioned.current = true
    programmaticScroll.current = true
    const firstFrame = window.requestAnimationFrame(() => {
      virtualizer.scrollToIndex(targetIndex, { align: 'start' })
      window.requestAnimationFrame(() => {
        lastScroll.current = element.scrollTop
        setFloatingDate(jalaliDayLabel(props.messages[targetIndex].date))
        persistScrollMemory()
        programmaticScroll.current = false
      })
    })
    return () => window.cancelAnimationFrame(firstFrame)
  }, [persistScrollMemory, props.focusEpoch, props.focusMessageId, props.messages, virtualizer])

  useLayoutEffect(() => {
    const currentTailId = props.messages[props.messages.length - 1]?.id ?? null
    const previous = previousTail.current
    if (previous.peerKey !== props.dialog.peer_key || previous.tailId === null) {
      previousTail.current = { peerKey: props.dialog.peer_key, tailId: currentTailId }
      return
    }
    const appended = appendedMessagesAfterTail(props.messages, previous.tailId)
    previousTail.current = { peerKey: props.dialog.peer_key, tailId: currentTailId }
    if (!appended.length || !positioned.current || !shouldAutoFollow(nearBottomRef.current, appended)) return
    const element = parentRef.current
    if (!element) return
    programmaticScroll.current = true
    const frame = window.requestAnimationFrame(() => {
      virtualizer.scrollToIndex(props.messages.length - 1, { align: 'end' })
      window.requestAnimationFrame(() => {
        lastScroll.current = element.scrollTop
        nearBottomRef.current = true
        persistScrollMemory()
        programmaticScroll.current = false
      })
    })
    return () => window.cancelAnimationFrame(frame)
  }, [persistScrollMemory, props.dialog.peer_key, props.messages, virtualizer])

  useEffect(() => () => {
    if (readTimer.current !== null) window.clearTimeout(readTimer.current)
    if (scrollFrame.current !== null) window.cancelAnimationFrame(scrollFrame.current)
  }, [])

  return <div ref={parentRef} className="message-scroll">
    <div className="message-scroll-overlays" aria-hidden="true">
      {floatingDate && <div className="floating-date">{floatingDate}</div>}
      {props.loading && <div className="loading-chip"><span className="loading loading-dots loading-sm" /> در حال همگام‌سازی</div>}
    </div>
    <div className="message-virtual" style={{ height: virtualizer.getTotalSize() }}>
      {virtualizer.getVirtualItems().map(row => {
        const message = props.messages[row.index]
        const key = messageKey(props.dialog, message)
        const album = albumLookup.get(message.id)
        const isAlbumFollower = Boolean(album && album.leader.id !== message.id)
        return <div key={key} data-index={row.index} data-message-key={key} ref={virtualizer.measureElement} className={`virtual-row ${isAlbumFollower ? 'album-follower-row' : ''} ${message.id === props.focusMessageId ? 'date-focus-row' : ''}`} style={{ transform: `translateY(${row.start}px)` }}>
          {!isAlbumFollower && <>
          {(row.index === 0 || dayKeys[row.index - 1] !== dayKeys[row.index]) && <div className="day-separator"><span>{jalaliDayLabel(message.date)}</span></div>}
          {row.index === firstUnreadIndex && <div className="unread-separator"><span>{props.dialog.unread_count} پیام خوانده‌نشده</span></div>}
          <MessageCard dialog={props.dialog} message={message} album={album} media={props.media} selectedKeys={props.selectedKeys} selectionMode={props.selectionMode} loadMedia={props.loadMedia} openFullMedia={props.openFullMedia} toggle={() => props.toggleMessage(message)} editIndex={() => props.editIndex(message, album?.messages || [message])} openUsage={() => props.openUsage(message)} />
          </>}
        </div>
      })}
    </div>
  </div>
}
function MessageCard({ dialog, message, album, media, selectedKeys, selectionMode, loadMedia, openFullMedia, toggle, editIndex, openUsage }: { dialog: DialogItem; message: MessageItem; album?: MediaAlbum; media: Record<string, string | null>; selectedKeys: string[]; selectionMode: boolean; loadMedia: (m: MessageItem) => Promise<void>; openFullMedia: (m: MessageItem) => Promise<void>; toggle: () => void; editIndex: () => void; openUsage: () => void }) {
  const members = album?.messages || [message]
  const images = members.filter(item => item.media?.is_image)
  const files = members.filter(item => item.media && !item.media.is_image)
  const caption = album ? albumCaption(members) : message.text
  const memberKeys = members.map(item => messageKey(dialog, item))
  const selected = memberKeys.every(key => selectedKeys.includes(key))
  const anyUsed = members.some(item => item.usage.used)
  const allUsed = members.every(item => item.usage.used)
  const anyStale = members.some(item => item.usage.usage_state === 'stale')
  const indexedByLabel = new Map<number, IndexPrediction>()
  for (const item of members) {
    for (const prediction of item.index_predictions || []) {
      const current = indexedByLabel.get(prediction.label_id)
      if (!current || prediction.score > current.score) indexedByLabel.set(prediction.label_id, prediction)
    }
  }
  const indexPredictions = [...indexedByLabel.values()].sort((a, b) => b.score - a.score).slice(0, 5)
  useEffect(() => {
    for (const item of images) {
      if (media[messageKey(dialog, item)] === undefined) void loadMedia(item)
    }
  }, [dialog, images, loadMedia, media])
  const usageClass = anyStale ? 'stale' : allUsed ? 'used' : anyUsed ? 'partly-used' : ''
  const click = () => selectionMode ? toggle() : anyUsed ? openUsage() : undefined
  const firstId = members[0].id
  const lastId = members[members.length - 1].id
  return <article className={`message-card card ${message.outgoing ? 'outgoing' : ''} ${album ? 'album-card' : ''} ${usageClass} ${selected ? 'selected' : ''}`} onClick={click} onContextMenu={e => { e.preventDefault(); toggle() }}>
    {album && <div className={`album-label ${album.kind === 'inferred' ? 'inferred-album' : ''}`}>{album.kind === 'inferred' ? `گالری پیشنهادی · ${members.length} تصویر` : `گالری · ${members.length} رسانه`}</div>}
    {images.length > 0 && <div className={`message-media ${album ? `album-grid album-grid-${Math.min(images.length, 4)}` : ''}`} style={album && images.length > 4 ? { gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gridTemplateRows: `repeat(${Math.ceil(images.length / 3)}, minmax(0, 1fr))` } : undefined}>
      {images.map(item => {
        const key = messageKey(dialog, item)
        const mediaUrl = media[key]
        return <div className="album-media-cell" key={key}>{mediaUrl ? <img src={mediaUrl} alt="پیش‌نمایش رسانه پیام" title="برای دریافت و نمایش تصویر اصلی کلیک کنید" loading="lazy" decoding="async" draggable onClick={e => { e.stopPropagation(); void openFullMedia(item) }} onDragStart={e => { e.dataTransfer.setData('application/x-eitaa-source', key); e.dataTransfer.effectAllowed = 'copy' }} /> : mediaUrl === null ? <div className="media-placeholder media-skeleton"><Skeleton variant="rectangular" animation="wave" width="100%" height="100%" /><span>در حال دریافت تصویر…</span></div> : <div className="media-placeholder">پیش‌نمایش تصویر</div>}</div>
      })}
    </div>}
    {files.map(item => <div className="file-chip" key={messageKey(dialog, item)}>📎 {item.media?.file_name || item.media?.type}</div>)}
    {caption && <div className="message-text">{caption}</div>}
    {indexPredictions.length > 0 && <div className="message-index-badges" aria-label="پیشنهادهای ایندکس محلی">
      {indexPredictions.map(prediction => <span
        className={`message-index-badge ${prediction.manual ? 'manual' : ''}`}
        key={prediction.label_id}
        title={`${Math.round(prediction.score * 100)}٪${prediction.evidence.length ? ` — نشانه‌ها: ${prediction.evidence.join('، ')}` : ''}`}
      >{prediction.label_name} <b>{prediction.manual ? 'دستی' : `${Math.round(prediction.score * 100)}٪`}</b></span>)}
      <button type="button" className="message-index-edit" title="اصلاح ایندکس‌های این پیام" onClick={event => { event.stopPropagation(); editIndex() }}>اصلاح</button>
    </div>}
    <div className="message-footer"><span>{album ? `#${firstId}–#${lastId}` : `#${message.id}`}</span><time>{formatDate(album?.last.date || message.date)}</time>{anyUsed && <button className="usage-badge badge" onClick={e => { e.stopPropagation(); openUsage() }}>{anyStale ? 'تغییرکرده' : allUsed ? 'وردپرس' : 'بخشی در وردپرس'}</button>}</div>
    {(selectionMode || selected) && <input aria-label={album ? 'انتخاب گالری' : 'انتخاب پیام'} className="checkbox checkbox-neutral message-checkmark" type="checkbox" checked={selected} readOnly />}
    {!selectionMode && !anyUsed && <button className="select-hover btn btn-xs" onClick={e => { e.stopPropagation(); toggle() }}>{album ? 'انتخاب گالری' : 'انتخاب'}</button>}
  </article>
}

function Composer(props: { dialog: DialogItem | null; dialogs: DialogItem[]; siteKey: string; sites: Site[]; setSiteKey: (v: string) => void; wordpressReady: boolean; openSettings: () => void; openBulk: (mode: BulkMode) => void; openMembers: () => void; selectedMessages: MessageItem[]; selectedKeys: string[]; setSelectedKeys: (v: string[]) => void; suggestedCategoryIds: number[]; categories: Term[]; tags: Term[]; setTags: (v: Term[]) => void; media: Record<string, string | null>; activeUsage: { message: MessageItem; usage: MessageUsage } | null; clearUsage: () => void; close: () => void; communityOpen: boolean; setCommunityOpen: (v: boolean) => void; onSuccess: () => Promise<void>; markSourcesUsed: (sourceKeys: string[], publication: { composition_key: string; post_id: number; post_url?: string | null; status: string; title: string }) => void }) {
  const [compositionKey, setCompositionKey] = useState(makeCompositionKey)
  const [title, setTitle] = useState('')
  const [excerpt, setExcerpt] = useState('')
  const [categoryIds, setCategoryIds] = useState<number[]>([])
  const [tagIds, setTagIds] = useState<number[]>([])
  const [tagSearch, setTagSearch] = useState('')
  const [featuredKey, setFeaturedKey] = useState<string | null>(null)
  const [includeFeatured, setIncludeFeatured] = useState(true)
  const [postStatus, setPostStatus] = useState<'draft' | 'publish'>('draft')
  const [confirmPublish, setConfirmPublish] = useState(false)
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState<ComposerResult | null>(null)
  const [error, setError] = useState('')
  const [editRecord, setEditRecord] = useState<CompositionRecord | null>(null)
  const [editSourceKeys, setEditSourceKeys] = useState<string[]>([])
  const categoryRows = useMemo(() => categoryTree(props.categories), [props.categories])

  const sourceKeys = editRecord ? editSourceKeys : props.selectedKeys
  useEffect(() => {
    if (editRecord || !props.selectedKeys.length) { if (!editRecord && !props.selectedKeys.length) setFeaturedKey(null); return }
    if (!featuredKey || !props.selectedKeys.includes(featuredKey)) {
      const firstImageIndex = props.selectedMessages.findIndex(message => message.media?.is_image)
      if (firstImageIndex >= 0) setFeaturedKey(props.selectedKeys[firstImageIndex])
    }
  }, [props.selectedKeys.join('|'), editRecord]) // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (editRecord || !props.selectedKeys.length || !props.suggestedCategoryIds.length) return
    setCategoryIds(current => [...new Set([...current, ...props.suggestedCategoryIds])])
  }, [editRecord, props.selectedKeys.join('|'), props.suggestedCategoryIds.join('|')]) // eslint-disable-line react-hooks/exhaustive-deps

  const reset = (clearSelection = true) => {
    setCompositionKey(makeCompositionKey()); setTitle(''); setExcerpt(''); setCategoryIds([]); setTagIds([]); setTagSearch(''); setFeaturedKey(null); setIncludeFeatured(true); setPostStatus('draft'); setConfirmPublish(false); setResult(null); setError(''); setEditRecord(null); setEditSourceKeys([]); props.clearUsage()
    if (clearSelection) props.setSelectedKeys([])
  }

  const buildSources = () => {
    if (editRecord) return editSourceKeys.map(key => {
      const parsed = parseSourceKey(key)
      const sourceDialog = props.dialogs.find(item => item.peer_key === parsed.peerKey)
      if (!sourceDialog) throw new Error(`گفتگوی مربوط به پیام ${parsed.messageId} در فهرست محلی نیست؛ ابتدا آن را دستی اضافه کنید.`)
      return { peer_file: sourceDialog.peer_file, message_id: parsed.messageId }
    })
    if (!props.dialog) throw new Error('ابتدا یک گفتگو را انتخاب کنید.')
    if (!props.selectedMessages.length) throw new Error('حداقل یک پیام استفاده‌نشده را انتخاب کنید.')
    return props.selectedMessages.map(message => ({ peer_file: props.dialog!.peer_file, message_id: message.id }))
  }

  const composition = () => ({ composition_key: compositionKey, site_key: props.siteKey, title, excerpt, category_ids: categoryIds, tag_ids: tagIds, featured_source_index: featuredKey ? sourceKeys.indexOf(featuredKey) : null, include_featured_in_body: includeFeatured, post_status: postStatus, confirm_publish: postStatus === 'publish' ? confirmPublish : false, sources: buildSources() })

  const run = async (action: 'preview' | 'publish' | 'update') => {
    setBusy(true); setError(''); setResult(null)
    try {
      if (!title.trim()) throw new Error('عنوان نوشته را وارد کنید.')
      if (!sourceKeys.length) throw new Error('حداقل یک پیام لازم است.')
      const committedSourceKeys = [...sourceKeys]
      const response = await api<any>('POST', `/api/v1/compositions/${action}`, { composition: composition() })
      setResult(response)
      toast.success(action === 'preview' ? 'پیش‌نمایش معتبر است.' : action === 'update' ? 'نوشته وردپرس به‌روزرسانی شد و فرم پاک شد.' : 'نوشته وردپرس ایجاد شد و فرم پاک شد.')
      if (action !== 'preview') {
        let refreshFailed = false
        try { await props.onSuccess() } catch { refreshFailed = true }
        const postId = Number(response.post?.id || response.record?.post_id || 0)
        if (postId > 0) {
          props.markSourcesUsed(committedSourceKeys, {
            composition_key: String(response.record?.composition_key || compositionKey),
            post_id: postId,
            post_url: response.post?.link || response.record?.post_url || null,
            status: String(response.post?.status || response.record?.status || postStatus),
            title: String(response.record?.title || title),
          })
        }
        reset(true)
        if (refreshFailed) toast.warning('نوشته ذخیره شد؛ نشان استفاده‌شدن پیام‌ها به‌صورت محلی به‌روزرسانی شد و در اجرای بعد نیز از پایگاه داده بازیابی می‌شود.')
      }
    } catch (e) { const message = e instanceof Error ? e.message : 'عملیات ناموفق بود.'; setError(message); toast.error(message) }
    finally { setBusy(false) }
  }

  const move = (from: number, to: number) => {
    const next = [...sourceKeys]; const [item] = next.splice(from, 1); next.splice(to, 0, item)
    if (editRecord) setEditSourceKeys(next); else props.setSelectedKeys(next)
  }

  const appendSelectedToEdit = () => {
    if (!editRecord) return
    const additions = props.selectedKeys.filter(key => !editSourceKeys.includes(key))
    if (!additions.length) { toast.info('پیام انتخاب‌شده جدیدی برای افزودن وجود ندارد.'); return }
    setEditSourceKeys(current => [...current, ...additions.filter(key => !current.includes(key))])
    if (!featuredKey) {
      const firstImage = props.selectedMessages.find(message => message.media?.is_image)
      if (firstImage && props.dialog) setFeaturedKey(messageKey(props.dialog, firstImage))
    }
    props.setSelectedKeys([])
    toast.success(`${additions.length.toLocaleString('fa-IR')} پیام به انتهای نوشته افزوده شد.`)
  }

  const loadHistory = async (target: { composition_key: string }) => {
    setBusy(true); setError('')
    try {
      const response = await api<{ compositions: CompositionRecord[] }>('GET', query('/api/v1/compositions', { site_key: props.siteKey, limit: 500 }))
      const record = response.compositions.find(item => item.composition_key === target.composition_key)
      if (!record) throw new Error('رکورد Composition پیدا نشد.')
      let live = { title: record.title, excerpt: record.excerpt, category_ids: record.category_ids, tag_ids: record.tag_ids, status: record.status, link: record.post_url }
      try {
        const remote = await api<{ post: typeof live }>('POST', '/api/v1/wordpress/post', { site_key: props.siteKey, post_id: record.post_id })
        live = remote.post
      } catch { /* local composition state remains a safe fallback */ }
      setEditRecord({ ...record, post_url: live.link || record.post_url }); setEditSourceKeys([...record.source_keys]); setTitle(live.title); setExcerpt(live.excerpt); setCategoryIds(live.category_ids); setTagIds(live.tag_ids); setCompositionKey(record.composition_key); setFeaturedKey(record.featured_source_key || null); setPostStatus(live.status === 'publish' ? 'publish' : 'draft'); setConfirmPublish(false); setResult(null)
    } catch (e) { setError(e instanceof Error ? e.message : 'بارگذاری سابقه ناموفق بود.') }
    finally { setBusy(false) }
  }

  const chooseTag = (term: Term) => {
    setTagIds(current => current.includes(term.id) ? current : [...current, term.id])
    setTagSearch('')
  }

  const createTag = async (requestedName?: string) => {
    const name = (requestedName ?? tagSearch).trim()
    if (!name) return
    const existing = props.tags.find(term => term.name.trim().toLocaleLowerCase('fa') === name.toLocaleLowerCase('fa'))
    if (existing) { chooseTag(existing); return }
    setBusy(true); setError('')
    try {
      const response = await api<{ term: Term }>('POST', '/api/v1/wordpress/tags', { site_key: props.siteKey, name })
      const merged = [...props.tags.filter(item => item.id !== response.term.id), response.term].sort((a, b) => a.name.localeCompare(b.name, 'fa'))
      props.setTags(merged); setTagIds(current => current.includes(response.term.id) ? current : [...current, response.term.id]); setTagSearch(''); toast.success(`کلمه کلیدی «${response.term.name}» ساخته و انتخاب شد.`)
    } catch (e) { setError(e instanceof Error ? e.message : 'ساخت کلمه کلیدی ناموفق بود.') }
    finally { setBusy(false) }
  }

  const normalizedTagSearch = tagSearch.trim().toLocaleLowerCase('fa')
  const filteredTags = normalizedTagSearch
    ? props.tags
      .filter(term => !tagIds.includes(term.id) && term.name.toLocaleLowerCase('fa').includes(normalizedTagSearch))
      .slice(0, 8)
    : []
  const exactTagMatch = props.tags.some(term => term.name.trim().toLocaleLowerCase('fa') === normalizedTagSearch)
  const featuredPreview = featuredKey ? props.media[featuredKey] : null

  return <div className="composer-inner">
    <div className="composer-chrome">
      <div className="pane-header composer-header">
        <div className="composer-context">
          <span className={`composer-context-mark ${props.communityOpen ? 'conversation' : 'wordpress'}`} aria-hidden="true">
            <Icon name={props.communityOpen ? 'group' : 'wordpress'} size={21} />
          </span>
          <div><h2>{props.communityOpen ? 'عملیات گفتگو' : editRecord ? `ویرایش نوشته #${editRecord.post_id}` : 'نوشته جدید وردپرس'}</h2><small>{props.communityOpen ? titleFor(props.dialog) : `${sourceKeys.length} پیام در بدنه`}</small></div>
        </div>
        <button type="button" className="close-drawer" aria-label="بستن ستون وردپرس" onClick={props.close}>×</button>
      </div>
      <div className="composer-section-tabs tabs tabs-box" role="tablist" aria-label="بخش ستون سوم">
        <button type="button" role="tab" aria-selected={!props.communityOpen} className={`tab wordpress-tab ${!props.communityOpen ? 'active' : ''}`} disabled={!props.wordpressReady} title={props.wordpressReady ? 'وردپرس' : 'ابتدا سایت و دسترسی وردپرس را تعریف کنید'} onClick={() => props.setCommunityOpen(false)}>وردپرس</button>
        <button type="button" role="tab" aria-selected={props.communityOpen} className={`tab conversation-tab ${props.communityOpen ? 'active' : ''}`} onClick={() => props.setCommunityOpen(true)}>عملیات گفتگو</button>
      </div>
    </div>
    {props.communityOpen ? <section className="community-panel fieldset bg-base-200 border-base-300 rounded-box border p-4">
      <legend className="fieldset-legend">{titleFor(props.dialog)}</legend>
      <div className="community-summary"><div className="avatar small">{initials(titleFor(props.dialog))}</div><div><b>{titleFor(props.dialog)}</b><small>{props.dialog?.peer.username ? `@${props.dialog.peer.username}` : props.dialog ? `Peer ID: ${props.dialog.peer.id}` : 'گفتگویی انتخاب نشده'}</small></div></div>
      <div className="community-actions">
        <button type="button" className="btn btn-neutral btn-sm" onClick={() => props.openBulk(props.dialog && props.dialog.display_kind !== 'personal' ? 'members' : 'numbers')}>ارسال و دعوت گروهی</button>
        <button type="button" className="btn btn-outline btn-sm" disabled={!props.dialog || props.dialog.display_kind === 'personal'} onClick={props.openMembers}>مدیریت اعضا</button>
        <small>{!props.dialog ? 'ارسال به شماره‌ها در دسترس است؛ برای عملیات اعضا ابتدا یک گروه یا کانال را انتخاب کنید.' : props.dialog.display_kind === 'personal' ? 'در گفتگوی شخصی، ابزار یکپارچه روی ارسال به شماره‌ها باز می‌شود.' : 'اعضای گفتگو، شماره‌های جدید و دعوت شماره‌ها همگی در یک ابزار و سه تب مستقل قرار دارند.'}</small>
      </div>
    </section> : !props.wordpressReady ? <section className="wordpress-unavailable card"><Icon name="wordpress" size={38} /><h3>وردپرس هنوز آماده نیست</h3><p>تا زمانی که یک سایت با نام کاربری و رمز برنامه معتبر تعریف نشده، دریافت دسته‌ها و دکمه‌های ساخت نوشته غیرفعال می‌مانند.</p><button type="button" className="btn btn-neutral" onClick={props.openSettings}>بازکردن تنظیمات سایت‌ها</button></section> : <>

    {props.activeUsage && !editRecord && <section className="history-card card"><div className="section-title"><h3>سابقه پیام #{props.activeUsage.message.id}</h3><button onClick={props.clearUsage}>×</button></div>
      {props.activeUsage.usage.compositions.length ? props.activeUsage.usage.compositions.map(item => <div className="history-item" key={item.composition_key}><b>{item.title || `نوشته ${item.post_id}`}</b><span>Post ID: {item.post_id} • {item.status}</span><div><button className="btn btn-sm" onClick={() => void loadHistory(item)}>بارگذاری برای ویرایش</button>{item.post_url && <button className="btn btn-sm btn-ghost" onClick={() => window.eitaaDesktop.openExternal(item.post_url!)}>بازکردن وردپرس</button>}</div></div>) : <div className="history-item"><b>انتقال قدیمی تک‌پیامی</b><span>Post ID: {String(props.activeUsage.usage.external_post_id || '—')}</span>{props.activeUsage.usage.external_url && <button className="btn btn-sm" onClick={() => window.eitaaDesktop.openExternal(props.activeUsage!.usage.external_url!)}>بازکردن وردپرس</button>}<small>این رکورد با Composer چندپیامی ساخته نشده و از این فرم قابل ویرایش نیست.</small></div>}
    </section>}

    {editRecord && <div className="edit-banner alert"><div><b>حالت ویرایش فعال است</b><span>همان Post ID {editRecord.post_id} به‌روزرسانی می‌شود؛ حذف منابع قبلی مجاز نیست، اما می‌توانید پیام‌های جدید را به انتهای نوشته اضافه کنید.</span></div>{editRecord.post_url && <button className="btn btn-sm" onClick={() => window.eitaaDesktop.openExternal(editRecord.post_url!)}>مشاهده</button>}</div>}
    <fieldset className="fieldset wp-fieldset bg-base-200 border-base-300 rounded-box border p-4">
      <legend className="fieldset-legend">مشخصات نوشته</legend>
      <label className="label">سایت مقصد</label><select className="select w-full" value={props.siteKey} disabled={!!editRecord} onChange={e => props.setSiteKey(e.target.value)}>{props.sites.map(site => <option key={site.site_key} value={site.site_key}>{site.site_key} — {site.base_url}</option>)}</select>
      <label className="label">عنوان مطلب</label><input className="input w-full" value={title} onChange={e => setTitle(e.target.value)} placeholder="عنوان نوشته وردپرس" />
      <label className="label">چکیده</label><textarea className="textarea w-full" value={excerpt} onChange={e => setExcerpt(e.target.value)} rows={3} placeholder="Excerpt وردپرس" />
    </fieldset>

    <fieldset className="fieldset taxonomy-box wp-fieldset bg-base-200 border-base-300 rounded-box border p-4">
      <legend className="fieldset-legend">دسته‌ها <small>{categoryIds.length} انتخاب</small></legend>
      <div className="selected-taxonomies" aria-label="دسته‌های انتخاب‌شده">
        {categoryIds.length ? categoryIds.map(id => { const term = props.categories.find(item => item.id === id); return term ? <button type="button" key={id} className="badge taxonomy-chip" onClick={() => setCategoryIds(current => current.filter(item => item !== id))}>{term.name}<span aria-hidden="true">×</span></button> : null }) : <small>هنوز دسته‌ای انتخاب نشده است.</small>}
      </div>
      <div className="checkbox-list category-list" role="tree">{categoryRows.map(({ term, depth }) => <label key={term.id} className={`check-row category-tree-row depth-${Math.min(depth, 6)}`} role="treeitem" aria-level={depth + 1} style={{ paddingInlineStart: `${8 + Math.min(depth, 6) * 20}px` }}><span className="category-branch" aria-hidden="true">{depth ? '↳' : '•'}</span><input className="checkbox checkbox-neutral" type="checkbox" checked={categoryIds.includes(term.id)} onChange={e => setCategoryIds(current => e.target.checked ? [...current, term.id] : current.filter(id => id !== term.id))} /><span>{term.name}</span></label>)}</div>
    </fieldset>

    <fieldset className="fieldset taxonomy-box wp-fieldset tag-fieldset bg-base-200 border-base-300 rounded-box border p-4">
      <legend className="fieldset-legend">کلمات کلیدی <small>{tagIds.length} انتخاب</small></legend>
      <div className="selected-taxonomies selected-tags">{tagIds.length ? tagIds.map(id => { const term = props.tags.find(item => item.id === id); return term ? <button type="button" key={id} className="badge taxonomy-chip tag-chip" onClick={() => setTagIds(current => current.filter(item => item !== id))}>{term.name}<span aria-hidden="true">×</span></button> : null }) : <small>نام یک کلمه کلیدی را تایپ کنید.</small>}</div>
      <div className="tag-combobox">
        <input
          className="input w-full tag-autocomplete-input"
          value={tagSearch}
          onChange={e => setTagSearch(e.target.value)}
          onKeyDown={e => {
            if (e.key === 'Enter') {
              e.preventDefault()
              if (filteredTags.length) chooseTag(filteredTags[0])
              else if (tagSearch.trim()) void createTag(tagSearch)
            } else if (e.key === 'Escape') setTagSearch('')
          }}
          role="combobox"
          aria-expanded={Boolean(normalizedTagSearch)}
          aria-controls="tag-suggestions"
          autoComplete="off"
          placeholder="نام کلمه کلیدی را تایپ کنید…"
        />
        {normalizedTagSearch && <div id="tag-suggestions" className="tag-suggestions" role="listbox">
          {filteredTags.map(term => <button type="button" role="option" key={term.id} onMouseDown={e => e.preventDefault()} onClick={() => chooseTag(term)}><b>{term.name}</b><small>انتخاب کلمه کلیدی موجود</small></button>)}
          {!exactTagMatch && <button type="button" className="create-tag-suggestion" disabled={busy} onMouseDown={e => e.preventDefault()} onClick={() => void createTag(tagSearch)}><b>ساخت «{tagSearch.trim()}»</b><small>کلمه کلیدی جدید در وردپرس</small></button>}
          {!filteredTags.length && exactTagMatch && <div className="tag-no-result">این کلمه کلیدی قبلاً انتخاب شده است.</div>}
        </div>}
      </div>
      <small className="tag-help">با Enter نخستین پیشنهاد انتخاب می‌شود؛ اگر موردی وجود نداشته باشد، کلمه کلیدی جدید ساخته خواهد شد.</small>
    </fieldset>

    <section className="selected-section card"><div className="section-title"><h3>ترتیب بدنه</h3><div className="section-title-actions">{editRecord && props.selectedKeys.some(key => !editSourceKeys.includes(key)) && <button className="btn btn-sm btn-secondary" onClick={appendSelectedToEdit}>افزودن {props.selectedKeys.filter(key => !editSourceKeys.includes(key)).length.toLocaleString('fa-IR')} پیام انتخاب‌شده</button>}{!editRecord && props.selectedKeys.length > 0 && <button onClick={() => props.setSelectedKeys([])}>پاک‌کردن</button>}</div></div>
      {!sourceKeys.length ? <div className="drop-empty">در ستون پیام‌ها راست‌کلیک کنید و پیام‌ها را انتخاب کنید.</div> : sourceKeys.map((key, index) => {
        const parsed = parseSourceKey(key); const message = !editRecord ? props.selectedMessages[index] : null
        return <div key={key} className="selected-source" draggable onDragStart={e => e.dataTransfer.setData('text/plain', String(index))} onDragOver={e => e.preventDefault()} onDrop={e => { e.preventDefault(); move(Number(e.dataTransfer.getData('text/plain')), index) }}><span className="drag">⋮⋮</span><b>#{parsed.messageId}</b><span>{message?.text.slice(0, 45) || message?.media?.type || `${parsed.peerType}:${parsed.peerId}`}</span>{!editRecord && <button onClick={() => props.setSelectedKeys(props.selectedKeys.filter(item => item !== key))}>×</button>}</div>
      })}
    </section>

    <section className={`featured-drop card ${featuredKey ? 'has-image' : ''}`} onDragOver={e => { e.preventDefault(); e.dataTransfer.dropEffect = 'copy' }} onDrop={e => { e.preventDefault(); const key = e.dataTransfer.getData('application/x-eitaa-source'); if (sourceKeys.includes(key)) setFeaturedKey(key) }}>
      <div className="section-title"><h3>تصویر شاخص</h3>{featuredKey && <button onClick={() => setFeaturedKey(null)}>حذف</button>}</div>
      {featuredPreview ? <img src={featuredPreview} alt="تصویر شاخص" /> : featuredKey ? <p>تصویر شاخص ثبت‌شده: پیام #{parseSourceKey(featuredKey).messageId}</p> : <p>تصویر یک پیام انتخاب‌شده را از ستون وسط اینجا بکشید.</p>}
      <label className="inline-check"><input className="checkbox checkbox-neutral" type="checkbox" checked={includeFeatured} onChange={e => setIncludeFeatured(e.target.checked)} /> نمایش تصویر شاخص در بدنه</label>
    </section>

    <div className="publish-choice"><label><input name="wordpress_post_status" className="radio radio-secondary" type="radio" checked={postStatus === 'draft'} onChange={() => { setPostStatus('draft'); setConfirmPublish(false) }} /> پیش‌نویس</label><label><input name="wordpress_post_status" className="radio radio-secondary" type="radio" checked={postStatus === 'publish'} onChange={() => setPostStatus('publish')} /> انتشار مستقیم</label></div>
    {postStatus === 'publish' && <label className="publish-confirm"><input className="checkbox checkbox-neutral" type="checkbox" checked={confirmPublish} onChange={e => setConfirmPublish(e.target.checked)} /> تأیید می‌کنم نوشته بلافاصله عمومی یا به‌روزرسانی شود.</label>}
    {error && <div className="error-box alert alert-error">{error}</div>}
    {result && <div className="success-box alert alert-success"><b>{result.outcome === 'composition_created' ? 'نوشته ایجاد شد' : result.outcome === 'composition_updated' ? 'نوشته به‌روزرسانی شد' : 'پیش‌نمایش معتبر است'}</b>{result.post?.id && <span>Post ID: {result.post.id}</span>}{result.plan?.blocked_source_count > 0 && <span>{result.plan.blocked_source_count} پیام قبلاً استفاده شده است.</span>}</div>}
    <div className="composer-actions">
      {!editRecord && <button className="btn btn-secondary secondary" disabled={busy} onClick={() => void run('preview')}>پیش‌نمایش</button>}
      <button className="btn btn-neutral" disabled={busy || !sourceKeys.length || (postStatus === 'publish' && !confirmPublish)} onClick={() => void run(editRecord ? 'update' : 'publish')}>{busy ? <><span className="loading loading-dots loading-sm" /> در حال انجام</> : editRecord ? 'به‌روزرسانی همان نوشته' : postStatus === 'publish' ? 'انتشار' : 'ساخت پیش‌نویس'}</button>
      <button className="btn btn-ghost link-button" onClick={() => reset(true)}>فرم جدید</button>
    </div>
    </>}
  </div>
}

function ManualDialogModal({ siteKey, close, onAdded }: { siteKey: string; close: () => void; onAdded: (item: DialogItem) => void }) {
  const [mode, setMode] = useState<'username' | 'peer'>('username')
  const [username, setUsername] = useState('')
  const [peerType, setPeerType] = useState<PeerType>('channel')
  const [peerId, setPeerId] = useState('')
  const [accessHash, setAccessHash] = useState('')
  const [title, setTitle] = useState('')
  const [displayKind, setDisplayKind] = useState<DisplayKind>('channel')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => { if (event.key === 'Escape') close() }
    window.addEventListener('keydown', onKey); return () => window.removeEventListener('keydown', onKey)
  }, [close])
  const submit = async (event: FormEvent) => {
    event.preventDefault(); setBusy(true); setError('')
    try {
      const payload = mode === 'username' ? { site_key: siteKey, mode, username, display_kind: displayKind } : { site_key: siteKey, mode, peer_type: peerType, peer_id: peerId, access_hash: accessHash || null, title, username: username || null, display_kind: displayKind }
      const response = await api<{ dialog: DialogItem }>('POST', '/api/v1/dialogs/manual', payload); onAdded(response.dialog)
    } catch (e) { setError(e instanceof Error ? e.message : 'افزودن گفتگو ناموفق بود.') }
    finally { setBusy(false) }
  }
  return <MaterialLegacyDialog close={close} maxWidth="sm"><form className="eb-dialog card material-dialog-surface" aria-label="افزودن دستی گفتگو" onSubmit={submit}><div className="section-title"><h2>افزودن دستی گفتگو</h2><button type="button" className="dialog-close" onClick={close} title="بستن"><Icon name="close" /></button></div>
    <div className="mode-tabs tabs tabs-box" role="tablist" aria-label="روش افزودن گفتگو"><button type="button" role="tab" aria-selected={mode === 'username'} className={`tab ${mode === 'username' ? 'active' : ''}`} onClick={() => setMode('username')}>با نام کاربری</button><button type="button" role="tab" aria-selected={mode === 'peer'} className={`tab ${mode === 'peer' ? 'active' : ''}`} onClick={() => setMode('peer')}>شناسه و Access Hash</button></div>
    <fieldset className="fieldset manual-fieldset bg-base-200 border-base-300 rounded-box border p-4">
      <legend className="fieldset-legend">مشخصات گفتگو</legend>
      <label className="label">نمایش در رابط</label>
      <select className="select w-full" value={displayKind} onChange={e => setDisplayKind(e.target.value as DisplayKind)}><option value="channel">کانال</option><option value="group">گروه</option><option value="personal">شخصی</option></select>
      {mode === 'username' ? <>
        <label className="label">نام کاربری</label>
        <input className="input w-full" dir="ltr" value={username} onChange={e => setUsername(e.target.value)} placeholder="username یا @username" />
      </> : <>
        <label className="label">نوع فنی Peer</label>
        <select className="select w-full" value={peerType} onChange={e => setPeerType(e.target.value as PeerType)}><option value="channel">channel</option><option value="chat">chat</option><option value="user">user</option></select>
        <label className="label">Peer ID</label>
        <input className="input w-full" dir="ltr" value={peerId} onChange={e => setPeerId(e.target.value)} />
        <label className="label">Access Hash</label>
        <input className="input w-full" dir="ltr" value={accessHash} onChange={e => setAccessHash(e.target.value)} placeholder="برای Peer خصوصی معمولاً لازم است" />
        <label className="label">عنوان نمایشی</label>
        <input className="input w-full" value={title} onChange={e => setTitle(e.target.value)} />
        <label className="label">نام کاربری اختیاری</label>
        <input className="input w-full" dir="ltr" value={username} onChange={e => setUsername(e.target.value)} />
      </>}
    </fieldset>
    <div className="notice">اگر یک سوپرگروه از نظر فنی با نوع channel برگردد، نوع فنی را channel و «نمایش در UI» را گروه انتخاب کنید.</div>
    {error && <div className="error-box">{error}</div>}<div className="modal-actions"><button type="button" className="btn btn-ghost" onClick={close}>انصراف</button><button className="btn btn-neutral" disabled={busy}>{busy ? <><span className="loading loading-dots loading-sm" /> در حال افزودن</> : 'افزودن'}</button></div>
  </form></MaterialLegacyDialog>
}

type CommunityMemberItem = {
  community: { id: number; type: string }
  user: {
    peer: { id: number; type: string }
    display_name: string
    phone?: string | null
    status?: { kind?: string } | null
    is_bot?: boolean
    is_deleted?: boolean
  }
  role: string
  state: string
  sendable: boolean
}

function CommunityMembersModal({ siteKey, dialog, close, openBulk }: { siteKey: string; dialog: DialogItem | null; close: () => void; openBulk: (memberIds: number[]) => void }) {
  const [members, setMembers] = useState<CommunityMemberItem[]>([])
  const [search, setSearch] = useState('')
  const [sendableOnly, setSendableOnly] = useState(false)
  const [includeBots, setIncludeBots] = useState(false)
  const [selected, setSelected] = useState<number[]>([])
  const [summary, setSummary] = useState<any>(null)
  const [syncSummary, setSyncSummary] = useState<any>(null)
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const [contactCategories, setContactCategories] = useState<Array<{ id: number; name: string }>>([])
  const [contactCategoryIds, setContactCategoryIds] = useState<number[]>([])
  const [contactImportJob, setContactImportJob] = useState<any>(null)
  const contactImportActive = Boolean(contactImportJob && ['queued', 'running', 'cancelling'].includes(contactImportJob.state))

  const waitTask = async (taskId: string) => {
    for (let attempt = 0; attempt < 3600; attempt += 1) {
      await new Promise(resolve => window.setTimeout(resolve, 1000))
      const response = await api<{ task: any }>('GET', query('/api/v1/background/status', { task_id: taskId }))
      if (response.task.status === 'failed') {
        const detail = response.task.error?.message || response.task.error?.error_code || response.task.error_type || 'خطای نامشخص'
        throw new Error(`همگام‌سازی اعضا متوقف شد: ${detail}`)
      }
      if (response.task.status === 'completed') return response.task.result
    }
    throw new Error('همگام‌سازی اعضا بیش از حد طول کشید؛ وضعیت در بخش پشتیبان حفظ شده است.')
  }

  const loadLocal = useCallback(async () => {
    if (!dialog || dialog.display_kind === 'personal') return
    setBusy(current => current || 'list'); setError('')
    try {
      const response = await api<{ page: any }>('POST', '/api/v1/community/members/list', {
        site_key: siteKey,
        peer_file: dialog.peer_file,
        text: search.trim() || undefined,
        sendable_only: sendableOnly,
        include_bots: includeBots,
        offset: 0,
        limit: 300,
      })
      setMembers(response.page.members || [])
      setSummary(response.page)
      setSelected(current => current.filter(id => (response.page.members || []).some((item: CommunityMemberItem) => item.user.peer.id === id && item.sendable)))
    } catch (e) { setError(e instanceof Error ? e.message : 'خواندن اعضای محلی ناموفق بود.') }
    finally { setBusy(current => current === 'list' ? '' : current) }
  }, [dialog?.peer_key, siteKey, search, sendableOnly, includeBots])

  useEffect(() => { void loadLocal() }, [loadLocal])
  useEffect(() => {
    void api<{ categories: Array<{ id: number; name: string }> }>('GET', '/api/v1/contacts/categories')
      .then(response => setContactCategories(response.categories))
      .catch(() => undefined)
  }, [])
  useEffect(() => {
    if (!contactImportActive) return
    const timer = window.setInterval(() => {
      void api<{ job: any }>('GET', query('/api/v1/contacts/import/status', { job_id: contactImportJob.job_id }))
        .then(response => {
          setContactImportJob(response.job)
          if (response.job.state === 'completed') {
            const progress = response.job.progress || {}
            toast.success(`${Number(progress.imported || 0).toLocaleString('fa-IR')} مخاطب جدید و ${Number(progress.updated || 0).toLocaleString('fa-IR')} مخاطب به‌روزشده در دفترچه ثبت شد.`)
          } else if (response.job.state === 'failed') {
            setError(response.job.error?.message || 'ورود اعضا به دفترچه ناموفق بود.')
          }
        })
        .catch(() => undefined)
    }, 1000)
    return () => window.clearInterval(timer)
  }, [contactImportActive, contactImportJob?.job_id])
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => { if (event.key === 'Escape' && !busy && !contactImportActive) close() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [busy, close, contactImportActive])

  const syncRemote = async () => {
    if (!dialog || dialog.display_kind === 'personal') return
    setBusy('sync'); setError(''); setSyncSummary(null)
    try {
      const started = await api<{ task: { task_id: string } }>('POST', '/api/v1/community/members/sync/start', {
        site_key: siteKey,
        peer_file: dialog.peer_file,
        page_size: 200,
        max_pages: Math.min(250, Math.max(1, Math.ceil((dialog.participants_count || 50_000) / 200))),
        expected_total: dialog.participants_count || undefined,
      })
      const completed = await waitTask(started.task.task_id)
      setSyncSummary(completed?.sync || completed)
      await loadLocal()
      toast.success('Snapshot اعضای گفتگو به‌روزرسانی شد.')
    } catch (e) { setError(e instanceof Error ? e.message : 'همگام‌سازی اعضا ناموفق بود.') }
    finally { setBusy('') }
  }

  const sendableMembers = members.filter(item => item.sendable)
  const allVisibleSelected = sendableMembers.length > 0 && sendableMembers.every(item => selected.includes(item.user.peer.id))
  const toggleAll = () => setSelected(allVisibleSelected ? [] : sendableMembers.map(item => item.user.peer.id))
  const startContactImport = async (memberIds?: number[]) => {
    if (!dialog || dialog.display_kind === 'personal') return
    setError('')
    try {
      const response = await api<{ job: any }>('POST', '/api/v1/contacts/import/community/start', {
        site_key: siteKey,
        peer_file: dialog.peer_file,
        member_ids: memberIds,
        include_bots: includeBots,
        category_ids: contactCategoryIds,
      })
      setContactImportJob(response.job)
      toast.info('ورود محلی اعضا آغاز شد؛ این کار Scheduler ایتا را اشغال نمی‌کند.')
    } catch (e) { setError(e instanceof Error ? e.message : 'شروع ورود اعضا ناموفق بود.') }
  }

  return <MaterialLegacyDialog close={close} locked={Boolean(busy) || contactImportActive} maxWidth="lg">
    <section className="eb-dialog members-dialog card material-dialog-surface" aria-label="مدیریت اعضای گفتگو">
      <div className="section-title"><div><h2>مدیریت اعضای گفتگو</h2><small>{titleFor(dialog)} — Snapshot محلی و بدون نمایش Access Hash</small></div><button className="dialog-close" disabled={Boolean(busy)} onClick={close}><Icon name="close" /></button></div>
      {!dialog || dialog.display_kind === 'personal' ? <div className="error-box alert alert-error">برای مدیریت اعضا یک گروه یا کانال را انتخاب کنید.</div> : <>
        <div className="members-toolbar">
          <div className="message-search"><Icon name="search" size={17} /><input value={search} onChange={event => setSearch(event.target.value)} placeholder="جست‌وجوی نام عضو" /></div>
          <label className="inline-check"><input className="checkbox checkbox-neutral" type="checkbox" checked={sendableOnly} onChange={event => setSendableOnly(event.target.checked)} /> فقط قابل ارسال</label>
          <label className="inline-check"><input className="checkbox checkbox-neutral" type="checkbox" checked={includeBots} onChange={event => setIncludeBots(event.target.checked)} /> شامل ربات‌ها</label>
          <button className="btn btn-outline btn-sm" disabled={Boolean(busy)} onClick={() => void loadLocal()}>{busy === 'list' ? <span className="loading loading-dots loading-sm" /> : 'بازخوانی محلی'}</button>
          <button className="btn btn-neutral btn-sm" disabled={Boolean(busy)} onClick={() => void syncRemote()}>{busy === 'sync' ? <><span className="loading loading-dots loading-sm" /> همگام‌سازی</> : 'همگام‌سازی از ایتا'}</button>
        </div>
        <div className="members-summary card"><span>نمایش: {members.length.toLocaleString('fa-IR')}</span><span>قابل ارسال: {sendableMembers.length.toLocaleString('fa-IR')}</span><span>انتخاب: {selected.length.toLocaleString('fa-IR')}</span>{summary?.total_count !== undefined && <span>کل Snapshot: {Number(summary.total_count).toLocaleString('fa-IR')}</span>}</div><div className="notice">برای حفظ سرعت، حداکثر ۳۰۰ عضو در هر نمای جست‌وجو نشان داده می‌شود؛ ارسال به همهٔ اعضای قابل ارسال همچنان در هسته انجام می‌شود.</div>
        {syncSummary && <div className="notice">دریافت‌شده: {Number(syncSummary.fetched || 0).toLocaleString('fa-IR')} — جدید: {Number(syncSummary.inserted || 0).toLocaleString('fa-IR')} — به‌روزشده: {Number(syncSummary.updated || 0).toLocaleString('fa-IR')} — Snapshot کامل: {syncSummary.complete_snapshot ? 'بله' : 'خیر'}</div>}
        <div className="members-select-row"><label><input className="checkbox checkbox-neutral" type="checkbox" checked={allVisibleSelected} onChange={toggleAll} /> انتخاب همه اعضای قابل ارسال در فهرست فعلی</label><button className="btn btn-sm btn-secondary" disabled={!selected.length} onClick={() => openBulk(selected)}>ارسال به {selected.length.toLocaleString('fa-IR')} عضو انتخاب‌شده</button><button className="btn btn-sm btn-outline" disabled={!sendableMembers.length} onClick={() => openBulk([])}>ارسال به همه اعضای قابل ارسال</button></div>
        <div className="member-contact-import card">
          <div><b>افزودن به دفترچهٔ محلی</b><small>دادهٔ معتبر مستقیماً از Snapshot محلی خوانده می‌شود؛ Access Hash در UI نمایش داده نمی‌شود.</small></div>
          {contactCategories.length > 0 && <details><summary>دسته‌های مقصد ({contactCategoryIds.length.toLocaleString('fa-IR')})</summary><div className="contact-category-checks">{contactCategories.map(category => <label key={category.id}><input type="checkbox" className="checkbox checkbox-sm" checked={contactCategoryIds.includes(category.id)} onChange={event => setContactCategoryIds(current => event.target.checked ? [...current, category.id] : current.filter(id => id !== category.id))} /><span>{category.name}</span></label>)}</div></details>}
          <div className="member-contact-actions"><button className="btn btn-sm btn-neutral" disabled={!selected.length || contactImportActive || Boolean(busy)} onClick={() => void startContactImport(selected)}>افزودن {selected.length.toLocaleString('fa-IR')} منتخب</button><button className="btn btn-sm btn-outline" disabled={!members.length || contactImportActive || Boolean(busy)} onClick={() => void startContactImport()}>افزودن کل نمایه محلی</button>{contactImportActive && <button className="btn btn-sm btn-ghost danger" disabled={contactImportJob.state === 'cancelling'} onClick={() => void api<{ job: any }>('POST', '/api/v1/contacts/import/cancel', { job_id: contactImportJob.job_id }).then(response => setContactImportJob(response.job))}>لغو ایمن</button>}</div>
          {contactImportJob && <div className={`import-job state-${contactImportJob.state}`}><div><b>{contactImportJob.state === 'completed' ? 'ورود کامل شد' : contactImportJob.state === 'cancelled' ? 'ورود لغو شد' : contactImportJob.state === 'failed' ? 'ورود ناموفق بود' : 'در حال ورود محلی'}</b><span>{Number(contactImportJob.progress?.processed || 0).toLocaleString('fa-IR')} / {Number(contactImportJob.progress?.total || 0).toLocaleString('fa-IR')}</span></div><progress className="progress progress-success" max={Number(contactImportJob.progress?.total || 1)} value={Number(contactImportJob.progress?.processed || 0)} /><small>جدید: {Number(contactImportJob.progress?.imported || 0).toLocaleString('fa-IR')} · به‌روزشده: {Number(contactImportJob.progress?.updated || 0).toLocaleString('fa-IR')} · ردشده/خطا: {(Number(contactImportJob.progress?.skipped || 0) + Number(contactImportJob.progress?.errors || 0)).toLocaleString('fa-IR')}</small></div>}
        </div>
        <div className="member-list" role="list">
          {members.map(item => {
            const id = item.user.peer.id
            const checked = selected.includes(id)
            return <label key={id} className={`member-row ${item.sendable ? '' : 'unsendable'}`} role="listitem">
              <input className="checkbox checkbox-neutral" type="checkbox" disabled={!item.sendable} checked={checked} onChange={() => setSelected(current => current.includes(id) ? current.filter(value => value !== id) : [...current, id])} />
              <span className="avatar small">{initials(item.user.display_name)}</span>
              <span className="member-identity"><b>{item.user.display_name}</b><small>{item.user.phone || `User ID: ${id}`}</small></span>
              <span className="member-role badge">{item.role}</span>
              <span className={`member-sendable badge ${item.sendable ? 'ready' : ''}`}>{item.sendable ? 'قابل ارسال' : item.user.is_deleted ? 'حذف‌شده' : 'بدون Access Hash'}</span>
            </label>
          })}
          {!members.length && !busy && <div className="empty">عضوی در نمایه محلی پیدا نشد. «همگام‌سازی از ایتا» را اجرا کنید.</div>}
        </div>
      </>}
      {error && <div className="error-box alert alert-error">{error}</div>}
      <div className="modal-actions"><button className="btn btn-ghost" disabled={Boolean(busy) || contactImportActive} onClick={close}>بستن</button></div>
    </section>
  </MaterialLegacyDialog>
}

function BulkOperationsModal({ siteKey, dialog, initialMode, initialMemberIds, initialNumbers, close }: { siteKey: string; dialog: DialogItem | null; initialMode: BulkMode; initialMemberIds: number[]; initialNumbers: string[]; close: () => void }) {
  const [mode, setMode] = useState<BulkMode>(initialMode)
  const [memberIds] = useState<number[]>(initialMemberIds)
  const [kind, setKind] = useState<'text' | 'photo' | 'file'>('text')
  const [text, setText] = useState('')
  const [caption, setCaption] = useState('')
  const [filePath, setFilePath] = useState('')
  const [fileInfo, setFileInfo] = useState<{ name: string; size_bytes: number; mime_type: string; kind: string } | null>(null)
  const [numbers, setNumbers] = useState(() => [...new Set(initialNumbers.map(value => value.trim()).filter(Boolean))].join('\n'))
  const [sourceFile, setSourceFile] = useState('')
  const [listName, setListName] = useState(initialNumbers.length ? 'خروجی دفترچه مخاطبان' : 'فهرست جدید')
  const [listId, setListId] = useState('')
  const [testLimit, setTestLimit] = useState('')
  const [delay, setDelay] = useState('2')
  const [preview, setPreview] = useState<any>(null)
  const [job, setJob] = useState<any>(null)
  const [result, setResult] = useState<any>(null)
  const [progress, setProgress] = useState<any>(null)
  const [failures, setFailures] = useState<any[]>([])
  const [confirmed, setConfirmed] = useState(false)
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => { if (event.key === 'Escape' && !busy) close() }
    window.addEventListener('keydown', onKey); return () => window.removeEventListener('keydown', onKey)
  }, [close, busy])

  const waitTask = async (taskId: string, onTick?: () => Promise<void>) => {
    for (let attempt = 0; attempt < 3600; attempt += 1) {
      await new Promise(resolve => window.setTimeout(resolve, 1000))
      const response = await api<{ task: any }>('GET', query('/api/v1/background/status', { task_id: taskId }))
      if (onTick && attempt % 2 === 0) await onTick()
      if (response.task.status === 'failed') {
        const detail = response.task.error?.message || response.task.error?.error_code || response.task.error_type || 'خطای نامشخص'
        throw new Error(`عملیات پس‌زمینه متوقف شد: ${detail}`)
      }
      if (response.task.status === 'completed') return response.task.result
    }
    throw new Error('عملیات طولانی شد؛ وضعیت آن در پایگاه داده حفظ شده است.')
  }

  const chooseMedia = async () => {
    const selected = await window.eitaaDesktop.selectFile({ title: 'انتخاب فایل برای ارسال', filters: [{ name: 'همه فایل‌ها', extensions: ['*'] }] })
    if (selected) { setFilePath(selected); setFileInfo(null); setPreview(null); setConfirmed(false) }
  }
  const choosePhoneFile = async () => {
    const selected = await window.eitaaDesktop.selectFile({ title: 'انتخاب فهرست شماره‌ها', filters: [{ name: 'TXT / CSV', extensions: ['txt', 'csv'] }] })
    if (selected) setSourceFile(selected)
  }

  const messagePayload = () => ({
    kind,
    text: kind === 'text' ? text : '',
    caption: kind === 'text' ? '' : caption,
    file_path: kind === 'text' ? undefined : filePath,
    mime_type: kind === 'text' ? undefined : fileInfo?.mime_type,
    delay_seconds: Number(delay || 0),
    test_limit: testLimit ? Number(testLimit) : undefined,
    max_attempts: 3,
    retry_delay_seconds: 5,
    stop_on_server_error: true,
  })

  const ensurePhoneList = async () => {
    if (listId) return listId
    const imported = await api<{ phone_list: any }>('POST', '/api/v1/phone-lists/import', {
      site_key: siteKey,
      name: listName,
      numbers: sourceFile ? undefined : numbers,
      source_file: sourceFile || undefined,
    })
    const id = imported.phone_list.id as string
    setListId(id)
    const started = await api<{ task: { task_id: string } }>('POST', '/api/v1/phone-lists/resolve', {
      site_key: siteKey, list_id: id, import_if_missing: true, delay_seconds: 1, max_attempts: 2,
    })
    await waitTask(started.task.task_id)
    return id
  }

  const prepare = async () => {
    setBusy('prepare'); setError(''); setPreview(null); setResult(null); setProgress(null); setFailures([]); setConfirmed(false)
    try {
      if (mode !== 'invite') {
        if (kind === 'text' && !text.trim()) throw new Error('متن پیام را وارد کنید.')
        if (kind !== 'text') {
          if (!filePath) throw new Error('ابتدا فایل را انتخاب کنید.')
          const validation = await api<{ file: { name: string; size_bytes: number; mime_type: string; kind: string } }>('POST', '/api/v1/community/bulk/validate', { ...messagePayload(), site_key: siteKey })
          setFileInfo(validation.file)
        }
      }
      if (mode === 'members') {
        if (!dialog || dialog.display_kind === 'personal') throw new Error('برای ارسال به اعضا، یک گروه یا کانال را انتخاب کنید.')
        const started = await api<{ task: { task_id: string } }>('POST', '/api/v1/community/members/sync/start', { site_key: siteKey, peer_file: dialog.peer_file, page_size: 200, max_pages: Math.min(250, Math.max(1, Math.ceil((dialog.participants_count || 50_000) / 200))), expected_total: dialog.participants_count || undefined })
        await waitTask(started.task.task_id)
        const response = await api<{ preview: any }>('POST', '/api/v1/community/bulk/preview', { site_key: siteKey, peer_file: dialog.peer_file, include_bots: false, member_ids: memberIds.length ? memberIds : undefined, test_limit: testLimit ? Number(testLimit) : undefined })
        setPreview(response.preview)
      } else {
        if (!sourceFile && !numbers.trim() && !listId) throw new Error('شماره‌ها را وارد کنید یا فایل TXT/CSV انتخاب کنید.')
        const id = await ensurePhoneList()
        if (mode === 'numbers') {
          const response = await api<{ preview: any }>('POST', '/api/v1/phone-lists/preview', { site_key: siteKey, list_id: id, test_limit: testLimit ? Number(testLimit) : undefined })
          setPreview(response.preview)
        } else {
          if (!dialog || dialog.display_kind === 'personal') throw new Error('برای دعوت، گروه یا کانال مقصد را انتخاب کنید.')
          const response = await api<{ preview: any }>('POST', '/api/v1/membership/preview', { site_key: siteKey, list_id: id, peer_file: dialog.peer_file, test_limit: testLimit ? Number(testLimit) : undefined })
          setPreview(response.preview)
        }
      }
      toast.success('پیش‌نمایش گیرندگان و محتوای عملیات آماده شد.')
    } catch (e) { setError(e instanceof Error ? e.message : 'آماده‌سازی عملیات ناموفق بود.') }
    finally { setBusy('') }
  }

  const loadJobReport = async (jobId: string) => {
    const response = await api<{ report: any }>('POST', '/api/v1/community/bulk/jobs', { site_key: siteKey, job_id: jobId })
    setProgress(response.report)
    return response.report
  }

  const loadFailures = async (jobId: string) => {
    const response = await api<{ recipients: any[] }>('POST', '/api/v1/community/bulk/recipients', { site_key: siteKey, job_id: jobId, status: 'failed', limit: 100 })
    setFailures(response.recipients)
    return response.recipients
  }

  const controlJob = async (action: 'pause' | 'resume' | 'cancel') => {
    const jobId = job?.id || progress?.job?.id
    if (!jobId) return
    setBusy(`job-${action}`); setError('')
    try {
      await api('POST', '/api/v1/community/bulk/action', { site_key: siteKey, job_id: jobId, action })
      if (action === 'resume') {
        const started = await api<{ task: { task_id: string } }>('POST', '/api/v1/community/bulk/run', { site_key: siteKey, job_id: jobId, confirm: true })
        const completed = await waitTask(started.task.task_id, () => loadJobReport(jobId))
        setResult(completed)
      }
      const report = await loadJobReport(jobId)
      if (Number(report?.job?.failed_count || 0)) await loadFailures(jobId)
      toast.info(action === 'pause' ? 'درخواست توقف موقت ثبت شد.' : action === 'cancel' ? 'وظیفه لغو شد.' : 'وظیفه از گیرندگان باقی‌مانده ادامه یافت.')
    } catch (e) { setError(e instanceof Error ? e.message : 'تغییر وضعیت وظیفه ناموفق بود.') }
    finally { setBusy('') }
  }

  const execute = async () => {
    if (!confirmed) { setError('تأیید صریح عملیات الزامی است.'); return }
    setBusy('run'); setError(''); setResult(null); setProgress(null); setFailures([])
    try {
      let created: { job: any }
      if (mode === 'members') {
        if (!dialog) throw new Error('گفتگوی مقصد انتخاب نشده است.')
        created = await api('POST', '/api/v1/community/bulk/create', { site_key: siteKey, peer_file: dialog.peer_file, include_bots: false, member_ids: memberIds.length ? memberIds : undefined, ...messagePayload() })
        setJob(created.job)
        const started = await api<{ task: { task_id: string } }>('POST', '/api/v1/community/bulk/run', { site_key: siteKey, job_id: created.job.id, confirm: true })
        const completed = await waitTask(started.task.task_id, () => loadJobReport(created.job.id))
        const report = completed?.report || await loadJobReport(created.job.id)
        setResult(completed); setProgress(report)
        const failed = Number(report?.job?.failed_count || 0)
        const sent = Number(report?.job?.sent_count || 0)
        if (failed) await loadFailures(created.job.id)
        const status = String(report?.job?.status || '')
        if (status === 'blocked' || status === 'paused' || status === 'cancelled' || status === 'failed') toast.warning(`وظیفه با وضعیت ${status} متوقف شد؛ گزارش و دکمه ادامه را بررسی کنید.`)
        else if (failed && !sent) toast.error('ارسال برای هیچ گیرنده‌ای موفق نشد؛ علت‌ها در گزارش پایین نمایش داده شده است.')
        else if (failed) toast.warning(`ارسال ناقص بود: ${sent} موفق و ${failed} ناموفق.`)
        else toast.success(`${sent} ارسال با موفقیت پایان یافت.`)
      } else if (mode === 'numbers') {
        const id = await ensurePhoneList()
        created = await api('POST', '/api/v1/phone-lists/bulk/create', { site_key: siteKey, list_id: id, ...messagePayload() })
        setJob(created.job)
        const started = await api<{ task: { task_id: string } }>('POST', '/api/v1/community/bulk/run', { site_key: siteKey, job_id: created.job.id, confirm: true })
        const completed = await waitTask(started.task.task_id, () => loadJobReport(created.job.id))
        const report = completed?.report || await loadJobReport(created.job.id)
        setResult(completed); setProgress(report)
        const failed = Number(report?.job?.failed_count || 0)
        const sent = Number(report?.job?.sent_count || 0)
        if (failed) await loadFailures(created.job.id)
        const status = String(report?.job?.status || '')
        if (status === 'blocked' || status === 'paused' || status === 'cancelled' || status === 'failed') toast.warning(`وظیفه با وضعیت ${status} متوقف شد؛ گزارش و دکمه ادامه را بررسی کنید.`)
        else if (failed && !sent) toast.error('ارسال برای هیچ شماره‌ای موفق نشد؛ گزارش خطا را بررسی کنید.')
        else if (failed) toast.warning(`ارسال ناقص بود: ${sent} موفق و ${failed} ناموفق.`)
        else toast.success(`${sent} ارسال با موفقیت پایان یافت.`)
      } else {
        if (!dialog) throw new Error('گفتگوی مقصد انتخاب نشده است.')
        const id = await ensurePhoneList()
        created = await api('POST', '/api/v1/membership/create', { site_key: siteKey, list_id: id, peer_file: dialog.peer_file, delay_seconds: Number(delay || 0), test_limit: testLimit ? Number(testLimit) : undefined })
        setJob(created.job)
        const started = await api<{ task: { task_id: string } }>('POST', '/api/v1/membership/run', { site_key: siteKey, job_id: created.job.id, confirm: true })
        const completed = await waitTask(started.task.task_id)
        setResult(completed)
        toast.success('عملیات دعوت پایان یافت؛ گزارش در هسته ذخیره شد.')
      }
    } catch (e) { setError(e instanceof Error ? e.message : 'اجرای عملیات ناموفق بود.') }
    finally { setBusy('') }
  }

  const selectedCount = preview?.selected_count ?? preview?.eligible_count ?? 0
  return <MaterialLegacyDialog close={close} locked={Boolean(busy)} maxWidth="lg">
    <section className="eb-dialog bulk-dialog card material-dialog-surface" aria-label="عملیات گروهی">
      <div className="section-title"><div><h2>ارسال و دعوت گروهی</h2><small>تمام عملیات با پیش‌نمایش، تأیید و گزارش پایدار هسته انجام می‌شود.</small></div><button className="dialog-close" disabled={Boolean(busy)} onClick={close}><Icon name="close" /></button></div>
      <div className="mode-tabs tabs tabs-box" role="tablist" aria-label="نوع عملیات گروهی">
        <button type="button" role="tab" aria-selected={mode === 'members'} className={`tab ${mode === 'members' ? 'active' : ''}`} onClick={() => { setMode('members'); setPreview(null); setResult(null); setProgress(null); setFailures([]); setConfirmed(false) }}>اعضای گفتگوی فعال</button>
        <button type="button" role="tab" aria-selected={mode === 'numbers'} className={`tab ${mode === 'numbers' ? 'active' : ''}`} onClick={() => { setMode('numbers'); setPreview(null); setResult(null); setProgress(null); setFailures([]); setConfirmed(false) }}>شماره‌های جدید</button>
        <button type="button" role="tab" aria-selected={mode === 'invite'} className={`tab ${mode === 'invite' ? 'active' : ''}`} onClick={() => { setMode('invite'); setPreview(null); setResult(null); setProgress(null); setFailures([]); setConfirmed(false) }}>دعوت شماره‌ها</button>
      </div>
      <div className="bulk-grid">
        <fieldset className={`fieldset rounded-box border p-4 bulk-recipient-fieldset ${mode === 'invite' ? 'bulk-recipient-fieldset--full' : ''}`}>
          <legend className="fieldset-legend">گیرندگان</legend>
          {mode === 'members' ? <div className="notice">مقصد: <b>{titleFor(dialog)}</b><br/>{memberIds.length ? `${memberIds.length.toLocaleString('fa-IR')} عضو انتخاب‌شده از مدیریت اعضا` : 'اعضای قابل ارسال از نمایه محلی پس از همگام‌سازی انتخاب می‌شوند.'}</div> : <>
            {mode === 'invite' && <div className="notice invite-explainer"><b>دعوت مستقیم به {titleFor(dialog)}</b><br/>شماره‌ها ابتدا شناسایی می‌شوند و سپس هسته برای افزودن یا دعوت هر حساب به گفتگوی مقصد درخواست می‌فرستد. موفقیت به دسترسی افزودن عضو، نوع گروه/کانال، حریم خصوصی کاربر و محدودیت‌های سرور ایتا وابسته است؛ این عملیات صرفاً لینک دعوت ارسال نمی‌کند.</div>}
            {mode === 'numbers' && initialNumbers.length > 0 && <div className="notice"><b>{initialNumbers.length.toLocaleString('fa-IR')} گیرنده از سازنده فهرست هدف دفترچه منتقل شد.</b><br/>این انتقال به‌تنهایی هیچ پیامی ارسال نمی‌کند؛ شماره‌ها دوباره در هسته پاک‌سازی و شناسایی می‌شوند و پیش‌نمایش و تأیید صریح لازم است.</div>}
            <label className="label">نام فهرست</label><input className="input w-full" value={listName} onChange={e => setListName(e.target.value)} />
            <label className="label">شماره‌ها، هر شماره در یک خط</label><textarea className="textarea w-full phone-input" dir="ltr" value={numbers} onChange={e => { setNumbers(e.target.value); setListId('') }} placeholder="+98912..." />
            <button className="btn btn-sm btn-outline" onClick={() => void choosePhoneFile()}>انتخاب TXT/CSV</button>
            {sourceFile && <small className="selected-path" dir="ltr">{sourceFile}</small>}
          </>}
          <label className="label">محدودیت آزمایشی</label><input className="input w-full" type="number" min="1" value={testLimit} onChange={e => setTestLimit(e.target.value)} placeholder="خالی = همه" />
          <label className="label">فاصله بین عملیات (ثانیه)</label><input className="input w-full" type="number" min="0" step="0.5" value={delay} onChange={e => setDelay(e.target.value)} />
        </fieldset>
        {mode !== 'invite' && <fieldset className="fieldset rounded-box border p-4 bulk-message-fieldset">
          <legend className="fieldset-legend">پیام</legend>
          <div className="bulk-message-kind-row"><label className="label" htmlFor="bulk-message-kind">نوع پیام</label><select id="bulk-message-kind" className="select bulk-message-kind" value={kind} onChange={e => { setKind(e.target.value as any); setFileInfo(null); setPreview(null); setConfirmed(false) }}><option value="text">متن</option><option value="photo">تصویر</option><option value="file">فایل</option></select></div>
          {kind === 'text' ? <textarea className="textarea w-full message-compose" rows={10} value={text} onChange={e => setText(e.target.value)} placeholder="متن پیام" /> : <div className="bulk-media-compose">
            <button className="btn btn-outline" onClick={() => void chooseMedia()}>انتخاب فایل</button>
            {filePath && <small className="selected-path" dir="ltr">{filePath}</small>}
            {fileInfo && <div className="file-preflight"><b>{fileInfo.name}</b><span>{(fileInfo.size_bytes / 1024 / 1024).toLocaleString('fa-IR', { maximumFractionDigits: 2 })} مگابایت</span><span dir="ltr">{fileInfo.mime_type}</span></div>}
            <textarea className="textarea w-full bulk-caption" rows={5} value={caption} onChange={e => setCaption(e.target.value)} placeholder="کپشن اختیاری" />
          </div>}
        </fieldset>}
      </div>
      <div className="bulk-summary card">
        {!preview ? <span>ابتدا «آماده‌سازی و پیش‌نمایش» را اجرا کنید.</span> : <><b>{selectedCount.toLocaleString('fa-IR')} گیرنده انتخاب شده</b><span>واجد شرایط: {(preview.eligible_count ?? selectedCount).toLocaleString('fa-IR')} — حذف‌شده/نامعتبر: {(preview.skipped_unsendable ?? preview.unresolved_count ?? 0).toLocaleString('fa-IR')}</span></>}
      </div>
      {progress?.job && <div className="operation-progress card" data-status={progress.job.status}>
        <div><b>وضعیت وظیفه: {progress.job.status}</b><span dir="ltr">{progress.job.id}</span></div>
        <div className="operation-progress-counts"><span>موفق: {Number(progress.job.sent_count || 0).toLocaleString('fa-IR')}</span><span>ناموفق: {Number(progress.job.failed_count || 0).toLocaleString('fa-IR')}</span><span>ردشده: {Number(progress.job.skipped_count || 0).toLocaleString('fa-IR')}</span><span>در انتظار: {Number(progress.pending || 0).toLocaleString('fa-IR')}</span></div>
        {progress.job.stop_reason && <small className="operation-stop-reason">علت توقف: <span dir="ltr">{progress.job.stop_reason}</span></small>}
        <div className="operation-job-actions">
          {['running', 'queued'].includes(progress.job.status) && <button type="button" className="btn btn-xs btn-outline" disabled={Boolean(busy)} onClick={() => void controlJob('pause')}>توقف موقت</button>}
          {['paused', 'blocked', 'failed'].includes(progress.job.status) && <button type="button" className="btn btn-xs btn-secondary" disabled={Boolean(busy)} onClick={() => void controlJob('resume')}>ادامه گیرندگان باقی‌مانده</button>}
          {!['completed', 'cancelled'].includes(progress.job.status) && <button type="button" className="btn btn-xs btn-ghost danger" disabled={Boolean(busy)} onClick={() => void controlJob('cancel')}>لغو وظیفه</button>}
        </div>
      </div>}
      {preview && <label className="publish-confirm"><input className="checkbox checkbox-neutral" type="checkbox" checked={confirmed} onChange={e => setConfirmed(e.target.checked)} /> گیرندگان، متن/فایل و محدودیت آزمایشی را بررسی کردم و اجرای عملیات را تأیید می‌کنم.</label>}
      {error && <div className="error-box alert alert-error">{error}</div>}
      {failures.length > 0 && <div className="recipient-failures alert alert-error"><b>{failures.length.toLocaleString('fa-IR')} خطای گیرنده ثبت شده است</b><div>{failures.slice(0, 12).map((item, index) => <span key={`${item.user?.peer?.id || index}:${item.error_code || item.error_type || index}`}><b>{item.user?.display_name || item.user?.first_name || `کاربر ${item.user?.peer?.id || '—'}`}</b><code dir="ltr">{item.error_code || item.error_type || 'UNKNOWN_ERROR'}</code></span>)}</div>{failures.length > 12 && <small>فقط ۱۲ مورد نخست نمایش داده شده؛ گزارش کامل در هسته SQLite باقی مانده است.</small>}</div>}
      {result && !failures.length && <div className="success-box alert alert-success"><b>عملیات ثبت و پایان یافت</b><span>وظیفه ID: {job?.id || result?.job_id || '—'}</span><span>گزارش کامل در هسته SQLite باقی می‌ماند و قابل Resume/بررسی است.</span></div>}
      <div className="modal-actions"><button className="btn btn-ghost" disabled={Boolean(busy)} onClick={close}>بستن</button><button className="btn btn-secondary" disabled={Boolean(busy)} onClick={() => void prepare()}>{busy === 'prepare' ? <span className="loading loading-dots loading-sm" /> : 'آماده‌سازی و پیش‌نمایش'}</button><button className="btn btn-neutral" disabled={Boolean(busy) || !preview || !confirmed || (mode !== 'invite' && kind === 'text' && !text.trim()) || (mode !== 'invite' && kind !== 'text' && !filePath)} onClick={() => void execute()}>{busy === 'run' ? <><span className="loading loading-dots loading-sm" /> در حال اجرا</> : mode === 'invite' ? 'شروع دعوت' : 'شروع ارسال'}</button></div>
    </section>
  </MaterialLegacyDialog>
}

function SettingsModal({ sites, close, onChanged }: { sites: Site[]; close: () => void; onChanged: () => Promise<void> | void }) {
  const emptySite = { site_key: '', base_url: 'http://localhost', default_status: 'draft', default_category_id: '', timeout_seconds: 30, verify_tls: false, retry_attempts: 2, allow_insecure_http: true, username: '', application_password: '', is_default: false }
  const [items, setItems] = useState<Site[]>(sites)
  const [form, setForm] = useState<any>(emptySite)
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const load = useCallback(async () => {
    const response = await api<{ sites: Site[] }>('GET', '/api/v1/settings/sites')
    setItems(response.sites)
  }, [])
  useEffect(() => { void load() }, [load])
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => { if (event.key === 'Escape' && !busy) close() }
    window.addEventListener('keydown', onKey); return () => window.removeEventListener('keydown', onKey)
  }, [close, busy])
  const edit = (site: Site) => setForm({ ...site, default_category_id: site.default_category_id ?? '', username: '', application_password: '' })
  const sitePayload = () => {
    const payload: any = { ...form, default_category_id: form.default_category_id === '' ? null : Number(form.default_category_id), timeout_seconds: Number(form.timeout_seconds), retry_attempts: Number(form.retry_attempts) }
    if (!form.username) delete payload.username
    if (!form.application_password) delete payload.application_password
    return payload
  }
  const persistForm = async (announce = true) => {
    const response = await api<{ sites: Site[] }>('POST', '/api/v1/settings/sites/upsert', sitePayload())
    setItems(response.sites)
    const saved = response.sites.find(item => item.site_key === form.site_key)
    if (saved) edit(saved)
    await onChanged()
    if (announce) setMessage('تنظیمات سایت ذخیره شد. پیش از هر تغییر نسخه پشتیبان ساخته شد.')
    return saved
  }
  const save = async () => {
    setBusy('save'); setError(''); setMessage('')
    try { await persistForm(true) }
    catch (e) { setError(e instanceof Error ? e.message : 'ذخیره تنظیمات ناموفق بود.') }
    finally { setBusy('') }
  }
  const test = async () => {
    setBusy('test'); setError(''); setMessage('')
    try {
      await persistForm(false)
      await api('POST', '/api/v1/settings/sites/test', { site_key: form.site_key })
      setMessage('تنظیمات ذخیره شد و اتصال و احراز هویت وردپرس با موفقیت تأیید شد.')
    }
    catch (e) { setError(e instanceof Error ? e.message : 'ذخیره یا آزمون اتصال ناموفق بود.') }
    finally { setBusy('') }
  }
  const makeDefault = async (site: Site) => {
    setBusy(`default-${site.site_key}`); setError('')
    try { const response = await api<{ sites: Site[] }>('POST', '/api/v1/settings/sites/default', { site_key: site.site_key }); setItems(response.sites); await onChanged() }
    catch (e) { setError(e instanceof Error ? e.message : 'تغییر سایت پیش‌فرض ناموفق بود.') }
    finally { setBusy('') }
  }
  const remove = async (site: Site) => {
    if (!confirm(`سایت «${site.site_key}» حذف شود؟ نسخه پشتیبان تنظیمات باقی می‌ماند.`)) return
    setBusy(`delete-${site.site_key}`); setError('')
    try { const response = await api<{ sites: Site[] }>('POST', '/api/v1/settings/sites/delete', { site_key: site.site_key, confirm: true }); setItems(response.sites); setForm(emptySite); await onChanged() }
    catch (e) { setError(e instanceof Error ? e.message : 'حذف سایت ناموفق بود.') }
    finally { setBusy('') }
  }
  return <MaterialLegacyDialog close={close} locked={Boolean(busy)} maxWidth="lg">
    <section className="eb-dialog settings-dialog settings-editor card material-dialog-surface" aria-label="سایت‌ها و تنظیمات">
      <div className="section-title"><div><h2>تنظیمات برنامه و سایت‌ها</h2><small>ظاهر صفحه ورود و اتصال‌های وردپرس از همین پنجره مدیریت می‌شوند.</small></div><button className="dialog-close" disabled={Boolean(busy)} onClick={close}><Icon name="close" /></button></div>
      <Paper variant="outlined" className="settings-login-appearance">
        <Box sx={{ mb: 2 }}>
          <Typography variant="h6">ظاهر صفحه ورود</Typography>
          <Typography variant="body2" color="text.secondary">تصویر انتخاب‌شده فقط در Runtime محلی برنامه نگهداری می‌شود.</Typography>
        </Box>
        <LoginAppearanceSettingsPanel />
      </Paper>
      <div className="settings-subheading"><h3>سایت‌ها و دسترسی وردپرس</h3><small>رمز برنامه در فایل محلی .env ذخیره می‌شود و هرگز در UI بازخوانی نمی‌شود.</small></div>
      <div className="settings-layout">
        <div className="settings-site-list">
          <button className="btn btn-sm btn-outline" onClick={() => setForm(emptySite)}>+ سایت جدید</button>
          {items.map(site => <div className={`site-card card ${form.site_key === site.site_key ? 'selected' : ''}`} key={site.site_key} onClick={() => edit(site)}><div className="site-status-dot" data-ready={site.credentials_configured} /><div><b>{site.site_key}{site.is_default ? ' — پیش‌فرض' : ''}</b><span>{site.base_url}</span><small>{site.credentials_configured ? 'دسترسی آماده' : 'نام کاربری یا رمز برنامه ناقص'}</small></div><div className="site-actions"><button disabled={site.is_default || Boolean(busy)} onClick={e => { e.stopPropagation(); void makeDefault(site) }}>پیش‌فرض</button><button className="danger" disabled={Boolean(busy)} onClick={e => { e.stopPropagation(); void remove(site) }}>حذف</button></div></div>)}
        </div>
        <fieldset className="fieldset settings-form rounded-box border p-4">
          <legend className="fieldset-legend">{form.site_key ? 'ویرایش اتصال' : 'اتصال جدید'}</legend>
          <label className="label">کلید سایت</label><input className="input w-full" dir="ltr" value={form.site_key} onChange={e => setForm({ ...form, site_key: e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, '-') })} placeholder="medical-site" />
          <label className="label">نشانی سایت</label><input className="input w-full" dir="ltr" value={form.base_url} onChange={e => { const base_url = e.target.value; const localHttp = /^http:\/\//i.test(base_url); const https = /^https:\/\//i.test(base_url); setForm({ ...form, base_url, allow_insecure_http: localHttp ? true : form.allow_insecure_http, verify_tls: localHttp ? false : https ? true : form.verify_tls }) }} placeholder="http://localhost یا https://example.com" />
          <small className="settings-help">برای Laragon روی همین رایانه از <b>http://localhost</b> و برای سیستم اداره از IP خصوصی مانند <b>http://192.168.1.2</b> استفاده کنید.</small>
          <div className="settings-form-row"><label><span>وضعیت پیش‌فرض</span><select className="select w-full" value={form.default_status} onChange={e => setForm({ ...form, default_status: e.target.value })}><option value="draft">پیش‌نویس</option><option value="pending">در انتظار بررسی</option><option value="private">خصوصی</option><option value="publish">انتشار</option></select></label><label><span>شناسه دسته پیش‌فرض</span><input className="input w-full" type="number" min="1" value={form.default_category_id} onChange={e => setForm({ ...form, default_category_id: e.target.value })} /></label></div>
          <label className="label">نام کاربری ورود به وردپرس</label><input className="input w-full" dir="ltr" autoComplete="username" value={form.username} onChange={e => setForm({ ...form, username: e.target.value })} placeholder={form.username_configured ? 'ذخیره شده؛ برای تغییر مقدار جدید وارد کنید' : 'eitaa-user'} />
          <small className="settings-help warning-help">این مقدار باید همان نام کاربری ورود به وردپرس باشد؛ نامی که هنگام ساخت رمز برنامه انتخاب می‌کنید، نام کاربری نیست.</small>
          <label className="label">رمز برنامه</label><input className="input w-full" dir="ltr" type="password" autoComplete="new-password" value={form.application_password} onChange={e => setForm({ ...form, application_password: e.target.value })} placeholder={form.application_password_configured ? 'ذخیره شده؛ برای تغییر مقدار جدید وارد کنید' : 'xxxx xxxx xxxx xxxx'} />
          <div className="settings-form-row"><label><span>زمان انتظار</span><input className="input w-full" type="number" min="1" value={form.timeout_seconds} onChange={e => setForm({ ...form, timeout_seconds: e.target.value })} /></label><label><span>تلاش مجدد</span><input className="input w-full" type="number" min="0" max="5" value={form.retry_attempts} onChange={e => setForm({ ...form, retry_attempts: e.target.value })} /></label></div>
          <label className="inline-check local-http-check"><input className="checkbox checkbox-neutral" type="checkbox" checked={Boolean(form.allow_insecure_http)} onChange={e => setForm({ ...form, allow_insecure_http: e.target.checked })} /> اجازه HTTP فقط برای localhost، دامنه‌های توسعه محلی و IP خصوصی شبکه</label>
          <label className="inline-check"><input className="checkbox checkbox-neutral" type="checkbox" disabled={/^http:\/\//i.test(form.base_url)} checked={Boolean(form.verify_tls)} onChange={e => setForm({ ...form, verify_tls: e.target.checked })} /> بررسی گواهی TLS در اتصال HTTPS</label>
          <label className="inline-check"><input className="checkbox checkbox-neutral" type="checkbox" checked={Boolean(form.is_default)} onChange={e => setForm({ ...form, is_default: e.target.checked })} /> انتخاب به‌عنوان سایت پیش‌فرض</label>
          <div className="settings-buttons"><button className="btn btn-outline" disabled={Boolean(busy) || !form.site_key} onClick={() => void test()}>{busy === 'test' ? <span className="loading loading-dots loading-sm" /> : 'ذخیره و آزمون اتصال'}</button><button className="btn btn-neutral" disabled={Boolean(busy) || !form.site_key || !form.base_url} onClick={() => void save()}>{busy === 'save' ? <span className="loading loading-dots loading-sm" /> : 'ذخیره تنظیمات'}</button></div>
        </fieldset>
      </div>
      {error && <div className="error-box alert alert-error">{error}</div>}{message && <div className="success-box alert alert-success">{message}</div>}
      <div className="modal-actions"><button className="btn btn-ghost" onClick={() => void window.eitaaDesktop.openLogs()}>بازکردن گزارش‌ها</button><button className="btn btn-primary" disabled={Boolean(busy)} onClick={close}>بستن</button></div>
    </section>
  </MaterialLegacyDialog>
}
