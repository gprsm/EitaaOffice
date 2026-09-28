import { useEffect, useRef, useState } from 'react'
import { Alert, Box, Button, CircularProgress, Dialog, DialogActions, DialogContent, DialogTitle, List, ListItemButton, ListItemText, Paper, Stack, TextField, Typography } from '@mui/material'
import { api } from './lib/api'
import { AddMessengerAccountButton, MessengerAccountManagementPanel, MessengerAccountMenuControl, useMessengerAccounts } from './MessengerAccountGate'
import { AppUserLogoutButton } from './AppUserGate'
import { AccessManagementPanel } from './AccessManagementPanel'
import { ServiceAccountSettingsPanel } from './ServiceAccountSettingsPanel'

type Auth = { auth_state: string; has_vault: boolean; step?: string; challenge_id?: string }
type Peer = { peer_reference: string; peer_kind: string; title: string; last_text?: string; unread_count: number }
type Message = { message_reference: string; text?: string; media_reference?: string; sent_at_unix_ms: number }
type Contact = { contact_reference: string; display_name: string }

function mergeMessages(previous: Message[], incoming: Message[]): Message[] {
  return [...new Map([...previous, ...incoming].map(item => [item.message_reference, item])).values()]
    .sort((a, b) => a.sent_at_unix_ms - b.sent_at_unix_ms || a.message_reference.localeCompare(b.message_reference)).slice(-500)
}

export function BaleWorkspace() {
  const accounts = useMessengerAccounts()
  const account = accounts.selected!
  const base = `/api/v2/messenger-accounts/${account.messenger_account_id}`
  const alive = useRef(true)
  const [auth, setAuth] = useState<Auth | null>(null)
  const [secret, setSecret] = useState('')
  const [dialogs, setDialogs] = useState<Peer[]>([])
  const [peer, setPeer] = useState<Peer | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [historyCursor, setHistoryCursor] = useState<string | null>(null)
  const selectedPeer = useRef<string | null>(null)
  selectedPeer.current = peer?.peer_reference || null
  const [contacts, setContacts] = useState<Contact[]>([])
  const [search, setSearch] = useState('')
  const [identity, setIdentity] = useState('')
  const [name, setName] = useState('')
  const [text, setText] = useState('')
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [busy, setBusy] = useState(false)
  const [view, setView] = useState<'chat' | 'contacts' | 'settings'>('chat')
  const [confirm, setConfirm] = useState<{ label: string; run: () => Promise<void> } | null>(null)
  const [draftFile, setDraftFile] = useState<File | null>(null)

  useEffect(() => {
    alive.current = true
    void api<Auth>('GET', `${base}/auth/status`).then(value => { if (alive.current) setAuth(value) }).catch(reason => { if (alive.current) setError(String(reason.message)) })
    return () => { alive.current = false }
  }, [base])
  const run = async (callback: () => Promise<void>) => {
    if (busy) return
    setBusy(true); setError(''); setNotice('')
    try { await callback() } catch (reason) { if (alive.current) setError(reason instanceof Error ? reason.message : 'عملیات انجام نشد.') }
    finally { if (alive.current) setBusy(false) }
  }
  const authenticate = async (action: string, body: Record<string, unknown> = {}) => {
    const next = await api<Auth>('POST', `${base}/auth/${action}`, body)
    if (!alive.current) return
    setSecret(''); setAuth(next); setMessages([]); setDialogs([]); setContacts([])
    await accounts.refresh()
  }
  useEffect(() => {
    if (auth?.auth_state !== 'authenticated' || view !== 'chat') return
    let active = true
    let timer: ReturnType<typeof setTimeout>
    const poll = async () => {
      try {
        if (accounts.hasCapability('dialogs.read')) {
          const result = await api<{ dialogs: Peer[] }>('POST', `${base}/dialogs/query`, { limit: 100 })
          if (active) setDialogs(result.dialogs)
        }
        if (peer?.peer_kind === 'private' && accounts.hasCapability('history.read')) {
          const result = await api<{ messages: Message[]; next_cursor?: string }>('POST', `${base}/history/query`, { peer_reference: peer.peer_reference, peer_kind: peer.peer_kind, limit: 100 })
          if (active) {
            setMessages(previous => mergeMessages(previous, result.messages))
            setHistoryCursor(previous => previous || result.next_cursor || null)
          }
        }
      } catch (reason) {
        if (active) {
          setError(reason instanceof Error ? reason.message : 'ارتباط برقرار نشد.')
          try {
            const status = await api<Auth>('GET', `${base}/auth/status`)
            if (active && status.auth_state !== 'authenticated') setAuth(status)
          } catch { /* Keep the connection error visible. */ }
        }
      }
      finally { if (active) timer = setTimeout(() => void poll(), 5000) }
    }
    setMessages([]); setHistoryCursor(null)
    void poll()
    return () => { active = false; clearTimeout(timer) }
  }, [base, auth?.auth_state, peer?.peer_reference, view, accounts.hasCapability])
  const loadOlder = async () => {
    if (!peer || !historyCursor) return
    const reference = peer.peer_reference
    const result = await api<{ messages: Message[]; next_cursor?: string }>('POST', `${base}/history/query`, { peer_reference: reference, peer_kind: peer.peer_kind, limit: 100, cursor: historyCursor })
    if (!alive.current || selectedPeer.current !== reference) return
    setMessages(previous => mergeMessages(previous, result.messages))
    setHistoryCursor(result.next_cursor && result.next_cursor !== historyCursor ? result.next_cursor : null)
  }
  const loadContacts = async () => {
    const result = search.trim()
      ? await api<{ contacts: Contact[] }>('POST', `${base}/contacts/search`, { query: search.trim() })
      : await api<{ contacts: Contact[] }>('POST', `${base}/contacts/query`, { limit: 500 })
    if (alive.current) setContacts(result.contacts)
  }
  useEffect(() => {
    if (view === 'contacts' && auth?.auth_state === 'authenticated' && accounts.hasCapability('contacts.read')) void run(loadContacts)
  }, [view, auth?.auth_state])
  const send = async () => {
    if (!peer || !text.trim()) return
    const key = crypto.randomUUID()
    const result = await api<{ status: string }>('POST', `${base}/messages/send-text`, { peer_reference: peer.peer_reference, peer_kind: peer.peer_kind, text, idempotency_key: key, confirm: true })
    if (!alive.current) return
    setText('')
    setNotice(result.status === 'succeeded' ? 'پیام به سرویس بله ارسال شد؛ مشاهدهٔ گیرنده تأیید نشده است.' : 'نتیجهٔ ارسال نامعلوم است؛ ارسال خودکار تکرار نمی‌شود.')
  }
  const sendFile = async () => {
    if (!peer || !draftFile) return
    if (draftFile.size > 512 * 1024) throw new Error('حد فعلی هر فایل ۵۱۲ کیلوبایت است.')
    const bytes = new Uint8Array(await draftFile.arrayBuffer())
    let binary = ''
    bytes.forEach(value => { binary += String.fromCharCode(value) })
    const result = await api<{ status: string }>('POST', `${base}/messages/send-media`, { peer_reference: peer.peer_reference, peer_kind: peer.peer_kind, filename: draftFile.name, data_base64: btoa(binary), caption: text, idempotency_key: crypto.randomUUID(), confirm: true })
    if (!alive.current) return
    setDraftFile(null); setText(''); setNotice(result.status === 'succeeded' ? 'فایل به سرویس ارسال شد.' : 'نتیجه نامعلوم است؛ خودکار تکرار نمی‌شود.')
  }
  const download = async (message: Message) => {
    if (!peer || !message.media_reference) return
    const receipt = await api<{ content_reference: string }>('POST', `${base}/media/read`, { peer_reference: peer.peer_reference, peer_kind: peer.peer_kind, message_reference: message.message_reference, media_reference: message.media_reference, max_bytes: 512 * 1024, variant: 'full' })
    const content = await api<{ data_base64: string; mime_type: string }>('POST', `${base}/media/content`, { content_reference: receipt.content_reference })
    if (!alive.current) return
    const bytes = Uint8Array.from(atob(content.data_base64), c => c.charCodeAt(0))
    const url = URL.createObjectURL(new Blob([bytes], { type: 'application/octet-stream' }))
    const link = document.createElement('a'); link.href = url; link.download = 'bale-media'; link.click()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  }

  return <Stack dir="rtl" spacing={1.5} sx={{ p: 2, height: '100%', overflow: 'auto' }} data-provider-workspace="bale">
    <Stack direction="row" alignItems="center" gap={2} flexWrap="wrap">
      <Typography variant="h5">بله — {account.label || account.phone_hint}</Typography>
      <Box sx={{ minWidth: 230 }}><MessengerAccountMenuControl /></Box>
      <AddMessengerAccountButton />
      <Button onClick={() => setView('chat')}>گفتگوها</Button><Button onClick={() => setView('contacts')}>مخاطبین</Button><Button onClick={() => setView('settings')}>تنظیمات و دسترسی</Button>
      <AppUserLogoutButton />
    </Stack>
    {error && <Alert severity="error">{error}</Alert>}
    {notice && <Alert severity="info">{notice}</Alert>}
    {accounts.capabilityError && <Alert severity="error">{accounts.capabilityError}</Alert>}
    {!auth && <CircularProgress aria-label="خواندن نشست بله" />}
    {auth && auth.auth_state !== 'authenticated' && <Paper variant="outlined" sx={{ p: 2 }}><Stack spacing={2}>
      <Typography variant="h6">ورود به حساب بله انتخابی</Typography>
      <Typography>{account.phone_hint} · وضعیت نشست: {auth.auth_state}</Typography>
      {auth.step && auth.challenge_id ? <>
        <TextField autoComplete="off" label={auth.step === 'password' ? 'رمز دومرحله‌ای' : 'کد ورود'} type={auth.step === 'password' ? 'password' : 'text'} value={secret} onChange={event => setSecret(event.target.value)} />
        <Button disabled={busy || !secret} onClick={() => void run(() => authenticate(auth.step === 'password' ? 'password' : 'code', { challenge_id: auth.challenge_id, [auth.step === 'password' ? 'password' : 'code']: secret }))}>ادامهٔ ورود</Button>
        <Button disabled={busy} onClick={() => void run(() => authenticate('cancel'))}>لغو ورود</Button>
      </> : <Button disabled={busy || !accounts.hasCapability('auth.phone')} onClick={() => setConfirm({ label: 'درخواست کد ورود بله برای همین حساب؟', run: () => authenticate('start', { confirm: true }) })}>درخواست کد ورود</Button>}
      {auth.has_vault && !['revoked', 'invalid'].includes(auth.auth_state) && <Button disabled={busy} onClick={() => void run(() => authenticate('restore', { confirm: true }))}>بازیابی نشست ذخیره‌شده</Button>}
    </Stack></Paper>}
    {auth?.auth_state === 'authenticated' && view === 'chat' && <Stack direction={{ xs: 'column', md: 'row' }} spacing={2} sx={{ minHeight: 350, flex: 1 }}>
      <Paper variant="outlined" sx={{ minWidth: 220, maxHeight: '75vh', overflow: 'auto' }}><List>
        {dialogs.map(item => <ListItemButton key={item.peer_reference} selected={peer?.peer_reference === item.peer_reference} onClick={() => { setPeer(item); setText(''); setDraftFile(null) }}><ListItemText primary={`${item.title}${item.unread_count ? ` (${item.unread_count})` : ''}`} secondary={item.last_text} /></ListItemButton>)}
        {!dialogs.length && <Typography sx={{ p: 2 }}>گفتگویی بارگذاری نشده است.</Typography>}
      </List></Paper>
      <Stack spacing={1} sx={{ flex: 1, minWidth: 0 }}>
        <Typography variant="h6">{peer?.title || 'یک گفتگو انتخاب کنید'}</Typography>
        {historyCursor && messages.length < 500 && <Button disabled={busy || !accounts.hasCapability('history.read')} onClick={() => void run(loadOlder)}>پیام‌های قدیمی‌تر</Button>}
        {messages.length >= 500 && <Typography variant="caption">حد نمایش این گفتگو ۵۰۰ پیام است.</Typography>}
        {peer && peer.peer_kind !== 'private' && <Alert severity="info">این کلاینت فعلاً خواندن و ارسال در گروه/کانال را پشتیبانی نمی‌کند.</Alert>}
        <Box sx={{ flex: 1, overflow: 'auto' }}>{messages.map(message => <Paper key={message.message_reference} variant="outlined" sx={{ p: 1.5, mb: 1 }}>
          <Typography sx={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{message.text}</Typography>
          {message.media_reference && <Button disabled={busy || !accounts.hasCapability('media.read')} onClick={() => void run(() => download(message))}>دریافت پیوست</Button>}
        </Paper>)}</Box>
        <TextField multiline label="متن پیام" value={text} onChange={event => setText(event.target.value)} />
        <Stack direction="row" gap={1}>
          <Button variant="contained" disabled={busy || !peer || peer.peer_kind !== 'private' || !text.trim() || !accounts.hasCapability('messages.send')} onClick={() => setConfirm({ label: `ارسال پیام به ${peer?.title}؟`, run: send })}>ارسال پیام</Button>
          <Button component="label" disabled={busy || !peer || peer.peer_kind !== 'private' || !accounts.hasCapability('media.send')}>انتخاب فایل<input hidden type="file" onChange={event => setDraftFile(event.target.files?.[0] || null)} /></Button>
          {draftFile && <Button disabled={busy} onClick={() => setConfirm({ label: `ارسال ${draftFile.name} به ${peer?.title}؟`, run: sendFile })}>ارسال فایل</Button>}
        </Stack>
      </Stack>
    </Stack>}
    {auth?.auth_state === 'authenticated' && view === 'contacts' && <Stack spacing={2}>
      <Stack direction="row" gap={1}><TextField label="جستجوی مخاطب" value={search} onChange={event => setSearch(event.target.value)} /><Button disabled={busy || !accounts.hasCapability('contacts.read')} onClick={() => void run(loadContacts)}>جستجو / تازه‌سازی</Button></Stack>
      <Stack direction="row" gap={1} flexWrap="wrap"><TextField label="شمارهٔ E.164 یا bale:user:شناسه" value={identity} onChange={event => setIdentity(event.target.value)} /><TextField label="نام مخاطب" value={name} onChange={event => setName(event.target.value)} />
        <Button disabled={busy || !identity || !name || !accounts.hasCapability('contacts.write')} onClick={() => setConfirm({ label: `افزودن مخاطب با نام ${name} در همین حساب بله؟`, run: async () => {
          await api('POST', `${base}/contacts/upsert`, { identity, display_name: name, idempotency_key: crypto.randomUUID(), confirm: true }); if (!alive.current) return; setIdentity(''); setName(''); await loadContacts()
        } })}>افزودن مخاطب</Button></Stack>
      {contacts.map(item => <Paper key={item.contact_reference} variant="outlined" sx={{ p: 1 }}><Stack direction="row" gap={2} alignItems="center">
        <Typography>{item.display_name || item.contact_reference}</Typography>
        <Button onClick={() => { setPeer({ peer_reference: item.contact_reference, peer_kind: 'private', title: item.display_name, unread_count: 0 }); setView('chat') }}>گفتگو</Button>
        <Button color="error" disabled={busy || !accounts.hasCapability('contacts.write')} onClick={() => setConfirm({ label: `حذف ${item.display_name || item.contact_reference} از مخاطبین همین حساب؟`, run: async () => { await api('POST', `${base}/contacts/remove`, { contact_reference: item.contact_reference, idempotency_key: crypto.randomUUID(), confirm: true }); if (alive.current) await loadContacts() } })}>حذف مخاطب</Button>
      </Stack></Paper>)}
    </Stack>}
    {view === 'settings' && <>
      <Alert severity={auth?.auth_state === 'authenticated' ? 'success' : 'info'}>آمادگی حساب بله: {auth?.auth_state === 'authenticated' ? 'نشست وارد شده' : 'ورود لازم است'} · Worker: {account.worker?.runtime_state || 'نامشخص'}</Alert>
      <MessengerAccountManagementPanel /><AccessManagementPanel /><ServiceAccountSettingsPanel />
      {auth?.auth_state === 'authenticated' && <Button color="warning" disabled={busy} onClick={() => setConfirm({ label: 'خروج از نشست بله همین حساب؟', run: () => authenticate('logout', { confirm: true }) })}>خروج از حساب بله</Button>}
    </>}
    <Dialog open={Boolean(confirm)} onClose={() => !busy && setConfirm(null)}><DialogTitle>تأیید عملیات</DialogTitle><DialogContent>{confirm?.label}</DialogContent><DialogActions>
      <Button disabled={busy} onClick={() => setConfirm(null)}>انصراف</Button><Button disabled={busy} onClick={() => { const operation = confirm; setConfirm(null); if (operation) void run(operation.run) }}>تأیید</Button>
    </DialogActions></Dialog>
  </Stack>
}
