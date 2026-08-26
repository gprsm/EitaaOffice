import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { adaptivePollDelay } from '../src/lib/polling.mjs'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const source = relative => fs.readFileSync(path.join(root, relative), 'utf8')

const gate = source('src/AppUserGate.tsx')
assert.match(gate, /\/api\/v2\/app-auth\/register/)
assert.match(gate, /کاربر جدید هستم/)
assert.match(gate, /password\.length < 4/)
assert.doesNotMatch(gate, /password\.length < 12|حداقل ۱۲ نویسه/)
assert.doesNotMatch(gate, /if \(!status\.principal\.permissions\.use_legacy_workspace\)/)

const app = source('src/App.tsx')
const login = source('src/LoginExperience.tsx')
const messageCard = source('src/MessageContentCard.tsx')
assert.match(app, /setLiveMessageState\('connecting'\)/)
assert.match(app, /background: true/)
assert.match(app, /propagateError: true/)
assert.match(app, /\/api\/v1\/dialogs\/live-sync/)
assert.match(app, /waitForAdaptivePoll\(failedAttempts, \{ active: false \}\)/)
assert.doesNotMatch(app, /title="بررسی پیام‌های جدید"/)
assert.match(app, /automatic_recovery: true/)
assert.match(app, /'POST', '\/api\/v1\/auth\/request-code', \{\}/)
assert.doesNotMatch(app, /نشست ایتا نیاز به بررسی دارد|بایگانی نشست و ورود تازه/)
assert.doesNotMatch(login, /مرکز یکپارچهٔ محتوای ایتا|آماده برای معماری چندحسابی ایزوله/)
assert.match(login, /justifySelf: 'center'/)
assert.doesNotMatch(login, /gridTemplateColumns/)
assert.match(messageCard, /CardHeader/)
assert.match(messageCard, /sender_display_name/)
assert.match(messageCard, /sender_is_eitaa_contact/)
assert.doesNotMatch(source('src/ChatHeader.tsx'), /همگام‌سازی زنده/)

const settings = source('src/SettingsPage.tsx')
assert.match(settings, /from '@mui\/material'/)
assert.match(settings, /gridTemplateColumns: \{ xs: '1fr'/)
assert.doesNotMatch(settings, /className=/)

for (const materialOnlySurface of ['src/LoginExperience.tsx', 'src/AuthBrand.tsx']) {
  assert.doesNotMatch(source(materialOnlySurface), /className=/)
}
for (const materialPage of ['src/WorkspaceNavigation.tsx', 'src/ConversationListPage.tsx', 'src/ChatHeader.tsx']) {
  assert.match(source(materialPage), /from '@mui\/material'/)
  assert.doesNotMatch(source(materialPage), /className=/)
}

assert.ok(adaptivePollDelay(0, { visible: true, online: true, mobile: true, active: true }) <= 1_250)
assert.ok(adaptivePollDelay(1, { visible: false, online: true, mobile: true, active: true }) >= 8_000)
assert.ok(adaptivePollDelay(1, { visible: true, online: false, mobile: true, active: true }) >= 8_000)

console.log('mobile auth and live-message contracts passed')
