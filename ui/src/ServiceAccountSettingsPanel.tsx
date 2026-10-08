import { useCallback, useEffect, useState } from 'react'
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Checkbox,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControl,
  FormControlLabel,
  IconButton,
  InputLabel,
  List,
  ListItem,
  ListItemText,
  ListItemSecondaryAction,
  MenuItem,
  Select,
  Stack,
  Switch,
  TextField,
  Typography
} from '@mui/material'
import ContentCopyIcon from '@mui/icons-material/ContentCopy'
import RotateRightIcon from '@mui/icons-material/RotateRight'
import DeleteIcon from '@mui/icons-material/Delete'
import AddIcon from '@mui/icons-material/Add'
import { api, ApiError } from './lib/api'
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
  auth_state?: string
  lifecycle_state?: string
  desired_worker_state?: string
  worker?: { runtime_state: string } | null
}

type SenderProfile = {
  id: string
  service_credential_id: string
  intent: string
  provider: string
  messenger_account_id: string
  enabled: boolean
  revision: number
  updated_at: string
  account_available: boolean
}

type ProfileDraft = {
  provider: string
  accountId: string
  enabled: boolean
}

type CredentialListResponse = { ok: true; credentials: ServiceCredential[] }
type TokenResponse = { ok: true; token: string; credential?: ServiceCredential }
type SenderProfileListResponse = { ok: true; profiles: SenderProfile[] }

type AiConnectionSettingsState = {
  enabled: boolean
  provider_dialect: string
  endpoint: string
  model_id: string
  display_name: string
  timeout_seconds: number
  max_input_length: number
  max_output_tokens: number
  concurrency_limit: number
  key_configured: boolean
  connection_status: string
  revision: number
  updated_at: string
}

type AiDataPolicyState = {
  service_id: string
  policy_level: 'disabled' | 'current_message' | 'limited_history' | 'approved_context'
  max_history_turns: number
  allowed_context_types: string[]
  revision: number
  updated_at: string
}

const SCOPE_LABELS: Record<string, string> = {
  'messages.send': 'ارسال پیام',
  'contacts.resolve': 'بررسی مخاطبین',
  'contacts.import': 'افزودن مخاطب با نام برای OTP',
  'messages.status': 'وضعیت ارسال',
  'agent.chat': 'چت نماینده هوشمند'
}

const SENDER_INTENTS = ['otp', 'notification']

const SENDER_INTENT_LABELS: Record<string, string> = {
  otp: 'فرستندهٔ کد یک‌بارمصرف (OTP)',
  notification: 'فرستندهٔ اطلاع‌رسانی'
}

const PROVIDER_LABELS: Record<string, string> = {
  eitaa: 'ایتا',
  bale: 'بله'
}

const accountAvailabilityLabel = (account: AccountSummary | undefined) => {
  if (!account) return 'وضعیت نامشخص'
  if (account.lifecycle_state && account.lifecycle_state !== 'active' && account.lifecycle_state !== 'created') {
    return `وضعیت حساب: ${account.lifecycle_state}`
  }
  if (account.auth_state === 'authenticated') return 'احراز شده'
  if (account.auth_state === 'absent' || !account.auth_state) return 'ورود حساب انجام نشده است'
  return `وضعیت ورود: ${account.auth_state}`
}

export const ServiceAccountSettingsPanel = () => {
  const [credentials, setCredentials] = useState<ServiceCredential[]>([])
  const [accounts, setAccounts] = useState<AccountSummary[]>([])
  const [providerAdapters, setProviderAdapters] = useState<Record<string, ProviderDescriptor>>({})
  const [senderProfiles, setSenderProfiles] = useState<SenderProfile[]>([])
  const [senderDrafts, setSenderDrafts] = useState<Record<string, ProfileDraft>>({})
  const [loadError, setLoadError] = useState<string | null>(null)
  const [createOpen, setCreateOpen] = useState(false)
  const [serviceName, setServiceName] = useState('')
  const [selectedScopes, setSelectedScopes] = useState<string[]>([])
  const [selectedAccounts, setSelectedAccounts] = useState<string[]>([])
  const [selectedProviders, setSelectedProviders] = useState<string[]>([])
  const [newToken, setNewToken] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)

  const [aiSettings, setAiSettings] = useState<AiConnectionSettingsState | null>(null)
  const [aiDraft, setAiDraft] = useState<Partial<AiConnectionSettingsState>>({})
  const [aiSecretKey, setAiSecretKey] = useState('')
  const [aiBusy, setAiBusy] = useState(false)
  const [aiProbeResult, setAiProbeResult] = useState<{ ok: boolean; message: string } | null>(null)
  const [aiMessage, setAiMessage] = useState<string | null>(null)
  const [servicePolicies, setServicePolicies] = useState<Record<string, AiDataPolicyState>>({})
  const [policyDrafts, setPolicyDrafts] = useState<Record<string, Partial<AiDataPolicyState>>>({})

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
      try {
        const profileList = await api<SenderProfileListResponse>('GET', '/api/v2/service-sender-profiles')
        const profiles = profileList.profiles
        setSenderProfiles(profiles)
        setSenderDrafts(prev => {
          const next: Record<string, ProfileDraft> = {}
          for (const cred of listed.credentials.filter(item => !item.revoked_at)) {
            for (const intent of SENDER_INTENTS) {
              const key = `${cred.id}:${intent}`
              const existing = profiles.find(
                profile => profile.service_credential_id === cred.id && profile.intent === intent
              )
              next[key] = prev[key] ?? (existing
                ? { provider: existing.provider, accountId: existing.messenger_account_id, enabled: existing.enabled }
                : { provider: '', accountId: '', enabled: true })
            }
          }
          return next
        })
      } catch {
        // Sender profile management needs the admin session; credentials stay usable.
      }
      try {
        const aiRes = await api<{ ok: true; connection: AiConnectionSettingsState }>('GET', '/api/v2/admin/ai-connection')
        setAiSettings(aiRes.connection)
        setAiDraft(aiRes.connection)
      } catch {
        // AI settings require admin session
      }
      try {
        const polMap: Record<string, AiDataPolicyState> = {}
        const draftMap: Record<string, Partial<AiDataPolicyState>> = {}
        for (const cred of listed.credentials.filter(c => !c.revoked_at)) {
          try {
            const pRes = await api<{ ok: true; policy: AiDataPolicyState }>(
              'GET',
              `/api/v2/admin/ai-data-policy/${cred.service_name}`
            )
            polMap[cred.service_name] = pRes.policy
            draftMap[cred.service_name] = { ...pRes.policy }
          } catch {
            // Service policy unconfigured or non-admin
          }
        }
        setServicePolicies(polMap)
        setPolicyDrafts(draftMap)
      } catch {
        // Ignore
      }
      setLoadError(null)
    } catch {
      setLoadError('خواندن فهرست گواهینامه‌های سرویس ممکن نشد؛ سطح دسترسی یا نشست را بررسی کنید.')
    }
  }, [])

  useEffect(() => { void load() }, [load])

  const updateSenderDraft = (key: string, patch: Partial<ProfileDraft>) => {
    setSenderDrafts(current => ({
      ...current,
      [key]: { ...(current[key] ?? { provider: '', accountId: '', enabled: true }), ...patch }
    }))
  }

  const handleSenderProfileSave = async (credential: ServiceCredential, intent: string) => {
    const key = `${credential.id}:${intent}`
    const draft = senderDrafts[key]
    if (!draft || !draft.provider || !draft.accountId) return
    setActionError(null)
    const existing = senderProfiles.find(
      profile => profile.service_credential_id === credential.id && profile.intent === intent
    )
    try {
      await api('PUT', '/api/v2/service-sender-profiles', {
        service_credential_id: credential.id,
        intent,
        provider: draft.provider,
        messenger_account_id: draft.accountId,
        enabled: draft.enabled,
        expected_revision: existing ? existing.revision : null
      })
      await load()
    } catch (error) {
      if (error instanceof ApiError && error.code === 'stale_revision') {
        setActionError('این پروفایل هم‌زمان در جای دیگری ویرایش شده است؛ فهرست به‌روزرسانی شد، دوباره تلاش کنید.')
      } else if (error instanceof ApiError && error.code === 'sender_profile_revision_required') {
        setActionError('برای ویرایش، شمارهٔ نسخهٔ فعلی لازم است؛ فهرست به‌روزرسانی شد.')
      } else if (error instanceof ApiError && error.code === 'm2m_account_not_allowed') {
        setActionError('حساب انتخاب‌شده در فهرست مجاز این گواهینامه نیست.')
      } else if (error instanceof ApiError && error.code === 'sender_profile_provider_mismatch') {
        setActionError('حساب انتخاب‌شده متعلق به سرویس‌دهندهٔ انتخاب‌شده نیست.')
      } else {
        setActionError('ذخیرهٔ فرستندهٔ هدف ناموفق بود؛ ورودی‌ها را بررسی کنید.')
      }
      await load()
    }
  }

  const handleSenderProfileDelete = async (profile: SenderProfile) => {
    setActionError(null)
    try {
      await api('DELETE', `/api/v2/service-sender-profiles/${profile.id}`)
      await load()
    } catch (error) {
      if (error instanceof ApiError && error.code === 'stale_revision') {
        setActionError('این پروفایل هم‌زمان تغییر کرده است؛ فهرست به‌روزرسانی شد.')
      } else {
        setActionError('حذف فرستندهٔ هدف ناموفق بود.')
      }
      await load()
    }
  }

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

  const handleAiSave = async () => {
    if (!aiSettings) return
    setAiBusy(true)
    setAiMessage(null)
    setAiProbeResult(null)
    try {
      const payload: Record<string, unknown> = {
        enabled: aiDraft.enabled ?? aiSettings.enabled,
        provider_dialect: aiDraft.provider_dialect ?? aiSettings.provider_dialect,
        endpoint: aiDraft.endpoint ?? aiSettings.endpoint,
        model_id: aiDraft.model_id ?? aiSettings.model_id,
        display_name: aiDraft.display_name ?? aiSettings.display_name,
        timeout_seconds: Number(aiDraft.timeout_seconds ?? aiSettings.timeout_seconds),
        max_input_length: Number(aiDraft.max_input_length ?? aiSettings.max_input_length),
        max_output_tokens: Number(aiDraft.max_output_tokens ?? aiSettings.max_output_tokens),
        concurrency_limit: Number(aiDraft.concurrency_limit ?? aiSettings.concurrency_limit),
        expected_revision: aiSettings.revision,
      }
      if (aiSecretKey.trim()) {
        payload.secret_key = aiSecretKey.trim()
      }
      const res = await api<{ ok: true; connection: AiConnectionSettingsState }>(
        'PUT',
        '/api/v2/admin/ai-connection',
        payload
      )
      setAiSettings(res.connection)
      setAiDraft(res.connection)
      setAiSecretKey('')
      setAiMessage('تنظیمات هوش مصنوعی ذخیره شد.')
    } catch (e: unknown) {
      setAiMessage(e instanceof Error ? e.message : 'خطا در ذخیره تنظیمات هوش مصنوعی')
    } finally {
      setAiBusy(false)
    }
  }

  const handleAiProbe = async () => {
    setAiBusy(true)
    setAiProbeResult(null)
    setAiMessage(null)
    try {
      const res = await api<{
        ok: true
        probe: { ok: boolean; reachable: boolean; latency_ms?: number; error?: string }
      }>('POST', '/api/v2/admin/ai-connection/probe')
      if (res.probe.ok) {
        setAiProbeResult({
          ok: true,
          message: `اتصال آزمایشی موفق بود (${res.probe.latency_ms ?? 0} میلی‌ثانیه)`
        })
      } else {
        setAiProbeResult({
          ok: false,
          message: `خطای اتصال: ${res.probe.error || 'پاسخ ناموفق'}`
        })
      }
    } catch (e: unknown) {
      setAiProbeResult({
        ok: false,
        message: e instanceof Error ? e.message : 'خطا در اجرای آزمون اتصال'
      })
    } finally {
      setAiBusy(false)
    }
  }

  const handlePolicySave = async (serviceName: string) => {
    const existing = servicePolicies[serviceName]
    const draft = policyDrafts[serviceName]
    if (!draft) return
    setAiBusy(true)
    try {
      const res = await api<{ ok: true; policy: AiDataPolicyState }>(
        'PUT',
        `/api/v2/admin/ai-data-policy/${serviceName}`,
        {
          policy_level: draft.policy_level || 'disabled',
          max_history_turns: Number(draft.max_history_turns ?? 5),
          allowed_context_types: draft.allowed_context_types || [],
          expected_revision: existing ? existing.revision : 0,
        }
      )
      setServicePolicies(prev => ({ ...prev, [serviceName]: res.policy }))
      setPolicyDrafts(prev => ({ ...prev, [serviceName]: { ...res.policy } }))
    } catch {
      setActionError('خطا در ذخیرهٔ سیاست خروج داده‌های AI')
    } finally {
      setAiBusy(false)
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
    const ready = accounts.some(account => account.provider === provider && account.auth_state === 'authenticated' && account.lifecycle_state === 'active' && account.desired_worker_state === 'running' && account.worker?.runtime_state === 'ready')
    return <Chip label={ready ? readyLabel : pendingLabel} color={ready ? 'success' : 'info'} size="small" />
  }

  const senderProfileFor = (credentialId: string, intent: string) =>
    senderProfiles.find(profile => profile.service_credential_id === credentialId && profile.intent === intent)

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
              {chipFor('bale', 'ارسال بله: پیکربندی نشده', 'ارسال بله (شخصی): فعال', 'بله شخصی: ورود حساب لازم است')}
              <Chip label="نماینده هوشمند: حالت آزمایشی" color="info" size="small" />
            </Box>
          </CardContent>
        </Card>

        {aiSettings && (
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2, flexWrap: 'wrap', gap: 1 }}>
                <Typography variant="h6">تنظیمات سراسری هوش مصنوعی (AI Model Connection)</Typography>
                <Stack direction="row" spacing={1} alignItems="center">
                  <Chip
                    size="small"
                    color={aiSettings.enabled ? (aiSettings.connection_status === 'configured' ? 'success' : 'info') : 'default'}
                    label={`وضعیت: ${aiSettings.connection_status} | نسخهٔ ${aiSettings.revision}`}
                  />
                  <Stack direction="row" spacing={0.5} alignItems="center">
                    <Switch
                      checked={aiDraft.enabled ?? aiSettings.enabled}
                      onChange={e => setAiDraft(prev => ({ ...prev, enabled: e.target.checked }))}
                    />
                    <Typography variant="body2">{aiDraft.enabled ? 'فعال' : 'غیرفعال'}</Typography>
                  </Stack>
                </Stack>
              </Box>

              {aiMessage && <Alert severity="info" sx={{ mb: 2 }}>{aiMessage}</Alert>}
              {aiProbeResult && (
                <Alert severity={aiProbeResult.ok ? 'success' : 'error'} sx={{ mb: 2 }}>
                  {aiProbeResult.message}
                </Alert>
              )}

              <Stack spacing={2}>
                <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr' }, gap: 2 }}>
                  <TextField
                    label="نشانی سرور هوش مصنوعی (Endpoint URL)"
                    value={aiDraft.endpoint ?? aiSettings.endpoint}
                    onChange={e => setAiDraft(prev => ({ ...prev, endpoint: e.target.value }))}
                    placeholder="https://api.openai.com/v1/chat/completions"
                    inputProps={{ dir: 'ltr' }}
                    size="small"
                  />
                  <TextField
                    label="شناسه مدل (Model ID)"
                    value={aiDraft.model_id ?? aiSettings.model_id}
                    onChange={e => setAiDraft(prev => ({ ...prev, model_id: e.target.value }))}
                    placeholder="gpt-4o"
                    inputProps={{ dir: 'ltr' }}
                    size="small"
                  />
                </Box>
                <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr' }, gap: 2 }}>
                  <TextField
                    label="نام نمایشی"
                    value={aiDraft.display_name ?? aiSettings.display_name}
                    onChange={e => setAiDraft(prev => ({ ...prev, display_name: e.target.value }))}
                    placeholder="OpenAI GPT-4o"
                    size="small"
                  />
                  <TextField
                    label="کلید محرمانه (Secret Key)"
                    type="password"
                    value={aiSecretKey}
                    onChange={e => setAiSecretKey(e.target.value)}
                    placeholder={aiSettings.key_configured ? '•••••••• (تنظیم شده؛ برای تغییر مقدار جدید وارد کنید)' : 'sk-...'}
                    inputProps={{ dir: 'ltr' }}
                    size="small"
                  />
                </Box>
                <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr 1fr', sm: '1fr 1fr 1fr 1fr' }, gap: 2 }}>
                  <TextField
                    label="مهلت زمانی (ثانیه)"
                    type="number"
                    value={aiDraft.timeout_seconds ?? aiSettings.timeout_seconds}
                    onChange={e => setAiDraft(prev => ({ ...prev, timeout_seconds: Number(e.target.value) }))}
                    size="small"
                  />
                  <TextField
                    label="سقف کاراکتر ورودی"
                    type="number"
                    value={aiDraft.max_input_length ?? aiSettings.max_input_length}
                    onChange={e => setAiDraft(prev => ({ ...prev, max_input_length: Number(e.target.value) }))}
                    size="small"
                  />
                  <TextField
                    label="سقف توکن خروجی"
                    type="number"
                    value={aiDraft.max_output_tokens ?? aiSettings.max_output_tokens}
                    onChange={e => setAiDraft(prev => ({ ...prev, max_output_tokens: Number(e.target.value) }))}
                    size="small"
                  />
                  <TextField
                    label="سقف هم‌زمانی"
                    type="number"
                    value={aiDraft.concurrency_limit ?? aiSettings.concurrency_limit}
                    onChange={e => setAiDraft(prev => ({ ...prev, concurrency_limit: Number(e.target.value) }))}
                    size="small"
                  />
                </Box>
                <Stack direction="row" spacing={1} sx={{ mt: 1 }}>
                  <Button variant="contained" disabled={aiBusy} onClick={() => void handleAiSave()}>
                    ذخیره تنظیمات هوش مصنوعی
                  </Button>
                  <Button variant="outlined" disabled={aiBusy} onClick={() => void handleAiProbe()}>
                    آزمون اتصال (Probe)
                  </Button>
                </Stack>
              </Stack>
            </CardContent>
          </Card>
        )}

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

        {credentials.filter(cred => !cred.revoked_at).map(cred => (
          <Card key={`sender-${cred.id}`}>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                فرستنده‌های هدف سرویس «{cred.service_name}»
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                انتخاب فرستنده برای هر هدف صریح است؛ هیچ حسابی به‌صورت خودکار پیش‌فرض نمی‌شود.
              </Typography>
              <Stack spacing={2}>
                {SENDER_INTENTS.map(intent => {
                  const draftKey = `${cred.id}:${intent}`
                  const existing = senderProfiles.find(
                    profile => profile.service_credential_id === cred.id && profile.intent === intent
                  )
                  const draft = senderDrafts[draftKey]
                  const providerOptions = Object.keys(providerAdapters).length > 0
                    ? Object.keys(providerAdapters)
                    : ['eitaa', 'bale']
                  const providerAccounts = accounts.filter(account => !draft || !draft.provider || account.provider === draft.provider)
                  const dirty = !existing || (
                    existing && draft && (
                      existing.provider !== draft.provider ||
                      existing.messenger_account_id !== draft.accountId ||
                      existing.enabled !== draft.enabled
                    )
                  )
                  return (
                    <Box key={`${cred.id}:${intent}`} sx={{ borderTop: '1px solid', borderColor: 'divider', pt: 2 }}>
                      <Stack direction="row" spacing={2} alignItems="center" sx={{ mb: 1, flexWrap: 'wrap', gap: 1 }}>
                        <Typography variant="subtitle2" sx={{ minWidth: 200 }}>
                          {SENDER_INTENT_LABELS[intent] || intent}
                        </Typography>
                        {existing && (
                          <Chip
                            size="small"
                            color={
                              !existing.enabled
                                ? 'default'
                                : existing.account_available ? 'success' : 'warning'
                            }
                            label={
                              !existing.enabled
                                ? 'غیرفعال'
                                : existing.account_available
                                  ? `نسخهٔ ${existing.revision} | حساب در دسترس`
                                  : `نسخهٔ ${existing.revision} | حساب در دسترس نیست`
                            }
                          />
                        )}
                      </Stack>
                      <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2} sx={{ alignItems: { sm: 'center' } }}>
                        <FormControl size="small" sx={{ minWidth: 160 }}>
                          <InputLabel id={`provider-label-${draftKey}`}>سرویس‌دهنده</InputLabel>
                          <Select
                            labelId={`provider-label-${draftKey}`}
                            label="سرویس‌دهنده"
                            value={draft?.provider ?? ''}
                            onChange={event => updateSenderDraft(draftKey, {
                              provider: event.target.value as string,
                              accountId: ''
                            })}
                          >
                            {providerOptions.map(provider => (
                              <MenuItem key={provider} value={provider}>
                                {PROVIDER_LABELS[provider] || provider}
                              </MenuItem>
                            ))}
                          </Select>
                        </FormControl>
                        <FormControl size="small" sx={{ minWidth: 260 }} disabled={!draft?.provider}>
                          <InputLabel id={`account-label-${draftKey}`}>حساب فرستنده</InputLabel>
                          <Select
                            labelId={`account-label-${draftKey}`}
                            label="حساب فرستنده"
                            value={draft?.accountId ?? ''}
                            onChange={event => updateSenderDraft(draftKey, { accountId: event.target.value as string })}
                          >
                            {accounts
                              .filter(account => !draft?.provider || account.provider === draft.provider)
                              .map(account => (
                                <MenuItem key={account.messenger_account_id} value={account.messenger_account_id}>
                                  {`${PROVIDER_LABELS[account.provider] || account.provider} — ${account.label || 'بدون نام'} (${account.phone_hint}) — ${accountAvailabilityLabel(account)}`}
                                </MenuItem>
                              ))}
                            {accounts.length === 0 && (
                              <MenuItem value="" disabled>حسابی ثبت نشده است</MenuItem>
                            )}
                          </Select>
                        </FormControl>
                        <Stack direction="row" spacing={1} alignItems="center">
                          <Switch
                            checked={draft?.enabled ?? false}
                            onChange={event => updateSenderDraft(draftKey, { enabled: event.target.checked })}
                          />
                          <Typography variant="body2">فعال</Typography>
                        </Stack>
                        <Button
                          variant="contained"
                          disabled={!dirty || !draft?.provider || !draft?.accountId}
                          onClick={() => { void handleSenderProfileSave(cred, intent) }}
                        >
                          ذخیره
                        </Button>
                        {existing && (
                          <Button
                            color="error"
                            onClick={() => { void handleSenderProfileDelete(existing) }}
                          >
                            حذف تنظیم
                          </Button>
                        )}
                      </Stack>
                    </Box>
                  )
                })}
              </Stack>

              <Box sx={{ borderTop: '2px solid', borderColor: 'divider', mt: 3, pt: 2 }}>
                <Typography variant="subtitle1" fontWeight={700} gutterBottom>
                  سیاست خروج داده‌های هوش مصنوعی (AI Data Policy)
                </Typography>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                  محدودسازی سطح انتقال داده‌های کاربر به مدل هوش مصنوعی برای سرویس «{cred.service_name}».
                </Typography>
                {(() => {
                  const policy = servicePolicies[cred.service_name] || {
                    service_id: cred.service_name,
                    policy_level: 'disabled' as const,
                    max_history_turns: 5,
                    allowed_context_types: [],
                    revision: 0,
                    updated_at: '',
                  }
                  const draft = policyDrafts[cred.service_name] || { ...policy }
                  return (
                    <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2} alignItems="center">
                      <FormControl size="small" sx={{ minWidth: 220 }}>
                        <InputLabel id={`policy-level-label-${cred.id}`}>سطح سیاست خروج داده</InputLabel>
                        <Select
                          labelId={`policy-level-label-${cred.id}`}
                          label="سطح سیاست خروج داده"
                          value={draft.policy_level || 'disabled'}
                          onChange={e => {
                            const val = e.target.value as AiDataPolicyState['policy_level']
                            setPolicyDrafts(prev => ({
                              ...prev,
                              [cred.service_name]: { ...(prev[cred.service_name] || policy), policy_level: val }
                            }))
                          }}
                        >
                          <MenuItem value="disabled">غیرفعال (fail-closed)</MenuItem>
                          <MenuItem value="current_message">فقط پیام جاری (current_message)</MenuItem>
                          <MenuItem value="limited_history">پیام جاری + سابقهٔ محدود (limited_history)</MenuItem>
                          <MenuItem value="approved_context">سابقهٔ محدود + زمینهٔ تأییدشده (approved_context)</MenuItem>
                        </Select>
                      </FormControl>
                      {draft.policy_level !== 'disabled' && (
                        <TextField
                          label="تعداد دور سابقه"
                          type="number"
                          size="small"
                          sx={{ width: 140 }}
                          value={draft.max_history_turns ?? 5}
                          onChange={e => {
                            const val = Number(e.target.value)
                            setPolicyDrafts(prev => ({
                              ...prev,
                              [cred.service_name]: { ...(prev[cred.service_name] || policy), max_history_turns: val }
                            }))
                          }}
                          inputProps={{ min: 0, max: 50 }}
                        />
                      )}
                      <Chip
                        size="small"
                        color={draft.policy_level === 'disabled' ? 'default' : 'success'}
                        label={`نسخهٔ ${policy.revision}`}
                      />
                      <Button
                        variant="outlined"
                        disabled={aiBusy}
                        onClick={() => void handlePolicySave(cred.service_name)}
                      >
                        ذخیره سیاست AI
                      </Button>
                    </Stack>
                  )
                })()}
              </Box>
            </CardContent>
          </Card>
        ))}
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
                  <FormControlLabel
                    key={scope}
                    label={label}
                    control={<Checkbox
                      checked={selectedScopes.includes(scope)}
                      onChange={(_, checked) => setSelectedScopes(current =>
                        checked ? [...current, scope] : current.filter(item => item !== scope)
                      )}
                    />}
                  />
                ))}
              </Stack>
              <Typography variant="subtitle1" gutterBottom>سرویس‌دهنده‌های مجاز</Typography>
              <Stack direction="row" spacing={1} sx={{ mb: 3, flexWrap: 'wrap', gap: 1 }}>
                {(Object.keys(providerAdapters).length > 0
                  ? Object.keys(providerAdapters)
                  : ['eitaa', 'bale']
                ).map(provider => (
                  <FormControlLabel
                    key={provider}
                    label={provider}
                    control={<Checkbox
                      checked={selectedProviders.includes(provider)}
                      onChange={(_, checked) => setSelectedProviders(current =>
                        checked ? [...current, provider] : current.filter(item => item !== provider)
                      )}
                    />}
                  />
                ))}
              </Stack>
              <Typography variant="subtitle1" gutterBottom>حساب‌های مجاز</Typography>
              <Stack direction="row" spacing={1} sx={{ flexWrap: 'wrap', gap: 1 }}>
                {accounts.map(account => {
                  const accountId = account.messenger_account_id
                  const selected = selectedAccounts.includes(accountId)
                  const hint = `${PROVIDER_LABELS[account.provider] || account.label || account.provider} (${account.phone_hint})`
                  return (
                    <FormControlLabel
                      key={accountId}
                      label={hint}
                      control={<Checkbox
                        checked={selected}
                        onChange={(_, checked) => setSelectedAccounts(current =>
                          checked ? [...current, accountId] : current.filter(item => item !== accountId)
                        )}
                      />}
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
