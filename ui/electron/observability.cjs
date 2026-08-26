const fs = require('node:fs')
const path = require('node:path')

const EVENT_SCHEMA_VERSION = 1
const EVENT_NAME = /^[a-z][a-z0-9_.-]{0,95}$/
const REASON_CODE = /^[a-z][a-z0-9_.-]{0,95}$/
const CORRELATION_ID = /^[0-9a-f]{12,64}$/
const ERROR_TYPE = /^[A-Za-z][A-Za-z0-9_.-]{0,80}$/
const LEVELS = new Set(['debug', 'info', 'warning', 'error', 'critical'])
const RESULTS = new Set(['observed', 'started', 'succeeded', 'failed', 'rejected', 'degraded', 'cancelled', 'uncertain'])
const CLIENT_EVENTS = new Set([
  'renderer_render_error',
  'renderer_unhandled_error',
  'renderer_unhandled_rejection',
])
const EVENTS = Object.freeze({
  API_START_FAILED: 'desktop_api_start_failed',
  API_PROCESS_STARTED: 'desktop_api_process_started',
  API_PROCESS_ERROR: 'desktop_api_process_error',
  API_PROCESS_EXITED: 'desktop_api_process_exited',
  API_OWNERSHIP_CONFLICT: 'desktop_api_ownership_conflict',
  API_HEALTH_TIMEOUT: 'desktop_api_health_timeout',
  API_RECOVERY_REQUESTED: 'desktop_api_recovery_requested',
  API_REQUEST_FAILED: 'desktop_api_request_failed',
  API_RETRY_FAILED: 'desktop_api_retry_failed',
  RENDERER_ERROR_REPORTED: 'desktop_renderer_error_reported',
  RENDERER_PROCESS_GONE: 'desktop_renderer_process_gone',
  RENDERER_UNRESPONSIVE: 'desktop_renderer_unresponsive',
  RENDERER_LOAD_FAILED: 'desktop_renderer_load_failed',
  PROCESS_WARNING: 'desktop_process_warning',
  UNCAUGHT_EXCEPTION: 'desktop_uncaught_exception',
})

function normalizeCorrelationId(value) {
  const selected = String(value || '').trim().toLowerCase().replaceAll('-', '')
  return CORRELATION_ID.test(selected) ? selected : null
}

function sanitizeRoutePath(value) {
  let selected
  try { selected = new URL(String(value || '/'), 'http://loopback.invalid').pathname }
  catch { return '/' }
  const segments = selected.split('/').filter(Boolean).map(segment => (
    /^[a-z][a-z0-9-]{0,31}$/i.test(segment) ? segment.toLowerCase() : '{redacted}'
  ))
  return `/${segments.join('/')}`
}

function safeValue(value, key = '', depth = 0) {
  if (depth > 8) return { truncated: true }
  const normalized = String(key).toLowerCase()
  if (/(password|secret|token|cookie|authorization|csrf|otp|session|access.hash|phone|payload|body|message|stack|url|query)/.test(normalized)) {
    return { redacted: true, present: value !== null && value !== undefined }
  }
  if (value === null || value === undefined || typeof value === 'boolean' || typeof value === 'number') return value ?? null
  if (typeof value === 'string') return value.slice(0, 160)
  if (Array.isArray(value)) return value.slice(0, 30).map(item => safeValue(item, '', depth + 1))
  if (typeof value === 'object') {
    const result = {}
    for (const [childKey, childValue] of Object.entries(value).slice(0, 40)) {
      result[String(childKey).slice(0, 64)] = safeValue(childValue, childKey, depth + 1)
    }
    return result
  }
  return { type: typeof value }
}

function rotate(filePath, maxBytes, backupCount) {
  if (!fs.existsSync(filePath) || fs.statSync(filePath).size < maxBytes) return
  for (let index = backupCount - 1; index >= 1; index -= 1) {
    const source = `${filePath}.${index}`
    const target = `${filePath}.${index + 1}`
    if (fs.existsSync(source)) fs.renameSync(source, target)
  }
  fs.renameSync(filePath, `${filePath}.1`)
}

class StructuredDesktopLogger {
  constructor(filePath, { maxBytes = 5 * 1024 * 1024, backupCount = 5 } = {}) {
    this.filePath = filePath
    this.maxBytes = maxBytes
    this.backupCount = backupCount
    fs.mkdirSync(path.dirname(filePath), { recursive: true })
  }

  emit(event, { level = 'info', result = null, reasonCode = null, correlationId = null, fields = {} } = {}) {
    const selectedEvent = String(event || '').trim().toLowerCase()
    if (!EVENT_NAME.test(selectedEvent)) return false
    const selectedLevel = LEVELS.has(level) ? level : 'info'
    const selectedResult = RESULTS.has(result)
      ? result
      : selectedLevel === 'error' || selectedLevel === 'critical'
        ? 'failed'
        : selectedLevel === 'warning' ? 'degraded' : 'observed'
    const selectedReason = REASON_CODE.test(String(reasonCode || '').toLowerCase())
      ? String(reasonCode).toLowerCase()
      : selectedLevel === 'warning' || selectedLevel === 'error' || selectedLevel === 'critical'
        ? selectedEvent
        : null
    const record = {
      schema_version: EVENT_SCHEMA_VERSION,
      at: new Date().toISOString(),
      source: 'desktop',
      event: selectedEvent,
      level: selectedLevel,
      result: selectedResult,
      reason_code: selectedReason,
      correlation_id: normalizeCorrelationId(correlationId),
      fields: safeValue(fields),
    }
    try {
      rotate(this.filePath, this.maxBytes, this.backupCount)
      fs.appendFileSync(this.filePath, `${JSON.stringify(record)}\n`, 'utf8')
      return true
    } catch { return false }
  }
}

function validateClientDiagnostic(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null
  const allowedKeys = new Set(['event', 'level', 'error_type', 'safe_context'])
  if (Object.keys(value).some(key => !allowedKeys.has(key))) return null
  const event = String(value.event || '').trim().toLowerCase()
  const level = String(value.level || 'error').trim().toLowerCase()
  const errorType = String(value.error_type || 'Error').trim()
  if (!CLIENT_EVENTS.has(event) || !['warning', 'error'].includes(level) || !ERROR_TYPE.test(errorType)) return null
  const context = value.safe_context || {}
  if (!context || typeof context !== 'object' || Array.isArray(context)) return null
  const allowedContext = new Set(['component_stack_present', 'document_visible', 'online', 'surface'])
  if (Object.keys(context).some(key => !allowedContext.has(key))) return null
  const surface = String(context.surface || 'renderer').trim().toLowerCase()
  if (!['renderer', 'browser'].includes(surface)) return null
  return {
    event,
    level,
    errorType,
    safeContext: {
      surface,
      component_stack_present: Boolean(context.component_stack_present),
      document_visible: Boolean(context.document_visible),
      online: Boolean(context.online),
    },
  }
}

module.exports = {
  EVENT_SCHEMA_VERSION,
  EVENTS,
  StructuredDesktopLogger,
  normalizeCorrelationId,
  sanitizeRoutePath,
  validateClientDiagnostic,
}
