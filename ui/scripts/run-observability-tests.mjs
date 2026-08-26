import assert from 'node:assert/strict'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { createRequire } from 'node:module'
import { fileURLToPath } from 'node:url'

const here = path.dirname(fileURLToPath(import.meta.url))
const uiRoot = path.resolve(here, '..')
const require = createRequire(import.meta.url)
const {
  StructuredDesktopLogger,
  sanitizeRoutePath,
  validateClientDiagnostic,
} = require(path.join(uiRoot, 'electron', 'observability.cjs'))

const main = fs.readFileSync(path.join(uiRoot, 'src', 'main.tsx'), 'utf8')
const boundary = fs.readFileSync(path.join(uiRoot, 'src', 'ClientErrorBoundary.tsx'), 'utf8')
const preload = fs.readFileSync(path.join(uiRoot, 'electron', 'preload.cjs'), 'utf8')
const electron = fs.readFileSync(path.join(uiRoot, 'electron', 'main.cjs'), 'utf8')

assert.match(main, /installGlobalErrorReporting\(\)/)
assert.match(main, /<ClientErrorBoundary><Root \/><\/ClientErrorBoundary>/)
assert.match(boundary, /renderer_unhandled_error/)
assert.match(boundary, /renderer_unhandled_rejection/)
assert.match(boundary, /renderer_render_error/)
assert.doesNotMatch(boundary, /error\.message|componentStack\s*:/)
assert.match(preload, /diagnostics:report/)
assert.match(electron, /sanitizeRoutePath\(targetPath\)/)
assert.doesNotMatch(electron, /desktopLog\(`API request failed path=\$\{targetPath\}/)

assert.equal(sanitizeRoutePath('/api/v1/messages/list?token=private'), '/api/v1/messages/list')
assert.equal(sanitizeRoutePath('/api/v1/messages/12345?phone=private'), '/api/v1/messages/{redacted}')
assert.equal(validateClientDiagnostic({ event: 'renderer_unhandled_error', level: 'error', error_type: 'TypeError', safe_context: { surface: 'renderer' } })?.errorType, 'TypeError')
assert.equal(validateClientDiagnostic({ event: 'renderer_unhandled_error', level: 'error', error_type: 'TypeError', message: 'private', safe_context: {} }), null)

const temporary = fs.mkdtempSync(path.join(os.tmpdir(), 'eitaa-observability-'))
const logPath = path.join(temporary, 'desktop.log')
const logger = new StructuredDesktopLogger(logPath)
logger.emit('desktop_api_request_failed', {
  level: 'error',
  reasonCode: 'desktop_api_request_failed',
  correlationId: 'a'.repeat(32),
  fields: { path: '/api/v1/messages/{redacted}', token: 'do-not-store', error_type: 'TypeError' },
})
const record = JSON.parse(fs.readFileSync(logPath, 'utf8').trim())
assert.equal(record.schema_version, 1)
assert.equal(record.source, 'desktop')
assert.equal(record.correlation_id, 'a'.repeat(32))
assert.equal(record.fields.path, '/api/v1/messages/{redacted}')
assert.notEqual(record.fields.token, 'do-not-store')
fs.rmSync(temporary, { recursive: true, force: true })

console.log('# observability UI/Electron contract assertions passed')
