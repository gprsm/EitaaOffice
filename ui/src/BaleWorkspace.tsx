import { useEffect, useMemo, useRef, useState } from 'react'
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Paper,
  Stack,
  TextField,
  Typography,
  useMediaQuery,
  useTheme,
} from '@mui/material'
import { api } from './lib/api'
import { AddMessengerAccountButton, MessengerAccountManagementPanel, MessengerAccountMenuControl, useMessengerAccounts } from './MessengerAccountGate'
import { AppUserLogoutButton, useAppUser } from './AppUserGate'
import { AccessManagementPanel } from './AccessManagementPanel'
import { ServiceAccountSettingsPanel } from './ServiceAccountSettingsPanel'
import { WorkspaceNavigation, type WorkspaceSectionValue } from './WorkspaceNavigation'
import { AuthBrandPill } from './AuthBrand'
import { LoginSurface } from './LoginExperience'
import { BaleConversationList, type BaleDialogItem } from './bale/BaleConversationList'
import { BaleAvatar } from './bale/BaleConversationList'
import { BaleChatHeader } from './bale/BaleChatHeader'
import { BaleMessageCard } from './bale/BaleMessageCard'
import { BaleComposer, type BaleSendTarget } from './bale/BaleComposer'
import { BaleContactDirectory } from './bale/BaleContactDirectory'

type Auth = { auth_state: string; has_vault: boolean; step?: string; challenge_id?: string }
type Message = { message_reference: string; text?: string; media_reference?: string; sender_reference?: string | null; sent_at_unix_ms: number }
type Contact = { contact_reference: string; display_name: string }

const CAPABILITY_LABELS: Record<string, string> = {
  'auth.phone': 'ورود با شماره',
  'auth.token': 'ورود با توکن',
  'auth.logout': 'خروج از نشست',
  'contacts.read': 'خواندن مخاطبین',
  'contacts.write': 'تغییر مخاطبین',
  'dialogs.read': 'خواندن گفتگوها',
  'history.read': 'خواندن تاریخچه',
  'messages.send': 'ارسال پیام',
  'media.read': 'دریافت رسانه',
  'media.send': 'ارسال رسانه',
  'updates.live': 'دریافت خودکار پیام‌های تازه',
}

const capabilityLabel = (capability: string) => CAPABILITY_LABELS[capability] || capability

function mergeMessages(previous: Message[], incoming: Message[]): Message[] {
  return [...new Map([...previous, ...incoming].map(item => [item.message_reference, item])).values()]
    .sort((a, b) => a.sent_at_unix_ms - b.sent_at_unix_ms || a.message_reference.localeCompare(b.message_reference)).slice(-500)
}

export function BaleWorkspace() {
  const accounts = useMessengerAccounts()
  const appUser = useAppUser()
  const account = accounts.selected!
  const base = `/api/v2/messenger-accounts/${account.messenger_account_id}`
  const theme = useTheme()
  const mobile = useMediaQuery('(max-width: 899px)', { noSsr: true })
  const alive = useRef(true)
  const [auth, setAuth] = useState<Auth | null>(null)
  const [authError, setAuthError] = useState('')
  const [secret, setSecret] = useState('')
  const [dialogs, setDialogs] = useState<BaleDialogItem[]>([])
  const [dialogsLoaded, setDialogsLoaded] = useState(false)
  const [peer, setPeer] = useState<BaleDialogItem | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [historyCursor, setHistoryCursor] = useState<string | null>(null)
  const selectedPeer = useRef<string | null>(null)
  selectedPeer.current = peer?.peer_reference || null
  const dialogPoll = useRef({ nextAt: 0, failures: 0, error: '' })
  const [section, setSection] = useState<WorkspaceSectionValue>('all')
  const [search, setSearch] = useState('')
  const [listOpen, setListOpen] = useState(true)
  const [syncing, setSyncing] = useState(false)
  const [directoryOpen, setDirectoryOpen] = useState(false)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [downloadingKey, setDownloadingKey] = useState('')
  const [error, setError] = useState('')
  const [pollError, setPollError] = useState('')
  const [busy, setBusy] = useState(false)
  const busyRef = useRef(false)
  const [confirm, setConfirm] = useState<{ label: string; run: () => Promise<void> } | null>(null)
  const scrollBoxRef = useRef<HTMLDivElement | null>(null)
  const followRef = useRef(true)

  useEffect(() => {
    alive.current = true
    dialogPoll.current = { nextAt: 0, failures: 0, error: '' }
    setPeer(null); setDialogs([]); setMessages([]); setPollError(''); setDialogsLoaded(false); setSection('all'); setSearch(''); setListOpen(true)
    setAuthError('')
    void api<Auth>('GET', `${base}/auth/status`).then(value => { if (alive.current) setAuth(value) }).catch(reason => { if (alive.current) { setAuthError(String(reason.message)); setAuth(null) } })
    return () => { alive.current = false }
  }, [base])

  const run = async (callback: () => Promise<void>) => {
    if (busyRef.current) return
    busyRef.current = true
    setBusy(true); setError('')
    try { await callback() } catch (reason) { if (alive.current) setError(reason instanceof Error ? reason.message : 'عملیات انجام نشد.') }
    finally { busyRef.current = false; if (alive.current) setBusy(false) }
  }
  const authenticate = async (action: string, body: Record<string, unknown> = {}) => {
    const next = await api<Auth>('POST', `${base}/auth/${action}`, body)
    if (!alive.current) return
    setSecret(''); setAuth(next); setMessages([]); setDialogs([]); setDialogsLoaded(false)
    await accounts.refresh()
  }

  // History stays responsive in the open chat (about every 5 seconds). Dialogs
  // have a separate provider-friendly cadence (about every 15 seconds) with an
  // independent failure backoff, a hidden tab never polls, and a dialogs
  // failure never blocks history — this ordering was fixed after Bale rate
  // problems and must be preserved.
  useEffect(() => {
    if (auth?.auth_state !== 'authenticated') return
    let active = true
    let timer: ReturnType<typeof setTimeout>
    let historyError = ''
    const poll = async () => {
      if (!active) return
      if (document.visibilityState === 'hidden' && accounts.hasCapability('updates.live')) {
        timer = setTimeout(() => void poll(), 5000)
        return
      }
      if (accounts.hasCapability('dialogs.read') && Date.now() >= dialogPoll.current.nextAt) {
        dialogPoll.current.nextAt = Date.now() + 15000
        try {
          const result = await api<{ dialogs: BaleDialogItem[] }>('POST', `${base}/dialogs/query`, { limit: 100 })
          if (active) setDialogs(result.dialogs)
          dialogPoll.current.failures = 0
          dialogPoll.current.error = ''
          if (active) setDialogsLoaded(true)
        } catch (reason) {
          dialogPoll.current.failures = Math.min(dialogPoll.current.failures + 1, 2)
          dialogPoll.current.nextAt = Date.now() + Math.min(60000, 15000 * 2 ** dialogPoll.current.failures)
          dialogPoll.current.error = reason instanceof Error ? reason.message : 'ارتباط برقرار نشد.'
        }
      }
      if ((peer?.peer_kind === 'private' || peer?.peer_kind === 'group' || peer?.peer_kind === 'channel') && accounts.hasCapability('history.read')) {
        try {
          const result = await api<{ messages: Message[]; next_cursor?: string }>('POST', `${base}/history/query`, { peer_reference: peer.peer_reference, peer_kind: peer.peer_kind, limit: 100 })
          if (active) {
            setMessages(previous => mergeMessages(previous, result.messages))
            setHistoryCursor(previous => previous || result.next_cursor || null)
          }
          historyError = ''
        } catch (reason) {
          historyError = reason instanceof Error ? reason.message : 'ارتباط برقرار نشد.'
        }
      }
      if (active) setPollError(dialogPoll.current.error || historyError)
      if (dialogPoll.current.error || historyError) {
        try {
          const status = await api<Auth>('GET', `${base}/auth/status`)
          if (active && status.auth_state !== 'authenticated') setAuth(status)
        } catch { /* Keep the connection error visible. */ }
      }
      if (active && accounts.hasCapability('updates.live')) timer = setTimeout(() => void poll(), 5000)
    }
    setMessages([]); setHistoryCursor(null)
    void poll()
    return () => { active = false; clearTimeout(timer) }
  }, [base, auth?.auth_state, peer?.peer_reference, accounts.hasCapability, accounts.capabilityLoading])

  const refreshNow = async () => {
    if (!accounts.hasCapability('dialogs.read')) return
    setSyncing(true)
    try {
      const result = await api<{ dialogs: BaleDialogItem[] }>('POST', `${base}/dialogs/query`, { limit: 100 })
      if (alive.current) {
        setDialogs(result.dialogs)
        setDialogsLoaded(true)
      }
      dialogPoll.current.failures = 0
      dialogPoll.current.error = ''
      dialogPoll.current.nextAt = Date.now() + 15000
      if (alive.current) setPollError(previous => (previous ? '' : previous))
    } catch (reason) {
      dialogPoll.current.failures = Math.min(dialogPoll.current.failures + 1, 2)
      dialogPoll.current.nextAt = Date.now() + Math.min(60000, 15000 * 2 ** dialogPoll.current.failures)
      dialogPoll.current.error = reason instanceof Error ? reason.message : 'ارتباط برقرار نشد.'
      if (alive.current) setPollError(dialogPoll.current.error)
    } finally { if (alive.current) setSyncing(false) }
  }

  const loadOlder = async () => {
    if (!peer || !historyCursor) return
    const reference = peer.peer_reference
    const result = await api<{ messages: Message[]; next_cursor?: string }>('POST', `${base}/history/query`, { peer_reference: reference, peer_kind: peer.peer_kind, limit: 100, cursor: historyCursor })
    if (!alive.current || selectedPeer.current !== reference) return
    setMessages(previous => mergeMessages(previous, result.messages))
    setHistoryCursor(result.next_cursor && result.next_cursor !== historyCursor ? result.next_cursor : null)
  }

  const send = async (payload: { kind: 'text'; peer: BaleSendTarget; text: string; idempotency_key: string } | { kind: 'media'; peer: BaleSendTarget; file: File; caption: string; idempotency_key: string }): Promise<'succeeded' | 'uncertain'> => {
    let status: string
    if (payload.kind === 'text') {
      const result = await api<{ status: string }>('POST', `${base}/messages/send-text`, {
        peer_reference: payload.peer.peer_reference,
        peer_kind: payload.peer.peer_kind,
        text: payload.text,
        idempotency_key: payload.idempotency_key,
        confirm: true,
      })
      status = result.status
    } else {
      const bytes = new Uint8Array(await payload.file.arrayBuffer())
      let binary = ''
      bytes.forEach(value => { binary += String.fromCharCode(value) })
      const result = await api<{ status: string }>('POST', `${base}/messages/send-media`, {
        peer_reference: payload.peer.peer_reference,
        peer_kind: payload.peer.peer_kind,
        filename: payload.file.name,
        data_base64: btoa(binary),
        caption: payload.caption,
        idempotency_key: payload.idempotency_key,
        confirm: true,
      })
      status = result.status
    }
    // A late response must never leak into a different account or dialog; the
    // composer owns its own state, so only history is refreshed here.
    if (payload.peer.peer_kind === 'private' && accounts.hasCapability('history.read')) {
      try {
        const history = await api<{ messages: Message[]; next_cursor?: string }>('POST', `${base}/history/query`, { peer_reference: payload.peer.peer_reference, peer_kind: payload.peer.peer_kind, limit: 100 })
        if (alive.current && selectedPeer.current === payload.peer.peer_reference) {
          setMessages(previous => mergeMessages(previous, history.messages))
        }
      } catch { /* Background poll handles errors */ }
    }
    return status === 'succeeded' ? 'succeeded' : 'uncertain'
  }

  const download = async (message: Message) => {
    if (!peer || !message.media_reference) return
    setDownloadingKey(message.message_reference)
    try {
      const receipt = await api<{ content_reference: string }>('POST', `${base}/media/read`, { peer_reference: peer.peer_reference, peer_kind: peer.peer_kind, message_reference: message.message_reference, media_reference: message.media_reference, max_bytes: 512 * 1024, variant: 'full' })
      const content = await api<{ data_base64: string; mime_type: string }>('POST', `${base}/media/content`, { content_reference: receipt.content_reference })
      if (!alive.current) return
      const bytes = Uint8Array.from(atob(content.data_base64), c => c.charCodeAt(0))
      const url = URL.createObjectURL(new Blob([bytes], { type: 'application/octet-stream' }))
      const link = document.createElement('a'); link.href = url; link.download = 'bale-media'; link.click()
      setTimeout(() => URL.revokeObjectURL(url), 1000)
    } finally { if (alive.current) setDownloadingKey('') }
  }

  useEffect(() => { followRef.current = true }, [peer?.peer_reference])
  useEffect(() => {
    if (!followRef.current) return
    const box = scrollBoxRef.current
    if (box) box.scrollTop = box.scrollHeight
  }, [messages, peer?.peer_reference])

  const railTabs = useMemo(() => {
    const unread = (kind?: string) => dialogs
      .filter(item => !kind || item.peer_kind === kind)
      .reduce((sum, item) => sum + (item.unread_count || 0), 0)
    return [
      { value: 'all' as const, label: 'همه', count: unread() },
      { value: 'personal' as const, label: 'شخصی', count: unread('private') },
      { value: 'group' as const, label: 'گروه‌ها', count: unread('group') },
      { value: 'channel' as const, label: 'کانال‌ها', count: unread('channel') },
    ]
  }, [dialogs])

  const visibleDialogs = useMemo(() => {
    const query = search.trim()
    return dialogs.filter(item => {
      if (section !== 'all' && item.peer_kind !== (section === 'personal' ? 'private' : section)) return false
      if (!query) return true
      return (item.title || '').includes(query) || (item.last_text || '').includes(query)
    })
  }, [dialogs, section, search])

  const dialogsSupported = accounts.hasCapability('dialogs.read')
  const liveState: 'idle' | 'connecting' | 'retrying' = pollError
    ? 'retrying'
    : (accounts.capabilityLoading || (auth?.auth_state === 'authenticated' && !dialogsLoaded)) ? 'connecting' : 'idle'
  const outgoingFor = (message: Message) => Boolean(
    peer?.peer_kind === 'private'
    && message.sender_reference
    && message.sender_reference !== peer.peer_reference,
  )
  // Group/channel senders have no display name in the Bale contract; the
  // short typed reference is shown instead of inventing one.
  const authorFor = (message: Message) => {
    if (peer?.peer_kind === 'private' || !message.sender_reference) return ''
    const suffix = message.sender_reference.replace(/^bale:user:/, '')
    return suffix === message.sender_reference ? '' : suffix
  }
  const sendDisabledReason = (kind: string) => {
    if (kind === 'private' || kind === 'group' || kind === 'channel') return ''
    return 'این نوع گفتگو پشتیبانی نمی‌شود.'
  }
  const contactCanOpenChat = (contact: Contact) => {
    setPeer({ peer_reference: contact.contact_reference, peer_kind: 'private', title: contact.display_name, unread_count: 0 })
    setSection('all')
  }
  const logoutSoftware = async () => {
    if (!window.confirm('از نرم‌افزار خارج شوید؟ نشست حساب بله حذف نمی‌شود.')) return
    try { await appUser.logout() } catch (reason) { if (alive.current) setError(reason instanceof Error ? reason.message : 'خروج از نرم‌افزار انجام نشد.') }
  }

  const alerts = <Stack spacing={1}>
    {error && <Alert severity="error" onClose={() => setError('')}>{error}</Alert>}
    {pollError && <Alert severity="warning">{pollError}</Alert>}
    {accounts.capabilityError && <Alert severity="error">{accounts.capabilityError}</Alert>}
  </Stack>

  if (!auth) {
    if (authError) {
      return <LoginSurface><Stack alignItems="center" spacing={2} sx={{ maxWidth: 420 }} data-provider-workspace="bale">
        <AuthBrandPill label="حساب بله" />
        <Typography variant="h6">خواندن وضعیت نشست انجام نشد</Typography>
        <Alert severity="error" sx={{ width: '100%' }}>{authError}</Alert>
        <Button variant="contained" onClick={() => { setAuthError(''); void api<Auth>('GET', `${base}/auth/status`).then(value => { if (alive.current) setAuth(value) }).catch(reason => { if (alive.current) setAuthError(String(reason.message)) }) }}>تلاش دوباره</Button>
        <AppUserLogoutButton />
      </Stack></LoginSurface>
    }
    return <LoginSurface><Stack alignItems="center" spacing={2} data-provider-workspace="bale">
      <AuthBrandPill label="حساب بله" />
      <Typography variant="h6">در حال خواندن وضعیت نشست بله</Typography>
      <CircularProgress size={32} />
    </Stack></LoginSurface>
  }
  if (auth.auth_state !== 'authenticated') {
    return <LoginSurface><Stack spacing={2} sx={{ maxWidth: 460, width: '100%' }} data-provider-workspace="bale">
      <AuthBrandPill label="حساب بله" />
      <Typography variant="h5">ورود به حساب بله انتخابی</Typography>
      <Typography>{account.label || 'حساب بله'} · <span dir="ltr">{account.phone_hint}</span> · وضعیت نشست: {auth.auth_state}</Typography>
      {alerts}
      {auth.step && auth.challenge_id ? <Paper variant="outlined" sx={{ p: 2 }}><Stack spacing={2}>
        <TextField autoComplete="off" label={auth.step === 'password' ? 'رمز دومرحله‌ای' : 'کد ورود'} type={auth.step === 'password' ? 'password' : 'text'} value={secret} onChange={event => setSecret(event.target.value)} />
        <Button variant="contained" disabled={busy || !secret} onClick={() => void run(() => authenticate(auth.step === 'password' ? 'password' : 'code', { challenge_id: auth.challenge_id, [auth.step === 'password' ? 'password' : 'code']: secret }))}>ادامهٔ ورود</Button>
        <Button disabled={busy} onClick={() => void run(() => authenticate('cancel'))}>لغو ورود</Button>
      </Stack></Paper>
        : <Paper variant="outlined" sx={{ p: 2 }}><Stack spacing={2}>
          <Button variant="contained" disabled={busy || !accounts.hasCapability('auth.phone')} onClick={() => setConfirm({ label: 'درخواست کد ورود بله برای همین حساب؟', run: () => authenticate('start', { confirm: true }) })}>درخواست کد ورود</Button>
          {!accounts.hasCapability('auth.phone') && <Alert severity="info">ورود با شماره برای این حساب در حال حاضر مجاز نیست.</Alert>}
          {auth.has_vault && !['revoked', 'invalid'].includes(auth.auth_state) && <Button disabled={busy} onClick={() => void run(() => authenticate('restore', { confirm: true }))}>بازیابی نشست ذخیره‌شده</Button>}
        </Stack></Paper>}
      <AddMessengerAccountButton />
      <AppUserLogoutButton disabled={busy} />
      <Dialog open={Boolean(confirm)} onClose={() => !busy && setConfirm(null)}><DialogTitle>تأیید عملیات</DialogTitle><DialogContent>{confirm?.label}</DialogContent><DialogActions>
        <Button disabled={busy} onClick={() => setConfirm(null)}>انصراف</Button><Button disabled={busy} onClick={() => { const operation = confirm; setConfirm(null); if (operation) void run(operation.run) }}>تأیید</Button>
      </DialogActions></Dialog>
    </Stack></LoginSurface>
  }

  return <Box sx={{ width: '100%', height: '100%', minWidth: 0, minHeight: 0, overflow: 'hidden', bgcolor: 'background.default' }} data-provider-workspace="bale">
    <Box component="main" sx={{
      width: '100%',
      height: '100%',
      minWidth: 0,
      minHeight: 0,
      overflow: 'hidden',
      display: { xs: 'block', md: 'grid' },
      pb: { xs: 'calc(66px + env(safe-area-inset-bottom))', md: 0 },
      gridTemplateColumns: { md: '72px minmax(280px, 32vw) minmax(0, 1fr)' },
      '& > *': { minWidth: 0, minHeight: 0 },
    }}>
      <WorkspaceNavigation
        sections={railTabs}
        activeSection={section}
        userName={appUser.principal?.display_name || 'بله'}
        userRole={appUser.principal?.global_role === 'admin' ? 'مدیر نرم‌افزار' : 'کاربر نرم‌افزار'}
        accountControl={<MessengerAccountMenuControl />}
        syncing={syncing}
        dialogsEnabled={dialogsSupported}
        wordpressVisible={false}
        wordpressEnabled={false}
        onSection={value => { setSection(value); if (mobile) setListOpen(true) }}
        onSettings={() => setSettingsOpen(true)}
        onSync={() => void run(refreshNow)}
        onContacts={() => setDirectoryOpen(true)}
        onMessengerLogout={() => setConfirm({ label: 'خروج از نشست بله همین حساب؟', run: () => authenticate('logout', { confirm: true }) })}
        onSoftwareLogout={appUser.enabled ? () => void logoutSoftware() : undefined}
        syncLabel="به‌روزرسانی گفتگوها"
        messengerLogoutLabel="خروج از حساب بله"
      />

      <BaleConversationList
        open={listOpen}
        docked={!mobile}
        loading={!dialogsLoaded && dialogsSupported}
        refreshing={syncing}
        dialogsEnabled={dialogsSupported}
        filterLabel={railTabs.find(item => item.value === section)?.label || 'گفتگوها'}
        search={search}
        items={visibleDialogs}
        totalCount={visibleDialogs.length}
        activePeerKey={peer?.peer_reference}
        warning={pollError || undefined}
        onSearch={setSearch}
        onClose={() => setListOpen(false)}
        onRefresh={() => void run(refreshNow)}
        onSelect={item => { setPeer(item); if (mobile) setListOpen(false) }}
      />

      <Paper component="section" square elevation={0} sx={{ display: 'flex', flexDirection: 'column', position: 'relative', minWidth: 0, minHeight: 0, height: { xs: 'calc(100dvh - 66px - env(safe-area-inset-bottom))', md: '100%' }, overflow: 'hidden', bgcolor: theme => theme.palette.mode === 'dark' ? '#0c131b' : '#e7f0ea' }}>
        {alerts}
        {!dialogsSupported && <Alert severity="info" sx={{ borderRadius: 0 }}>خواندن گفتگوها برای این حساب در حال حاضر مجاز نیست.</Alert>}
        <BaleChatHeader
          title={peer?.title || 'یک گفتگو را انتخاب کنید'}
          subtitle={peer ? `${messages.length.toLocaleString('fa-IR')} پیام در این نشست` : `${account.label || 'حساب بله'} — ${account.phone_hint}`}
          avatar={<BaleAvatar title={peer?.title || 'ب'} small />}
          liveState={liveState}
          onOpenChats={() => setListOpen(true)}
        />
        {!peer ? <Stack alignItems="center" justifyContent="center" spacing={1.5} sx={{ minHeight: 0, flex: 1, p: 3, textAlign: 'center' }}>
          <AuthBrandPill label="بله" />
          <Typography variant="h6">یک گفتگو را انتخاب کنید</Typography>
          <Typography variant="body2" color="text.secondary">از فهرست گفتگوها یا دفترچهٔ مخاطبین، مقصد خصوصی را باز کنید.</Typography>
        </Stack> : <Stack spacing={0.75} sx={{ minHeight: 0, flex: 1, p: { xs: 1, sm: 1.5 }, minWidth: 0 }}>
          <Stack direction="row" alignItems="center" gap={1} flexWrap="wrap">
            {historyCursor && messages.length < 500 && <Button size="small" variant="outlined" disabled={busy || !accounts.hasCapability('history.read')} onClick={() => void run(loadOlder)}>پیام‌های قدیمی‌تر</Button>}
            {messages.length >= 500 && <Typography variant="caption" color="text.secondary">حد نمایش این گفتگو ۵۰۰ پیام است.</Typography>}
            {Boolean(messages.length) && !historyCursor && <Chip size="small" variant="outlined" label="ابتدای گفتگو نمایش داده شد" />}
            {peer.peer_kind !== 'private' && peer.peer_kind !== 'group' && peer.peer_kind !== 'channel' && <Alert severity="info" sx={{ py: 0.25 }}>این کلاینت خواندن و ارسال در این نوع گفتگو را پشتیبانی نمی‌کند.</Alert>}
          </Stack>
          <Box ref={scrollBoxRef} onScroll={() => {
            const box = scrollBoxRef.current
            if (box) followRef.current = box.scrollHeight - box.scrollTop - box.clientHeight < 160
          }} sx={{ flex: 1, minHeight: 0, overflowY: 'auto', overflowAnchor: 'none', display: 'flex', flexDirection: 'column', gap: 0.75, py: 0.5 }}>
            {messages.map(message => <BaleMessageCard
              key={message.message_reference}
              text={message.text}
              sentAtUnixMs={message.sent_at_unix_ms}
              outgoing={outgoingFor(message)}
              author={authorFor(message)}
              hasMedia={Boolean(message.media_reference)}
              canDownloadMedia={accounts.hasCapability('media.read')}
              downloading={downloadingKey === message.message_reference}
              onDownload={() => void run(() => download(message))}
            />)}
            {!messages.length && <Typography variant="body2" color="text.secondary" sx={{ textAlign: 'center', py: 3 }}>پیامی برای نمایش نیست؛ پیام‌های تازه به‌صورت خودکار ظاهر می‌شوند.</Typography>}
          </Box>
          <BaleComposer
            key={peer.peer_reference}
            peer={sendDisabledReason(peer.peer_kind) ? null : { peer_reference: peer.peer_reference, peer_kind: peer.peer_kind, title: peer.title }}
            unsupportedReason={sendDisabledReason(peer.peer_kind)}
            canSendText={accounts.hasCapability('messages.send')}
            canSendMedia={accounts.hasCapability('media.send')}
            capabilityLoading={accounts.capabilityLoading}
            capabilityError={accounts.capabilityError}
            send={send}
            onSent={() => undefined}
          />
        </Stack>}
      </Paper>
    </Box>

    <BaleContactDirectory
      open={directoryOpen}
      base={base}
      can={capability => accounts.hasCapability(capability)}
      onClose={() => setDirectoryOpen(false)}
      onOpenChat={contactCanOpenChat}
    />

    <Dialog open={settingsOpen} fullScreen onClose={() => setSettingsOpen(false)}>
      <DialogContent sx={{ p: 0, bgcolor: 'background.default' }}>
        <Stack spacing={2} sx={{ p: { xs: 1, sm: 2 }, maxWidth: 980, mx: 'auto' }}>
          <Stack direction="row" alignItems="center" justifyContent="space-between" gap={1}>
            <Typography variant="h5" fontWeight={850}>تنظیمات و دسترسی بله</Typography>
            <Button variant="outlined" onClick={() => setSettingsOpen(false)}>بازگشت به گفتگوها</Button>
          </Stack>
          <Alert severity={auth.auth_state === 'authenticated' ? 'success' : 'info'}>آمادگی حساب بله: نشست وارد شده · Worker: {account.worker?.runtime_state || 'نامشخص'}</Alert>
          {accounts.capabilitySnapshot && <Paper variant="outlined" sx={{ p: 2 }}>
            <Typography variant="h6">قابلیت‌های مجاز این حساب</Typography>
            <Typography variant="caption" color="text.secondary">هر قابلیت غیرمجاز با کد علت خودش نمایش داده می‌شود.</Typography>
            <Stack direction="row" gap={1} flexWrap="wrap" sx={{ pt: 1 }}>
              {accounts.capabilitySnapshot.capabilities.map(item => <Stack key={item.capability} direction="row" spacing={0.75} alignItems="center">
                <Chip size="small" color={item.status === 'supported' ? 'success' : item.status === 'restricted' ? 'warning' : 'default'} label={capabilityLabel(item.capability)} />
                <Typography variant="caption" color="text.secondary">{item.status === 'supported' ? 'مجاز' : item.reason_code}</Typography>
              </Stack>)}
            </Stack>
          </Paper>}
          <MessengerAccountManagementPanel />
          <AccessManagementPanel />
          <ServiceAccountSettingsPanel />
          <Button color="warning" disabled={busy} onClick={() => setConfirm({ label: 'خروج از نشست بله همین حساب؟', run: () => authenticate('logout', { confirm: true }) })}>خروج از حساب بله</Button>
        </Stack>
      </DialogContent>
    </Dialog>

    <Dialog open={Boolean(confirm)} onClose={() => !busy && setConfirm(null)}><DialogTitle>تأیید عملیات</DialogTitle><DialogContent>{confirm?.label}</DialogContent><DialogActions>
      <Button disabled={busy} onClick={() => setConfirm(null)}>انصراف</Button><Button disabled={busy} onClick={() => { const operation = confirm; setConfirm(null); if (operation) void run(operation.run) }}>تأیید</Button>
    </DialogActions></Dialog>
  </Box>
}
