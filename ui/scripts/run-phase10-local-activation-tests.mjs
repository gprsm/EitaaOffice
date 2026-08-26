import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const source = name => readFileSync(resolve(here, '..', name), 'utf8')
const helpers = source('src/utils/helpers.tsx')
let passed = 0
const check = (name, callback) => {
  callback()
  passed += 1
  process.stdout.write(`ok ${passed} - ${name}\n`)
}

check('software logout is a reusable authenticated control', () => {
  const gate = source('src/AppUserGate.tsx')
  assert.match(gate, /export function AppUserLogoutButton/)
  assert.match(gate, /await appUser\.logout\(\)/)
  assert.match(gate, /خروج از نرم‌افزار/)
  assert.match(gate, /در حال خروج/)
})

check('account selection gate always provides software logout', () => {
  const gate = source('src/MessengerAccountGate.tsx')
  assert.match(gate, /AppUserLogoutButton/)
  assert.match(gate, /<AppUserLogoutButton disabled=\{Boolean\(busyAccountId\)\} \/>/)
})

check('provider login and recovery surfaces provide software logout', () => {
  const app = source('src/App.tsx')
  assert.match(app, /<AppUserLogoutButton disabled=\{busy\} \/>/)
  assert.match(app, /<AppUserLogoutButton disabled=\{!failed\} \/>/)
})

check('normal provider login recovers a migrated session without exposing archive internals', () => {
  const app = source('src/App.tsx')
  assert.match(app, /e instanceof ApiError && e\.code === 'api_auth_session_reset_required'/)
  assert.match(app, /'POST', '\/api\/v1\/auth\/reset-local-session', \{ confirm: true \}/)
  assert.match(app, /const result = await api<any>\('POST', '\/api\/v1\/auth\/request-code', \{ phone \}\)/)
  assert.doesNotMatch(app, /archivePreviousSession|بایگانی نشست قبلی و آماده‌سازی ورود تازه|پسوند \.bak/)
})

check('normal provider login offers confirmed DPAPI identity recovery', () => {
  const app = source('src/App.tsx')
  assert.match(app, /e instanceof ApiError && e\.code === 'phone_unprotection_failed'/)
  assert.match(app, /recoverPhoneIdentity/)
  assert.match(app, /'POST', '\/api\/v1\/auth\/recover-phone-identity', \{ phone, confirm: true \}/)
  assert.match(app, /کلید و پایگاه دادهٔ قبلی پیش از تغییر پشتیبان‌گیری می‌شوند/)
  assert.match(app, /بازیابی امن محافظت شماره/)
})

check('provider challenge id is preserved across code, password, and page reload', () => {
  const app = source('src/App.tsx')
  assert.match(app, /initialChallenge=\{status\.challenge\}/)
  assert.match(app, /useState\(\(\) => String\(initialChallenge\?\.challenge_id \|\| ''\)\.trim\(\)\)/)
  assert.match(app, /'\/api\/v1\/auth\/submit-code', \{ challenge_id: challengeId, code: normalizeLoginCodeInput\(code\) \}/)
  assert.ok(
    /import \{[^\n]*normalizeLoginCodeInput[^\n]*\} from '\.\/utils\/helpers'/.test(app),
    'App must import the canonical login-code normalizer',
  )
  assert.ok(
    helpers.includes('export function normalizeLoginCodeInput'),
    'the canonical helper module must export normalizeLoginCodeInput',
  )
  assert.match(app, /'\/api\/v1\/auth\/submit-password', \{ challenge_id: challengeId, password \}/)
  assert.match(app, /setChallengeId\(String\(result\.challenge\?\.challenge_id \|\| challengeId\)\.trim\(\)\)/)
})

check('logout failures remain visible and retryable', () => {
  const gate = source('src/AppUserGate.tsx')
  assert.match(gate, /setError\(/)
  assert.match(gate, /<Alert severity="error">\{error\}<\/Alert>/)
  assert.match(gate, /setBusy\(false\)/)
})

process.stdout.write(`# ${passed}/${passed} Phase 10 local activation assertions passed\n`)
