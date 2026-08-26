import { Component, type ErrorInfo, type ReactNode } from 'react'
import { Alert, Box, Button, Container, Typography } from '@mui/material'
import { reportClientDiagnostic } from './lib/api'

const recent = new Map<string, number>()
const WINDOW_MS = 5_000

function safeErrorType(reason: unknown) {
  const candidate = reason instanceof Error ? reason.name : typeof reason
  return /^[A-Za-z][A-Za-z0-9_.-]{0,80}$/.test(candidate) ? candidate : 'Error'
}

async function report(
  event: ClientDiagnosticPayload['event'],
  reason: unknown,
  componentStackPresent = false,
) {
  const errorType = safeErrorType(reason)
  const key = `${event}:${errorType}`
  const now = Date.now()
  if (now - (recent.get(key) || 0) < WINDOW_MS) return
  recent.set(key, now)
  await reportClientDiagnostic({
    event,
    level: 'error',
    error_type: errorType,
    safe_context: {
      component_stack_present: componentStackPresent,
      document_visible: document.visibilityState === 'visible',
      online: navigator.onLine !== false,
      surface: 'renderer',
    },
  })
}

let installed = false
export function installGlobalErrorReporting() {
  if (installed) return
  installed = true
  window.addEventListener('error', event => { void report('renderer_unhandled_error', event.error) })
  window.addEventListener('unhandledrejection', event => { void report('renderer_unhandled_rejection', event.reason) })
}

export class ClientErrorBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false }

  static getDerivedStateFromError() { return { failed: true } }

  componentDidCatch(error: Error, info: ErrorInfo) {
    void report('renderer_render_error', error, Boolean(info.componentStack))
  }

  render() {
    if (!this.state.failed) return this.props.children
    return <Box component="main" role="alert" dir="rtl" sx={{ minHeight: '100dvh', display: 'grid', placeItems: 'center', bgcolor: 'background.default', p: 2 }}>
      <Container maxWidth="sm">
        <Alert severity="error" variant="outlined" sx={{ alignItems: 'flex-start', '& .MuiAlert-message': { width: '100%' } }}>
          <Typography variant="h5" component="h1" fontWeight={900} gutterBottom>رابط برنامه با خطای غیرمنتظره روبه‌رو شد</Typography>
          <Typography color="text.secondary" sx={{ mb: 2 }}>گزارش فنی امن ثبت شد؛ اطلاعات حساب، پیام یا رمز در آن ذخیره نمی‌شود.</Typography>
          <Button type="button" variant="contained" onClick={() => window.location.reload()}>بارگذاری دوباره</Button>
        </Alert>
      </Container>
    </Box>
  }
}
