import { useEffect, useMemo, useState } from 'react'
import { Alert, Box, Button, Chip, CircularProgress, Collapse, IconButton, MenuItem, Paper, Select, Stack, TextField, Tooltip, Typography } from '@mui/material'
import AttachFileRounded from '@mui/icons-material/AttachFileRounded'
import CloseRounded from '@mui/icons-material/CloseRounded'
import SendRounded from '@mui/icons-material/SendRounded'
import AutoAwesomeRounded from '@mui/icons-material/AutoAwesomeRounded'
import KeyboardArrowDownRounded from '@mui/icons-material/KeyboardArrowDownRounded'
import KeyboardArrowUpRounded from '@mui/icons-material/KeyboardArrowUpRounded'
import type { DialogItem } from './lib/types'
import { api } from './lib/api'

type SendMode = 'auto' | 'photo' | 'file'

type Props = {
  siteKey: string
  dialog: DialogItem | null
  onSent?: () => Promise<void> | void
}

const draftKey = (peerKey: string) => `eitaa-bridge.quick-send.${peerKey}`

export function QuickSendBar({ siteKey, dialog, onSent }: Props) {
  const [expanded, setExpanded] = useState(false)
  const [text, setText] = useState('')
  const [attachmentPath, setAttachmentPath] = useState<string | null>(null)
  const [attachmentName, setAttachmentName] = useState('')
  const [sendAs, setSendAs] = useState<SendMode>('auto')
  const [sending, setSending] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!dialog) { setText(''); setAttachmentPath(null); setAttachmentName(''); return }
    try {
      const saved = JSON.parse(localStorage.getItem(draftKey(dialog.peer_key)) || '{}')
      setText(typeof saved.text === 'string' ? saved.text : '')
      setSendAs(saved.sendAs === 'photo' || saved.sendAs === 'file' ? saved.sendAs : 'auto')
    } catch { setText(''); setSendAs('auto') }
    setAttachmentPath(null); setAttachmentName(''); setError('')
  }, [dialog?.peer_key])

  useEffect(() => {
    if (!dialog) return
    try { localStorage.setItem(draftKey(dialog.peer_key), JSON.stringify({ text, sendAs })) } catch { /* best effort */ }
  }, [dialog?.peer_key, text, sendAs])

  const canSend = Boolean(dialog && !sending && (text.trim() || attachmentPath))
  const title = useMemo(() => dialog?.peer.title || dialog?.peer.username || 'گفت‌وگو', [dialog])

  const chooseAttachment = async () => {
    setError('')
    try {
      const path = await window.eitaaDesktop.selectUploadFile({ title: 'انتخاب عکس یا فایل', filters: [{ name: 'همه فایل‌ها', extensions: ['*'] }] })
      if (!path) return
      setAttachmentPath(path)
      setAttachmentName(path.split(/[\\/]/).pop() || 'فایل انتخاب‌شده')
      setExpanded(true)
    } catch (exc) { setError(exc instanceof Error ? exc.message : 'انتخاب فایل ناموفق بود.') }
  }

  const send = async () => {
    if (!dialog || !canSend) return
    setSending(true); setError('')
    try {
      await api('POST', '/api/v1/messages/send', {
        site_key: siteKey,
        peer_file: dialog.peer_file,
        text: text.trim(),
        upload_path: attachmentPath,
        send_as: sendAs,
        cleanup_upload: true,
      })
      setText(''); setAttachmentPath(null); setAttachmentName(''); setSendAs('auto')
      try { localStorage.removeItem(draftKey(dialog.peer_key)) } catch { /* best effort */ }
      await onSent?.()
    } catch (exc) { setError(exc instanceof Error ? exc.message : 'ارسال پیام ناموفق بود.') }
    finally { setSending(false) }
  }

  return <Paper elevation={8} className="quick-send-shell" sx={{ borderRadius: 0, borderTop: 1, borderColor: 'divider', bgcolor: 'background.paper' }}>
    <Stack direction="row" alignItems="flex-end" spacing={1} sx={{ p: { xs: .75, sm: 1 }, minWidth: 0 }}>
      <Tooltip title={expanded ? 'جمع‌کردن ابزار ارسال' : 'نمایش ابزارهای بیشتر'}>
        <IconButton size="small" onClick={() => setExpanded(value => !value)} aria-label="نمایش ابزارهای ارسال">{expanded ? <KeyboardArrowDownRounded /> : <KeyboardArrowUpRounded />}</IconButton>
      </Tooltip>
      <TextField
        multiline
        maxRows={expanded ? 8 : 3}
        minRows={1}
        value={text}
        onChange={event => setText(event.target.value)}
        disabled={!dialog || sending}
        placeholder={dialog ? `نوشتن پیام برای ${title}` : 'ابتدا یک گفت‌وگو را انتخاب کنید'}
        onKeyDown={event => { if (event.key === 'Enter' && !event.shiftKey && canSend) { event.preventDefault(); void send() } }}
        sx={{ flex: 1, minWidth: 0, '& .MuiInputBase-root': { alignItems: 'flex-end' } }}
      />
      <Tooltip title="افزودن عکس یا فایل"><span><IconButton color={attachmentPath ? 'primary' : 'default'} disabled={!dialog || sending} onClick={() => void chooseAttachment()} aria-label="افزودن پیوست"><AttachFileRounded /></IconButton></span></Tooltip>
      <Tooltip title="ارسال"><span><IconButton color="primary" disabled={!canSend} onClick={() => void send()} aria-label="ارسال پیام" sx={{ width: 44, height: 44 }}>{sending ? <CircularProgress size={23} /> : <SendRounded />}</IconButton></span></Tooltip>
    </Stack>
    <Collapse in={expanded || Boolean(attachmentPath) || Boolean(error)}>
      <Box sx={{ px: { xs: 1, sm: 1.5 }, pb: 1.25 }}>
        {error && <Alert severity="error" sx={{ mb: 1 }}>{error}</Alert>}
        <Stack direction={{ xs: 'column', sm: 'row' }} alignItems={{ xs: 'stretch', sm: 'center' }} justifyContent="space-between" gap={1}>
          <Stack direction="row" gap={1} flexWrap="wrap" alignItems="center">
            {attachmentPath && <Chip label={attachmentName} onDelete={() => { setAttachmentPath(null); setAttachmentName('') }} deleteIcon={<CloseRounded />} />}
            {attachmentPath && <Select size="small" value={sendAs} onChange={event => setSendAs(event.target.value as SendMode)} sx={{ minWidth: 155 }}>
              <MenuItem value="auto">تشخیص خودکار</MenuItem><MenuItem value="photo">ارسال به‌صورت عکس</MenuItem><MenuItem value="file">ارسال به‌صورت فایل</MenuItem>
            </Select>}
          </Stack>
          <Tooltip title="زیرساخت تمپلیت در نسخه بعدی به این بخش متصل می‌شود">
            <Button disabled startIcon={<AutoAwesomeRounded />} variant="text">تمپلیت‌های پیام</Button>
          </Tooltip>
        </Stack>
        <Typography variant="caption" color="text.secondary">Enter برای ارسال و Shift+Enter برای رفتن به خط بعد. پیش‌نویس هر گفت‌وگو به‌صورت محلی نگه‌داری می‌شود.</Typography>
      </Box>
    </Collapse>
  </Paper>
}
