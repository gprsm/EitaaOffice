import { StrictMode, useMemo } from 'react'
import { createRoot } from 'react-dom/client'
import { CacheProvider } from '@emotion/react'
import { CssBaseline, ThemeProvider } from '@mui/material'
import { ColorModeContext, createAppTheme } from './theme'
import { rtlCache } from './rtlCache'
import App from './App'
import { appAuthRequestHeaders, reportClientConnectivity } from './lib/api'
import { ClientErrorBoundary, installGlobalErrorReporting } from './ClientErrorBoundary'
import { ConnectionStatus } from './ConnectionStatus'
import { MaterialToastHost } from './MaterialToast'

async function browserApi(method: string, path: string, body?: unknown, csrfToken?: string, messengerAccountId?: string, correlationId?: string) {
  const headers: Record<string, string> = {
    Accept: 'application/json',
    'X-Eitaa-Client-Kind': 'browser',
  }
  if (csrfToken) headers['X-CSRF-Token'] = csrfToken
  if (messengerAccountId) headers['X-Eitaa-Messenger-Account'] = messengerAccountId
  if (correlationId) headers['X-Eitaa-Correlation-Id'] = correlationId
  const options: RequestInit = { method, headers, credentials: 'same-origin' }
  if (body !== undefined && method !== 'GET') { (options.headers as Record<string, string>)['Content-Type'] = 'application/json'; options.body = JSON.stringify(body) }
  const attempts = method === 'GET' ? 2 : 1
  let lastError: unknown = null
  for (let attempt = 0; attempt < attempts; attempt += 1) {
    const controller = new AbortController()
    const timeout = window.setTimeout(() => controller.abort(), path.includes('/media-preview') || path.includes('/messages/sync') ? 120_000 : 60_000)
    try {
      const response = await fetch(path, { ...options, signal: controller.signal })
      reportClientConnectivity('online')
      return { status: response.status, payload: await response.json() }
    } catch (error) {
      if (error instanceof SyntaxError) {
        reportClientConnectivity('online')
        throw error
      }
      lastError = error
      if (attempt + 1 < attempts) await new Promise(resolve => window.setTimeout(resolve, 350))
    } finally {
      window.clearTimeout(timeout)
    }
  }
  reportClientConnectivity('offline')
  throw lastError instanceof Error ? lastError : new Error('Browser API request failed.')
}
async function browserSelectFile(options?: { title?: string; filters?: Array<{ name: string; extensions: string[] }>; messengerAccountId?: string }) {
  const input = document.createElement('input'); input.type = 'file'
  const extensions = options?.filters?.flatMap(item => item.extensions || []).filter(value => value && value !== '*') || []
  if (extensions.length) input.accept = extensions.map(value => `.${value}`).join(',')
  const file = await new Promise<File | null>(resolve => { input.addEventListener('change', () => resolve(input.files?.[0] || null), { once: true }); input.addEventListener('cancel', () => resolve(null), { once: true }); input.click() })
  if (!file) return null
  let response: Response
  try {
    response = await fetch('/api/v1/files/upload', {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        'Content-Type': 'application/octet-stream',
        'X-Eitaa-Client-Kind': 'browser',
        'X-Eitaa-Filename': encodeURIComponent(file.name),
        ...appAuthRequestHeaders(),
      },
      body: file,
    })
    reportClientConnectivity('online')
  } catch {
    reportClientConnectivity('offline')
    throw new Error('ارتباط هنگام بارگذاری فایل قطع شد؛ فایل دوباره ارسال نشده است.')
  }
  const payload = await response.json()
  if (!response.ok || payload?.ok === false) throw new Error(payload?.error?.message || 'بارگذاری فایل ناموفق بود.')
  return String(payload.path || '') || null
}
const BROWSER_LOGIN_APPEARANCE_KEY = 'eitaa-bridge.ui.login-appearance.preview'
const browserLoginAppearanceDefault: LoginAppearanceValue = {
  backgroundDataUrl: null,
  backgroundFile: null,
  backgroundFileName: null,
  position: 'center',
  overlay: 0.58,
}
function browserLoginAppearance(): LoginAppearanceValue {
  try {
    const stored = JSON.parse(localStorage.getItem(BROWSER_LOGIN_APPEARANCE_KEY) || '{}')
    return {
      ...browserLoginAppearanceDefault,
      ...stored,
      position: ['center', 'top', 'bottom'].includes(stored.position) ? stored.position : 'center',
      overlay: Math.min(0.82, Math.max(0.2, Number(stored.overlay) || 0.58)),
    }
  } catch { return { ...browserLoginAppearanceDefault } }
}
function storeBrowserLoginAppearance(value: LoginAppearanceValue) {
  localStorage.setItem(BROWSER_LOGIN_APPEARANCE_KEY, JSON.stringify(value))
  return value
}

const visualFixtureEnabled = (import.meta.env.DEV || import.meta.env.VITE_PHASE9_VISUAL_FIXTURE === '1')
  && new URLSearchParams(window.location.search).get('__phase9_visual_fixture') === '1'

function phase9VisualFixtureApi(method: string, rawPath: string, body?: unknown, _csrf?: string, accountId?: string, _correlationId?: string) {
  const path = rawPath.split('?', 1)[0]
  const params = new URLSearchParams(window.location.search)
  const userKind = params.get('__phase9_user') === 'operator' ? 'operator' : 'admin'
  const selectedAccount = accountId || (userKind === 'operator'
    ? '22222222-2222-4222-8222-222222222222'
    : '11111111-1111-4111-8111-111111111111')
  const principal = {
    app_user_id: userKind === 'operator'
      ? 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb'
      : 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
    display_name: userKind === 'operator' ? 'اپراتور آزمایشی' : 'مدیر آزمایشی',
    global_role: userKind === 'operator' ? 'user' : 'admin',
    permissions: { manage_users: userKind === 'admin', use_legacy_workspace: true },
  }
  const accounts = [
    {
      messenger_account_id: selectedAccount,
      phone_account_id: userKind === 'operator'
        ? '44444444-4444-4444-8444-444444444444'
        : '33333333-3333-4333-8333-333333333333',
      provider: 'eitaa',
      label: userKind === 'operator' ? 'حساب پشتیبانی' : 'حساب تحریریه',
      phone_hint: userKind === 'operator' ? '+••••••••۴۵' : '+••••••••۶۷',
      membership_role: userKind === 'operator' ? 'operator' : 'admin',
      lifecycle_state: 'active',
      desired_worker_state: 'running',
      auth_state: 'authenticated',
      session_generation: 2,
      storage_revision: 1,
      worker: { worker_instance_id: '55555555-5555-4555-8555-555555555555', generation: 2, runtime_state: 'ready', process_id: 1234, last_heartbeat_at: new Date().toISOString(), safe_reason_code: null },
      permissions: { view: true, operate: true, manage_worker: userKind === 'admin' },
    },
  ]
  const dialogs = [
    { peer_key: 'channel:101', peer: { id: 101, type: 'channel', title: 'اخبار فناوری', username: 'tech_news', access_hash_present: true }, peer_file: 'fixture-channel.json', technical_kind: 'channel', display_kind: 'channel', display_kind_locked: false, favorite: true, source: 'fixture', top_message_id: 106, unread_count: 3, unread_mentions_count: 0, read_inbox_max_id: 103, pinned: true, unread_mark: false, participants_count: 1240 },
    { peer_key: 'chat:202', peer: { id: 202, type: 'chat', title: 'گروه تحریریه', username: null, access_hash_present: true }, peer_file: 'fixture-group.json', technical_kind: 'supergroup', display_kind: 'group', display_kind_locked: false, favorite: false, source: 'fixture', top_message_id: 205, unread_count: 0, unread_mentions_count: 0, read_inbox_max_id: 205, pinned: false, unread_mark: false, participants_count: 38 },
    { peer_key: 'user:303', peer: { id: 303, type: 'user', title: 'مخاطب نمونه', username: 'sample_user', access_hash_present: true }, peer_file: 'fixture-user.json', technical_kind: 'private', display_kind: 'personal', display_kind_locked: false, favorite: false, source: 'fixture', top_message_id: 304, unread_count: 1, unread_mentions_count: 0, read_inbox_max_id: 303, pinned: false, unread_mark: false },
  ]
  const messages = Array.from({ length: 16 }, (_, index) => {
    const id = 91 + index
    return {
      id,
      date: new Date(Date.now() - (16 - index) * 180_000).toISOString(),
      text: index % 4 === 0
        ? 'این یک پیام نمونهٔ نسبتاً بلند برای بررسی چیدمان راست‌به‌چپ، شکست صحیح خطوط و خوانایی رابط در نمایشگرهای مختلف است.'
        : `پیام نمونه شمارهٔ ${(index + 1).toLocaleString('fa-IR')}`,
      text_length: 24,
      media: null,
      outgoing: index % 3 === 0,
      sender_key: index % 3 === 0 ? null : 'user:404',
      sender_display_name: index % 3 === 0 ? null : 'همکار نمونه',
      sender_username: index % 3 === 0 ? null : 'colleague',
      sender_is_eitaa_contact: true,
      sender_resolution: index % 3 === 0 ? 'self' : 'eitaa_contact',
      usage: { used: false, usage_state: 'unused', stale: false, compositions: [] },
    }
  })
  let payload: Record<string, unknown> = { ok: true }
  if (path === '/api/v2/app-auth/status' || path === '/api/v2/app-auth/me') payload = { ok: true, enabled: true, setup_required: false, authenticated: true, self_registration_enabled: true, principal, csrf_token: 'phase9-visual-csrf', idle_expires_at: new Date(Date.now() + 365 * 24 * 60 * 60_000).toISOString(), absolute_expires_at: new Date(Date.now() + 365 * 24 * 60 * 60_000).toISOString() }
  else if (method === 'GET' && path === '/api/v2/messenger-accounts') payload = { ok: true, feature_enabled: true, default_messenger_account_id: selectedAccount, accounts, provider_adapters: { eitaa: { provider: 'eitaa', display_name: 'ایتا', configured: true, runtime_enabled: true, onboarding_enabled: true, account_identity_kind: 'phone_e164', auth_steps: ['identity', 'challenge', 'second_factor_optional'], account_kind: 'personal', implementation_state: 'live_accepted', capabilities: ['auth.logout', 'auth.phone', 'contacts.read', 'dialogs.read', 'history.read', 'media.read', 'media.send', 'messages.send', 'updates.live'] }, bale: { provider: 'bale', display_name: 'بله', configured: false, runtime_enabled: false, onboarding_enabled: false, account_identity_kind: null, auth_steps: [], account_kind: 'personal', implementation_state: 'implemented', capabilities: [], reason_code: 'provider_adapter_not_configured' } } }
  else if (method === 'GET' && /^\/api\/v2\/messenger-accounts\/[0-9a-f-]{36}\/capabilities$/i.test(path)) payload = { ok: true, messenger_account_id: selectedAccount, provider: 'eitaa', implementation_state: 'live_accepted', runtime_enabled: true, capabilities: ['contacts.read', 'contacts.write', 'dialogs.read', 'history.read', 'media.read', 'media.send', 'messages.send'].map(capability => ({ capability, status: 'supported', reason_code: 'provider_capability_supported', constraints_present: false, revision: 1 })) }
  else if (method === 'POST' && path === '/api/v2/messenger-accounts') payload = { ok: true, account: { ...accounts[0], messenger_account_id: '88888888-8888-4888-8888-888888888888', phone_account_id: '99999999-9999-4999-8999-999999999999', label: typeof body === 'object' && body && 'label' in body ? String(body.label || '') || null : null, phone_hint: '+••••••••89', lifecycle_state: 'created', desired_worker_state: 'stopped', auth_state: 'absent', worker: null } }
  else if (path === '/api/v1/auth/status') payload = { ok: true, authenticated: true, session_present: true, password_pending: false }
  else if (path === '/api/v1/sites') payload = { ok: true, default_site_key: 'main', sites: [{ site_key: 'main', base_url: 'https://example.invalid', is_default: true, default_status: 'draft', credentials_configured: true }] }
  else if (path === '/api/v1/settings/sites') payload = { ok: true, sites: [{ site_key: 'main', base_url: 'https://example.invalid', is_default: true, default_status: 'draft', default_category_id: null, timeout_seconds: 30, verify_tls: true, retry_attempts: 2, allow_insecure_http: false, username_configured: true, application_password_configured: true, credentials_configured: true }] }
  else if (path === '/api/v1/dialogs/list' || path === '/api/v1/dialogs/live-sync') payload = { ok: true, dialogs }
  else if (path === '/api/v1/messages/list') payload = { ok: true, messages }
  else if (path === '/api/v1/wordpress/categories') payload = { ok: true, terms: [{ id: 1, name: 'فناوری', slug: 'technology', parent_id: null }, { id: 2, name: 'اخبار', slug: 'news', parent_id: null }] }
  else if (path === '/api/v1/wordpress/tags') payload = { ok: true, terms: [{ id: 3, name: 'ایران', slug: 'iran' }] }
  else if (path === '/api/v1/messages/index/results') payload = { ok: true, results: [], labels: [] }
  else if (path === '/api/v1/dialogs/avatar') payload = { ok: true, avatar_present: false }
  else if (path === '/api/v1/contacts/categories') payload = { ok: true, categories: [] }
  else if (path === '/api/v2/app-auth/sessions') payload = { ok: true, sessions: [{ session_id: '66666666-6666-4666-8666-666666666666', current: true, status: 'active', client_kind: 'browser', device_label: 'Web browser', created_at: new Date(Date.now() - 120_000).toISOString(), last_seen_at: new Date().toISOString(), idle_expires_at: new Date(Date.now() + 365 * 24 * 60 * 60_000).toISOString(), absolute_expires_at: new Date(Date.now() + 365 * 24 * 60 * 60_000).toISOString(), revoked_at: null, safe_reason_code: null, expires_soon: false, recent_login: false }] }
  else if (path === '/api/v2/app-users') payload = { ok: true, users: [{ ...principal, status: 'active', credential_configured: true, active_session_count: 1 }] }
  else if (path === '/api/v2/phone-accounts') payload = { ok: true, phone_accounts: [] }
  else if (path === '/api/v2/app-integrations') payload = { ok: true, can_manage: userKind === 'admin', integrations: [{ integration_id: '77777777-7777-4777-8777-777777777777', integration_type: 'wordpress', integration_key: 'main', display_name: 'WordPress (main)', status: 'active' }] }
  else if (method === 'POST' && path === '/api/v1/dialogs/read') payload = { ok: true }
  void body
  return Promise.resolve({ status: 200, payload })
}

if (visualFixtureEnabled && !('eitaaDesktop' in window)) {
  document.documentElement.dataset.visualFixture = 'phase9'
  Object.defineProperty(window, 'eitaaDesktop', {
    value: {
      api: phase9VisualFixtureApi,
      reportDiagnostic: async () => true,
      openExternal: async () => undefined,
      selectFile: async () => null,
      selectUploadFile: async () => null,
      loginAppearance: {
        get: async () => browserLoginAppearanceDefault,
        selectBackground: async () => browserLoginAppearanceDefault,
        save: async () => browserLoginAppearanceDefault,
        clearBackground: async () => browserLoginAppearanceDefault,
      },
      openLogs: async () => undefined,
      platform: 'win32',
      windowControls: {
        minimize: async () => undefined,
        toggleMaximize: async () => false,
        close: async () => undefined,
        isMaximized: async () => false,
        onMaximized: () => () => undefined,
      },
    },
    configurable: false,
    writable: false,
  })
}

async function browserSelectLoginBackground() {
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = 'image/avif,image/jpeg,image/png,image/webp'
  const file = await new Promise<File | null>(resolve => {
    input.addEventListener('change', () => resolve(input.files?.[0] || null), { once: true })
    input.addEventListener('cancel', () => resolve(null), { once: true })
    input.click()
  })
  if (!file) return browserLoginAppearance()
  if (file.size > 3 * 1024 * 1024) throw new Error('در پیش‌نمایش مرورگر، حجم تصویر باید حداکثر ۳ مگابایت باشد.')
  const backgroundDataUrl = await new Promise<string>((resolve, reject) => {
    const reader = new FileReader()
    reader.addEventListener('load', () => resolve(String(reader.result || '')), { once: true })
    reader.addEventListener('error', () => reject(new Error('خواندن تصویر ناموفق بود.')), { once: true })
    reader.readAsDataURL(file)
  })
  return storeBrowserLoginAppearance({
    ...browserLoginAppearance(),
    backgroundDataUrl,
    backgroundFile: file.name,
    backgroundFileName: file.name,
  })
}
if (!('eitaaDesktop' in window)) {
  Object.defineProperty(window, 'eitaaDesktop', {
    value: {
      api: browserApi,
      reportDiagnostic: async () => false,
      openExternal: async (url: string) => { window.open(url, '_blank', 'noopener,noreferrer') },
      selectFile: browserSelectFile,
      selectUploadFile: browserSelectFile,
      loginAppearance: {
        get: async () => browserLoginAppearance(),
        selectBackground: browserSelectLoginBackground,
        save: async (value: Pick<LoginAppearanceValue, 'position' | 'overlay'>) => storeBrowserLoginAppearance({ ...browserLoginAppearance(), ...value }),
        clearBackground: async () => storeBrowserLoginAppearance({ ...browserLoginAppearance(), backgroundDataUrl: null, backgroundFile: null, backgroundFileName: null }),
      },
      openLogs: async () => { window.alert('گزارش‌ها در پوشه runtime\\logs محل نصب برنامه ذخیره می‌شوند.') },
      platform: 'win32',
      windowControls: {
        minimize: async () => undefined,
        toggleMaximize: async () => false,
        close: async () => window.close(),
        isMaximized: async () => false,
        onMaximized: () => () => undefined,
      },
    },
    configurable: false,
    writable: false,
  })
}

document.documentElement.lang = 'fa'
document.documentElement.dir = 'rtl'
document.documentElement.dataset.theme = 'dark'
document.documentElement.style.colorScheme = 'dark'
localStorage.setItem('eitaa-bridge.display-mode', 'dark')

function Root() {
  const appTheme = useMemo(() => createAppTheme(), [])
  const fixedDarkMode = useMemo(() => ({
    mode: 'dark' as const,
    resolvedMode: 'dark' as const,
    setMode: () => undefined,
  }), [])
  return <ColorModeContext.Provider value={fixedDarkMode}><CacheProvider value={rtlCache}><ThemeProvider theme={appTheme}><CssBaseline enableColorScheme /><ConnectionStatus /><App /><MaterialToastHost /></ThemeProvider></CacheProvider></ColorModeContext.Provider>
}
installGlobalErrorReporting()
createRoot(document.getElementById('root')!).render(<StrictMode><ClientErrorBoundary><Root /></ClientErrorBoundary></StrictMode>)
