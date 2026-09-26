import assert from 'node:assert/strict'
import { authStartupFailure, authStartupRetryDelay, shouldRefreshAppAuthAfterError } from '../src/lib/authStartupRecovery.mjs'

const incompatible = authStartupFailure({ status: 401, code: 'api_unauthorized' })
assert.equal(incompatible.code, 'api_unauthorized')
assert.equal(incompatible.retryable, false)
assert.match(incompatible.message, /تنظیمات ورود سرور/)
assert.equal(authStartupRetryDelay({ status: 401, code: 'api_unauthorized' }, 0), null)

const unavailable = { status: 503, code: 'service_not_ready' }
assert.equal(authStartupFailure(unavailable).retryable, true)
assert.equal(authStartupRetryDelay(unavailable, 0), 1200)
assert.equal(authStartupRetryDelay(unavailable, 1), null)
assert.equal(authStartupRetryDelay(new Error('network unavailable'), 0), 1200)
assert.equal(authStartupRetryDelay(new Error('network unavailable'), 1), null)

const malformed = authStartupFailure({ status: 400, code: 'secret\nvalue' })
assert.equal(malformed.code, '')
assert.equal(malformed.retryable, false)

assert.equal(shouldRefreshAppAuthAfterError('/api/v2/app-auth/status', 'app_auth_required'), false)
assert.equal(shouldRefreshAppAuthAfterError('/api/v2/app-auth/status', 'app_auth_session_invalid'), false)
assert.equal(shouldRefreshAppAuthAfterError('/api/v2/app-auth/me', 'app_auth_required'), true)
assert.equal(shouldRefreshAppAuthAfterError('/api/v2/app-auth/me', 'app_auth_session_invalid'), true)

console.log('auth startup recovery contracts passed')
