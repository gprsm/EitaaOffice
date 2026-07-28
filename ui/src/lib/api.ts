export const AUTH_SESSION_INVALID_EVENT = 'eitaa-bridge:auth-session-invalid'

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
  const result = await window.eitaaDesktop.api(method, path, body)
  if (result.status < 200 || result.status >= 300 || result.payload?.ok === false) {
    const error = new ApiError(result.status, result.payload)
    if (error.status === 401 && error.code === 'auth_session_invalid') {
      window.dispatchEvent(new Event(AUTH_SESSION_INVALID_EVENT))
    }
    throw error
  }
  return result.payload as T
}

export function query(path: string, params: Record<string, string | number | undefined>) {
  const search = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== '') search.set(key, String(value))
  })
  return `${path}?${search.toString()}`
}
