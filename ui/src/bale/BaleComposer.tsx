import { useEffect, useRef, useState } from 'react'
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Collapse,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  IconButton,
  Paper,
  Stack,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material'
import AttachFileRounded from '@mui/icons-material/AttachFileRounded'
import CloseRounded from '@mui/icons-material/CloseRounded'
import KeyboardArrowDownRounded from '@mui/icons-material/KeyboardArrowDownRounded'
import KeyboardArrowUpRounded from '@mui/icons-material/KeyboardArrowUpRounded'
import SendRounded from '@mui/icons-material/SendRounded'
import { api, scopedStorageKey } from '../lib/api'

const MAX_MEDIA_BYTES = 512 * 1024

export type BaleSendTarget = { peer_reference: string; peer_kind: string; title: string }

type SendPayload =
  | { kind: 'text'; peer: BaleSendTarget; text: string; idempotency_key: string }
  | { kind: 'media'; peer: BaleSendTarget; file: File; caption: string; idempotency_key: string }

export function BaleComposer({
  peer,
  unsupportedReason,
  canSendText,
  canSendMedia,
  capabilityLoading,
  capabilityError,
  send,
  onSent,
}: {
  peer: BaleSendTarget | null
  unsupportedReason: string
  canSendText: boolean
  canSendMedia: boolean
  capabilityLoading: boolean
  capabilityError: string
  send: (payload: SendPayload) => Promise<'succeeded' | 'uncertain'>
  onSent: () => void
}) {
  const alive = useRef(true)
  useEffect(() => {
    alive.current = true
    return () => { alive.current = false }
  }, [])
  const [expanded, setExpanded] = useState(false)
  const [text, setText] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [confirming, setConfirming] = useState<SendPayload | null>(null)
  const [sending, setSending] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const draftKey = peer ? scopedStorageKey(`eitaa-bridge.bale-composer.${peer.peer_reference}`) : ''

  useEffect(() => {
    setText(''); setFile(null); setError(''); setNotice('')
    if (!draftKey) return
    try {
      const saved = JSON.parse(localStorage.getItem(draftKey) || '{}')
      if (typeof saved.text === 'string') setText(saved.text)
    } catch { /* empty draft is fine */ }
  }, [draftKey])

  useEffect(() => {
    if (!draftKey) return
    try { localStorage.setItem(draftKey, JSON.stringify({ text })) } catch { /* best effort */ }
  }, [draftKey, text])

  const mediaBlocked = Boolean(file) && !canSendMedia
  const requestedSupported = file ? (canSendText && canSendMedia) : canSendText
  const canSend = Boolean(peer && !sending && requestedSupported && !unsupportedReason && (text.trim() || file))
  const targetLabel = peer?.title || 'گفتگو'

  const chooseFile = (chosen: File | null) => {
    setError(''); setNotice('')
    if (!chosen) return
    if (chosen.size > MAX_MEDIA_BYTES) {
      setFile(null)
      setError('حد فعلی هر فایل ۵۱۲ کیلوبایت است.')
      return
    }
    setFile(chosen)
    setExpanded(true)
  }

  const buildPayload = (): SendPayload | null => {
    if (!peer) return null
    const value = text.trim()
    if (file) return { kind: 'media', peer, file, caption: value, idempotency_key: crypto.randomUUID() }
    if (value) return { kind: 'text', peer, text: value, idempotency_key: crypto.randomUUID() }
    return null
  }

  const requestSend = () => {
    const payload = buildPayload()
    if (payload) { setError(''); setConfirming(payload) }
  }

  const runSend = async () => {
    const payload = confirming
    if (!payload || sending) return
    setConfirming(null)
    setSending(true); setError(''); setNotice('')
    try {
      const status = await send(payload)
      if (!alive.current) return
      if (payload.peer.peer_reference !== peer?.peer_reference) return
      setNotice(status === 'succeeded'
        ? 'پیام به سرویس بله ارسال شد؛ مشاهدهٔ گیرنده تأیید نشده است.'
        : 'نتیجهٔ ارسال نامعلوم است؛ ارسال خودکار تکرار نمی‌شود.')
      setText(''); setFile(null)
      onSent()
    } catch (reason) {
      if (alive.current) setError(reason instanceof Error ? reason.message : 'ارسال پیام ناموفق بود.')
    } finally {
      if (alive.current) setSending(false)
    }
  }

  return <Paper elevation={8} sx={{ borderRadius: 0, borderTop: 1, borderColor: 'divider', bgcolor: 'background.paper' }}>
    <Stack direction="row" alignItems="flex-end" spacing={1} sx={{ p: { xs: 0.75, sm: 1 }, minWidth: 0 }}>
      <Tooltip title={expanded ? 'جمع‌کردن ابزار ارسال' : 'نمایش ابزارهای بیشتر'}>
        <IconButton size="small" onClick={() => setExpanded(value => !value)} aria-label="نمایش ابزارهای ارسال">{expanded ? <KeyboardArrowDownRounded /> : <KeyboardArrowUpRounded />}</IconButton>
      </Tooltip>
      <TextField
        multiline
        maxRows={expanded ? 8 : 3}
        minRows={1}
        value={text}
        onChange={event => setText(event.target.value)}
        disabled={!peer || sending || !requestedSupported || Boolean(unsupportedReason)}
        placeholder={
          unsupportedReason ? unsupportedReason
            : !peer ? 'ابتدا یک گفتگو را انتخاب کنید'
              : !requestedSupported ? 'ارسال برای این حساب پشتیبانی نمی‌شود'
                : `نوشتن پیام برای ${targetLabel}`}
        onKeyDown={event => { if (event.key === 'Enter' && !event.shiftKey && canSend) { event.preventDefault(); requestSend() } }}
        sx={{ flex: 1, minWidth: 0, '& .MuiInputBase-root': { alignItems: 'flex-end' } }}
      />
      <Tooltip title={canSendMedia ? 'افزودن فایل' : 'ارسال فایل برای این حساب پشتیبانی نمی‌شود'}><span><IconButton color={file ? 'primary' : 'default'} disabled={!peer || sending || !canSendMedia || Boolean(unsupportedReason)} aria-label="افزودن پیوست" component="label"><AttachFileRounded /><input hidden type="file" onChange={event => chooseFile(event.target.files?.[0] || null)} /></IconButton></span></Tooltip>
      <Tooltip title="ارسال"><span><IconButton color="primary" disabled={!canSend} onClick={requestSend} aria-label="ارسال پیام" sx={{ width: 44, height: 44 }}>{sending ? <CircularProgress size={23} /> : <SendRounded />}</IconButton></span></Tooltip>
    </Stack>
    <Collapse in={expanded || Boolean(file) || Boolean(error) || Boolean(notice) || Boolean(capabilityError) || capabilityLoading || Boolean(unsupportedReason)}>
      <Box sx={{ px: { xs: 1, sm: 1.5 }, pb: 1.25 }}>
        {capabilityLoading && <Alert severity="info" sx={{ mb: 1 }}>در حال بررسی قابلیت‌های حساب…</Alert>}
        {capabilityError && <Alert severity="warning" sx={{ mb: 1 }}>{capabilityError}</Alert>}
        {unsupportedReason && <Alert severity="info" sx={{ mb: 1 }}>{unsupportedReason}</Alert>}
        {!capabilityLoading && !canSendText && !unsupportedReason && <Alert severity="info" sx={{ mb: 1 }}>ارسال پیام برای حساب انتخاب‌شده غیرفعال است.</Alert>}
        {mediaBlocked && <Alert severity="info" sx={{ mb: 1 }}>ارسال فایل برای حساب انتخاب‌شده غیرفعال است.</Alert>}
        {error && <Alert severity="error" sx={{ mb: 1 }}>{error}</Alert>}
        {notice && <Alert severity="success" sx={{ mb: 1 }}>{notice}</Alert>}
        <Stack direction="row" gap={1} flexWrap="wrap" alignItems="center">
          {file && <Chip label={`${file.name} · ${(file.size / 1024).toFixed(0)} کیلوبایت`} onDelete={sending ? undefined : () => setFile(null)} deleteIcon={<CloseRounded />} />}
        </Stack>
        <Typography variant="caption" color="text.secondary">Enter برای ارسال و Shift+Enter برای رفتن به خط بعد. پیش‌نویس فقط برای همین حساب و همین گفتگو نگه‌داری می‌شود.</Typography>
      </Box>
    </Collapse>
    <Dialog open={Boolean(confirming)} onClose={() => !sending && setConfirming(null)} fullWidth maxWidth="xs">
      <DialogTitle>تأیید ارسال</DialogTitle>
      <DialogContent>
        <Stack spacing={1} sx={{ pt: 0.5 }}>
          <Typography>گیرنده: <strong>{confirming?.peer.title}</strong></Typography>
          {confirming?.kind === 'text' && <Typography sx={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{confirming.text}</Typography>}
          {confirming?.kind === 'media' && <Typography>{confirming.file.name}{confirming.caption ? ` — ${confirming.caption}` : ''}</Typography>}
          <Typography variant="caption" color="text.secondary">پیام با شناسهٔ ارسال یکتا ثبت می‌شود؛ خطای شبکه باعث ارسال دوبارهٔ خودکار نمی‌شود.</Typography>
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button disabled={sending} onClick={() => setConfirming(null)}>انصراف</Button>
        <Button disabled={sending} variant="contained" onClick={() => void runSend()}>ارسال</Button>
      </DialogActions>
    </Dialog>
  </Paper>
}
