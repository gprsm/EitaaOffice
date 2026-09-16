import {
  createContext,
  Fragment,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react'
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Divider,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControl,
  InputLabel,
  MenuItem,
  Paper,
  Select,
  Stack,
  TextField,
  Typography,
} from '@mui/material'
import { api, setSelectedMessengerAccountId } from './lib/api'
import { AppUserLogoutButton, useAppUser } from './AppUserGate'
import { LoginSurface } from './LoginExperience'
import { AuthBrandPill, ProviderBrandBadge } from './AuthBrand'

export type MessengerAccount = {
  messenger_account_id: string
  phone_account_id: string
  provider: string
  label: string | null
  phone_hint: string
  membership_role: 'admin' | 'owner' | 'operator' | 'viewer'
  lifecycle_state: 'created' | 'active' | 'paused' | 'disabled' | 'quarantined' | 'archived'
  desired_worker_state: 'running' | 'stopped'
  auth_state: 'absent' | 'challenge_pending' | 'authenticated' | 'expired' | 'revoked' | 'invalid'
  session_generation: number
  storage_revision: number
  worker: null | {
    worker_instance_id: string
    generation: number
    runtime_state: string
    process_id: number | null
    last_heartbeat_at: string | null
    safe_reason_code: string | null
  }
  permissions: { view: boolean; operate: boolean; manage_worker: boolean }
}

export type ProviderDescriptor = {
  provider: string
  display_name: string
  configured: boolean
  runtime_enabled: boolean
  onboarding_enabled: boolean
  account_identity_kind: string | null
  auth_steps: string[]
  account_kind: string
  implementation_state: string
  capabilities: string[]
  reason_code?: string
}

type AccountList = {
  ok: true
  feature_enabled: boolean
  default_messenger_account_id: string | null
  accounts: MessengerAccount[]
  provider_adapters: Record<string, ProviderDescriptor>
}

type OnboardingInput = { provider: string; phone: string; label: string }
type OnboardingResponse = { ok: true; account: MessengerAccount }
export type AccountCapabilityDecision = {
  capability: string
  status: 'supported' | 'restricted' | 'unsupported' | 'unknown'
  reason_code: string
  constraints_present: boolean
  revision: number
}
type AccountCapabilitySnapshot = {
  ok: true
  messenger_account_id: string
  provider: string
  implementation_state: string
  runtime_enabled: boolean
  capabilities: AccountCapabilityDecision[]
}

type MessengerAccountContextValue = {
  featureEnabled: boolean
  accounts: MessengerAccount[]
  selected: MessengerAccount | null
  select: (accountId: string) => void
  refresh: () => Promise<void>
  start: (accountId: string) => Promise<void>
  stop: (accountId: string) => Promise<void>
  onboard: (input: OnboardingInput) => Promise<MessengerAccount>
  providerAdapters: Record<string, ProviderDescriptor>
  capabilitySnapshot: AccountCapabilitySnapshot | null
  hasCapability: (capability: string) => boolean
  capabilityLoading: boolean
  capabilityError: string
  busyAccountId: string | null
  onboardingBusy: boolean
  error: string
}

const MessengerAccountContext = createContext<MessengerAccountContextValue>({
  featureEnabled: false,
  accounts: [],
  selected: null,
  select: () => undefined,
  refresh: async () => undefined,
  start: async () => undefined,
  stop: async () => undefined,
  onboard: async () => { throw new Error('Account onboarding is unavailable.') },
  providerAdapters: {},
  capabilitySnapshot: null,
  hasCapability: () => false,
  capabilityLoading: false,
  capabilityError: '',
  busyAccountId: null,
  onboardingBusy: false,
  error: '',
})

export function useMessengerAccounts() {
  return useContext(MessengerAccountContext)
}

const isRunnable = (
  account: MessengerAccount,
  adapters: Record<string, ProviderDescriptor>,
) => (
  Boolean(adapters[account.provider]?.configured)
  && Boolean(adapters[account.provider]?.runtime_enabled)
  && account.permissions.operate
  && account.lifecycle_state === 'active'
  && account.desired_worker_state === 'running'
)

export function MessengerAccountGate({ children }: { children: ReactNode }) {
  const appUser = useAppUser()
  const [snapshot, setSnapshot] = useState<AccountList | null>(null)
  const [selectedId, setSelectedId] = useState('')
  const [busyAccountId, setBusyAccountId] = useState<string | null>(null)
  const [onboardingBusy, setOnboardingBusy] = useState(false)
  const [error, setError] = useState('')
  const [capabilitySnapshot, setCapabilitySnapshot] = useState<AccountCapabilitySnapshot | null>(null)
  const [capabilityLoading, setCapabilityLoading] = useState(false)
  const [capabilityError, setCapabilityError] = useState('')

  const refresh = useCallback(async () => {
    if (!appUser.enabled || !appUser.principal) {
      setSnapshot(null)
      setSelectedId('')
      setCapabilitySnapshot(null)
      setCapabilityError('')
      setSelectedMessengerAccountId(null)
      return
    }
    setError('')
    try {
      const next = await api<AccountList>('GET', '/api/v2/messenger-accounts')
      setSnapshot(next)
      if (!next.feature_enabled) {
        setSelectedId('')
        setSelectedMessengerAccountId(null)
        return
      }
      setSelectedId(current => {
        const existing = next.accounts.find(item => item.messenger_account_id === current)
        const fallback = next.accounts.find(
          item => item.messenger_account_id === next.default_messenger_account_id,
        ) || next.accounts.find(item => isRunnable(item, next.provider_adapters))
          || next.accounts.find(item => item.permissions.operate)
        const chosen = existing || fallback || null
        setSelectedMessengerAccountId(chosen?.messenger_account_id || null)
        return chosen?.messenger_account_id || ''
      })
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'خواندن حساب‌های پیام‌رسان انجام نشد.')
    }
  }, [appUser.enabled, appUser.principal])

  useEffect(() => { void refresh() }, [refresh])

  const select = useCallback((accountId: string) => {
    const account = snapshot?.accounts.find(item => item.messenger_account_id === accountId)
    if (!account?.permissions.operate) return
    setSelectedId(accountId)
    setSelectedMessengerAccountId(accountId)
  }, [snapshot?.accounts])

  const workerAction = useCallback(async (accountId: string, action: 'start' | 'stop') => {
    setBusyAccountId(accountId)
    setError('')
    try {
      await api('POST', `/api/v2/messenger-accounts/${accountId}/worker/${action}`)
      if (action === 'start') {
        setSelectedId(accountId)
        setSelectedMessengerAccountId(accountId)
      }
      await refresh()
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'تغییر وضعیت Worker انجام نشد.')
      throw reason
    } finally {
      setBusyAccountId(null)
    }
  }, [refresh])

  const onboard = useCallback(async (input: OnboardingInput) => {
    setOnboardingBusy(true)
    setError('')
    try {
      const result = await api<OnboardingResponse>('POST', '/api/v2/messenger-accounts', input)
      setSelectedId(result.account.messenger_account_id)
      setSelectedMessengerAccountId(result.account.messenger_account_id)
      await refresh()
      return result.account
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'افزودن حساب پیام‌رسان انجام نشد.')
      throw reason
    } finally {
      setOnboardingBusy(false)
    }
  }, [refresh])

  const selected = snapshot?.accounts.find(
    item => item.messenger_account_id === selectedId,
  ) || null
  useEffect(() => {
    if (!selected || !appUser.principal) {
      setCapabilitySnapshot(null)
      setCapabilityError('')
      setCapabilityLoading(false)
      return
    }
    let active = true
    setCapabilitySnapshot(null)
    setCapabilityError('')
    setCapabilityLoading(true)
    void api<AccountCapabilitySnapshot>(
      'GET',
      `/api/v2/messenger-accounts/${selected.messenger_account_id}/capabilities`,
    ).then(result => {
      if (!active || result.messenger_account_id !== selected.messenger_account_id) return
      setCapabilitySnapshot(result)
    }).catch(reason => {
      if (!active) return
      setCapabilityError(reason instanceof Error ? reason.message : 'خواندن قابلیت‌های حساب انجام نشد.')
    }).finally(() => { if (active) setCapabilityLoading(false) })
    return () => { active = false }
  }, [appUser.principal, selected?.messenger_account_id])

  const hasCapability = useCallback((capability: string) => Boolean(
    capabilitySnapshot
    && capabilitySnapshot.messenger_account_id === selected?.messenger_account_id
    && capabilitySnapshot.runtime_enabled
    && capabilitySnapshot.capabilities.some(
      item => item.capability === capability && item.status === 'supported',
    )
  ), [capabilitySnapshot, selected?.messenger_account_id])
  const context = useMemo<MessengerAccountContextValue>(() => ({
    featureEnabled: Boolean(snapshot?.feature_enabled),
    accounts: snapshot?.accounts || [],
    selected,
    select,
    refresh,
    start: accountId => workerAction(accountId, 'start'),
    stop: accountId => workerAction(accountId, 'stop'),
    onboard,
    providerAdapters: snapshot?.provider_adapters || {},
    capabilitySnapshot,
    hasCapability,
    capabilityLoading,
    capabilityError,
    busyAccountId,
    onboardingBusy,
    error,
  }), [busyAccountId, capabilityError, capabilityLoading, capabilitySnapshot, error, hasCapability, onboard, onboardingBusy, refresh, select, selected, snapshot, workerAction])

  if (!appUser.enabled) return <>{children}</>
  if (!snapshot && !error) {
    return <LoginSurface><Stack alignItems="center" spacing={2}>
      <Typography variant="h6">در حال خواندن حساب‌های پیام‌رسان</Typography>
      <CircularProgress size={32} />
    </Stack></LoginSurface>
  }
  if (error && !snapshot) {
    return <LoginSurface><Stack spacing={2}>
      <Alert severity="error">{error}</Alert>
      <Button variant="contained" onClick={() => void refresh()}>تلاش دوباره</Button>
    </Stack></LoginSurface>
  }
  if (!snapshot?.feature_enabled) {
    return <MessengerAccountContext.Provider value={context}>{children}</MessengerAccountContext.Provider>
  }
  if (!selected || !isRunnable(selected, snapshot.provider_adapters)) {
    return <MessengerAccountContext.Provider value={context}>
      <LoginSurface><Stack spacing={2.25}>
        <AuthBrandPill label="حساب‌های پیام‌رسان" />
        <Typography variant="h5">یک حساب فعال را انتخاب کنید</Typography>
        {error && <Alert severity="error">{error}</Alert>}
        {!snapshot.accounts.length && <Alert severity="info">
          هنوز حساب پیام‌رسانی برای این کاربر تعریف نشده است.
        </Alert>}
        {snapshot.accounts.map(account => <AccountCard
          key={account.messenger_account_id}
          account={account}
          selected={account.messenger_account_id === selectedId}
          busy={busyAccountId === account.messenger_account_id}
          descriptor={snapshot.provider_adapters[account.provider]}
          onSelect={select}
          onStart={id => workerAction(id, 'start')}
          onStop={id => workerAction(id, 'stop')}
        />)}
        <AddMessengerAccountButton />
        <Divider />
        <AppUserLogoutButton disabled={Boolean(busyAccountId)} />
      </Stack></LoginSurface>
    </MessengerAccountContext.Provider>
  }
  return <MessengerAccountContext.Provider value={context}>
    <Fragment key={selected.messenger_account_id}>{children}</Fragment>
  </MessengerAccountContext.Provider>
}

export function MessengerAccountMenuControl() {
  const state = useMessengerAccounts()
  if (!state.featureEnabled || !state.selected) return null
  return <FormControl size="small" fullWidth sx={{ my: 1 }}>
    <InputLabel id="messenger-account-select-label">حساب پیام‌رسان</InputLabel>
    <Select
      labelId="messenger-account-select-label"
      value={state.selected.messenger_account_id}
      label="حساب پیام‌رسان"
      onChange={event => state.select(String(event.target.value))}
    >
      {state.accounts.filter(item => item.permissions.operate).map(account => <MenuItem
        key={account.messenger_account_id}
        value={account.messenger_account_id}
        disabled={!isRunnable(account, state.providerAdapters)}
      >
        <Stack direction="row" gap={1} alignItems="center">
          <ProviderBrandBadge provider={account.provider} size={16} />
          <span>{account.label || providerLabel(account.provider, state.providerAdapters)} — {account.phone_hint}</span>
        </Stack>
      </MenuItem>)}
    </Select>
  </FormControl>
}

export function MessengerAccountManagementPanel() {
  const state = useMessengerAccounts()
  const appUser = useAppUser()
  if (!appUser.enabled) return null
  return <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
    <Stack spacing={1.5}>
      <Box>
        <Typography variant="h6">حساب‌های پیام‌رسان</Typography>
        <Typography variant="body2" color="text.secondary">
          هر شماره یک PhoneAccount است و می‌تواند حساب‌های مستقل ایتا و بله داشته باشد.
        </Typography>
      </Box>
      {!state.featureEnabled && <Alert severity="info">
        مدیریت چندحسابی هنوز با Feature Flag فعال نشده و نرم‌افزار در حالت سازگار قبلی کار می‌کند.
      </Alert>}
      {state.error && <Alert severity="error">{state.error}</Alert>}
      {state.featureEnabled && !state.accounts.length && <Alert severity="info">حسابی در دسترس نیست.</Alert>}
      {state.accounts.map(account => <AccountCard
        key={account.messenger_account_id}
        account={account}
        selected={account.messenger_account_id === state.selected?.messenger_account_id}
        busy={state.busyAccountId === account.messenger_account_id}
        descriptor={state.providerAdapters[account.provider]}
        onSelect={state.select}
        onStart={state.start}
        onStop={state.stop}
      />)}
      {state.featureEnabled && <AddMessengerAccountButton />}
      <Divider />
      <Button size="small" onClick={() => void state.refresh()}>تازه‌سازی وضعیت حساب‌ها</Button>
    </Stack>
  </Paper>
}

function AccountCard(props: {
  account: MessengerAccount
  selected: boolean
  busy: boolean
  descriptor?: ProviderDescriptor
  onSelect: (id: string) => void
  onStart: (id: string) => Promise<void>
  onStop: (id: string) => Promise<void>
}) {
  const account = props.account
  const running = account.lifecycle_state === 'active' && account.desired_worker_state === 'running'
  const adapterReady = Boolean(props.descriptor?.configured && props.descriptor?.runtime_enabled)
  return <Paper variant="outlined" sx={{ p: 1.5, borderColor: props.selected ? 'primary.main' : undefined }}>
    <Stack spacing={1}>
      <Stack direction="row" justifyContent="space-between" alignItems="center" gap={1}>
        <Box>
          <Typography fontWeight={700}>{account.label || props.descriptor?.display_name || account.provider}</Typography>
          <Stack direction="row" gap={0.75} alignItems="center"><ProviderBrandBadge provider={account.provider} size={16} /><Typography variant="body2" dir="ltr">{account.phone_hint}</Typography></Stack>
        </Box>
        <Stack direction="row" gap={0.75} flexWrap="wrap" justifyContent="flex-end">
          <Chip size="small" label={props.descriptor?.display_name || account.provider} />
          <Chip size="small" label={authLabel(account.auth_state)} color={account.auth_state === 'authenticated' ? 'success' : 'default'} />
          <Chip size="small" label={running ? 'Worker فعال' : 'Worker متوقف'} color={running ? 'success' : 'default'} />
        </Stack>
      </Stack>
      <Typography variant="caption" color="text.secondary">
        نقش: {roleLabel(account.membership_role)} · وضعیت: {account.lifecycle_state}
      </Typography>
      <Stack direction="row" gap={1}>
        {running && account.permissions.operate && <Button
          size="small"
          variant={props.selected ? 'contained' : 'outlined'}
          onClick={() => props.onSelect(account.messenger_account_id)}
        >{props.selected ? 'انتخاب‌شده' : 'انتخاب حساب'}</Button>}
        {!running && adapterReady && account.permissions.manage_worker && <Button
          size="small"
          variant="contained"
          disabled={props.busy}
          onClick={() => void props.onStart(account.messenger_account_id).catch(() => undefined)}
        >{props.busy ? 'در حال شروع…' : 'شروع Worker'}</Button>}
        {running && account.permissions.manage_worker && <Button
          size="small"
          color="warning"
          disabled={props.busy}
          onClick={() => void props.onStop(account.messenger_account_id).catch(() => undefined)}
        >{props.busy ? 'در حال توقف…' : 'توقف Worker'}</Button>}
      </Stack>
      {!adapterReady && <Alert severity="info">Adapter این پیام‌رسان هنوز تعریف نشده است.</Alert>}
      {!account.permissions.operate && <Alert severity="info">دسترسی شما فقط مشاهده است.</Alert>}
    </Stack>
  </Paper>
}

function AddMessengerAccountButton() {
  const state = useMessengerAccounts()
  const [open, setOpen] = useState(false)
  const [provider, setProvider] = useState('')
  const [phone, setPhone] = useState('')
  const [label, setLabel] = useState('')
  const [localError, setLocalError] = useState('')
  const providers = Object.values(state.providerAdapters).filter(item => item.onboarding_enabled)
  const selectedProvider = provider || providers[0]?.provider || ''

  const close = () => {
    if (state.onboardingBusy) return
    setPhone('')
    setLabel('')
    setLocalError('')
    setOpen(false)
  }
  const submit = async () => {
    setLocalError('')
    try {
      await state.onboard({ provider: selectedProvider, phone, label })
      setPhone('')
      setLabel('')
      setOpen(false)
    } catch (reason) {
      setLocalError(reason instanceof Error ? reason.message : 'افزودن حساب انجام نشد.')
    } finally {
      // Private identity must not remain in component state after submission.
      setPhone('')
    }
  }

  if (!providers.length) {
    return <Alert severity="info">در حال حاضر ارائه‌دهنده‌ای برای افزودن حساب فعال نیست.</Alert>
  }
  return <>
    <Button variant="outlined" onClick={() => setOpen(true)}>افزودن حساب پیام‌رسان</Button>
    <Dialog open={open} onClose={close} fullWidth maxWidth="sm">
      <DialogTitle>افزودن حساب پیام‌رسان</DialogTitle>
      <DialogContent>
        <Stack spacing={2} sx={{ pt: 1 }}>
          <Alert severity="info">
            شماره فقط برای ساخت هویت رمزگذاری‌شده ارسال می‌شود؛ در لاگ، گزارش یا مرورگر ذخیره نخواهد شد.
          </Alert>
          {localError && <Alert severity="error">{localError}</Alert>}
          <FormControl fullWidth>
            <InputLabel id="onboarding-provider-label">پیام‌رسان</InputLabel>
            <Select
              labelId="onboarding-provider-label"
              value={selectedProvider}
              label="پیام‌رسان"
              onChange={event => setProvider(String(event.target.value))}
              disabled={state.onboardingBusy}
            >
              {providers.map(item => <MenuItem key={item.provider} value={item.provider}>
                {item.display_name}
              </MenuItem>)}
            </Select>
          </FormControl>
          <TextField
            label="شماره در قالب بین‌المللی"
            type="tel"
            dir="ltr"
            value={phone}
            onChange={event => setPhone(event.target.value)}
            placeholder="+98912…"
            autoComplete="off"
            inputProps={{ maxLength: 16, inputMode: 'tel' }}
            disabled={state.onboardingBusy}
            helperText="شماره باید با + و کد کشور وارد شود."
          />
          <TextField
            label="نام دلخواه حساب (اختیاری)"
            value={label}
            onChange={event => setLabel(event.target.value)}
            inputProps={{ maxLength: 120 }}
            disabled={state.onboardingBusy}
          />
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={close} disabled={state.onboardingBusy}>انصراف</Button>
        <Button
          variant="contained"
          disabled={state.onboardingBusy || !selectedProvider || !/^\+[1-9][0-9]{7,14}$/.test(phone)}
          onClick={() => void submit()}
        >{state.onboardingBusy ? 'در حال ساخت…' : 'ساخت حساب'}</Button>
      </DialogActions>
    </Dialog>
  </>
}

const providerLabel = (
  provider: MessengerAccount['provider'],
  adapters: Record<string, ProviderDescriptor> = {},
) => adapters[provider]?.display_name || provider
const roleLabel = (role: MessengerAccount['membership_role']) => ({
  admin: 'مدیر نرم‌افزار', owner: 'مالک', operator: 'اپراتور', viewer: 'مشاهده‌گر',
}[role])
const authLabel = (state: MessengerAccount['auth_state']) => ({
  absent: 'وارد نشده',
  challenge_pending: 'در انتظار کد',
  authenticated: 'واردشده',
  expired: 'منقضی',
  revoked: 'خارج‌شده',
  invalid: 'نامعتبر',
}[state])
