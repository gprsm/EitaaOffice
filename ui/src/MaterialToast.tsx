import { useEffect, useState } from 'react'
import { Alert, Snackbar, type AlertColor } from '@mui/material'

type ToastOptions = { toastId?: string | number }
type ToastItem = {
  key: number
  message: string
  severity: AlertColor
  toastId?: string | number
}

const listeners = new Set<(item: ToastItem) => void>()
const pending: ToastItem[] = []
let sequence = 0

function publish(severity: AlertColor, message: unknown, options?: ToastOptions) {
  const item: ToastItem = {
    key: ++sequence,
    message: String(message ?? ''),
    severity,
    toastId: options?.toastId,
  }
  if (listeners.size === 0) {
    pending.push(item)
    if (pending.length > 6) pending.splice(0, pending.length - 6)
  } else {
    listeners.forEach(listener => listener(item))
  }
  return item.key
}

export const toast = {
  success: (message: unknown, options?: ToastOptions) => publish('success', message, options),
  error: (message: unknown, options?: ToastOptions) => publish('error', message, options),
  info: (message: unknown, options?: ToastOptions) => publish('info', message, options),
  warning: (message: unknown, options?: ToastOptions) => publish('warning', message, options),
  warn: (message: unknown, options?: ToastOptions) => publish('warning', message, options),
}

export function MaterialToastHost() {
  const [queue, setQueue] = useState<ToastItem[]>([])
  const [open, setOpen] = useState(false)
  const current = queue[0]

  useEffect(() => {
    const receive = (item: ToastItem) => setQueue(items => {
      if (item.toastId !== undefined && items.some(existing => existing.toastId === item.toastId)) return items
      return [...items, item].slice(-6)
    })
    listeners.add(receive)
    pending.splice(0).forEach(receive)
    return () => { listeners.delete(receive) }
  }, [])

  useEffect(() => {
    if (current) setOpen(true)
  }, [current?.key])

  if (!current) return null
  return <Snackbar
    key={current.key}
    open={open}
    autoHideDuration={3600}
    anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
    onClose={(_event, reason) => { if (reason !== 'clickaway') setOpen(false) }}
    slotProps={{ transition: { onExited: () => setQueue(items => items.slice(1)) } }}
    sx={{ bottom: { xs: 'calc(76px + env(safe-area-inset-bottom))', md: 20 }, maxWidth: 'min(94vw, 640px)' }}
  >
    <Alert severity={current.severity} variant="filled" onClose={() => setOpen(false)} sx={{ width: '100%', boxShadow: 8, alignItems: 'center' }}>
      {current.message}
    </Alert>
  </Snackbar>
}
