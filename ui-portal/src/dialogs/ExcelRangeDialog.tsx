import { useState } from 'react'
import {
  Alert, Box, Button, Dialog, DialogActions, DialogContent, DialogContentText,
  DialogTitle, LinearProgress,
} from '@mui/material'
import { api } from '../api'
import { usePeriod } from '../components/PeriodPicker'
import { faNum } from '../periods'

/**
 * صدور اکسل بر اساس دورهٔ انتخاب‌شده در نوار دوره (F-097)
 * پیش‌نمایش دوره و هشدار بازمحاسبه؛ خروجی فقط شامل رویدادهای همان بازه است.
 */
export function ExcelRangeDialog({
  open, onClose, notify,
}: { open: boolean; onClose: () => void; notify: (text: string, severity?: 'success' | 'error' | 'info') => void }) {
  const { period } = usePeriod()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const run = async () => {
    setBusy(true)
    setError('')
    try {
      const fromJ = `${faNum(period.fromJalali[0])}/${faNum(String(period.fromJalali[1]).padStart(2, '0'))}/${faNum(String(period.fromJalali[2]).padStart(2, '0'))}`
      const toJ = `${faNum(period.toJalali[0])}/${faNum(String(period.toJalali[1]).padStart(2, '0'))}/${faNum(String(period.toJalali[2]).padStart(2, '0'))}`
      const res = await api.triggerExcel(fromJ, toJ)
      notify(`فایل اکسل «${period.label}» صادر شد — دانلود آغاز می‌شود`, 'success')
      onClose()
      window.location.href = res.download_url
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطای نامشخص')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog open={open} onClose={busy ? undefined : onClose} maxWidth="sm" fullWidth>
      <DialogTitle>صدور اکسل دورهٔ «{period.label}»</DialogTitle>
      <DialogContent>
        {busy && <LinearProgress sx={{ mb: 2 }} />}
        <DialogContentText sx={{ mb: 2, lineHeight: 2 }}>
          کارنامهٔ اکسل رسمی فقط با رویدادهای داخل دورهٔ انتخاب‌شده بازمحاسبه می‌شود؛ جمع ستون‌های شیت‌ها
          از فکت‌های همان بازه اخذ می‌گردد و جمع‌های دوره‌های دیگر در آن نشت نمی‌کند.
        </DialogContentText>
        <Alert severity="info" variant="outlined">
          دورهٔ فعال: <strong>{period.label}</strong> — خروجی با نام مستقل ذخیره می‌شود.
        </Alert>
        {error && <Alert severity="error" sx={{ mt: 2 }}>{error}</Alert>}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} disabled={busy}>انصراف</Button>
        <Button onClick={run} variant="contained" disabled={busy}>صدور و دریافت فایل</Button>
      </DialogActions>
    </Dialog>
  )
}
