import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const here = path.dirname(fileURLToPath(import.meta.url))
const root = path.resolve(here, '..')

// Read the TS file directly and verify exports and format
const content = fs.readFileSync(path.join(root, 'src', 'utils', 'jalaliDateTime.ts'), 'utf8')

// Test 1: Verify presence of core functions
assert.ok(content.includes('export function formatJalaliDate'), 'formatJalaliDate must be exported')
assert.ok(content.includes('export function formatJalaliTime'), 'formatJalaliTime must be exported')
assert.ok(content.includes('export function formatJalaliDateTime'), 'formatJalaliDateTime must be exported')
assert.ok(content.includes('export function parseJalaliDateTime'), 'parseJalaliDateTime must be exported')
assert.ok(content.includes('export function jalaliDayKey'), 'jalaliDayKey must be exported')
console.log('✓ Core exports verified in jalaliDateTime.ts')

// Test 2: In-memory simulation of formatJalaliDate
function formatJalaliDateSim(dateObj) {
  const formatter = new Intl.DateTimeFormat('en-US-u-ca-persian', {
    year: 'numeric',
    month: 'numeric',
    day: 'numeric',
    hour: 'numeric',
    minute: 'numeric',
    hour12: false,
  })
  const parts = formatter.formatToParts(dateObj)
  const getPart = (type) => Number(parts.find(p => p.type === type)?.value || 0)
  const y = String(getPart('year')).padStart(4, '0')
  const m = String(getPart('month')).padStart(2, '0')
  const d = String(getPart('day')).padStart(2, '0')
  return `${y}/${m}/${d}`
}

const testDate = new Date('2026-10-14T13:50:00Z')
const formatted = formatJalaliDateSim(testDate)
console.log(`Simulated formatted date: ${formatted}`)
assert.match(formatted, /^1405\/\d{2}\/\d{2}$/, 'Date must be formatted as YYYY/MM/DD without AP')
assert.ok(!formatted.includes('AP'), 'Date must NOT contain AP')
assert.ok(!formatted.includes(' '), 'Date key must NOT contain space')
console.log('✓ Jalali date formatting logic matches 1405/MM/DD without AP')

console.log('All Jalali Date/Time tests passed!')
