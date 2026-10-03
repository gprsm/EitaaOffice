import { accountScopeIsCurrent, captureAccountScope } from './accountScope.mjs'
import { shouldRefreshAppAuthAfterError } from './authStartupRecovery.mjs'

export const AUTH_SESSION_INVALID_EVENT = 'eitaa-bridge:auth-session-invalid'
export const APP_AUTH_SESSION_INVALID_EVENT = 'eitaa-bridge:app-auth-session-invalid'
export const CLIENT_CONNECTIVITY_CHANGED_EVENT = 'eitaa-bridge:client-connectivity-changed'
export const CLIENT_STORAGE_SCOPE_CHANGED_EVENT = 'eitaa-bridge:client-storage-scope-changed'

let appCsrfToken = ''
let selectedMessengerAccountId = ''
let storageAppUserId = ''
let connectivity: 'online' | 'offline' | 'reconnecting' = (
  typeof navigator !== 'undefined' && navigator.onLine === false ? 'offline' : 'online'
)

export function createClientCorrelationId() {
  const bytes = new Uint8Array(16)
  globalThis.crypto.getRandomValues(bytes)
  return Array.from(bytes, value => value.toString(16).padStart(2, '0')).join('')
}

export const MESSENGER_ACCOUNT_CHANGED_EVENT = 'eitaa-bridge:messenger-account-changed'

export class ApiAccountScopeChangedError extends Error {
  constructor() {
    super('حساب پیام‌رسان هنگام اجرای درخواست تغییر کرد؛ نتیجهٔ قبلی کنار گذاشته شد.')
    this.name = 'ApiAccountScopeChangedError'
  }
}

const safeScopePart = (value?: string | null) => {
  const selected = String(value || '').trim().toLowerCase()
  return /^[a-z0-9-]{1,64}$/.test(selected) ? selected : ''
}

export function getClientStoragePrefix() {
  if (!storageAppUserId) return ''
  return `user-${storageAppUserId}.account-${selectedMessengerAccountId || 'default'}`
}

export function scopedStorageKey(key: string) {
  const prefix = getClientStoragePrefix()
  return prefix ? `${key}.${prefix}` : key
}

function publishStorageScope() {
  document.documentElement.dataset.clientStorageScope = getClientStoragePrefix()
  window.dispatchEvent(new CustomEvent(CLIENT_STORAGE_SCOPE_CHANGED_EVENT, {
    detail: { storagePrefix: getClientStoragePrefix() },
  }))
}

export function setAppUserStorageScope(value?: string | null) {
  const next = safeScopePart(value)
  if (next === storageAppUserId) return
  storageAppUserId = next
  selectedMessengerAccountId = ''
  publishStorageScope()
}

export function setSelectedMessengerAccountId(value?: string | null) {
  const next = safeScopePart(value)
  if (next === selectedMessengerAccountId) return
  selectedMessengerAccountId = next
  window.dispatchEvent(new CustomEvent(MESSENGER_ACCOUNT_CHANGED_EVENT, {
    detail: { messengerAccountId: selectedMessengerAccountId || null },
  }))
  publishStorageScope()
}

export function getSelectedMessengerAccountId() {
  return selectedMessengerAccountId || null
}

export function appAuthRequestHeaders(): Record<string, string> {
  return {
    ...(appCsrfToken ? { 'X-CSRF-Token': appCsrfToken } : {}),
    ...(selectedMessengerAccountId
      ? { 'X-Eitaa-Messenger-Account': selectedMessengerAccountId }
      : {}),
  }
}

export function getClientConnectivity() {
  return connectivity
}

export function reportClientConnectivity(next: 'online' | 'offline' | 'reconnecting') {
  if (connectivity === next) return
  connectivity = next
  window.dispatchEvent(new CustomEvent(CLIENT_CONNECTIVITY_CHANGED_EVENT, {
    detail: { status: connectivity },
  }))
}

export async function probeReadiness() {
  const correlationId = createClientCorrelationId()
  try {
    const result = await window.eitaaDesktop.api(
      'GET',
      '/api/v1/readiness',
      undefined,
      undefined,
      selectedMessengerAccountId || undefined,
      correlationId,
    )
    if (result.status === 200 && result.payload?.ok === true) {
      reportClientConnectivity('online')
      return true
    }
    if (result.status >= 500) reportClientConnectivity('reconnecting')
    else reportClientConnectivity('online')
    return result.status < 500
  } catch {
    reportClientConnectivity('offline')
    return false
  }
}

export class ApiError extends Error {
  readonly code: string
  readonly status: number
  readonly context: Record<string, unknown>

  constructor(status: number, payload: any) {
    const error = payload?.error ?? {}
    super(error.message || 'درخواست ناموفق بود.')
    this.name = 'ApiError'
    this.status = status
    this.code = error.error_code || 'unknown_error'
    this.context = error.safe_context || {}
  }
}

export async function api<T>(method: string, path: string, body?: unknown): Promise<T> {
  let result
  const requestAccountId = captureAccountScope(selectedMessengerAccountId)
  const correlationId = createClientCorrelationId()
  try {
    result = await window.eitaaDesktop.api(
      method,
      path,
      body,
      appCsrfToken || undefined,
      requestAccountId || undefined,
      correlationId,
    )
    reportClientConnectivity('online')
  } catch {
    reportClientConnectivity('offline')
    throw new Error('ارتباط با سرویس قطع شده است. پس از اتصال دوباره تلاش کنید.')
  }
  if (!accountScopeIsCurrent(requestAccountId, selectedMessengerAccountId)) {
    throw new ApiAccountScopeChangedError()
  }
  if (result.status < 200 || result.status >= 300 || result.payload?.ok === false) {
    const error = new ApiError(result.status, result.payload)
    if (error.status === 401 && error.code === 'auth_session_invalid') {
      window.dispatchEvent(new Event(AUTH_SESSION_INVALID_EVENT))
    }
    if (shouldRefreshAppAuthAfterError(path, error.code)) {
      appCsrfToken = ''
      setSelectedMessengerAccountId(null)
      window.dispatchEvent(new Event(APP_AUTH_SESSION_INVALID_EVENT))
    }
    throw error
  }
  if (typeof result.payload?.csrf_token === 'string') {
    appCsrfToken = result.payload.csrf_token
  }
  const appUserSessionInvalid = (
    path === '/api/v2/app-auth/status' && result.payload?.session_invalid
  )
  if (path === '/api/v2/app-auth/logout' || appUserSessionInvalid) {
    appCsrfToken = ''
    setSelectedMessengerAccountId(null)
  }
  return result.payload as T
}

export async function reportClientDiagnostic(
  payload: ClientDiagnosticPayload,
  correlationId = createClientCorrelationId(),
) {
  try {
    const result = await window.eitaaDesktop.api(
      'POST',
      '/api/v2/client-diagnostics',
      payload,
      appCsrfToken || undefined,
      undefined,
      correlationId,
    )
    if (result.status >= 200 && result.status < 300 && result.payload?.ok === true) return true
  } catch { /* the desktop fallback below must remain best effort */ }
  try { return await window.eitaaDesktop.reportDiagnostic(payload, correlationId) }
  catch { return false }
}

export function query(path: string, params: Record<string, string | number | undefined>) {
  const search = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== '') search.set(key, String(value))
  })
  return `${path}?${search.toString()}`
}

export type ReportingWitnessEventRef = {
  event_id: string
  role: string
  review_status: string
}

export type ReportingWitnessStatus = {
  peer_id: string
  message_id: string
  registered: boolean
  events: ReportingWitnessEventRef[]
}

export async function fetchReportingWitnessStatus(
  peerId: string,
  messageIds: string[],
): Promise<Record<string, ReportingWitnessStatus>> {
  const ids = messageIds.filter(id => String(id).trim())
  if (!peerId || ids.length === 0) return {}
  const query = new URLSearchParams({ peer_id: peerId, message_id: ids.join(',') })
  const payload = await api<{ ok?: boolean; statuses?: ReportingWitnessStatus[] }>(
    'GET',
    `/api/v3/reporting/witness-status?${query.toString()}`,
  )
  const byMessage: Record<string, ReportingWitnessStatus> = {}
  for (const status of payload.statuses || []) {
    byMessage[String(status.message_id)] = status
  }
  return byMessage
}
