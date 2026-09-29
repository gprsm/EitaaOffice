import { useEffect, useState } from 'react'
import {
  Alert, Box, Button, Card, CardContent, Chip, Dialog, DialogActions,
  DialogContent, DialogTitle, FormControl, FormHelperText, Grid, IconButton,
  InputLabel, MenuItem, Select, Table, TableBody, TableCell, TableContainer,
  TableHead, TablePagination, TableRow, TextField, Typography, Paper,
} from '@mui/material'
import DeleteIcon from '@mui/icons-material/Delete'
import AddCircleIcon from '@mui/icons-material/AddCircle'
import { api, MANDATE_KINDS, type Mandate } from '../api'
import { faCode, faDate, faNum } from '../periods'
import { ChipCode, VisitChip } from './DashboardPage'
import type { PageProps } from '../App'

const AXIS_LABELS: Record<string, { chip: 'code' | 'visit'; label: string; name: string }> = {
  '80401': { chip: 'code', label: '۸۰۴۰۱', name: 'اردو' },
  '80402': { chip: 'code', label: '۸۰۴۰۲', name: 'مسابقات' },
  '80403': { chip: 'code', label: '۸۰۴۰۳', name: 'مراسم مذهبی' },
  '80501': { chip: 'code', label: '۸۰۵۰۱', name: 'اقامه نماز' },
  '80406': { chip: 'code', label: '۸۰۴۰۶', name: 'تکریم و تجلیل' },
  '80601': { chip: 'code', label: '۸۰۶۰۱', name: 'تشویق ارباب رجوع' },
  '80202': { chip: 'code', label: '۸۰۲۰۲', name: 'منشور اخلاقی' },
  '80403-A': { chip: 'code', label: 'پیوست ۸۰۴۰۳', name: 'ضمیمه زیارت عاشورا' },
  training_courses: { chip: 'visit', label: 'ردیف ۲', name: 'دوره و کارگاه آموزشی' },
  content_production: { chip: 'visit', label: 'ردیف ۴', name: 'تولید محتوا' },
  counseling: { chip: 'visit', label: 'ردیف ۶', name: 'خدمات مشاوره' },
  education_services: { chip: 'visit', label: 'ردیف ۸', name: 'خدمات تحصیلی فرزندان' },
  external_collaboration: { chip: 'visit', label: 'ردیف ۹', name: 'تعامل برون‌سازمانی' },
}

/** رجیستری اسناد بالادستی — دید تجمیعی + ثبت/حذف (F-097) */
export default function MandatesPage({ notify }: PageProps) {
  const [program, setProgram] = useState('')
  const [search, setSearch] = useState('')
  const [rows, setRows] = useState<Mandate[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(0)
  const [pageSize, setPageSize] = useState(25)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [dialogOpen, setDialogOpen] = useState(false)

  useEffect(() => { setPage(0) }, [program, search])

  useEffect(() => {
    let alive = true
    setLoading(true)
    api.mandates(program, search, pageSize, page * pageSize)
      .then((res) => { if (alive) { setRows(res.rows); setTotal(res.total); setError('') } })
      .catch((err) => alive && setError(err instanceof Error ? err.message : 'خطا در دریافت اسناد'))
      .finally(() => alive && setLoading(false))
    return () => { alive = false }
  }, [program, search, page, pageSize])

  const remove = async (id: string) => {
    if (!window.confirm('آیا از حذف این سند اطمینان دارید؟')) return
    try {
      await api.deleteMandate(id)
      notify('سند ابلاغی حذف شد', 'success')
      setRows((r) => r.filter((row) => row.mandate_id !== id))
    } catch (err) {
      notify(err instanceof Error ? err.message : 'خطا در حذف سند', 'error')
    }
  }

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      <Card>
        <CardContent sx={{ display: 'flex', flexWrap: 'wrap', gap: 1.5, alignItems: 'center' }}>
          <FormControl size="small" sx={{ minWidth: 230, flex: { md: 1 } }}>
            <InputLabel>محور گزارش</InputLabel>
            <Select label="محور گزارش" value={program} onChange={(e) => setProgram(e.target.value)}>
              <MenuItem value="">همهٔ محورها</MenuItem>
              {Object.entries(AXIS_LABELS).map(([ref, meta]) => (
                <MenuItem key={ref} value={ref}>{meta.label} — {meta.name}</MenuItem>
              ))}
            </Select>
          </FormControl>
          <TextField size="small" label="جستجو در عنوان، شماره، مرجع…" value={search}
            onChange={(e) => setSearch(e.target.value)} sx={{ flex: 2, minWidth: 220 }} />
          <Button variant="contained" startIcon={<AddCircleIcon />} onClick={() => setDialogOpen(true)}>
            ثبت مستند ابلاغی
          </Button>
        </CardContent>
      </Card>

      {error && <Alert severity="error">{error}</Alert>}

      <TableContainer component={Paper}>
        <Table size="small" sx={{ minWidth: 760 }}>
          <TableHead>
            <TableRow>
              <TableCell>محور برنامه</TableCell>
              <TableCell>نوع سند</TableCell>
              <TableCell>عنوان سند</TableCell>
              <TableCell>شماره</TableCell>
              <TableCell>تاریخ ابلاغ</TableCell>
              <TableCell>مرجع ابلاغ</TableCell>
              <TableCell align="center">حذف</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {rows.map((md) => {
              const meta = AXIS_LABELS[md.program_code]
              return (
                <TableRow key={md.mandate_id} hover>
                  <TableCell>
                    {meta
                      ? (meta.chip === 'code' ? <ChipCode code={md.program_code === '80403-A' ? '80403-A' : md.program_code} /> : <VisitChip label={meta.label} />)
                      : <Typography variant="caption" color="text.secondary">سازمانی</Typography>}
                    {meta && <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>{meta.name}</Typography>}
                  </TableCell>
                  <TableCell><Chip size="small" color="primary" variant="outlined" label={MANDATE_KINDS[md.kind] ?? md.kind} /></TableCell>
                  <TableCell sx={{ maxWidth: 340 }}>
                    <strong>{md.title}</strong>
                    {md.notes && (
                      <Typography variant="caption" color="text.secondary" sx={{ display: 'block', whiteSpace: 'normal' }}>
                        {md.notes.slice(0, 140)}{md.notes.length > 140 ? '…' : ''}
                      </Typography>
                    )}
                  </TableCell>
                  <TableCell><code>{md.number || '—'}</code></TableCell>
                  <TableCell style={{ whiteSpace: 'nowrap' }}>{faDate(md.issued_on)}</TableCell>
                  <TableCell sx={{ fontSize: 11.5 }}>{md.document_ref || '—'}</TableCell>
                  <TableCell align="center">
                    <IconButton size="small" color="error" onClick={() => remove(md.mandate_id)} aria-label="حذف سند">
                      <DeleteIcon fontSize="small" />
                    </IconButton>
                  </TableCell>
                </TableRow>
              )
            })}
          </TableBody>
        </Table>
      </TableContainer>

      <TablePagination
        component="div"
        count={total}
        page={page}
        onPageChange={(_, p) => setPage(p)}
        rowsPerPage={pageSize}
        onRowsPerPageChange={(e) => { setPageSize(Number(e.target.value)); setPage(0) }}
        rowsPerPageOptions={[25, 50, 100]}
        labelRowsPerPage="سطر در صفحه:"
        labelDisplayedRows={({ from, to, count }) => `${faNum(from)}–${faNum(to)} از ${faNum(count)}`}
      />

      <NewMandateDialog open={dialogOpen} onClose={() => setDialogOpen(false)}
        onSaved={(title) => { setDialogOpen(false); notify(`سند «${title}» ثبت شد`, 'success'); setPage(0) }} />
    </Box>
  )
}

function NewMandateDialog({
  open, onClose, onSaved,
}: { open: boolean; onClose: () => void; onSaved: (title: string) => void }) {
  const [form, setForm] = useState({ program_code: '80401', kind: 'circular', title: '', number: '', issued_on: '', document_ref: '', notes: '' })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

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
        <Grid container spacing={1.5}>
          <Grid size={{ xs: 12, sm: 6 }}>
            <FormControl size="small" fullWidth>
              <InputLabel>محور برنامه</InputLabel>
              <Select label="محور برنامه" value={form.program_code}
                onChange={(e) => set('program_code', e.target.value)}>
                {Object.entries(AXIS_LABELS).map(([ref, meta]) => (
                  <MenuItem key={ref} value={ref}>{meta.label} — {meta.name}</MenuItem>
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

void faCode
