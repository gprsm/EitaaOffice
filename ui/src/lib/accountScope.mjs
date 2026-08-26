export function captureAccountScope(accountId) {
  return String(accountId || '')
}

export function accountScopeIsCurrent(captured, current) {
  return captureAccountScope(captured) === captureAccountScope(current)
}

export function accountStateKey(appUserId, accountId) {
  const user = String(appUserId || '').trim().toLowerCase()
  const account = String(accountId || '').trim().toLowerCase()
  return `user-${user || 'anonymous'}.account-${account || 'default'}`
}
