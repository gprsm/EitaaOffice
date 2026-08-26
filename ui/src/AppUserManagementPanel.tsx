import { type FormEvent, useCallback, useEffect, useState } from 'react'
import {
  Alert,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Box,
  Button,
  Divider,
  MenuItem,
  Paper,
  Stack,
  TextField,
  Typography,
} from '@mui/material'
import { api } from './lib/api'
import { useAppUser } from './AppUserGate'
import { AccessManagementPanel } from './AccessManagementPanel'
import { SessionManagementPanel } from './SessionManagementPanel'

type ManagedAppUser = {
  app_user_id: string
  display_name: string
  global_role: 'admin' | 'user'
  status: 'active' | 'disabled' | 'archived'
  credential_configured: boolean
  active_session_count: number
}

export function AppUserManagementPanel() {
  const appUser = useAppUser()
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmation, setConfirmation] = useState('')
  const [passwordBusy, setPasswordBusy] = useState(false)
  const [passwordMessage, setPasswordMessage] = useState('')
  const [passwordError, setPasswordError] = useState('')

  if (!appUser.enabled || !appUser.principal) return null

  const changePassword = async (event: FormEvent) => {
    event.preventDefault()
    setPasswordMessage('')
    setPasswordError('')
    if (newPassword !== confirmation) {
      setPasswordError('تکرار رمز با رمز جدید یکسان نیست.')
      return
    }
    setPasswordBusy(true)
    try {
      await api('POST', '/api/v2/app-auth/change-password', {
        current_password: currentPassword,
        new_password: newPassword,
      })
      setCurrentPassword('')
      setNewPassword('')
      setConfirmation('')
      setPasswordMessage('رمز ورود تغییر کرد و نشست‌های دیگر این کاربر بسته شدند.')
    } catch (reason) {
      setPasswordError(reason instanceof Error ? reason.message : 'تغییر رمز ورود انجام نشد.')
    } finally {
      setPasswordBusy(false)
    }
  }

  return <Paper variant="outlined" sx={{ p: { xs: 2, md: 2.5 } }}>
    <Stack spacing={2.25}>
      <Box>
        <Typography variant="h6">کاربران و امنیت نرم‌افزار</Typography>
        <Typography variant="body2" color="text.secondary">
          ورود نرم‌افزار کاملاً از ورود حساب‌های ایتا و سایر پیام‌رسان‌ها جداست.
        </Typography>
      </Box>
      <Box component="form" onSubmit={changePassword}>
        <Stack spacing={1.5}>
          <Typography variant="subtitle1">تغییر رمز ورود من</Typography>
          <TextField
            label="رمز فعلی"
            type="password"
            value={currentPassword}
            onChange={event => setCurrentPassword(event.target.value)}
            autoComplete="current-password"
          />
          <TextField
            label="رمز جدید"
            type="password"
            value={newPassword}
            onChange={event => setNewPassword(event.target.value)}
            autoComplete="new-password"
            helperText="حداقل ۴ نویسه؛ رمز ۴ رقمی نیز پذیرفته می‌شود."
            inputProps={{ minLength: 4, maxLength: 128 }}
          />
          <TextField
            label="تکرار رمز جدید"
            type="password"
            value={confirmation}
            onChange={event => setConfirmation(event.target.value)}
            autoComplete="new-password"
          />
          {passwordError && <Alert severity="error">{passwordError}</Alert>}
          {passwordMessage && <Alert severity="success">{passwordMessage}</Alert>}
          <Button
            type="submit"
            variant="outlined"
            disabled={
              passwordBusy
              || !currentPassword
              || newPassword.length < 4
              || confirmation.length < 4
            }
          >
            {passwordBusy ? 'در حال تغییر…' : 'تغییر رمز ورود'}
          </Button>
        </Stack>
      </Box>
      <Divider />
      <SessionManagementPanel />
      {appUser.principal.permissions.manage_users && <>
        <Divider />
        <AppUserAdminPanel currentUserId={appUser.principal.app_user_id} />
        <Divider />
        <AccessManagementPanel />
      </>}
    </Stack>
  </Paper>
}

function AppUserAdminPanel({ currentUserId }: { currentUserId: string }) {
  const [users, setUsers] = useState<ManagedAppUser[]>([])
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [role, setRole] = useState<'admin' | 'user'>('user')
  const [createDialogOpen, setCreateDialogOpen] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const response = await api<{ users: ManagedAppUser[] }>('GET', '/api/v2/app-users')
      setUsers(response.users)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'فهرست کاربران دریافت نشد.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { void load() }, [load])

  const create = async (event: FormEvent) => {
    event.preventDefault()
    setBusy('create')
    setError('')
    setMessage('')
    try {
      await api('POST', '/api/v2/app-users', {
        display_name: displayName,
        username,
        password,
        global_role: role,
      })
      setDisplayName('')
      setUsername('')
      setPassword('')
      setRole('user')
      setMessage('کاربر جدید ساخته شد.')
      setCreateDialogOpen(false)
      await load()
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'ساخت کاربر انجام نشد.')
    } finally {
      setBusy('')
    }
  }

  const update = async (
    user: ManagedAppUser,
    change: Partial<Pick<ManagedAppUser, 'global_role' | 'status'>>,
  ) => {
    setBusy(user.app_user_id)
    setError('')
    setMessage('')
    try {
      await api(
        'POST',
        `/api/v2/app-users/${user.app_user_id}/update`,
        change,
      )
      setMessage('دسترسی کاربر به‌روزرسانی شد.')
      setCreateDialogOpen(false)
      await load()
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'تغییر دسترسی انجام نشد.')
    } finally {
      setBusy('')
    }
  }

  const revokeSessions = async (user: ManagedAppUser) => {
    setBusy(`sessions:${user.app_user_id}`)
    setError('')
    setMessage('')
    try {
      const result = await api<{ sessions_revoked: number }>(
        'POST', `/api/v2/app-users/${user.app_user_id}/revoke-sessions`,
      )
      setMessage(`${result.sessions_revoked.toLocaleString('fa-IR')} نشست فعال لغو شد.`)
      setCreateDialogOpen(false)
      await load()
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'لغو نشست‌ها انجام نشد.')
    } finally {
      setBusy('')
    }
  }

  return <Stack spacing={2}>
    <Box>
      <Typography variant="subtitle1">مدیریت کاربران</Typography>
      <Typography variant="body2" color="text.secondary">
        نام کاربری پس از ثبت دوباره نمایش داده نمی‌شود. رمز نیز فقط به‌صورت مشتق امن در همین رایانه نگهداری می‌شود.
      </Typography>
    </Box>
    <Stack spacing={1}>
      {loading && <Typography color="text.secondary">در حال دریافت کاربران…</Typography>}
      {!loading && users.map(user => <Paper
        key={user.app_user_id}
        variant="outlined"
        sx={{ p: 1.5 }}
      >
        <Stack direction={{ xs: 'column', md: 'row' }} spacing={1.25} alignItems={{ md: 'center' }}>
          <Box sx={{ flex: 1 }}>
            <Typography fontWeight={700}>
              {user.display_name}{user.app_user_id === currentUserId ? ' (شما)' : ''}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              {user.credential_configured ? 'ورود محلی آماده است' : 'رمز ورود تعریف نشده'}
            </Typography>
          </Box>
          <TextField
            select
            size="small"
            label="نقش"
            value={user.global_role}
            disabled={Boolean(busy)}
            onChange={event => void update(user, {
              global_role: event.target.value as 'admin' | 'user',
            })}
            sx={{ minWidth: 140 }}
          >
            <MenuItem value="admin">مدیر</MenuItem>
            <MenuItem value="user">کاربر</MenuItem>
          </TextField>
          <TextField
            select
            size="small"
            label="وضعیت"
            value={user.status}
            disabled={Boolean(busy)}
            onChange={event => void update(user, {
              status: event.target.value as 'active' | 'disabled',
            })}
            sx={{ minWidth: 140 }}
          >
            <MenuItem value="active">فعال</MenuItem>
            <MenuItem value="disabled">غیرفعال</MenuItem>
            {user.status === 'archived' && <MenuItem value="archived">بایگانی‌شده</MenuItem>}
          </TextField>
          <Button
            size="small"
            color="warning"
            disabled={Boolean(busy) || user.active_session_count < 1}
            onClick={() => void revokeSessions(user)}
          >
            {busy === `sessions:${user.app_user_id}`
              ? 'در حال لغو…'
              : `لغو نشست‌ها (${user.active_session_count.toLocaleString('fa-IR')})`}
          </Button>
        </Stack>
      </Paper>)}
    </Stack>
    
    <Divider />
    <Box>
      <Typography variant="subtitle1" sx={{ mb: 1.5 }}>ایجاد کاربر جدید</Typography>
      <Button variant="outlined" onClick={() => setCreateDialogOpen(true)}>
        افزودن حساب کاربری (AppUser)
      </Button>
    </Box>

    <Dialog open={createDialogOpen} onClose={() => setCreateDialogOpen(false)} fullWidth maxWidth="sm">
      <Box component="form" onSubmit={create}>
        <DialogTitle>افزودن حساب کاربری</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ pt: 1 }}>
            <TextField
              label="نام نمایشی"
              value={displayName}
              onChange={event => setDisplayName(event.target.value)}
              autoComplete="off"
            />
            <TextField
              label="نام کاربری نرم‌افزار"
              value={username}
              onChange={event => setUsername(event.target.value)}
              autoComplete="off"
              inputProps={{ dir: 'ltr', spellCheck: false }}
            />
            <TextField
              label="رمز عبور"
              type="password"
              value={password}
              onChange={event => setPassword(event.target.value)}
              autoComplete="new-password"
              inputProps={{ minLength: 4, maxLength: 128 }}
            />
            <TextField
              select
              label="نقش کاربری"
              value={role}
              onChange={event => setRole(event.target.value as 'admin' | 'user')}
            >
              <MenuItem value="user">کاربر عادی</MenuItem>
              <MenuItem value="admin">مدیر</MenuItem>
            </TextField>
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setCreateDialogOpen(false)} disabled={busy === 'create'}>انصراف</Button>
          <Button
            type="submit"
            variant="contained"
            disabled={
              busy === 'create'
              || !displayName.trim()
              || !username.trim()
              || password.length < 4
            }
          >
            {busy === 'create' ? 'در حال ایجاد...' : 'ایجاد کاربر'}
          </Button>
        </DialogActions>
      </Box>
    </Dialog>

  </Stack>
}
