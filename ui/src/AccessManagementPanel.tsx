import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Alert,
  Box,
  Button,
  Chip,
  Divider,
  MenuItem,
  Paper,
  Stack,
  TextField,
  Typography,
} from '@mui/material'
import { api } from './lib/api'

type ManagedUser = {
  app_user_id: string
  display_name: string
  global_role: 'admin' | 'user'
  status: 'active' | 'disabled' | 'archived'
}

type Membership = {
  membership_id: string
  app_user_id: string
  display_name: string
  global_role: 'admin' | 'user'
  app_user_status: 'active' | 'disabled' | 'archived'
  role: 'owner' | 'operator' | 'viewer'
  status: 'active' | 'revoked'
}

type PhoneAccount = {
  phone_account_id: string
  phone_hint: string
  status: 'active' | 'disabled' | 'archived'
  messenger_accounts: Array<{
    messenger_account_id: string
    provider: string
    label: string | null
    lifecycle_state: string
  }>
  memberships: Membership[]
}

type AppIntegration = {
  integration_id: string
  integration_type: 'wordpress'
  integration_key: string
  display_name: string
  status: 'active' | 'disabled' | 'archived'
}

const roleLabel = (role: Membership['role']) => ({
  owner: 'مالک', operator: 'اپراتور', viewer: 'مشاهده‌گر',
}[role])

export function AccessManagementPanel() {
  const [users, setUsers] = useState<ManagedUser[]>([])
  const [phones, setPhones] = useState<PhoneAccount[]>([])
  const [integrations, setIntegrations] = useState<AppIntegration[]>([])
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [selectedUsers, setSelectedUsers] = useState<Record<string, string>>({})
  const [selectedRoles, setSelectedRoles] = useState<Record<string, Membership['role']>>({})

  const load = useCallback(async () => {
    setError('')
    try {
      const [userResult, phoneResult, integrationResult] = await Promise.all([
        api<{ users: ManagedUser[] }>('GET', '/api/v2/app-users'),
        api<{ phone_accounts: PhoneAccount[] }>('GET', '/api/v2/phone-accounts'),
        api<{ integrations: AppIntegration[] }>('GET', '/api/v2/app-integrations'),
      ])
      setUsers(userResult.users)
      setPhones(phoneResult.phone_accounts)
      setIntegrations(integrationResult.integrations)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'اطلاعات دسترسی دریافت نشد.')
    }
  }, [])

  useEffect(() => { void load() }, [load])

  const activeUsers = useMemo(
    () => users.filter(user => user.status === 'active'),
    [users],
  )

  const updateMembership = async (
    phone: PhoneAccount,
    userId: string,
    role: Membership['role'],
    status: Membership['status'],
  ) => {
    const key = `membership:${phone.phone_account_id}:${userId}`
    setBusy(key); setError(''); setMessage('')
    try {
      await api('POST', `/api/v2/phone-accounts/${phone.phone_account_id}/memberships`, {
        app_user_id: userId,
        role,
        status,
      })
      setMessage('دسترسی PhoneAccount به‌روزرسانی و نشست‌های قدیمی کاربر لغو شد.')
      await load()
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'تغییر دسترسی انجام نشد.')
    } finally {
      setBusy('')
    }
  }

  const updateIntegration = async (integration: AppIntegration) => {
    const key = `integration:${integration.integration_id}`
    setBusy(key); setError(''); setMessage('')
    try {
      await api('POST', `/api/v2/app-integrations/${integration.integration_id}/update`, {
        status: integration.status === 'active' ? 'disabled' : 'active',
      })
      setMessage('وضعیت اتصال مشترک WordPress تغییر کرد.')
      await load()
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'وضعیت اتصال تغییر نکرد.')
    } finally {
      setBusy('')
    }
  }

  return <Stack spacing={2.25}>
    <Box>
      <Typography variant="subtitle1">PhoneAccount و دسترسی کاربران</Typography>
      <Typography variant="body2" color="text.secondary">
        شماره‌ها فقط به‌صورت پوشیده نمایش داده می‌شوند. مالک و اپراتور امکان عملیات دارند و مشاهده‌گر فقط وضعیت و داده‌های مجاز را می‌بیند.
      </Typography>
    </Box>
    {error && <Alert severity="error">{error}</Alert>}
    {message && <Alert severity="success">{message}</Alert>}
    {!phones.length && <Alert severity="info">هنوز PhoneAccount قابل مدیریتی وجود ندارد.</Alert>}
    {phones.map(phone => {
      const assigned = new Set(phone.memberships.map(item => item.app_user_id))
      const candidates = activeUsers.filter(user => !assigned.has(user.app_user_id))
      const selectedUser = selectedUsers[phone.phone_account_id] || candidates[0]?.app_user_id || ''
      const selectedRole = selectedRoles[phone.phone_account_id] || 'viewer'
      return <Paper key={phone.phone_account_id} variant="outlined" sx={{ p: 1.75 }}>
        <Stack spacing={1.5}>
          <Stack direction={{ xs: 'column', sm: 'row' }} justifyContent="space-between" gap={1}>
            <Box>
              <Typography fontWeight={800} dir="ltr">{phone.phone_hint}</Typography>
              <Typography variant="caption" color="text.secondary">
                {phone.messenger_accounts.map(item => item.label || item.provider).join(' · ') || 'بدون حساب پیام‌رسان'}
              </Typography>
            </Box>
            <Chip size="small" label={phone.status === 'active' ? 'فعال' : 'غیرفعال'} color={phone.status === 'active' ? 'success' : 'default'} />
          </Stack>
          {phone.memberships.map(membership => <Stack
            key={membership.membership_id}
            direction={{ xs: 'column', md: 'row' }}
            spacing={1}
            alignItems={{ md: 'center' }}
          >
            <Box sx={{ flex: 1 }}>
              <Typography variant="body2" fontWeight={700}>{membership.display_name}</Typography>
              <Typography variant="caption" color="text.secondary">
                {membership.app_user_status === 'active' ? 'کاربر فعال' : 'کاربر غیرفعال'}
              </Typography>
            </Box>
            <TextField
              select size="small" label="نقش PhoneAccount" value={membership.role}
              disabled={Boolean(busy) || membership.status === 'revoked'}
              onChange={event => void updateMembership(
                phone,
                membership.app_user_id,
                event.target.value as Membership['role'],
                membership.status,
              )}
              sx={{ minWidth: 155 }}
            >
              <MenuItem value="owner">مالک</MenuItem>
              <MenuItem value="operator">اپراتور</MenuItem>
              <MenuItem value="viewer">مشاهده‌گر</MenuItem>
            </TextField>
            <Button
              size="small"
              color={membership.status === 'active' ? 'warning' : 'success'}
              disabled={Boolean(busy) || membership.app_user_status !== 'active'}
              onClick={() => void updateMembership(
                phone,
                membership.app_user_id,
                membership.role,
                membership.status === 'active' ? 'revoked' : 'active',
              )}
            >
              {busy === `membership:${phone.phone_account_id}:${membership.app_user_id}`
                ? 'در حال ثبت…'
                : membership.status === 'active' ? 'لغو دسترسی' : `فعال‌سازی ${roleLabel(membership.role)}`}
            </Button>
          </Stack>)}
          {!!candidates.length && <>
            <Divider />
            <Stack direction={{ xs: 'column', md: 'row' }} spacing={1} alignItems={{ md: 'center' }}>
              <TextField
                select size="small" label="کاربر" value={selectedUser}
                onChange={event => setSelectedUsers(current => ({
                  ...current, [phone.phone_account_id]: String(event.target.value),
                }))}
                sx={{ flex: 1, minWidth: 180 }}
              >
                {candidates.map(user => <MenuItem key={user.app_user_id} value={user.app_user_id}>{user.display_name}</MenuItem>)}
              </TextField>
              <TextField
                select size="small" label="نقش" value={selectedRole}
                onChange={event => setSelectedRoles(current => ({
                  ...current,
                  [phone.phone_account_id]: event.target.value as Membership['role'],
                }))}
                sx={{ minWidth: 150 }}
              >
                <MenuItem value="owner">مالک</MenuItem>
                <MenuItem value="operator">اپراتور</MenuItem>
                <MenuItem value="viewer">مشاهده‌گر</MenuItem>
              </TextField>
              <Button
                variant="outlined" disabled={!selectedUser || Boolean(busy)}
                onClick={() => void updateMembership(phone, selectedUser, selectedRole, 'active')}
              >افزودن دسترسی</Button>
            </Stack>
          </>}
        </Stack>
      </Paper>
    })}
    <Divider />
    <Box>
      <Typography variant="subtitle1">اتصال مشترک WordPress</Typography>
      <Typography variant="body2" color="text.secondary">
        مشخصات ورود فقط در سرور نگهداری می‌شود؛ این صفحه صرفاً نام و وضعیت اتصال نصب را نمایش می‌دهد.
      </Typography>
    </Box>
    {!integrations.length && <Alert severity="info">اتصال WordPress پیکربندی نشده است.</Alert>}
    {integrations.map(integration => <Paper key={integration.integration_id} variant="outlined" sx={{ p: 1.5 }}>
      <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1} alignItems={{ sm: 'center' }}>
        <Box sx={{ flex: 1 }}>
          <Typography fontWeight={700}>{integration.display_name}</Typography>
          <Typography variant="caption" color="text.secondary">WordPress · {integration.integration_key}</Typography>
        </Box>
        <Chip size="small" label={integration.status === 'active' ? 'در دسترس همهٔ کاربران فعال' : 'غیرفعال'} color={integration.status === 'active' ? 'success' : 'default'} />
        {integration.status !== 'archived' && <Button
          size="small" disabled={Boolean(busy)}
          color={integration.status === 'active' ? 'warning' : 'success'}
          onClick={() => void updateIntegration(integration)}
        >{busy === `integration:${integration.integration_id}` ? 'در حال ثبت…' : integration.status === 'active' ? 'غیرفعال‌کردن' : 'فعال‌کردن'}</Button>}
      </Stack>
    </Paper>)}
  </Stack>
}
