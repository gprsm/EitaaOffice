import { useCallback, useEffect, useState } from 'react'
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  IconButton,
  List,
  ListItem,
  ListItemText,
  ListItemSecondaryAction,
  Stack,
  TextField,
  Typography
} from '@mui/material'
import ContentCopyIcon from '@mui/icons-material/ContentCopy'
import RotateRightIcon from '@mui/icons-material/RotateRight'
import DeleteIcon from '@mui/icons-material/Delete'
import AddIcon from '@mui/icons-material/Add'
import { api } from './lib/api'
import type { ProviderDescriptor } from './MessengerAccountGate'

type ServiceCredential = {
  id: string
  service_name: string
  description: string
  allowed_providers: string[]
  allowed_messenger_account_ids: string[] | null
  scopes: string[]
  created_at: string
  revoked_at: string | null
}

type AccountSummary = {
  messenger_account_id: string
  provider: string
  label: string | null
  phone_hint: string
}

type CredentialListResponse = { ok: true; credentials: ServiceCredential[] }
type TokenResponse = { ok: true; token: string; credential?: ServiceCredential }

const SCOPE_LABELS: Record<string, string> = {
  'messages.send': 'ارسال پیام',
  'contacts.resolve': 'بررسی مخاطبین',
  'agent.chat': 'چت نماینده هوشمند'
}

export const ServiceAccountSettingsPanel = () => {
  const [credentials, setCredentials] = useState<ServiceCredential[]>([])
  const [accounts, setAccounts] = useState<AccountSummary[]>([])
  const [providerAdapters, setProviderAdapters] = useState<Record<string, ProviderDescriptor>>({})
  const [loadError, setLoadError] = useState<string | null>(null)
  const [createOpen, setCreateOpen] = useState(false)
  const [serviceName, setServiceName] = useState('')
  const [selectedScopes, setSelectedScopes] = useState<string[]>([])
  const [selectedAccounts, setSelectedAccounts] = useState<string[]>([])
  const [selectedProviders, setSelectedProviders] = useState<string[]>([])
  const [newToken, setNewToken] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      const listed = await api<CredentialListResponse>('GET', '/api/v2/service-credentials')
      setCredentials(listed.credentials)
      try {
        const accountList = await api<{
          ok: true
          accounts: AccountSummary[]
          provider_adapters: Record<string, ProviderDescriptor>
        }>('GET', '/api/v2/messenger-accounts')
        setAccounts(accountList.accounts)
        setProviderAdapters(accountList.provider_adapters)
      } catch {
        // Account visibility depends on the active session; credentials stay usable.
      }
      setLoadError(null)
    } catch {
      setLoadError('خواندن فهرست گواهینامه‌های سرویس ممکن نشد؛ سطح دسترسی یا نشست را بررسی کنید.')
    }
  }, [])

  useEffect(() => { void load() }, [load])

  const resetDialog = () => {
    setServiceName('')
    setSelectedScopes([])
    setSelectedAccounts([])
    setSelectedProviders([])
    setNewToken(null)
    setActionError(null)
  }

  const handleCreate = async () => {
    setActionError(null)
    try {
      const created = await api<TokenResponse>('POST', '/api/v2/service-credentials', {
        service_name: serviceName.trim(),
        description: '',
        allowed_providers: selectedProviders,
        allowed_messenger_account_ids: selectedAccounts,
        scopes: selectedScopes
      })
      setNewToken(created.token)
      await load()
    } catch {
      setActionError('ایجاد گواهینامه ناموفق بود؛ نام سرویس و دسترسی‌ها را بررسی کنید.')
    }
  }

  const handleRotate = async (credentialId: string) => {
    setActionError(null)
    try {
      const rotated = await api<TokenResponse>('POST', `/api/v2/service-credentials/${credentialId}/rotate`)
      setNewToken(rotated.token)
      setCreateOpen(true)
      await load()
    } catch {
      setActionError('چرخش توکن ناموفق بود.')
    }
  }

  const handleRevoke = async (credentialId: string) => {
    setActionError(null)
    try {
      await api('POST', `/api/v2/service-credentials/${credentialId}/revoke`)
      await load()
    } catch {
      setActionError('ابطال گواهینامه ناموفق بود.')
    }
  }

  const chipFor = (provider: string, fallbackLabel: string, readyLabel: string, pendingLabel: string) => {
    const descriptor = providerAdapters[provider]
    if (!descriptor || !descriptor.configured || !descriptor.runtime_enabled) {
      if (
        descriptor &&
        descriptor.configured &&
        descriptor.implementation_state === 'implemented'
      ) {
        return <Chip label={pendingLabel} color="info" size="small" />
      }
      return <Chip label={fallbackLabel} color="warning" size="small" />
    }
    return <Chip label={readyLabel} color="success" size="small" />
  }

  return (
    <Box sx={{ p: 2, direction: 'rtl' }}>
      <Typography variant="h5" gutterBottom>تنظیمات سرویس‌های یکپارچه</Typography>
      {actionError && <Alert severity="error" sx={{ mb: 2 }}>{actionError}</Alert>}
      {loadError && <Alert severity="warning" sx={{ mb: 2 }}>{loadError}</Alert>}

      <Stack spacing={3}>
        <Card>
          <CardContent>
            <Typography variant="h6" gutterBottom>وضعیت سیستم</Typography>
            <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
              {chipFor('eitaa', 'ارسال ایتا: حساب فعال ندارد', 'ارسال ایتا: فعال', 'ارسال ایتا: در حال اتصال')}
              {chipFor('bale', 'ارسال بله: پیکربندی نشده', 'ارسال بله (شخصی): فعال', 'بله شخصی: مجاز — اتصال خودکار در فاز بعد')}
              <Chip label="نماینده هوشمند: حالت آزمایشی" color="info" size="small" />
            </Box>
          </CardContent>
        </Card>

        <Card>
          <CardContent>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 2 }}>
              <Typography variant="h6">گواهینامه‌های سرویس</Typography>
              <Button variant="contained" startIcon={<AddIcon />} onClick={() => { resetDialog(); setCreateOpen(true) }}>
                ایجاد
              </Button>
            </Box>
            {credentials.length === 0 && (
              <Typography variant="body2" color="text.secondary">هنوز گواهینامه‌ای ساخته نشده است.</Typography>
            )}
            <List>
              {credentials.map(cred => (
                <ListItem key={cred.id} divider>
                  <ListItemText
                    primary={cred.service_name}
                    secondary={
                      (cred.revoked_at ? 'ابطال‌شده' : 'فعال')
                      + ` | دامنه‌ها: ${cred.scopes.map(s => SCOPE_LABELS[s] || s).join('، ') || '—'}`
                    }
                  />
                  <ListItemSecondaryAction>
                    <IconButton
                      edge="end"
                      title="چرخش توکن"
                      disabled={cred.revoked_at !== null}
                      onClick={() => { void handleRotate(cred.id) }}
                    >
                      <RotateRightIcon />
                    </IconButton>
                    <IconButton
                      edge="end"
                      color="error"
                      title="ابطال"
                      disabled={cred.revoked_at !== null}
                      onClick={() => { void handleRevoke(cred.id) }}
                    >
                      <DeleteIcon />
                    </IconButton>
                  </ListItemSecondaryAction>
                </ListItem>
              ))}
            </List>
          </CardContent>
        </Card>
      </Stack>

      <Dialog open={createOpen} onClose={() => setCreateOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>{newToken ? 'توکن جدید' : 'ایجاد گواهینامه جدید'}</DialogTitle>
        <DialogContent>
          {!newToken ? (
            <Box sx={{ mt: 2 }}>
              <TextField
                fullWidth
                label="نام سرویس"
                variant="outlined"
                sx={{ mb: 3 }}
                value={serviceName}
                onChange={event => setServiceName(event.target.value)}
              />
              <Typography variant="subtitle1" gutterBottom>دامنهٔ دسترسی‌ها</Typography>
              <Stack direction="row" spacing={1} sx={{ mb: 3, flexWrap: 'wrap', gap: 1 }}>
                {Object.entries(SCOPE_LABELS).map(([scope, label]) => (
                  <Chip
                    key={scope}
                    label={label}
                    clickable
                    color={selectedScopes.includes(scope) ? 'primary' : 'default'}
                    onClick={() => setSelectedScopes(current =>
                      current.includes(scope) ? current.filter(item => item !== scope) : [...current, scope]
                    )}
                  />
                ))}
              </Stack>
              <Typography variant="subtitle1" gutterBottom>سرویس‌دهنده‌های مجاز</Typography>
              <Stack direction="row" spacing={1} sx={{ mb: 3, flexWrap: 'wrap', gap: 1 }}>
                {(Object.keys(providerAdapters).length > 0
                  ? Object.keys(providerAdapters)
                  : ['eitaa', 'bale']
                ).map(provider => (
                  <Chip
                    key={provider}
                    label={provider}
                    clickable
                    color={selectedProviders.includes(provider) ? 'primary' : 'default'}
                    onClick={() => setSelectedProviders(current =>
                      current.includes(provider) ? current.filter(item => item !== provider) : [...current, provider]
                    )}
                  />
                ))}
              </Stack>
              <Typography variant="subtitle1" gutterBottom>حساب‌های مجاز</Typography>
              <Stack direction="row" spacing={1} sx={{ flexWrap: 'wrap', gap: 1 }}>
                {accounts.map(account => {
                  const accountId = account.messenger_account_id
                  const selected = selectedAccounts.includes(accountId)
                  const hint = `${account.label || account.provider} (${account.phone_hint})`
                  return (
                    <Chip
                      key={accountId}
                      label={hint}
                      clickable
                      color={selected ? 'primary' : 'default'}
                      onClick={() => setSelectedAccounts(current =>
                        current.includes(accountId) ? current.filter(item => item !== accountId) : [...current, accountId]
                      )}
                    />
                  )
                })}
                {accounts.length === 0 && (
                  <Typography variant="body2" color="text.secondary">
                    حسابی برای انتساب نیست؛ ابتدا از بخش حساب‌های پیام‌رسان یک حساب فعال کنید.
                  </Typography>
                )}
              </Stack>
            </Box>
          ) : (
            <Box sx={{ mt: 2 }}>
              <Alert severity="warning" sx={{ mb: 2 }}>
                این توکن فقط همین یک‌بار نمایش داده می‌شود؛ پس از بستن این پنجره قابل بازیابی نیست.
              </Alert>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, bgcolor: 'background.default', p: 2, borderRadius: 1 }}>
                <Typography sx={{ fontFamily: 'monospace', wordBreak: 'break-all', flexGrow: 1 }}>
                  {newToken}
                </Typography>
                <IconButton
                  title="کپی توکن"
                  onClick={() => { void navigator.clipboard.writeText(newToken) }}
                >
                  <ContentCopyIcon />
                </IconButton>
              </Box>
            </Box>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setCreateOpen(false)}>بستن</Button>
          {!newToken && (
            <Button
              variant="contained"
              disabled={
                serviceName.trim().length < 3 ||
                selectedScopes.length === 0 ||
                selectedAccounts.length === 0 ||
                selectedProviders.length === 0
              }
              onClick={() => { void handleCreate() }}
            >
              ایجاد توکن
            </Button>
          )}
        </DialogActions>
      </Dialog>
    </Box>
  )
}
