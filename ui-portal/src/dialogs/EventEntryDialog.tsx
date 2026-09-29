import { useEffect, useMemo, useRef, useState } from 'react'
import {
  Alert, Box, Button, Chip, Dialog, DialogActions, DialogContent, DialogTitle,
  FormControl, FormControlLabel, FormHelperText, Grid, InputLabel, LinearProgress, MenuItem,
  Select, Switch, Tab, Tabs, TextField, Typography,
} from '@mui/material'
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider'
import { AdapterDateFnsJalali } from '@mui/x-date-pickers/AdapterDateFnsJalali'
import { DatePicker } from '@mui/x-date-pickers/DatePicker'
import { faIR } from 'date-fns-jalali/locale'
import UploadFileIcon from '@mui/icons-material/UploadFile'
import EventNoteIcon from '@mui/icons-material/EventNote'
import TuneIcon from '@mui/icons-material/Tune'
import AssignmentIcon from '@mui/icons-material/Assignment'
import ArrowForwardIcon from '@mui/icons-material/ArrowForward'
import ArrowBackIcon from '@mui/icons-material/ArrowBack'
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
 * فرم ثبت/ویرایش رویداد با ساختار تب‌دار و مرحله‌ای (Wizard-Tabs):
 *  - تب ۱: مشخصات رویداد و زمان‌بندی (عنوان، تاریخ شمسی، مخاطبان)
 *  - تب ۲: سنجه‌ها و اقلام تخصصی برنامه (مشتق از spec فرم کاربرگ سفر استانی)
 *  - تب ۳: تمهیدات، عوامل اجرایی و مستندات (پذیرایی، حضور مسئولان، پیوست، یادداشت)
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
  const [programRef, setProgramRef] = useState(initialRef || '80401')
  const [activeTab, setActiveTab] = useState(0)
  const [spec, setSpec] = useState<EntryFormSpec | null>(null)
  const [specLoading, setSpecLoading] = useState(false)
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
  const loadedEventRef = useRef<PortalEvent | null>(null)

  const inferProgramRef = (ev: PortalEvent): string => {
    if (ev.program_code) return ev.program_code
    if (Number(ev.is_ashura_pilgrimage) === 1) return '80403-A'
    try {
      const kinds = JSON.parse(ev.program_kinds_json || '[]')
      const k = Array.isArray(kinds) ? kinds[0] : ''
      const map: Record<string, string> = {
        trip: '80401',
        contest: '80402',
        ceremony: '80403',
        prayer: '80501',
        honor: '80406',
        customer_care: '80601',
        charter: '80202',
        training_course: 'training_courses',
        content_production: 'content_production',
        counseling: 'counseling',
        education_services: 'education_services',
        external_collaboration: 'external_collaboration',
      }
      return map[k] || '80403'
    } catch {
      return '80403'
    }
  }

  // ۱. چرخه بارگذاری اولیه: هنگام باز یا بسته شدن دیالوگ
  useEffect(() => {
    if (!open) {
      setSpec(null)
      setSpecLoading(false)
      setSpecError('')
      setValues({})
      setError('')
      setOccasion('')
      setAttendees('')
      setAttendeesKind('verified')
      setOfficialPresent(false)
      setHadReception(false)
      setNotes('')
      setEvidence(null)
      setDate(todayJalali())
      setActiveTab(0)
      loadedEventRef.current = null
      return
    }

    let alive = true

    if (editEventId) {
      setBusy(true)
      setSpecLoading(true)
      setError('')
      setSpecError('')

      // تنها یک درخواست برای eventDetail و سپس بارگذاری spec متناظر بدون race condition و بدون درخواست تکراری
      api.eventDetail(editEventId)
        .then(async (ev) => {
          if (!alive) return
          loadedEventRef.current = ev
          setOccasion(ev.occasion || '')
          setAttendees(ev.attendees_count !== null && ev.attendees_count !== undefined ? String(Math.round(ev.attendees_count)) : '')
          setAttendeesKind(ev.attendees_value_kind === 'estimated' ? 'estimated' : 'verified')
          setOfficialPresent(Number(ev.official_present) === 1)
          setHadReception(Number(ev.had_reception) === 1)
          setNotes(ev.notes || '')
          const j = /^(\d{4})-(\d{2})-(\d{2})/.exec(ev.occurred_on || '')
          if (j) setDate(gregorianToJalali(Number(j[1]), Number(j[2]), Number(j[3])))

          const ref = inferProgramRef(ev)
          setProgramRef(ref)

          try {
            const s = await api.entryFormSpec(ref)
            if (!alive) return
            setSpec(s)
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
          } catch (specErr) {
            if (alive) setSpecError(specErr instanceof Error ? specErr.message : 'خطا در دریافت فرم اختصاصی')
          }
        })
        .catch((err) => {
          if (alive) setError(err instanceof Error ? err.message : 'خطا در بارگذاری جزئیات رویداد')
        })
        .finally(() => {
          if (alive) {
            setBusy(false)
            setSpecLoading(false)
          }
        })
    } else {
      loadedEventRef.current = null
      const targetRef = initialRef || '80401'
      setProgramRef(targetRef)
      setOccasion('')
      setAttendees('')
      setAttendeesKind('verified')
      setOfficialPresent(false)
      setHadReception(false)
      setNotes('')
      setEvidence(null)
      setDate(todayJalali())
      setActiveTab(0)
      setValues({})
      setError('')
      setSpecError('')

      setSpecLoading(true)
      api.entryFormSpec(targetRef)
        .then((s) => {
          if (!alive) return
          setSpec(s)
        })
        .catch((err) => {
          if (alive) setSpecError(err instanceof Error ? err.message : 'خطا در دریافت فرم اختصاصی')
        })
        .finally(() => {
          if (alive) setSpecLoading(false)
        })
    }

    return () => { alive = false }
  }, [open, editEventId, initialRef])

  // ۲. مدیریت تغییر محور برنامه: حفظ ورودی‌های کاربر و بارگذاری spec جدید بدون درخواست مجدد رویداد
  const handleProgramRefChange = async (newRef: string) => {
    if (newRef === programRef) return
    setProgramRef(newRef)
    setSpecLoading(true)
    setSpecError('')

    try {
      const s = await api.entryFormSpec(newRef)
      setSpec(s)

      // حفظ ورودی‌های قبلی کاربر و در صورت وجود رویداد اولیه، پر کردن فیلدهای جدید خالی از فکت‌های ذخیره‌شده
      setValues((prev) => {
        const next = { ...prev }
        if (loadedEventRef.current) {
          const ev = loadedEventRef.current
          for (const section of s.sections) {
            for (const field of section.fields) {
              if (field.t === 'occasion_class' && !next[field.n]) {
                next[field.n] = ev.occasion_class || 'standard'
              } else if (field.t === 'number' && field.n.startsWith('dim_') && !next[field.n]) {
                const v = ev.facts?.[field.n.slice(4)]?.value
                if (v !== undefined && v > 0) next[field.n] = String(Math.round(v))
              } else if (field.t === 'select' && field.cn?.startsWith('selcount_') && !next[field.n]) {
                const chosen = field.o?.find((o) => o.m && (ev.facts?.[o.m]?.value ?? 0) > 0)
                if (chosen && chosen.m) {
                  next[field.n] = chosen.v
                  if (!next[field.cn]) next[field.cn] = String(Math.round(ev.facts[chosen.m].value))
                }
              }
            }
          }
        }
        return next
      })
    } catch (err) {
      setSpecError(err instanceof Error ? err.message : 'خطا در بارگذاری فرم اختصاصی محور جدید')
    } finally {
      setSpecLoading(false)
    }
  }

  const setField = (name: string, value: string) => setValues((v) => ({ ...v, [name]: value }))

  const payload = useMemo(() => {
    // تاریخ شمسی با ارقام استاندارد انگلیسی برای تضمین پارس و اعتبارسنجی قطعی در سرور
    const formattedDate = `${date[0]}/${String(date[1]).padStart(2, '0')}/${String(date[2]).padStart(2, '0')}`

    const data: Record<string, string> = {
      program_kind: programRef,
      occasion: occasion.trim(),
      occurred_on: formattedDate,
      attendees_value_kind: attendeesKind,
      notes: notes.trim(),
      official_present: officialPresent ? '1' : '0',
      had_reception: hadReception ? '1' : '0',
    }

    if (attendees.trim()) {
      data.attendees_count = attendees.trim()
    }

    // پرچم زیارت عاشورا برای محور 80403-A یا تغییر از آن در حالت ویرایش
    if (programRef === '80403-A') {
      data.is_ashura_pilgrimage = '1'
    } else if (editEventId) {
      data.is_ashura_pilgrimage = '0'
    }

    // مقدار پیش‌فرض occasion_class در صورت لزوم
    if (values.occasion_class) {
      data.occasion_class = values.occasion_class
    } else if (programRef === '80403') {
      data.occasion_class = 'standard'
    }

    if (!spec) return data

    for (const section of spec.sections) {
      for (const field of section.fields) {
        const value = (values[field.n] ?? '').trim()

        if (field.t === 'occasion_class') {
          data.occasion_class = value || 'standard'
          continue
        }

        if (field.t === 'select' && field.cn?.startsWith('selcount_')) {
          // گزینهٔ دسته‌دار مسابقات: عدد → dim_<metric گزینهٔ فعال>
          const chosen = field.o?.find((o) => o.v === value)
          const countVal = (values[field.cn] ?? '').trim()
          if (field.o) {
            for (const opt of field.o) {
              if (opt.m) {
                if (chosen && opt.m === chosen.m && countVal && Number(countVal) > 0) {
                  data[`dim_${opt.m}`] = countVal
                } else if (editEventId) {
                  // در حالت ویرایش، در صورت تغییر رده، رده قبلی صفر فرستاده شود تا حذف گردد
                  data[`dim_${opt.m}`] = '0'
                }
              }
            }
          }
          if (value) data[field.n] = value
          continue
        }

        if (field.t === 'number' && field.n.startsWith('dim_')) {
          if (value !== '') {
            data[field.n] = value
          } else if (editEventId) {
            // در حالت ویرایش، در صورت خالی‌شدن سنجه توسط کاربر مقدار 0 فرستاده شود تا فکت در دیتابیس پاک شود
            data[field.n] = '0'
          }
          continue
        }

        if (value !== '') {
          data[field.n] = value
        }
      }
    }
    return data
  }, [programRef, occasion, date, attendees, attendeesKind, officialPresent, hadReception, notes, spec, values, editEventId])

  const filledMetricsCount = useMemo(() => {
    return Object.entries(values).filter(([k, v]) => k.startsWith('dim_') && Number(v) > 0).length
  }, [values])

  const submit = async () => {
    if (!occasion.trim()) {
      setActiveTab(0)
      setError('عنوان یا مناسبت برنامه الزامی است (تب ۱)')
      return
    }
    setBusy(true)
    setError('')
    try {
      if (editEventId) {
        await api.updateEvent(editEventId, payload, evidence)
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
        <DialogTitle sx={{ pb: 1 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 1 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <Typography variant="h6" sx={{ fontWeight: 800 }}>
                {editEventId ? 'ویرایش رویداد فرهنگی' : 'ثبت رویداد فرهنگی جدید'}
              </Typography>
              {editEventId && <Chip size="small" color="warning" variant="outlined" label="حالت ویرایش" />}
            </Box>
            {spec && (
              <Chip
                size="small"
                color="primary"
                variant="outlined"
                label={spec.row_label ? `${spec.row_label} — ${spec.name}` : spec.name}
              />
            )}
          </Box>
        </DialogTitle>

        {/* نوار تب‌های مرحله‌ای */}
        <Box sx={{ borderBottom: 1, borderColor: 'divider', px: 2 }}>
          <Tabs value={activeTab} onChange={(_, val) => setActiveTab(val)}>
            <Tab
              icon={<EventNoteIcon />}
              iconPosition="start"
              label="۱. مشخصات رویداد"
              sx={{ minHeight: 48, fontWeight: 700 }}
            />
            <Tab
              icon={<TuneIcon />}
              iconPosition="start"
              label={
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.8 }}>
                  <span>۲. سنجه‌های برنامه</span>
                  {filledMetricsCount > 0 && (
                    <Chip size="small" label={faNum(filledMetricsCount)} color="primary" sx={{ height: 18, fontSize: 10.5 }} />
                  )}
                </Box>
              }
              sx={{ minHeight: 48, fontWeight: 700 }}
            />
            <Tab
              icon={<AssignmentIcon />}
              iconPosition="start"
              label="۳. تمهیدات و پیوست‌ها"
              sx={{ minHeight: 48, fontWeight: 700 }}
            />
          </Tabs>
        </Box>

        <DialogContent dividers sx={{ py: 2.5 }}>
          {busy && <LinearProgress sx={{ mb: 2 }} />}
          {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

          {/* تب ۱: مشخصات رویداد و زمان‌بندی */}
          {activeTab === 0 && (
            <Grid container spacing={2}>
              <Grid size={{ xs: 12, sm: 6 }}>
                <FormControl size="small" fullWidth required>
                  <InputLabel>محور گزارش / کاربرگ</InputLabel>
                  <Select
                    label="محور گزارش / کاربرگ"
                    value={programRef}
                    onChange={(e) => handleProgramRefChange(e.target.value)}
                  >
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
                  {editEventId && (
                    <FormHelperText sx={{ color: 'primary.main' }}>
                      با تغییر محور، سنجه‌های تخصصی متناسب با محور جدید بارگذاری و ذخیره می‌شوند
                    </FormHelperText>
                  )}
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
                <TextField
                  size="small"
                  fullWidth
                  required
                  label="عنوان یا مناسبت برنامه"
                  placeholder="مثال: آیین تجلیل از نخبگان قرآنی / کارگاه سبک زندگی اسلامی"
                  value={occasion}
                  onChange={(e) => setOccasion(e.target.value)}
                />
              </Grid>

              <Grid size={{ xs: 12, sm: 6 }}>
                <TextField
                  size="small"
                  fullWidth
                  type="number"
                  label="تعداد کل شرکت‌کنندگان / مخاطبان"
                  value={attendees}
                  onChange={(e) => setAttendees(e.target.value)}
                  inputProps={{ min: 0 }}
                  placeholder="مثال: ۱۲۰"
                />
              </Grid>

              <Grid size={{ xs: 12, sm: 6 }}>
                <FormControl size="small" fullWidth>
                  <InputLabel>نوع آمار مخاطب</InputLabel>
                  <Select
                    label="نوع آمار مخاطب"
                    value={attendeesKind}
                    onChange={(e) => setAttendeesKind(e.target.value)}
                  >
                    <MenuItem value="verified">قطعی و مستند (با لیست حضور)</MenuItem>
                    <MenuItem value="estimated">تخمینی / برآوردی</MenuItem>
                  </Select>
                </FormControl>
              </Grid>
            </Grid>
          )}

          {/* تب ۲: سنجه‌ها و اقلام تخصصی برنامه */}
          {activeTab === 1 && (
            <Box>
              {specError && <Alert severity="error" sx={{ mb: 2 }}>{specError}</Alert>}
              {(specLoading || (!spec && !specError && programRef)) && <LinearProgress sx={{ my: 2 }} />}
              {spec && (
                <Box>
                  <Alert severity="info" variant="outlined" sx={{ mb: 2.5 }}>
                    <strong>{spec.row_label ? `${spec.row_label} — ` : ''}{spec.name}:</strong> {spec.intro}
                  </Alert>

                  {spec.sections.map((section) => (
                    <Box key={section.title} sx={{ mb: 3 }}>
                      <Typography variant="subtitle2" sx={{ mb: 0.8, display: 'flex', alignItems: 'center', gap: 0.8, color: 'primary.main', fontWeight: 800 }}>
                        <Box component="span" aria-hidden>▪</Box> {section.title}
                      </Typography>
                      {section.hint && (
                        <FormHelperText sx={{ mb: 1.2, mt: 0 }}>{section.hint}</FormHelperText>
                      )}
                      <Grid container spacing={1.8}>
                        {section.fields.map((field) => (
                          <Grid size={{ xs: 12, sm: 6, md: 4 }} key={field.n}>
                            <EntryFieldInput
                              field={field}
                              value={values[field.n] ?? ''}
                              onChange={(v) => setField(field.n, v)}
                            />
                            {field.cn && field.cl && (
                              <TextField
                                size="small"
                                fullWidth
                                type="number"
                                sx={{ mt: 1 }}
                                label={field.cl}
                                placeholder="۱"
                                value={values[field.cn] ?? ''}
                                onChange={(e) => setField(field.cn!, e.target.value)}
                              />
                            )}
                          </Grid>
                        ))}
                      </Grid>
                    </Box>
                  ))}
                </Box>
              )}
            </Box>
          )}

          {/* تب ۳: تمهیدات، عوامل اجرایی و مستندات */}
          {activeTab === 2 && (
            <Grid container spacing={2}>
              <Grid size={{ xs: 12, sm: 6 }}>
                <Box sx={{ border: '1px solid #e2e8f0', p: 1.5, borderRadius: 2 }}>
                  <FormControlLabel
                    control={
                      <Switch
                        checked={officialPresent}
                        onChange={(e) => setOfficialPresent(e.target.checked)}
                        color="primary"
                      />
                    }
                    label="حضور مسئولان قضایی (رئیس کل / دادستان / معاونان)"
                  />
                  <FormHelperText>در ارزیابی‌های کیفی کارنامه موثر است</FormHelperText>
                </Box>
              </Grid>

              <Grid size={{ xs: 12, sm: 6 }}>
                <Box sx={{ border: '1px solid #e2e8f0', p: 1.5, borderRadius: 2 }}>
                  <FormControlLabel
                    control={
                      <Switch
                        checked={hadReception}
                        onChange={(e) => setHadReception(e.target.checked)}
                        color="primary"
                      />
                    }
                    label="پذیرایی / تدارکات انجام شده است"
                  />
                  <FormHelperText>ثبت تمهیدات برگزاری مراسم یا رویداد</FormHelperText>
                </Box>
              </Grid>

              <Grid size={{ xs: 12 }}>
                <TextField
                  size="small"
                  fullWidth
                  multiline
                  rows={3}
                  label="توضیحات و گزارش تکمیلی رویداد"
                  placeholder="نکات مهم، بازخوردها، مصوبات یا جزئیات عملیاتی برنامه..."
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                />
              </Grid>

              <Grid size={{ xs: 12 }}>
                <Button variant="outlined" component="label" startIcon={<UploadFileIcon />} fullWidth sx={{ py: 1.5 }}>
                  {editEventId ? 'پیوست فاکتور هزینه، فهرست افراد یا تصویر تکمیلی' : 'پیوست مستندات، فاکتور هزینه یا تصویر رویداد (اختیاری)'}
                  <input
                    type="file"
                    hidden
                    accept="image/*,.pdf,.docx,.xlsx,.xls"
                    onChange={(e) => setEvidence(e.target.files?.[0] ?? null)}
                  />
                </Button>
                {evidence ? (
                  <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mt: 1, p: 1, bgcolor: '#f0fdf4', borderRadius: 1.5, border: '1px solid #bbf7d0' }}>
                    <FormHelperText sx={{ m: 0, color: 'success.main', fontWeight: 700 }}>
                      فایل انتخاب‌شده: {evidence.name} ({(evidence.size / 1024).toFixed(1)} کیلوبایت)
                    </FormHelperText>
                    <Button size="small" color="error" onClick={() => setEvidence(null)} sx={{ minWidth: 0, px: 1, py: 0.2 }}>
                      حذف پیوست
                    </Button>
                  </Box>
                ) : (
                  <FormHelperText sx={{ mt: 0.5, color: 'text.secondary' }}>
                    پشتیبانی از انواع اسناد: فاکتور هزینه (PDF)، لیست اکسل شرکت‌کنندگان (.xlsx) و تصاویر مستند
                  </FormHelperText>
                )}
              </Grid>
            </Grid>
          )}
        </DialogContent>

        <DialogActions sx={{ px: 2.5, py: 1.5, justifyContent: 'space-between' }}>
          <Box sx={{ display: 'flex', gap: 1 }}>
            <Button onClick={onClose} disabled={busy} color="inherit">
              انصراف
            </Button>
            {activeTab > 0 && (
              <Button
                startIcon={<ArrowForwardIcon />}
                onClick={() => setActiveTab((t) => t - 1)}
                disabled={busy}
              >
                مرحله قبل
              </Button>
            )}
          </Box>

          <Box sx={{ display: 'flex', gap: 1 }}>
            {activeTab < 2 ? (
              <Button
                variant="outlined"
                endIcon={<ArrowBackIcon />}
                onClick={() => setActiveTab((t) => t + 1)}
              >
                مرحله بعد
              </Button>
            ) : null}

            <Button
              onClick={submit}
              variant="contained"
              disabled={busy || !programRef}
              color="primary"
              sx={{ fontWeight: 800 }}
            >
              {editEventId ? 'ذخیره تغییرات' : 'ثبت نهایی رویداد'}
            </Button>
          </Box>
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
