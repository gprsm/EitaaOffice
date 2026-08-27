import { FormEvent, lazy, ReactNode, Suspense, useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { useVirtualizer } from '@tanstack/react-virtual'
import { TEMPORAL_YEAR_OFFSET, TEMPORAL_MONTH_OFFSET, PERSIAN_MONTHS, LOCALIZED_LOGIN_CODE_DIGITS, normalizeLoginCodeInput, messageKey, titleFor, displayKindLabel, CategoryTreeRow, categoryTree, STORAGE, readStored, writeStored, REMOTE_MESSAGE_TTL_MS, AUTO_NEWER_TTL_MS, TERM_CACHE_TTL_MS, mediaUrl, JALALI_DAY_LABEL_FORMATTER, JALALI_DAY_KEY_FORMATTER, parseSourceKey, jalaliDayLabel, jalaliDayKey, temporalIndexPredictions, div, mod, jalCal, g2d, d2g, j2d, jalaliToGregorian, parseJalaliDate, jalaliParts, jalaliYmd, jalaliMonthLength, jalaliMonths, jalaliWeekdays, JalaliDatePicker } from './utils/helpers'
import { toast } from './MaterialToast'
import { Alert, Avatar, Box, Button, ButtonBase, Checkbox, Chip, CircularProgress, Dialog, DialogContent, FormControl, FormControlLabel, IconButton, InputLabel, LinearProgress, MenuItem, Paper, Popover, Radio, RadioGroup, Select, Skeleton, Stack, TextField, ToggleButton, ToggleButtonGroup, Tooltip, Typography, useMediaQuery, useTheme } from '@mui/material'
import CalendarMonthRounded from '@mui/icons-material/CalendarMonthRounded'
import ChevronLeftRounded from '@mui/icons-material/ChevronLeftRounded'
import ChevronRightRounded from '@mui/icons-material/ChevronRightRounded'
import CloseRounded from '@mui/icons-material/CloseRounded'
import { api, ApiError, AUTH_SESSION_INVALID_EVENT, query, scopedStorageKey } from './lib/api'
import { buildMessageGroupLookup, messageGroupText } from './lib/groupedMedia'
import type { MessageGroup } from './lib/groupedMedia'
import { anchorScrollTop, appendedMessagesAfterTail, estimateMessageRowSize, isNearBottom, mergeMessagesById, shouldAutoFollow, stableMessageKey, updateTopPaginationGate } from './lib/scrollMath'
import type { MessageScrollMemory, ScrollAnchor, TopPaginationGate } from './lib/scrollMath'
import type { CompositionRecord, ContentIndexJob, ContentIndexResult, DialogItem, DisplayKind, IndexPrediction, MessageItem, MessageUsage, PeerType, SenderFilterOption, Site, Term } from './lib/types'
import { QuickSendBar } from './QuickSendBar'
import { loadDialogAvatar, peekDialogAvatar } from './lib/avatarLoader'
import { waitForAdaptivePoll } from './lib/polling.mjs'
import { LoginAppearanceProvider, LoginSurface } from './LoginExperience'
import { AppUserGate, AppUserLogoutButton, useAppUser } from './AppUserGate'
import { WorkspaceNavigation } from './WorkspaceNavigation'
import { UsageInfoDialog } from './UsageInfoDialog'
import { ConversationListPage } from './ConversationListPage'
import { ChatHeader } from './ChatHeader'
import { AuthBrandMark, AuthBrandPill } from './AuthBrand'
import { MessageContentCard } from './MessageContentCard'

const ContactDirectoryModal = lazy(() => import('./ContactDirectoryModal').then(module => ({ default: module.ContactDirectoryModal })))
const SettingsPage = lazy(() => import('./SettingsPage').then(module => ({ default: module.SettingsPage })))
const MessageFilterDialog = lazy(() => import('./MessageFilterDialog').then(module => ({ default: module.MessageFilterDialog })))
const ContentIndexDialog = lazy(() => import('./ContentIndexDialog').then(module => ({ default: module.ContentIndexDialog })))
const MessageIndexEditor = lazy(() => import('./MessageIndexEditor').then(module => ({ default: module.MessageIndexEditor })))
import {
  MessengerAccountGate,
  MessengerAccountMenuControl,
  useMessengerAccounts,
} from './MessengerAccountGate'

type AuthChallengeSummary = { challenge_id?: string; stage?: 'code' | 'password'; delivery_type?: string }
type AuthStatus = { authenticated: boolean; session_present: boolean; password_pending: boolean; session_error?: boolean; session_invalid?: boolean; session_error_code?: string; session_error_type?: string; fresh_login_available?: boolean; remote_warning?: boolean; remote_error_type?: string; remote_error_code?: number | string; challenge?: AuthChallengeSummary }
type Tab = 'all' | 'channel' | 'group' | 'personal' | 'favorite'
type BulkMode = 'members' | 'numbers' | 'invite'
type MemberScope = 'all_snapshot' | 'selected'
type ComposerResult = Record<string, any>
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
  return <Avatar ref={ref} sx={{ width: small ? 34 : 46, height: small ? 34 : 46, flex: '0 0 auto', bgcolor: 'primary.main', color: 'primary.contrastText', fontWeight: 800 }}>
    {src === undefined
      ? <Skeleton variant="circular" animation="wave" width="100%" height="100%" />
      : src
        ? <Box component="img" src={src} alt={titleFor(dialog)} loading="lazy" decoding="async" onError={() => setSrc(null)} sx={{ width: '100%', height: '100%', objectFit: 'cover' }} />
        : initials(titleFor(dialog))}
  </Avatar>
}

function makeCompositionKey() {
  const stamp = new Date().toISOString().replace(/[-:TZ.]/g, '').slice(0, 14)
  return `ui-${stamp}-${Math.random().toString(36).slice(2, 8)}`
}

function MaterialLegacyDialog({ children, close, locked = false, maxWidth = 'md' }: { children: ReactNode; close: () => void; locked?: boolean; maxWidth?: 'sm' | 'md' | 'lg' | 'xl' }) {
  const theme = useTheme()
  const fullScreen = useMediaQuery(theme.breakpoints.down('sm'))
  return <Dialog open fullScreen={fullScreen} fullWidth maxWidth={maxWidth} onClose={locked ? undefined : close}>
    <DialogContent sx={{ p: { xs: 1, sm: 1.5 }, bgcolor: 'background.default' }}>
      {children}
    </DialogContent>
  </Dialog>
}

export default function App() {
  const mobileShell = useMediaQuery(
    '(max-width:599px), (max-width:899px) and (orientation:landscape) and (max-height:599px)',
    { noSsr: true },
  )
  const content = <AppUserGate><MessengerAccountGate><EitaaApp /></MessengerAccountGate></AppUserGate>
  return <LoginAppearanceProvider>
    {mobileShell ? <MobileShell>{content}</MobileShell> : <DesktopShell>{content}</DesktopShell>}
  </LoginAppearanceProvider>
}

function MobileShell({ children }: { children: ReactNode }) {
  return <Box data-presentation-shell="mobile" sx={{ width: '100%', height: '100dvh', minWidth: 0, minHeight: '100svh', overflow: 'hidden', bgcolor: 'background.default' }}>{children}</Box>
}

function DesktopShell({ children }: { children: ReactNode }) {
  return <Box data-presentation-shell="desktop" sx={{ width: '100%', height: '100dvh', minWidth: 0, minHeight: '100svh', overflow: 'hidden', bgcolor: 'background.default' }}>{children}</Box>
}

function EitaaApp() {
  const [status, setStatus] = useState<AuthStatus | null>(null)
  const [fatal, setFatal] = useState('')
  const [forceFreshLogin, setForceFreshLogin] = useState(false)
  const [freshChallenge, setFreshChallenge] = useState<AuthChallengeSummary | undefined>()
  const [loginEpoch, setLoginEpoch] = useState(0)
  const refreshStatus = useCallback(async () => {
    setFatal('')
    try {
      const next = await api<AuthStatus & { ok: true }>('GET', '/api/v1/auth/status')
      setStatus(next)
      if (next.authenticated) setForceFreshLogin(false)
    } catch (error) { setFatal(error instanceof Error ? error.message : 'سرویس محلی در دسترس نیست.') }
  }, [])
  const beginFreshLogin = useCallback((challenge?: AuthChallengeSummary) => {
    setFatal(''); setForceFreshLogin(true); setLoginEpoch(value => value + 1)
    setFreshChallenge(challenge)
    setStatus({ authenticated: false, session_present: false, password_pending: false, fresh_login_available: true })
  }, [])
  const handleAuthenticated = useCallback(async () => { setForceFreshLogin(false); setFreshChallenge(undefined); await refreshStatus() }, [refreshStatus])
  useEffect(() => { void refreshStatus() }, [refreshStatus])
  useEffect(() => {
    const recoverInvalidSession = () => { void refreshStatus() }
    window.addEventListener(AUTH_SESSION_INVALID_EVENT, recoverInvalidSession)
    return () => window.removeEventListener(AUTH_SESSION_INVALID_EVENT, recoverInvalidSession)
  }, [refreshStatus])
  let content: ReactNode
  if (fatal) content = <StartupError message={fatal} retry={refreshStatus} />
  else if (!status) content = <Splash />
  else if (forceFreshLogin) content = <LoginGate key={`fresh-login-${loginEpoch}`} initialChallenge={freshChallenge} onAuthenticated={handleAuthenticated} />
  else if (!status.authenticated && status.session_present && status.session_error) content = <SessionRecovery status={status} onFreshLogin={beginFreshLogin} />
  else if (!status.authenticated) content = <LoginGate key={`login-${loginEpoch}`} initialChallenge={status.challenge} onAuthenticated={handleAuthenticated} />
  else {
    const sessionWarning = status.remote_warning
      ? `نشست محلی باز شد، اما بررسی ارتباط با ایتا موفق نبود${status.remote_error_type ? ` (${status.remote_error_type})` : ''}. همگام‌سازی را دوباره امتحان کنید.`
      : undefined
    content = <Workspace onLogout={refreshStatus} sessionWarning={sessionWarning} />
  }
  return <>{content}</>
}

function Splash() {
  return <LoginSurface><Box sx={{ display: 'grid', placeItems: 'center', minHeight: 260 }}>
    <Stack alignItems="center" spacing={2}>
      <AuthBrandMark />
      <Typography variant="h5">Eitaa Bridge</Typography>
      <CircularProgress size={32} aria-label="در حال آماده‌سازی" />
    </Stack>
  </Box></LoginSurface>
}
function StartupError({ message, retry }: { message: string; retry: () => void }) {
  return <LoginSurface><Stack spacing={2} alignItems="stretch">
    <Avatar sx={{ alignSelf: 'center', bgcolor: 'error.main', color: 'error.contrastText', fontWeight: 900 }}>!</Avatar>
    <Typography variant="h5" textAlign="center">راه‌اندازی انجام نشد</Typography>
    <Alert severity="error">{message}</Alert>
    <Button variant="contained" onClick={retry}>تلاش دوباره</Button>
  </Stack></LoginSurface>
}

function SessionRecovery({ status, onFreshLogin }: { status: AuthStatus; onFreshLogin: (challenge?: AuthChallengeSummary) => void }) {
  const started = useRef(false)
  const [failed, setFailed] = useState(false)
  const recover = useCallback(async () => {
    if (started.current) return
    started.current = true
    setFailed(false)
    const invalidSession = status.session_invalid || status.session_error_code === 'auth_session_invalid'
    try {
      await api<{ login_ready?: boolean }>(
        'POST',
        '/api/v1/auth/reset-local-session',
        invalidSession ? { automatic_recovery: true } : { confirm: true },
      )
      try {
        const result = await api<{ challenge?: AuthChallengeSummary }>('POST', '/api/v1/auth/request-code', {})
        onFreshLogin(result.challenge)
      } catch {
        onFreshLogin()
      }
    } catch {
      started.current = false
      setFailed(true)
    }
  }, [onFreshLogin, status.session_error_code, status.session_invalid])
  useEffect(() => { void recover() }, [recover])
  return <LoginSurface><Stack spacing={2.25} alignItems="center" textAlign="center">
    <AuthBrandMark />
    <Typography variant="h5">در حال آماده‌سازی ورود</Typography>
    <Typography variant="body2" color="text.secondary">لطفاً چند لحظه صبر کنید.</Typography>
    {!failed && <CircularProgress size={30} aria-label="در حال آماده‌سازی ورود" />}
    {failed && <Button variant="contained" onClick={() => void recover()}>تلاش دوباره</Button>}
    <AppUserLogoutButton disabled={!failed} />
  </Stack></LoginSurface>
}

function LoginGate({ onAuthenticated, initialChallenge }: { onAuthenticated: () => Promise<void> | void; initialChallenge?: AuthChallengeSummary }) {
  const [step, setStep] = useState<'phone' | 'code' | 'password'>(() => initialChallenge?.stage === 'password' ? 'password' : initialChallenge?.challenge_id ? 'code' : 'phone')
  const [challengeId, setChallengeId] = useState(() => String(initialChallenge?.challenge_id || '').trim())
  const [phone, setPhone] = useState('+98')
  const phoneInputRef = useRef<HTMLInputElement | null>(null)
  const [code, setCode] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [hint, setHint] = useState(() => initialChallenge?.challenge_id
    ? `کد ورود از طریق ${initialChallenge.delivery_type || 'ایتا'} ارسال شد.`
    : '')
  const [identityRecoveryRequired, setIdentityRecoveryRequired] = useState(false)
  useEffect(() => {
    if (step === 'phone') window.setTimeout(() => phoneInputRef.current?.focus(), 0)
  }, [step])
  const applyCodeChallenge = (result: any) => {
    const issuedChallengeId = String(result.challenge?.challenge_id || '').trim()
    if (!issuedChallengeId) throw new Error('شناسهٔ امن چالش ورود از سرویس دریافت نشد. صفحه را تازه‌سازی و دوباره تلاش کنید.')
    setChallengeId(issuedChallengeId)
    setIdentityRecoveryRequired(false)
    setHint(`کد از طریق ${result.challenge?.delivery_type || 'ایتا'} ارسال شد.`)
    setStep('code')
  }
  const requestFreshCode = async () => {
    setBusy(true); setError('')
    try {
      const result = await api<any>('POST', '/api/v1/auth/request-code', {})
      applyCodeChallenge(result)
      setCode('')
      setHint('کد تازه ارسال شد؛ فقط آخرین کد دریافتی را وارد کنید.')
    } catch (e) {
      setError(e instanceof Error ? e.message : 'دریافت کد تازه ناموفق بود.')
    } finally {
      setBusy(false)
    }
  }
  const submit = async (event: FormEvent) => {
    event.preventDefault(); setBusy(true); setError('')
    try {
      if (step === 'phone') {
        const result = await api<any>('POST', '/api/v1/auth/request-code', { phone })
        applyCodeChallenge(result)
      } else if (step === 'code') {
        if (!challengeId) throw new Error('شناسهٔ چالش ورود در دسترس نیست. صفحه را تازه‌سازی کنید تا چالش فعال بازیابی شود.')
        const result = await api<any>('POST', '/api/v1/auth/submit-code', { challenge_id: challengeId, code: normalizeLoginCodeInput(code) })
        if (result.step === 'password') {
          setChallengeId(String(result.challenge?.challenge_id || challengeId).trim())
          setCode('')
          setHint('رمز دوم حساب را وارد کنید.'); setStep('password')
        }
        else await onAuthenticated()
      } else {
        if (!challengeId) throw new Error('شناسهٔ چالش ورود در دسترس نیست. صفحه را تازه‌سازی کنید تا چالش فعال بازیابی شود.')
        await api('POST', '/api/v1/auth/submit-password', { challenge_id: challengeId, password })
        await onAuthenticated()
      }
    } catch (e) {
      if (e instanceof ApiError && e.code === 'api_auth_session_reset_required') {
        try {
          await api<{ login_ready?: boolean }>('POST', '/api/v1/auth/reset-local-session', { confirm: true })
          const result = await api<any>('POST', '/api/v1/auth/request-code', { phone })
          applyCodeChallenge(result)
        } catch (recoveryError) {
          setError(recoveryError instanceof Error ? recoveryError.message : 'آماده‌سازی ورود ناموفق بود. دوباره تلاش کنید.')
        }
      } else if (e instanceof ApiError && e.code === 'phone_unprotection_failed') {
        setIdentityRecoveryRequired(true)
        setError('کلید محافظت محلیِ مهاجرت قبلی در این اجرای ویندوز قابل بازکردن نیست. می‌توانید شمارهٔ همین حساب را با یک کلید پایدار تازه بازیابی کنید.')
      } else if (e instanceof ApiError && e.code === 'auth_provider_code_expired') {
        try {
          const result = await api<any>('POST', '/api/v1/auth/request-code', {})
          applyCodeChallenge(result)
          setCode('')
          setHint('کد قبلی منقضی شده بود؛ کد تازه ارسال شد.')
        } catch (refreshError) {
          setError(refreshError instanceof Error ? refreshError.message : 'دریافت کد تازه ناموفق بود.')
        }
      } else {
        setError(e instanceof Error ? e.message : 'ورود ناموفق بود.')
      }
    }
    finally { setBusy(false) }
  }
  const recoverPhoneIdentity = async () => {
    if (!confirm('محافظت محلی شمارهٔ همین حساب بازسازی شود؟ کلید و پایگاه دادهٔ قبلی پیش از تغییر پشتیبان‌گیری می‌شوند و هنوز هیچ کد ورودی از ایتا درخواست نخواهد شد.')) return
    setBusy(true); setError('')
    try {
      await api<{ recovered?: boolean; login_ready?: boolean }>('POST', '/api/v1/auth/recover-phone-identity', { phone, confirm: true })
      setIdentityRecoveryRequired(false)
      setHint('محافظت شماره با موفقیت بازیابی شد؛ اکنون دوباره دریافت کد ورود را انتخاب کنید.')
      window.setTimeout(() => phoneInputRef.current?.focus(), 0)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'بازیابی محافظت شماره ناموفق بود.')
    } finally {
      setBusy(false)
    }
  }
  return <LoginSurface><Box component="form" onSubmit={submit} noValidate>
    <Stack spacing={2.25}>
      <AppUserLogoutButton disabled={busy} />
      <AuthBrandPill label="حساب ایتا" />
      <Box>
        <Typography variant="h5" component="h2" textAlign="center">ورود به ایتا</Typography>
      </Box>
      <Stack direction="row" spacing={0.75} aria-label="مراحل ورود">
        {(['phone', 'code', 'password'] as const).map((item, index) => {
          const active = step === item
          const done = (['phone', 'code', 'password'] as const).indexOf(step) > index
          return <Stack key={item} direction="row" alignItems="center" justifyContent="center" spacing={0.5} sx={{ flex: 1, minWidth: 0, p: 0.75, color: active || done ? 'primary.main' : 'text.secondary', bgcolor: active ? 'action.selected' : 'action.hover', border: 1, borderColor: active || done ? 'primary.main' : 'divider', borderRadius: 1.5 }}>
            <Avatar sx={{ width: 22, height: 22, fontSize: '0.7rem', bgcolor: active || done ? 'primary.main' : 'action.disabledBackground', color: active || done ? 'primary.contrastText' : 'text.secondary' }}>{(index + 1).toLocaleString('fa-IR')}</Avatar>
            <Typography variant="caption" fontWeight={700} noWrap>{item === 'phone' ? 'شماره' : item === 'code' ? 'کد' : 'رمز دوم'}</Typography>
          </Stack>
        })}
      </Stack>
      {step === 'phone' && <TextField inputRef={phoneInputRef} label="شماره تلفن ایتا" type="tel" name="phone" dir="ltr" autoComplete="tel" value={phone} onChange={e => setPhone(e.target.value)} placeholder="+98912…" slotProps={{ htmlInput: { inputMode: 'tel', spellCheck: false, dir: 'ltr' } }} helperText="شماره را با کد کشور وارد کنید؛ نمونه: ‎+98912…" />}
      {step === 'code' && <TextField label="کد یک‌بارمصرف" dir="ltr" autoFocus value={code} onChange={e => setCode(normalizeLoginCodeInput(e.target.value))} autoComplete="one-time-code" slotProps={{ htmlInput: { dir: 'ltr', inputMode: 'numeric' } }} />}
      {step === 'password' && <TextField label="رمز دوم حساب" type="password" autoFocus value={password} onChange={e => setPassword(e.target.value)} autoComplete="current-password" />}
      <Box aria-live="polite">{hint && <Alert severity="info">{hint}</Alert>}{error && <Alert severity="error">{error}</Alert>}</Box>
      <Button type="submit" size="large" variant="contained" disabled={busy} startIcon={busy ? <CircularProgress size={18} color="inherit" /> : undefined}>
        {busy ? 'در حال بررسی…' : step === 'phone' ? 'دریافت کد ورود' : 'ادامه ورود'}
      </Button>
      {step === 'code' && <Button type="button" variant="outlined" disabled={busy} onClick={() => void requestFreshCode()}>دریافت کد تازه</Button>}
      {identityRecoveryRequired && <Button type="button" variant="outlined" color="warning" disabled={busy} onClick={() => void recoverPhoneIdentity()}>
        بازیابی امن محافظت شماره
      </Button>}
      {step !== 'phone' && <Button type="button" variant="text" onClick={() => { setStep('phone'); setChallengeId(''); setCode(''); setPassword(''); setHint('') }}>ورود با شماره‌ای دیگر</Button>}
    </Stack>
  </Box></LoginSurface>
}

function Workspace({ onLogout, sessionWarning }: { onLogout: () => void; sessionWarning?: string }) {
  const appUser = useAppUser()
  const messengerAccounts = useMessengerAccounts()
  const dialogsSupported = !messengerAccounts.featureEnabled || messengerAccounts.hasCapability('dialogs.read')
  const historySupported = !messengerAccounts.featureEnabled || messengerAccounts.hasCapability('history.read')
  const mediaReadSupported = !messengerAccounts.featureEnabled || messengerAccounts.hasCapability('media.read')
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
  const [liveMessageState, setLiveMessageState] = useState<'idle' | 'connecting' | 'live' | 'retrying'>('idle')
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
  const [chatsOpen, setChatsOpen] = useState(() => window.matchMedia('(max-width: 899px)').matches)
  const [communityOpen, setCommunityOpen] = useState(false)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [bulkOpen, setBulkOpen] = useState(false)
  const [bulkMode, setBulkMode] = useState<BulkMode>('members')
  const [bulkMemberIds, setBulkMemberIds] = useState<number[]>([])
  const [bulkMemberScope, setBulkMemberScope] = useState<MemberScope>('all_snapshot')
  const [bulkInitialNumbers, setBulkInitialNumbers] = useState<string[]>([])
  const [membersOpen, setMembersOpen] = useState(false)
  const [manualOpen, setManualOpen] = useState(false)
  const [contactsOpen, setContactsOpen] = useState(false)
  const [mediaDisplay, setMediaDisplay] = useState<'dynamic' | 'framed'>(() => readStored<'dynamic' | 'framed'>(STORAGE.mediaDisplay, 'dynamic'))
  const [contentFiltersOpen, setContentFiltersOpen] = useState(false)
  const [indexDialogOpen, setIndexDialogOpen] = useState(false)
  const [showWordPressUsed, setShowWordPressUsed] = useState(true)
  const [selectedIndexLabel, setSelectedIndexLabel] = useState<number | null>(null)
  const [selectedSenderKey, setSelectedSenderKey] = useState<string | null>(null)
  const [senderResolutionState, setSenderResolutionState] = useState<'idle' | 'syncing' | 'ready' | 'failed'>('idle')
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
  const liveDialogSyncInFlightRef = useRef(false)
  const activeMessagePeerRef = useRef<string | null>(null)
  const messageScrollMemoryRef = useRef<Map<string, MessageScrollMemory>>(new Map())
  const messageCacheRef = useRef<Map<string, MessageItem[]>>(new Map())
  const messageSyncInFlightRef = useRef<Set<string>>(new Set())
  const senderSyncAttemptRef = useRef<Set<string>>(new Set())
  const [composerDocked, setComposerDocked] = useState(() => window.matchMedia('(min-width: 1500px)').matches)
  const [chatsDocked, setChatsDocked] = useState(() => window.matchMedia('(min-width: 900px)').matches)
  useEffect(() => {
    const composerQuery = window.matchMedia('(min-width: 1500px)')
    const chatsQuery = window.matchMedia('(min-width: 900px)')
    const update = () => {
      setComposerDocked(composerQuery.matches); setChatsDocked(chatsQuery.matches)
      if (composerQuery.matches) setComposerOpen(false)
      if (chatsQuery.matches) setChatsOpen(false)
    }
    update(); composerQuery.addEventListener('change', update); chatsQuery.addEventListener('change', update)
    return () => { composerQuery.removeEventListener('change', update); chatsQuery.removeEventListener('change', update) }
  }, [])
  useEffect(() => {
    const closeTransientPanels = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') return
      setChatsOpen(false)
      setComposerOpen(false)
      setContentFiltersOpen(false)
    }
    window.addEventListener('keydown', closeTransientPanels)
    return () => window.removeEventListener('keydown', closeTransientPanels)
  }, [])
  useEffect(() => {
    if (sessionWarning) toast.warn(sessionWarning, { toastId: 'session-remote-warning' })
  }, [sessionWarning])
  useEffect(() => { writeStored(STORAGE.tab, tab) }, [tab])
  useEffect(() => { writeStored(STORAGE.mediaDisplay, mediaDisplay) }, [mediaDisplay])
  useEffect(() => { if (siteKey) writeStored(STORAGE.siteKey, siteKey) }, [siteKey])
  useEffect(() => { if (dialog) writeStored(STORAGE.peerKey, dialog.peer_key) }, [dialog?.peer_key])

  const openBulk = useCallback((mode: BulkMode, memberIds: number[] = [], numbers: string[] = [], memberScope: MemberScope = memberIds.length ? 'selected' : 'all_snapshot') => {
    setBulkMode(mode)
    setBulkMemberIds(memberIds)
    setBulkMemberScope(memberScope)
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
    setSenderResolutionState('idle')
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
    if (!siteKey || syncingDialogs || !dialogsSupported) return
    const previousCount = dialogs.length
    setSyncingDialogs(true)
    try {
      const started = await api<{ job: { job_id: string; state: string } }>('POST', '/api/v1/dialogs/sync/start', { site_key: siteKey, page_size: 100, max_pages: 100 })
      let job: any = started.job
      for (let attempt = 0; attempt < 600 && ['queued', 'running'].includes(job.state); attempt += 1) {
        await waitForAdaptivePoll(attempt, { active: true })
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
  }, [siteKey, syncingDialogs, dialogs.length, dialogsSupported, applyDialogs])

  const loadDialogs = useCallback(async () => {
    if (!siteKey) return
    if (!dialogsSupported) {
      setDialogs([])
      setDialog(null)
      return
    }
    setLoadingDialogs(true)
    try {
      const response = await api<{ dialogs: DialogItem[]; sync?: { deferred?: boolean } }>('POST', '/api/v1/dialogs/list', { site_key: siteKey, refresh_if_empty: true })
      applyDialogs(response.dialogs)
      if (!response.dialogs.length && response.sync?.deferred) {
        await syncDialogs()
      }
    } catch (e) { toast.error(e instanceof Error ? e.message : 'دریافت گفتگوها ناموفق بود.') }
    finally { setLoadingDialogs(false) }
  }, [siteKey, dialogsSupported, applyDialogs, syncDialogs])

  const liveSyncDialogs = useCallback(async () => {
    if (!siteKey || !dialogsSupported || syncingDialogs || liveDialogSyncInFlightRef.current) return
    liveDialogSyncInFlightRef.current = true
    try {
      const response = await api<{ dialogs: DialogItem[] }>('POST', '/api/v1/dialogs/live-sync', { site_key: siteKey })
      applyDialogs(response.dialogs)
    } finally {
      liveDialogSyncInFlightRef.current = false
    }
  }, [applyDialogs, dialogsSupported, siteKey, syncingDialogs])

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
    if (!historySupported) return []
    const response = await api<{ messages: MessageItem[] }>('POST', '/api/v1/messages/list', { site_key: siteKey, peer_file: selected.peer_file, limit, before_id: beforeId })
    return [...response.messages].reverse()
  }, [historySupported, siteKey, viewportPageSize])

  const markDialogRead = useCallback(async (selected: DialogItem, maxId: number, remainingUnreadCount: number) => {
    if (!siteKey || !historySupported || maxId < 1 || lastReadRef.current[selected.peer_key] === maxId) return
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
  }, [historySupported, siteKey, loadDialogs])

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

  const syncDialogMessages = useCallback(async (selected: DialogItem, options?: {
    force?: boolean
    silent?: boolean
    local?: MessageItem[]
    background?: boolean
    propagateError?: boolean
  }) => {
    const lastSync = syncTimesRef.current[selected.peer_key] || 0
    if (!options?.force && Date.now() - lastSync < REMOTE_MESSAGE_TTL_MS) return options?.local || []
    if (options?.background && messageSyncInFlightRef.current.has(selected.peer_key)) return options.local || []
    messageSyncInFlightRef.current.add(selected.peer_key)
    const unreadCount = Math.max(0, selected.unread_count || 0)
    const initialLimit = Math.min(500, Math.max(viewportPageSize, unreadCount + 15))
    const local = options?.local || []
    const newestLocalId = local.length ? local[local.length - 1].id : 0
    const remoteAhead = Boolean(selected.top_message_id && selected.top_message_id > newestLocalId)
    const pages = !local.length ? Math.max(1, Math.min(20, Math.ceil(initialLimit / 25))) : remoteAhead || unreadCount > 0 ? Math.max(1, Math.min(6, Math.ceil(Math.max(unreadCount, viewportPageSize) / 50))) : 1
    if (!options?.background) setLoadingMessages(true)
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
      if (options?.propagateError) throw e
      return local
    } finally {
      messageSyncInFlightRef.current.delete(selected.peer_key)
      if (!options?.background) setLoadingMessages(false)
    }
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
    if (!siteKey || !dialogsSupported) return
    let cancelled = false

    const poll = async () => {
      let failedAttempts = 0
      while (!cancelled) {
        await waitForAdaptivePoll(failedAttempts, { active: false })
        if (cancelled) return
        try {
          await liveSyncDialogs()
          failedAttempts = 0
        } catch {
          failedAttempts = Math.min(8, failedAttempts + 1)
        }
      }
    }
    void poll()
    return () => { cancelled = true }
  }, [dialogsSupported, liveSyncDialogs, siteKey])
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

    if (dateRange && messages.length) {
      const lastMessage = messages[messages.length - 1]
      setLoadingMessages(true)
      try {
        const nextFrom = new Date(new Date(lastMessage.date).getTime() + 1000).toISOString()
        const request = {
          site_key: siteKey,
          peer_file: dialog.peer_file,
          date_from: nextFrom,
          date_to: dateRange.to,
          limit: 10000,
        }
        let response = await api<{ messages: MessageItem[] }>('POST', '/api/v1/messages/list', request)
        
        if (!response.messages.length) {
          await api('POST', '/api/v1/messages/date-range/sync', {
            site_key: siteKey,
            peer_file: dialog.peer_file,
            date_from: nextFrom,
            date_to: dateRange.to,
            pages: 20,
            page_size: 100,
          })
          response = await api<{ messages: MessageItem[] }>('POST', '/api/v1/messages/list', request)
        }

        if (response.messages.length) {
          const chronological = [...response.messages].sort((left, right) => (
            new Date(left.date).getTime() - new Date(right.date).getTime() || left.id - right.id
          ))
          setMessages(current => mergeMessagesById(current, chronological))
        }
      } finally {
        setLoadingMessages(false)
      }
      return
    }

    const current = messages
    await syncDialogMessages(dialog, { force, silent: !force, local: current })
    if (force) toast.success('درخواست همگام‌سازی با موفقیت ارسال شد و در پس‌زمینه درحال انجام است.')
  }, [dialog, loadingMessages, messages, syncDialogMessages, dateRange, siteKey])

  useEffect(() => {
    if (!dialog || !siteKey || !historySupported || dateRange || loadingDateRange) {
      setLiveMessageState('idle')
      return
    }
    let cancelled = false
    const selected = dialog
    setLiveMessageState('connecting')

    const poll = async () => {
      let failedAttempts = 0
      while (!cancelled) {
        await waitForAdaptivePoll(failedAttempts, { active: true })
        if (cancelled || activeMessagePeerRef.current !== selected.peer_key) return
        try {
          const local = messageCacheRef.current.get(selected.peer_key) || []
          await syncDialogMessages(selected, {
            force: true,
            silent: true,
            local,
            background: true,
            propagateError: true,
          })
          if (cancelled) return
          failedAttempts = 0
          setLiveMessageState('live')
        } catch {
          if (cancelled) return
          failedAttempts = Math.min(8, failedAttempts + 1)
          setLiveMessageState('retrying')
        }
      }
    }
    void poll()
    return () => { cancelled = true }
  }, [dateRange, dialog?.peer_key, historySupported, loadingDateRange, siteKey, syncDialogMessages])

  const loadFromJalaliDate = useCallback(async (selectedValue?: string, selectedMode?: 'day' | 'from', forceSync?: boolean) => {
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
        limit: 10000,
      }
      let response = await api<{ messages: MessageItem[] }>('POST', '/api/v1/messages/list', request)
      let source = 'حافظه محلی'
      if (!response.messages.length || forceSync) {
          if (forceSync) toast.info("در حال همگام‌سازی عمیق با سرور ایتا... (لطفاً منتظر بمانید)");
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
    if (!dialog || !mediaReadSupported) return
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
  }, [dialog, mediaReadSupported, siteKey])

  const openFullMedia = useCallback(async (message: MessageItem) => {
    if (!dialog || !mediaReadSupported) return
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
  }, [dialog, mediaReadSupported, siteKey])

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
        is_primary: item.kind === 'wordpress-category',
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
        await waitForAdaptivePoll(attempt, { active: true })
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

  const messageGroupLookup = useMemo(() => buildMessageGroupLookup(indexedMessages, {
    fallbackIncomingSenderKey: dialog && dialog.display_kind !== 'group' ? dialog.peer_key : null,
  }), [dialog, indexedMessages])

  const filteredMessages = useMemo(() => {
    const q = messageSearch.trim().toLowerCase()
    return indexedMessages.filter(item => {
      const members = messageGroupLookup.get(item.id)?.messages || [item]
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
  }, [indexedMessages, messageGroupLookup, messageSearch, selectedIndexLabel, selectedSenderKey, showWordPressUsed])

  const indexFilterLabels = useMemo(() => {
    const labels = new Map<number, string>()
    for (const message of indexedMessages) {
      for (const prediction of message.index_predictions || []) labels.set(prediction.label_id, prediction.label_name)
    }
    return [...labels].map(([id, name]) => ({ id, name })).sort((left, right) => left.name.localeCompare(right.name, 'fa'))
  }, [indexedMessages])
  const senderFilterOptions = useMemo<SenderFilterOption[]>(() => {
    const options = new Map<string, SenderFilterOption>()
    const resolutionRank: Record<SenderFilterOption['resolution'], number> = {
      self: 5,
      eitaa_contact: 4,
      local_contact: 3,
      history_user: 3,
      community_member: 2,
      unknown: 1,
    }
    for (const message of indexedMessages) {
      const key = message.sender_key
      if (!key) continue
      const rawUserId = key.startsWith('user:') ? key.slice('user:'.length) : ''
      const numericUserId = /^\d+$/.test(rawUserId) ? Number(rawUserId) : null
      const resolution = message.sender_resolution || (key === 'self' ? 'self' : 'unknown')
      const candidate: SenderFilterOption = {
        key,
        label: message.sender_display_name?.trim()
          || (key === 'self'
            ? 'پیام‌های ارسالی من'
            : `کاربر ناشناس · شناسه ${numericUserId !== null ? numericUserId.toLocaleString('fa-IR') : rawUserId}`),
        username: message.sender_username || null,
        isEitaaContact: Boolean(message.sender_is_eitaa_contact),
        resolution,
      }
      const current = options.get(key)
      if (
        !current
        || (candidate.isEitaaContact && !current.isEitaaContact)
        || resolutionRank[candidate.resolution] > resolutionRank[current.resolution]
      ) options.set(key, candidate)
    }
    return [...options.values()].sort((left, right) => {
      if (left.key === 'self') return -1
      if (right.key === 'self') return 1
      return left.label.localeCompare(right.label, 'fa')
    })
  }, [indexedMessages])
  const unresolvedSenderCount = senderFilterOptions.filter(option => option.resolution === 'unknown').length

  useEffect(() => {
    const selected = dialog
    if (
      !contentFiltersOpen
      
      || !selected
      || selected.display_kind === 'personal'
      || unresolvedSenderCount === 0
    ) {
      if (contentFiltersOpen && unresolvedSenderCount === 0) {
        setSenderResolutionState('ready')
      }
      return
    }
    const attemptKey = `${siteKey}:${selected.peer_key}`
    if (senderSyncAttemptRef.current.has(attemptKey)) return
    senderSyncAttemptRef.current.add(attemptKey)
    setSenderResolutionState('syncing')
    const loadedMessageCount = messages.length

    void (async () => {
      try {
        await api('POST', '/api/v1/messages/sync', {
          site_key: siteKey,
          peer_file: selected.peer_file,
          pages: Math.min(50, Math.max(1, Math.ceil(loadedMessageCount / 100))),
          page_size: 100,
          offset_id: 0,
          stop_when_unchanged: false,
        })
        await refreshLocalMessages(selected, Math.min(5000, Math.max(viewportPageSize, loadedMessageCount)))
        setSenderResolutionState('ready')
      } catch (error) {
        setSenderResolutionState('failed')
        toast.warning(error instanceof Error ? error.message : 'بازیابی نام نویسندگان ناموفق بود.')
      }
    })()
  }, [
    contentFiltersOpen,
    dialog,
    
    messages.length,
    refreshLocalMessages,
    siteKey,
    unresolvedSenderCount,
    viewportPageSize,
  ])
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
      void startContentIndex()
      toast.success('اصلاح شما ثبت شد و همین حالا در پیشنهادها و فیلترها اعمال شد.')
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'ثبت اصلاح ایندکس ناموفق بود.')
    } finally {
      setSavingIndexEditor(false)
    }
  }, [contentIndexResults, dialog, indexDefinitions, indexEditor, loadContentIndexResults, siteKey, startContentIndex])

  const dialogCounts = useMemo(() => ({
    all: dialogs.length,
    channel: dialogs.filter(item => item.display_kind === 'channel').length,
    group: dialogs.filter(item => item.display_kind === 'group').length,
    personal: dialogs.filter(item => item.display_kind === 'personal').length,
    favorite: dialogs.filter(item => item.favorite).length,
  }), [dialogs])

  const railTabs: Array<{ value: Tab; label: string; count: number }> = [
    { value: 'all', label: 'همه', count: dialogCounts.all },
    { value: 'channel', label: 'کانال‌ها', count: dialogCounts.channel },
    { value: 'group', label: 'گروه‌ها', count: dialogCounts.group },
    { value: 'personal', label: 'شخصی', count: dialogCounts.personal },
    { value: 'favorite', label: 'منتخب', count: dialogCounts.favorite },
  ]

  const toggleFavorite = async (item: DialogItem) => {
    const originalDialogs = dialogs;
    const targetState = !item.favorite;
    applyDialogs(dialogs.map(entry => entry.peer_key === item.peer_key ? { ...entry, favorite: targetState } : entry));
    try {
      const response = await api<{ dialog: DialogItem }>('POST', '/api/v1/dialogs/favorite', { site_key: siteKey, peer_key: item.peer_key, favorite: targetState })
      applyDialogs(originalDialogs.map(entry => entry.peer_key === item.peer_key ? response.dialog : entry))
    } catch (e) {
      applyDialogs(originalDialogs);
      toast.error(e instanceof Error ? e.message : 'خطا در ثبت منتخب')
    }
  }

  const setDisplayKind = async (item: DialogItem, displayKind: DisplayKind) => {
    try {
      const response = await api<{ dialog: DialogItem }>('POST', '/api/v1/dialogs/display-kind', { site_key: siteKey, peer_key: item.peer_key, display_kind: displayKind })
      applyDialogs(dialogs.map(entry => entry.peer_key === item.peer_key ? response.dialog : entry))
    } catch (e) { toast.error(e instanceof Error ? e.message : 'اصلاح نوع گفتگو ناموفق بود.') }
  }

  const toggleMessage = (message: MessageItem) => {
    if (!dialog) return
    const groupMessages = messageGroupLookup.get(message.id)?.messages || [message]
    const usedMessage = groupMessages.find(item => item.usage.used)
    if (usedMessage && !selectionMode && selectedKeys.length === 0) {
      setActiveUsage({ message: usedMessage, usage: usedMessage.usage })
      return
    }
    const keys = groupMessages.map(item => messageKey(dialog, item))
    setSelectedKeys(current => {
      const remove = keys.every(key => current.includes(key))
      return remove ? current.filter(item => !keys.includes(item)) : [...new Set([...current, ...keys])]
    })
    setSelectionMode(true)
  }

  const clearSelection = () => { setSelectedKeys([]); setSelectionMode(false) }
  const showDialogSection = useCallback((value: Tab) => {
    setTab(value)
    if (!chatsDocked) {
      setComposerOpen(false)
      setChatsOpen(true)
    }
  }, [chatsDocked])
  const logout = async () => {
    if (!confirm('از حساب ایتا خارج شوید؟')) return
    try { await api('POST', '/api/v1/auth/logout'); await onLogout() }
    catch (e) { toast.error(e instanceof Error ? e.message : 'خروج ناموفق بود.') }
  }
  const logoutSoftware = async () => {
    if (!confirm('از نرم‌افزار خارج شوید؟ نشست حساب ایتا حذف نمی‌شود.')) return
    try { await appUser.logout() }
    catch (e) { toast.error(e instanceof Error ? e.message : 'خروج از نرم‌افزار انجام نشد.') }
  }

  return <Box sx={{ width: '100%', height: '100%', minWidth: 0, minHeight: 0, overflow: 'hidden', bgcolor: 'background.default' }}>
    <Box component="main" sx={{ width: '100%', height: '100%', minWidth: 0, minHeight: 0, overflow: 'hidden', display: { xs: 'block', md: 'grid' }, pb: { xs: 'calc(66px + env(safe-area-inset-bottom))', md: 0 }, gridTemplateColumns: { md: composerDocked ? '72px minmax(300px, 22vw) minmax(0, 1fr) minmax(340px, 26vw)' : '72px minmax(280px, 32vw) minmax(0, 1fr)' }, '& > *': { minWidth: 0, minHeight: 0 } }}>
      <WorkspaceNavigation
        sections={railTabs}
        activeSection={tab}
        userName={appUser.principal?.display_name || 'Eitaa Bridge'}
        userRole={appUser.principal?.global_role === 'admin' ? 'مدیر نرم‌افزار' : 'کاربر نرم‌افزار'}
        accountControl={<MessengerAccountMenuControl />}
        syncing={syncingDialogs}
        dialogsEnabled={dialogsSupported}
        wordpressEnabled={wordpressAvailable}
        onSection={showDialogSection}
        onSettings={() => setSettingsOpen(true)}
        onAddDialog={() => setManualOpen(true)}
        onSync={() => void syncDialogs()}
        onContacts={() => setContactsOpen(true)}
        onBulk={() => openBulk(dialog && dialog.display_kind !== 'personal' ? 'members' : 'numbers')}
        onWordpress={() => { setCommunityOpen(false); setComposerOpen(true) }}
        onMessengerLogout={() => void logout()}
        onSoftwareLogout={appUser.enabled ? () => void logoutSoftware() : undefined}
      />

      <ConversationListPage
        open={chatsOpen}
        docked={chatsDocked}
        loading={loadingDialogs}
        syncing={syncingDialogs}
        dialogsEnabled={dialogsSupported}
        filterLabel={railTabs.find(item => item.value === tab)?.label || 'گفتگوها'}
        search={dialogSearch}
        items={visibleDialogs}
        totalFiltered={filteredDialogs.length}
        activePeerKey={dialog?.peer_key}
        renderAvatar={item => <DialogAvatar dialog={item} siteKey={siteKey} />}
        titleFor={item => titleFor(item)}
        onSearch={setDialogSearch}
        onClose={() => setChatsOpen(false)}
        onSync={() => void syncDialogs()}
        onAdd={() => setManualOpen(true)}
        onSelect={selectDialog}
        onFavorite={item => void toggleFavorite(item)}
        onDisplayKind={(item, kind) => void setDisplayKind(item, kind)}
      />

      <Paper component="section" square elevation={0} sx={{ display: 'grid', gridTemplateRows: 'auto minmax(0, 1fr) auto', position: 'relative', minWidth: 0, minHeight: 0, height: { xs: 'calc(100dvh - 66px - env(safe-area-inset-bottom))', md: '100%' }, overflow: 'hidden', bgcolor: theme => theme.palette.mode === 'dark' ? '#0c131b' : '#e7f0ea' }}>
        {messengerAccounts.featureEnabled && messengerAccounts.capabilityError && <Alert severity="warning" sx={{ borderRadius: 0 }}>{messengerAccounts.capabilityError} عملیات پیام‌رسان تا بازیابی وضعیت غیرفعال می‌ماند.</Alert>}
        {messengerAccounts.featureEnabled && !messengerAccounts.capabilityLoading && !dialogsSupported && <Alert severity="info" sx={{ borderRadius: 0 }}>خواندن گفتگوها برای حساب انتخاب‌شده پشتیبانی نمی‌شود.</Alert>}
        <ChatHeader
          title={titleFor(dialog)}
          subtitle={dialog ? `${messages.length.toLocaleString('fa-IR')} پیام ذخیره‌شده` : 'گفتگویی انتخاب نشده'}
          avatar={<DialogAvatar dialog={dialog} siteKey={siteKey} small />}
          selectionCount={selectionMode ? selectedKeys.length : 0}
          liveState={dialog && historySupported ? liveMessageState : 'idle'}
          mediaDynamic={mediaDisplay === 'dynamic'}
          mediaEnabled={Boolean(dialog && mediaReadSupported)}
          filtersActive={contentFiltersOpen || !showWordPressUsed || selectedIndexLabel !== null || selectedSenderKey !== null}
          filterEnabled={Boolean(dialog && dialog.display_kind !== 'personal')}
          indexActive={indexDialogOpen}
          indexEnabled={Boolean(dialog && (dialog.display_kind === "channel" || dialog.display_kind === "group") && tab === "favorite")}
          onToggleIndex={() => setIndexDialogOpen(v => !v)}
          datePicker={<JalaliDatePicker
            value={jalaliFrom}
            mode={dateMode}
            disabled={!dialog || loadingDateRange}
            busy={loadingDateRange}
            onMode={setDateMode}
            onSelect={(value, mode, forceSync) => void loadFromJalaliDate(value, mode, forceSync)}
            onClear={() => void clearDateRange()}
          />}
          search={messageSearch}
          wordpressEnabled={wordpressAvailable}
          composerVisible={composerDocked || composerOpen}
          onOpenChats={() => setChatsOpen(true)}
          onClearSelection={clearSelection}
          onToggleMedia={() => setMediaDisplay(value => value === 'dynamic' ? 'framed' : 'dynamic')}
          onToggleFilters={() => setContentFiltersOpen(value => !value)}
          onSearch={setMessageSearch}
          onOpenComposer={() => setComposerOpen(true)}
        />
        {!dialog ? <Stack alignItems="center" justifyContent="center" spacing={2} sx={{ minHeight: 0, height: '100%', p: 3, textAlign: 'center' }}><AuthBrandMark /><Typography variant="h6">یک گفتگو را انتخاب کنید</Typography></Stack> : <VirtualMessageList key={dialog.peer_key} dialog={dialog} siteKey={siteKey} messages={filteredMessages} groupLookup={messageGroupLookup} media={media} mediaDisplay={mediaDisplay} selectedKeys={selectedKeys} selectionMode={selectionMode} loading={loadingMessages} readReceiptsEnabled={!dateRange && !messageSearch.trim() && showWordPressUsed && selectedIndexLabel === null && selectedSenderKey === null} focusMessageId={dateJump?.messageId || null} focusEpoch={dateJump?.epoch || 0} scrollMemory={messageScrollMemoryRef.current} loadMedia={loadMedia} openFullMedia={openFullMedia} toggleMessage={toggleMessage} editIndex={(message, members) => setIndexEditor({ message, messageIds: members.map(item => item.id), selectedIds: [...new Set(members.flatMap(item => (contentIndexResults[item.id]?.predictions || []).map(prediction => prediction.label_id)))] })} loadOlder={loadOlder} loadNewer={loadNewer} markRead={markDialogRead} openUsage={message => { setActiveUsage({ message, usage: message.usage }) }} />}
        <QuickSendBar siteKey={siteKey} dialog={dialog} onSent={() => loadNewer(true)} />
      </Paper>

      <Paper component="aside" square elevation={composerDocked ? 0 : 12} sx={composerDocked ? {
        position: 'static', minWidth: 0, minHeight: 0, overflow: 'hidden', borderInlineStart: 1, borderColor: 'divider', zIndex: 1,
      } : {
        position: 'fixed', zIndex: theme => theme.zIndex.drawer + 2, insetBlock: 0, insetInlineEnd: 0, width: 'min(520px, 94vw)', minWidth: 0, minHeight: 0, overflow: 'hidden', borderInlineStart: 1, borderColor: 'divider', transform: composerOpen ? 'translateX(0)' : 'translateX(105%)', transition: theme => theme.transitions.create('transform', { duration: theme.transitions.duration.shorter }),
      }}>
        <Composer dialog={dialog} dialogs={dialogs} siteKey={siteKey} sites={sites} setSiteKey={setSiteKey} wordpressReady={Boolean(activeSite?.credentials_configured)} openSettings={() => setSettingsOpen(true)} openBulk={openBulk} openMembers={() => setMembersOpen(true)} selectedMessages={selectedMessages} selectedKeys={selectedKeys} setSelectedKeys={setSelectedKeys} suggestedCategoryIds={suggestedCategoryIds} categories={categories} tags={tags} setTags={setTags} media={media} close={() => setComposerOpen(false)} communityOpen={communityOpen} setCommunityOpen={setCommunityOpen} onSuccess={refreshCurrentLocalView} markSourcesUsed={markWordPressSourcesUsed} />
      </Paper>
    </Box>
    <UsageInfoDialog activeUsage={activeUsage} clearUsage={() => setActiveUsage(null)} loadHistory={item => { /* will do loadHistory later or let user implement if needed */ }} />
    <Dialog open={settingsOpen} fullScreen onClose={() => setSettingsOpen(false)}>
      <DialogContent sx={{ p: 0, bgcolor: 'background.default' }}>
        <Suspense fallback={<Stack alignItems="center" justifyContent="center" spacing={2} sx={{ minHeight: '100dvh' }}><CircularProgress /><Typography>در حال آماده‌سازی تنظیمات…</Typography></Stack>}>
          <SettingsPage sites={sites} onClose={() => setSettingsOpen(false)} onChanged={loadSites} />
        </Suspense>
      </DialogContent>
    </Dialog>
    {bulkOpen && <BulkOperationsModal siteKey={siteKey} dialog={dialog} initialMode={bulkMode} initialMemberIds={bulkMemberIds} initialMemberScope={bulkMemberScope} initialNumbers={bulkInitialNumbers} close={() => setBulkOpen(false)} />}
    {membersOpen && <CommunityMembersModal siteKey={siteKey} dialog={dialog} dialogs={dialogs} close={() => setMembersOpen(false)} openBulk={selection => { setMembersOpen(false); openBulk('members', selection.memberIds, [], selection.scope) }} />}
    {manualOpen && <ManualDialogModal siteKey={siteKey} close={() => setManualOpen(false)} onAdded={item => { applyDialogs([item, ...dialogs.filter(d => d.peer_key !== item.peer_key)]); selectDialog(item); setManualOpen(false) }} />}
    {contactsOpen && <Suspense fallback={<CircularProgress sx={{ position: 'fixed', inset: 0, m: 'auto', zIndex: theme => theme.zIndex.modal + 1 }} />}><ContactDirectoryModal
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
    /></Suspense>}
    {mediaViewer && <MaterialLegacyDialog close={() => setMediaViewer(null)} maxWidth="xl">
      <Paper variant="outlined" sx={{ overflow: 'hidden', borderRadius: 3 }}>
        <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ px: 2, py: 1, borderBottom: 1, borderColor: 'divider' }}><Typography fontWeight={850}>{mediaViewer.title}</Typography><IconButton onClick={() => setMediaViewer(null)} aria-label="بستن"><CloseRounded /></IconButton></Stack>
        <Box sx={{ minHeight: 260, maxHeight: '78dvh', display: 'grid', placeItems: 'center', overflow: 'auto', bgcolor: 'action.hover', p: 1 }}>
          {fullMedia[mediaViewer.key] === null || fullMedia[mediaViewer.key] === undefined
            ? <Skeleton variant="rounded" animation="wave" width="min(76vw, 920px)" height="min(68vh, 620px)" />
            : fullMedia[mediaViewer.key]
              ? <Box component="img" src={fullMedia[mediaViewer.key] || ''} alt={mediaViewer.title} sx={{ display: 'block', maxWidth: '100%', maxHeight: '74dvh', objectFit: 'contain' }} />
              : <Alert severity="error">تصویر اصلی در دسترس نیست.</Alert>}
        </Box>
      </Paper>
    </MaterialLegacyDialog>}
    {contentFiltersOpen && <Suspense fallback={<CircularProgress sx={{ position: 'fixed', inset: 0, m: 'auto', zIndex: theme => theme.zIndex.modal + 1 }} />}><MessageFilterDialog
      open={contentFiltersOpen}
      close={() => setContentFiltersOpen(false)}
      showWordPressUsed={showWordPressUsed}
      setShowWordPressUsed={setShowWordPressUsed}
      selectedIndexLabel={selectedIndexLabel}
      setSelectedIndexLabel={setSelectedIndexLabel}
      selectedSenderKey={selectedSenderKey}
      setSelectedSenderKey={setSelectedSenderKey}
      indexFilterLabels={indexDefinitions.map(def => ({ id: def.id, name: def.name }))}
      senderFilterOptions={senderFilterOptions}
      senderResolutionState={senderResolutionState}
      unresolvedSenderCount={unresolvedSenderCount}
      filteredMessageCount={filteredMessages.length}
    /></Suspense>}
    {indexDialogOpen && <Suspense fallback={<CircularProgress sx={{ position: 'fixed', inset: 0, m: 'auto', zIndex: theme => theme.zIndex.modal + 1 }} />}><ContentIndexDialog
      open={indexDialogOpen}
      close={() => setIndexDialogOpen(false)}
      contentIndexActive={contentIndexActive}
      contentIndexState={contentIndexJob?.state}
      contentIndexProcessed={contentIndexProgress.processed_messages || 0}
      contentIndexTarget={contentIndexProgress.target_messages || 0}
      contentIndexPercent={contentIndexPercent}
      coldStart={Object.keys(contentIndexResults).length < 5}
      resultCount={Object.keys(contentIndexResults).length}
      canStart={dialog != null && indexDefinitions.length > 0}
      start={startContentIndex}
      cancel={cancelContentIndex}
      definitions={indexDefinitions}
      categories={categories.map(c => ({ id: c.id, name: c.name }))}
      customIndexName={customIndexName}
      setCustomIndexName={setCustomIndexName}
      customIndexKeywords={customIndexKeywords}
      setCustomIndexKeywords={setCustomIndexKeywords}
      customIndexCategoryId={customIndexCategoryId}
      setCustomIndexCategoryId={setCustomIndexCategoryId}
      addCustomIndex={addCustomIndex}
      selectedDefinitionId={indexKeywordCategoryId}
      selectDefinition={setIndexKeywordCategoryId}
      indexNameDraft={indexNameDraft}
      setIndexNameDraft={setIndexNameDraft}
      indexKeywordDraft={indexKeywordDraft}
      setIndexKeywordDraft={setIndexKeywordDraft}
      saveDefinition={saveIndexKeywords}
      deleteDefinition={deleteCustomIndex}
    /></Suspense>}
    {indexEditor && <Suspense fallback={<CircularProgress sx={{ position: 'fixed', inset: 0, m: 'auto', zIndex: theme => theme.zIndex.modal + 1 }} />}><MessageIndexEditor
      open
      messageLabel={indexEditor.messageIds.length > 1 ? `گالری ${indexEditor.messageIds.length}‌پیامی` : `پیام #${indexEditor.message.id}`}
      definitions={indexDefinitions}
      selectedIds={indexEditor.selectedIds}
      setSelectedIds={selectedIds => setIndexEditor(current => current ? ({ ...current, selectedIds }) : current)}
      saving={savingIndexEditor}
      close={() => setIndexEditor(null)}
      save={() => void saveMessageIndexFeedback()}
    /></Suspense>}
    {((chatsOpen && !chatsDocked) || (composerOpen && !composerDocked)) && <Box role="presentation" onClick={() => { setChatsOpen(false); setComposerOpen(false) }} sx={{ position: 'fixed', inset: 0, zIndex: theme => theme.zIndex.drawer - 1, bgcolor: 'rgba(0,0,0,.42)', backdropFilter: 'blur(1px)' }} />}
  </Box>
}

function VirtualMessageList(props: { dialog: DialogItem; siteKey: string; messages: MessageItem[]; groupLookup: Map<number, MessageGroup>; media: Record<string, string | null>; mediaDisplay: 'dynamic' | 'framed'; selectedKeys: string[]; selectionMode: boolean; loading: boolean; readReceiptsEnabled: boolean; focusMessageId: number | null; focusEpoch: number; scrollMemory: Map<string, MessageScrollMemory>; loadMedia: (message: MessageItem) => Promise<void>; openFullMedia: (message: MessageItem) => Promise<void>; toggleMessage: (message: MessageItem) => void; editIndex: (message: MessageItem, members: MessageItem[]) => void; loadOlder: () => Promise<number>; loadNewer: () => Promise<void>; markRead: (dialog: DialogItem, maxId: number, remainingUnreadCount: number) => Promise<void>; openUsage: (message: MessageItem) => void }) {
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
  const groupLookup = props.groupLookup

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
    const group = candidate ? groupLookup.get(candidate.id) : undefined
    return group ? props.messages.findIndex(message => message.id === group.leader.id) : firstUnreadCandidateIndex
  }, [firstUnreadCandidateIndex, groupLookup, props.messages])

  const virtualizer = useVirtualizer({
    count: props.messages.length,
    getScrollElement: () => parentRef.current,
    getItemKey: index => props.messages[index] ? messageKey(props.dialog, props.messages[index]) : `${props.dialog.peer_key}:missing:${index}`,
    estimateSize: index => {
      let message = props.messages[index]
      if (!message) return 120
      const group = groupLookup.get(message.id)
      if (group && group.leader.id !== message.id) return 0
      const caption = group ? messageGroupText(group.messages) : message.text
      if (group) message = { ...message, text: caption, text_length: caption.length }
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
    const row = [...element.querySelectorAll<HTMLElement>('[data-message-key]')]
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
      .filter(message => !groupLookup.has(message.id) || groupLookup.get(message.id)?.leader.id === message.id)
      .flatMap(message => groupLookup.get(message.id)?.messages || [message])
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
  }, [firstUnreadIndex, groupLookup, props.dialog, props.markRead, props.messages, props.readReceiptsEnabled, virtualizer])

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
    const focusedGroup = groupLookup.get(props.focusMessageId)
    const targetMessageId = focusedGroup?.leader.id || props.focusMessageId
    const targetIndex = props.messages.findIndex(message => message.id === targetMessageId)
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
  }, [groupLookup, persistScrollMemory, props.focusEpoch, props.focusMessageId, props.messages, virtualizer])

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

  return <Box ref={parentRef} sx={{ position: 'relative', minHeight: 0, overflow: 'auto', overflowAnchor: 'none', scrollbarGutter: 'stable', background: theme => theme.palette.mode === 'dark' ? 'linear-gradient(rgba(12,19,27,.94),rgba(12,19,27,.94)), radial-gradient(circle at 20% 20%,rgba(126,163,146,.16) 1px,transparent 1.5px)' : 'linear-gradient(rgba(231,240,234,.9),rgba(231,240,234,.9)), radial-gradient(circle at 20% 20%,rgba(91,130,73,.18) 1px,transparent 1.5px)', backgroundSize: 'auto, 27px 27px' }}>
    <Box aria-hidden="true" sx={{ position: 'sticky', zIndex: 8, top: 0, height: 0, width: '100%', pointerEvents: 'none' }}>
      {floatingDate && <Chip label={floatingDate} size="small" sx={{ position: 'absolute', top: 8, left: '50%', transform: 'translateX(-50%)', bgcolor: 'rgba(29,44,39,.78)', color: '#fff', backdropFilter: 'blur(5px)' }} />}
      {props.loading && <Chip icon={<CircularProgress size={14} color="inherit" />} label="در حال همگام‌سازی" size="small" sx={{ position: 'absolute', top: 42, left: '50%', transform: 'translateX(-50%)', bgcolor: 'rgba(29,44,39,.78)', color: '#fff', '& .MuiChip-icon': { color: 'inherit' } }} />}
    </Box>
    <Box sx={{ width: 'min(760px, calc(100% - 20px))', mx: 'auto', position: 'relative', height: virtualizer.getTotalSize() }}>
      {virtualizer.getVirtualItems().map(row => {
        const message = props.messages[row.index]
        const key = messageKey(props.dialog, message)
        const group = groupLookup.get(message.id)
        const isGroupFollower = Boolean(group && group.leader.id !== message.id)
        const focused = group
          ? group.messages.some(member => member.id === props.focusMessageId)
          : message.id === props.focusMessageId

        return <Box key={key} data-index={row.index} data-message-key={key} ref={virtualizer.measureElement} sx={{ position: 'absolute', top: 0, right: 0, width: '100%', py: isGroupFollower ? 0 : 0.75, height: isGroupFollower ? 0 : undefined, overflow: 'hidden', overflowAnchor: 'none', contain: isGroupFollower ? 'strict' : 'layout style', pointerEvents: isGroupFollower ? 'none' : undefined, transform: `translateY(${row.start}px)`, '& > article': focused ? { outline: '3px solid', outlineColor: 'primary.main', boxShadow: theme => `0 0 0 7px ${theme.palette.action.selected}` } : undefined }}>
          {!isGroupFollower && <>
          {(row.index === 0 || dayKeys[row.index - 1] !== dayKeys[row.index]) && <Stack direction="row" alignItems="center" spacing={1} sx={{ mb: 0.75, color: 'text.secondary' }}><Box sx={{ height: 1, bgcolor: 'divider', flex: 1 }} /><Chip label={jalaliDayLabel(message.date)} size="small" variant="outlined" sx={{ bgcolor: 'background.paper' }} /><Box sx={{ height: 1, bgcolor: 'divider', flex: 1 }} /></Stack>}
          {row.index === firstUnreadIndex && <Stack direction="row" alignItems="center" spacing={1} sx={{ mb: 0.75, color: 'error.main' }}><Box sx={{ height: 1, bgcolor: 'error.light', flex: 1 }} /><Chip label={`${props.dialog.unread_count.toLocaleString('fa-IR')} پیام خوانده‌نشده`} size="small" color="error" variant="outlined" sx={{ bgcolor: 'background.paper' }} /><Box sx={{ height: 1, bgcolor: 'error.light', flex: 1 }} /></Stack>}
          <MessageContentCard siteKey={props.siteKey} dialog={props.dialog} message={message} group={group} media={props.media} mediaDisplay={props.mediaDisplay} selectedKeys={props.selectedKeys} selectionMode={props.selectionMode} loadMedia={props.loadMedia} openFullMedia={props.openFullMedia} toggle={() => props.toggleMessage(message)} editIndex={() => props.editIndex(message, group?.messages || [message])} openUsage={() => props.openUsage(group?.messages.find(item => item.usage.used) || message)} />
          </>}
        </Box>
      })}
    </Box>
  </Box>
}
function Composer(props: { dialog: DialogItem | null; dialogs: DialogItem[]; siteKey: string; sites: Site[]; setSiteKey: (v: string) => void; wordpressReady: boolean; openSettings: () => void; openBulk: (mode: BulkMode) => void; openMembers: () => void; selectedMessages: MessageItem[]; selectedKeys: string[]; setSelectedKeys: (v: string[]) => void; suggestedCategoryIds: number[]; categories: Term[]; tags: Term[]; setTags: (v: Term[]) => void; media: Record<string, string | null>; close: () => void; communityOpen: boolean; setCommunityOpen: (v: boolean) => void; onSuccess: () => Promise<void>; markSourcesUsed: (sourceKeys: string[], publication: { composition_key: string; post_id: number; post_url?: string | null; status: string; title: string }) => void }) {
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
    setCompositionKey(makeCompositionKey()); setTitle(''); setExcerpt(''); setCategoryIds([]); setTagIds([]); setTagSearch(''); setFeaturedKey(null); setIncludeFeatured(true); setPostStatus('draft'); setConfirmPublish(false); setResult(null); setError(''); setEditRecord(null); setEditSourceKeys([])
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

  return <Box sx={{ height: '100%', minHeight: 0, overflow: 'auto', bgcolor: 'background.default' }}>
    
    <Paper square elevation={0} sx={{ position: 'sticky', top: 0, zIndex: 4, p: 1.25, borderBottom: 1, borderColor: 'divider' }}>
      <Stack direction="row" alignItems="center" spacing={1}>
        <Avatar sx={{ bgcolor: props.communityOpen ? 'secondary.main' : 'primary.main' }}>{props.communityOpen ? 'گ' : 'W'}</Avatar>
        <Box sx={{ flex: 1, minWidth: 0 }}><Typography fontWeight={900} noWrap>{props.communityOpen ? 'عملیات گفتگو' : editRecord ? `ویرایش نوشته #${editRecord.post_id}` : 'نوشته جدید وردپرس'}</Typography><Typography variant="caption" color="text.secondary" noWrap>{props.communityOpen ? titleFor(props.dialog) : `${sourceKeys.length.toLocaleString('fa-IR')} پیام در بدنه`}</Typography></Box>
        <IconButton aria-label="بستن ستون" onClick={props.close}><CloseRounded /></IconButton>
      </Stack>
      <ToggleButtonGroup exclusive fullWidth size="small" value={props.communityOpen ? 'community' : 'wordpress'} onChange={(_event, value) => { if (value) props.setCommunityOpen(value === 'community') }} sx={{ mt: 1 }}>
        <ToggleButton value="wordpress" disabled={!props.wordpressReady}>وردپرس</ToggleButton>
        <ToggleButton value="community">عملیات گفتگو</ToggleButton>
      </ToggleButtonGroup>
    </Paper>
    <Stack spacing={1.25} sx={{ p: { xs: 1, sm: 1.5 } }}>
      {props.communityOpen ? <Paper variant="outlined" sx={{ p: 2 }}>
        <Stack spacing={2}>
          <Stack direction="row" spacing={1.25} alignItems="center"><Avatar>{initials(titleFor(props.dialog))}</Avatar><Box sx={{ minWidth: 0 }}><Typography fontWeight={850} noWrap>{titleFor(props.dialog)}</Typography><Typography variant="caption" color="text.secondary" noWrap>{props.dialog?.peer.username ? `@${props.dialog.peer.username}` : props.dialog ? `Peer ID: ${props.dialog.peer.id}` : 'گفتگویی انتخاب نشده'}</Typography></Box></Stack>
          <Button variant="contained" onClick={() => props.openBulk(props.dialog && props.dialog.display_kind !== 'personal' ? 'members' : 'numbers')}>ارسال و دعوت گروهی</Button>
          <Button variant="outlined" disabled={!props.dialog || props.dialog.display_kind === 'personal'} onClick={props.openMembers}>مدیریت اعضا</Button>
          <Typography variant="caption" color="text.secondary">{!props.dialog ? 'ارسال به شماره‌ها در دسترس است؛ برای عملیات اعضا ابتدا یک گروه یا کانال را انتخاب کنید.' : props.dialog.display_kind === 'personal' ? 'در گفتگوی شخصی، ابزار یکپارچه روی ارسال به شماره‌ها باز می‌شود.' : 'اعضا، شماره‌های جدید و دعوت شماره‌ها در تب‌های مستقل ابزار گروهی قرار دارند.'}</Typography>
        </Stack>
      </Paper> : !props.wordpressReady ? <Alert severity="info" aria-label="وردپرس آماده نیست" action={<Button color="inherit" onClick={props.openSettings}>تنظیمات</Button>}><Typography fontWeight={850}>وردپرس هنوز آماده نیست</Typography>ابتدا یک سایت و دسترسی معتبر وردپرس تعریف کنید.</Alert> : <>
        

        {editRecord && <Alert severity="warning" action={editRecord.post_url ? <Button color="inherit" size="small" onClick={() => window.eitaaDesktop.openExternal(editRecord.post_url!)}>مشاهده</Button> : undefined}><Typography fontWeight={850}>حالت ویرایش فعال است</Typography>همان Post ID {editRecord.post_id} به‌روزرسانی می‌شود؛ حذف منابع قبلی مجاز نیست و فقط می‌توان پیام تازه افزود.</Alert>}

        <Paper variant="outlined" sx={{ p: 1.5 }}><Stack spacing={1.25}>
          <Typography variant="subtitle1" fontWeight={850}>مشخصات نوشته</Typography>
          <FormControl fullWidth size="small"><InputLabel>سایت مقصد</InputLabel><Select label="سایت مقصد" value={props.siteKey} disabled={Boolean(editRecord)} onChange={e => props.setSiteKey(String(e.target.value))}>{props.sites.map(site => <MenuItem key={site.site_key} value={site.site_key}>{site.site_key} — {site.base_url}</MenuItem>)}</Select></FormControl>
          <TextField size="small" label="عنوان مطلب" value={title} onChange={e => setTitle(e.target.value)} placeholder="عنوان نوشته وردپرس" />
          <TextField size="small" multiline minRows={3} label="چکیده" value={excerpt} onChange={e => setExcerpt(e.target.value)} placeholder="Excerpt وردپرس" />
        </Stack></Paper>

        <Paper variant="outlined" sx={{ p: 1.5 }}><Stack spacing={1}>
          <Typography variant="subtitle1" fontWeight={850}>دسته‌ها <Typography component="span" variant="caption" color="text.secondary">({categoryIds.length.toLocaleString('fa-IR')} انتخاب)</Typography></Typography>
          <Stack direction="row" flexWrap="wrap" gap={0.5}>{categoryIds.length ? categoryIds.map(id => { const term = props.categories.find(item => item.id === id); return term ? <Chip key={id} label={term.name} onDelete={() => setCategoryIds(current => current.filter(item => item !== id))} /> : null }) : <Typography variant="caption" color="text.secondary">هنوز دسته‌ای انتخاب نشده است.</Typography>}</Stack>
          <Box role="tree" sx={{ maxHeight: 260, overflow: 'auto', borderTop: 1, borderColor: 'divider', pt: 0.5 }}>{categoryRows.map(({ term, depth }) => <FormControlLabel key={term.id} role="treeitem" aria-level={depth + 1} control={<Checkbox size="small" checked={categoryIds.includes(term.id)} onChange={e => setCategoryIds(current => e.target.checked ? [...current, term.id] : current.filter(id => id !== term.id))} />} label={term.name} sx={{ display: 'flex', m: 0, pl: `${Math.min(depth, 6) * 18}px`, minHeight: 34 }} />)}</Box>
        </Stack></Paper>

        <Paper variant="outlined" sx={{ p: 1.5 }}><Stack spacing={1}>
          <Typography variant="subtitle1" fontWeight={850}>کلمات کلیدی <Typography component="span" variant="caption" color="text.secondary">({tagIds.length.toLocaleString('fa-IR')} انتخاب)</Typography></Typography>
          <Stack direction="row" flexWrap="wrap" gap={0.5}>{tagIds.length ? tagIds.map(id => { const term = props.tags.find(item => item.id === id); return term ? <Chip key={id} color="secondary" label={term.name} onDelete={() => setTagIds(current => current.filter(item => item !== id))} /> : null }) : <Typography variant="caption" color="text.secondary">نام یک کلمه کلیدی را تایپ کنید.</Typography>}</Stack>
          <TextField size="small" label="نام کلمه کلیدی" value={tagSearch} onChange={e => setTagSearch(e.target.value)} onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); if (filteredTags.length) chooseTag(filteredTags[0]); else if (tagSearch.trim()) void createTag(tagSearch) } else if (e.key === 'Escape') setTagSearch('') }} role="combobox" aria-expanded={Boolean(normalizedTagSearch)} autoComplete="off" helperText="Enter نخستین پیشنهاد را انتخاب یا کلمه جدید را ایجاد می‌کند." />
          {normalizedTagSearch && <Paper variant="outlined" role="listbox" sx={{ overflow: 'hidden' }}>{filteredTags.map(term => <ButtonBase role="option" key={term.id} onMouseDown={e => e.preventDefault()} onClick={() => chooseTag(term)} sx={{ display: 'flex', width: '100%', p: 1, justifyContent: 'space-between', textAlign: 'start', '&:hover': { bgcolor: 'action.hover' } }}><Typography fontWeight={750}>{term.name}</Typography><Typography variant="caption" color="text.secondary">انتخاب موجود</Typography></ButtonBase>)}{!exactTagMatch && <ButtonBase disabled={busy} onMouseDown={e => e.preventDefault()} onClick={() => void createTag(tagSearch)} sx={{ display: 'flex', width: '100%', p: 1, justifyContent: 'space-between', textAlign: 'start', color: 'primary.main', '&:hover': { bgcolor: 'action.hover' } }}><Typography fontWeight={750}>ساخت «{tagSearch.trim()}»</Typography><Typography variant="caption">مورد جدید</Typography></ButtonBase>}{!filteredTags.length && exactTagMatch && <Typography variant="caption" color="text.secondary" sx={{ display: 'block', p: 1 }}>این کلمه قبلاً انتخاب شده است.</Typography>}</Paper>}
        </Stack></Paper>

        <Paper variant="outlined" sx={{ p: 1.5 }}><Stack spacing={1}>
          <Stack direction="row" alignItems="center" justifyContent="space-between" gap={1}><Typography variant="subtitle1" fontWeight={850}>ترتیب بدنه</Typography><Stack direction="row" gap={0.5}>{editRecord && props.selectedKeys.some(key => !editSourceKeys.includes(key)) && <Button size="small" variant="contained" onClick={appendSelectedToEdit}>افزودن {props.selectedKeys.filter(key => !editSourceKeys.includes(key)).length.toLocaleString('fa-IR')} پیام</Button>}{!editRecord && props.selectedKeys.length > 0 && <Button size="small" color="error" onClick={() => props.setSelectedKeys([])}>پاک‌کردن</Button>}</Stack></Stack>
          {!sourceKeys.length ? <Alert severity="info">در ستون پیام‌ها، پیام‌های لازم را انتخاب کنید.</Alert> : sourceKeys.map((key, index) => { const parsed = parseSourceKey(key); const message = !editRecord ? props.selectedMessages[index] : null; return <Paper key={key} draggable variant="outlined" onDragStart={e => e.dataTransfer.setData('text/plain', String(index))} onDragOver={e => e.preventDefault()} onDrop={e => { e.preventDefault(); move(Number(e.dataTransfer.getData('text/plain')), index) }} sx={{ p: 0.75, display: 'grid', gridTemplateColumns: 'auto auto minmax(0,1fr) auto', alignItems: 'center', gap: 0.75, cursor: 'grab' }}><Typography color="text.secondary">⋮⋮</Typography><Typography fontWeight={850}>#{parsed.messageId}</Typography><Typography variant="caption" noWrap>{message?.text.slice(0, 45) || message?.media?.type || `${parsed.peerType}:${parsed.peerId}`}</Typography>{!editRecord && <IconButton size="small" onClick={() => props.setSelectedKeys(props.selectedKeys.filter(item => item !== key))}><CloseRounded fontSize="small" /></IconButton>}</Paper> })}
        </Stack></Paper>

        <Paper variant="outlined" onDragOver={e => { e.preventDefault(); e.dataTransfer.dropEffect = 'copy' }} onDrop={e => { e.preventDefault(); const key = e.dataTransfer.getData('application/x-eitaa-source'); if (sourceKeys.includes(key)) setFeaturedKey(key) }} sx={{ p: 1.5, borderStyle: 'dashed' }}><Stack spacing={1}>
          <Stack direction="row" alignItems="center" justifyContent="space-between"><Typography variant="subtitle1" fontWeight={850}>تصویر شاخص</Typography>{featuredKey && <Button size="small" color="error" onClick={() => setFeaturedKey(null)}>حذف</Button>}</Stack>
          {featuredPreview ? <Box component="img" src={featuredPreview} alt="تصویر شاخص" sx={{ width: '100%', maxHeight: 260, objectFit: 'contain', borderRadius: 2, bgcolor: 'action.hover' }} /> : <Typography variant="body2" color="text.secondary">{featuredKey ? `تصویر شاخص ثبت‌شده: پیام #${parseSourceKey(featuredKey).messageId}` : 'تصویر یکی از پیام‌های انتخاب‌شده را اینجا بکشید.'}</Typography>}
          <FormControlLabel control={<Checkbox checked={includeFeatured} onChange={e => setIncludeFeatured(e.target.checked)} />} label="نمایش تصویر شاخص در بدنه" />
        </Stack></Paper>

        <Paper variant="outlined" sx={{ p: 1.5 }}><RadioGroup row value={postStatus} onChange={e => { const value = e.target.value as 'draft' | 'publish'; setPostStatus(value); if (value === 'draft') setConfirmPublish(false) }}><FormControlLabel value="draft" control={<Radio />} label="پیش‌نویس" /><FormControlLabel value="publish" control={<Radio />} label="انتشار مستقیم" /></RadioGroup>{postStatus === 'publish' && <FormControlLabel control={<Checkbox checked={confirmPublish} onChange={e => setConfirmPublish(e.target.checked)} />} label="تأیید می‌کنم نوشته بلافاصله عمومی یا به‌روزرسانی شود." />}</Paper>
        {error && <Alert severity="error">{error}</Alert>}
        {result && <Alert severity="success"><Typography fontWeight={850}>{result.outcome === 'composition_created' ? 'نوشته ایجاد شد' : result.outcome === 'composition_updated' ? 'نوشته به‌روزرسانی شد' : 'پیش‌نمایش معتبر است'}</Typography>{result.post?.id && <Typography variant="caption">Post ID: {result.post.id}</Typography>}{result.plan?.blocked_source_count > 0 && <Typography variant="caption">{Number(result.plan.blocked_source_count).toLocaleString('fa-IR')} پیام قبلاً استفاده شده است.</Typography>}</Alert>}
        <Stack direction={{ xs: 'column', sm: 'row' }} gap={1} sx={{ position: 'sticky', bottom: 0, bgcolor: 'background.default', py: 1, zIndex: 2 }}>
          {!editRecord && <Button variant="outlined" disabled={busy} onClick={() => void run('preview')}>پیش‌نمایش</Button>}
          <Button variant="contained" disabled={busy || !sourceKeys.length || (postStatus === 'publish' && !confirmPublish)} onClick={() => void run(editRecord ? 'update' : 'publish')} startIcon={busy ? <CircularProgress size={18} color="inherit" /> : undefined}>{busy ? 'در حال انجام' : editRecord ? 'به‌روزرسانی همان نوشته' : postStatus === 'publish' ? 'انتشار' : 'ساخت پیش‌نویس'}</Button>
          <Button variant="text" onClick={() => reset(true)}>فرم جدید</Button>
        </Stack>
      </>}
    </Stack>
  </Box>
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
  return <MaterialLegacyDialog close={close} maxWidth="sm"><Box component="form" aria-label="افزودن دستی گفتگو" onSubmit={submit}>
    <Paper variant="outlined" sx={{ p: { xs: 1.5, sm: 2 }, borderRadius: 3 }}><Stack spacing={1.5}>
      <Stack direction="row" alignItems="center" justifyContent="space-between"><Typography variant="h6" fontWeight={900}>افزودن دستی گفتگو</Typography><IconButton type="button" onClick={close} aria-label="بستن"><CloseRounded /></IconButton></Stack>
      <ToggleButtonGroup exclusive fullWidth size="small" value={mode} onChange={(_event, value) => value && setMode(value)} aria-label="روش افزودن گفتگو"><ToggleButton value="username">با نام کاربری</ToggleButton><ToggleButton value="peer">شناسه فنی</ToggleButton></ToggleButtonGroup>
      <FormControl fullWidth><InputLabel>نمایش در رابط</InputLabel><Select label="نمایش در رابط" value={displayKind} onChange={e => setDisplayKind(e.target.value as DisplayKind)}><MenuItem value="channel">کانال</MenuItem><MenuItem value="group">گروه</MenuItem><MenuItem value="personal">شخصی</MenuItem></Select></FormControl>
      {mode === 'username' ? <TextField label="نام کاربری" dir="ltr" value={username} onChange={e => setUsername(e.target.value)} placeholder="username یا @username" slotProps={{ htmlInput: { dir: 'ltr' } }} /> : <>
        <FormControl fullWidth><InputLabel>نوع فنی Peer</InputLabel><Select label="نوع فنی Peer" value={peerType} onChange={e => setPeerType(e.target.value as PeerType)}><MenuItem value="channel">channel</MenuItem><MenuItem value="chat">chat</MenuItem><MenuItem value="user">user</MenuItem></Select></FormControl>
        <TextField label="Peer ID" value={peerId} onChange={e => setPeerId(e.target.value)} slotProps={{ htmlInput: { dir: 'ltr', inputMode: 'numeric' } }} />
        <TextField label="Access Hash" value={accessHash} onChange={e => setAccessHash(e.target.value)} helperText="برای Peer خصوصی معمولاً لازم است" slotProps={{ htmlInput: { dir: 'ltr', inputMode: 'numeric' } }} />
        <TextField label="عنوان نمایشی" value={title} onChange={e => setTitle(e.target.value)} />
        <TextField label="نام کاربری اختیاری" value={username} onChange={e => setUsername(e.target.value)} slotProps={{ htmlInput: { dir: 'ltr' } }} />
      </>}
      <Alert severity="info">اگر سوپرگروه از نظر فنی با نوع channel برگشت، نوع فنی را channel و نمایش رابط را «گروه» انتخاب کنید.</Alert>
      {error && <Alert severity="error">{error}</Alert>}
      <Stack direction="row" justifyContent="flex-end" gap={1}><Button type="button" onClick={close}>انصراف</Button><Button type="submit" variant="contained" disabled={busy} startIcon={busy ? <CircularProgress size={18} color="inherit" /> : undefined}>{busy ? 'در حال افزودن' : 'افزودن'}</Button></Stack>
    </Stack></Paper>
  </Box></MaterialLegacyDialog>
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
  contact: {
    state: 'eitaa' | 'local' | 'none'
    is_eitaa_contact: boolean
    is_local_contact: boolean
    display_name?: string | null
    local_contact_id?: number | null
  }
}

type MemberSelection = { scope: MemberScope; memberIds: number[] }

function CommunityMembersModal({
  siteKey,
  dialog,
  dialogs,
  close,
  openBulk,
}: {
  siteKey: string
  dialog: DialogItem | null
  dialogs: DialogItem[]
  close: () => void
  openBulk: (selection: MemberSelection) => void
}) {
  const [members, setMembers] = useState<CommunityMemberItem[]>([])
  const [search, setSearch] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [sendableOnly, setSendableOnly] = useState(false)
  const [includeBots, setIncludeBots] = useState(false)
  const [selected, setSelected] = useState<number[]>([])
  const [summary, setSummary] = useState<any>(null)
  const [syncSummary, setSyncSummary] = useState<any>(null)
  const [mutationSummary, setMutationSummary] = useState<any>(null)
  const [inviteTargetPeerFile, setInviteTargetPeerFile] = useState('')
  const [nextOffset, setNextOffset] = useState<number | null>(null)
  const [listBusy, setListBusy] = useState(false)
  const [loadingMore, setLoadingMore] = useState(false)
  const [loadAllProgress, setLoadAllProgress] = useState<{ loaded: number; total: number } | null>(null)
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const [contactCategories, setContactCategories] = useState<Array<{ id: number; name: string }>>([])
  const [contactCategoryIds, setContactCategoryIds] = useState<number[]>([])
  const [contactImportJob, setContactImportJob] = useState<any>(null)
  const memberListRef = useRef<HTMLDivElement>(null)
  const memberQueryGenerationRef = useRef(0)
  const autoSyncAttemptedRef = useRef(false)
  const contactImportActive = Boolean(contactImportJob && ['queued', 'running', 'cancelling'].includes(contactImportJob.state))
  const invitationTargets = dialogs.filter(item => (
    item.display_kind !== 'personal'
    && item.peer_key !== dialog?.peer_key
  ))

  const waitTask = async (taskId: string) => {
    for (let attempt = 0; attempt < 3600; attempt += 1) {
      await waitForAdaptivePoll(attempt, { active: true })
      const response = await api<{ task: any }>('GET', query('/api/v1/background/status', { task_id: taskId }))
      if (response.task.status === 'failed') {
        const detail = response.task.error?.message || response.task.error?.error_code || response.task.error_type || 'خطای نامشخص'
        throw new Error(`عملیات اعضا متوقف شد: ${detail}`)
      }
      if (response.task.status === 'completed') return response.task.result
    }
    throw new Error('عملیات اعضا بیش از حد طول کشید؛ وضعیت آن در بخش پشتیبان حفظ شده است.')
  }

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedSearch(search.trim()), 250)
    return () => window.clearTimeout(timer)
  }, [search])

  useEffect(() => {
    setSelected([])
    setMutationSummary(null)
    setInviteTargetPeerFile('')
    autoSyncAttemptedRef.current = false
  }, [dialog?.peer_key])

  const requestMemberPage = useCallback(async (offset: number, limit: number) => {
    if (!dialog || dialog.display_kind === 'personal') return
    return api<{ page: any }>('POST', '/api/v1/community/members/list', {
      site_key: siteKey,
      peer_file: dialog.peer_file,
      text: debouncedSearch || undefined,
      sendable_only: sendableOnly,
      include_bots: includeBots,
      offset,
      limit,
    })
  }, [dialog?.peer_key, siteKey, debouncedSearch, sendableOnly, includeBots])

  const mergeMembers = (current: CommunityMemberItem[], incoming: CommunityMemberItem[]) => {
    const merged = new Map(current.map(item => [item.user.peer.id, item]))
    for (const item of incoming) merged.set(item.user.peer.id, item)
    return [...merged.values()]
  }

  const loadMemberPage = useCallback(async (offset: number, append: boolean) => {
    const generation = append ? memberQueryGenerationRef.current : ++memberQueryGenerationRef.current
    if (append) setLoadingMore(true)
    else { setListBusy(true); setError(''); setLoadAllProgress(null) }
    try {
      const response = await requestMemberPage(offset, 200)
      if (!response || generation !== memberQueryGenerationRef.current) return
      const incoming = (response.page.members || []) as CommunityMemberItem[]
      setMembers(current => append ? mergeMembers(current, incoming) : incoming)
      setSummary(response.page)
      setNextOffset(response.page.next_offset ?? null)
    } catch (e) {
      if (generation === memberQueryGenerationRef.current) {
        setError(e instanceof Error ? e.message : 'خواندن اعضای محلی ناموفق بود.')
      }
    } finally {
      if (generation === memberQueryGenerationRef.current) {
        setListBusy(false)
        setLoadingMore(false)
      }
    }
  }, [requestMemberPage])

  useEffect(() => {
    setMembers([])
    setSummary(null)
    setNextOffset(null)
    void loadMemberPage(0, false)
  }, [loadMemberPage])

  const loadAllMembers = async () => {
    const generation = ++memberQueryGenerationRef.current
    setBusy('load-all'); setError(''); setLoadAllProgress({ loaded: 0, total: 0 })
    try {
      let offset = 0
      let collected: CommunityMemberItem[] = []
      while (true) {
        const response = await requestMemberPage(offset, 1_000)
        if (!response || generation !== memberQueryGenerationRef.current) return
        collected = mergeMembers(collected, response.page.members || [])
        setMembers(collected)
        setSummary(response.page)
        setLoadAllProgress({
          loaded: collected.length,
          total: Number(response.page.total_count || collected.length),
        })
        const following = response.page.next_offset
        if (following === null || following === undefined) {
          setNextOffset(null)
          break
        }
        offset = Number(following)
        setNextOffset(offset)
        await new Promise(resolve => window.setTimeout(resolve, 0))
      }
      toast.success(`${collected.length.toLocaleString('fa-IR')} عضو مطابق فیلتر در نمای مجازی آماده شد.`)
    } catch (e) { setError(e instanceof Error ? e.message : 'بارگذاری همه اعضا ناموفق بود.') }
    finally { setBusy(''); setLoadAllProgress(null) }
  }

  useEffect(() => {
    void api<{ categories: Array<{ id: number; name: string }> }>('GET', '/api/v1/contacts/categories')
      .then(response => setContactCategories(response.categories))
      .catch(() => undefined)
  }, [])
  useEffect(() => {
    if (!contactImportActive) return
    let cancelled = false
    const poll = async () => {
      for (let attempt = 0; !cancelled; attempt += 1) {
        await waitForAdaptivePoll(attempt, { active: true })
        if (cancelled) return
        try {
          const response = await api<{ job: any }>('GET', query('/api/v1/contacts/import/status', { job_id: contactImportJob.job_id }))
          if (cancelled) return
          setContactImportJob(response.job)
          if (response.job.state === 'completed') {
            const progress = response.job.progress || {}
            toast.success(`${Number(progress.imported || 0).toLocaleString('fa-IR')} مخاطب جدید و ${Number(progress.updated || 0).toLocaleString('fa-IR')} مخاطب به‌روزشده در دفترچه ثبت شد.`)
            void loadMemberPage(0, false)
            return
          } else if (response.job.state === 'failed') {
            setError(response.job.error?.message || 'ورود اعضا به دفترچه ناموفق بود.')
            return
          } else if (response.job.state === 'cancelled') {
            return
          }
        } catch {
          if (cancelled) return
        }
      }
    }
    void poll()
    return () => { cancelled = true }
  }, [contactImportActive, contactImportJob?.job_id, loadMemberPage])
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => { if (event.key === 'Escape' && !busy && !contactImportActive) close() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [busy, close, contactImportActive])

  const syncRemote = async () => {
    if (!dialog || dialog.display_kind === 'personal') return
    setBusy('sync'); setError(''); setSyncSummary(null)
    try {
      const expectedTotal = Number(dialog.participants_count || 0)
      const maxPages = expectedTotal
        ? Math.max(20, Math.min(10_000, Math.ceil(expectedTotal / 25) + 20))
        : 200
      const started = await api<{ task: { task_id: string } }>('POST', '/api/v1/community/members/sync/start', {
        site_key: siteKey,
        peer_file: dialog.peer_file,
        page_size: 200,
        max_pages: maxPages,
        expected_total: expectedTotal || undefined,
      })
      const completed = await waitTask(started.task.task_id)
      const nextSummary = completed?.sync || completed
      setSyncSummary(nextSummary)
      await loadMemberPage(0, false)
      if (nextSummary?.complete_snapshot) {
        toast.success('فهرست اعضای گفتگو به‌طور کامل به‌روزرسانی شد.')
      } else {
        const fetched = Number(nextSummary?.fetched || 0).toLocaleString('fa-IR')
        const expected = Number(nextSummary?.expected_total || expectedTotal || 0).toLocaleString('fa-IR')
        toast.warning(`ایتا فقط ${fetched} عضو از ${expected} عضو گزارش‌شده را برگرداند؛ فهرست محلی ناقص است.`)
      }
    } catch (e) { setError(e instanceof Error ? e.message : 'همگام‌سازی اعضا ناموفق بود.') }
    finally { setBusy('') }
  }

  const sendableMembers = members.filter(item => item.sendable)
  const allLoadedSelected = sendableMembers.length > 0 && sendableMembers.every(item => selected.includes(item.user.peer.id))
  const toggleAll = () => setSelected(current => {
    const loadedIds = new Set(sendableMembers.map(item => item.user.peer.id))
    return allLoadedSelected
      ? current.filter(id => !loadedIds.has(id))
      : [...new Set([...current, ...loadedIds])]
  })
  const contactCounts = members.reduce((counts, item) => {
    counts[item.contact?.state || 'none'] += 1
    return counts
  }, { eitaa: 0, local: 0, none: 0 })
  const expectedMemberCount = Number(dialog?.participants_count || 0)
  const snapshotMemberCount = Number(summary?.snapshot_total_count ?? summary?.total_count ?? 0)
  const snapshotIncomplete = Boolean(
    expectedMemberCount
    && summary
    && snapshotMemberCount < expectedMemberCount
  )

  useEffect(() => {
    if (
      snapshotIncomplete
      && !autoSyncAttemptedRef.current
      && !busy
      && !listBusy
      && dialog?.peer_key
    ) {
      autoSyncAttemptedRef.current = true
      void syncRemote()
    }
  }, [snapshotIncomplete, dialog?.peer_key, busy, listBusy])

  const memberVirtualizer = useVirtualizer({
    count: members.length,
    getScrollElement: () => memberListRef.current,
    estimateSize: () => 72,
    overscan: 10,
  })
  const virtualMembers = memberVirtualizer.getVirtualItems()
  const lastVirtualIndex = virtualMembers.at(-1)?.index ?? -1
  useEffect(() => {
    if (
      lastVirtualIndex >= members.length - 20
      && nextOffset !== null
      && !loadingMore
      && !listBusy
      && !busy
    ) void loadMemberPage(nextOffset, true)
  }, [lastVirtualIndex, members.length, nextOffset, loadingMore, listBusy, busy, loadMemberPage])

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

  const runMemberMutation = async (action: 'remove' | 'invite', allMembers: boolean) => {
    if (!dialog || dialog.display_kind === 'personal') return
    if (!allMembers && !selected.length) { setError('ابتدا دست‌کم یک عضو را انتخاب کنید.'); return }
    const target = invitationTargets.find(item => item.peer_file === inviteTargetPeerFile)
    if (action === 'invite' && !target) { setError('گفتگوی مقصد دعوت را انتخاب کنید.'); return }
    const scopeText = allMembers ? 'همه اعضای قابل دعوت Snapshot کامل' : `${selected.length.toLocaleString('fa-IR')} عضو انتخاب‌شده`
    const question = action === 'remove'
      ? `آیا ${scopeText} از «${titleFor(dialog)}» حذف شوند؟ این تغییر روی ایتا انجام می‌شود.`
      : `آیا ${scopeText} به «${titleFor(target || null)}» دعوت شوند؟ محدودیت‌ها و حریم خصوصی ایتا اعمال خواهد شد.`
    if (!confirm(question)) return
    setBusy(action); setError(''); setMutationSummary(null)
    try {
      const path = action === 'remove'
        ? '/api/v1/community/members/remove/start'
        : '/api/v1/community/members/invite/start'
      const started = await api<{ task: { task_id: string } }>('POST', path, {
        site_key: siteKey,
        peer_file: action === 'remove' ? dialog.peer_file : undefined,
        source_peer_file: action === 'invite' ? dialog.peer_file : undefined,
        target_peer_file: action === 'invite' ? target?.peer_file : undefined,
        member_ids: allMembers ? undefined : selected,
        all_members: allMembers,
        include_bots: includeBots,
        delay_seconds: 2,
        confirm: true,
      })
      const completed = await waitTask(started.task.task_id)
      const report = completed?.report || completed
      setMutationSummary(report)
      if (action === 'remove') {
        setSelected([])
        await loadMemberPage(0, false)
      }
      if (report?.stopped || Number(report?.failed || 0)) {
        toast.warning(`عملیات پایان یافت: ${Number(report?.succeeded || 0).toLocaleString('fa-IR')} موفق و ${Number(report?.failed || 0).toLocaleString('fa-IR')} ناموفق.`)
      } else {
        toast.success(`${Number(report?.succeeded || 0).toLocaleString('fa-IR')} عملیات عضویت با موفقیت ثبت شد.`)
      }
    } catch (e) { setError(e instanceof Error ? e.message : 'عملیات عضویت ناموفق بود.') }
    finally { setBusy('') }
  }

  return <MaterialLegacyDialog close={close} locked={Boolean(busy) || contactImportActive} maxWidth="lg">
    <Paper component="section" variant="outlined" aria-label="مدیریت اعضای گفتگو" sx={{ p: { xs: 1.25, sm: 2 }, borderRadius: 3 }}><Stack spacing={1.5}>
      <Stack direction="row" alignItems="flex-start" justifyContent="space-between" gap={1}><Box><Typography variant="h6" fontWeight={900}>مدیریت اعضای گفتگو</Typography><Typography variant="caption" color="text.secondary">{titleFor(dialog)} — Snapshot محلی و بدون نمایش Access Hash</Typography></Box><IconButton disabled={Boolean(busy)} onClick={close} aria-label="بستن"><CloseRounded /></IconButton></Stack>
      {!dialog || dialog.display_kind === 'personal' ? <Alert severity="error">برای مدیریت اعضا یک گروه یا کانال را انتخاب کنید.</Alert> : <>
        <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: 'minmax(220px,1fr) auto auto', md: 'minmax(240px,1fr) auto auto auto auto auto' }, gap: 1, alignItems: 'center' }}>
          <TextField size="small" value={search} onChange={event => setSearch(event.target.value)} label="جست‌وجوی نام عضو" />
          <FormControlLabel control={<Checkbox checked={sendableOnly} onChange={event => setSendableOnly(event.target.checked)} />} label="فقط قابل ارسال" />
          <FormControlLabel control={<Checkbox checked={includeBots} onChange={event => setIncludeBots(event.target.checked)} />} label="شامل ربات‌ها" />
          <Button variant="outlined" disabled={Boolean(busy) || listBusy} onClick={() => void loadMemberPage(0, false)} startIcon={listBusy ? <CircularProgress size={16} /> : undefined}>بازخوانی محلی</Button>
          <Button variant="outlined" disabled={Boolean(busy) || listBusy || nextOffset === null} onClick={() => void loadAllMembers()} startIcon={busy === 'load-all' ? <CircularProgress size={16} /> : undefined}>بارگذاری همه</Button>
          <Button variant="contained" disabled={Boolean(busy)} onClick={() => void syncRemote()} startIcon={busy === 'sync' ? <CircularProgress size={16} color="inherit" /> : undefined}>همگام‌سازی از ایتا</Button>
        </Box>
        <Stack direction="row" flexWrap="wrap" gap={0.75}><Chip label={`بارگذاری‌شده: ${members.length.toLocaleString('fa-IR')}`} /><Chip label={`کل نتیجه: ${Number(summary?.total_count || members.length).toLocaleString('fa-IR')}`} /><Chip color="success" label={`قابل ارسال: ${sendableMembers.length.toLocaleString('fa-IR')}`} /><Chip color="primary" label={`انتخاب: ${selected.length.toLocaleString('fa-IR')}`} /><Chip label={`مخاطب ایتا: ${contactCounts.eitaa.toLocaleString('fa-IR')}`} /><Chip label={`دفترچه محلی: ${contactCounts.local.toLocaleString('fa-IR')}`} /><Chip label={`غیرمخاطب: ${contactCounts.none.toLocaleString('fa-IR')}`} /></Stack>
        {snapshotIncomplete && <Alert severity="warning">فهرست محلی فعلاً {snapshotMemberCount.toLocaleString('fa-IR')} عضو از {expectedMemberCount.toLocaleString('fa-IR')} عضو گزارش‌شده را دارد. {busy === 'sync' ? 'برنامه در حال تکمیل خودکار آن از ایتاست.' : 'برای تکمیل فهرست، همگام‌سازی از ایتا را دوباره اجرا کنید.'}</Alert>}
        {loadAllProgress && <Paper variant="outlined" sx={{ p: 1.25 }}><Stack spacing={0.75}><Stack direction="row" justifyContent="space-between"><Typography fontWeight={750}>در حال آماده‌سازی نمای کامل</Typography><Typography variant="caption">{loadAllProgress.loaded.toLocaleString('fa-IR')} / {loadAllProgress.total.toLocaleString('fa-IR')}</Typography></Stack><LinearProgress variant="determinate" value={Math.min(100, loadAllProgress.loaded / Math.max(1, loadAllProgress.total) * 100)} /></Stack></Paper>}
        {syncSummary && <Alert severity={syncSummary.complete_snapshot ? 'success' : 'warning'}>دریافت‌شده: {Number(syncSummary.fetched || 0).toLocaleString('fa-IR')} — جدید: {Number(syncSummary.inserted || 0).toLocaleString('fa-IR')} — به‌روزشده: {Number(syncSummary.updated || 0).toLocaleString('fa-IR')} — {syncSummary.complete_snapshot ? 'فهرست کامل است.' : `${Number(syncSummary.missing_count || 0).toLocaleString('fa-IR')} عضو هنوز دریافت نشده است.`}</Alert>}
        <Paper variant="outlined" sx={{ p: 1.25 }}><Stack direction={{ xs: 'column', md: 'row' }} alignItems={{ md: 'center' }} gap={1}><FormControlLabel sx={{ flex: 1 }} control={<Checkbox checked={allLoadedSelected} onChange={toggleAll} />} label="انتخاب همه اعضای قابل ارسالِ بارگذاری‌شده" /><Button variant="contained" disabled={!selected.length} onClick={() => openBulk({ scope: 'selected', memberIds: selected })}>ارسال به {selected.length.toLocaleString('fa-IR')} عضو انتخاب‌شده</Button><Button variant="outlined" disabled={!Number(summary?.total_count || 0)} onClick={() => openBulk({ scope: 'all_snapshot', memberIds: [] })}>ارسال به همه Snapshot</Button></Stack></Paper>
        <Paper variant="outlined" sx={{ p: 1.5 }}><Stack spacing={1}><Box><Typography fontWeight={850}>مدیریت عضویت</Typography><Typography variant="caption" color="text.secondary">حذف برای منتخب‌هاست؛ دعوت برای منتخب‌ها یا Snapshot کامل و با تأیید صریح انجام می‌شود.</Typography></Box><FormControl fullWidth size="small"><InputLabel>گفتگوی مقصد دعوت</InputLabel><Select label="گفتگوی مقصد دعوت" value={inviteTargetPeerFile} onChange={event => setInviteTargetPeerFile(String(event.target.value))}><MenuItem value="">انتخاب نشده</MenuItem>{invitationTargets.map(item => <MenuItem key={item.peer_key} value={item.peer_file}>{titleFor(item)}</MenuItem>)}</Select></FormControl><Stack direction={{ xs: 'column', sm: 'row' }} gap={1}><Button variant="outlined" disabled={!selected.length || Boolean(busy)} onClick={() => void runMemberMutation('invite', false)}>دعوت منتخب‌ها</Button><Button variant="outlined" disabled={!inviteTargetPeerFile || !Number(summary?.total_count || 0) || Boolean(busy)} onClick={() => void runMemberMutation('invite', true)}>دعوت همه Snapshot</Button><Button color="error" disabled={!selected.length || Boolean(busy)} onClick={() => void runMemberMutation('remove', false)}>حذف منتخب‌ها</Button></Stack></Stack></Paper>
        {mutationSummary && <Alert severity={Number(mutationSummary.failed || 0) || mutationSummary.stopped ? 'warning' : 'success'}><Typography fontWeight={850}>{mutationSummary.action === 'remove' ? 'گزارش حذف اعضا' : 'گزارش دعوت اعضا'} — {mutationSummary.stopped ? 'متوقف‌شده' : 'پایان‌یافته'}</Typography><Stack direction="row" flexWrap="wrap" gap={0.5} mt={0.5}><Chip size="small" color="success" label={`موفق: ${Number(mutationSummary.succeeded || 0).toLocaleString('fa-IR')}`} /><Chip size="small" color="error" label={`ناموفق: ${Number(mutationSummary.failed || 0).toLocaleString('fa-IR')}`} /><Chip size="small" label={`ردشده: ${Number(mutationSummary.skipped || 0).toLocaleString('fa-IR')}`} /><Chip size="small" label={`پردازش: ${Number(mutationSummary.processed || 0).toLocaleString('fa-IR')}`} /></Stack>{mutationSummary.stop_reason && <Typography variant="caption" component="div" dir="ltr" mt={0.5}>{mutationSummary.stop_reason}</Typography>}</Alert>}
        <Paper variant="outlined" sx={{ p: 1.5 }}><Stack spacing={1}><Box><Typography fontWeight={850}>افزودن به دفترچهٔ محلی</Typography><Typography variant="caption" color="text.secondary">داده معتبر از Snapshot محلی خوانده می‌شود و Access Hash نمایش داده نمی‌شود.</Typography></Box>{contactCategories.length > 0 && <Box sx={{ maxHeight: 150, overflow: 'auto', display: 'grid', gridTemplateColumns: { xs: '1fr', sm: 'repeat(2,1fr)', md: 'repeat(3,1fr)' } }}>{contactCategories.map(category => <FormControlLabel key={category.id} control={<Checkbox size="small" checked={contactCategoryIds.includes(category.id)} onChange={event => setContactCategoryIds(current => event.target.checked ? [...current, category.id] : current.filter(id => id !== category.id))} />} label={category.name} />)}</Box>}<Stack direction={{ xs: 'column', sm: 'row' }} gap={1}><Button variant="contained" disabled={!selected.length || contactImportActive || Boolean(busy)} onClick={() => void startContactImport(selected)}>افزودن {selected.length.toLocaleString('fa-IR')} منتخب</Button><Button variant="outlined" disabled={!members.length || contactImportActive || Boolean(busy)} onClick={() => void startContactImport()}>افزودن کل نمایه محلی</Button>{contactImportActive && <Button color="error" disabled={contactImportJob.state === 'cancelling'} onClick={() => void api<{ job: any }>('POST', '/api/v1/contacts/import/cancel', { job_id: contactImportJob.job_id }).then(response => setContactImportJob(response.job))}>لغو ایمن</Button>}</Stack>{contactImportJob && <Stack spacing={0.75}><Stack direction="row" justifyContent="space-between"><Typography fontWeight={750}>{contactImportJob.state === 'completed' ? 'ورود کامل شد' : contactImportJob.state === 'cancelled' ? 'ورود لغو شد' : contactImportJob.state === 'failed' ? 'ورود ناموفق بود' : 'در حال ورود محلی'}</Typography><Typography variant="caption">{Number(contactImportJob.progress?.processed || 0).toLocaleString('fa-IR')} / {Number(contactImportJob.progress?.total || 0).toLocaleString('fa-IR')}</Typography></Stack><LinearProgress variant="determinate" value={Math.min(100, Number(contactImportJob.progress?.processed || 0) / Math.max(1, Number(contactImportJob.progress?.total || 1)) * 100)} /><Typography variant="caption" color="text.secondary">جدید: {Number(contactImportJob.progress?.imported || 0).toLocaleString('fa-IR')} · به‌روزشده: {Number(contactImportJob.progress?.updated || 0).toLocaleString('fa-IR')} · ردشده/خطا: {(Number(contactImportJob.progress?.skipped || 0) + Number(contactImportJob.progress?.errors || 0)).toLocaleString('fa-IR')}</Typography></Stack>}</Stack></Paper>
        <Paper variant="outlined" role="list" ref={memberListRef} sx={{ position: 'relative', height: 'min(48dvh, 520px)', minHeight: 260, overflow: 'auto' }}>
          <Box sx={{ height: memberVirtualizer.getTotalSize(), position: 'relative' }}>{virtualMembers.map(virtualRow => { const item = members[virtualRow.index]; const id = item.user.peer.id; const checked = selected.includes(id); const contactName = item.contact?.display_name?.trim(); return <Paper component="label" square elevation={0} key={id} data-index={virtualRow.index} ref={memberVirtualizer.measureElement} role="listitem" sx={{ position: 'absolute', top: 0, insetInline: 0, transform: `translateY(${virtualRow.start}px)`, minHeight: 72, p: 1, display: 'grid', gridTemplateColumns: 'auto auto minmax(0,1fr)', gridTemplateRows: 'auto auto', alignItems: 'center', columnGap: 1, opacity: item.sendable ? 1 : 0.58, borderBottom: 1, borderColor: 'divider', cursor: item.sendable ? 'pointer' : 'default' }}><Checkbox disabled={!item.sendable} checked={checked} onChange={() => setSelected(current => current.includes(id) ? current.filter(value => value !== id) : [...current, id])} sx={{ gridRow: '1 / -1' }} /><Avatar sx={{ gridRow: '1 / -1', width: 38, height: 38 }}>{initials(contactName || item.user.display_name)}</Avatar><Box sx={{ minWidth: 0 }}><Typography fontWeight={750} noWrap>{contactName || item.user.display_name}</Typography>{contactName && contactName !== item.user.display_name && <Typography variant="caption" color="text.secondary" noWrap>نام ایتا: {item.user.display_name}</Typography>}<Typography variant="caption" color="text.secondary" display="block" noWrap>{item.user.phone || `User ID: ${id}`}</Typography></Box><Stack direction="row" flexWrap="wrap" gap={0.5} sx={{ gridColumn: 3 }}><Chip size="small" label={item.contact?.state === 'eitaa' ? 'مخاطب ایتا' : item.contact?.state === 'local' ? 'دفترچه محلی' : 'غیرمخاطب'} /><Chip size="small" label={item.role} /><Chip size="small" color={item.sendable ? 'success' : 'default'} label={item.sendable ? 'قابل ارسال' : item.user.is_deleted ? 'حذف‌شده' : 'بدون Access Hash'} /></Stack></Paper> })}</Box>
          {loadingMore && <Stack direction="row" justifyContent="center" alignItems="center" gap={1} sx={{ position: 'sticky', bottom: 8 }}><CircularProgress size={18} /><Typography variant="caption">دریافت صفحهٔ بعد</Typography></Stack>}
          {!members.length && !busy && <Typography color="text.secondary" textAlign="center" sx={{ p: 4 }}>عضوی در نمایه محلی پیدا نشد. همگام‌سازی از ایتا را اجرا کنید.</Typography>}
        </Paper>
      </>}
      {error && <Alert severity="error">{error}</Alert>}
      <Stack direction="row" justifyContent="flex-end"><Button disabled={Boolean(busy) || contactImportActive} onClick={close}>بستن</Button></Stack>
    </Stack></Paper>
  </MaterialLegacyDialog>
}

function BulkOperationsModal({ siteKey, dialog, initialMode, initialMemberIds, initialMemberScope, initialNumbers, close }: { siteKey: string; dialog: DialogItem | null; initialMode: BulkMode; initialMemberIds: number[]; initialMemberScope: MemberScope; initialNumbers: string[]; close: () => void }) {
  const [mode, setMode] = useState<BulkMode>(initialMode)
  const [memberIds] = useState<number[]>(initialMemberIds)
  const [memberScope] = useState<MemberScope>(initialMemberScope)
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
      await waitForAdaptivePoll(attempt, { active: true })
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
        if (memberScope === 'selected' && !memberIds.length) throw new Error('هیچ عضو انتخاب‌شده‌ای به فرم منتقل نشده است.')
        const started = await api<{ task: { task_id: string } }>('POST', '/api/v1/community/members/sync/start', { site_key: siteKey, peer_file: dialog.peer_file, page_size: 200, max_pages: 10_000, expected_total: dialog.participants_count || undefined })
        const completed = await waitTask(started.task.task_id)
        const sync = completed?.sync || completed
        if (memberScope === 'all_snapshot' && sync && sync.complete_snapshot === false) {
          throw new Error('Snapshot اعضا کامل نیست؛ برای جلوگیری از ارسال ناقص، عملیات «همه اعضا» متوقف شد.')
        }
        const response = await api<{ preview: any }>('POST', '/api/v1/community/bulk/preview', { site_key: siteKey, peer_file: dialog.peer_file, include_bots: false, member_scope: memberScope, member_ids: memberScope === 'selected' ? memberIds : undefined, test_limit: testLimit ? Number(testLimit) : undefined })
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
        if (!preview) throw new Error('پیش‌نمایش گیرندگان را دوباره آماده کنید.')
        created = await api('POST', '/api/v1/community/bulk/create', { site_key: siteKey, peer_file: dialog.peer_file, include_bots: false, member_scope: memberScope, member_ids: memberScope === 'selected' ? memberIds : undefined, ...messagePayload() })
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
    <Paper component="section" variant="outlined" aria-label="عملیات گروهی" sx={{ p: { xs: 1.25, sm: 2 }, borderRadius: 3 }}><Stack spacing={1.5}>
      <Stack direction="row" alignItems="flex-start" justifyContent="space-between" gap={1}><Box><Typography variant="h6" fontWeight={900}>ارسال و دعوت گروهی</Typography><Typography variant="caption" color="text.secondary">همه عملیات با پیش‌نمایش، تأیید و گزارش پایدار انجام می‌شوند.</Typography></Box><IconButton disabled={Boolean(busy)} onClick={close} aria-label="بستن"><CloseRounded /></IconButton></Stack>
      <ToggleButtonGroup exclusive fullWidth size="small" value={mode} onChange={(_event, value: BulkMode | null) => { if (!value) return; setMode(value); setPreview(null); setResult(null); setProgress(null); setFailures([]); setConfirmed(false) }} aria-label="نوع عملیات گروهی"><ToggleButton value="members">اعضای گفتگو</ToggleButton><ToggleButton value="numbers">شماره‌های جدید</ToggleButton><ToggleButton value="invite">دعوت شماره‌ها</ToggleButton></ToggleButtonGroup>
      <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: mode === 'invite' ? '1fr' : 'minmax(0,1fr) minmax(0,1fr)' }, gap: 1.5 }}>
        <Paper variant="outlined" aria-label="گیرندگان عملیات گروهی" sx={{ p: 1.5 }}><Stack spacing={1.25}><Typography fontWeight={850}>گیرندگان</Typography>
          {mode === 'members' ? <Alert severity="info">مقصد: <strong>{titleFor(dialog)}</strong><br />{memberScope === 'selected' ? `${memberIds.length.toLocaleString('fa-IR')} عضو انتخاب‌شده از مدیریت اعضا` : 'دامنه: همه اعضای قابل ارسال از فهرست کامل.'}</Alert> : <>
            {mode === 'invite' && <Alert severity="warning"><Typography fontWeight={850}>دعوت مستقیم به {titleFor(dialog)}</Typography>این عملیات صرفاً لینک دعوت ارسال نمی‌کند؛ شماره‌ها شناسایی و حساب‌ها مستقیماً دعوت می‌شوند. دسترسی افزودن عضو، حریم خصوصی و محدودیت‌های ایتا اعمال می‌شود.</Alert>}
            {mode === 'numbers' && initialNumbers.length > 0 && <Alert severity="info">{initialNumbers.length.toLocaleString('fa-IR')} گیرنده از دفترچه منتقل شده است؛ پیش‌نمایش و تأیید همچنان الزامی است.</Alert>}
            <TextField size="small" label="نام فهرست" value={listName} onChange={e => setListName(e.target.value)} />
            <TextField multiline minRows={6} label="شماره‌ها؛ هر شماره در یک خط" value={numbers} onChange={e => { setNumbers(e.target.value); setListId('') }} placeholder="+98912..." slotProps={{ htmlInput: { dir: 'ltr' } }} />
            <Button variant="outlined" onClick={() => void choosePhoneFile()}>انتخاب TXT/CSV</Button>
            {sourceFile && <Typography variant="caption" dir="ltr" sx={{ overflowWrap: 'anywhere' }}>{sourceFile}</Typography>}
          </>}
          <TextField size="small" type="number" label="محدودیت آزمایشی" value={testLimit} onChange={e => setTestLimit(e.target.value)} placeholder="خالی = همه" slotProps={{ htmlInput: { min: 1 } }} />
          <TextField size="small" type="number" label="فاصله بین عملیات (ثانیه)" value={delay} onChange={e => setDelay(e.target.value)} slotProps={{ htmlInput: { min: 0, step: 0.5 } }} />
        </Stack></Paper>
        {mode !== 'invite' && <Paper variant="outlined" aria-label="پیام عملیات گروهی" sx={{ p: 1.5 }}><Stack spacing={1.25}><Typography fontWeight={850}>پیام</Typography>
          <FormControl fullWidth size="small"><InputLabel>نوع پیام</InputLabel><Select label="نوع پیام" value={kind} onChange={e => { setKind(e.target.value as 'text' | 'photo' | 'file'); setFileInfo(null); setPreview(null); setConfirmed(false) }}><MenuItem value="text">متن</MenuItem><MenuItem value="photo">تصویر</MenuItem><MenuItem value="file">فایل</MenuItem></Select></FormControl>
          {kind === 'text' ? <TextField multiline minRows={10} value={text} onChange={e => setText(e.target.value)} label="متن پیام" /> : <>
            <Button variant="outlined" onClick={() => void chooseMedia()}>انتخاب فایل</Button>
            {filePath && <Typography variant="caption" dir="ltr" sx={{ overflowWrap: 'anywhere' }}>{filePath}</Typography>}
            {fileInfo && <Alert severity="info" aria-label="نتیجه پیش‌بررسی فایل"><Typography fontWeight={750}>{fileInfo.name}</Typography>{(fileInfo.size_bytes / 1024 / 1024).toLocaleString('fa-IR', { maximumFractionDigits: 2 })} مگابایت · <Box component="span" dir="ltr">{fileInfo.mime_type}</Box></Alert>}
            <TextField multiline minRows={5} value={caption} onChange={e => setCaption(e.target.value)} label="کپشن اختیاری" />
          </>}
        </Stack></Paper>}
      </Box>
      <Alert severity={preview ? 'success' : 'info'}>{!preview ? 'ابتدا آماده‌سازی و پیش‌نمایش را اجرا کنید.' : <><Typography fontWeight={850}>{Number(selectedCount).toLocaleString('fa-IR')} گیرنده انتخاب شده</Typography>واجد شرایط: {Number(preview.eligible_count ?? selectedCount).toLocaleString('fa-IR')} — حذف‌شده/نامعتبر: {Number(preview.skipped_unsendable ?? preview.unresolved_count ?? 0).toLocaleString('fa-IR')}</>}</Alert>
      {progress?.job && <Paper variant="outlined" aria-label="پیشرفت عملیات گروهی" data-status={progress.job.status} sx={{ p: 1.5 }}><Stack spacing={1}><Stack direction="row" justifyContent="space-between" gap={1}><Typography fontWeight={850}>وضعیت وظیفه: {progress.job.status}</Typography><Typography variant="caption" dir="ltr" sx={{ overflowWrap: 'anywhere' }}>{progress.job.id}</Typography></Stack><Stack direction="row" flexWrap="wrap" gap={0.5}><Chip color="success" label={`موفق: ${Number(progress.job.sent_count || 0).toLocaleString('fa-IR')}`} /><Chip color="error" label={`ناموفق: ${Number(progress.job.failed_count || 0).toLocaleString('fa-IR')}`} /><Chip label={`ردشده: ${Number(progress.job.skipped_count || 0).toLocaleString('fa-IR')}`} /><Chip label={`در انتظار: ${Number(progress.pending || 0).toLocaleString('fa-IR')}`} /></Stack>{progress.job.stop_reason && <Typography variant="caption">علت توقف: <Box component="span" dir="ltr">{progress.job.stop_reason}</Box></Typography>}<Stack direction={{ xs: 'column', sm: 'row' }} gap={1}>{['running', 'queued'].includes(progress.job.status) && <Button variant="outlined" disabled={Boolean(busy)} onClick={() => void controlJob('pause')}>توقف موقت</Button>}{['paused', 'blocked', 'failed'].includes(progress.job.status) && <Button variant="contained" disabled={Boolean(busy)} onClick={() => void controlJob('resume')}>ادامه گیرندگان باقی‌مانده</Button>}{!['completed', 'cancelled'].includes(progress.job.status) && <Button color="error" disabled={Boolean(busy)} onClick={() => void controlJob('cancel')}>لغو وظیفه</Button>}</Stack></Stack></Paper>}
      {preview && <FormControlLabel control={<Checkbox checked={confirmed} onChange={e => setConfirmed(e.target.checked)} />} label="گیرندگان، متن یا فایل و محدودیت آزمایشی را بررسی کردم و اجرای عملیات را تأیید می‌کنم." />}
      {error && <Alert severity="error">{error}</Alert>}
      {failures.length > 0 && <Alert severity="error" aria-label="خطاهای گیرندگان"><Typography fontWeight={850}>{failures.length.toLocaleString('fa-IR')} خطای گیرنده ثبت شده است</Typography><Stack spacing={0.5} mt={1}>{failures.slice(0, 12).map((item, index) => <Paper variant="outlined" key={`${item.user?.peer?.id || index}:${item.error_code || item.error_type || index}`} sx={{ p: 0.75, display: 'flex', justifyContent: 'space-between', gap: 1 }}><Typography variant="caption" fontWeight={750}>{item.user?.display_name || item.user?.first_name || `کاربر ${item.user?.peer?.id || '—'}`}</Typography><Typography component="code" variant="caption" dir="ltr">{item.error_code || item.error_type || 'UNKNOWN_ERROR'}</Typography></Paper>)}</Stack>{failures.length > 12 && <Typography variant="caption">فقط ۱۲ مورد نخست نمایش داده شده؛ گزارش کامل در هسته باقی مانده است.</Typography>}</Alert>}
      {result && !failures.length && <Alert severity="success"><Typography fontWeight={850}>عملیات ثبت و پایان یافت</Typography><Typography variant="caption" display="block">وظیفه ID: {job?.id || result?.job_id || '—'}</Typography><Typography variant="caption">گزارش کامل پایدار است و امکان ادامه یا بررسی دارد.</Typography></Alert>}
      <Stack direction={{ xs: 'column-reverse', sm: 'row' }} justifyContent="flex-end" gap={1}><Button disabled={Boolean(busy)} onClick={close}>بستن</Button><Button variant="outlined" disabled={Boolean(busy)} onClick={() => void prepare()} startIcon={busy === 'prepare' ? <CircularProgress size={18} /> : undefined}>آماده‌سازی و پیش‌نمایش</Button><Button variant="contained" disabled={Boolean(busy) || !preview || !confirmed || (mode !== 'invite' && kind === 'text' && !text.trim()) || (mode !== 'invite' && kind !== 'text' && !filePath)} onClick={() => void execute()} startIcon={busy === 'run' ? <CircularProgress size={18} color="inherit" /> : undefined}>{busy === 'run' ? 'در حال اجرا' : mode === 'invite' ? 'شروع دعوت' : 'شروع ارسال'}</Button></Stack>
    </Stack></Paper>
  </MaterialLegacyDialog>
}
