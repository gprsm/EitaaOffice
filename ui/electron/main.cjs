const { app, BrowserWindow, ipcMain, shell, dialog, protocol, net: electronNet } = require('electron')
const { spawn } = require('node:child_process')
const path = require('node:path')
const fs = require('node:fs')
const net = require('node:net')
const { randomUUID } = require('node:crypto')
const {
  EVENTS: OBSERVABILITY_EVENTS,
  StructuredDesktopLogger,
  normalizeCorrelationId,
  sanitizeRoutePath,
  validateClientDiagnostic,
} = require('./observability.cjs')

const DEFAULT_DESKTOP_HOST = '127.0.0.1'
const DEFAULT_DESKTOP_PORT = 8765
const DESKTOP_MEDIA_SCHEME = 'eitaa-media'
const DESKTOP_MEDIA_PATH = /^\/api\/v1\/media-cache\/[0-9a-f]{32}$/
const FALLBACK_BRIDGE_VERSION = '0.7.0-ui-mvp6.1.1-gmi4.2'
const LOGIN_BACKGROUND_MAX_BYTES = 15 * 1024 * 1024
const LOGIN_BACKGROUND_MIME = {
  '.avif': 'image/avif',
  '.jpeg': 'image/jpeg',
  '.jpg': 'image/jpeg',
  '.png': 'image/png',
  '.webp': 'image/webp',
}
const DEFAULT_LOGIN_APPEARANCE = {
  backgroundFile: null,
  backgroundFileName: null,
  position: 'center',
  overlay: 0.58,
}
let apiStartupError = ''
protocol.registerSchemesAsPrivileged([
  {
    scheme: DESKTOP_MEDIA_SCHEME,
    privileges: { secure: true, standard: true, supportFetchAPI: true, stream: true },
  },
])
const gotSingleInstanceLock = app.requestSingleInstanceLock()
if (!gotSingleInstanceLock) app.quit()
else app.on('second-instance', () => {
  if (!mainWindow) return
  if (mainWindow.isMinimized()) mainWindow.restore()
  mainWindow.show()
  mainWindow.focus()
})

let mainWindow = null
let apiProcess = null
let apiLogFd = null
let appSessionCookie = ''
let selectedMessengerAccountId = ''
let cachedDesktopEndpoint = null
let desktopLogger = null
const rendererDiagnosticWindow = []
const CANONICAL_ACCOUNT_ID = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/

function projectRoot() {
  if (app.isPackaged) return path.join(path.dirname(process.execPath), 'bridge-runtime')
  return path.resolve(__dirname, '..', '..')
}
function expectedBridgeVersion(root = projectRoot()) {
  try {
    const firstLine = fs.readFileSync(path.join(root, 'VERSION.txt'), 'utf8').split(/\r?\n/, 1)[0].trim()
    if (/^[A-Za-z0-9][A-Za-z0-9._+-]{0,127}$/.test(firstLine)) return firstLine
  } catch { /* packaged fallback remains fail-closed to the release version */ }
  return FALLBACK_BRIDGE_VERSION
}
function desktopEndpoint(root = projectRoot()) {
  if (cachedDesktopEndpoint) return cachedDesktopEndpoint
  let mode = 'desktop_loopback'
  let host = DEFAULT_DESKTOP_HOST
  let port = DEFAULT_DESKTOP_PORT
  try {
    const payload = JSON.parse(fs.readFileSync(path.join(root, 'bridge.json'), 'utf8'))
    if (payload?.deployment) {
      mode = String(payload.deployment.mode || '')
      host = String(payload.deployment.bind?.host || '')
      port = Number(payload.deployment.bind?.port)
    }
  } catch (error) {
    if (error?.code !== 'ENOENT') throw new Error('Desktop deployment configuration is invalid.')
  }
  if (mode !== 'desktop_loopback') {
    throw new Error('Electron may start only the desktop_loopback deployment profile.')
  }
  if (!net.isIP(host) || !Number.isInteger(port) || port < 1 || port > 65535) {
    throw new Error('Desktop Loopback bind configuration is invalid.')
  }
  const address = net.isIPv6(host) ? `[${host}]` : host
  cachedDesktopEndpoint = { baseUrl: `http://${address}:${port}`, host, port }
  return cachedDesktopEndpoint
}
function backendEnvironment(root) {
  const environment = { ...process.env }
  const sourcePackages = path.join(root, 'src')
  if (fs.existsSync(path.join(sourcePackages, 'eitaa_bridge'))) {
    environment.PYTHONPATH = [sourcePackages, environment.PYTHONPATH].filter(Boolean).join(path.delimiter)
  }
  return environment
}
function runtimeLogPath(name) {
  const directory = path.join(projectRoot(), 'runtime', 'logs')
  fs.mkdirSync(directory, { recursive: true })
  return path.join(directory, name)
}
function loginAppearanceDirectory() {
  const directory = path.join(projectRoot(), 'runtime', 'ui')
  fs.mkdirSync(directory, { recursive: true })
  return directory
}
function loginAppearanceConfigPath() {
  return path.join(loginAppearanceDirectory(), 'login-appearance.json')
}
function sanitizeLoginAppearance(value = {}) {
  const position = ['center', 'top', 'bottom'].includes(value.position) ? value.position : 'center'
  const selectedOverlay = Number(value.overlay)
  const overlay = Number.isFinite(selectedOverlay)
    ? Math.min(0.82, Math.max(0.2, selectedOverlay))
    : DEFAULT_LOGIN_APPEARANCE.overlay
  const rawFile = typeof value.backgroundFile === 'string' ? path.basename(value.backgroundFile) : null
  const backgroundFile = rawFile && /^login-background\.(?:avif|jpe?g|png|webp)$/i.test(rawFile) ? rawFile : null
  const backgroundFileName = backgroundFile && typeof value.backgroundFileName === 'string'
    ? path.basename(value.backgroundFileName).slice(0, 180)
    : null
  return { backgroundFile, backgroundFileName, position, overlay }
}
function writeLoginAppearance(value) {
  const config = sanitizeLoginAppearance(value)
  const target = loginAppearanceConfigPath()
  const temporary = `${target}.${process.pid}.${Date.now()}.tmp`
  fs.writeFileSync(temporary, `${JSON.stringify(config, null, 2)}\n`, 'utf8')
  fs.renameSync(temporary, target)
  return config
}
function readLoginAppearance() {
  let config = { ...DEFAULT_LOGIN_APPEARANCE }
  try {
    const parsed = JSON.parse(fs.readFileSync(loginAppearanceConfigPath(), 'utf8'))
    config = sanitizeLoginAppearance(parsed)
  } catch { /* missing or invalid appearance settings fall back safely */ }
  let backgroundDataUrl = null
  if (config.backgroundFile) {
    const filePath = path.join(loginAppearanceDirectory(), config.backgroundFile)
    try {
      const stat = fs.statSync(filePath)
      const extension = path.extname(filePath).toLowerCase()
      const mime = LOGIN_BACKGROUND_MIME[extension]
      if (stat.isFile() && stat.size <= LOGIN_BACKGROUND_MAX_BYTES && mime) {
        backgroundDataUrl = `data:${mime};base64,${fs.readFileSync(filePath).toString('base64')}`
      }
    } catch { /* a missing image is represented as an empty background */ }
  }
  return { ...config, backgroundDataUrl }
}
function removeStoredLoginBackground(exceptFile = null) {
  const directory = loginAppearanceDirectory()
  for (const name of fs.readdirSync(directory)) {
    if (!/^login-background\.(?:avif|jpe?g|png|webp)$/i.test(name) || name === exceptFile) continue
    try { fs.unlinkSync(path.join(directory, name)) } catch { /* best effort cleanup */ }
  }
}
function rotateLogFile(filePath, maxBytes = 5 * 1024 * 1024, backupCount = 5) {
  try {
    if (!fs.existsSync(filePath) || fs.statSync(filePath).size < maxBytes) return
    for (let index = backupCount - 1; index >= 1; index -= 1) {
      const source = `${filePath}.${index}`
      const target = `${filePath}.${index + 1}`
      if (fs.existsSync(source)) fs.renameSync(source, target)
    }
    fs.renameSync(filePath, `${filePath}.1`)
  } catch { /* logging must never block startup */ }
}
function desktopLog(event, options = {}) {
  if (!desktopLogger) desktopLogger = new StructuredDesktopLogger(runtimeLogPath('desktop.log'))
  return desktopLogger.emit(event, options)
}
process.on('uncaughtExceptionMonitor', error => desktopLog(
  OBSERVABILITY_EVENTS.UNCAUGHT_EXCEPTION,
  { level: 'critical', result: 'failed', reasonCode: 'uncaught_exception', fields: { error_type: error?.name || 'Error' } },
))
process.on('warning', warning => desktopLog(
  OBSERVABILITY_EVENTS.PROCESS_WARNING,
  { level: 'warning', result: 'degraded', reasonCode: 'process_warning', fields: { warning_type: warning?.name || 'Warning' } },
))
async function health(timeoutMs = 1600) {
  try {
    const response = await fetch(`${desktopEndpoint().baseUrl}/api/v1/health`, { signal: AbortSignal.timeout(timeoutMs) })
    if (!response.ok) return null
    return await response.json()
  } catch { return null }
}
function closeApiLog() {
  if (apiLogFd !== null) {
    try { fs.closeSync(apiLogFd) } catch { /* already closed */ }
    apiLogFd = null
  }
}
function startApi() {
  if (apiProcess && !apiProcess.killed) return
  const root = projectRoot()
  const exe = path.join(root, '.venv', 'Scripts', 'eitaa-bridge-api.exe')
  const python = path.join(root, '.venv', 'Scripts', 'python.exe')
  try { desktopEndpoint(root) } catch (error) {
    apiStartupError = 'پروفایل استقرار Electron باید desktop_loopback معتبر باشد.'
    desktopLog(OBSERVABILITY_EVENTS.API_START_FAILED, { level: 'error', result: 'failed', reasonCode: 'deployment_config_invalid', fields: { error_type: error?.name || 'Error' } })
    return
  }
  const args = ['--config', 'bridge.json']
  closeApiLog()
  const apiLogPath = runtimeLogPath('api.log')
  rotateLogFile(apiLogPath)
  apiLogFd = fs.openSync(apiLogPath, 'a')
  const spawnOptions = {
    cwd: root,
    env: backendEnvironment(root),
    windowsHide: true,
    stdio: ['ignore', apiLogFd, apiLogFd],
  }
  if (!app.isPackaged && fs.existsSync(python)) apiProcess = spawn(python, ['-m', 'eitaa_bridge.interfaces.http_api', ...args], spawnOptions)
  else if (fs.existsSync(exe)) apiProcess = spawn(exe, args, spawnOptions)
  else if (fs.existsSync(python)) apiProcess = spawn(python, ['-m', 'eitaa_bridge.interfaces.http_api', ...args], spawnOptions)
  else {
    apiStartupError = 'محیط Backend پیدا نشد. install_app.bat را اجرا کنید.'
    desktopLog(OBSERVABILITY_EVENTS.API_START_FAILED, { level: 'error', result: 'failed', reasonCode: 'backend_runtime_missing' })
    closeApiLog()
    return
  }
  desktopLog(OBSERVABILITY_EVENTS.API_PROCESS_STARTED, { result: 'succeeded', fields: { process_id: apiProcess.pid || null } })
  apiProcess.once('error', error => desktopLog(OBSERVABILITY_EVENTS.API_PROCESS_ERROR, { level: 'error', result: 'failed', reasonCode: 'api_process_error', fields: { error_type: error?.name || 'Error' } }))
  apiProcess.once('exit', (code, signal) => {
    desktopLog(OBSERVABILITY_EVENTS.API_PROCESS_EXITED, { level: code === 0 ? 'info' : 'warning', result: code === 0 ? 'succeeded' : 'degraded', reasonCode: code === 0 ? null : 'api_process_nonzero_exit', fields: { exit_code: code ?? null, signal_present: Boolean(signal) } })
    apiProcess = null
    closeApiLog()
  })
}
async function waitForExpectedApi(attempts = 80) {
  for (let attempt = 0; attempt < attempts; attempt += 1) {
    await new Promise(resolve => setTimeout(resolve, 250))
    const current = await health()
    if (current?.bridge_version === expectedBridgeVersion()) return true
    if (current && current.bridge_version !== expectedBridgeVersion()) return false
  }
  return false
}
async function ensureApi() {
  apiStartupError = ''
  const existing = await health()
  if (existing) {
    apiStartupError = `یک API خارجی روی پورت محلی فعال است (${existing.bridge_version || 'نامشخص'}). Electron آن را بدون مالکیت بازاستفاده یا متوقف نمی‌کند.`
    desktopLog(OBSERVABILITY_EVENTS.API_OWNERSHIP_CONFLICT, { level: 'warning', result: 'rejected', reasonCode: 'api_ownership_conflict', fields: { bridge_version_present: Boolean(existing.bridge_version) } })
    return false
  }
  startApi()
  const ready = await waitForExpectedApi()
  if (ready) return true
  apiStartupError = `سرویس محلی Eitaa Bridge راه‌اندازی نشد. گزارش: ${runtimeLogPath('api.log')}`
  desktopLog(OBSERVABILITY_EVENTS.API_HEALTH_TIMEOUT, { level: 'error', result: 'failed', reasonCode: 'api_health_timeout' })
  return false
}
async function restartApi() {
  desktopLog(OBSERVABILITY_EVENTS.API_RECOVERY_REQUESTED, { level: 'warning', result: 'started', reasonCode: 'api_health_check_failed' })
  apiStartupError = ''
  if (apiProcess && !apiProcess.killed) {
    try { apiProcess.kill() } catch { /* best effort */ }
    await new Promise(resolve => setTimeout(resolve, 450))
  }
  apiProcess = null
  closeApiLog()
  const external = await health()
  if (external) {
    apiStartupError = `یک API خارجی روی پورت محلی فعال است (${external.bridge_version || 'نامشخص'}).`
    return false
  }
  startApi()
  return await waitForExpectedApi(60)
}
function timeoutFor(targetPath) {
  if (targetPath.includes('/dialogs/sync/status')) return 10000
  if (targetPath.includes('/dialogs/avatar')) return 120000
  if (targetPath.includes('/messages/media-preview')) return 120000
  if (targetPath.includes('/messages/sync')) return 90000
  return 60000
}
function updateAppSessionCookie(setCookie) {
  if (!setCookie || !String(setCookie).toLowerCase().startsWith('eitaa_bridge_app_session=')) return
  const first = String(setCookie).split(';', 1)[0]
  const value = first.slice(first.indexOf('=') + 1)
  appSessionCookie = /(?:^|;)\s*max-age=0(?:;|$)/i.test(String(setCookie)) ? '' : value
}
async function requestApi(method, targetPath, body, csrfToken, messengerAccountId, correlationId) {
  const options = { method, headers: { Accept: 'application/json' }, signal: AbortSignal.timeout(timeoutFor(targetPath)) }
  options.headers['X-Eitaa-Client-Kind'] = 'electron'
  if (correlationId) options.headers['X-Eitaa-Correlation-Id'] = correlationId
  if (appSessionCookie) options.headers.Cookie = `eitaa_bridge_app_session=${appSessionCookie}`
  if (csrfToken) options.headers['X-CSRF-Token'] = String(csrfToken)
  if (messengerAccountId) {
    options.headers['X-Eitaa-Messenger-Account'] = String(messengerAccountId)
  }
  if (body !== undefined && method !== 'GET') {
    options.headers['Content-Type'] = 'application/json'
    options.body = JSON.stringify(body)
  }
  const response = await fetch(`${desktopEndpoint().baseUrl}${targetPath}`, options)
  updateAppSessionCookie(response.headers.get('set-cookie'))
  const payload = await response.json()
  if (
    response.status === 401
    && String(payload?.error?.error_code || '').startsWith('app_auth_')
  ) appSessionCookie = ''
  return { status: response.status, payload }
}
function registerDesktopMediaProtocol() {
  protocol.handle(DESKTOP_MEDIA_SCHEME, async request => {
    let selected
    try { selected = new URL(request.url) } catch { return new Response(null, { status: 400 }) }
    if (
      selected.hostname !== 'bridge'
      || selected.search
      || selected.hash
      || !DESKTOP_MEDIA_PATH.test(selected.pathname)
    ) return new Response(null, { status: 400 })
    const headers = { Accept: '*/*', 'X-Eitaa-Client-Kind': 'electron' }
    if (appSessionCookie) headers.Cookie = `eitaa_bridge_app_session=${appSessionCookie}`
    if (selectedMessengerAccountId) {
      headers['X-Eitaa-Messenger-Account'] = selectedMessengerAccountId
    }
    try {
      return await electronNet.fetch(`${desktopEndpoint().baseUrl}${selected.pathname}`, {
        method: 'GET',
        headers,
        bypassCustomProtocolHandlers: true,
      })
    } catch {
      return new Response(null, { status: 503 })
    }
  })
}
async function createWindow() {
  await ensureApi()
  mainWindow = new BrowserWindow({
    width: 1540, height: 940, minWidth: 680, minHeight: 620,
    backgroundColor: '#f1eee8', title: 'Eitaa Bridge', show: false,
    frame: true, autoHideMenuBar: true,
    webPreferences: {
      preload: path.join(__dirname, 'preload.cjs'), contextIsolation: true,
      nodeIntegration: false, sandbox: true,
    },
  })
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (/^https?:\/\//i.test(url)) shell.openExternal(url)
    return { action: 'deny' }
  })
  mainWindow.on('maximize', () => mainWindow?.webContents.send('window:maximized', true))
  mainWindow.on('unmaximize', () => mainWindow?.webContents.send('window:maximized', false))
  mainWindow.webContents.on('render-process-gone', (_event, details) => desktopLog(
    OBSERVABILITY_EVENTS.RENDERER_PROCESS_GONE,
    { level: 'error', result: 'failed', reasonCode: 'renderer_process_gone', fields: { reason: String(details?.reason || 'unknown').slice(0, 64), exit_code: details?.exitCode ?? null } },
  ))
  mainWindow.webContents.on('unresponsive', () => desktopLog(
    OBSERVABILITY_EVENTS.RENDERER_UNRESPONSIVE,
    { level: 'warning', result: 'degraded', reasonCode: 'renderer_unresponsive' },
  ))
  mainWindow.webContents.on('did-fail-load', (_event, errorCode, _errorDescription, _validatedURL, isMainFrame) => {
    if (!isMainFrame) return
    desktopLog(
      OBSERVABILITY_EVENTS.RENDERER_LOAD_FAILED,
      { level: 'error', result: 'failed', reasonCode: 'renderer_load_failed', fields: { error_code: Number(errorCode) || 0, main_frame: true } },
    )
  })
  const devUrl = process.env.EITAA_UI_DEV_URL
  if (devUrl) await mainWindow.loadURL(devUrl)
  else await mainWindow.loadFile(path.join(__dirname, '..', 'dist', 'index.html'))
  mainWindow.once('ready-to-show', () => mainWindow?.show())
}

ipcMain.handle('api:request', async (_event, request) => {
  if (apiStartupError) {
    const recovered = await restartApi()
    if (!recovered) return { status: 503, payload: { ok: false, error: { component: 'desktop', error_code: 'api_startup_failed', message: apiStartupError, safe_context: { log_file: runtimeLogPath('api.log') } } } }
  }
  const method = String(request?.method || 'GET').toUpperCase()
  const targetPath = String(request?.path || '/api/v1/health')
  const safeTargetPath = sanitizeRoutePath(targetPath)
  const correlationId = normalizeCorrelationId(request?.correlationId) || randomUUID().replaceAll('-', '')
  const suppliedAccountId = String(request?.messengerAccountId || '')
  if (suppliedAccountId && !CANONICAL_ACCOUNT_ID.test(suppliedAccountId)) {
    return { status: 400, payload: { ok: false, error: { component: 'desktop', error_code: 'messenger_account_identifier_invalid', message: 'شناسه حساب پیام‌رسان معتبر نیست.', safe_context: {} } } }
  }
  selectedMessengerAccountId = suppliedAccountId
  try { return await requestApi(method, targetPath, request?.body, request?.csrfToken, suppliedAccountId, correlationId) }
  catch (error) {
    const errorName = error?.name || 'Error'
    desktopLog(OBSERVABILITY_EVENTS.API_REQUEST_FAILED, { level: 'error', result: 'failed', reasonCode: 'desktop_api_request_failed', correlationId, fields: { path: safeTargetPath, error_type: errorName } })
    // A slow media or synchronization call must never kill a healthy API or
    // interrupt a token/session write. Restart only when the health endpoint
    // also proves the process is unavailable.
    const alive = await health(2000)
    if (alive?.bridge_version === expectedBridgeVersion()) {
      return { status: 504, payload: { ok: false, error: { component: 'desktop', error_code: 'api_request_timeout', message: 'درخواست محلی طولانی شد، اما سرویس و نشست همچنان فعال هستند. دوباره تلاش کنید.', safe_context: { error_type: errorName, path: safeTargetPath, correlation_id: correlationId } } } }
    }
    const recovered = await restartApi()
    if (recovered) {
      try { return await requestApi(method, targetPath, request?.body, request?.csrfToken, suppliedAccountId, correlationId) }
      catch (retryError) { desktopLog(OBSERVABILITY_EVENTS.API_RETRY_FAILED, { level: 'error', result: 'failed', reasonCode: 'desktop_api_retry_failed', correlationId, fields: { path: safeTargetPath, error_type: retryError?.name || 'Error' } }) }
    }
    return { status: 503, payload: { ok: false, error: { component: 'desktop', error_code: 'api_unavailable', message: 'سرویس محلی Eitaa Bridge در دسترس نیست. برنامه نشست شما را حذف نکرده است.', safe_context: { error_type: errorName, log_file: runtimeLogPath('api.log') } } } }
  }
})
ipcMain.handle('diagnostics:report', (_event, payload, suppliedCorrelationId) => {
  const diagnostic = validateClientDiagnostic(payload)
  if (!diagnostic) return false
  const now = Date.now()
  while (rendererDiagnosticWindow.length && now - rendererDiagnosticWindow[0] > 60_000) rendererDiagnosticWindow.shift()
  if (rendererDiagnosticWindow.length >= 20) return false
  rendererDiagnosticWindow.push(now)
  const correlationId = normalizeCorrelationId(suppliedCorrelationId) || randomUUID().replaceAll('-', '')
  return desktopLog(OBSERVABILITY_EVENTS.RENDERER_ERROR_REPORTED, {
    level: diagnostic.level,
    result: diagnostic.level === 'error' ? 'failed' : 'degraded',
    reasonCode: diagnostic.event,
    correlationId,
    fields: { client_event: diagnostic.event, error_type: diagnostic.errorType, ...diagnostic.safeContext },
  })
})
ipcMain.handle('shell:open-external', async (_event, url) => { if (/^https?:\/\//i.test(String(url || ''))) await shell.openExternal(url) })
ipcMain.handle('dialog:select-file', async (_event, options) => {
  const result = await dialog.showOpenDialog(mainWindow, {
    title: String(options?.title || 'انتخاب فایل'),
    properties: ['openFile'],
    filters: Array.isArray(options?.filters) ? options.filters : [{ name: 'همه فایل‌ها', extensions: ['*'] }],
  })
  return result.canceled ? null : result.filePaths[0] || null
})
ipcMain.handle('dialog:select-upload-file', async (_event, options) => {
  const result = await dialog.showOpenDialog(mainWindow, {
    title: String(options?.title || 'انتخاب فایل برای ارسال'),
    properties: ['openFile'],
    filters: Array.isArray(options?.filters) ? options.filters : [{ name: 'همه فایل‌ها', extensions: ['*'] }],
  })
  if (result.canceled || !result.filePaths[0]) return null
  const source = path.resolve(result.filePaths[0])
  const suppliedAccountId = String(options?.messengerAccountId || '')
  if (suppliedAccountId && !CANONICAL_ACCOUNT_ID.test(suppliedAccountId)) {
    throw new Error('شناسه حساب پیام‌رسان معتبر نیست.')
  }
  const uploadDirectory = suppliedAccountId
    ? path.join(projectRoot(), 'runtime', 'accounts', suppliedAccountId, 'cache', 'uploads')
    : path.join(projectRoot(), 'runtime', 'uploads')
  fs.mkdirSync(uploadDirectory, { recursive: true })
  const base = path.basename(source).replace(/[<>:\"/\\|?*\x00-\x1f]/g, '_').slice(0, 150) || 'upload.bin'
  const extension = path.extname(base)
  const stem = path.basename(base, extension)
  const destination = path.join(uploadDirectory, `${Date.now()}-${Math.random().toString(36).slice(2, 8)}-${stem}${extension}`)
  fs.copyFileSync(source, destination)
  return destination
})
ipcMain.handle('login-appearance:get', () => readLoginAppearance())
ipcMain.handle('login-appearance:select-background', async () => {
  const result = await dialog.showOpenDialog(mainWindow, {
    title: 'انتخاب تصویر پس‌زمینه صفحه ورود',
    properties: ['openFile'],
    filters: [{ name: 'تصویر', extensions: ['avif', 'jpeg', 'jpg', 'png', 'webp'] }],
  })
  if (result.canceled || !result.filePaths[0]) return readLoginAppearance()
  const source = path.resolve(result.filePaths[0])
  const extension = path.extname(source).toLowerCase()
  const stat = fs.statSync(source)
  if (!LOGIN_BACKGROUND_MIME[extension] || !stat.isFile()) {
    throw new Error('فرمت تصویر انتخاب‌شده پشتیبانی نمی‌شود.')
  }
  if (stat.size > LOGIN_BACKGROUND_MAX_BYTES) {
    throw new Error('حجم تصویر پس‌زمینه باید حداکثر ۱۵ مگابایت باشد.')
  }
  const destinationName = `login-background${extension}`
  const destination = path.join(loginAppearanceDirectory(), destinationName)
  const temporary = `${destination}.${process.pid}.${Date.now()}.tmp`
  fs.copyFileSync(source, temporary)
  fs.renameSync(temporary, destination)
  const current = readLoginAppearance()
  writeLoginAppearance({
    ...current,
    backgroundFile: destinationName,
    backgroundFileName: path.basename(source),
  })
  removeStoredLoginBackground(destinationName)
  return readLoginAppearance()
})
ipcMain.handle('login-appearance:save', (_event, value) => {
  const current = readLoginAppearance()
  writeLoginAppearance({
    ...current,
    position: value?.position,
    overlay: value?.overlay,
  })
  return readLoginAppearance()
})
ipcMain.handle('login-appearance:clear-background', () => {
  const current = readLoginAppearance()
  writeLoginAppearance({
    ...current,
    backgroundFile: null,
    backgroundFileName: null,
  })
  removeStoredLoginBackground()
  return readLoginAppearance()
})
ipcMain.handle('shell:open-logs', async () => { await shell.openPath(path.dirname(runtimeLogPath('desktop.log'))) })
ipcMain.handle('window:minimize', () => mainWindow?.minimize())
ipcMain.handle('window:toggle-maximize', () => { if (!mainWindow) return false; if (mainWindow.isMaximized()) mainWindow.unmaximize(); else mainWindow.maximize(); return mainWindow.isMaximized() })
ipcMain.handle('window:close', () => mainWindow?.close())
ipcMain.handle('window:is-maximized', () => Boolean(mainWindow?.isMaximized()))

app.whenReady().then(() => {
  registerDesktopMediaProtocol()
  return createWindow()
})
app.on('activate', () => { if (BrowserWindow.getAllWindows().length === 0) createWindow() })
app.on('window-all-closed', () => { if (process.platform !== 'darwin') app.quit() })
app.on('before-quit', () => { if (apiProcess && !apiProcess.killed) apiProcess.kill(); closeApiLog() })
