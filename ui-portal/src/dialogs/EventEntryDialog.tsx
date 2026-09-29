import { useEffect, useMemo, useState } from 'react'
import {
  Alert, Box, Button, Chip, Dialog, DialogActions, DialogContent, DialogTitle,
  FormControl, FormHelperText, Grid, InputLabel, LinearProgress, MenuItem,
  Select, TextField, Typography,
} from '@mui/material'
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider'
import { AdapterDateFnsJalali } from '@mui/x-date-pickers/AdapterDateFnsJalali'
import { DatePicker } from '@mui/x-date-pickers/DatePicker'
import { faIR } from 'date-fns-jalali/locale'
import UploadFileIcon from '@mui/icons-material/UploadFile'
import { api, type EntryField, type EntryFormSpec, type PortalEvent } from '../api'
import { faNum, gregorianToJalali, jalaliToGregorian } from '../periods'

/** جلالی ↔ Date برای دیت‌پیکر MUI جلالی */
const jalaliToDate = (j: [number, number, number]): Date => {
  const [gy, gm, gd] = jalaliToGregorian(j[0], j[1], j[2])
  return new Date(gy, gm - 1, gd)
}
const dateToJalali = (d: Date): [number, number, number] =>
  gregorianToJalali(d.getFullYear(), d.getMonth() + 1, d.getDate())

const todayJalali = (): [number, number, number] => dateToJalali(new Date())

const jalaliLabel = (j: [number, number, number]): string =>
  `${faNum(j[0])}/${faNum(String(j[1]).padStart(2, '0'))}/${faNum(String(j[2]).padStart(2, '0'))}`

/**
 * فرم ثبت/ویرایش رویداد — بخش‌ها و فیلدها دقیقاً از مشخصات فرم اختصاصی برنامه
 * (get_entry_form&format=json) رندر می‌شود؛ سنجه‌های عددی فکت می‌سازند و
 * گزینه‌های دسته با data-metric به همان فکت نگاشت می‌شوند (F-096/F-097/V-231).
 * حالت ویرایش: prefill از get_event_detail و ذخیره با update_event.
 */
export function EventEntryDialog({
  open, initialRef, editEventId = null, onClose, onSaved,
}: {
  open: boolean
  initialRef: string
  editEventId?: string | null
  onClose: () => void
  onSaved: () => void
}) {
  const [programRef, setProgramRef] = useState(initialRef)
  const [spec, setSpec] = useState<EntryFormSpec | null>(null)
  const [specError, setSpecError] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const [values, setValues] = useState<Record<string, string>>({})
  const [occasion, setOccasion] = useState('')
  const [date, setDate] = useState<[number, number, number]>(todayJalali())
  const [attendees, setAttendees] = useState('')
  const [attendeesKind, setAttendeesKind] = useState('verified')
  const [officialPresent, setOfficialPresent] = useState(false)
  const [hadReception, setHadReception] = useState(false)
  const [notes, setNotes] = useState('')
  const [evidence, setEvidence] = useState<File | null>(null)

  useEffect(() => {
    if (open) setProgramRef(initialRef)
  }, [open, initialRef])

  // بارگذاری spec فرم اختصاصی + prefill در حالت ویرایش
  useEffect(() => {
    if (!open || !programRef) { setSpec(null); return }
    setSpec(null)
    setSpecError('')
    setValues({})
    setError('')
    const load = async () => {
      try {
        const s = await api.entryFormSpec(programRef)
        setSpec(s)
        if (editEventId) {
          const ev: PortalEvent = await api.eventDetail(editEventId)
          setOccasion(ev.occasion || '')
          setAttendees(ev.attendees_count !== null && ev.attendees_count !== undefined ? String(Math.round(ev.attendees_count)) : '')
          setAttendeesKind(ev.attendees_value_kind === 'estimated' ? 'estimated' : 'verified')
          setOfficialPresent(Number(ev.official_present) === 1)
          setHadReception(Number(ev.had_reception) === 1)
          setNotes(ev.notes || '')
          const j = /^(\d{4})-(\d{2})-(\d{2})/.exec(ev.occurred_on || '')
          if (j) setDate(gregorianToJalali(Number(j[1]), Number(j[2]), Number(j[3])))
          // prefill ابعاد عددی + بازسازی انتخاب‌های دسته از فکت‌ها
          const pre: Record<string, string> = {}
          for (const section of s.sections) {
            for (const field of section.fields) {
              if (field.t === 'occasion_class') {
                pre[field.n] = ev.occasion_class || 'standard'
              } else if (field.t === 'number' && field.n.startsWith('dim_')) {
                const v = ev.facts?.[field.n.slice(4)]?.value
                if (v !== undefined && v > 0) pre[field.n] = String(Math.round(v))
              } else if (field.t === 'select' && field.cn?.startsWith('selcount_')) {
                const chosen = field.o?.find((o) => o.m && (ev.facts?.[o.m]?.value ?? 0) > 0)
                if (chosen && chosen.m) {
                  pre[field.n] = chosen.v
                  pre[field.cn] = String(Math.round(ev.facts[chosen.m].value))
                }
              }
            }
          }
          setValues(pre)
        } else {
          setOccasion('')
          setAttendees('')
          setOfficialPresent(false)
          setHadReception(false)
          setNotes('')
          setDate(todayJalali())
        }
      } catch (err) {
        setSpecError(err instanceof Error ? err.message : 'خطا در دریافت فرم اختصاصی')
      }
    }
    void load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, programRef, editEventId])

  const setField = (name: string, value: string) => setValues((v) => ({ ...v, [name]: value }))

  const payload = useMemo(() => {
    const data: Record<string, string> = {
      program_kind: programRef,
      occasion,
      occurred_on: jalaliLabel(date),
      attendees_value_kind: attendeesKind,
      notes,
      official_present: officialPresent ? '1' : '0',
      had_reception: hadReception ? '1' : '0',
    }
    if (attendees) data.attendees_count = attendees
    if (!spec) return data

    for (const section of spec.sections) {
      for (const field of section.fields) {
        const value = (values[field.n] ?? '').trim()
        if (field.t === 'occasion_class') {
          if (value) data.occasion_class = value
          continue
        }
        if (field.t === 'select' && field.cn?.startsWith('selcount_')) {
          // گزینهٔ دسته‌دار: عدد → dim_<metric گزینهٔ فعال>
          const chosen = field.o?.find((o) => o.v === value)
          if (chosen?.m && field.cn) {
            const countVal = (values[field.cn] ?? '').trim()
            if (countVal && Number(countVal) > 0) data[`dim_${chosen.m}`] = countVal
          }
          if (value) data[field.n] = value
          continue
        }
        if (value !== '') data[field.n] = value
      }
    }
    return data
  }, [programRef, occasion, date, attendees, attendeesKind, officialPresent, hadReception, notes, spec, values])

  const submit = async () => {
    if (!occasion.trim()) { setError('عنوان یا مناسبت برنامه الزامی است'); return }
    setBusy(true)
    setError('')
    try {
      if (editEventId) {
        await api.updateEvent(editEventId, payload)
        onSaved()
      } else {
        await api.createEvent(payload, evidence)
        onSaved()
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطا در ذخیره رویداد')
    } finally {
      setBusy(false)
    }
  }

  return (
    <LocalizationProvider dateAdapter={AdapterDateFnsJalali} adapterLocale={faIR}>
      <Dialog open={open} onClose={busy ? undefined : onClose} maxWidth="md" fullWidth scroll="paper">
        <DialogTitle>
          {editEventId ? 'ویرایش رویداد فرهنگی' : 'ثبت رویداد فرهنگی جدید'}
          {spec && <Chip size="small" sx={{ mr: 1.5 }} color="primary" variant="outlined"
            label={spec.row_label ? `${spec.row_label} — ${spec.name}` : spec.name} />}
          {editEventId && <Chip size="small" sx={{ mr: 1 }} color="warning" variant="outlined" label="حالت ویرایش" />}
        </DialogTitle>
        <DialogContent dividers>
          {busy && <LinearProgress sx={{ mb: 2 }} />}
          {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

          {/* فیلدهای مشترک */}
          <Grid container spacing={1.5} sx={{ mb: 2 }}>
            <Grid size={{ xs: 12, sm: 6 }}>
              <FormControl size="small" fullWidth required disabled={!!editEventId}>
                <InputLabel>محور گزارش / کاربرگ</InputLabel>
                <Select label="محور گزارش / کاربرگ" value={programRef}
                  onChange={(e) => setProgramRef(e.target.value)}>
                  <MenuItem value="80401">۸۰۴۰۱ — اردو</MenuItem>
                  <MenuItem value="80402">۸۰۴۰۲ — مسابقات</MenuItem>
                  <MenuItem value="80403">۸۰۴۰۳ — مراسم مذهبی</MenuItem>
                  <MenuItem value="80501">۸۰۵۰۱ — اقامه نماز</MenuItem>
                  <MenuItem value="80406">۸۰۴۰۶ — تکریم و تجلیل</MenuItem>
                  <MenuItem value="80601">۸۰۶۰۱ — تشویق ارباب رجوع</MenuItem>
                  <MenuItem value="80202">۸۰۲۰۲ — منشور اخلاقی</MenuItem>
                  <MenuItem value="80403-A">پیوست ۸۰۴۰۳ — ضمیمه زیارت عاشورا</MenuItem>
                  <MenuItem value="training_courses">ردیف ۲ کاربرگ بازدید — دوره و کارگاه آموزشی</MenuItem>
                  <MenuItem value="content_production">ردیف ۴ کاربرگ بازدید — تولید محتوا</MenuItem>
                  <MenuItem value="counseling">ردیف ۶ کاربرگ بازدید — خدمات مشاوره</MenuItem>
                  <MenuItem value="education_services">ردیف ۸ کاربرگ بازدید — خدمات تحصیلی فرزندان</MenuItem>
                  <MenuItem value="external_collaboration">ردیف ۹ کاربرگ بازدید — تعامل برون‌سازمانی</MenuItem>
                </Select>
                {editEventId && <FormHelperText>محور رویداد موجود قابل تغییر نیست</FormHelperText>}
              </FormControl>
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              <DatePicker
                label="تاریخ برگزاری (شمسی)"
                value={jalaliToDate(date)}
                onChange={(d) => { if (d) setDate(dateToJalali(d as Date)) }}
                slotProps={{ textField: { size: 'small', fullWidth: true } }}
              />
            </Grid>
            <Grid size={{ xs: 12 }}>
              <TextField size="small" fullWidth required label="عنوان یا مناسبت برنامه"
                value={occasion} onChange={(e) => setOccasion(e.target.value)} />
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              <TextField size="small" fullWidth type="number" label="تعداد شرکت‌کنندگان"
                value={attendees} onChange={(e) => setAttendees(e.target.value)} inputProps={{ min: 0 }} />
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              <FormControl size="small" fullWidth>
                <InputLabel>نوع آمار مخاطب</InputLabel>
                <Select label="نوع آمار مخاطب" value={attendeesKind}
                  onChange={(e) => setAttendeesKind(e.target.value)}>
                  <MenuItem value="verified">قطعی و مستند</MenuItem>
                  <MenuItem value="estimated">تخمینی</MenuItem>
                </Select>
              </FormControl>
            </Grid>
          </Grid>

          {/* فرم اختصاصی برنامه */}
          {specError && <Alert severity="error" sx={{ mb: 2 }}>{specError}</Alert>}
          {!spec && !specError && programRef && <LinearProgress sx={{ my: 2 }} />}
          {spec && (
            <Box sx={{ mb: 1 }}>
              <Alert severity="info" variant="outlined" sx={{ mb: 2 }}>
                <strong>{spec.row_label ? `${spec.row_label} — ` : ''}{spec.name}:</strong> {spec.intro}
              </Alert>
              {spec.sections.map((section) => (
                <Box key={section.title} sx={{ mb: 2.5 }}>
                  <Typography variant="subtitle2" sx={{ mb: 0.5, display: 'flex', alignItems: 'center', gap: 0.8 }}>
                    <Box component="span" aria-hidden>▪</Box> {section.title}
                  </Typography>
                  {section.hint && (
                    <FormHelperText sx={{ mb: 1, mt: 0 }}>{section.hint}</FormHelperText>
                  )}
                  <Grid container spacing={1.5}>
                    {section.fields.map((field) => (
                      <Grid size={{ xs: 12, sm: 6, md: 4 }} key={field.n}>
                        <EntryFieldInput field={field} value={values[field.n] ?? ''} onChange={(v) => setField(field.n, v)} />
                        {field.cn && field.cl && (
                          <TextField size="small" fullWidth type="number" sx={{ mt: 1 }}
                            label={field.cl} placeholder="۱"
                            value={values[field.cn] ?? ''}
                            onChange={(e) => setField(field.cn!, e.target.value)} />
                        )}
                      </Grid>
                    ))}
                  </Grid>
                </Box>
              ))}
            </Box>
          )}

          <Grid container spacing={1.5}>
            <Grid size={{ xs: 12 }}>
              <TextField size="small" fullWidth multiline rows={2} label="توضیحات و گزارش تکمیلی"
                value={notes} onChange={(e) => setNotes(e.target.value)} />
            </Grid>
            {!editEventId && (
              <Grid size={{ xs: 12, sm: 6 }}>
                <Button variant="outlined" component="label" startIcon={<UploadFileIcon />} fullWidth>
                  پیوست تصویر یا سند (اختیاری)
                  <input type="file" hidden accept="image/*,.pdf,.docx"
                    onChange={(e) => setEvidence(e.target.files?.[0] ?? null)} />
                </Button>
                {evidence && <FormHelperText>{evidence.name}</FormHelperText>}
              </Grid>
            )}
          </Grid>
        </DialogContent>
        <DialogActions>
          <Button onClick={onClose} disabled={busy}>انصراف</Button>
          <Button onClick={submit} variant="contained" disabled={busy || !programRef}>
            {editEventId ? 'ذخیره تغییرات' : 'ثبت نهایی رویداد'}
          </Button>
        </DialogActions>
      </Dialog>
    </LocalizationProvider>
  )
}

function EntryFieldInput({
  field, value, onChange,
}: { field: EntryField; value: string; onChange: (v: string) => void }) {
  const label = field.l + (field.req ? ' *' : '')
  if (field.t === 'occasion_class') {
    return (
      <FormControl size="small" fullWidth required={!!field.req}>
        <InputLabel>{label}</InputLabel>
        <Select label={label} value={value} onChange={(e) => onChange(e.target.value)}>
          <MenuItem value="religious">مذهبی</MenuItem>
          <MenuItem value="national">ملی</MenuItem>
          <MenuItem value="revolutionary">انقلابی</MenuItem>
          <MenuItem value="standard">سایر / عمومی</MenuItem>
        </Select>
        {field.h && <FormHelperText>{field.h}</FormHelperText>}
      </FormControl>
    )
  }
  if (field.t === 'select') {
    return (
      <FormControl size="small" fullWidth required={!!field.req}>
        <InputLabel>{label}</InputLabel>
        <Select label={label} value={value} onChange={(e) => onChange(e.target.value)}>
          <MenuItem value="">— انتخاب کنید —</MenuItem>
          {field.o?.map((o) => <MenuItem key={o.v} value={o.v}>{o.v}</MenuItem>)}
        </Select>
        {field.h && <FormHelperText>{field.h}</FormHelperText>}
      </FormControl>
    )
  }
  if (field.t === 'textarea') {
    return (
      <TextField size="small" fullWidth multiline rows={2} label={label}
        value={value} onChange={(e) => onChange(e.target.value)}
        helperText={field.h} />
    )
  }
  if (field.t === 'number') {
    return (
      <TextField size="small" fullWidth type="number" label={label} placeholder="۰"
        value={value} onChange={(e) => onChange(e.target.value)} helperText={field.h}
        inputProps={{ min: 0, step: 1 }} />
    )
  }
  return (
    <TextField size="small" fullWidth label={label}
      value={value} onChange={(e) => onChange(e.target.value)} helperText={field.h} />
  )
}
