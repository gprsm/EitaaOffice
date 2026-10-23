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
  FormControlLabel,
  IconButton,
  MenuItem,
  Stack,
  Step,
  StepLabel,
  Stepper,
  Switch,
  Paper,
  TextField,
  Typography,
} from '@mui/material'
import CloseRounded from '@mui/icons-material/CloseRounded'
import AddRounded from '@mui/icons-material/AddRounded'
import DeleteOutlineRounded from '@mui/icons-material/DeleteOutlineRounded'
import AccountBalanceRounded from '@mui/icons-material/AccountBalanceRounded'
import AssignmentTurnedInRounded from '@mui/icons-material/AssignmentTurnedInRounded'
import VisibilityRounded from '@mui/icons-material/VisibilityRounded'
import CheckCircleRounded from '@mui/icons-material/CheckCircleRounded'
import AssessmentRounded from '@mui/icons-material/AssessmentRounded'
import { api } from './lib/api'
import { jalaliDayKey, jalaliDayLabel, parseJalaliDate } from './utils/helpers'
import { JalaliDatePicker } from './components/JalaliDatePicker'
import { JudicialUnitsManagementModal, JudicialUnitItem, LiaisonItem } from './components/JudicialUnitsManagementModal'
import { useAppUser } from './AppUserGate'
import type { DialogItem, MessageItem } from './lib/types'
import { authorLabel } from './MessageContentCard'
import {
  MACRO_INDICATORS,
  type MicroIndicatorItem,
  type ProgramCatalogItem,
  fetchMicroIndicators,
  fetchProgramCatalog,
} from './lib/indicators'

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
  'احسانی': { unit: 'judicial_domain', unit_name: 'دادگستری بابل', canonicalAuthor: 'احسانی (رابط فرهنگی بابل)' },
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

  // If author is generic, inspect SENDER_BINDINGS strictly against sender peer title or username (NEVER message text!)
  if (isGenericAuthor) {
    const senderIdentity = `${dialog?.peer?.title || ''} ${primaryMsg?.sender_username || ''}`
    for (const [senderKey, binding] of Object.entries(SENDER_BINDINGS)) {
      if (senderIdentity.includes(senderKey) && binding.canonicalAuthor) {
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

  // First check sender bindings strictly against author or peer title (NEVER against arbitrary words in combinedText)
  for (const [senderName, binding] of Object.entries(SENDER_BINDINGS)) {
    if (author.includes(senderName) || (dialog?.peer?.title && dialog.peer.title.includes(senderName))) {
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

  // 5. Official Presence detection
  const officialPresent = /رئیس( کل)? دادگستری|دادستان|معاون قضایی|رئیس دادگاه|مدیرکل/i.test(combinedText)

  return {
    occurredOn,
    sourceTimeFormatted,
    author: author === 'نویسنده نامشخص' ? '' : author,
    unit,
    unit_name,
    topic,
    notes: combinedText,
    officialPresent,
  }
}

const EMPTY: RegistrationDraft = {
  macroCategory: 'workbook_approved', customTopic: '',
  macroIndicator: '', microIndicators: [],
  topic: '', author: '', notes: '', occurredOn: '', unit: 'provincial_hq', unit_name: '',
  programKinds: [], witnesses: [], facts: [],
  officialPresent: false,
}

const STEPS = ['موضوع و شناسنامه', 'سرفصل برنامه و آمار عددی', 'شاهدان ایتا', 'بازبینی و ثبت']

const COMMON_METRICS = [
  { metric: 'attendees', label: 'تعداد کل شرکت‌کنندگان', unit: 'نفر', type: 'integer' },
  { metric: 'trip_type_staff', label: 'تعداد همکاران (پرسنل)', unit: 'نفر', type: 'integer' },
  { metric: 'trip_type_family', label: 'تعداد اعضای خانواده', unit: 'نفر', type: 'integer' },
  { metric: 'survey', label: 'نمره نظرسنجی اثربخشی', unit: 'نمره', type: 'decimal' },
  { metric: 'honored_count', label: 'تعداد افراد تقدیرشده', unit: 'نفر', type: 'integer' },
]

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
  officialPresent: boolean
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
  onOpenEventDossier?: (eventId: string) => void
  onOpenCartable?: () => void
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
  const [programCatalog, setProgramCatalog] = useState<ProgramCatalogItem[]>([])
  const [unitsModalOpen, setUnitsModalOpen] = useState(false)
  const dirtyRef = useRef(false)
  const userEditedAuthorRef = useRef(false)
  const userEditedUnitRef = useRef(false)
  const resolvedMsgKeyRef = useRef<string>('')

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
    void fetchProgramCatalog({ include_inactive: false }).then(progs => {
      if (progs && progs.length > 0) {
        setProgramCatalog(progs)
      }
    })
  }, [loadJudicialUnits])

  // Resolve liaison and unit from backend registry automatically (only once per unique message)
  useEffect(() => {
    const primaryMsg = props.sourceMessage || (props.sourceMessages && props.sourceMessages.length ? props.sourceMessages[0] : null)
    const msgKey = `${primaryMsg?.id || ''}_${props.dialog?.peer?.id || ''}`
    if (!msgKey || msgKey === '_' || resolvedMsgKeyRef.current === msgKey) return
    resolvedMsgKeyRef.current = msgKey

    let isMounted = true
    const resolveSenderAndUnit = async () => {
      try {
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
        if (!isMounted) return

        if (res.matched) {
          setDraft(current => {
            const nextAuthor = !userEditedAuthorRef.current && res.liaison?.full_name ? res.liaison.full_name : current.author
            const nextUnitName = !userEditedUnitRef.current && res.unit?.display_name ? res.unit.display_name : current.unit_name
            const nextUnit = !userEditedUnitRef.current && res.unit?.kind ? (res.unit.kind === 'provincial_hq' ? 'provincial_hq' : 'judicial_domain') : current.unit
            return {
              ...current,
              unit_name: nextUnitName,
              unit: nextUnit as any,
              author: nextAuthor,
            }
          })
        }
      } catch (err) {
        console.warn('Auto resolve liaison warning:', err)
      }
    }
    void resolveSenderAndUnit()
    return () => { isMounted = false }
  }, [props.sourceMessage?.id, props.dialog?.peer?.id])

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

  // Auto-sync programKinds if user picked a macroIndicator and programKinds is empty
  useEffect(() => {
    if (draft.macroIndicator && (!draft.programKinds || draft.programKinds.length === 0) && programCatalog.length > 0) {
      const matchedProg = programCatalog.find(p => (p.canonical_macro || p.title) === draft.macroIndicator)
      if (matchedProg?.kind) {
        setDraft(d => ({ ...d, programKinds: [matchedProg.kind] }))
      } else if (draft.macroIndicator === 'غیر برنامه‌ای') {
        setDraft(d => ({ ...d, programKinds: ['non_programmatic'] }))
      }
    }
  }, [draft.macroIndicator, programCatalog])

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

      let effectiveProgramKinds = draft.programKinds
      if (!effectiveProgramKinds || effectiveProgramKinds.length === 0) {
        const matched = programCatalog.find(p => (p.canonical_macro || p.title) === draft.macroIndicator)
        if (matched?.kind) {
          effectiveProgramKinds = [matched.kind]
        } else if (draft.macroCategory === 'other_cultural' || draft.macroIndicator === 'غیر برنامه‌ای') {
          effectiveProgramKinds = ['non_programmatic']
        }
      }

      const created = await api<{ ok?: boolean; event_id: string; etag: string }>('POST', '/api/v3/reporting/events', {
        macro_category: draft.macroCategory,
        custom_topic: draft.customTopic,
        macro_indicator: draft.macroIndicator,
        micro_indicators: draft.microIndicators,
        program_kinds: effectiveProgramKinds && effectiveProgramKinds.length > 0 ? effectiveProgramKinds : undefined,
        occurred_on: iso,
        unit: draft.unit,
        unit_name: draft.unit_name,
        official_present: draft.officialPresent ? 1 : 0,
        occasion: draft.topic.trim(),
        topic: draft.topic.trim(),
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
              onChange={event => {
                const val = event.target.value
                const matchedProg = programCatalog.find(p => (p.canonical_macro || p.title) === val)
                update({
                  macroIndicator: val,
                  programKinds: matchedProg ? [matchedProg.kind] : (val === 'غیر برنامه‌ای' ? ['non_programmatic'] : draft.programKinds),
                })
              }}
              fullWidth
              helperText="انتخاب از بین ۸ برنامه مصوب یا عنوان «غیر برنامه‌ای»"
            >
              <MenuItem value="">
                <em>(تعیین‌نشده)</em>
              </MenuItem>
              {(programCatalog.length > 0 ? Array.from(new Set(programCatalog.map(p => p.canonical_macro || p.title))) : MACRO_INDICATORS).map(ind => (
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
            <JalaliDatePicker
              value={draft.occurredOn}
              onChange={val => update({ occurredOn: val })}
              label="تاریخ برگزاری رویداد (شمسی)"
              required
              fullWidth
              size="small"
              helperText="تقویم خورشیدی و درج تاریخ وقوع فعالیت فرهنگی"
            />
          </Box>
          <TextField
            label="نویسنده / رابط فرهنگی گزارش"
            value={draft.author}
            onChange={event => {
              userEditedAuthorRef.current = true
              update({ author: event.target.value })
            }}
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
                userEditedUnitRef.current = true
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
                userEditedUnitRef.current = true
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

      {step === 1 && <Stack spacing={2.5} sx={{ maxWidth: 720, mx: 'auto' }}>
        {/* ۱. سرفصل برنامه‌های مصوب مرتبط */}
        <Box sx={{ p: 2, bgcolor: 'background.paper', borderRadius: 2, border: 1, borderColor: 'divider' }}>
          <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1.5 }}>
            <AssessmentRounded color="primary" fontSize="small" />
            <Typography variant="subtitle2" fontWeight={800}>
              سرفصل‌های مصوب مرتبط با گزارش
            </Typography>
          </Stack>

          {draft.macroIndicator ? (
            <Alert severity="info" sx={{ mb: 2, py: 0.5, '& .MuiAlert-message': { fontSize: '0.82rem' } }}>
              سرفصل متناظر با شاخصهٔ کلی انتخابی شما در مرحلهٔ اول (<strong>{draft.macroIndicator}</strong>) به صورت پیش‌فرض فعال و تأیید شده است. در صورتی که این گزارش مشترکاً به چند برنامه مربوط است، می‌توانید سرفصل‌های مکمل دیگر را نیز انتخاب یا لغو نمایید:
            </Alert>
          ) : (
            <Alert severity="warning" sx={{ mb: 2, py: 0.5, '& .MuiAlert-message': { fontSize: '0.82rem' } }}>
              لطفاً حداقل یک سرفصل برنامهٔ مصوب مرتبط با این رویداد را انتخاب نمایید:
            </Alert>
          )}

          <Stack direction="row" flexWrap="wrap" gap={1}>
            {programCatalog.length > 0 ? (
              programCatalog.map(prog => {
                const selected = draft.programKinds.includes(prog.kind) || draft.programKinds.includes(prog.program_code)
                return (
                  <Chip
                    key={prog.program_code}
                    icon={selected ? <CheckCircleRounded sx={{ fontSize: '18px !important', color: 'primary.contrastText !important' }} /> : undefined}
                    label={`${prog.program_code} · ${prog.title}`}
                    color={selected ? 'primary' : 'default'}
                    variant={selected ? 'filled' : 'outlined'}
                    onClick={() => {
                      const newKinds = selected
                        ? draft.programKinds.filter(v => v !== prog.kind && v !== prog.program_code)
                        : [...draft.programKinds, prog.kind]
                      update({
                        programKinds: newKinds,
                        macroIndicator: !selected && !draft.macroIndicator ? (prog.canonical_macro || prog.title) : draft.macroIndicator,
                      })
                    }}
                    sx={{
                      fontWeight: selected ? 800 : 500,
                      px: 0.75,
                      py: 2.2,
                      borderRadius: 2,
                      cursor: 'pointer',
                      transition: 'all 0.15s ease',
                      bgcolor: selected ? 'primary.main' : 'action.hover',
                      color: selected ? 'primary.contrastText' : 'text.primary',
                      border: '1.5px solid',
                      borderColor: selected ? 'primary.main' : 'divider',
                      boxShadow: selected ? '0 2px 8px rgba(37, 99, 235, 0.35)' : 'none',
                      '&:hover': {
                        bgcolor: selected ? 'primary.dark' : 'action.selected',
                        borderColor: 'primary.main',
                      },
                    }}
                  />
                )
              })
            ) : (
              PROGRAM_KINDS.map(kind => {
                const selected = draft.programKinds.includes(kind.value)
                return (
                  <Chip
                    key={kind.value}
                    icon={selected ? <CheckCircleRounded sx={{ fontSize: '18px !important', color: 'primary.contrastText !important' }} /> : undefined}
                    label={kind.label}
                    color={selected ? 'primary' : 'default'}
                    variant={selected ? 'filled' : 'outlined'}
                    onClick={() => update({ programKinds: selected ? draft.programKinds.filter(v => v !== kind.value) : [...draft.programKinds, kind.value] })}
                    sx={{
                      fontWeight: selected ? 800 : 500,
                      px: 0.75,
                      py: 2.2,
                      borderRadius: 2,
                      bgcolor: selected ? 'primary.main' : 'action.hover',
                      color: selected ? 'primary.contrastText' : 'text.primary',
                      border: '1.5px solid',
                      borderColor: selected ? 'primary.main' : 'divider',
                    }}
                  />
                )
              })
            )}
          </Stack>
        </Box>

        {/* حضور مقام عالی قضایی (قاعده B9/C8 برای تکریم و تجلیل و تشویق ارباب رجوع) */}
        <Box sx={{ p: 2, bgcolor: 'background.paper', borderRadius: 2, border: 1, borderColor: 'divider' }}>
          <FormControlLabel
            control={
              <Switch
                checked={draft.officialPresent}
                onChange={e => update({ officialPresent: e.target.checked })}
                color="success"
              />
            }
            label={
              <Box>
                <Typography variant="subtitle2" fontWeight={800}>
                  حضور رئیس‌کل دادگستری یا بالاترین مقام قضایی استان / شهرستان
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  مطابق ضوابط کاربرگ‌های «تکریم و تجلیل» و «تشویق ارباب رجوع»، احراز حضور مقام قضایی جهت تأیید و تجمیع رسمی آمار الزامی است.
                </Typography>
              </Box>
            }
          />
        </Box>

        {/* ۲. آمار، سنجه‌ها و ارقام عددی رویداد */}
        <Box sx={{ p: 2, bgcolor: 'background.paper', borderRadius: 2, border: 1, borderColor: 'divider' }}>
          <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 1 }}>
            <Typography variant="subtitle2" fontWeight={800}>
              آمار و سنجه‌های عددی رویداد (اختیاری)
            </Typography>
            <Typography variant="caption" color="text.secondary">
              جهت محاسبه خودکار در کاربرگ‌ها و داشبوردها
            </Typography>
          </Stack>

          <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1.5 }}>
            با کلیک روی گزینه‌های زیر، سنجه‌های پرکاربرد فوراً افزوده می‌شوند (یا می‌توانید با دکمه انتهای بخش سنجهٔ دستی اضافه کنید):
          </Typography>

          {/* Quick presets */}
          <Stack direction="row" flexWrap="wrap" gap={0.75} sx={{ mb: 2 }}>
            {COMMON_METRICS.map(m => {
              const alreadyAdded = draft.facts.some(f => f.metric === m.metric)
              return (
                <Chip
                  key={m.metric}
                  label={alreadyAdded ? `✓ ${m.label}` : `+ ${m.label}`}
                  size="small"
                  color={alreadyAdded ? 'success' : 'default'}
                  variant={alreadyAdded ? 'filled' : 'outlined'}
                  onClick={() => {
                    if (!alreadyAdded) {
                      update({
                        facts: [
                          ...draft.facts,
                          { metric: m.metric, value: '', unit_of_measure: m.unit, value_type: m.type },
                        ],
                      })
                    }
                  }}
                  sx={{
                    fontWeight: 600,
                    fontSize: '0.75rem',
                    cursor: alreadyAdded ? 'default' : 'pointer',
                  }}
                />
              )
            })}
          </Stack>

          <Stack spacing={1.5}>
            {draft.facts.map((fact, index) => {
              const preset = COMMON_METRICS.find(m => m.metric === fact.metric)
              return (
                <Paper
                  key={index}
                  variant="outlined"
                  sx={{ p: 1.5, borderRadius: 1.5, bgcolor: 'action.hover' }}
                >
                  <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1} alignItems="center">
                    <TextField
                      size="small"
                      label="عنوان سنجه / شاخص"
                      value={fact.metric}
                      helperText={preset ? preset.label : undefined}
                      onChange={event =>
                        update({
                          facts: draft.facts.map((f, i) =>
                            i === index ? { ...f, metric: event.target.value } : f,
                          ),
                        })
                      }
                      sx={{ flex: 2 }}
                    />
                    <TextField
                      size="small"
                      label="مقدار عددی"
                      type="number"
                      value={fact.value}
                      placeholder="مثال: ۵۰"
                      onChange={event =>
                        update({
                          facts: draft.facts.map((f, i) =>
                            i === index ? { ...f, value: event.target.value } : f,
                          ),
                        })
                      }
                      sx={{ flex: 1.2 }}
                      dir="ltr"
                    />
                    <TextField
                      size="small"
                      label="واحد سنجش"
                      value={fact.unit_of_measure}
                      placeholder="نفر / عدد / نمره"
                      onChange={event =>
                        update({
                          facts: draft.facts.map((f, i) =>
                            i === index ? { ...f, unit_of_measure: event.target.value } : f,
                          ),
                        })
                      }
                      sx={{ flex: 1 }}
                    />
                    <IconButton
                      aria-label="حذف سنجه"
                      color="error"
                      size="small"
                      onClick={() => update({ facts: draft.facts.filter((_, i) => i !== index) })}
                    >
                      <DeleteOutlineRounded />
                    </IconButton>
                  </Stack>
                </Paper>
              )
            })}
            <Button
              variant="text"
              size="small"
              startIcon={<AddRounded />}
              onClick={() =>
                update({
                  facts: [
                    ...draft.facts,
                    { metric: '', value: '', unit_of_measure: 'نفر', value_type: 'integer' },
                  ],
                })
              }
              sx={{ alignSelf: 'flex-start' }}
            >
              افزودن سنجهٔ سفارشی دیگر
            </Button>
          </Stack>
        </Box>
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
        <Typography variant="body2">آمار و سنجه‌های ثبت‌شده: <strong>{draft.facts.length > 0 ? `${draft.facts.length} شاخص عددی (${draft.facts.map(f => `${f.metric}: ${f.value} ${f.unit_of_measure}`).join('، ')})` : 'ثبت نشده (اختیاری)'}</strong></Typography>
        <Typography variant="body2">شاهدان: {draft.witnesses.filter(w => w.message_id.trim()).length} مورد ({draft.witnesses.filter(w => w.role === 'primary').length} اصلی، {draft.witnesses.filter(w => w.role === 'supporting').length} پشتیبان)</Typography>

        {draft.witnesses.filter(w => w.message_id.trim()).length === 0 && (
          <Alert severity="error">
            عدم پیوند به شاهد: هنوز هیچ پیام معتبری به عنوان شاهد ثبت نشده است.
          </Alert>
        )}
        {draft.programKinds.some(k => ['ceremony', 'contest', 'quran_contest', 'trip'].includes(k)) &&
          !draft.facts.some(f => f.metric === 'attendees' && Number(f.value) > 0) && (
          <Alert severity="warning">
            توجه کیفی: برای این برنامهٔ جمعی، سنجهٔ تعداد مخاطبان / شرکت‌کنندگان ثبت نشده است.
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
        <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1} sx={{ mt: 1 }}>
          {props.onOpenEventDossier && (
            <Button
              variant="contained"
              color="secondary"
              startIcon={<VisibilityRounded />}
              onClick={() => {
                props.onOpenEventDossier?.(results.eventId)
              }}
              sx={{ flex: 1 }}
            >
              مشاهده و تکمیل پوشه پرونده رویداد
            </Button>
          )}
          {props.onOpenCartable && (
            <Button
              variant="outlined"
              color="primary"
              startIcon={<AssignmentTurnedInRounded />}
              onClick={() => {
                props.onOpenCartable?.()
              }}
              sx={{ flex: 1 }}
            >
              مشاهده در کارتابل و آرشیو گزارش‌ها
            </Button>
          )}
        </Stack>
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
