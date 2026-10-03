import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const here = path.dirname(fileURLToPath(import.meta.url))
const uiRoot = path.resolve(here, '..')

const card = fs.readFileSync(path.join(uiRoot, 'src', 'MessageContentCard.tsx'), 'utf8')
const panel = fs.readFileSync(path.join(uiRoot, 'src', 'ReportingRegistrationPanel.tsx'), 'utf8')
const app = fs.readFileSync(path.join(uiRoot, 'src', 'App.tsx'), 'utf8')
const api = fs.readFileSync(path.join(uiRoot, 'src', 'lib', 'api.ts'), 'utf8')
const fixture = fs.readFileSync(path.join(uiRoot, 'src', 'main.tsx'), 'utf8')

// 1. Message card: registered chip is text+icon (never color-only) and action button opens the panel
assert.match(card, /reportUsageByMessage\?: Record<string, ReportingWitnessStatus>/)
assert.match(card, /ثبت‌شده · /)
assert.match(card, /openReportEvent\(reportUsage\.events\[0\]\.event_id\)/)
assert.match(card, /openRegistration\(members\.map\(item => item\.id\)\)/)
assert.match(card, /ثبت در گزارش/)

// 2. Client: batched witness-status call
assert.match(api, /export async function fetchReportingWitnessStatus/)
assert.match(api, /\/api\/v3\/reporting\/witness-status\?/)

// 3. Registration panel: steps, draft autosave+restore, jalali reference engine, etag conflict surface
assert.match(panel, /Stepper/)
assert.match(panel, /localStorage\.setItem\(storageKey, JSON\.stringify\(draft\)\)/)
assert.match(panel, /بازیابی/)
assert.match(panel, /parseJalaliDate/)
assert.match(panel, /ثبت پیش‌نویس و پیوند شاهدان/)
assert.match(panel, /existing_event_id/)

// 4. App wiring: batched fetch effect, panel render, refresh after registration
assert.match(app, /fetchReportingWitnessStatus\(dialog\.peer_key, ids\)/)
assert.match(app, /ReportingRegistrationPanel = lazy\(/)
assert.match(app, /setReportUsageRefresh\(value => value \+ 1\)/)

// 5. Fixture: browser visual-test backend for the v3 reporting flows
assert.match(fixture, /phase9-visual-reporting-store/)
assert.match(fixture, /\/api\/v3\/reporting\/witness-status/)

console.log('# Reporting chat-surface integration contract assertions passed')
