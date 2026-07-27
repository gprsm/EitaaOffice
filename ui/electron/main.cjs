const { app, BrowserWindow, ipcMain, shell, dialog } = require('electron')
const { spawn } = require('node:child_process')
const path = require('node:path')
const fs = require('node:fs')

const API_BASE = 'http://127.0.0.1:8765'
const EXPECTED_BRIDGE_VERSION = '0.7.0-ui-mvp6.1.1-gmi4'
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

function projectRoot() {
  if (app.isPackaged) return path.join(path.dirname(process.execPath), 'bridge-runtime')
  return path.resolve(__dirname, '..', '..')
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
function desktopLog(message) {
  const filePath = runtimeLogPath('desktop.log')
  rotateLogFile(filePath)
  const line = `${new Date().toISOString()} ${message}\n`
  try { fs.appendFileSync(filePath, line, 'utf8') } catch { /* best effort */ }
}
async function health(timeoutMs = 1600) {
  try {
    const response = await fetch(`${API_BASE}/api/v1/health`, { signal: AbortSignal.timeout(timeoutMs) })
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
  const args = ['--config', 'bridge.json', '--host', '127.0.0.1', '--port', '8765']
  closeApiLog()
  const apiLogPath = runtimeLogPath('api.log')
  rotateLogFile(apiLogPath)
  apiLogFd = fs.openSync(apiLogPath, 'a')
  const spawnOptions = { cwd: root, windowsHide: true, stdio: ['ignore', apiLogFd, apiLogFd] }
  if (fs.existsSync(exe)) apiProcess = spawn(exe, args, spawnOptions)
  else if (fs.existsSync(python)) apiProcess = spawn(python, ['-m', 'eitaa_bridge.interfaces.http_api', ...args], spawnOptions)
  else {
    apiStartupError = 'محیط Backend پیدا نشد. install_app.bat را اجرا کنید.'
    desktopLog('API start failed: backend runtime missing')
    closeApiLog()
    return
  }
  desktopLog(`API process started pid=${apiProcess.pid || 'unknown'}`)
  apiProcess.once('error', error => desktopLog(`API process error type=${error?.name || 'Error'}`))
  apiProcess.once('exit', (code, signal) => {
    desktopLog(`API process exited code=${code ?? 'null'} signal=${signal || 'none'}`)
    apiProcess = null
    closeApiLog()
  })
}
async function waitForExpectedApi(attempts = 80) {
  for (let attempt = 0; attempt < attempts; attempt += 1) {
    await new Promise(resolve => setTimeout(resolve, 250))
    const current = await health()
    if (current?.bridge_version === EXPECTED_BRIDGE_VERSION) return true
    if (current && current.bridge_version !== EXPECTED_BRIDGE_VERSION) return false
  }
  return false
}
async function ensureApi() {
  apiStartupError = ''
  const existing = await health()
  if (existing) {
    apiStartupError = `یک API خارجی روی پورت محلی فعال است (${existing.bridge_version || 'نامشخص'}). Electron آن را بدون مالکیت بازاستفاده یا متوقف نمی‌کند.`
    desktopLog(`API ownership conflict: ${existing.bridge_version || 'unknown'}`)
    return false
  }
  startApi()
  const ready = await waitForExpectedApi()
  if (ready) return true
  apiStartupError = `سرویس محلی Eitaa Bridge راه‌اندازی نشد. گزارش: ${runtimeLogPath('api.log')}`
  desktopLog('API failed to become healthy')
  return false
}
async function restartApi() {
  desktopLog('API recovery requested after failed health check')
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
async function requestApi(method, targetPath, body) {
  const options = { method, headers: { Accept: 'application/json' }, signal: AbortSignal.timeout(timeoutFor(targetPath)) }
  if (body !== undefined && method !== 'GET') {
    options.headers['Content-Type'] = 'application/json'
    options.body = JSON.stringify(body)
  }
  const response = await fetch(`${API_BASE}${targetPath}`, options)
  const payload = await response.json()
  return { status: response.status, payload }
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
  try { return await requestApi(method, targetPath, request?.body) }
  catch (error) {
    const errorName = error?.name || 'Error'
    desktopLog(`API request failed path=${targetPath} type=${errorName}`)
    // A slow media or synchronization call must never kill a healthy API or
    // interrupt a token/session write. Restart only when the health endpoint
    // also proves the process is unavailable.
    const alive = await health(2000)
    if (alive?.bridge_version === EXPECTED_BRIDGE_VERSION) {
      return { status: 504, payload: { ok: false, error: { component: 'desktop', error_code: 'api_request_timeout', message: 'درخواست محلی طولانی شد، اما سرویس و نشست همچنان فعال هستند. دوباره تلاش کنید.', safe_context: { error_type: errorName, path: targetPath } } } }
    }
    const recovered = await restartApi()
    if (recovered) {
      try { return await requestApi(method, targetPath, request?.body) }
      catch (retryError) { desktopLog(`API retry failed path=${targetPath} type=${retryError?.name || 'Error'}`) }
    }
    return { status: 503, payload: { ok: false, error: { component: 'desktop', error_code: 'api_unavailable', message: 'سرویس محلی Eitaa Bridge در دسترس نیست. برنامه نشست شما را حذف نکرده است.', safe_context: { error_type: errorName, log_file: runtimeLogPath('api.log') } } } }
  }
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
  const uploadDirectory = path.join(projectRoot(), 'runtime', 'uploads')
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

app.whenReady().then(createWindow)
app.on('activate', () => { if (BrowserWindow.getAllWindows().length === 0) createWindow() })
app.on('window-all-closed', () => { if (process.platform !== 'darwin') app.quit() })
app.on('before-quit', () => { if (apiProcess && !apiProcess.killed) apiProcess.kill(); closeApiLog() })
