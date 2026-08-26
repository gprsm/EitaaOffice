import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'
import { accountScopeIsCurrent, accountStateKey, captureAccountScope } from '../src/lib/accountScope.mjs'
import { adaptivePollDelay } from '../src/lib/polling.mjs'

const here = dirname(fileURLToPath(import.meta.url))
const source = name => readFileSync(resolve(here, '..', name), 'utf8')
let passed = 0
const check = (name, callback) => {
  callback()
  passed += 1
  
}

check('account scope captures one immutable request account', () => {
  const captured = captureAccountScope('account-a')
  assert.equal(accountScopeIsCurrent(captured, 'account-a'), true)
  assert.equal(accountScopeIsCurrent(captured, 'account-b'), false)
})

check('client storage keys separate users and accounts', () => {
  assert.notEqual(accountStateKey('user-a', 'account-a'), accountStateKey('user-a', 'account-b'))
  assert.notEqual(accountStateKey('user-a', 'account-a'), accountStateKey('user-b', 'account-a'))
})

check('active polling is slower on a mobile viewport', () => {
  assert.equal(adaptivePollDelay(0, { online: true, visible: true, mobile: false, active: true }), 750)
  assert.equal(adaptivePollDelay(0, { online: true, visible: true, mobile: true, active: true }), 1250)
})

check('background and save-data polling reduce request frequency', () => {
  assert.ok(adaptivePollDelay(0, { online: true, visible: false, active: true }) >= 8000)
  assert.ok(adaptivePollDelay(0, { online: true, visible: true, mobile: true, saveData: true, active: true }) >= 2500)
})

check('offline reconnect uses bounded exponential backoff', () => {
  assert.equal(adaptivePollDelay(0, { online: false }), 4000)
  assert.equal(adaptivePollDelay(2, { online: false }), 16000)
  assert.equal(adaptivePollDelay(20, { online: false }), 30000)
})

check('API freezes account context and rejects a late stale result', () => {
  const api = source('src/lib/api.ts')
  assert.match(api, /captureAccountScope\(selectedMessengerAccountId\)/)
  assert.match(api, /accountScopeIsCurrent\(requestAccountId, selectedMessengerAccountId\)/)
  assert.match(api, /ApiAccountScopeChangedError/)
})

check('Workspace remounts and module caches include account scope', () => {
  assert.match(source('src/MessengerAccountGate.tsx'), /Fragment key=\{selected\.messenger_account_id\}/)
  assert.match(source('src/lib/avatarLoader.ts'), /getClientStoragePrefix\(\)/)
})

check('long-running workspace jobs use adaptive polling', () => {
  const app = source('src/App.tsx')
  assert.ok((app.match(/waitForAdaptivePoll/g) || []).length >= 6)
  assert.doesNotMatch(app, /setInterval\(/)
})

check('mobile and desktop shells remain explicit and share the same application tree', () => {
  const app = source('src/App.tsx')
  assert.match(app, /function MobileShell/)
  assert.match(app, /function DesktopShell/)
  assert.match(app, /const content = <AppUserGate>/)
})

check('phone shell uses Material safe areas, touch targets, and a single-column layout', () => {
  const app = source('src/App.tsx')
  const navigation = source('src/WorkspaceNavigation.tsx')
  const theme = source('src/theme.ts')
  assert.match(app, /env\(safe-area-inset-bottom\)/)
  assert.match(app, /display: \{ xs: 'block', md: 'grid' \}/)
  assert.match(navigation, /height: 'calc\(66px \+ env\(safe-area-inset-bottom\)\)'/)
  assert.match(navigation, /width: 48, height: 48/)
  assert.match(theme, /minHeight: 44/)
})

check('laptop shell keeps Material navigation, conversations, and content in one grid row', () => {
  const app = source('src/App.tsx')
  assert.match(app, /gridTemplateColumns: \{ md: composerDocked/)
  assert.match(app, /72px minmax\(280px, 32vw\) minmax\(0, 1fr\)/)
  assert.match(app, /<WorkspaceNavigation/)
  assert.match(app, /<ConversationListPage/)
  assert.match(app, /component="section" square elevation=\{0\}/)
})

check('microphase 2.3: favorite section is highlighted and positioned center on mobile', () => {
  const navigation = source('src/WorkspaceNavigation.tsx')
  assert.match(navigation, /mobileSections = useMemo/)
  assert.match(navigation, /'all', 'channel', 'favorite', 'group', 'personal'/)
  assert.match(navigation, /transform: 'translateY\(-8px\)'/)
})

process.stdout.write(`# ${passed}/${passed} Phase 9 workspace assertions passed\n`)

check('microphase 3.1: header search is an overlay that captures focus', () => {
  const search = source('src/HeaderMessageSearch.tsx')
  const header = source('src/ChatHeader.tsx')
  assert.match(search, /position: 'absolute'/)
  assert.match(search, /insetInlineEnd: 0/)
  assert.match(search, /minWidth: \{ xs: 'calc\(100vw - 32px\)'/)
  assert.match(search, /inputRef\.current\?\.focus\(\)/)
  assert.doesNotMatch(header, /<TextField.*label="جست‌وجوی پیام"/)
  assert.match(header, /<HeaderMessageSearch/)
})

check('microphase 3.2: selection usage history uses independent Dialog and does not open composer', () => {
  const app = source('src/App.tsx')
  const dialog = source('src/UsageInfoDialog.tsx')
  assert.doesNotMatch(app, /setSelectionMode\(true\); setComposerOpen\(true\)/)
  assert.match(app, /setActiveUsage\(\{ message: usedMessage/)
  assert.match(dialog, /<Dialog open=\{true\}/)
  assert.doesNotMatch(app, /props\.activeUsage && !editRecord && <Paper/)
})

check('microphase 3.3: wordpress icon replaces public icon globally', () => {
  const wp = source('src/WordPressIcon.tsx')
  const nav = source('src/WorkspaceNavigation.tsx')
  const header = source('src/ChatHeader.tsx')
  assert.match(wp, /<path d="M12 2C6\.48 2 2 6\.48 2 12s4\.48 10 10 10 10-4\.48 10-10S17\.52 2 12 2zm/)
  assert.match(nav, /<WordPressIcon \/>/)
  assert.doesNotMatch(nav, /<PublicRounded \/>وردپرس/)
  assert.match(header, /<WordPressIcon \/><\/IconButton>/)
  assert.doesNotMatch(header, /<PublicRounded \/><\/IconButton>/)
})

process.stdout.write(`# ${passed}/${passed} Phase 9 workspace assertions passed\n`)
