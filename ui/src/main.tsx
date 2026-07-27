import { StrictMode, useMemo } from 'react'
import { createRoot } from 'react-dom/client'
import { ToastContainer } from 'react-toastify'
import { CacheProvider } from '@emotion/react'
import { CssBaseline, ThemeProvider } from '@mui/material'
import { ColorModeContext, createAppTheme } from './theme'
import { rtlCache } from './rtlCache'
import App from './App'
import 'react-toastify/dist/ReactToastify.css'
import './styles.css'
import './login-experience.css'

async function browserApi(method: string, path: string, body?: unknown) {
  const options: RequestInit = { method, headers: { Accept: 'application/json' } }
  if (body !== undefined && method !== 'GET') { (options.headers as Record<string, string>)['Content-Type'] = 'application/json'; options.body = JSON.stringify(body) }
  const response = await fetch(path, options)
  return { status: response.status, payload: await response.json() }
}
async function browserSelectFile(options?: { title?: string; filters?: Array<{ name: string; extensions: string[] }> }) {
  const input = document.createElement('input'); input.type = 'file'
  const extensions = options?.filters?.flatMap(item => item.extensions || []).filter(value => value && value !== '*') || []
  if (extensions.length) input.accept = extensions.map(value => `.${value}`).join(',')
  const file = await new Promise<File | null>(resolve => { input.addEventListener('change', () => resolve(input.files?.[0] || null), { once: true }); input.addEventListener('cancel', () => resolve(null), { once: true }); input.click() })
  if (!file) return null
  const response = await fetch('/api/v1/files/upload', { method: 'POST', headers: { 'Content-Type': 'application/octet-stream', 'X-Eitaa-Filename': encodeURIComponent(file.name) }, body: file })
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
  return <ColorModeContext.Provider value={fixedDarkMode}><CacheProvider value={rtlCache}><ThemeProvider theme={appTheme}><CssBaseline enableColorScheme /><App /><ToastContainer position="top-center" autoClose={2800} hideProgressBar newestOnTop closeOnClick rtl pauseOnFocusLoss={false} limit={3} theme="dark" /></ThemeProvider></CacheProvider></ColorModeContext.Provider>
}
createRoot(document.getElementById('root')!).render(<StrictMode><Root /></StrictMode>)
