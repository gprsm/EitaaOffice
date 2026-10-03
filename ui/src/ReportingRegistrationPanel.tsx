import { useEffect, useMemo, useRef, useState } from 'react'
import {
  Alert,
  Box,
  Button,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  IconButton,
  MenuItem,
  Stack,
  Step,
  StepLabel,
  Stepper,
  TextField,
  Typography,
} from '@mui/material'
import CloseRounded from '@mui/icons-material/CloseRounded'
import AddRounded from '@mui/icons-material/AddRounded'
import DeleteOutlineRounded from '@mui/icons-material/DeleteOutlineRounded'
import { api } from './lib/api'
import { parseJalaliDate } from './utils/helpers'

const PROGRAM_KINDS = [
  { value: 'trip', label: 'بازدید و سفر' },
  { value: 'contest', label: 'مسابقه' },
  { value: 'quran_contest', label: 'مسابقهٔ قرآنی' },
  { value: 'ceremony', label: 'مراسم' },
  { value: 'prayer', label: 'نماز جمعه و اقامه' },
  { value: 'honor', label: 'تجلیل و افتخار' },
  { value: 'customer_care', label: 'پاسخگویی' },
  { value: 'charter', label: 'منشور' },
  { value: 'training_course', label: 'دورهٔ آموزشی' },
  { value: 'content_production', label: 'تولید محتوا' },
  { value: 'counseling', label: 'مشاوره' },
  { value: 'education_services', label: 'خدمات آموزشی' },
  { value: 'external_collaboration', label: 'همکاری بیرونی' },
]

const UNIT_SCOPES = [
  { value: 'provincial_hq', label: 'ستاد استانی' },
  { value: 'judicial_domain', label: 'حوزهٔ قضایی' },
]

const VALUE_TYPES = [
  { value: 'integer', label: 'شمارش' },
  { value: 'decimal', label: 'مبلغ/اعشاری' },
  { value: 'text', label: 'متنی' },
  { value: 'bool', label: 'بله/خیر' },
  { value: 'unknown', label: 'نامعلوم' },
]

const EMPTY: RegistrationDraft = {
  topic: '', notes: '', occurredOn: '', unit: 'provincial_hq', unit_name: '',
  programKinds: ['ceremony'], witnesses: [], facts: [],
}

const STEPS = ['موضوع رویداد', 'برنامه و فکتها', 'شاهدان', 'بازبینی و ثبت']

type WitnessDraft = {
  peer_id: string
  message_id: string
  messenger_account: string
  role: 'primary' | 'supporting'
  note: string
}

type FactDraft = { metric: string; value: string; unit_of_measure: string; value_type: string }

type RegistrationDraft = {
  topic: string
  notes: string
  occurredOn: string
  unit: string
  unit_name: string
  programKinds: string[]
  witnesses: WitnessDraft[]
  facts: FactDraft[]
}

type SubmitResult = { message_id: string; ok: boolean; error?: string; existing_event_id?: string }

function witnessRow(peerKey: string, messageId: number | string): WitnessDraft {
  return { peer_id: peerKey, message_id: String(messageId), messenger_account: '', role: 'primary', note: '' }
}

export function ReportingRegistrationPanel(props: {
  siteKey: string
  dialogPeerKey: string
  messageIds: number[]
  onClose: () => void
}) {
  const storageKey = useMemo(
    () => `reporting-registration-${props.dialogPeerKey}-${props.messageIds.join('-')}`,
    [props.dialogPeerKey, props.messageIds],
  )
  const [step, setStep] = useState(0)
  const [draft, setDraft] = useState<RegistrationDraft>(() => ({
    ...EMPTY,
    witnesses: props.messageIds.map(id => witnessRow(props.dialogPeerKey, id)),
  }))
  const [restored, setRestored] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [results, setResults] = useState<{ eventId: string; etag: string; witnesses: SubmitResult[] } | null>(null)
  const [conflict, setConflict] = useState<{ message: string; current_etag?: string } | null>(null)
  const [confirmClose, setConfirmClose] = useState(false)
  const [errorText, setErrorText] = useState('')
  const dirtyRef = useRef(false)

  // Restore a saved draft once on mount (incomplete forms must survive reloads).
  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(storageKey)
      if (!raw) return
      const parsed = JSON.parse(raw) as Partial<RegistrationDraft>
      setDraft(current => ({
        ...current,
        ...parsed,
        witnesses: parsed.witnesses && parsed.witnesses.length ? parsed.witnesses : current.witnesses,
      }))
      setRestored(true)
    } catch { /* corrupt draft is ignored */ }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Debounced autosave of the incomplete draft.
  useEffect(() => {
    const timer = window.setTimeout(() => {
      try { window.localStorage.setItem(storageKey, JSON.stringify(draft)) } catch { /* storage full */ }
    }, 400)
    return () => window.clearTimeout(timer)
  }, [draft, storageKey])

  const update = (patch: Partial<RegistrationDraft>) => {
    dirtyRef.current = true
    setDraft(current => ({ ...current, ...patch }))
  }

  const jalaliDate = parseJalaliDate(draft.occurredOn)
  const stepValid = step === 0
    ? Boolean(jalaliDate) && draft.topic.trim().length > 1
    : step === 2
      ? draft.witnesses.every(w => w.role === 'primary' || w.note.trim().length > 0)
      : true

  const submit = async () => {
    if (!jalaliDate) { setErrorText('تاریخ وقوع جلالی نامعتبر است (مثال: ۱۴۰۵/۰۵/۰۱)'); setStep(0); return }
    setSubmitting(true)
    setErrorText('')
    try {
      const iso = `${jalaliDate.getFullYear()}-${String(jalaliDate.getMonth() + 1).padStart(2, '0')}-${String(jalaliDate.getDate()).padStart(2, '0')}`
      const created = await api<{ ok?: boolean; event_id: string; etag: string }>('POST', '/api/v3/reporting/events', {
        program_kinds: draft.programKinds.length ? draft.programKinds : ['ceremony'],
        occurred_on: iso,
        unit: draft.unit,
        unit_name: draft.unit_name,
        notes: [draft.topic, draft.notes].filter(Boolean).join('\n'),
      })
      const witnessResults: SubmitResult[] = []
      for (const witness of draft.witnesses) {
        if (!witness.message_id.trim()) continue
        try {
          await api('POST', `/api/v3/reporting/events/${created.event_id}/witnesses`, {
            peer_id: witness.peer_id,
            message_id: witness.message_id,
            messenger_account: witness.messenger_account,
            role: witness.role,
            note: witness.note,
          })
          witnessResults.push({ message_id: witness.message_id, ok: true })
        } catch (exc) {
          const context = (exc as { context?: { existing_event_id?: string } }).context || {}
          witnessResults.push({
            message_id: witness.message_id,
            ok: false,
            error: exc instanceof Error && exc.message ? exc.message : 'ثبت شاهد ناموفق بود',
            existing_event_id: context.existing_event_id,
          })
        }
      }
      setResults({ eventId: created.event_id, etag: created.etag, witnesses: witnessResults })
      window.localStorage.removeItem(storageKey)
      dirtyRef.current = false
      setStep(3)
    } catch (exc) {
      setErrorText(exc instanceof Error ? exc.message : 'ثبت رویداد ناموفق بود')
    } finally {
      setSubmitting(false)
    }
  }

  const requestClose = () => {
    if (dirtyRef.current && !results) setConfirmClose(true)
    else props.onClose()
  }

  return <Dialog open fullScreen onClose={() => requestClose()}>
    <DialogTitle sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
      <Typography variant="h6" component="h2" sx={{ flex: 1 }}>ثبت رویداد در سامانه گزارشگیری</Typography>
      <IconButton aria-label="بستن پنل ثبت" onClick={() => requestClose()}><CloseRounded /></IconButton>
    </DialogTitle>
    <DialogContent dividers sx={{ bgcolor: 'background.default' }}>
      <Stepper activeStep={step} alternativeLabel sx={{ mb: 2 }}>
        {STEPS.map(label => <Step key={label}><StepLabel>{label}</StepLabel></Step>)}
      </Stepper>
      {restored && !results && <Alert severity="info" sx={{ mb: 2 }}>پیشنویس پیشین همین فرم بازیابی شد؛ میتوانید ادامه دهید.</Alert>}
      {errorText && <Alert severity="error" sx={{ mb: 2 }}>{errorText}</Alert>}
      {conflict && <Alert severity="warning" sx={{ mb: 2 }}>تعارض ویرایش: {conflict.message}{conflict.current_etag ? ' — نسخهٔ سرور تازهتر است.' : ''}</Alert>}

      {step === 0 && <Stack spacing={2} sx={{ maxWidth: 640, mx: 'auto' }}>
        <TextField label="موضوع رویداد" value={draft.topic} onChange={event => update({ topic: event.target.value })} required fullWidth />
        <TextField label="تاریخ وقوع (جلالی، مثال ۱۴۰۵/۰۵/۰۱)" value={draft.occurredOn} onChange={event => update({ occurredOn: event.target.value })} required fullWidth dir="ltr" error={draft.occurredOn.length > 3 && !jalaliDate} helperText={draft.occurredOn.length > 3 && !jalaliDate ? 'قالب تاریخ نامعتبر است' : undefined} />
        <TextField select label="حوزهٔ ثبت" value={draft.unit} onChange={event => update({ unit: event.target.value })} fullWidth>
          {UNIT_SCOPES.map(item => <MenuItem key={item.value} value={item.value}>{item.label}</MenuItem>)}
        </TextField>
        <TextField label="نام واحد" value={draft.unit_name} onChange={event => update({ unit_name: event.target.value })} fullWidth />
        <TextField label="توضیحات تکمیلی" value={draft.notes} onChange={event => update({ notes: event.target.value })} multiline minRows={3} fullWidth />
      </Stack>}

      {step === 1 && <Stack spacing={2} sx={{ maxWidth: 720, mx: 'auto' }}>
        <Box>
          <Typography variant="subtitle2" sx={{ mb: 1 }}>برنامههای مرتبط (حداقل یکی)</Typography>
          <Stack direction="row" flexWrap="wrap" gap={0.75}>
            {PROGRAM_KINDS.map(kind => {
              const selected = draft.programKinds.includes(kind.value)
              return <Chip key={kind.value} label={kind.label} color={selected ? 'primary' : 'default'} variant={selected ? 'filled' : 'outlined'} onClick={() => update({ programKinds: selected ? draft.programKinds.filter(v => v !== kind.value) : [...draft.programKinds, kind.value] })} />
            })}
          </Stack>
        </Box>
        <Divider />
        <Typography variant="subtitle2">فکتهای شمارشی (اختیاری)</Typography>
        {draft.facts.map((fact, index) => <Stack key={index} direction={{ xs: 'column', sm: 'row' }} spacing={1} alignItems={{ sm: 'center' }}>
          <TextField size="small" label="سنجه" value={fact.metric} onChange={event => update({ facts: draft.facts.map((f, i) => i === index ? { ...f, metric: event.target.value } : f) })} sx={{ flex: 2 }} />
          <TextField size="small" label="مقدار" value={fact.value} onChange={event => update({ facts: draft.facts.map((f, i) => i === index ? { ...f, value: event.target.value } : f) })} sx={{ flex: 1 }} dir="ltr" />
          <TextField size="small" select label="نوع" value={fact.value_type} onChange={event => update({ facts: draft.facts.map((f, i) => i === index ? { ...f, value_type: event.target.value } : f) })} sx={{ flex: 1 }}>
            {VALUE_TYPES.map(item => <MenuItem key={item.value} value={item.value}>{item.label}</MenuItem>)}
          </TextField>
          <TextField size="small" label="واحد" value={fact.unit_of_measure} onChange={event => update({ facts: draft.facts.map((f, i) => i === index ? { ...f, unit_of_measure: event.target.value } : f) })} sx={{ flex: 1 }} />
          <IconButton aria-label="حذف فکت" onClick={() => update({ facts: draft.facts.filter((_, i) => i !== index) })}><DeleteOutlineRounded /></IconButton>
        </Stack>)}
        <Button variant="text" startIcon={<AddRounded />} onClick={() => update({ facts: [...draft.facts, { metric: '', value: '', unit_of_measure: 'count', value_type: 'integer' }] })}>افزودن فکت</Button>
      </Stack>}

      {step === 2 && <Stack spacing={1.5} sx={{ maxWidth: 760, mx: 'auto' }}>
        {draft.witnesses.map((witness, index) => <Stack key={`${witness.message_id}-${index}`} spacing={1} sx={{ border: 1, borderColor: 'divider', borderRadius: 2, p: 1.5 }}>
          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1}>
            <TextField size="small" label="شناسهٔ گفتگو (peer)" value={witness.peer_id} onChange={event => update({ witnesses: draft.witnesses.map((w, i) => i === index ? { ...w, peer_id: event.target.value } : w) })} sx={{ flex: 2 }} dir="ltr" />
            <TextField size="small" label="شناسهٔ پیام" value={witness.message_id} onChange={event => update({ witnesses: draft.witnesses.map((w, i) => i === index ? { ...w, message_id: event.target.value } : w) })} sx={{ flex: 1 }} dir="ltr" />
            <TextField size="small" label="حساب پیامرسان (اختیاری)" value={witness.messenger_account} onChange={event => update({ witnesses: draft.witnesses.map((w, i) => i === index ? { ...w, messenger_account: event.target.value } : w) })} sx={{ flex: 1 }} dir="ltr" />
            <TextField size="small" select label="نقش" value={witness.role} onChange={event => update({ witnesses: draft.witnesses.map((w, i) => i === index ? { ...w, role: event.target.value as 'primary' | 'supporting' } : w) })} sx={{ flex: 1 }}>
              <MenuItem value="primary">اصلی</MenuItem>
              <MenuItem value="supporting">پشتیبان</MenuItem>
            </TextField>
          </Stack>
          {witness.role === 'supporting' && <TextField size="small" label="دلیل پیوند پشتیبان (الزامی)" value={witness.note} onChange={event => update({ witnesses: draft.witnesses.map((w, i) => i === index ? { ...w, note: event.target.value } : w) })} fullWidth />}
          <Stack direction="row" justifyContent="flex-end">
            <Button size="small" color="error" startIcon={<DeleteOutlineRounded />} onClick={() => update({ witnesses: draft.witnesses.filter((_, i) => i !== index) })}>حذف شاهد</Button>
          </Stack>
        </Stack>)}
        <Button variant="text" startIcon={<AddRounded />} onClick={() => update({ witnesses: [...draft.witnesses, witnessRow('', '')] })}>افزودن شاهد دستی</Button>
      </Stack>}

      {step === 3 && !results && <Stack spacing={2} sx={{ maxWidth: 640, mx: 'auto' }}>
        <Typography variant="subtitle2">خلاصهٔ ثبت</Typography>
        <Typography variant="body2">موضوع: {draft.topic || '—'}</Typography>
        <Typography variant="body2">تاریخ وقوع: {draft.occurredOn || '—'} (جلالی)</Typography>
        <Typography variant="body2">برنامهها: {draft.programKinds.join('، ') || '—'}</Typography>
        <Typography variant="body2">تعداد فکتها: {draft.facts.length}</Typography>
        <Typography variant="body2">شاهدان: {draft.witnesses.filter(w => w.message_id.trim()).length} مورد ({draft.witnesses.filter(w => w.role === 'primary').length} اصلی، {draft.witnesses.filter(w => w.role === 'supporting').length} پشتیبان)</Typography>
        <Alert severity="info">ثبت بهصورت پیشنویس انجام میشود و پیش از تأیید انسانی در خروجی رسمی اثر نمیگذارد.</Alert>
        <Button variant="contained" onClick={() => void submit()} disabled={submitting}>ثبت پیش‌نویس و پیوند شاهدان</Button>
      </Stack>}

      {results && <Stack spacing={1.5} sx={{ maxWidth: 640, mx: 'auto' }}>
        <Alert severity="success">پیش‌نویس رویداد {results.eventId} ساخته شد.</Alert>
        {results.witnesses.map(result => <Stack key={result.message_id} direction="row" spacing={1} alignItems="center">
          <Chip size="small" color={result.ok ? 'success' : 'error'} label={result.ok ? `پیوند شد · پیام ${result.message_id}` : `تعارض · پیام ${result.message_id}`} />
          {!result.ok && result.existing_event_id && <Typography variant="caption" color="text.secondary">این پیام پیشتر در پروندهٔ {result.existing_event_id} ثبت شده است.</Typography>}
          {!result.ok && !result.existing_event_id && <Typography variant="caption" color="text.secondary">{result.error}</Typography>}
        </Stack>)}
        <Alert severity="info">وضعیت کارت پیام پس از بستن پنل بهروز میشود.</Alert>
      </Stack>}
    </DialogContent>
    <DialogActions sx={{ justifyContent: 'space-between', px: 2 }}>
      <Button disabled={step === 0 || submitting} onClick={() => setStep(value => Math.max(0, value - 1))}>مرحلهٔ قبل</Button>
      <Stack direction="row" spacing={1}>
        <Button color="inherit" onClick={() => requestClose()} disabled={submitting}>بستن</Button>
        {step < 3 && <Button variant="contained" disabled={!stepValid} onClick={() => setStep(value => Math.min(3, value + 1))}>مرحلهٔ بعد</Button>}
      </Stack>
    </DialogActions>
    {confirmClose && <Dialog open onClose={() => setConfirmClose(false)}>
      <DialogTitle>تغییرات ذخیرهنشده</DialogTitle>
      <DialogContent><Typography variant="body2">پیشنویس این فرم بهصورت خودکار در همین دستگاه ذخیره شده است؛ با بستن، در بازگشایی بعدی بازیابی میشود. بستن پنل؟</Typography></DialogContent>
      <DialogActions>
        <Button onClick={() => setConfirmClose(false)}>ادامهٔ ثبت</Button>
        <Button color="warning" onClick={() => { setConfirmClose(false); props.onClose() }}>بستن پنل</Button>
      </DialogActions>
    </Dialog>}
  </Dialog>
}
