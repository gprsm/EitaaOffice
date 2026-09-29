import { useEffect, useState } from 'react'
import {
  Alert, Button, Dialog, DialogActions, DialogContent, DialogTitle,
  FormControl, FormHelperText, Grid, InputLabel, LinearProgress, MenuItem,
  Select, TextField,
} from '@mui/material'
import { api, MANDATE_KINDS } from '../api'

/**
 * دیالوگ ثبت مستند ابلاغی — مشترک تب اسناد و کارت هر شیت
 * با initialProgram کد/ارجاع برنامه از پیش انتخاب می‌شود (F-097).
 */
export function NewMandateDialog({
  open, initialProgram = '80401', onClose, onSaved,
}: {
  open: boolean
  initialProgram?: string
  onClose: () => void
  onSaved: (title: string) => void
}) {
  const AXES: { ref: string; label: string }[] = [
    { ref: '80401', label: '۸۰۴۰۱ — اردو' },
    { ref: '80402', label: '۸۰۴۰۲ — مسابقات' },
    { ref: '80403', label: '۸۰۴۰۳ — مراسم مذهبی' },
    { ref: '80501', label: '۸۰۵۰۱ — اقامه نماز' },
    { ref: '80406', label: '۸۰۴۰۶ — تکریم و تجلیل' },
    { ref: '80601', label: '۸۰۶۰۱ — تشویق ارباب رجوع' },
    { ref: '80202', label: '۸۰۲۰۲ — منشور اخلاقی' },
    { ref: '80403-A', label: 'پیوست ۸۰۴۰۳ — ضمیمه زیارت عاشورا' },
    { ref: 'training_courses', label: 'ردیف ۲ بازدید — دوره و کارگاه آموزشی' },
    { ref: 'content_production', label: 'ردیف ۴ بازدید — تولید محتوا' },
    { ref: 'counseling', label: 'ردیف ۶ بازدید — خدمات مشاوره' },
    { ref: 'education_services', label: 'ردیف ۸ بازدید — خدمات تحصیلی فرزندان' },
    { ref: 'external_collaboration', label: 'ردیف ۹ بازدید — تعامل برون‌سازمانی' },
  ]

  const [form, setForm] = useState({
    program_code: initialProgram, kind: 'circular', title: '', number: '', issued_on: '', document_ref: '', notes: '',
  })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (open) {
      setForm((f) => ({ ...f, program_code: initialProgram }))
      setError('')
    }
  }, [open, initialProgram])

  const set = (k: keyof typeof form, v: string) => setForm((f) => ({ ...f, [k]: v }))

  const submit = async () => {
    setBusy(true)
    setError('')
    try {
      await api.createMandate(form)
      onSaved(form.title)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطا در ثبت سند')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>ثبت مستند ابلاغی و سند بالادستی</DialogTitle>
      <DialogContent dividers>
        {busy && <LinearProgress sx={{ mb: 2 }} />}
        <Grid container spacing={1.5}>
          <Grid size={{ xs: 12, sm: 6 }}>
            <FormControl size="small" fullWidth>
              <InputLabel>محور برنامه</InputLabel>
              <Select label="محور برنامه" value={form.program_code}
                onChange={(e) => set('program_code', e.target.value)}>
                {AXES.map((a) => (
                  <MenuItem key={a.ref} value={a.ref}>{a.label}</MenuItem>
                ))}
              </Select>
            </FormControl>
          </Grid>
          <Grid size={{ xs: 12, sm: 6 }}>
            <FormControl size="small" fullWidth>
              <InputLabel>نوع سند</InputLabel>
              <Select label="نوع سند" value={form.kind} onChange={(e) => set('kind', e.target.value)}>
                {Object.entries(MANDATE_KINDS).map(([k, label]) => (
                  <MenuItem key={k} value={k}>{label}</MenuItem>
                ))}
              </Select>
            </FormControl>
          </Grid>
          <Grid size={{ xs: 12 }}>
            <TextField size="small" fullWidth required label="عنوان سند" value={form.title}
              onChange={(e) => set('title', e.target.value)} />
          </Grid>
          <Grid size={{ xs: 12, sm: 6 }}>
            <TextField size="small" fullWidth label="شماره سند" value={form.number}
              onChange={(e) => set('number', e.target.value)} />
          </Grid>
          <Grid size={{ xs: 12, sm: 6 }}>
            <TextField size="small" fullWidth label="تاریخ ابلاغ (شمسی)" placeholder="۱۴۰۵/۰۱/۱۵"
              value={form.issued_on} onChange={(e) => set('issued_on', e.target.value)} />
          </Grid>
          <Grid size={{ xs: 12 }}>
            <TextField size="small" fullWidth label="مرجع ابلاغ" value={form.document_ref}
              onChange={(e) => set('document_ref', e.target.value)} />
          </Grid>
          <Grid size={{ xs: 12 }}>
            <TextField size="small" fullWidth multiline rows={2} label="مفاد کلیدی"
              value={form.notes} onChange={(e) => set('notes', e.target.value)} />
          </Grid>
        </Grid>
        {error && <FormHelperText error sx={{ mt: 1 }}>{error}</FormHelperText>}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} disabled={busy}>انصراف</Button>
        <Button onClick={submit} variant="contained" disabled={busy || !form.title.trim()}>ثبت سند</Button>
      </DialogActions>
    </Dialog>
  )
}
