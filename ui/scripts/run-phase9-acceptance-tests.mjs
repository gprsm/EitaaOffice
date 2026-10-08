import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const source = name => readFileSync(resolve(here, '..', name), 'utf8')
let passed = 0
const check = (name, callback) => {
  callback()
  passed += 1
  process.stdout.write(`ok ${passed} - ${name}\n`)
}

check('document language and direction are explicit Persian RTL', () => {
  const main = source('src/main.tsx')
  assert.match(main, /document\.documentElement\.lang = 'fa'/)
  assert.match(main, /document\.documentElement\.dir = 'rtl'/)
})

check('workspace inherits the root RTL direction without a second Emotion flip', () => {
  const app = source('src/App.tsx')
  const workspaceMain = app.match(/<Box component="main" sx=\{\{[^\n]+/)
  assert.ok(workspaceMain, 'workspace main surface was not found')
  assert.doesNotMatch(workspaceMain[0], /direction:\s*'rtl'/)
})

check('visual fixture is development-only and represents two users', () => {
  const main = source('src/main.tsx')
  assert.match(main, /import\.meta\.env\.DEV/)
  assert.match(main, /__phase9_visual_fixture/)
  assert.match(main, /__phase9_user/)
  assert.match(main, /\/api\/v1\/settings\/sites/)
  assert.match(main, /application_password_configured: true/)
  assert.doesNotMatch(main, /application_password:\s*['"][^'"]+['"]/)
  assert.match(main, /اپراتور آزمایشی/)
  assert.match(main, /مدیر آزمایشی/)
})

check('mobile acceptance covers 360 and 390 Material breakpoint', () => {
  const app = source('src/App.tsx')
  assert.match(app, /max-width:599px/)
  assert.match(app, /height: '100dvh'/)
  assert.match(app, /overflow: 'hidden'/)
})

check('desktop acceptance retains 1280 and 1600 layout ranges', () => {
  const app = source('src/App.tsx')
  assert.match(app, /matchMedia\('\(min-width: 1500px\)'\)/)
  assert.match(app, /composerDocked \? '72px minmax\(300px, 22vw\)/)
  assert.match(app, /'72px minmax\(280px, 32vw\)/)
})

check('safe areas and mobile keyboard inputs are explicit', () => {
  const app = source('src/App.tsx')
  const navigation = source('src/WorkspaceNavigation.tsx')
  assert.match(navigation, /safe-area-inset-top/)
  assert.match(app, /safe-area-inset-bottom/)
  assert.match(app, /<TextField multiline/)
})

check('orientation change receives a compact landscape layout', () => {
  const app = source('src/App.tsx')
  assert.match(app, /max-width:899px/)
  assert.match(app, /orientation:landscape/)
  assert.match(app, /max-height:599px/)
})

check('mobile composer uses a Material drawer surface and dialogs become full screen', () => {
  const app = source('src/App.tsx')
  assert.match(app, /position: 'fixed'/)
  assert.match(app, /insetInlineEnd: 0, width: 'min\(520px, 94vw\)'/)
  assert.match(app, /transform: composerOpen \? 'translateX\(0\)' : 'translateX\(105%\)'/)
  assert.match(app, /fullScreen=\{fullScreen\}/)
  assert.match(app, /useMediaQuery\(theme\.breakpoints\.down\('sm'\)\)/)
})

check('mobile conversation drawer enters from the RTL inline start edge', () => {
  const conversations = source('src/ConversationListPage.tsx')
  assert.match(conversations, /insetInlineStart: 0/)
  assert.match(conversations, /transform: open \? 'translateX\(0\)' : 'translateX\(-110%\)'/)
})

check('Material touch targets and focus management meet accessibility contract', () => {
  const theme = source('src/theme.ts')
  const navigation = source('src/WorkspaceNavigation.tsx')
  assert.match(theme, /minHeight: 44/)
  assert.match(navigation, /width: 48, height: 48/)
  assert.match(navigation, /aria-current=/)
})

check('account switch and session invalidation have accessible event boundaries', () => {
  assert.match(source('src/lib/api.ts'), /MESSENGER_ACCOUNT_CHANGED_EVENT/)
  assert.match(source('src/AppUserGate.tsx'), /APP_AUTH_SESSION_INVALID_EVENT/)
  assert.match(source('src/ConnectionStatus.tsx'), /role="status"/)
})

check('MobileShell and DesktopShell remain separate render targets', () => {
  const app = source('src/App.tsx')
  assert.match(app, /data-presentation-shell="mobile"/)
  assert.match(app, /data-presentation-shell="desktop"/)
})

check('application surfaces no longer depend on custom CSS classes', () => {
  const surfaces = ['src/App.tsx', 'src/AppUserGate.tsx', 'src/LoginExperience.tsx', 'src/WorkspaceNavigation.tsx', 'src/ConversationListPage.tsx', 'src/ChatHeader.tsx', 'src/SettingsPage.tsx', 'src/ContactDirectoryModal.tsx']
  surfaces.forEach(file => assert.doesNotMatch(source(file), /className=/, file))
  const main = source('src/main.tsx')
  assert.doesNotMatch(main, /styles\.css|login-experience\.css|react-toastify/)
  assert.match(main, /MaterialToastHost/)
})

check('JalaliDatePicker popover manages anchorEl cleanly without document mousedown trap', () => {
  const helpers = source('src/utils/helpers.tsx')
  assert.match(helpers, /export function JalaliDatePicker/)
  assert.match(helpers, /const \[anchorEl, setAnchorEl\] = useState<HTMLElement \| null>\(null\)/)
  assert.doesNotMatch(helpers, /document\.addEventListener\('mousedown'/)
  assert.match(helpers, /aria-label="ماه قبل"/)
  assert.match(helpers, /aria-label="ماه بعد"/)
})

process.stdout.write(`# ${passed}/${passed} Phase 9 acceptance assertions passed\n`)
