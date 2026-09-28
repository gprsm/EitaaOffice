import { useEffect, useState } from 'react'
import {
  Alert, Box, Card, CardContent, Chip, Grid, LinearProgress, Typography,
} from '@mui/material'
import CheckCircleIcon from '@mui/icons-material/CheckCircle'
import ErrorIcon from '@mui/icons-material/Error'
import { api } from '../api'
import { faNum } from '../periods'

/** پل ارتباطی: سلامت هستهٔ پایتون، پایگاه SQLite و فایل اکسل رسمی (F-097) */
export default function SystemBridgePage() {
  const [state, setState] = useState<{
    python_ready: boolean
    sqlite_ready: boolean
    excel_ready: boolean
    excel_modified: string | null
    excel_size?: number
  } | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    api.health()
      .then((res) => setState(res.health))
      .catch((err) => setError(err instanceof Error ? err.message : 'خطا در دریافت وضعیت'))
  }, [])

  if (error) return <Alert severity="error">{error}</Alert>
  if (!state) return <LinearProgress />

  const items = [
    { label: 'هستهٔ پایتون EitaaBridge', ok: state.python_ready, desc: 'موتور پردازش و صدور اکسل' },
    { label: 'پایگاه SQLite گزارش‌ها', ok: state.sqlite_ready, desc: 'منبع واحد رویدادها و فکت‌ها' },
    { label: 'فایل اکسل رسمی ۱۴۰۵', ok: state.excel_ready, desc: state.excel_modified ? `آخرین تولید: ${faNum(state.excel_modified)}` : 'هنوز تولید نشده' },
  ]

  return (
    <Card>
      <CardContent>
        <Typography variant="h6" sx={{ mb: 2 }}>وضعیت سلامت سامانه (معماری ایزوله LAN)</Typography>
        <Grid container spacing={2}>
          {items.map((item) => (
            <Grid size={{ xs: 12, md: 4 }} key={item.label}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, p: 1.5, border: '1px solid #e2e8f0', borderRadius: 2 }}>
                {item.ok
                  ? <CheckCircleIcon color="success" />
                  : <ErrorIcon color="error" />}
                <Box>
                  <Typography variant="subtitle2">{item.label}</Typography>
                  <Typography variant="caption" color="text.secondary">{item.desc}</Typography>
                </Box>
                <Chip size="small" sx={{ mr: 'auto' }} color={item.ok ? 'success' : 'error'} variant="outlined"
                  label={item.ok ? 'متصل' : 'غیرواکنش'} />
              </Box>
            </Grid>
          ))}
        </Grid>
      </CardContent>
    </Card>
  )
}
