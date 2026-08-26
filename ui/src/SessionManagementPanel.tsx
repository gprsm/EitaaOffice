import { useCallback, useEffect, useMemo, useState } from 'react'
import { Alert, Box, Button, Chip, Paper, Stack, Typography } from '@mui/material'
import { api } from './lib/api'
import { useAppUser } from './AppUserGate'

type SafeSession = {
  session_id: string
  current: boolean
  status: 'active' | 'revoked' | 'expired'
  client_kind: 'electron' | 'browser' | 'api' | 'test'
  device_label: string
  created_at: string
  last_seen_at: string
  idle_expires_at: string
  absolute_expires_at: string
  revoked_at: string | null
  safe_reason_code: string | null
  expires_soon: boolean
  recent_login: boolean
}

const dateTime = new Intl.DateTimeFormat('fa-IR', {
  year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
})

const formatTime = (value: string) => {
  try { return dateTime.format(new Date(value)) }
  catch { return value }
}

const statusLabel = (session: SafeSession) => {
  if (session.status === 'active') return session.current ? 'نشست جاری' : 'فعال'
  if (session.status === 'expired') return 'منقضی'
  return 'لغوشده'
}

export function SessionManagementPanel() {
  const appUser = useAppUser()
  const [sessions, setSessions] = useState<SafeSession[]>([])
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')

  const load = useCallback(async () => {
    setError('')
    try {
      const response = await api<{ sessions: SafeSession[] }>('GET', '/api/v2/app-auth/sessions')
      setSessions(response.sessions)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'فهرست نشست‌ها دریافت نشد.')
    }
  }, [])

  useEffect(() => { void load() }, [load])

  const recentLogin = useMemo(() => sessions.some(item => item.recent_login), [sessions])
  const expiring = useMemo(() => sessions.some(item => item.current && item.expires_soon), [sessions])

  const revoke = async (session: SafeSession) => {
    const prompt = session.current
      ? 'نشست جاری بسته شود؟ برای ادامه باید دوباره وارد نرم‌افزار شوید.'
      : `نشست «${session.device_label}» بسته شود؟`
    if (!window.confirm(prompt)) return
    setBusy(session.session_id); setError(''); setMessage('')
    try {
      const result = await api<{ current_session_revoked: boolean }>(
        'POST', `/api/v2/app-auth/sessions/${session.session_id}/revoke`,
      )
      if (result.current_session_revoked) {
        await appUser.refresh()
        return
      }
      setMessage('نشست انتخاب‌شده لغو شد.')
      await load()
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'لغو نشست انجام نشد.')
    } finally {
      setBusy('')
    }
  }

  const logoutAll = async () => {
    if (!window.confirm('همهٔ نشست‌های شما، از جمله این دستگاه، بسته شوند؟')) return
    setBusy('all'); setError(''); setMessage('')
    try {
      await api('POST', '/api/v2/app-auth/logout-all')
      await appUser.refresh()
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'خروج از همهٔ دستگاه‌ها انجام نشد.')
    } finally {
      setBusy('')
    }
  }

  return <Stack spacing={1.5}>
    <Box>
      <Typography variant="subtitle1">نشست‌های دستگاه‌های من</Typography>
      <Typography variant="body2" color="text.secondary">
        فقط نوع دستگاه و زمان‌های امنیتی نمایش داده می‌شود؛ Token و نشانی IP در این فهرست وجود ندارد.
      </Typography>
    </Box>
    {recentLogin && <Alert severity="warning">در پانزده دقیقهٔ اخیر نشست فعال دیگری برای حساب شما ایجاد شده است.</Alert>}
    {expiring && <Alert severity="info">نشست جاری کمتر از ده دقیقه تا انقضای بعدی فاصله دارد.</Alert>}
    {error && <Alert severity="error">{error}</Alert>}
    {message && <Alert severity="success">{message}</Alert>}
    {sessions.map(session => <Paper key={session.session_id} variant="outlined" sx={{ p: 1.5 }}>
      <Stack direction={{ xs: 'column', md: 'row' }} spacing={1.25} alignItems={{ md: 'center' }}>
        <Box sx={{ flex: 1 }}>
          <Stack direction="row" gap={1} alignItems="center" flexWrap="wrap">
            <Typography fontWeight={700}>{session.device_label}</Typography>
            <Chip
              size="small"
              label={statusLabel(session)}
              color={session.status === 'active' ? 'success' : 'default'}
            />
          </Stack>
          <Typography variant="caption" color="text.secondary" component="div">
            آخرین فعالیت: {formatTime(session.last_seen_at)} · ورود: {formatTime(session.created_at)}
          </Typography>
          {session.status === 'active' && <Typography variant="caption" color="text.secondary" component="div">
            انقضای عدم فعالیت: {formatTime(session.idle_expires_at)} · انقضای قطعی: {formatTime(session.absolute_expires_at)}
          </Typography>}
        </Box>
        {session.status === 'active' && <Button
          size="small"
          color={session.current ? 'warning' : 'error'}
          disabled={Boolean(busy)}
          onClick={() => void revoke(session)}
        >{busy === session.session_id ? 'در حال خروج…' : session.current ? 'خروج این دستگاه' : 'خروج این نشست'}</Button>}
      </Stack>
    </Paper>)}
    <Stack direction="row" justifyContent="space-between" alignItems="center" gap={1} flexWrap="wrap">
      <Button size="small" onClick={() => void load()} disabled={Boolean(busy)}>تازه‌سازی نشست‌ها</Button>
      <Button size="small" color="error" variant="outlined" onClick={() => void logoutAll()} disabled={Boolean(busy)}>
        {busy === 'all' ? 'در حال خروج…' : 'خروج از همهٔ دستگاه‌ها'}
      </Button>
    </Stack>
  </Stack>
}
