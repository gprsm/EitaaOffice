import { useCallback, useEffect, useState } from 'react'
import { Alert, Button } from '@mui/material'
import {
  CLIENT_CONNECTIVITY_CHANGED_EVENT,
  getClientConnectivity,
  probeReadiness,
  reportClientConnectivity,
} from './lib/api'
import { adaptivePollDelay, currentPollingEnvironment } from './lib/polling.mjs'

type Connectivity = 'online' | 'offline' | 'reconnecting'

export function ConnectionStatus() {
  const [status, setStatus] = useState<Connectivity>(() => getClientConnectivity())
  const [retryAttempt, setRetryAttempt] = useState(0)
  const retry = useCallback(async () => {
    reportClientConnectivity('reconnecting')
    const ready = await probeReadiness()
    setRetryAttempt(current => ready ? 0 : Math.min(20, current + 1))
  }, [])

  useEffect(() => {
    const changed = (event: Event) => {
      const detail = (event as CustomEvent<{ status?: Connectivity }>).detail
      setStatus(detail?.status || getClientConnectivity())
    }
    const offline = () => reportClientConnectivity('offline')
    const online = () => { void retry() }
    window.addEventListener(CLIENT_CONNECTIVITY_CHANGED_EVENT, changed)
    window.addEventListener('offline', offline)
    window.addEventListener('online', online)
    return () => {
      window.removeEventListener(CLIENT_CONNECTIVITY_CHANGED_EVENT, changed)
      window.removeEventListener('offline', offline)
      window.removeEventListener('online', online)
    }
  }, [retry])

  useEffect(() => {
    if (status === 'online') return undefined
    const timer = window.setTimeout(
      () => { void retry() },
      adaptivePollDelay(retryAttempt, {
        ...currentPollingEnvironment(),
        active: false,
        online: false,
      }),
    )
    return () => window.clearTimeout(timer)
  }, [retry, retryAttempt, status])

  if (status === 'online') return null
  return <Alert
    severity={status === 'offline' ? 'error' : 'warning'}
    role="status"
    sx={{ position: 'fixed', insetInline: { xs: 8, sm: 'auto' }, insetInlineEnd: { sm: 16 }, top: 12, zIndex: theme => theme.zIndex.snackbar, boxShadow: 4 }}
    action={<Button color="inherit" size="small" onClick={() => void retry()}>تلاش دوباره</Button>}
  >
    {status === 'offline' ? 'ارتباط با سرور قطع شده است.' : 'در حال اتصال دوباره به سرور…'}
  </Alert>
}
