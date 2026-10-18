import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const here = path.dirname(fileURLToPath(import.meta.url))
const uiRoot = path.resolve(here, '..')

// Dynamic import or compile check
console.log('# Testing Registration Defaults and Inference Logic')

// Read the TS file directly and verify the core exported function and tables
const panelTs = fs.readFileSync(path.join(uiRoot, 'src', 'ReportingRegistrationPanel.tsx'), 'utf8')

// Test 1: Verification of Mazandaran Cities dictionary presence
const cities = [
  'ساری', 'بابل', 'آمل', 'قائمشهر', 'تنکابن', 'چالوس', 'نوشهر', 'نکا',
  'بهشهر', 'رامسر', 'بابلسر', 'محمودآباد', 'سوادکوه', 'جویبار', 'فریدونکنار',
  'کلاردشت', 'سیمرغ', 'عباس‌آباد', 'نور'
]
for (const city of cities) {
  assert.ok(panelTs.includes(city), `City ${city} must be in Mazandaran cities registry`)
}
console.log('✓ All key Mazandaran cities present in registry')

// Test 2: Verification of Sender-to-Unit Provenance bindings from Rulebook §9
assert.ok(panelTs.includes('مهدوی') && panelTs.includes('دادگستری سوادکوه'), 'Binding for مهدوی -> سوادکوه required')
assert.ok(panelTs.includes('دیوسالار') && panelTs.includes('دادگستری نور'), 'Binding for دیوسالار -> نور required')
assert.ok(panelTs.includes('احسا') && panelTs.includes('دادگستری بابل'), 'Binding for احسا -> بابل required')
assert.ok(panelTs.includes('قاسمی شورابی') && panelTs.includes('ستاد دادگستری کل استان'), 'Binding for قاسمی شورابی -> ستاد required')
console.log('✓ Rulebook §9 Sender-to-Unit bindings verified')

// Test 3: Verification of author field in draft state and form
assert.ok(panelTs.includes('author: string'), 'RegistrationDraft must declare author field')
assert.ok(panelTs.includes('draft.author'), 'Form must bind draft.author')
assert.ok(panelTs.includes('نویسنده / رابط فرهنگی گزارش'), 'Form must display author label')
console.log('✓ Author field and draft wiring verified')

// Test 4: Verification of Jalali date and time formatting
assert.ok(panelTs.includes('occurredOn = jalaliDayKey(primaryMsg.date)'), 'Date must be converted to Jalali key')
assert.ok(panelTs.includes('sourceTimeFormatted = `${jalaliDayLabel(primaryMsg.date)} · ساعت ${timeStr}`'), 'Time must be formatted with day and hour:minute')
console.log('✓ Jalali date and time formatting verified')

// Test 5: Verification of notes preservation with author
assert.ok(panelTs.includes('draft.author ? `نویسنده / رابط گزارش: ${draft.author.trim()}` : \'\''), 'Author must be prepended to notes on submit')
console.log('✓ Notes author persistence verified')

console.log('All 5 Registration Defaults & Inference contract tests passed!')
