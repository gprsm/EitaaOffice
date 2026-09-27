import {
  createContext,
  type FormEvent,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react'
import {
  Alert,
  Box,
  Button,
  CircularProgress,
  Stack,
  TextField,
  Typography,
} from '@mui/material'
import { api, APP_AUTH_SESSION_INVALID_EVENT, setAppUserStorageScope } from './lib/api'
import { authStartupFailure, authStartupRetryDelay, type AuthStartupFailure } from './lib/authStartupRecovery.mjs'
import { LoginSurface } from './LoginExperience'
import { AuthBrandMark, AuthBrandPill } from './AuthBrand'

export type AppUserPrincipal = {
  app_user_id: string
  display_name: string
  global_role: 'admin' | 'user'
  permissions: {
    manage_users: boolean
    use_legacy_workspace: boolean
  }
}

type AppAuthStatus = {
  ok: true
  enabled: boolean
  setup_required: boolean
  authenticated: boolean
  session_invalid?: boolean
  principal?: AppUserPrincipal
  csrf_token?: string
  self_registration_enabled?: boolean
}

type AppUserContextValue = {
  enabled: boolean
  principal: AppUserPrincipal | null
  logout: () => Promise<void>
  refresh: () => Promise<void>
}

const AppUserContext = createContext<AppUserContextValue>({
  enabled: false,
  principal: null,
  logout: async () => undefined,
  refresh: async () => undefined,
})

export function useAppUser() {
  return useContext(AppUserContext)
}

export function AppUserLogoutButton({ disabled = false }: { disabled?: boolean }) {
  const appUser = useAppUser()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  if (!appUser.enabled || !appUser.principal) return null

  const logout = async () => {
    setBusy(true)
    setError('')
    try {
      await appUser.logout()
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : 'خروج از نرم‌افزار انجام نشد.',
      )
      setBusy(false)
    }
  }

  return <Stack spacing={1}>
    {error && <Alert severity="error">{error}</Alert>}
    <Button
      type="button"
      color="inherit"
      variant="outlined"
      disabled={disabled || busy}
      onClick={() => void logout()}
    >
      {busy ? 'در حال خروج…' : 'خروج از نرم‌افزار'}
    </Button>
  </Stack>
}

export function AppUserGate({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AppAuthStatus | null>(null)
  const [fatal, setFatal] = useState<AuthStartupFailure | null>(null)
  const refreshInFlight = useRef<Promise<void> | null>(null)

  const refresh = useCallback((): Promise<void> => {
    if (refreshInFlight.current) return refreshInFlight.current
    const run = async () => {
      setFatal(null)
      for (let attempt = 0; attempt < 2; attempt += 1) {
        try {
          setStatus(await api<AppAuthStatus>('GET', '/api/v2/app-auth/status'))
          return
        } catch (error) {
          const delay = authStartupRetryDelay(error, attempt)
          if (delay !== null) {
            await new Promise(resolve => window.setTimeout(resolve, delay))
            continue
          }
          setFatal(authStartupFailure(error))
          return
        }
      }
    }
    const pending = run()
    refreshInFlight.current = pending
    void pending.finally(() => {
      if (refreshInFlight.current === pending) refreshInFlight.current = null
    })
    return pending
  }, [])

  useEffect(() => { void refresh() }, [refresh])
  useEffect(() => {
    const onInvalid = () => { void refresh() }
    window.addEventListener(APP_AUTH_SESSION_INVALID_EVENT, onInvalid)
    return () => window.removeEventListener(APP_AUTH_SESSION_INVALID_EVENT, onInvalid)
  }, [refresh])

  const logout = useCallback(async () => {
    await api('POST', '/api/v2/app-auth/logout')
    await refresh()
  }, [refresh])

  const context = useMemo<AppUserContextValue>(() => ({
    enabled: Boolean(status?.enabled),
    principal: status?.principal || null,
    logout,
    refresh,
  }), [logout, refresh, status?.enabled, status?.principal])

  if (fatal) {
    return <LoginSurface><Stack spacing={2}>
      <Typography variant="h5" textAlign="center">راه‌اندازی ورود نرم‌افزار انجام نشد</Typography>
      <Alert severity="error">{fatal.message}</Alert>
      {fatal.code && <Typography variant="body2" textAlign="center">کد خطا: {fatal.code}</Typography>}
      <Button variant="contained" onClick={() => void refresh()}>تلاش دوباره</Button>
    </Stack></LoginSurface>
  }
  if (!status) {
    return <LoginSurface><Stack alignItems="center" spacing={2}>
      <AuthBrandMark />
      <Typography variant="h6">در حال بررسی دسترسی نرم‌افزار</Typography>
      <CircularProgress size={32} />
    </Stack></LoginSurface>
  }
  if (!status.enabled) {
    setAppUserStorageScope(null)
    return <AppUserContext.Provider value={context}>{children}</AppUserContext.Provider>
  }
  if (status.setup_required) {
    return <AppUserSetup onComplete={refresh} />
  }
  if (!status.authenticated || !status.principal) {
    setAppUserStorageScope(null)
    return <AppUserLogin
      registrationEnabled={Boolean(status.self_registration_enabled)}
      onComplete={refresh}
    />
  }
  setAppUserStorageScope(status.principal.app_user_id)
  return <AppUserContext.Provider value={context}>{children}</AppUserContext.Provider>
}

function AppUserLogin({
  registrationEnabled,
  onComplete,
}: {
  registrationEnabled: boolean
  onComplete: () => Promise<void>
}) {
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      await api('POST', '/api/v2/app-auth/login', { username, password })
      setPassword('')
      await onComplete()
    } catch (reason) {
      setPassword('')
      setError(
        reason instanceof Error
          ? reason.message
          : 'نام کاربری یا رمز ورود درست نیست.',
      )
    } finally {
      setBusy(false)
    }
  }

  if (mode === 'register') {
    return <AppUserRegister onBack={() => setMode('login')} onComplete={onComplete} />
  }

  return <LoginSurface><Box component="form" onSubmit={submit} noValidate>
    <Stack spacing={2.25}>
      <AuthBrandPill label="ورود به نرم‌افزار" />
      <Box>
        <Typography variant="h5">ورود کاربر محلی</Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mt: .75, lineHeight: 1.9 }}>
          این ورود با حساب ایتا یا سایر پیام‌رسان‌ها جداست و مشخص می‌کند چه کسی به امکانات نرم‌افزار دسترسی دارد.
        </Typography>
      </Box>
      <TextField
        label="نام کاربری نرم‌افزار"
        value={username}
        onChange={event => setUsername(event.target.value)}
        autoComplete="username"
        autoFocus
        inputProps={{ dir: 'ltr', spellCheck: false }}
      />
      <TextField
        label="رمز ورود نرم‌افزار"
        type="password"
        value={password}
        onChange={event => setPassword(event.target.value)}
        autoComplete="current-password"
      />
      {error && <Alert severity="error">{error}</Alert>}
      <Button
        type="submit"
        size="large"
        variant="contained"
        disabled={busy || !username.trim() || !password}
        startIcon={busy ? <CircularProgress size={18} color="inherit" /> : undefined}
      >
        {busy ? 'در حال بررسی…' : 'ورود به نرم‌افزار'}
      </Button>
      {registrationEnabled && <Button
        type="button"
        size="large"
        variant="text"
        disabled={busy}
        onClick={() => setMode('register')}
      >
        کاربر جدید هستم
      </Button>}
    </Stack>
  </Box></LoginSurface>
}

function AppUserRegister({
  onBack,
  onComplete,
}: {
  onBack: () => void
  onComplete: () => Promise<void>
}) {
  const [displayName, setDisplayName] = useState('')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [confirmation, setConfirmation] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setError('')
    if (password !== confirmation) {
      setError('تکرار رمز ورود با رمز انتخاب‌شده یکسان نیست.')
      return
    }
    setBusy(true)
    try {
      await api('POST', '/api/v2/app-auth/register', {
        display_name: displayName,
        username,
        password,
      })
      setPassword('')
      setConfirmation('')
      await onComplete()
    } catch (reason) {
      setPassword('')
      setConfirmation('')
      setError(reason instanceof Error ? reason.message : 'ثبت‌نام کاربر انجام نشد.')
    } finally {
      setBusy(false)
    }
  }

  return <LoginSurface><Box component="form" onSubmit={submit} noValidate>
    <Stack spacing={2}>
      <AuthBrandPill label="ثبت‌نام در شبکه خصوصی" />
      <Box>
        <Typography variant="h5">ساخت حساب کاربری</Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mt: 0.75, lineHeight: 1.9 }}>
          پس از ثبت‌نام می‌توانید حساب ایتای خودتان را اضافه کنید. حساب بله در فاز بعدی فعال خواهد شد.
        </Typography>
      </Box>
      <TextField
        label="نام نمایشی"
        value={displayName}
        onChange={event => setDisplayName(event.target.value)}
        autoComplete="name"
        autoFocus
      />
      <TextField
        label="نام کاربری نرم‌افزار"
        value={username}
        onChange={event => setUsername(event.target.value)}
        autoComplete="username"
        inputProps={{ dir: 'ltr', spellCheck: false }}
        helperText="۳ تا ۶۴ نویسه؛ حروف، عدد، نقطه، خط تیره یا زیرخط"
      />
      <TextField
        label="رمز ورود"
        type="password"
        value={password}
        onChange={event => setPassword(event.target.value)}
        autoComplete="new-password"
        helperText="حداقل ۴ نویسه؛ رمز ۴ رقمی نیز پذیرفته می‌شود."
        inputProps={{ minLength: 4, maxLength: 128 }}
      />
      <TextField
        label="تکرار رمز ورود"
        type="password"
        value={confirmation}
        onChange={event => setConfirmation(event.target.value)}
        autoComplete="new-password"
        inputProps={{ minLength: 4, maxLength: 128 }}
      />
      {error && <Alert severity="error">{error}</Alert>}
      <Button
        type="submit"
        size="large"
        variant="contained"
        disabled={
          busy
          || !displayName.trim()
          || !username.trim()
          || password.length < 4
          || confirmation.length < 4
        }
        startIcon={busy ? <CircularProgress size={18} color="inherit" /> : undefined}
      >
        {busy ? 'در حال ثبت‌نام…' : 'ثبت‌نام و ادامه'}
      </Button>
      <Button type="button" size="large" disabled={busy} onClick={onBack}>
        بازگشت به ورود
      </Button>
    </Stack>
  </Box></LoginSurface>
}

function AppUserSetup({ onComplete }: { onComplete: () => Promise<void> }) {
  const [displayName, setDisplayName] = useState('')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [confirmation, setConfirmation] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setError('')
    if (password !== confirmation) {
      setError('تکرار رمز ورود با رمز انتخاب‌شده یکسان نیست.')
      return
    }
    setBusy(true)
    try {
      await api('POST', '/api/v2/app-auth/setup', {
        display_name: displayName,
        username,
        password,
      })
      setPassword('')
      setConfirmation('')
      await onComplete()
    } catch (reason) {
      setPassword('')
      setConfirmation('')
      setError(reason instanceof Error ? reason.message : 'ساخت مدیر اولیه انجام نشد.')
    } finally {
      setBusy(false)
    }
  }

  return <LoginSurface><Box component="form" onSubmit={submit} noValidate>
    <Stack spacing={2}>
      <AuthBrandPill label="راه‌اندازی امن" />
      <Box>
        <Typography variant="h5">ساخت مدیر اولیه نرم‌افزار</Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mt: .75, lineHeight: 1.9 }}>
          این مرحله فقط یک‌بار انجام می‌شود. نام کاربری و رمز را همین‌جا وارد کنید و آن‌ها را در چت ارسال نکنید.
        </Typography>
      </Box>
      <TextField
        label="نام نمایشی"
        value={displayName}
        onChange={event => setDisplayName(event.target.value)}
        autoComplete="name"
        autoFocus
      />
      <TextField
        label="نام کاربری نرم‌افزار"
        value={username}
        onChange={event => setUsername(event.target.value)}
        autoComplete="username"
        inputProps={{ dir: 'ltr', spellCheck: false }}
        helperText="۳ تا ۶۴ نویسه؛ حروف، عدد، نقطه، خط تیره یا زیرخط"
      />
      <TextField
        label="رمز ورود"
        type="password"
        value={password}
        onChange={event => setPassword(event.target.value)}
        autoComplete="new-password"
        helperText="حداقل ۴ نویسه؛ رمز ۴ رقمی نیز پذیرفته می‌شود."
        inputProps={{ minLength: 4, maxLength: 128 }}
      />
      <TextField
        label="تکرار رمز ورود"
        type="password"
        value={confirmation}
        onChange={event => setConfirmation(event.target.value)}
        autoComplete="new-password"
      />
      {error && <Alert severity="error">{error}</Alert>}
      <Button
        type="submit"
        size="large"
        variant="contained"
        disabled={
          busy
          || !displayName.trim()
          || !username.trim()
          || password.length < 4
          || confirmation.length < 4
        }
        startIcon={busy ? <CircularProgress size={18} color="inherit" /> : undefined}
      >
        {busy ? 'در حال ساخت مدیر…' : 'ساخت مدیر و ورود'}
      </Button>
    </Stack>
  </Box></LoginSurface>
}
