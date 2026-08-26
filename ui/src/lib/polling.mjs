export function adaptivePollDelay(attempt = 0, environment = {}) {
  const selectedAttempt = Math.max(0, Math.min(100, Number(attempt) || 0))
  const visible = environment.visible !== false
  const online = environment.online !== false
  const mobile = environment.mobile === true
  const saveData = environment.saveData === true
  const active = environment.active !== false
  if (!online) return Math.min(30_000, 4_000 * (2 ** Math.min(3, selectedAttempt)))
  if (!visible) return active ? 8_000 : 20_000
  let delay = active ? (mobile ? 1_250 : 750) : (mobile ? 4_000 : 2_500)
  if (saveData) delay = Math.max(delay, active ? 2_500 : 8_000)
  if (selectedAttempt > 30) delay = Math.max(delay, mobile ? 2_000 : 1_250)
  return delay
}

export function currentPollingEnvironment() {
  const connection = typeof navigator === 'undefined' ? undefined : navigator.connection
  return {
    visible: typeof document === 'undefined' || document.visibilityState === 'visible',
    online: typeof navigator === 'undefined' || navigator.onLine !== false,
    mobile: typeof window !== 'undefined' && window.matchMedia('(max-width: 599px)').matches,
    saveData: Boolean(connection?.saveData),
  }
}

export function waitForAdaptivePoll(attempt = 0, options = {}) {
  const delay = adaptivePollDelay(attempt, {
    ...currentPollingEnvironment(),
    active: options.active !== false,
  })
  return new Promise(resolve => window.setTimeout(resolve, delay))
}
