import { useEffect, useRef, useState } from 'react'
import {
  Alert,
  Box,
  Button,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  IconButton,
  InputAdornment,
  List,
  ListItemAvatar,
  ListItemButton,
  ListItemText,
  Stack,
  TextField,
  Typography,
  useMediaQuery,
  useTheme,
} from '@mui/material'
import CloseRounded from '@mui/icons-material/CloseRounded'
import SearchRounded from '@mui/icons-material/SearchRounded'
import { api } from '../lib/api'
import { BaleAvatar } from './BaleConversationList'

type Contact = { contact_reference: string; display_name: string }
type ContactPage = { contacts: Contact[]; next_cursor?: string | null }

export function BaleContactDirectory({
  open,
  base,
  can,
  onClose,
  onOpenChat,
}: {
  open: boolean
  base: string
  can: (capability: string) => boolean
  onClose: () => void
  onOpenChat: (contact: Contact) => void
}) {
  const theme = useTheme()
  const fullScreen = useMediaQuery(theme.breakpoints.down('sm'))
  const alive = useRef(true)
  useEffect(() => {
    alive.current = true
    return () => { alive.current = false }
  }, [])
  const [contacts, setContacts] = useState<Contact[]>([])
  const [cursor, setCursor] = useState<string | null>(null)
  const [pagedQuery, setPagedQuery] = useState('')
  const [searchInput, setSearchInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [loadingMore, setLoadingMore] = useState(false)
  const [error, setError] = useState('')
  const [identity, setIdentity] = useState('')
  const [name, setName] = useState('')
  const [confirm, setConfirm] = useState<{ label: string; run: () => Promise<void> } | null>(null)
  const [busy, setBusy] = useState(false)
  const busyRef = useRef(false)

  const loadContacts = async () => {
    const selectedQuery = searchInput.trim()
    const result = await api<ContactPage>('POST', `${base}/contacts/${selectedQuery ? 'search' : 'query'}`,
      selectedQuery ? { query: selectedQuery, limit: 100 } : { limit: 100 })
    if (!alive.current) return
    setContacts(result.contacts)
    setCursor(result.next_cursor || null)
    setPagedQuery(selectedQuery)
  }
  const loadMoreContacts = async () => {
    if (!cursor) return
    const result = pagedQuery
      ? await api<ContactPage>('POST', `${base}/contacts/search`, { query: pagedQuery, limit: 100, cursor })
      : await api<ContactPage>('POST', `${base}/contacts/query`, { limit: 100, cursor })
    if (!alive.current) return
    setContacts(previous => {
      const existing = new Set(previous.map(item => item.contact_reference))
      return [...previous, ...result.contacts.filter(item => !existing.has(item.contact_reference))]
    })
    setCursor(result.next_cursor && result.next_cursor !== cursor ? result.next_cursor : null)
  }
  const run = async (callback: () => Promise<void>, pending: (value: boolean) => void = setLoading) => {
    if (busyRef.current || busy || loading || loadingMore) return
    busyRef.current = true
    pending(true); setError('')
    try { await callback() } catch (reason) {
      if (alive.current) setError(reason instanceof Error ? reason.message : 'خواندن مخاطبین انجام نشد.')
    } finally { busyRef.current = false; if (alive.current) pending(false) }
  }
  useEffect(() => {
    if (!open) return
    setContacts([]); setCursor(null); setPagedQuery(''); setSearchInput(''); setError(''); setIdentity(''); setName('')
    if (can('contacts.read')) void run(loadContacts)
    // A fresh page is fetched for every open so another account's rows never linger here.
  }, [open, base]) // eslint-disable-line react-hooks/exhaustive-deps

  const addContact = async () => {
    const cleanIdentity = identity.trim().replace(/\s+/g, '')
    await api('POST', `${base}/contacts/upsert`, { identity: cleanIdentity, display_name: name.trim(), idempotency_key: crypto.randomUUID(), confirm: true })
    if (!alive.current) return
    setIdentity(''); setName('')
    await loadContacts()
  }
  const removeContact = async (contact: Contact) => {
    await api('POST', `${base}/contacts/remove`, { contact_reference: contact.contact_reference, idempotency_key: crypto.randomUUID(), confirm: true })
    if (!alive.current) return
    await loadContacts()
  }

  return <Dialog open={open} onClose={() => { if (!busy && !loading && !loadingMore) onClose() }} fullScreen={fullScreen} fullWidth maxWidth="md">
    <DialogTitle component="div">
      <Stack direction="row" alignItems="center" justifyContent="space-between" gap={1}>
        <Box sx={{ minWidth: 0 }}>
          <Typography variant="h6" component="div" fontWeight={850}>دفترچهٔ مخاطبین بله</Typography>
          <Typography variant="caption" color="text.secondary">مخاطبین همین حساب بله؛ فهرست صفحه‌بندی‌شده است.</Typography>
        </Box>
        <IconButton onClick={onClose} aria-label="بستن دفترچهٔ مخاطبین" disabled={busy || loading || loadingMore}><CloseRounded /></IconButton>
      </Stack>
    </DialogTitle>
    <DialogContent dividers sx={{ bgcolor: 'background.default' }}>
      <Stack spacing={1.5} sx={{ pt: 0.5 }}>
        <Stack direction={{ xs: 'column', sm: 'row' }} gap={1}>
          <TextField
            size="small"
            fullWidth
            label="جست‌وجوی مخاطب"
            value={searchInput}
            onChange={event => setSearchInput(event.target.value)}
            onKeyDown={event => { if (event.key === 'Enter' && can('contacts.read')) void run(loadContacts) }}
            InputProps={{ startAdornment: <InputAdornment position="start"><SearchRounded fontSize="small" /></InputAdornment> }}
          />
          <Button variant="outlined" disabled={busy || loading || loadingMore || !can('contacts.read')} onClick={() => void run(loadContacts)}>جستجو / تازه‌سازی</Button>
        </Stack>
        {can('contacts.write') && <Stack component="section" aria-label="افزودن مخاطب" spacing={1} sx={{ p: 1.25, border: 1, borderColor: 'divider', borderRadius: 2, bgcolor: 'background.paper' }}>
          <Typography variant="subtitle2">افزودن مخاطب</Typography>
          <Stack direction={{ xs: 'column', sm: 'row' }} gap={1}>
            <TextField size="small" fullWidth label="شمارهٔ E.164 یا شناسهٔ بله" dir="auto" value={identity} onChange={event => setIdentity(event.target.value)} helperText="مثال: +989123456789 یا bale:user:123456" />
            <TextField size="small" fullWidth label="نام مخاطب" value={name} onChange={event => setName(event.target.value)} />
            <Button variant="contained" disabled={busy || !identity.trim() || !name.trim() || !can('contacts.write')}
              onClick={() => setConfirm({ label: `افزودن مخاطب با نام ${name.trim()} در همین حساب بله؟`, run: addContact })}
            >افزودن مخاطب</Button>
          </Stack>
        </Stack>}
        {error && <Alert severity="error" onClose={() => setError('')}>{error}</Alert>}
        {loading && !contacts.length && <Stack alignItems="center" spacing={1} sx={{ py: 4 }}><CircularProgress size={28} /><Typography variant="body2" color="text.secondary">در حال خواندن مخاطبین</Typography></Stack>}
        {!loading && !contacts.length && !error && <Typography color="text.secondary" sx={{ py: 3, textAlign: 'center' }}>مخاطبی در دفترچهٔ این حساب نیست.</Typography>}
        <List disablePadding>
          {contacts.map(item => <ListItemButton key={item.contact_reference} sx={{ borderRadius: 2, mb: 0.5, border: 1, borderColor: 'divider', bgcolor: 'background.paper' }} aria-label={`مخاطب ${item.display_name || item.contact_reference}`}>
            <ListItemAvatar><BaleAvatar title={item.display_name || 'م'} /></ListItemAvatar>
            <ListItemText
              primary={item.display_name || item.contact_reference}
              secondary={item.display_name ? item.contact_reference : undefined}
              primaryTypographyProps={{ fontWeight: 650, noWrap: true }}
              secondaryTypographyProps={{ noWrap: true, dir: 'ltr' }}
            />
            <Stack direction="row" gap={0.5}>
              <Button size="small" onClick={() => { onOpenChat(item); onClose() }}>گفتگو</Button>
              {can('contacts.write') && <Button size="small" color="error" disabled={busy || loading}
                onClick={() => setConfirm({ label: `حذف ${item.display_name || item.contact_reference} از مخاطبین همین حساب؟`, run: () => removeContact(item) })}
              >حذف</Button>}
            </Stack>
          </ListItemButton>)}
        </List>
        {cursor && <Button variant="outlined" disabled={busy || loading || loadingMore || !can('contacts.read')} onClick={() => void run(loadMoreContacts, setLoadingMore)}>{loadingMore ? 'در حال دریافت…' : pagedQuery ? 'نتایج بیشتر' : 'موارد بیشتر'}</Button>}
      </Stack>
    </DialogContent>
    <DialogActions sx={{ justifyContent: 'space-between', px: 2 }}>
      <Typography variant="caption" color="text.secondary">{contacts.length.toLocaleString('fa-IR')} مخاطب نمایش داده شده</Typography>
      <Button onClick={onClose} disabled={busy || loading || loadingMore}>بستن</Button>
    </DialogActions>
    <Dialog open={Boolean(confirm)} onClose={() => !busy && setConfirm(null)} fullWidth maxWidth="xs">
      <DialogTitle>تأیید عملیات</DialogTitle>
      <DialogContent>{confirm?.label}</DialogContent>
      <DialogActions>
        <Button disabled={busy} onClick={() => setConfirm(null)}>انصراف</Button>
        <Button disabled={busy} variant="contained" onClick={() => { const operation = confirm; setConfirm(null); if (operation) void run(async () => { await operation.run() }) }}>تأیید</Button>
      </DialogActions>
    </Dialog>
  </Dialog>
}
