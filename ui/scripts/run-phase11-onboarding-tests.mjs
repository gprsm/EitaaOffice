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

const gate = source('src/MessengerAccountGate.tsx')
const app = source('src/App.tsx')
const appUserGate = source('src/AppUserGate.tsx')
const api = source('../src/eitaa_bridge/application/api.py')
const providers = source('../src/eitaa_bridge/providers/registry.py')
const baleSlot = source('../src/eitaa_bridge/providers/bale/slot.py')
const store = source('../src/eitaa_bridge/infrastructure/coordinator/store.py')
const baleRuntime = source('../src/eitaa_bridge/application/bale_runtime.py')
const baleWorkspace = source('src/BaleWorkspace.tsx')

check('fresh install creates the initial administrator before messenger onboarding', () => {
  assert.match(app, /<AppUserGate>[\s\S]*<MessengerAccountGate>[\s\S]*<EitaaApp \/>/)
  assert.match(appUserGate, /if \(status\.setup_required\) \{[\s\S]*<AppUserSetup/)
  assert.match(appUserGate, /ساخت مدیر اولیه نرم‌افزار/)
  assert.match(appUserGate, /api\('POST', '\/api\/v2\/app-auth\/setup'/)
})

check('UI provider contract is descriptor-driven rather than a fixed union', () => {
  assert.match(gate, /provider: string/)
  assert.match(gate, /runtime_enabled: boolean/)
  assert.match(gate, /onboarding_enabled: boolean/)
  assert.doesNotMatch(gate, /provider: 'eitaa' \| 'bale'/)
})

check('add-account dialog posts only provider, private phone and optional label', () => {
  assert.match(gate, /type OnboardingInput = \{ provider: string; phone: string; label: string \}/)
  assert.match(gate, /api<OnboardingResponse>\('POST', '\/api\/v2\/messenger-accounts', input\)/)
  assert.match(api, /allowed_keys = \{"provider", "phone", "label"\}/)
})

check('private identity is cleared after submit and is not browser-persisted', () => {
  assert.match(gate, /finally \{[\s\S]*setPhone\(''\)/)
  assert.match(gate, /autoComplete="off"/)
  assert.doesNotMatch(gate, /localStorage[\s\S]{0,120}phone/)
})

check('server owns identifiers and filesystem choices', () => {
  assert.match(store, /messenger_account_id = _new_uuid\(\)/)
  assert.match(store, /phone_account_id = _new_uuid\(\)/)
  assert.match(api, /messenger_account_onboarding_fields_rejected/)
  assert.doesNotMatch(gate, /type OnboardingInput = \{[^\n]*(session_path|storage_path|phone_account_id)/)
})

check('Eitaa and authorized contract-verified Bale have explicit onboarding', () => {
  assert.match(providers, /provider="eitaa"[\s\S]*onboarding_enabled=True/)
  assert.match(baleSlot, /provider="bale"[\s\S]*onboarding_enabled=True/)
  assert.match(baleSlot, /implementation_state=ProviderImplementationState\.CONTRACT_VERIFIED/)
  assert.match(baleSlot, /authorization_reference="document:F-086"/)
  assert.match(baleSlot, /worker_factory=worker_factory/)
  assert.match(baleSlot, /worker_config_required=True/)
})

check('account switching and runnable state use provider capabilities', () => {
  assert.match(gate, /isRunnable\(item, next\.provider_adapters\)/)
  assert.match(gate, /adapters\[account\.provider\]\?\.runtime_enabled/)
})

check('bale LIVE_UPDATES is grounded in the observed polling transport', () => {
  assert.match(baleRuntime, /record_messenger_capability_observation/)
  assert.match(baleRuntime, /bale_updates_polling_transport/)
  assert.match(store, /def record_messenger_capability_observation/)
  assert.match(baleWorkspace, /accounts\.hasCapability\('updates\.live'\)/)
})

check('login keeps account identity explicit and offers a different account path', () => {
  assert.match(gate, /export function AddMessengerAccountButton\(\)/)
  assert.match(app, /messengerAccounts\.featureEnabled && <>[\s\S]*<MessengerAccountMenuControl \/>[\s\S]*<AddMessengerAccountButton \/>/)
  assert.match(app, /e\.code === 'eitaa_account_phone_mismatch'/)
  assert.match(app, /messengerAccounts\.selected\.phone_hint/)
  assert.match(app, /اصلاح شمارهٔ همین حساب/)
})

check('dialog has bounded responsive width and an explicit privacy notice', () => {
  assert.match(gate, /<Dialog open=\{open\}[\s\S]*fullWidth maxWidth="sm"/)
  assert.match(gate, /شماره فقط برای ساخت هویت رمزگذاری‌شده/)
})

process.stdout.write(`# ${passed}/${passed} Phase 11 onboarding assertions passed\n`)
