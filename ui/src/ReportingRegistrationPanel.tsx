import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  Alert,
  Autocomplete,
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
import AccountBalanceRounded from '@mui/icons-material/AccountBalanceRounded'
import { api } from './lib/api'
import { jalaliDayKey, jalaliDayLabel, parseJalaliDate } from './utils/helpers'
import { JalaliDateTimePicker } from './components/JalaliDateTimePicker'
import { JudicialUnitsManagementModal, JudicialUnitItem, LiaisonItem } from './components/JudicialUnitsManagementModal'
import { useAppUser } from './AppUserGate'
import { authorLabel } from './MessageContentCard'
import type { DialogItem, MessageItem } from './lib/types'
import { MACRO_INDICATORS, type MicroIndicatorItem, fetchMicroIndicators } from './lib/indicators'

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

export const MAZANDARAN_CITIES = [
  'ساری', 'بابل', 'آمل', 'قائمشهر', 'قائم‌شهر', 'تنکابن', 'چالوس',
  'نوشهر', 'نکا', 'بهشهر', 'رامسر', 'بابلسر', 'محمودآباد', 'سوادکوه',
  'جویبار', 'فریدونکنار', 'فریدون‌کنار', 'گلوگاه', 'میاندرود', 'میاندورود',
  'کلاردشت', 'سیمرغ', 'عباس‌آباد', 'زیراب', 'پل‌سفید', 'چمستان', 'دابودشت',
  'کیاسر', 'بلده', 'کجور', 'نور',
]

export const SENDER_BINDINGS: Record<string, { unit: 'provincial_hq' | 'judicial_domain'; unit_name: string; canonicalAuthor?: string }> = {
  'مهدوی': { unit: 'judicial_domain', unit_name: 'دادگستری سوادکوه', canonicalAuthor: 'مهدوی (رابط فرهنگی سوادکوه)' },
  'دیوسالار': { unit: 'judicial_domain', unit_name: 'دادگستری نور', canonicalAuthor: 'محمدامین دیوسالار (رابط فرهنگی نور)' },
  'احسا': { unit: 'judicial_domain', unit_name: 'دادگستری بابل', canonicalAuthor: 'احسانی (رابط فرهنگی بابل)' },
  'قاسمی شورابی': { unit: 'provincial_hq', unit_name: 'ستاد دادگستری کل استان', canonicalAuthor: 'قاسمی شورابی (ستاد استانی)' },
  'شورابی': { unit: 'provincial_hq', unit_name: 'ستاد دادگستری کل استان', canonicalAuthor: 'قاسمی شورابی (ستاد استانی)' },
}

export function inferRegistrationDefaults(
  sourceMessage?: MessageItem | null,
  dialog?: DialogItem | null,
  sourceMessages?: MessageItem[] | null,
) {
  const members = sourceMessages && sourceMessages.length ? sourceMessages : sourceMessage ? [sourceMessage] : []
  const primaryMsg = sourceMessage || (members.length ? members[0] : null)

  // 1. Report Date (زمان گزارش)
  let occurredOn = ''
  let sourceTimeFormatted = ''
  if (primaryMsg?.date) {
    occurredOn = jalaliDayKey(primaryMsg.date)
    try {
      const d = new Date(primaryMsg.date)
      const timeStr = d.toLocaleTimeString('fa-IR', { hour: '2-digit', minute: '2-digit' })
      sourceTimeFormatted = `${jalaliDayLabel(primaryMsg.date)} · ساعت ${timeStr}`
    } catch {
      sourceTimeFormatted = jalaliDayLabel(primaryMsg.date)
    }
  }

  // Check if text has an explicit Jalali date
  const combinedText = members.map(m => m.text || '').join('\n')
  const dateMatch = combinedText.match(/(?:مورخ|تاریخ|روز)?\s*([1۱][34۳۴][0-9۰-۹]{2}[\/-][0-9۰-۹]{1,2}[\/-][0-9۰-۹]{1,2})/)
  if (dateMatch) {
    const rawDate = dateMatch[1].replace(/[۰-۹]/g, char => String('۰۱۲۳۴۵۶۷۸۹'.indexOf(char))).replace('-', '/')
    if (parseJalaliDate(rawDate)) {
      occurredOn = rawDate
    }
  }

  // 2. Author (نویسنده / رابط فرهنگی گزارش)
  let author = ''
  if (primaryMsg) {
    author = authorLabel(dialog, primaryMsg)
  }

  const isGenericAuthor = !author || author === 'Eitaa' || author === 'شما' || author === 'نویسنده نامشخص' || author === 'مخاطب ایتا'

  // If author is generic, inspect SENDER_BINDINGS against message text
  if (isGenericAuthor) {
    for (const [senderKey, binding] of Object.entries(SENDER_BINDINGS)) {
      if (combinedText.includes(senderKey) && binding.canonicalAuthor) {
        author = binding.canonicalAuthor
        break
      }
    }
  }

  // Also check textual author/liaison regex if still generic
  if (!author || author === 'Eitaa' || author === 'نویسنده نامشخص' || author === 'شما' || author === 'مخاطب ایتا') {
    const textAuthorMatch = combinedText.match(/(?:رابط فرهنگی|گزارشگر|نویسنده|ارسال‌کننده|توسط)\s*[:：\-–]?\s*([^\n،,.:]{3,35})/)
    if (textAuthorMatch && textAuthorMatch[1]?.trim()) {
      author = textAuthorMatch[1].trim()
    }
  }

  // Fallback to dialog title or username if still generic
  if (!author || author === 'Eitaa' || author === 'نویسنده نامشخص') {
    if (dialog?.peer?.title?.trim() && dialog.peer.title.trim() !== 'Eitaa') {
      author = dialog.peer.title.trim()
    } else if (primaryMsg?.sender_username) {
      author = `@${primaryMsg.sender_username.replace(/^@/, '')}`
    }
  }

  // 3. Judicial Domain / City (شهر یا حوزه قضایی)
  let unit: 'provincial_hq' | 'judicial_domain' = 'provincial_hq'
  let unit_name = ''

  // First check sender bindings
  for (const [senderName, binding] of Object.entries(SENDER_BINDINGS)) {
    if (author.includes(senderName) || combinedText.includes(senderName)) {
      unit = binding.unit
      unit_name = binding.unit_name
      break
    }
  }

  if (!unit_name) {
    if (combinedText.includes('شورای حل اختلاف') || author.includes('شورای حل اختلاف')) {
      unit = 'judicial_domain'
      unit_name = 'شورای حل اختلاف'
    } else if (author.includes('ساری') || author.includes('ستاد') || author.includes('دادگستری کل') || combinedText.includes('دادگستری کل')) {
      unit = 'provincial_hq'
      unit_name = 'ستاد دادگستری کل استان'
    } else {
      // Check author first, then dialog title, then text for cities
      const searchTargets = [author, dialog?.peer?.title || '', combinedText]
      for (const target of searchTargets) {
        for (const city of MAZANDARAN_CITIES) {
          if (target.includes(city)) {
            if (city === 'ساری') {
              unit = 'provincial_hq'
              unit_name = 'ستاد دادگستری کل استان'
            } else {
              unit = 'judicial_domain'
              unit_name = `دادگستری ${city}`
            }
            break
          }
        }
        if (unit_name) break
      }
    }
  }

  if (!unit_name && dialog?.display_kind === 'personal' && dialog.peer.title?.trim()) {
    unit = 'judicial_domain'
    unit_name = dialog.peer.title.trim()
  }

  // 4. Topic
  let topic = ''
  if (combinedText.trim()) {
    const lines = combinedText.split('\n').map(l => l.trim()).filter(Boolean)
    if (lines.length) {
      const cleanLine = lines[0].replace(/^[\s#*•\u{1F300}-\u{1F9FF}\u{2600}-\u{26FF}]+/u, '').trim()
      if (cleanLine.length > 2) {
        topic = cleanLine.slice(0, 100)
      }
    }
  }

  return {
    occurredOn,
    sourceTimeFormatted,
    author: author === 'نویسنده نامشخص' ? '' : author,
    unit,
    unit_name,
    topic,
    notes: combinedText,
  }
}

const EMPTY: RegistrationDraft = {
  macroCategory: 'workbook_approved', customTopic: '',
  macroIndicator: '', microIndicators: [],
  topic: '', author: '', notes: '', occurredOn: '', unit: 'provincial_hq', unit_name: '',
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
  macroCategory: 'workbook_approved' | 'other_cultural'
  customTopic: string
  macroIndicator: string
  microIndicators: string[]
  topic: string
  author: string
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
  dialog?: DialogItem | null
  messageIds: number[]
  sourceMessage?: MessageItem | null
  sourceMessages?: MessageItem[] | null
  initialMacroIndicator?: string
  initialMicroIndicators?: string[]
  onClose: () => void
}) {
  const { principal } = useAppUser()
  const activeUserId = principal?.app_user_id || 'local_staff'
  const activeUserName = principal?.display_name || 'کارشناس ثبت'

  const storageKey = useMemo(
    () => `reporting-registration-${props.dialogPeerKey}-${props.messageIds.join('-')}`,
    [props.dialogPeerKey, props.messageIds],
  )
  const [step, setStep] = useState(0)

  const initialInferred = useMemo(
    () => inferRegistrationDefaults(props.sourceMessage, props.dialog, props.sourceMessages),
    [props.sourceMessage, props.dialog, props.sourceMessages],
  )
  const sourceTimeFormatted = initialInferred.sourceTimeFormatted

  const [draft, setDraft] = useState<RegistrationDraft>(() => ({
    ...EMPTY,
    ...initialInferred,
    macroIndicator: props.initialMacroIndicator || '',
    microIndicators: props.initialMicroIndicators || [],
    witnesses: props.messageIds.map(id => witnessRow(props.dialogPeerKey, id)),
  }))
  const [restored, setRestored] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [results, setResults] = useState<{ eventId: string; etag: string; witnesses: SubmitResult[] } | null>(null)
  const [conflict, setConflict] = useState<{ message: string; current_etag?: string } | null>(null)
  const [confirmClose, setConfirmClose] = useState(false)
  const [errorText, setErrorText] = useState('')
  const [judicialUnits, setJudicialUnits] = useState<JudicialUnitItem[]>([])
  const [unitsModalOpen, setUnitsModalOpen] = useState(false)
  const dirtyRef = useRef(false)

  const loadJudicialUnits = useCallback(async () => {
    try {
      const res = await api<{ units: JudicialUnitItem[]; counties: string[] }>('GET', '/api/v3/reporting/units')
      if (res.units && res.units.length > 0) {
        setJudicialUnits(res.units)
      }
    } catch (err) {
      console.warn('Failed to load judicial units:', err)
    }
  }, [])

  useEffect(() => {
    loadJudicialUnits()
  }, [loadJudicialUnits])

  // Resolve liaison and unit from backend registry automatically
  useEffect(() => {
    const resolveSenderAndUnit = async () => {
      try {
        const primaryMsg = props.sourceMessage || (props.sourceMessages && props.sourceMessages.length ? props.sourceMessages[0] : null)
        const combinedText = (props.sourceMessages || (props.sourceMessage ? [props.sourceMessage] : [])).map(m => m.text || '').join('\n')
        const author = primaryMsg ? authorLabel(props.dialog, primaryMsg) : ''

        const res = await api<{
          matched: boolean
          liaison: LiaisonItem | null
          unit: JudicialUnitItem | null
        }>('POST', '/api/v3/reporting/liaisons/resolve', {
          sender_key: primaryMsg?.sender_username || props.dialog?.peer?.id || '',
          username: primaryMsg?.sender_username || '',
          full_name: author,
          text: combinedText,
        })
        if (res.matched) {
          setDraft(current => ({
            ...current,
            unit_name: res.unit?.display_name || current.unit_name,
            unit: (res.unit?.kind === 'provincial_hq' ? 'provincial_hq' : 'judicial_domain') as any,
            author: res.liaison?.full_name ? res.liaison.full_name : current.author,
          }))
        }
      } catch (err) {
        console.warn('Auto resolve liaison warning:', err)
      }
    }
    resolveSenderAndUnit()
  }, [props.sourceMessage, props.dialog, props.sourceMessages])

  // Restore a saved draft once on mount (incomplete forms must survive reloads).
  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(storageKey)
      if (!raw) return
      const parsed = JSON.parse(raw) as Partial<RegistrationDraft>
      setDraft(current => ({
        ...current,
        ...parsed,
        author: parsed.author !== undefined && parsed.author !== '' ? parsed.author : current.author,
        occurredOn: parsed.occurredOn || current.occurredOn,
        unit: parsed.unit || current.unit,
        unit_name: parsed.unit_name || current.unit_name,
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

  const [availableMicroIndicators, setAvailableMicroIndicators] = useState<MicroIndicatorItem[]>([])

  useEffect(() => {
    void fetchMicroIndicators().then(setAvailableMicroIndicators).catch(() => {})
  }, [])

  const submit = async () => {
    if (!jalaliDate) { setErrorText('تاریخ وقوع جلالی نامعتبر است (مثال: ۱۴۰۵/۰۵/۰۱)'); setStep(0); return }
    setSubmitting(true)
    setErrorText('')
    try {
      const iso = `${jalaliDate.getFullYear()}-${String(jalaliDate.getMonth() + 1).padStart(2, '0')}-${String(jalaliDate.getDate()).padStart(2, '0')}`
      const factsPayload = draft.facts
        .filter(f => f.metric.trim() && !isNaN(Number(f.value)) && Number(f.value) >= 0)
        .map(f => ({
          metric: f.metric.trim(),
          value: Number(f.value),
          value_kind: 'verified',
          unit_of_measure: f.unit_of_measure || 'count',
        }))

      const created = await api<{ ok?: boolean; event_id: string; etag: string }>('POST', '/api/v3/reporting/events', {
        macro_category: draft.macroCategory,
        custom_topic: draft.customTopic,
        macro_indicator: draft.macroIndicator,
        micro_indicators: draft.microIndicators,
        program_kinds: draft.programKinds.length ? draft.programKinds : ['ceremony'],
        occurred_on: iso,
        unit: draft.unit,
        unit_name: draft.unit_name,
        notes: [draft.author ? `نویسنده / رابط گزارش: ${draft.author.trim()}` : '', draft.topic, draft.notes].filter(Boolean).join('\n'),
        author: draft.author,
        registered_by_id: activeUserId,
        registered_by_name: activeUserName,
        facts: factsPayload,
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

      // Automatically transition the newly registered event to needs_review
      try {
        await api('POST', `/api/v3/reporting/events/${created.event_id}/submit-review`, {
          actor_id: activeUserId,
          actor_name: activeUserName,
          actor_role: principal?.global_role || 'staff',
          reason: 'ارسال خودکار پس از ثبت نهایی فرم ثبت رویداد',
        })
      } catch (submitErr) {
        console.warn('Auto submit-review warning:', submitErr)
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
        {(sourceTimeFormatted || draft.author || draft.unit_name) && (
          <Box sx={{ p: 1.5, bgcolor: 'action.hover', borderRadius: 2, border: 1, borderColor: 'divider' }}>
            <Typography variant="caption" color="text.secondary" fontWeight={800} sx={{ mb: 1, display: 'block' }}>
              مشخصات استخراج‌شده از پیام ایتا:
            </Typography>
            <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2} divider={<Divider orientation="vertical" flexItem />}>
              {sourceTimeFormatted && (
                <Box sx={{ flex: 1 }}>
                  <Typography variant="caption" color="text.secondary" display="block">زمان ارسال گزارش:</Typography>
                  <Typography variant="body2" fontWeight={800} color="text.primary">{sourceTimeFormatted}</Typography>
                </Box>
              )}
              <Box sx={{ flex: 1 }}>
                <Typography variant="caption" color="text.secondary" display="block">نویسنده / رابط گزارش:</Typography>
                <Typography variant="body2" fontWeight={800} color="primary.main">{draft.author || 'نامشخص'}</Typography>
              </Box>
              <Box sx={{ flex: 1 }}>
                <Typography variant="caption" color="text.secondary" display="block">حوزه قضایی / شهر:</Typography>
                <Typography variant="body2" fontWeight={800} color="secondary.main">{draft.unit_name || (draft.unit === 'provincial_hq' ? 'ستاد استانی' : 'تعیین‌نشده')}</Typography>
              </Box>
            </Stack>
          </Box>
        )}

        <Box sx={{ p: 1.5, bgcolor: 'background.paper', borderRadius: 2, border: 1, borderColor: 'divider' }}>
          <Typography variant="subtitle2" fontWeight={800} sx={{ mb: 1 }}>
            دسته‌بندی کلان برنامه:
          </Typography>
          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1}>
            <Button
              variant={draft.macroCategory === 'workbook_approved' ? 'contained' : 'outlined'}
              color="primary"
              onClick={() => update({ macroCategory: 'workbook_approved' })}
              sx={{ flex: 1, py: 1 }}
            >
              برنامه‌های مصوب سازمانی (شیت‌های ۸ گانه)
            </Button>
            <Button
              variant={draft.macroCategory === 'other_cultural' ? 'contained' : 'outlined'}
              color="secondary"
              onClick={() => update({ macroCategory: 'other_cultural' })}
              sx={{ flex: 1, py: 1 }}
            >
              سایر برنامه‌های فرهنگی (فعالیت‌های آزاد و مشارکتی)
            </Button>
          </Stack>
        </Box>

        {draft.macroCategory === 'other_cultural' && (
          <TextField
            label="عنوان / محور برنامه فرهنگی خارج از شیت"
            placeholder="مثال: پویش‌های مردمی، یادواره‌های خاص، همکاری با ائمه جمعه و نهادهای انقلابی"
            value={draft.customTopic}
            onChange={event => update({ customTopic: event.target.value })}
            required
            fullWidth
            color="secondary"
            helperText="این فعالیت در پیوست فرهنگی ثبت شده و بدون اختلال در جداول شیت‌های ۸ گانه محاسبه می‌گردد."
          />
        )}

        <TextField label="موضوع رویداد" value={draft.topic} onChange={event => update({ topic: event.target.value })} required fullWidth placeholder="مثال: برگزاری مراسم زیارت عاشورا / تجلیل از فعالان فرهنگی" />

        {/* شاخصه‌های کلی و جزئی متصل به گزارش */}
        <Box sx={{ p: 1.5, bgcolor: 'action.hover', borderRadius: 2, border: 1, borderColor: 'divider' }}>
          <Stack spacing={1.5}>
            <TextField
              select
              label="شاخصه کلی (سرفصل برنامه فرهنگی)"
              value={draft.macroIndicator || ''}
              onChange={event => update({ macroIndicator: event.target.value })}
              fullWidth
              helperText="انتخاب از بین ۸ برنامه مصوب یا عنوان «غیر برنامه‌ای»"
            >
              <MenuItem value="">
                <em>(تعیین‌نشده)</em>
              </MenuItem>
              {MACRO_INDICATORS.map(ind => (
                <MenuItem key={ind} value={ind} sx={{ fontWeight: 600 }}>
                  {ind}
                </MenuItem>
              ))}
            </TextField>

            <Autocomplete
              multiple
              freeSolo
              options={availableMicroIndicators.map(i => i.title)}
              value={draft.microIndicators || []}
              onChange={(_, val) => update({ microIndicators: val })}
              renderTags={(value, getTagProps) =>
                value.map((option, index) => (
                  <Chip
                    {...getTagProps({ index })}
                    key={option}
                    label={option}
                    size="small"
                    color="secondary"
                    variant="filled"
                    sx={{ fontWeight: 400 }}
                  />
                ))
              }
              renderInput={params => (
                <TextField
                  {...params}
                  label="شاخصه‌های جزئی (تایپ آزاد یا انتخاب از فهرست)"
                  placeholder="عنوان شاخصه جزئی را تایپ کرده و Enter بزنید..."
                  helperText="عناوین تفصیلی و کلیدواژه‌های موضوعی مرتبط با فعالیت فرهنگی"
                />
              )}
            />
          </Stack>
        </Box>

        <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
          <Box sx={{ flex: 1 }}>
            <JalaliDateTimePicker
              value={draft.occurredOn}
              onChange={val => update({ occurredOn: val })}
              label="تاریخ و زمان رویداد (شمسی)"
              required
              fullWidth
              error={Boolean(draft.occurredOn.length > 3 && !parseJalaliDate(draft.occurredOn))}
              helperText={draft.occurredOn.length > 3 && !parseJalaliDate(draft.occurredOn) ? 'قالب تاریخ نامعتبر است' : 'تقویم خورشیدی و انتخاب ساعت/دقیقه'}
            />
          </Box>
          <TextField
            label="نویسنده / رابط فرهنگی گزارش"
            value={draft.author}
            onChange={event => update({ author: event.target.value })}
            fullWidth
            placeholder="مثال: روابط عمومی دادگستری بابل / مهدوی"
            helperText="نام رابط فرهنگی یا ارسال‌کننده پیام در ایتا"
            sx={{ flex: 1 }}
          />
        </Stack>

        <Box sx={{ p: 1.5, bgcolor: 'background.paper', borderRadius: 2, border: 1, borderColor: 'divider' }}>
          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5} alignItems="center">
            <Autocomplete
              freeSolo
              options={judicialUnits}
              getOptionLabel={option => (typeof option === 'string' ? option : option.display_name || option.name)}
              groupBy={option => (typeof option === 'string' ? 'سایر' : (option.county || 'واحدهای استانی'))}
              value={draft.unit_name}
              onChange={(_, val) => {
                if (typeof val === 'string') {
                  const isHq = val.includes('اداره کل') || val.includes('ستاد')
                  update({
                    unit_name: val,
                    unit: isHq ? 'provincial_hq' : 'judicial_domain',
                  })
                } else if (val) {
                  update({
                    unit_name: val.display_name || val.name,
                    unit: val.kind === 'provincial_hq' ? 'provincial_hq' : 'judicial_domain',
                  })
                } else {
                  update({ unit_name: '', unit: 'judicial_domain' })
                }
              }}
              onInputChange={(_, val) => {
                const isHq = val.includes('اداره کل') || val.includes('ستاد')
                update({
                  unit_name: val,
                  unit: isHq ? 'provincial_hq' : 'judicial_domain',
                })
              }}
              renderInput={params => (
                <TextField
                  {...params}
                  label="حوزه قضایی / واحد سازمانی (انتخابی با قابلیت سرچ)"
                  placeholder="جستجو یا انتخاب: مثال: ساری - اداره کل، ساری - دادسرا، نور - دادگستری..."
                  required
                  fullWidth
                  helperText="حوزه‌های دارای چند واحد به‌صورت چندگانه (شهرستان - واحد) دسته‌بندی شده‌اند"
                />
              )}
              sx={{ flex: 1 }}
            />
            <Button
              variant="outlined"
              color="primary"
              startIcon={<AccountBalanceRounded />}
              onClick={() => setUnitsModalOpen(true)}
              sx={{ height: 48, whiteSpace: 'nowrap', minWidth: 'fit-content' }}
            >
              مدیریت حوزه‌ها و رابطین
            </Button>
          </Stack>
        </Box>

        <TextField label="توضیحات تکمیلی (متن گزارش)" value={draft.notes} onChange={event => update({ notes: event.target.value })} multiline minRows={3} fullWidth />
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
        <Typography variant="subtitle2" fontWeight={800}>خلاصهٔ اطلاعات و ارزیابی اولیه کیفیت پرونده</Typography>
        <Typography variant="body2">
          دسته‌بندی کلان: <strong>{draft.macroCategory === 'workbook_approved' ? 'برنامه مصوب سازمانی (شیت‌های ۸ گانه)' : `سایر برنامه‌های فرهنگی ${draft.customTopic ? `(${draft.customTopic})` : ''}`}</strong>
        </Typography>
        <Typography variant="body2">موضوع: {draft.topic || '—'}</Typography>
        <Typography variant="body2">نویسنده / رابط گزارش: <strong>{draft.author || '—'}</strong></Typography>
        <Typography variant="body2">تاریخ وقوع: <strong>{draft.occurredOn || '—'}</strong> (جلالی)</Typography>
        <Typography variant="body2">حوزه و واحد: <strong>{draft.unit === 'provincial_hq' ? 'ستاد استانی' : 'حوزهٔ قضایی'}{draft.unit_name ? ` (${draft.unit_name})` : ''}</strong></Typography>
        <Typography variant="body2">برنامه‌ها: {draft.programKinds.join('، ') || '—'}</Typography>
        <Typography variant="body2">تعداد فکت‌ها: {draft.facts.length}</Typography>
        <Typography variant="body2">شاهدان: {draft.witnesses.filter(w => w.message_id.trim()).length} مورد ({draft.witnesses.filter(w => w.role === 'primary').length} اصلی، {draft.witnesses.filter(w => w.role === 'supporting').length} پشتیبان)</Typography>

        {draft.witnesses.filter(w => w.message_id.trim()).length === 0 && (
          <Alert severity="error">
            عدم پیوند به شاهد: هنوز هیچ پیام معتبری به عنوان شاهد ثبت نشده است.
          </Alert>
        )}
        {draft.programKinds.some(k => ['ceremony', 'contest', 'quran_contest', 'trip'].includes(k)) &&
          !draft.facts.some(f => f.metric === 'attendees' && Number(f.value) > 0) && (
          <Alert severity="warning">
            توجه کیفی: برای این برنامهٔ جمعی، فکت تعداد مخاطبان ثبت نشده است.
          </Alert>
        )}
        {!draft.unit_name.trim() && draft.unit !== 'provincial_hq' && (
          <Alert severity="info">
            راهنمای ماده ۲۳: پیشنهاد می‌شود نام حوزه یا واحد قضایی میزبان تکمیل شود.
          </Alert>
        )}

        <Alert severity="info">ثبت اولیه جهت بررسی سرپرست ارسال خواهد شد و در کارنامهٔ ثبت عملکرد شما درج می‌گردد.</Alert>
        <Button variant="contained" onClick={() => void submit()} disabled={submitting}>ثبت رویداد و ارسال جهت بررسی</Button>
      </Stack>}

      {results && <Stack spacing={1.5} sx={{ maxWidth: 640, mx: 'auto' }}>
        <Alert severity="success">رویداد {results.eventId} با موفقیت ثبت شد و جهت بازبینی به کارتابل سرپرست ارسال گردید.</Alert>
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
    {unitsModalOpen && (
      <JudicialUnitsManagementModal
        open={unitsModalOpen}
        onClose={() => setUnitsModalOpen(false)}
        onDataChanged={() => loadJudicialUnits()}
      />
    )}
  </Dialog>
}
