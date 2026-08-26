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
const quickSend = source('src/QuickSendBar.tsx')
const contacts = source('src/ContactDirectoryModal.tsx')
const fixture = source('src/main.tsx')

check('selected account owns a fresh server capability snapshot', () => {
  assert.match(gate, /setCapabilitySnapshot\(null\)[\s\S]*messenger-accounts\/\$\{selected\.messenger_account_id\}\/capabilities/)
  assert.match(gate, /result\.messenger_account_id !== selected\.messenger_account_id/)
})

check('capability failures remain fail-closed', () => {
  assert.match(gate, /capabilitySnapshot[\s\S]*capabilitySnapshot\.messenger_account_id === selected\?\.messenger_account_id/)
  assert.match(gate, /&& capabilitySnapshot\.runtime_enabled/)
  assert.match(gate, /item\.status === 'supported'/)
  assert.match(gate, /catch\(reason =>[\s\S]*setCapabilityError/)
})

check('dialog, history and media reads are independently gated', () => {
  assert.match(app, /hasCapability\('dialogs\.read'\)/)
  assert.match(app, /hasCapability\('history\.read'\)/)
  assert.match(app, /hasCapability\('media\.read'\)/)
})

check('text and media sends are blocked before requests', () => {
  assert.match(quickSend, /hasCapability\('messages\.send'\)/)
  assert.match(quickSend, /hasCapability\('media\.send'\)/)
  assert.match(quickSend, /requestedOperationSupported[\s\S]*const canSend/)
  assert.match(quickSend, /disabled=\{!dialog \|\| sending \|\| !textSendSupported\}/)
  assert.match(quickSend, /disabled=\{!dialog \|\| sending \|\| !mediaSendSupported\}/)
  assert.match(quickSend, /if \(!dialog \|\| !canSend\) return/)
})

check('contact reads and writes are independently gated', () => {
  assert.match(contacts, /hasCapability\('contacts\.read'\)/)
  assert.match(contacts, /hasCapability\('contacts\.write'\)/)
  assert.match(contacts, /importAddToEitaa && !canWriteProviderContacts/)
})

check('visual fixture serves account-specific capability decisions', () => {
  assert.match(fixture, /messenger-accounts\\\/\[0-9a-f-\]\{36\}\\\/capabilities/)
  assert.match(fixture, /provider_capability_supported/)
})

process.stdout.write(`# ${passed}/${passed} Phase 11-B2 UI capability assertions passed\n`)
