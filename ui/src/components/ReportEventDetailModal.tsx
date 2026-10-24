import React, { useEffect, useMemo, useState } from 'react'
import {
  Alert,
  Autocomplete,
  Avatar,
  Box,
  Button,
  Card,
  CardActionArea,
  CardContent,
  CardMedia,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  FormControl,
  FormControlLabel,
  Grid,
  IconButton,
  InputAdornment,
  InputLabel,
  MenuItem,
  Paper,
  Select,
  Stack,
  Switch,
  Tab,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Tabs,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material'
import CloseRounded from '@mui/icons-material/CloseRounded'
import SaveRounded from '@mui/icons-material/SaveRounded'
import CheckCircleOutlineRounded from '@mui/icons-material/CheckCircleOutlineRounded'
import WarningAmberRounded from '@mui/icons-material/WarningAmberRounded'
import ErrorOutlineRounded from '@mui/icons-material/ErrorOutlineRounded'
import AssignmentTurnedInRounded from '@mui/icons-material/AssignmentTurnedInRounded'
import SendRounded from '@mui/icons-material/SendRounded'
import BlockRounded from '@mui/icons-material/BlockRounded'
import RefreshRounded from '@mui/icons-material/RefreshRounded'
import LabelOutlined from '@mui/icons-material/LabelOutlined'
import EventNoteRounded from '@mui/icons-material/EventNoteRounded'
import AccountBalanceRounded from '@mui/icons-material/AccountBalanceRounded'
import LayersRounded from '@mui/icons-material/LayersRounded'
import DeleteOutlineRounded from '@mui/icons-material/DeleteOutlineRounded'
import PhotoLibraryRounded from '@mui/icons-material/PhotoLibraryRounded'
import CloudUploadRounded from '@mui/icons-material/CloudUploadRounded'
import InsertDriveFileRounded from '@mui/icons-material/InsertDriveFileRounded'
import StarRounded from '@mui/icons-material/StarRounded'
import StarOutlineRounded from '@mui/icons-material/StarOutlineRounded'
import CallMergeRounded from '@mui/icons-material/CallMergeRounded'
import AnalyticsRounded from '@mui/icons-material/AnalyticsRounded'
import AssessmentRounded from '@mui/icons-material/AssessmentRounded'
import DownloadRounded from '@mui/icons-material/DownloadRounded'
import AddRounded from '@mui/icons-material/AddRounded'
import CheckRounded from '@mui/icons-material/CheckRounded'
import DeleteForeverRounded from '@mui/icons-material/DeleteForeverRounded'
import PictureAsPdfRounded from '@mui/icons-material/PictureAsPdfRounded'
import TableChartRounded from '@mui/icons-material/TableChartRounded'
import DescriptionRounded from '@mui/icons-material/DescriptionRounded'
import VisibilityRounded from '@mui/icons-material/VisibilityRounded'

import { api } from '../lib/api'
import { toast } from '../MaterialToast'
import {
  fetchMacroIndicators,
  fetchMicroIndicators,
  fetchProgramCatalog,
  type MicroIndicatorItem,
  type ProgramCatalogItem,
} from '../lib/indicators'
import { JalaliDatePicker } from './JalaliDatePicker'
import { toPersianDigits } from '../utils/jalaliDateTime'

export const METRIC_LABELS: Record<string, string> = {
  honored_count: 'تعداد کل افراد تقدیرشده',
  honorees: 'تعداد افراد تجلیل‌شده',
  honoree_count: 'تعداد افراد تقدیرشده',
  honor_legends: 'تکریم مفاخر و نخبگان',
  honor_retirees: 'تکریم بازنشستگان',
  honor_veterans: 'تکریم ایثارگران و جانبازان',
  honor_prayer_servants: 'تجلیل از خادمان نماز',
  honor_special: 'تقدیر ویژه / مناسبتی',
  trip_type_staff: 'تعداد همکاران (پرسنل)',
  trip_type_family: 'تعداد اعضای خانواده',
  trip_count: 'تعداد اردوها / سفرها',
  session_count: 'تعداد جلسات / نوبت‌ها',
  duration_hours: 'مدت زمان برگزاری (ساعت)',
  duration_minutes: 'مدت زمان (دقیقه)',
  survey: 'نمره نظرسنجی اثربخشی',
  survey_score: 'نمره نظرسنجی',
  survey_respondents: 'تعداد پاسخ‌دهندگان نظرسنجی',
  survey_satisfaction: 'درصد رضایت نظرسنجی',
  attendees: 'تعداد شرکت‌کنندگان / مخاطبان',
  attendee_count: 'تعداد مخاطبان',
  participants_count: 'تعداد شرکت‌کنندگان',
  quran_attendees: 'تعداد شرکت‌کنندگان قرآنی',
  contest_count: 'تعداد مسابقات برگزارشده',
  prayer_count: 'تعداد اقامه نماز جماعت',
  reception: 'پذیرایی / میان‌وعده',
  reception_cost: 'هزینه پذیرایی',
  announcement: 'اطلاع‌رسانی قبلی / پوستر',
  gifts: 'اهدای جوایز / هدایا',
  exhibition_booths: 'تعداد غرفه‌های نمایشگاهی',
  consultation_sessions: 'تعداد جلسات مشاوره',
  charity_beneficiaries: 'تعداد بهره‌مندان کمک‌های مومنانه',
  financial_docs_present: 'مستندات مالی موجود',
}

export interface ReportEventDetailModalProps {
  open: boolean
  eventId: string | null
  onClose: () => void
  onSaved?: () => void
}

const UNIT_SCOPES: Array<{ value: string; label: string }> = [
  { value: 'provincial_hq', label: 'ستاد دادگستری کل استان' },
  { value: 'courthouse', label: 'دادگستری / حوزه قضایی شهرستان' },
  { value: 'special_council', label: 'شورای حل اختلاف' },
  { value: 'province_wide', label: 'استانی / مشترک' },
]

function b64toBlob(b64Data: string, contentType = '', sliceSize = 512): Blob {
  const byteCharacters = atob(b64Data)
  const byteArrays = []
  for (let offset = 0; offset < byteCharacters.length; offset += sliceSize) {
    const slice = byteCharacters.slice(offset, offset + sliceSize)
    const byteNumbers = new Array(slice.length)
    for (let i = 0; i < slice.length; i++) {
      byteNumbers[i] = slice.charCodeAt(i)
    }
    byteArrays.push(new Uint8Array(byteNumbers))
  }
  return new Blob(byteArrays, { type: contentType })
}

function getInitialOccasion(ev: Record<string, any> | null): string {
  if (!ev) return ''
  let occ = (ev.occasion || ev.custom_topic || '').trim()
  if (!occ && ev.notes) {
    const cleanNotes = ev.notes.replace(/^نویسنده[^\n]*\n?/, '').trim()
    const firstLine = cleanNotes.split('\n')[0]?.trim()
    if (firstLine && firstLine.length > 2) {
      occ = firstLine.slice(0, 120)
    }
  }
  return occ
}

export function ReportEventDetailModal({
  open,
  eventId,
  onClose,
  onSaved,
}: ReportEventDetailModalProps) {
  const [activeTab, setActiveTab] = useState<number>(0)
  const [loading, setLoading] = useState<boolean>(false)
  const [saving, setSaving] = useState<boolean>(false)
  const [actionLoading, setActionLoading] = useState<boolean>(false)
  const [errorText, setErrorText] = useState<string>('')

  // Raw fetched event & relations
  const [rawEvent, setRawEvent] = useState<Record<string, any> | null>(null)
  const [auditRecords, setAuditRecords] = useState<any[]>([])
  const [normalization, setNormalization] = useState<Record<string, any> | null>(null)
  const [mergeCandidates, setMergeCandidates] = useState<any[]>([])
  const [loadingMerge, setLoadingMerge] = useState<boolean>(false)

  // Catalogs
  const [macroOptions, setMacroOptions] = useState<string[]>([])
  const [microOptions, setMicroOptions] = useState<MicroIndicatorItem[]>([])
  const [programsCatalog, setProgramsCatalog] = useState<ProgramCatalogItem[]>([])
  const [judicialUnits, setJudicialUnits] = useState<Array<{ display_name: string; name: string }>>([])

  // Editable fields
  const [occasion, setOccasion] = useState<string>('')
  const [macroCategory, setMacroCategory] = useState<string>('workbook_approved')
  const [customTopic, setCustomTopic] = useState<string>('')
  const [macroIndicator, setMacroIndicator] = useState<string>('')
  const [microIndicators, setMicroIndicators] = useState<string[]>([])
  const [newMicroTag, setNewMicroTag] = useState<string>('')
  const [selectedPrograms, setSelectedPrograms] = useState<string[]>([])
  const [unitScope, setUnitScope] = useState<string>('provincial_hq')
  const [unitName, setUnitName] = useState<string>('')
  const [occurredOn, setOccurredOn] = useState<string>('')
  const [officialPresent, setOfficialPresent] = useState<boolean>(false)
  const [isAshuraPilgrimage, setIsAshuraPilgrimage] = useState<boolean>(false)
  const [notes, setNotes] = useState<string>('')

  // Facts & metrics
  const [facts, setFacts] = useState<Array<{ metric: string; value: number; unit_of_measure: string; note: string }>>([])
  const [viewingProgramKind, setViewingProgramKind] = useState<string>('')
  const [newCustomFactMetric, setNewCustomFactMetric] = useState<string>('')
  const [newCustomFactValue, setNewCustomFactValue] = useState<string>('')
  const [newCustomFactUnit, setNewCustomFactUnit] = useState<string>('نفر')

  // Document upload state
  const [uploadingDoc, setUploadingDoc] = useState<boolean>(false)
  const [uploadKind, setUploadKind] = useState<string>('image')
  const [uploadIsCover, setUploadIsCover] = useState<boolean>(false)

  // Delete event confirmation modal
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState<boolean>(false)

  // Image Lightbox Preview
  const [previewImageDoc, setPreviewImageDoc] = useState<{ url: string; title: string } | null>(null)

  // Load catalogs once
  useEffect(() => {
    let active = true
    async function loadCatalogs() {
      try {
        const [macros, micros, progs, unitsRes] = await Promise.all([
          fetchMacroIndicators(),
          fetchMicroIndicators(),
          fetchProgramCatalog({ include_inactive: true }),
          api<{ units: Array<{ display_name: string; name: string }> }>('GET', '/api/v3/reporting/units').catch(
            () => ({ units: [] }),
          ),
        ])
        if (active) {
          setMacroOptions(macros)
          setMicroOptions(micros)
          setProgramsCatalog(progs)
          setJudicialUnits(unitsRes.units || [])
        }
      } catch (err) {
        console.error('Error loading catalogs in detail modal:', err)
      }
    }
    if (open) {
      loadCatalogs()
    }
    return () => {
      active = false
    }
  }, [open])

  // Fetch event details
  const fetchEventData = async (id: string, options?: { silent?: boolean; syncFields?: boolean }) => {
    try {
      if (!options?.silent) {
        setLoading(true)
      }
      setErrorText('')
      const [res, auditRes, normRes] = await Promise.all([
        api<{ ok: boolean; event: Record<string, any> }>('GET', `/api/v3/reporting/events/${encodeURIComponent(id)}`),
        api<{ ok: boolean; audit: any[] }>('GET', `/api/v3/reporting/events/${encodeURIComponent(id)}/audit`).catch(() => ({ ok: true, audit: [] })),
        api<Record<string, any>>('GET', `/api/v3/reporting/events/${encodeURIComponent(id)}/normalization`).catch(() => null),
      ])

      const ev = res.event || {}
      setRawEvent(ev)
      setAuditRecords(auditRes.audit || [])
      setNormalization(normRes)

      if (!options?.silent || options?.syncFields) {
        setOccasion(getInitialOccasion(ev))
        setMacroCategory(ev.macro_category || 'workbook_approved')
        setCustomTopic(ev.custom_topic || '')
        setMacroIndicator(ev.macro_indicator || '')

        let parsedMicros: string[] = []
        if (Array.isArray(ev.micro_indicators)) {
          parsedMicros = ev.micro_indicators
        } else if (typeof ev.micro_indicators_json === 'string') {
          try {
            parsedMicros = JSON.parse(ev.micro_indicators_json)
          } catch {
            parsedMicros = []
          }
        }
        setMicroIndicators(parsedMicros)

        setSelectedPrograms(Array.isArray(ev.program_kinds) ? ev.program_kinds : [])
        setUnitScope(ev.unit || 'provincial_hq')
        setUnitName(ev.unit_name || '')
        setOccurredOn(ev.occurred_on || '')
        setOfficialPresent(Boolean(ev.official_present))
        const hasAshura = Boolean(ev.is_ashura_pilgrimage)
          || parsedMicros.some((m: string) => typeof m === 'string' && m.includes('عاشورا'))
          || (typeof ev.topic === 'string' && ev.topic.includes('عاشورا'))
          || (typeof ev.notes === 'string' && ev.notes.includes('عاشورا'))
          || (Array.isArray(ev.witnesses) && ev.witnesses.some((w: any) => (w.text || w.message_text || w.note || '').includes('عاشورا')))
        setIsAshuraPilgrimage(hasAshura)
        setNotes(ev.notes || '')

        // Facts
        if (Array.isArray(ev.facts)) {
          setFacts(ev.facts.map((f: any) => ({
            metric: f.metric || '',
            value: typeof f.value === 'number' ? f.value : parseFloat(f.value || 0),
            unit_of_measure: f.unit_of_measure || 'count',
            note: f.note || '',
          })))
        } else {
          setFacts([])
        }
      }
    } catch (err) {
      setErrorText(err instanceof Error ? err.message : 'خطا در بارگذاری اطلاعات پرونده رویداد')
    } finally {
      if (!options?.silent) {
        setLoading(false)
      }
    }
  }

  useEffect(() => {
    if (open && eventId) {
      void fetchEventData(eventId)
      setActiveTab(0)
    } else {
      setRawEvent(null)
      setAuditRecords([])
      setNormalization(null)
      setMergeCandidates([])
    }
  }, [open, eventId])

  // Load merge candidates
  const loadMergeCandidates = async () => {
    if (!eventId) return
    try {
      setLoadingMerge(true)
      const res = await api<{ ok: boolean; candidates: any[] }>(
        'GET',
        `/api/v3/reporting/events/${encodeURIComponent(eventId)}/merge-candidates`,
      )
      setMergeCandidates(res.candidates || [])
    } catch (err) {
      toast.error('خطا در بارگذاری گزارش‌های مشابه جهت ادغام')
    } finally {
      setLoadingMerge(false)
    }
  }

  useEffect(() => {
    if (activeTab === 4 && eventId) {
      void loadMergeCandidates()
    }
  }, [activeTab, eventId])

  // Fact alias mapping
  const FACT_ALIASES: Record<string, string[]> = {
    honored_count: ['honored_count', 'honoree_count', 'honorees'],
    honorees: ['honorees', 'honored_count', 'honoree_count'],
    attendees: ['attendees', 'participants_count', 'quran_attendees', 'attendee_count'],
    participants_count: ['participants_count', 'attendees', 'attendee_count'],
    ceremony_count: ['ceremony_count', 'ceremonies', 'events', 'sessions'],
    trip_count: ['trip_count', 'trips', 'events'],
    contest_count: ['contest_count', 'contests', 'events'],
    prayer_count: ['prayer_count', 'prayers', 'sessions'],
    survey: ['survey', 'survey_score', 'survey_count'],
    reception: ['reception', 'reception_count'],
    announcement: ['announcement', 'announcement_count'],
    gifts: ['gifts', 'gift_count'],
  }

  // Fact helpers
  const getFactValue = (metric: string): number => {
    const aliases = FACT_ALIASES[metric] || [metric]
    const f = facts.find(x => aliases.includes(x.metric))
    return f ? f.value : 0
  }

  const setFactValue = (metric: string, value: number, unit = 'count', note = '') => {
    const aliases = FACT_ALIASES[metric] || [metric]
    setFacts(prev => {
      const idx = prev.findIndex(x => aliases.includes(x.metric))
      if (idx >= 0) {
        const next = [...prev]
        next[idx] = { ...next[idx], metric, value, unit_of_measure: unit, note: note || next[idx].note }
        return next
      } else {
        return [...prev, { metric, value, unit_of_measure: unit, note }]
      }
    })
  }

  const removeFact = (metric: string) => {
    const aliases = FACT_ALIASES[metric] || [metric]
    setFacts(prev => prev.filter(x => !aliases.includes(x.metric) && x.metric !== metric))
  }

  // Micro-indicators tag operations
  const handleAddMicroTag = (title: string) => {
    const trimmed = title.trim()
    if (!trimmed || microIndicators.includes(trimmed)) return
    setMicroIndicators(prev => [...prev, trimmed])
    if (trimmed.includes('عاشورا')) {
      setIsAshuraPilgrimage(true)
    }
    setNewMicroTag('')
  }

  const handleRemoveMicroTag = (title: string) => {
    setMicroIndicators(prev => prev.filter(m => m !== title))
  }

  // Reset / Discard unsaved changes (عدم ذخیره تغییرات)
  const handleResetChanges = () => {
    if (!rawEvent) return
    const ev = rawEvent
    setOccasion(getInitialOccasion(ev))
    setMacroCategory(ev.macro_category || 'workbook_approved')
    setCustomTopic(ev.custom_topic || '')
    setMacroIndicator(ev.macro_indicator || '')

    let parsedMicros: string[] = []
    if (Array.isArray(ev.micro_indicators)) {
      parsedMicros = ev.micro_indicators
    } else if (typeof ev.micro_indicators_json === 'string') {
      try {
        parsedMicros = JSON.parse(ev.micro_indicators_json)
      } catch {
        parsedMicros = []
      }
    }
    setMicroIndicators(parsedMicros)
    setSelectedPrograms(Array.isArray(ev.program_kinds) ? ev.program_kinds : [])
    setUnitScope(ev.unit || 'provincial_hq')
    setUnitName(ev.unit_name || '')
    setOccurredOn(ev.occurred_on || '')
    setOfficialPresent(Boolean(ev.official_present))
    const hasAshura = Boolean(ev.is_ashura_pilgrimage)
      || parsedMicros.some((m: string) => typeof m === 'string' && m.includes('عاشورا'))
      || (typeof ev.topic === 'string' && ev.topic.includes('عاشورا'))
      || (typeof ev.notes === 'string' && ev.notes.includes('عاشورا'))
      || (Array.isArray(ev.witnesses) && ev.witnesses.some((w: any) => (w.text || w.message_text || w.note || '').includes('عاشورا')))
    setIsAshuraPilgrimage(hasAshura)
    setNotes(ev.notes || '')

    if (Array.isArray(ev.facts)) {
      setFacts(
        ev.facts.map((f: any) => ({
          metric: f.metric || '',
          value: typeof f.value === 'number' ? f.value : parseFloat(f.value || 0),
          unit_of_measure: f.unit_of_measure || 'count',
          note: f.note || '',
        })),
      )
    } else {
      setFacts([])
    }
    setErrorText('')
    toast.info('کلیه تغییرات لغو و مقادیر اولیه پرونده از پایگاه داده بازیابی شد.')
  }

  // Calculate dirty state across all editable fields
  const isDirty = useMemo(() => {
    if (!rawEvent) return false
    const origOccasion = getInitialOccasion(rawEvent)
    if (occasion !== origOccasion) return true
    if (macroCategory !== (rawEvent.macro_category || 'workbook_approved')) return true
    if (customTopic !== (rawEvent.custom_topic || '')) return true
    if (macroIndicator !== (rawEvent.macro_indicator || '')) return true
    if (unitScope !== (rawEvent.unit || 'provincial_hq')) return true
    if (unitName !== (rawEvent.unit_name || '')) return true
    if (occurredOn !== (rawEvent.occurred_on || '')) return true
    if (officialPresent !== Boolean(rawEvent.official_present)) return true
    if (isAshuraPilgrimage !== Boolean(rawEvent.is_ashura_pilgrimage)) return true
    if (notes !== (rawEvent.notes || '')) return true

    let origMicros: string[] = []
    if (Array.isArray(rawEvent.micro_indicators)) {
      origMicros = rawEvent.micro_indicators
    } else if (typeof rawEvent.micro_indicators_json === 'string') {
      try {
        origMicros = JSON.parse(rawEvent.micro_indicators_json)
      } catch {
        origMicros = []
      }
    }
    if (JSON.stringify([...microIndicators].sort()) !== JSON.stringify([...origMicros].sort())) return true

    const origPrograms = Array.isArray(rawEvent.program_kinds) ? rawEvent.program_kinds : []
    if (JSON.stringify([...selectedPrograms].sort()) !== JSON.stringify([...origPrograms].sort())) return true

    const origFacts = Array.isArray(rawEvent.facts) ? rawEvent.facts : []
    if (facts.length !== origFacts.length) return true
    for (const f of facts) {
      const orig = origFacts.find((x: any) => x.metric === f.metric)
      if (!orig || (typeof orig.value === 'number' ? orig.value : parseFloat(orig.value || 0)) !== f.value) {
        return true
      }
    }

    return false
  }, [
    rawEvent,
    occasion,
    macroCategory,
    customTopic,
    macroIndicator,
    unitScope,
    unitName,
    occurredOn,
    officialPresent,
    isAshuraPilgrimage,
    notes,
    microIndicators,
    selectedPrograms,
    facts,
  ])

  // Calculate only the fields that have actually changed (Delta / Partial Update)
  const getDirtyFields = (): Record<string, any> => {
    if (!rawEvent) return {}
    const dirty: Record<string, any> = {}

    const origOccasion = getInitialOccasion(rawEvent)
    if (occasion.trim() !== origOccasion.trim()) {
      dirty.occasion = occasion.trim()
    }
    if (macroCategory !== (rawEvent.macro_category || 'workbook_approved')) {
      dirty.macro_category = macroCategory
    }
    if (customTopic.trim() !== (rawEvent.custom_topic || '').trim()) {
      dirty.custom_topic = customTopic.trim()
    }
    if (macroIndicator.trim() !== (rawEvent.macro_indicator || '').trim()) {
      dirty.macro_indicator = macroIndicator.trim()
    }
    if (unitScope !== (rawEvent.unit || 'provincial_hq')) {
      dirty.unit = unitScope
    }
    if (unitName.trim() !== (rawEvent.unit_name || '').trim()) {
      dirty.unit_name = unitName.trim()
    }
    if (occurredOn.trim() !== (rawEvent.occurred_on || '').trim()) {
      dirty.occurred_on = occurredOn.trim()
    }
    if (officialPresent !== Boolean(rawEvent.official_present)) {
      dirty.official_present = officialPresent ? 1 : 0
    }
    if (isAshuraPilgrimage !== Boolean(rawEvent.is_ashura_pilgrimage)) {
      dirty.is_ashura_pilgrimage = isAshuraPilgrimage ? 1 : 0
    }
    if (notes.trim() !== (rawEvent.notes || '').trim()) {
      dirty.notes = notes.trim()
    }

    let origMicros: string[] = []
    if (Array.isArray(rawEvent.micro_indicators)) {
      origMicros = rawEvent.micro_indicators
    } else if (typeof rawEvent.micro_indicators_json === 'string') {
      try {
        origMicros = JSON.parse(rawEvent.micro_indicators_json)
      } catch {
        origMicros = []
      }
    }
    if (JSON.stringify([...microIndicators].sort()) !== JSON.stringify([...origMicros].sort())) {
      dirty.micro_indicators = microIndicators
    }

    const origPrograms = Array.isArray(rawEvent.program_kinds) ? rawEvent.program_kinds : []
    if (JSON.stringify([...selectedPrograms].sort()) !== JSON.stringify([...origPrograms].sort())) {
      dirty.program_kinds = selectedPrograms
    }

    const origFacts = Array.isArray(rawEvent.facts) ? rawEvent.facts : []
    let factsChanged = facts.length !== origFacts.length
    if (!factsChanged) {
      for (const f of facts) {
        const orig = origFacts.find((x: any) => x.metric === f.metric)
        if (
          !orig ||
          (typeof orig.value === 'number' ? orig.value : parseFloat(orig.value || 0)) !== f.value ||
          (orig.unit_of_measure || 'count') !== (f.unit_of_measure || 'count') ||
          (orig.note || '') !== (f.note || '')
        ) {
          factsChanged = true
          break
        }
      }
    }
    if (factsChanged) {
      dirty.facts = facts
    }

    return dirty
  }

  // Save changes
  const handleSave = async () => {
    if (!eventId) return

    const dirtyFields = getDirtyFields()
    if (Object.keys(dirtyFields).length === 0) {
      toast.info('هیچ تغییری برای ذخیره یافت نشد.')
      return
    }

    // Validation for modified mandatory fields
    if ('occasion' in dirtyFields && !dirtyFields.occasion.trim()) {
      setErrorText('عنوان یا مناسبت رویداد نمی‌تواند خالی باشد.')
      return
    }
    if ('occurred_on' in dirtyFields && !dirtyFields.occurred_on.trim()) {
      setErrorText('تاریخ برگزاری رویداد نمی‌تواند خالی باشد.')
      return
    }
    if (!occurredOn.trim()) {
      setErrorText('تاریخ برگزاری رویداد نمی‌تواند خالی باشد.')
      return
    }

    try {
      setSaving(true)
      setErrorText('')
      await api('PUT', `/api/v3/reporting/events/${encodeURIComponent(eventId)}`, {
        if_match: rawEvent?.etag,
        fields: dirtyFields,
      })
      toast.success('تغییرات پرونده با موفقیت ذخیره شد.')
      onSaved?.()
      await fetchEventData(eventId, { silent: true, syncFields: true })
    } catch (err) {
      setErrorText(err instanceof Error ? err.message : 'خطا در ذخیره تغییرات پرونده')
    } finally {
      setSaving(false)
    }
  }

  // Delete whole event
  const handleDeleteEvent = async () => {
    if (!eventId) return
    try {
      setActionLoading(true)
      await api('DELETE', `/api/v3/reporting/events/${encodeURIComponent(eventId)}`)
      toast.success('پرونده رویداد به همراه کلیه اسناد و محاسبات وابسته با موفقیت حذف گردید.')
      setDeleteConfirmOpen(false)
      onSaved?.()
      onClose()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'خطا در حذف پرونده')
    } finally {
      setActionLoading(false)
    }
  }

  // File upload
  const handleFileInputChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file || !eventId) return

    try {
      setUploadingDoc(true)
      const reader = new FileReader()
      reader.onload = async () => {
        try {
          const result = reader.result as string
          const b64 = result.includes(',') ? result.split(',')[1] : result
          await api('POST', `/api/v3/reporting/events/${encodeURIComponent(eventId)}/documents/upload`, {
            filename: file.name,
            content_base64: b64,
            kind: uploadKind,
            is_cover: uploadIsCover,
          })
          toast.success(`فایل ${file.name} با موفقیت به پرونده الحاق شد.`)
          await fetchEventData(eventId, { silent: true })
        } catch (uploadErr) {
          toast.error(uploadErr instanceof Error ? uploadErr.message : 'خطا در بارگذاری فایل')
        } finally {
          setUploadingDoc(false)
          e.target.value = ''
        }
      }
      reader.readAsDataURL(file)
    } catch (err) {
      setUploadingDoc(false)
      toast.error('خطا در خواندن فایل از حافظه')
    }
  }

  // Document actions
  const handleDeleteDocument = async (docId: string, docName: string) => {
    if (!eventId) return
    if (!window.confirm(`آیا از حذف سند "${docName}" اطمینان دارید؟`)) return
    try {
      // Optimistic local state update to prevent any modal flickering or full reloading
      setRawEvent((prev: any) => {
        if (!prev) return prev
        const docs = Array.isArray(prev.documents) ? prev.documents : []
        return {
          ...prev,
          documents: docs.filter((d: any) => d.document_id !== docId && d.media_id !== docId),
        }
      })
      await api('DELETE', `/api/v3/reporting/events/${encodeURIComponent(eventId)}/documents/${encodeURIComponent(docId)}`)
      toast.success('سند با موفقیت از پرونده حذف گردید.')
      await fetchEventData(eventId, { silent: true })
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'خطا در حذف سند')
      await fetchEventData(eventId, { silent: true })
    }
  }

  const handleSetCover = async (docId: string) => {
    if (!eventId) return
    try {
      // Optimistic local state update for instant cover indicator toggle
      setRawEvent((prev: any) => {
        if (!prev) return prev
        const docs = Array.isArray(prev.documents) ? prev.documents : []
        return {
          ...prev,
          documents: docs.map((d: any) => ({
            ...d,
            is_cover: d.document_id === docId || d.media_id === docId,
          })),
        }
      })
      await api('POST', `/api/v3/reporting/events/${encodeURIComponent(eventId)}/documents/${encodeURIComponent(docId)}/cover`, {
        is_cover: true,
      })
      toast.success('تصویر موردنظر به عنوان عکس شاخص رویداد برگزیده شد.')
      await fetchEventData(eventId, { silent: true })
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'خطا در انتخاب عکس شاخص')
      await fetchEventData(eventId, { silent: true })
    }
  }

  const handleDownloadDoc = async (doc: any) => {
    if (doc.media_url) {
      window.open(doc.media_url, '_blank')
      return
    }
    try {
      const res = await api<{ ok: boolean; content_base64: string; mime_type: string; filename: string }>(
        'GET',
        `/api/v3/reporting/events/${encodeURIComponent(eventId!)}/documents/${encodeURIComponent(doc.document_id)}/view`,
      )
      if (res.content_base64) {
        const blob = b64toBlob(res.content_base64, res.mime_type)
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = res.filename || doc.media_id || 'document'
        a.click()
        URL.revokeObjectURL(url)
      }
    } catch (err) {
      toast.error('خطا در دریافت و دانلود فایل سند')
    }
  }

  const handlePreviewDoc = async (doc: any) => {
    const isImage = doc.kind === 'image' || doc.media_id?.match(/\.(jpg|jpeg|png|webp|gif)$/i)
    if (isImage) {
      if (doc.media_url) {
        setPreviewImageDoc({ url: doc.media_url, title: doc.media_id || 'تصویر سند' })
        return
      }
      try {
        const res = await api<{ ok: boolean; content_base64: string; mime_type: string; filename: string }>(
          'GET',
          `/api/v3/reporting/events/${encodeURIComponent(eventId!)}/documents/${encodeURIComponent(doc.document_id)}/view`,
        )
        if (res.content_base64) {
          const blob = b64toBlob(res.content_base64, res.mime_type || 'image/jpeg')
          const url = URL.createObjectURL(blob)
          setPreviewImageDoc({ url, title: res.filename || doc.media_id || 'تصویر سند' })
        }
      } catch (err) {
        toast.error('خطا در دریافت و نمایش تصویر')
      }
    } else {
      void handleDownloadDoc(doc)
    }
  }

  const handleDetachWitness = async (linkId: string) => {
    if (!eventId) return
    const reason = window.prompt('علت آزادسازی و جداسازی شاهد پیام ایتا را وارد نمایید:', 'جداسازی و آزادسازی شاهد توسط کاربر')
    if (reason === null) return
    if (!reason.trim()) {
      toast.error('ثبت علت جداسازی شاهد الزامی است.')
      return
    }
    try {
      setActionLoading(true)
      await api('POST', `/api/v3/reporting/witness-links/${encodeURIComponent(linkId)}/detach`, { reason: reason.trim() })
      toast.success('شاهد پیام ایتا با موفقیت از پرونده جدا شد.')
      onSaved?.()
      await fetchEventData(eventId)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'خطا در جداسازی شاهد')
    } finally {
      setActionLoading(false)
    }
  }

  // Merge execution
  const handleMergeCandidate = async (cand: any) => {
    if (!eventId) return
    const msg = `آیا از ادغام گزارش "${cand.title}" در این پرونده اطمینان دارید؟\nکلیه عکس‌ها، مستندات، شواهد ایتا و شاخصه‌های آن با این پرونده تجمیع شده و گزارش مبدأ حذف خواهد گردید.`
    if (!window.confirm(msg)) return
    try {
      setActionLoading(true)
      await api('POST', `/api/v3/reporting/events/${encodeURIComponent(eventId)}/merge`, {
        source_event_id: cand.event_id,
      })
      toast.success(`گزارش "${cand.title}" با موفقیت در این پرونده ادغام و یکپارچه شد.`)
      onSaved?.()
      await fetchEventData(eventId)
      await loadMergeCandidates()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'خطا در ادغام گزارش‌ها')
    } finally {
      setActionLoading(false)
    }
  }

  // Workflow transitions
  const handleApprove = async () => {
    if (!eventId) return
    try {
      setActionLoading(true)
      await api('POST', `/api/v3/reporting/events/${encodeURIComponent(eventId)}/approve`, { force_approve: true })
      toast.success('پرونده رویداد با موفقیت تأیید گردید.')
      onSaved?.()
      await fetchEventData(eventId)
    } catch (err) {
      setErrorText(err instanceof Error ? err.message : 'خطا در تأیید رویداد')
    } finally {
      setActionLoading(false)
    }
  }

  const handleRequestRevision = async () => {
    if (!eventId) return
    const reason = window.prompt('شرح نقص یا دستور اصلاح مدیر را وارد نمایید:', rawEvent?.review_notes || '')
    if (reason === null) return
    if (!reason.trim()) {
      toast.error('شرح نقص الزامی است.')
      return
    }
    try {
      setActionLoading(true)
      await api('POST', `/api/v3/reporting/events/${encodeURIComponent(eventId)}/request-revision`, { reason: reason.trim() })
      toast.warning('دستور اصلاح ثبت و گزارش به کارتابل همکار ارجاع داده شد.')
      onSaved?.()
      await fetchEventData(eventId)
    } catch (err) {
      setErrorText(err instanceof Error ? err.message : 'خطا در ثبت دستور اصلاح')
    } finally {
      setActionLoading(false)
    }
  }

  const handleMarkConflict = async () => {
    if (!eventId) return
    const reason = window.prompt('علت رد یا اعلام تعارض این رویداد را وارد نمایید:')
    if (reason === null) return
    if (!reason.trim()) {
      toast.error('علت رد الزامی است.')
      return
    }
    try {
      setActionLoading(true)
      await api('POST', `/api/v3/reporting/events/${encodeURIComponent(eventId)}/mark-conflict`, { reason: reason.trim() })
      toast.info('پرونده به وضعیت تعارض / رد منتقل شد.')
      onSaved?.()
      await fetchEventData(eventId)
    } catch (err) {
      setErrorText(err instanceof Error ? err.message : 'خطا در اعلام تعارض')
    } finally {
      setActionLoading(false)
    }
  }

  const handleSubmitReview = async () => {
    if (!eventId) return
    try {
      setActionLoading(true)
      await handleSave()
      await api('POST', `/api/v3/reporting/events/${encodeURIComponent(eventId)}/submit-review`, {
        notes: 'اصلاحات انجام شد و گزارش مجدداً جهت بررسی نهایی برای مدیر ارسال گردید.',
      })
      toast.success('پرونده جهت بررسی نهایی برای مدیر ارسال شد.')
      onSaved?.()
      await fetchEventData(eventId)
    } catch (err) {
      setErrorText(err instanceof Error ? err.message : 'خطا در ارسال مجدد به مدیر')
    } finally {
      setActionLoading(false)
    }
  }

  // Active review status
  const reviewStatus = rawEvent?.review_status || 'draft'
  const defectsList = Array.isArray(rawEvent?.defects) ? rawEvent.defects : []
  const documentsList = Array.isArray(rawEvent?.documents) ? rawEvent.documents : []
  const photosList = documentsList.filter(d => d.kind === 'image' || d.media_id?.match(/\.(jpg|jpeg|png|webp|gif)$/i))
  const filesList = documentsList.filter(d => !photosList.includes(d))

  // Determine active primary program kind
  const activeProgramKind = viewingProgramKind && selectedPrograms.includes(viewingProgramKind)
    ? viewingProgramKind
    : (selectedPrograms[0] || 'honor')

  return (
    <Dialog open={open} onClose={onClose} maxWidth="lg" fullWidth dir="rtl" PaperProps={{ sx: { bgcolor: 'background.paper', color: 'text.primary', backgroundImage: 'none' } }}>
      {/* Header Bar */}
      <DialogTitle sx={{ p: 2, bgcolor: 'background.paper', borderBottom: '1px solid', borderColor: 'divider' }}>
        <Stack direction="row" justifyContent="space-between" alignItems="center">
          <Stack direction="row" spacing={1.5} alignItems="center">
            <Avatar sx={{ bgcolor: 'primary.main', width: 36, height: 36 }}>
              <AssessmentRounded fontSize="small" />
            </Avatar>
            <Box>
              <Stack direction="row" spacing={1} alignItems="center">
                <Typography variant="h6" fontWeight={800} noWrap sx={{ maxWidth: 480 }} title={occasion || getInitialOccasion(rawEvent) || 'پوشه پرونده جامع رویداد فرهنگی'}>
                  {occasion || getInitialOccasion(rawEvent) || 'پوشه پرونده جامع رویداد فرهنگی'}
                </Typography>
                <Chip size="small" label={eventId} sx={{ fontFamily: 'monospace', fontWeight: 700 }} />
                {isDirty && (
                  <Chip
                    size="small"
                    label="تغییرات ذخیره‌نشده"
                    color="warning"
                    variant="outlined"
                    sx={{ fontWeight: 800 }}
                  />
                )}
                <Chip
                  size="small"
                  label={
                    reviewStatus === 'approved'
                      ? 'تأیید مدیر'
                      : reviewStatus === 'conflict'
                      ? 'تعارض / رد'
                      : reviewStatus === 'needs_review'
                      ? ((rawEvent?.revision_count || 0) > 0 ? `اصلاحیه (${rawEvent?.revision_count})` : 'در انتظار بررسی')
                      : 'پیش‌نویس'
                  }
                  color={
                    reviewStatus === 'approved'
                      ? 'success'
                      : reviewStatus === 'conflict'
                      ? 'error'
                      : reviewStatus === 'needs_review'
                      ? 'warning'
                      : 'default'
                  }
                  sx={{ fontWeight: 800 }}
                />
              </Stack>
              <Typography variant="caption" color="text.secondary">
                واحد: {rawEvent?.unit_name || rawEvent?.unit || 'نامشخص'} | تاریخ وقوع: {rawEvent?.occurred_on || '—'}
              </Typography>
            </Box>
          </Stack>
          <IconButton onClick={onClose} size="small">
            <CloseRounded />
          </IconButton>
        </Stack>

        {/* Tab Navigation */}
        <Tabs
          value={activeTab}
          onChange={(_, val) => setActiveTab(val)}
          sx={{ mt: 1.5, minHeight: 40 }}
          indicatorColor="primary"
          textColor="primary"
        >
          <Tab icon={<EventNoteRounded fontSize="small" />} iconPosition="start" label="شناسنامه و سرفصل" sx={{ fontWeight: 700, minHeight: 40, py: 0.5 }} />
          <Tab icon={<AnalyticsRounded fontSize="small" />} iconPosition="start" label="ارزیابی و اقلام کاربرگ" sx={{ fontWeight: 700, minHeight: 40, py: 0.5 }} />
          <Tab icon={<PhotoLibraryRounded fontSize="small" />} iconPosition="start" label={`اسناد و تصاویر (${documentsList.length})`} sx={{ fontWeight: 700, minHeight: 40, py: 0.5 }} />
          <Tab icon={<LayersRounded fontSize="small" />} iconPosition="start" label={`شواهد ایتا (${rawEvent?.witnesses?.length || 0})`} sx={{ fontWeight: 700, minHeight: 40, py: 0.5 }} />
          <Tab icon={<CallMergeRounded fontSize="small" />} iconPosition="start" label="ادغام هوشمند و یکپارچه‌سازی" sx={{ fontWeight: 700, minHeight: 40, py: 0.5 }} />
        </Tabs>
      </DialogTitle>

      <DialogContent dividers sx={{ p: 2.5, bgcolor: 'background.default', color: 'text.primary' }}>
        {loading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
            <CircularProgress />
          </Box>
        ) : (
          <Stack spacing={2.5}>
            {errorText && (
              <Alert severity="error" onClose={() => setErrorText('')}>
                {errorText}
              </Alert>
            )}

            {/* TAB 0: Event Identity & Classification */}
            {activeTab === 0 && (
              <Stack spacing={2.5}>
                {/* Defect Alerts / Manager Notes */}
                {(defectsList.length > 0 || rawEvent?.review_notes) && (
                  <Paper
                    variant="outlined"
                    sx={{
                      p: 2,
                      borderRadius: 2,
                      bgcolor: defectsList.some((d: any) => d.severity === 'blocker') ? 'error.50' : 'warning.50',
                      borderColor: defectsList.some((d: any) => d.severity === 'blocker') ? 'error.main' : 'warning.main',
                    }}
                  >
                    <Stack spacing={1}>
                      <Stack direction="row" spacing={1} alignItems="center">
                        <WarningAmberRounded color={defectsList.some((d: any) => d.severity === 'blocker') ? 'error' : 'warning'} />
                        <Typography variant="subtitle2" fontWeight={800}>
                          هشدارها و نقایص گزارش‌گیری / دستور اصلاح مدیر
                        </Typography>
                      </Stack>
                      {rawEvent?.review_notes && (
                        <Typography variant="body2" sx={{ fontWeight: 600 }}>
                          <strong>شرح دستور اصلاح:</strong> {rawEvent.review_notes}
                        </Typography>
                      )}
                      {defectsList.map((d: any, idx: number) => (
                        <Typography key={idx} variant="caption" display="block" color={d.severity === 'blocker' ? 'error.main' : 'warning.dark'}>
                          • {d.title}: {d.description}
                        </Typography>
                      ))}
                    </Stack>
                  </Paper>
                )}

                {/* Basic Information */}
                <Paper variant="outlined" sx={{ p: 2.5, borderRadius: 2, bgcolor: 'background.paper' }}>
                  <Typography variant="subtitle2" fontWeight={800} color="primary" sx={{ mb: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
                    <EventNoteRounded fontSize="small" />
                    اطلاعات شناسنامه‌ای و سرفصل رویداد
                  </Typography>

                  <Grid container spacing={2}>
                    <Grid size={{ xs: 12 }}>
                      <TextField
                        label="عنوان / مناسبت رویداد"
                        size="small"
                        fullWidth
                        value={occasion}
                        onChange={e => setOccasion(e.target.value)}
                        placeholder="مثال: برگزاری اردوی خانوادگی پرسنل مشهد مقدس"
                        required
                      />
                    </Grid>

                    <Grid size={{ xs: 12, sm: 6 }}>
                      <FormControl size="small" fullWidth>
                        <InputLabel>دسته‌بندی کلی سرفصل</InputLabel>
                        <Select
                          value={macroCategory}
                          label="دسته‌بندی کلی سرفصل"
                          onChange={e => setMacroCategory(e.target.value)}
                        >
                          <MenuItem value="workbook_approved">برنامه‌های مصوب شیت‌های هفت‌گانه</MenuItem>
                          <MenuItem value="other_cultural">سایر فعالیت‌های فرهنگی (خارج از شیت)</MenuItem>
                        </Select>
                      </FormControl>
                    </Grid>

                    {macroCategory === 'other_cultural' ? (
                      <Grid size={{ xs: 12, sm: 6 }}>
                        <TextField
                          label="عنوان سرفصل فرهنگی سفارشی"
                          size="small"
                          fullWidth
                          value={customTopic}
                          onChange={e => setCustomTopic(e.target.value)}
                          placeholder="عنوان فعالیت فرهنگی خارج از شیت"
                        />
                      </Grid>
                    ) : (
                      <Grid size={{ xs: 12, sm: 6 }}>
                        <Autocomplete
                          multiple
                          options={programsCatalog.map(p => p.kind || p.program_code)}
                          getOptionLabel={opt => {
                            const found = programsCatalog.find(p => p.kind === opt || p.program_code === opt)
                            return found ? `${found.program_code} - ${found.title}` : opt
                          }}
                          value={selectedPrograms}
                          onChange={(_, val) => setSelectedPrograms(val)}
                          renderInput={params => (
                            <TextField {...params} label="سرفصل‌های مصوب مرتبط" size="small" placeholder="انتخاب برنامه" />
                          )}
                          renderTags={(value, getTagProps) =>
                            value.map((option, index) => {
                              const found = programsCatalog.find(p => p.kind === option || p.program_code === option)
                              return (
                                <Chip
                                  {...getTagProps({ index })}
                                  key={option}
                                  size="small"
                                  color="primary"
                                  label={found ? `${found.program_code} (${found.title})` : option}
                                />
                              )
                            })
                          }
                        />
                      </Grid>
                    )}

                    <Grid size={{ xs: 12, sm: 6 }}>
                      <FormControl size="small" fullWidth>
                        <InputLabel>سطح سازمانی حوزه قضایی</InputLabel>
                        <Select
                          value={unitScope}
                          label="سطح سازمانی حوزه قضایی"
                          onChange={e => setUnitScope(e.target.value)}
                        >
                          {UNIT_SCOPES.map(s => (
                            <MenuItem key={s.value} value={s.value}>
                              {s.label}
                            </MenuItem>
                          ))}
                        </Select>
                      </FormControl>
                    </Grid>

                    <Grid size={{ xs: 12, sm: 6 }}>
                      <Autocomplete
                        freeSolo
                        options={judicialUnits.map(u => u.name || u.display_name)}
                        value={unitName}
                        onInputChange={(_, val) => setUnitName(val)}
                        renderInput={params => (
                          <TextField {...params} label="نام حوزه قضایی / واحد سازمانی" size="small" placeholder="مثال: ساری - دادگستری" />
                        )}
                      />
                    </Grid>

                    <Grid size={{ xs: 12, sm: 6 }}>
                      <JalaliDatePicker
                        label="تاریخ برگزاری رویداد (شمسی)"
                        value={occurredOn}
                        onChange={val => setOccurredOn(val)}
                        required
                        error={!occurredOn.trim()}
                        helperText={!occurredOn.trim() ? 'تاریخ برگزاری الزامی است' : 'مثال: ۱۴۰۵/۰۷/۲۷'}
                        size="small"
                        fullWidth
                      />
                    </Grid>

                    <Grid size={{ xs: 12, sm: 6 }}>
                      <FormControl size="small" fullWidth>
                        <InputLabel>شاخصه کلی (برنامه مصوب)</InputLabel>
                        <Select
                          value={macroIndicator}
                          label="شاخصه کلی (برنامه مصوب)"
                          onChange={e => setMacroIndicator(e.target.value)}
                        >
                          <MenuItem value="">
                            <em>— بدون شاخصه کلی —</em>
                          </MenuItem>
                          <MenuItem value="none">
                            <strong>🚫 فاقد شاخصه (آزاد / اطلاعیه عمومی)</strong>
                          </MenuItem>
                          {macroOptions
                            .filter(m => m !== 'none')
                            .map(m => (
                              <MenuItem key={m} value={m}>
                                {m}
                              </MenuItem>
                            ))}
                        </Select>
                      </FormControl>
                    </Grid>

                    {/* Compact 2-Column Micro-indicators Management (Single Row Layout) */}
                    <Grid size={{ xs: 12 }}>
                      <Box
                        sx={{
                          p: 1.5,
                          borderRadius: 2,
                          bgcolor: 'action.hover',
                          border: '1px solid',
                          borderColor: 'divider',
                        }}
                      >
                        <Grid container spacing={1.5} alignItems="center">
                          {/* Right Column: Selected Micro-Indicators as Button-like Tags */}
                          <Grid size={{ xs: 12, md: 7 }}>
                            <Stack direction="row" spacing={0.75} alignItems="center" flexWrap="wrap" useFlexGap>
                              <Typography variant="caption" fontWeight={700} color="text.secondary" sx={{ whiteSpace: 'nowrap', display: 'flex', alignItems: 'center', gap: 0.5 }}>
                                <LabelOutlined sx={{ fontSize: 16 }} />
                                شاخصه‌های جزئی ({microIndicators.length}):
                              </Typography>
                              {microIndicators.length === 0 ? (
                                <Typography variant="caption" color="text.disabled">
                                  هنوز شاخصه‌ای افزوده نشده است.
                                </Typography>
                              ) : (
                                microIndicators.map(m => (
                                  <Chip
                                    key={m}
                                    label={m}
                                    size="small"
                                    color="secondary"
                                    variant="outlined"
                                    onDelete={() => handleRemoveMicroTag(m)}
                                    deleteIcon={<CloseRounded sx={{ fontSize: '14px !important' }} />}
                                    sx={{
                                      fontWeight: 700,
                                      fontSize: '0.72rem',
                                      height: 26,
                                      bgcolor: 'rgba(77, 208, 184, 0.08)',
                                      borderColor: 'rgba(77, 208, 184, 0.35)',
                                      '& .MuiChip-deleteIcon': {
                                        color: 'error.light',
                                        '&:hover': { color: 'error.main' },
                                      },
                                    }}
                                  />
                                ))
                              )}
                            </Stack>
                          </Grid>

                          {/* Left Column: Searchable Autocomplete & Quick Add Button */}
                          <Grid size={{ xs: 12, md: 5 }}>
                            <Stack direction="row" spacing={0.5} alignItems="center">
                              <Autocomplete
                                freeSolo
                                size="small"
                                fullWidth
                                options={microOptions.map(o => o.title).filter(t => !microIndicators.includes(t))}
                                value={newMicroTag}
                                onInputChange={(_, val) => setNewMicroTag(val)}
                                onChange={(_, val) => {
                                  if (val) handleAddMicroTag(val)
                                }}
                                renderInput={params => (
                                  <TextField
                                    {...params}
                                    placeholder="جستجو یا تایپ شاخصه جزئی..."
                                    size="small"
                                    onKeyDown={e => {
                                      if (e.key === 'Enter' && newMicroTag.trim()) {
                                        e.preventDefault()
                                        handleAddMicroTag(newMicroTag)
                                      }
                                    }}
                                  />
                                )}
                              />
                              <Button
                                variant="contained"
                                color="primary"
                                size="small"
                                onClick={() => handleAddMicroTag(newMicroTag)}
                                disabled={!newMicroTag.trim()}
                                sx={{ minWidth: 36, px: 1.25, height: 40 }}
                                title="افزودن به شاخصه‌ها"
                              >
                                <AddRounded fontSize="small" />
                              </Button>
                            </Stack>
                          </Grid>
                        </Grid>
                      </Box>
                    </Grid>

                    {/* Summary of Registered Numeric Metrics (فکت‌ها و سنجه‌های ثبت‌شده رویداد) */}
                    <Grid size={{ xs: 12 }}>
                      <Paper
                        variant="outlined"
                        sx={{
                          p: 2,
                          borderRadius: 2,
                          bgcolor: 'background.paper',
                          borderColor: facts.length > 0 ? 'primary.main' : 'divider',
                        }}
                      >
                        <Stack spacing={1.5}>
                          <Stack direction="row" justifyContent="space-between" alignItems="center" flexWrap="wrap" gap={1}>
                            <Stack direction="row" spacing={1} alignItems="center">
                              <AssessmentRounded color={facts.length > 0 ? 'primary' : 'disabled'} fontSize="small" />
                              <Typography variant="subtitle2" fontWeight={800}>
                                آمار و سنجه‌های ثبت‌شده این رویداد ({toPersianDigits(facts.length)} قلم)
                              </Typography>
                            </Stack>
                            <Button
                              size="small"
                              variant="outlined"
                              onClick={() => setActiveTab(1)}
                            >
                              مشاهده و ویرایش تفصیلی در کاربرگ ←
                            </Button>
                          </Stack>

                          {facts.length > 0 ? (
                            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                              {facts.map((fact, idx) => {
                                const label = METRIC_LABELS[fact.metric] || fact.note || fact.metric
                                return (
                                  <Chip
                                    key={fact.metric + idx}
                                    label={`${label}: ${toPersianDigits(fact.value)} ${fact.unit_of_measure || 'نفر'}`}
                                    color="primary"
                                    variant="outlined"
                                    onClick={() => setActiveTab(1)}
                                    clickable
                                    sx={{ fontWeight: 700 }}
                                  />
                                )
                              })}
                            </Box>
                          ) : (
                            <Typography variant="caption" color="text.secondary">
                              هنوز سنجهٔ عددی برای این رویداد ثبت نشده است. می‌توانید در برگهٔ «ارزیابی و اقلام کاربرگ» یا بخش افزودن سنجه، آمار مورد نظر را وارد نمایید.
                            </Typography>
                          )}
                        </Stack>
                      </Paper>
                    </Grid>

                    {/* Extended Summary & Detailed Event Notes (Minimum 5 lines) */}
                    <Grid size={{ xs: 12 }}>
                      <TextField
                        label="شرح کامل، خلاصه رویداد و یادداشت‌های تفصیلی"
                        size="small"
                        fullWidth
                        multiline
                        minRows={5}
                        rows={5}
                        value={notes}
                        onChange={e => setNotes(e.target.value)}
                        placeholder="توضیحات تفصیلی، اهداف، آمار تفکیکی، بازخوردها و نکات تکمیلی برگزاری رویداد..."
                        helperText="حداقل ۵ خط فضا جهت مشاهده، مطالعه و ویرایش راحت شرح رویداد بدون تنگی کادر"
                      />
                    </Grid>

                    <Grid size={{ xs: 12, sm: 6 }}>
                      <FormControlLabel
                        control={
                          <Switch
                            checked={officialPresent}
                            onChange={e => setOfficialPresent(e.target.checked)}
                          />
                        }
                        label={<Typography variant="body2">حضور مسئولان / مقامات ارشد استانی</Typography>}
                      />
                    </Grid>

                    <Grid size={{ xs: 12, sm: 6 }}>
                      <FormControlLabel
                        control={
                          <Switch
                            checked={isAshuraPilgrimage}
                            onChange={e => setIsAshuraPilgrimage(e.target.checked)}
                          />
                        }
                        label={<Typography variant="body2">قرائت زیارت عاشورا (C12)</Typography>}
                      />
                    </Grid>
                  </Grid>
                </Paper>
              </Stack>
            )}

            {/* TAB 1: Worksheet Questionnaire & Metrics */}
            {activeTab === 1 && (
              <Stack spacing={2.5}>
                {/* Statistical Normalization & KPI Card */}
                {normalization && (
                  <Paper
                    variant="outlined"
                    sx={{
                      p: 2,
                      borderRadius: 2,
                      bgcolor: normalization.has_anomalies ? 'warning.50' : 'info.50',
                      borderColor: normalization.has_anomalies ? 'warning.main' : 'info.main',
                    }}
                  >
                    <Stack spacing={1.5}>
                      <Stack direction="row" spacing={1} alignItems="center">
                        <AnalyticsRounded color={normalization.has_anomalies ? 'warning' : 'info'} />
                        <Typography variant="subtitle2" fontWeight={800}>
                          پایش نرمال‌سازی آماری واحد ({normalization.unit_id || unitName || 'نامشخص'})
                        </Typography>
                      </Stack>

                      <Grid container spacing={2}>
                        <Grid size={{ xs: 6, sm: 3 }}>
                          <Typography variant="caption" color="text.secondary" display="block">
                            کادر پرسنلی پایه واحد:
                          </Typography>
                          <Typography variant="body1" fontWeight={800}>
                            {normalization.baseline_staff_count || 'تعریف‌نشده'} نفر
                          </Typography>
                        </Grid>
                        <Grid size={{ xs: 6, sm: 3 }}>
                          <Typography variant="caption" color="text.secondary" display="block">
                            برآورد ظرفیت خانوادگی:
                          </Typography>
                          <Typography variant="body1" fontWeight={800}>
                            {normalization.estimated_family_pool || '—'} نفر
                          </Typography>
                        </Grid>
                        <Grid size={{ xs: 6, sm: 3 }}>
                          <Typography variant="caption" color="text.secondary" display="block">
                            {activeProgramKind === 'honor' || activeProgramKind === 'customer_care' ? 'افراد تقدیرشده ثبت‌شده:' : 'شرکت‌کنندگان ثبت‌شده:'}
                          </Typography>
                          <Typography variant="body1" fontWeight={800} color="primary.main">
                            {activeProgramKind === 'honor' || activeProgramKind === 'customer_care'
                              ? `${getFactValue('honored_count')} نفر`
                              : `${normalization.reported_attendees || getFactValue('attendees')} نفر`}
                          </Typography>
                        </Grid>
                        <Grid size={{ xs: 6, sm: 3 }}>
                          <Typography variant="caption" color="text.secondary" display="block">
                            ضریب مشارکت پرسنل:
                          </Typography>
                          <Typography variant="body1" fontWeight={800} color={normalization.attendance_rate_staff_pct && normalization.attendance_rate_staff_pct > 100 ? 'warning.dark' : 'success.main'}>
                            {normalization.attendance_rate_staff_pct ? `${normalization.attendance_rate_staff_pct}%` : '—'}
                          </Typography>
                        </Grid>
                      </Grid>

                      {normalization.anomalies && normalization.anomalies.length > 0 && (
                        <Box sx={{ mt: 1 }}>
                          {normalization.anomalies.map((anom: string, i: number) => (
                            <Typography key={i} variant="caption" color="warning.dark" display="block" fontWeight={700}>
                              ⚠️ {anom}
                            </Typography>
                          ))}
                        </Box>
                      )}
                    </Stack>
                  </Paper>
                )}

                {/* Universal Registered Facts Section (کلیه سنجه‌های آماری ثبت‌شده این رویداد) */}
                <Paper variant="outlined" sx={{ p: 2.5, borderRadius: 2, bgcolor: 'background.paper', border: 1, borderColor: 'primary.light' }}>
                  <Stack spacing={2}>
                    <Stack direction="row" justifyContent="space-between" alignItems="center" flexWrap="wrap" gap={1}>
                      <Stack direction="row" spacing={1} alignItems="center">
                        <AssessmentRounded color="primary" />
                        <Typography variant="subtitle1" fontWeight={800}>
                          کلیه سنجه‌های آماری ثبت‌شده این رویداد ({toPersianDigits(facts.length)} سنجه)
                        </Typography>
                      </Stack>
                      <Typography variant="caption" color="text.secondary">
                        کلیه شاخص‌های کمی (از جمله افراد، همکاران، شرکت‌کنندگان و...) بدون تفکیک سرفصل از این بخش قابل مشاهده و ویرایش هستند.
                      </Typography>
                    </Stack>

                    {facts.length > 0 ? (
                      <Grid container spacing={2}>
                        {facts.map((fact, idx) => {
                          const label = METRIC_LABELS[fact.metric] || fact.note || fact.metric
                          return (
                            <Grid key={fact.metric + idx} size={{ xs: 12, sm: 6, md: 4 }}>
                              <Paper
                                variant="outlined"
                                sx={{
                                  p: 1.5,
                                  borderRadius: 2,
                                  bgcolor: 'action.hover',
                                  borderColor: 'divider',
                                  display: 'flex',
                                  flexDirection: 'column',
                                  gap: 1,
                                }}
                              >
                                <Stack direction="row" justifyContent="space-between" alignItems="flex-start">
                                  <Box sx={{ flex: 1 }}>
                                    <Typography variant="body2" fontWeight={800} color="text.primary">
                                      {label}
                                    </Typography>
                                    <Typography variant="caption" color="text.secondary" sx={{ fontFamily: 'monospace' }}>
                                      {fact.metric}
                                    </Typography>
                                  </Box>
                                  <Tooltip title="حذف این سنجه">
                                    <IconButton size="small" color="error" onClick={() => removeFact(fact.metric)}>
                                      <DeleteOutlineRounded fontSize="small" />
                                    </IconButton>
                                  </Tooltip>
                                </Stack>

                                <Stack direction="row" spacing={1} alignItems="center">
                                  <TextField
                                    size="small"
                                    type="number"
                                    fullWidth
                                    label="مقدار"
                                    value={fact.value}
                                    onChange={e => setFactValue(fact.metric, parseFloat(e.target.value) || 0, fact.unit_of_measure, fact.note)}
                                    InputProps={{
                                      endAdornment: <InputAdornment position="end">{fact.unit_of_measure || 'نفر'}</InputAdornment>,
                                    }}
                                  />
                                  <TextField
                                    size="small"
                                    label="واحد"
                                    value={fact.unit_of_measure}
                                    onChange={e => {
                                      const nextUnit = e.target.value
                                      setFacts(prev => prev.map((f, i) => i === idx ? { ...f, unit_of_measure: nextUnit } : f))
                                    }}
                                    sx={{ width: 90 }}
                                  />
                                </Stack>
                              </Paper>
                            </Grid>
                          )
                        })}
                      </Grid>
                    ) : (
                      <Alert severity="info" variant="outlined">
                        هنوز هیچ سنجهٔ آماری برای این رویداد ثبت نشده است. می‌توانید با فیلدهای کاربرگ زیر یا بخش «افزودن سنجه جدید» آمار را وارد نمایید.
                      </Alert>
                    )}
                  </Stack>
                </Paper>

                {/* Worksheet Criteria Inputs */}
                <Paper variant="outlined" sx={{ p: 2.5, borderRadius: 2, bgcolor: 'background.paper' }}>
                  <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 2 }} flexWrap="wrap" gap={1}>
                    <Typography variant="subtitle2" fontWeight={800} color="primary" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <AssessmentRounded fontSize="small" />
                      سنجه‌ها و اقلام تفکیکی کاربرگ مربوطه ({activeProgramKind})
                    </Typography>

                    {selectedPrograms.length > 1 && (
                      <Stack direction="row" spacing={0.5} alignItems="center">
                        <Typography variant="caption" color="text.secondary">انتخاب کاربرگ:</Typography>
                        {selectedPrograms.map(prog => (
                          <Chip
                            key={prog}
                            label={prog}
                            size="small"
                            clickable
                            color={activeProgramKind === prog ? 'primary' : 'default'}
                            variant={activeProgramKind === prog ? 'filled' : 'outlined'}
                            onClick={() => setViewingProgramKind(prog)}
                          />
                        ))}
                      </Stack>
                    )}
                  </Stack>

                  {/* 1. HONOR (80406 - تکریم و تجلیل) */}
                  {activeProgramKind === 'honor' && (
                    <Grid container spacing={2}>
                      <Grid size={{ xs: 12, sm: 4 }}>
                        <TextField
                          label="تعداد کل افراد تقدیرشده (نفر)"
                          type="number"
                          size="small"
                          fullWidth
                          value={getFactValue('honored_count')}
                          onChange={e => setFactValue('honored_count', parseFloat(e.target.value) || 0, 'نفر', 'افراد تقدیرشده کل')}
                          InputProps={{ endAdornment: <InputAdornment position="end">نفر</InputAdornment> }}
                        />
                      </Grid>
                      <Grid size={{ xs: 12, sm: 4 }}>
                        <TextField
                          label="تکریم مفاخر و نخبگان"
                          type="number"
                          size="small"
                          fullWidth
                          value={getFactValue('honor_legends')}
                          onChange={e => setFactValue('honor_legends', parseFloat(e.target.value) || 0, 'نفر', 'مفاخر')}
                          InputProps={{ endAdornment: <InputAdornment position="end">نفر</InputAdornment> }}
                        />
                      </Grid>
                      <Grid size={{ xs: 12, sm: 4 }}>
                        <TextField
                          label="تکریم بازنشستگان"
                          type="number"
                          size="small"
                          fullWidth
                          value={getFactValue('honor_retirees')}
                          onChange={e => setFactValue('honor_retirees', parseFloat(e.target.value) || 0, 'نفر', 'بازنشستگان')}
                          InputProps={{ endAdornment: <InputAdornment position="end">نفر</InputAdornment> }}
                        />
                      </Grid>
                      <Grid size={{ xs: 12, sm: 4 }}>
                        <TextField
                          label="تکریم پیشکسوتان و ایثارگران"
                          type="number"
                          size="small"
                          fullWidth
                          value={getFactValue('honor_veterans')}
                          onChange={e => setFactValue('honor_veterans', parseFloat(e.target.value) || 0, 'نفر', 'پیشکسوتان')}
                          InputProps={{ endAdornment: <InputAdornment position="end">نفر</InputAdornment> }}
                        />
                      </Grid>
                      <Grid size={{ xs: 12, sm: 4 }}>
                        <TextField
                          label="تکریم خادمان نماز"
                          type="number"
                          size="small"
                          fullWidth
                          value={getFactValue('honor_prayer_servants')}
                          onChange={e => setFactValue('honor_prayer_servants', parseFloat(e.target.value) || 0, 'نفر', 'خادمان نماز')}
                          InputProps={{ endAdornment: <InputAdornment position="end">نفر</InputAdornment> }}
                        />
                      </Grid>
                      <Grid size={{ xs: 12, sm: 4 }}>
                        <TextField
                          label="تکریم مناسبت‌های خاص"
                          type="number"
                          size="small"
                          fullWidth
                          value={getFactValue('honor_special')}
                          onChange={e => setFactValue('honor_special', parseFloat(e.target.value) || 0, 'نفر', 'مناسبت‌های خاص')}
                          InputProps={{ endAdornment: <InputAdornment position="end">نفر</InputAdornment> }}
                        />
                      </Grid>
                      <Grid size={{ xs: 12, sm: 4 }}>
                        <TextField
                          label="هدایای اهدایی به تکریم‌شدگان"
                          type="number"
                          size="small"
                          fullWidth
                          value={getFactValue('gifts')}
                          onChange={e => setFactValue('gifts', parseFloat(e.target.value) || 0, 'فقره', 'هدایا')}
                          InputProps={{ endAdornment: <InputAdornment position="end">فقره</InputAdornment> }}
                        />
                      </Grid>
                      <Grid size={{ xs: 12, sm: 4 }}>
                        <TextField
                          label="پذیرایی و ضیافت غذا"
                          type="number"
                          size="small"
                          fullWidth
                          value={getFactValue('reception')}
                          onChange={e => setFactValue('reception', parseFloat(e.target.value) || 0, 'وعده', 'پذیرایی')}
                          InputProps={{ endAdornment: <InputAdornment position="end">وعده</InputAdornment> }}
                        />
                      </Grid>
                      <Grid size={{ xs: 12, sm: 4 }}>
                        <TextField
                          label="اطلاع‌رسانی و بازتاب رسانه‌ای"
                          type="number"
                          size="small"
                          fullWidth
                          value={getFactValue('announcement')}
                          onChange={e => setFactValue('announcement', parseFloat(e.target.value) || 0, 'مورد', 'اطلاع‌رسانی')}
                          InputProps={{ endAdornment: <InputAdornment position="end">مورد</InputAdornment> }}
                        />
                      </Grid>
                    </Grid>
                  )}

                  {/* 2. CEREMONIES (80403 - مراسم مذهبی، ملی و انقلابی) */}
                  {(activeProgramKind === 'ceremony' || activeProgramKind === 'ceremonies') && (
                    <Grid container spacing={2}>
                      <Grid size={{ xs: 12, sm: 4 }}>
                        <TextField
                          label="تعداد کل شرکت‌کنندگان در مراسم (نفر)"
                          type="number"
                          size="small"
                          fullWidth
                          value={getFactValue('attendees')}
                          onChange={e => setFactValue('attendees', parseFloat(e.target.value) || 0, 'نفر', 'شرکت‌کنندگان کل')}
                          InputProps={{ endAdornment: <InputAdornment position="end">نفر</InputAdornment> }}
                        />
                      </Grid>
                      <Grid size={{ xs: 12, sm: 4 }}>
                        <TextField
                          label="تعداد مراسم مذهبی"
                          type="number"
                          size="small"
                          fullWidth
                          value={getFactValue('ceremony_religious')}
                          onChange={e => setFactValue('ceremony_religious', parseFloat(e.target.value) || 0, 'مراسم', 'مذهبی')}
                          InputProps={{ endAdornment: <InputAdornment position="end">مراسم</InputAdornment> }}
                        />
                      </Grid>
                      <Grid size={{ xs: 12, sm: 4 }}>
                        <TextField
                          label="تعداد مراسم ملی"
                          type="number"
                          size="small"
                          fullWidth
                          value={getFactValue('ceremony_national')}
                          onChange={e => setFactValue('ceremony_national', parseFloat(e.target.value) || 0, 'مراسم', 'ملی')}
                          InputProps={{ endAdornment: <InputAdornment position="end">مراسم</InputAdornment> }}
                        />
                      </Grid>
                      <Grid size={{ xs: 12, sm: 4 }}>
                        <TextField
                          label="تعداد مراسم انقلابی"
                          type="number"
                          size="small"
                          fullWidth
                          value={getFactValue('ceremony_revolutionary')}
                          onChange={e => setFactValue('ceremony_revolutionary', parseFloat(e.target.value) || 0, 'مراسم', 'انقلابی')}
                          InputProps={{ endAdornment: <InputAdornment position="end">مراسم</InputAdornment> }}
                        />
                      </Grid>
                      <Grid size={{ xs: 12, sm: 4 }}>
                        <TextField
                          label="هماهنگی سخنران / مداح / مجری"
                          type="number"
                          size="small"
                          fullWidth
                          value={getFactValue('speaker_count')}
                          onChange={e => setFactValue('speaker_count', parseFloat(e.target.value) || 0, 'نفر', 'سخنران/مداح')}
                          InputProps={{ endAdornment: <InputAdornment position="end">نفر</InputAdornment> }}
                        />
                      </Grid>
                      <Grid size={{ xs: 12, sm: 4 }}>
                        <TextField
                          label="بسته‌های فرهنگی توزیع‌شده"
                          type="number"
                          size="small"
                          fullWidth
                          value={getFactValue('culture_pack_count')}
                          onChange={e => setFactValue('culture_pack_count', parseFloat(e.target.value) || 0, 'بسته', 'بسته‌های فرهنگی')}
                          InputProps={{ endAdornment: <InputAdornment position="end">بسته</InputAdornment> }}
                        />
                      </Grid>
                      <Grid size={{ xs: 12, sm: 4 }}>
                        <TextField
                          label="فضاسازی و تبلیغات محیطی"
                          type="number"
                          size="small"
                          fullWidth
                          value={getFactValue('space_setup_count')}
                          onChange={e => setFactValue('space_setup_count', parseFloat(e.target.value) || 0, 'مورد', 'فضاسازی')}
                          InputProps={{ endAdornment: <InputAdornment position="end">مورد</InputAdornment> }}
                        />
                      </Grid>
                      <Grid size={{ xs: 12, sm: 4 }}>
                        <TextField
                          label="پذیرایی و ضیافت غذا"
                          type="number"
                          size="small"
                          fullWidth
                          value={getFactValue('reception')}
                          onChange={e => setFactValue('reception', parseFloat(e.target.value) || 0, 'وعده', 'پذیرایی')}
                          InputProps={{ endAdornment: <InputAdornment position="end">وعده</InputAdornment> }}
                        />
                      </Grid>
                      <Grid size={{ xs: 12, sm: 4 }}>
                        <TextField
                          label="زیارت عاشورا — تعداد مراسم (پیوست جدا)"
                          type="number"
                          size="small"
                          fullWidth
                          value={getFactValue('ashura_pilgrimage_count')}
                          onChange={e => setFactValue('ashura_pilgrimage_count', parseFloat(e.target.value) || 0, 'مراسم', 'زیارت عاشورا')}
                          InputProps={{ endAdornment: <InputAdornment position="end">مراسم</InputAdornment> }}
                        />
                      </Grid>
                    </Grid>
                  )}

                  {/* 3. PRAYER (80501 - ترویج و توسعه فرهنگ اقامه نماز) */}
                  {activeProgramKind === 'prayer' && (
                    <Grid container spacing={2}>
                      <Grid size={{ xs: 12, sm: 4 }}>
                        <TextField
                          label="تعداد نمازگزاران (نفر)"
                          type="number"
                          size="small"
                          fullWidth
                          value={getFactValue('attendees')}
                          onChange={e => setFactValue('attendees', parseFloat(e.target.value) || 0, 'نفر', 'نمازگزاران')}
                          InputProps={{ endAdornment: <InputAdornment position="end">نفر</InputAdornment> }}
                        />
                      </Grid>
                      <Grid size={{ xs: 12, sm: 4 }}>
                        <TextField
                          label="تعداد نوبت‌های اقامه نماز جماعت"
                          type="number"
                          size="small"
                          fullWidth
                          value={getFactValue('prayer_sessions')}
                          onChange={e => setFactValue('prayer_sessions', parseFloat(e.target.value) || 0, 'نوبت', 'نوبت‌های نماز')}
                          InputProps={{ endAdornment: <InputAdornment position="end">نوبت</InputAdornment> }}
                        />
                      </Grid>
                      <Grid size={{ xs: 12, sm: 4 }}>
                        <TextField
                          label="تجلیل از نومکلفین (رویش جوانه‌ها)"
                          type="number"
                          size="small"
                          fullWidth
                          value={getFactValue('new_duty_honorees')}
                          onChange={e => setFactValue('new_duty_honorees', parseFloat(e.target.value) || 0, 'نفر', 'نومکلفین')}
                          InputProps={{ endAdornment: <InputAdornment position="end">نفر</InputAdornment> }}
                        />
                      </Grid>
                      <Grid size={{ xs: 12, sm: 4 }}>
                        <TextField
                          label="ائمه جماعت مستقر و راتب"
                          type="number"
                          size="small"
                          fullWidth
                          value={getFactValue('clergy_count')}
                          onChange={e => setFactValue('clergy_count', parseFloat(e.target.value) || 0, 'نفر', 'ائمه جماعت')}
                          InputProps={{ endAdornment: <InputAdornment position="end">نفر</InputAdornment> }}
                        />
                      </Grid>
                      <Grid size={{ xs: 12, sm: 4 }}>
                        <TextField
                          label="تجهیز و زیباسازی نمازخانه"
                          type="number"
                          size="small"
                          fullWidth
                          value={getFactValue('space_setup')}
                          onChange={e => setFactValue('space_setup', parseFloat(e.target.value) || 0, 'مورد', 'تجهیز نمازخانه')}
                          InputProps={{ endAdornment: <InputAdornment position="end">مورد</InputAdornment> }}
                        />
                      </Grid>
                      <Grid size={{ xs: 12, sm: 4 }}>
                        <TextField
                          label="پذیرایی و افطاری"
                          type="number"
                          size="small"
                          fullWidth
                          value={getFactValue('reception')}
                          onChange={e => setFactValue('reception', parseFloat(e.target.value) || 0, 'وعده', 'پذیرایی نماز')}
                          InputProps={{ endAdornment: <InputAdornment position="end">وعده</InputAdornment> }}
                        />
                      </Grid>
                    </Grid>
                  )}

                  {/* 4. CONTEST (80402 - مسابقات قرآن و مسابقات فرهنگی-ورزشی) */}
                  {(activeProgramKind === 'contest' || activeProgramKind === 'contests' || activeProgramKind === 'quran_contest') && (
                    <Grid container spacing={2}>
                      <Grid size={{ xs: 12, sm: 4 }}>
                        <TextField
                          label="شرکت‌کنندگان مسابقات قرآنی"
                          type="number"
                          size="small"
                          fullWidth
                          value={getFactValue('quran_attendees')}
                          onChange={e => setFactValue('quran_attendees', parseFloat(e.target.value) || 0, 'نفر', 'شرکت‌کنندگان قرآنی')}
                          InputProps={{ endAdornment: <InputAdornment position="end">نفر</InputAdornment> }}
                        />
                      </Grid>
                      <Grid size={{ xs: 12, sm: 4 }}>
                        <TextField
                          label="شرکت‌کنندگان مسابقات فرهنگی-ورزشی"
                          type="number"
                          size="small"
                          fullWidth
                          value={getFactValue('attendees')}
                          onChange={e => setFactValue('attendees', parseFloat(e.target.value) || 0, 'نفر', 'شرکت‌کنندگان فرهنگی')}
                          InputProps={{ endAdornment: <InputAdornment position="end">نفر</InputAdornment> }}
                        />
                      </Grid>
                      <Grid size={{ xs: 12, sm: 4 }}>
                        <TextField
                          label="تعداد مسابقات برگزار شده"
                          type="number"
                          size="small"
                          fullWidth
                          value={getFactValue('contest_count')}
                          onChange={e => setFactValue('contest_count', parseFloat(e.target.value) || 0, 'دوره', 'تعداد مسابقه')}
                          InputProps={{ endAdornment: <InputAdornment position="end">دوره</InputAdornment> }}
                        />
                      </Grid>
                      <Grid size={{ xs: 12, sm: 4 }}>
                        <TextField
                          label="تعداد برندگان و تجلیل‌شدگان"
                          type="number"
                          size="small"
                          fullWidth
                          value={getFactValue('winners_count')}
                          onChange={e => setFactValue('winners_count', parseFloat(e.target.value) || 0, 'نفر', 'برندگان')}
                          InputProps={{ endAdornment: <InputAdornment position="end">نفر</InputAdornment> }}
                        />
                      </Grid>
                      <Grid size={{ xs: 12, sm: 4 }}>
                        <TextField
                          label="مسابقه تشویق به فرزندآوری (ماده ۲۸)"
                          type="number"
                          size="small"
                          fullWidth
                          value={getFactValue('contest_childbearing')}
                          onChange={e => setFactValue('contest_childbearing', parseFloat(e.target.value) || 0, 'مورد', 'ماده ۲۸')}
                          InputProps={{ endAdornment: <InputAdornment position="end">مورد</InputAdornment> }}
                        />
                      </Grid>
                      <Grid size={{ xs: 12, sm: 4 }}>
                        <TextField
                          label="جوایز و هدایای اهدایی"
                          type="number"
                          size="small"
                          fullWidth
                          value={getFactValue('awards_count')}
                          onChange={e => setFactValue('awards_count', parseFloat(e.target.value) || 0, 'فقره', 'جوایز')}
                          InputProps={{ endAdornment: <InputAdornment position="end">فقره</InputAdornment> }}
                        />
                      </Grid>
                    </Grid>
                  )}

                  {/* 5. CUSTOMER CARE (80601 - تشویق ارباب رجوع) */}
                  {activeProgramKind === 'customer_care' && (
                    <Grid container spacing={2}>
                      <Grid size={{ xs: 12, sm: 4 }}>
                        <TextField
                          label="تعداد کارکنان تشویق‌شده (نفر)"
                          type="number"
                          size="small"
                          fullWidth
                          value={getFactValue('honored_count')}
                          onChange={e => setFactValue('honored_count', parseFloat(e.target.value) || 0, 'نفر', 'کارکنان تشویق‌شده')}
                          InputProps={{ endAdornment: <InputAdornment position="end">نفر</InputAdornment> }}
                        />
                      </Grid>
                      <Grid size={{ xs: 12, sm: 4 }}>
                        <TextField
                          label="تعداد نشست‌ها و آیین‌های تشویق"
                          type="number"
                          size="small"
                          fullWidth
                          value={getFactValue('ceremony_count')}
                          onChange={e => setFactValue('ceremony_count', parseFloat(e.target.value) || 0, 'مراسم', 'جلسات تشویق')}
                          InputProps={{ endAdornment: <InputAdornment position="end">مراسم</InputAdornment> }}
                        />
                      </Grid>
                      <Grid size={{ xs: 12, sm: 4 }}>
                        <TextField
                          label="کارکنان اداری تشویق‌شده"
                          type="number"
                          size="small"
                          fullWidth
                          value={getFactValue('audience_administrative')}
                          onChange={e => setFactValue('audience_administrative', parseFloat(e.target.value) || 0, 'نفر', 'اداری')}
                          InputProps={{ endAdornment: <InputAdornment position="end">نفر</InputAdornment> }}
                        />
                      </Grid>
                      <Grid size={{ xs: 12, sm: 4 }}>
                        <TextField
                          label="کارکنان قضایی تشویق‌شده"
                          type="number"
                          size="small"
                          fullWidth
                          value={getFactValue('audience_judicial')}
                          onChange={e => setFactValue('audience_judicial', parseFloat(e.target.value) || 0, 'نفر', 'قضایی')}
                          InputProps={{ endAdornment: <InputAdornment position="end">نفر</InputAdornment> }}
                        />
                      </Grid>
                      <Grid size={{ xs: 12, sm: 4 }}>
                        <TextField
                          label="پذیرایی و ضیافت غذا"
                          type="number"
                          size="small"
                          fullWidth
                          value={getFactValue('reception')}
                          onChange={e => setFactValue('reception', parseFloat(e.target.value) || 0, 'وعده', 'پذیرایی')}
                          InputProps={{ endAdornment: <InputAdornment position="end">وعده</InputAdornment> }}
                        />
                      </Grid>
                    </Grid>
                  )}

                  {/* 6. CHARTER (80602 - منشور اخلاقی و رفتار حرفه‌ای) */}
                  {activeProgramKind === 'charter' && (
                    <Grid container spacing={2}>
                      <Grid size={{ xs: 12, sm: 4 }}>
                        <TextField
                          label="شرکت‌کنندگان دوره‌ها و کارگاه‌ها"
                          type="number"
                          size="small"
                          fullWidth
                          value={getFactValue('attendees')}
                          onChange={e => setFactValue('attendees', parseFloat(e.target.value) || 0, 'نفر', 'شرکت‌کنندگان منشور')}
                          InputProps={{ endAdornment: <InputAdornment position="end">نفر</InputAdornment> }}
                        />
                      </Grid>
                      <Grid size={{ xs: 12, sm: 4 }}>
                        <TextField
                          label="تعداد جلسات و نشست‌های تبیینی"
                          type="number"
                          size="small"
                          fullWidth
                          value={getFactValue('sessions')}
                          onChange={e => setFactValue('sessions', parseFloat(e.target.value) || 0, 'جلسه', 'جلسات منشور')}
                          InputProps={{ endAdornment: <InputAdornment position="end">جلسه</InputAdornment> }}
                        />
                      </Grid>
                      <Grid size={{ xs: 12, sm: 4 }}>
                        <TextField
                          label="توزیع منشور و دستنامه‌های رفتاری"
                          type="number"
                          size="small"
                          fullWidth
                          value={getFactValue('handbooks')}
                          onChange={e => setFactValue('handbooks', parseFloat(e.target.value) || 0, 'جلد', 'دستنامه‌ها')}
                          InputProps={{ endAdornment: <InputAdornment position="end">جلد</InputAdornment> }}
                        />
                      </Grid>
                      <Grid size={{ xs: 12, sm: 4 }}>
                        <TextField
                          label="پذیرایی و ضیافت"
                          type="number"
                          size="small"
                          fullWidth
                          value={getFactValue('reception')}
                          onChange={e => setFactValue('reception', parseFloat(e.target.value) || 0, 'وعده', 'پذیرایی')}
                          InputProps={{ endAdornment: <InputAdornment position="end">وعده</InputAdornment> }}
                        />
                      </Grid>
                    </Grid>
                  )}

                  {/* 7. TRIP (80404 - اردو و گردشگری) OR DEFAULT */}
                  {(activeProgramKind === 'trip' || (!['honor', 'ceremony', 'ceremonies', 'prayer', 'contest', 'contests', 'quran_contest', 'customer_care', 'charter'].includes(activeProgramKind))) && (
                    <Grid container spacing={2}>
                      <Grid size={{ xs: 12, sm: 4 }}>
                        <TextField
                          label="تعداد کل شرکت‌کنندگان (نفر)"
                          type="number"
                          size="small"
                          fullWidth
                          value={getFactValue('attendees')}
                          onChange={e => setFactValue('attendees', parseFloat(e.target.value) || 0, 'نفر', 'شرکت‌کنندگان کل')}
                          InputProps={{ endAdornment: <InputAdornment position="end">نفر</InputAdornment> }}
                        />
                      </Grid>

                      <Grid size={{ xs: 12, sm: 4 }}>
                        <TextField
                          label="نفرات اختصاصی همکاران"
                          type="number"
                          size="small"
                          fullWidth
                          value={getFactValue('trip_type_staff')}
                          onChange={e => setFactValue('trip_type_staff', parseFloat(e.target.value) || 0, 'نفر', 'همکاران')}
                          InputProps={{ endAdornment: <InputAdornment position="end">نفر</InputAdornment> }}
                        />
                      </Grid>

                      <Grid size={{ xs: 12, sm: 4 }}>
                        <TextField
                          label="نفرات اعضای خانواده"
                          type="number"
                          size="small"
                          fullWidth
                          value={getFactValue('trip_type_family')}
                          onChange={e => setFactValue('trip_type_family', parseFloat(e.target.value) || 0, 'نفر', 'اعضای خانواده')}
                          InputProps={{ endAdornment: <InputAdornment position="end">نفر</InputAdornment> }}
                        />
                      </Grid>

                      <Grid size={{ xs: 12, sm: 4 }}>
                        <TextField
                          label="ویژه مزدوجین سال اول ازدواج"
                          type="number"
                          size="small"
                          fullWidth
                          value={getFactValue('trip_type_marriage')}
                          onChange={e => setFactValue('trip_type_marriage', parseFloat(e.target.value) || 0, 'نفر', 'مزدوجین')}
                          InputProps={{ endAdornment: <InputAdornment position="end">نفر</InputAdornment> }}
                        />
                      </Grid>

                      <Grid size={{ xs: 12, sm: 4 }}>
                        <TextField
                          label="امتیاز / تعداد نظرسنجی اثربخشی"
                          type="number"
                          size="small"
                          fullWidth
                          value={getFactValue('survey')}
                          onChange={e => setFactValue('survey', parseFloat(e.target.value) || 0, 'عدد', 'نظرسنجی')}
                          InputProps={{ endAdornment: <InputAdornment position="end">نمره/تعداد</InputAdornment> }}
                        />
                      </Grid>

                      <Grid size={{ xs: 12, sm: 4 }}>
                        <TextField
                          label="وسیله نقلیه / اتوبوس هماهنگ‌شده"
                          type="number"
                          size="small"
                          fullWidth
                          value={getFactValue('vehicle')}
                          onChange={e => setFactValue('vehicle', parseFloat(e.target.value) || 0, 'دستگاه', 'هماهنگی خودرو')}
                          InputProps={{ endAdornment: <InputAdornment position="end">دستگاه</InputAdornment> }}
                        />
                      </Grid>

                      <Grid size={{ xs: 12, sm: 4 }}>
                        <TextField
                          label="بیمه‌نامه معتبر حوادث"
                          type="number"
                          size="small"
                          fullWidth
                          value={getFactValue('insurance')}
                          onChange={e => setFactValue('insurance', parseFloat(e.target.value) || 0, 'فقره', 'بیمه‌نامه')}
                          InputProps={{ endAdornment: <InputAdornment position="end">فقره</InputAdornment> }}
                        />
                      </Grid>

                      <Grid size={{ xs: 12, sm: 4 }}>
                        <TextField
                          label="پذیرایی و ضیافت غذا"
                          type="number"
                          size="small"
                          fullWidth
                          value={getFactValue('reception')}
                          onChange={e => setFactValue('reception', parseFloat(e.target.value) || 0, 'وعده', 'پذیرایی')}
                          InputProps={{ endAdornment: <InputAdornment position="end">وعده</InputAdornment> }}
                        />
                      </Grid>

                      <Grid size={{ xs: 12, sm: 4 }}>
                        <TextField
                          label="سین تفصیلی برنامه"
                          type="number"
                          size="small"
                          fullWidth
                          value={getFactValue('program_schedule')}
                          onChange={e => setFactValue('program_schedule', parseFloat(e.target.value) || 0, 'برنامه', 'سین برنامه')}
                          InputProps={{ endAdornment: <InputAdornment position="end">برگ</InputAdornment> }}
                        />
                      </Grid>
                    </Grid>
                  )}
                </Paper>

                {/* All Event Facts Table with Inline Edit & Delete */}
                <Paper variant="outlined" sx={{ p: 2, borderRadius: 2, bgcolor: 'background.paper' }}>
                  <Typography variant="subtitle2" fontWeight={800} color="text.secondary" sx={{ mb: 1.5 }}>
                    جدول کلیه فکت‌ها و سنجه‌های ثبت‌شده در پایگاه داده ({facts.length} ردیف):
                  </Typography>
                  <TableContainer sx={{ maxHeight: 260 }}>
                    <Table size="small">
                      <TableHead sx={{ bgcolor: 'action.hover' }}>
                        <TableRow>
                          <TableCell sx={{ fontWeight: 700 }}>شناسه سنجه (Metric)</TableCell>
                          <TableCell sx={{ fontWeight: 700, width: 140 }}>مقدار</TableCell>
                          <TableCell sx={{ fontWeight: 700, width: 100 }}>واحد سنجش</TableCell>
                          <TableCell sx={{ fontWeight: 700 }}>توضیحات</TableCell>
                          <TableCell sx={{ fontWeight: 700, width: 60 }} align="center">عملیات</TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {facts.map((f, i) => (
                          <TableRow key={i}>
                            <TableCell sx={{ fontFamily: 'monospace', fontWeight: 600 }}>{f.metric}</TableCell>
                            <TableCell>
                              <TextField
                                size="small"
                                type="number"
                                value={f.value}
                                onChange={e => {
                                  const val = parseFloat(e.target.value) || 0
                                  setFacts(prev => prev.map((item, idx) => idx === i ? { ...item, value: val } : item))
                                }}
                                sx={{ width: 110 }}
                              />
                            </TableCell>
                            <TableCell>{f.unit_of_measure}</TableCell>
                            <TableCell>{f.note || '—'}</TableCell>
                            <TableCell align="center">
                              <IconButton
                                size="small"
                                color="error"
                                onClick={() => removeFact(f.metric)}
                                title="حذف این سنجه"
                              >
                                <DeleteForeverRounded fontSize="small" />
                              </IconButton>
                            </TableCell>
                          </TableRow>
                        ))}
                        {facts.length === 0 && (
                          <TableRow>
                            <TableCell colSpan={5} align="center" sx={{ py: 2, color: 'text.secondary' }}>
                              هنوز سنجه‌ای ذخیره نشده است. با تنظیم فیلدهای بالا و ذخیره، اقلام اضافه خواهند شد.
                            </TableCell>
                          </TableRow>
                        )}
                      </TableBody>
                    </Table>
                  </TableContainer>

                  {/* Add Custom Fact inline */}
                  <Box sx={{ mt: 2, pt: 1.5, borderTop: 1, borderColor: 'divider' }}>
                    <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1} alignItems="center">
                      <TextField
                        size="small"
                        label="شناسه سنجه جدید (Metric)"
                        value={newCustomFactMetric}
                        onChange={e => setNewCustomFactMetric(e.target.value)}
                        placeholder="مثال: honored_count"
                        sx={{ flex: 1 }}
                      />
                      <TextField
                        size="small"
                        type="number"
                        label="مقدار"
                        value={newCustomFactValue}
                        onChange={e => setNewCustomFactValue(e.target.value)}
                        sx={{ width: 100 }}
                      />
                      <TextField
                        size="small"
                        label="واحد"
                        value={newCustomFactUnit}
                        onChange={e => setNewCustomFactUnit(e.target.value)}
                        sx={{ width: 90 }}
                      />
                      <Button
                        variant="outlined"
                        size="small"
                        disabled={!newCustomFactMetric.trim() || isNaN(Number(newCustomFactValue))}
                        onClick={() => {
                          if (!newCustomFactMetric.trim()) return
                          setFactValue(newCustomFactMetric.trim(), parseFloat(newCustomFactValue) || 0, newCustomFactUnit.trim() || 'count', 'دستی')
                          setNewCustomFactMetric('')
                          setNewCustomFactValue('')
                        }}
                      >
                        + افزودن سنجه
                      </Button>
                    </Stack>
                  </Box>
                </Paper>
              </Stack>
            )}

            {/* TAB 2: Photos & Documents Gallery */}
            {activeTab === 2 && (
              <Stack spacing={2.5}>
                {/* Upload Action Box */}
                <Paper variant="outlined" sx={{ p: 2, borderRadius: 2, bgcolor: 'background.paper' }}>
                  <Typography variant="subtitle2" fontWeight={800} color="primary" sx={{ mb: 1.5, display: 'flex', alignItems: 'center', gap: 1 }}>
                    <CloudUploadRounded fontSize="small" />
                    بارگذاری سریع عکس‌ها، فاکتورها، اسکن نظرسنجی و اسناد
                  </Typography>

                  <Grid container spacing={2} alignItems="center">
                    <Grid size={{ xs: 12, sm: 4 }}>
                      <FormControl size="small" fullWidth>
                        <InputLabel>نوع سند پیوست</InputLabel>
                        <Select
                          value={uploadKind}
                          label="نوع سند پیوست"
                          onChange={e => setUploadKind(e.target.value)}
                        >
                          <MenuItem value="image">تصویر و نگارخانه رویداد</MenuItem>
                          <MenuItem value="survey">اسکن فرم نظرسنجی</MenuItem>
                          <MenuItem value="invoice">فاکتور مالی و هزینه‌ها</MenuItem>
                          <MenuItem value="excel">لیست شرکت‌کنندگان (Excel)</MenuItem>
                          <MenuItem value="word">صورتجلسه و مکاتبات (Word)</MenuItem>
                          <MenuItem value="pdf">سند اداری / مجوز (PDF)</MenuItem>
                        </Select>
                      </FormControl>
                    </Grid>

                    <Grid size={{ xs: 12, sm: 4 }}>
                      <FormControlLabel
                        control={
                          <Switch
                            checked={uploadIsCover}
                            onChange={e => setUploadIsCover(e.target.checked)}
                          />
                        }
                        label={<Typography variant="body2">تعیین به عنوان عکس شاخص</Typography>}
                      />
                    </Grid>

                    <Grid size={{ xs: 12, sm: 4 }}>
                      <Button
                        component="label"
                        variant="contained"
                        color="primary"
                        fullWidth
                        size="small"
                        startIcon={uploadingDoc ? <CircularProgress size={16} color="inherit" /> : <CloudUploadRounded />}
                        disabled={uploadingDoc}
                      >
                        {uploadingDoc ? 'در حال ارسال سند...' : 'انتخاب و آپلود فایل'}
                        <input
                          type="file"
                          hidden
                          accept="image/*,.pdf,.doc,.docx,.xls,.xlsx"
                          onChange={handleFileInputChange}
                        />
                      </Button>
                    </Grid>
                  </Grid>
                </Paper>

                {/* Photo Gallery Grid */}
                <Paper variant="outlined" sx={{ p: 2, borderRadius: 2, bgcolor: 'background.paper' }}>
                  <Typography variant="subtitle2" fontWeight={800} color="primary" sx={{ mb: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
                    <PhotoLibraryRounded fontSize="small" />
                    نگارخانه تصاویر شاخص رویداد ({photosList.length} عکس)
                  </Typography>

                  {photosList.length === 0 ? (
                    <Box sx={{ p: 3, textAlign: 'center', color: 'text.secondary', bgcolor: 'action.hover', borderRadius: 2 }}>
                      <Typography variant="body2">هیچ تصویری برای این پرونده بارگذاری نشده است.</Typography>
                    </Box>
                  ) : (
                    <Grid container spacing={2}>
                      {photosList.map((doc: any) => (
                        <Grid size={{ xs: 12, sm: 6, md: 4 }} key={doc.document_id}>
                          <Card variant="outlined" sx={{ position: 'relative', borderRadius: 2, overflow: 'hidden' }}>
                            {doc.is_cover ? (
                              <Chip
                                size="small"
                                color="warning"
                                icon={<StarRounded />}
                                label="عکس شاخص رویداد"
                                sx={{ position: 'absolute', top: 8, right: 8, zIndex: 2, fontWeight: 800 }}
                              />
                            ) : null}

                            <Box
                              onClick={() => handlePreviewDoc(doc)}
                              sx={{
                                height: 160,
                                bgcolor: 'action.hover',
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                overflow: 'hidden',
                                cursor: 'pointer',
                                transition: 'transform 0.2s',
                                '&:hover': { opacity: 0.9 },
                              }}
                              title="کلیک جهت مشاهده تمام‌صفحه تصویر"
                            >
                              {doc.media_url ? (
                                <img
                                  src={doc.media_url}
                                  alt={doc.media_id}
                                  style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                                />
                              ) : (
                                <PhotoLibraryRounded sx={{ fontSize: 48, color: 'text.disabled' }} />
                              )}
                            </Box>

                            <CardContent sx={{ p: 1.5, pb: '12px !important' }}>
                              <Typography variant="caption" fontWeight={700} noWrap display="block" title={doc.media_id}>
                                {doc.media_id}
                              </Typography>
                              <Typography variant="caption" color="text.secondary" display="block">
                                حجم: {doc.size_bytes ? `${Math.round(doc.size_bytes / 1024)} KB` : 'نامشخص'}
                              </Typography>

                              <Stack direction="row" spacing={1} sx={{ mt: 1 }} justifyContent="space-between" alignItems="center">
                                {!doc.is_cover ? (
                                  <Button
                                    size="small"
                                    variant="outlined"
                                    color="warning"
                                    startIcon={<StarOutlineRounded />}
                                    onClick={() => handleSetCover(doc.document_id)}
                                    sx={{ fontSize: '0.7rem', py: 0.2 }}
                                  >
                                    عکس شاخص
                                  </Button>
                                ) : (
                                  <Chip size="small" color="success" icon={<CheckRounded />} label="شاخص" />
                                )}

                                <Stack direction="row" spacing={0.5}>
                                  <IconButton size="small" color="primary" onClick={() => handlePreviewDoc(doc)} title="مشاهده تمام‌صفحه تصویر">
                                    <VisibilityRounded fontSize="small" />
                                  </IconButton>
                                  <IconButton size="small" color="secondary" onClick={() => handleDownloadDoc(doc)} title="دانلود فایل اصلی تصویر">
                                    <DownloadRounded fontSize="small" />
                                  </IconButton>
                                  <IconButton
                                    size="small"
                                    color="error"
                                    onClick={() => handleDeleteDocument(doc.document_id, doc.media_id)}
                                    title="حذف تصویر"
                                  >
                                    <DeleteOutlineRounded fontSize="small" />
                                  </IconButton>
                                </Stack>
                              </Stack>
                            </CardContent>
                          </Card>
                        </Grid>
                      ))}
                    </Grid>
                  )}
                </Paper>

                {/* Documents & Attached Files List */}
                <Paper variant="outlined" sx={{ p: 2, borderRadius: 2, bgcolor: 'background.paper' }}>
                  <Typography variant="subtitle2" fontWeight={800} color="primary" sx={{ mb: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
                    <InsertDriveFileRounded fontSize="small" />
                    اسناد اداری، فاکتورها، اسکن‌های نظرسنجی و فایل‌های اکسل/ورد ({filesList.length} سند)
                  </Typography>

                  {filesList.length === 0 ? (
                    <Box sx={{ p: 3, textAlign: 'center', color: 'text.secondary', bgcolor: 'action.hover', borderRadius: 2 }}>
                      <Typography variant="body2">هیچ سند یا فایلی (PDF, Excel, Word, فاکتور) بارگذاری نشده است.</Typography>
                    </Box>
                  ) : (
                    <Stack spacing={1}>
                      {filesList.map((doc: any) => {
                        const isPdf = doc.kind === 'pdf' || doc.media_id?.endsWith('.pdf')
                        const isXls = doc.kind === 'excel' || doc.media_id?.match(/\.(xls|xlsx)$/i)
                        const isDoc = doc.kind === 'word' || doc.media_id?.match(/\.(doc|docx)$/i)

                        return (
                          <Paper
                            key={doc.document_id}
                            variant="outlined"
                            sx={{ p: 1.5, borderRadius: 1.5, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}
                          >
                            <Stack direction="row" spacing={1.5} alignItems="center">
                              {isPdf ? (
                                <PictureAsPdfRounded color="error" />
                              ) : isXls ? (
                                <TableChartRounded color="success" />
                              ) : isDoc ? (
                                <DescriptionRounded color="primary" />
                              ) : (
                                <InsertDriveFileRounded color="action" />
                              )}
                              <Box>
                                <Typography variant="body2" fontWeight={700}>
                                  {doc.media_id}
                                </Typography>
                                <Typography variant="caption" color="text.secondary">
                                  نوع: {doc.kind || 'سند'} | حجم: {doc.size_bytes ? `${Math.round(doc.size_bytes / 1024)} KB` : 'نامشخص'} | الحاق: {doc.added_at ? doc.added_at.slice(0, 10) : '—'}
                                </Typography>
                              </Box>
                            </Stack>

                            <Stack direction="row" spacing={1}>
                              <Button
                                size="small"
                                variant="outlined"
                                color="primary"
                                startIcon={<DownloadRounded />}
                                onClick={() => handleDownloadDoc(doc)}
                              >
                                دریافت سند
                              </Button>
                              <IconButton
                                size="small"
                                color="error"
                                onClick={() => handleDeleteDocument(doc.document_id, doc.media_id)}
                                title="حذف سند"
                              >
                                <DeleteOutlineRounded fontSize="small" />
                              </IconButton>
                            </Stack>
                          </Paper>
                        )
                      })}
                    </Stack>
                  )}
                </Paper>
              </Stack>
            )}

            {/* TAB 3: Eitaa Witnesses & Audit Log */}
            {activeTab === 3 && (
              <Stack spacing={2.5}>
                {/* Source Eitaa Witnesses */}
                <Paper variant="outlined" sx={{ p: 2, borderRadius: 2, bgcolor: 'background.paper' }}>
                  <Typography variant="subtitle2" fontWeight={800} color="info.main" sx={{ mb: 1.5, display: 'flex', alignItems: 'center', gap: 1 }}>
                    <LayersRounded fontSize="small" />
                    پیام‌ها و شواهد منبع پیام‌رسان ایتا ({rawEvent?.witnesses?.length || 0} پیام استخراج‌شده)
                  </Typography>

                  {(!rawEvent?.witnesses || rawEvent.witnesses.length === 0) ? (
                    <Box sx={{ p: 3, textAlign: 'center', color: 'text.secondary', bgcolor: 'action.hover', borderRadius: 2 }}>
                      <Typography variant="body2">هیچ شاهد پیام ایتایی به این گزارش قفل نشده است (ثبت مستقیم / تجمیعی).</Typography>
                    </Box>
                  ) : (
                    <Stack spacing={1}>
                      {rawEvent.witnesses.map((w: any, idx: number) => (
                        <Box key={w.link_id || idx} sx={{ p: 1.5, bgcolor: 'action.hover', borderRadius: 1.5, border: '1px solid', borderColor: 'divider' }}>
                          <Stack direction="row" spacing={1} justifyContent="space-between" alignItems="center">
                            <Stack direction="row" spacing={1} alignItems="center">
                              <Chip size="small" color="info" label={w.provider === 'eitaa' ? 'پیام ایتا' : (w.provider || 'ایتا')} />
                              <Typography variant="body2" fontWeight={700}>
                                شناسه گفتگو: {w.peer_id} | شماره پیام: #{w.message_id}
                              </Typography>
                            </Stack>
                            <Stack direction="row" spacing={1} alignItems="center">
                              <Chip size="small" variant="outlined" label={w.role === 'primary' ? 'شاهد اصلی' : 'شاهد پشتیبان'} />
                              {w.link_id && (
                                <Button
                                  size="small"
                                  color="error"
                                  variant="outlined"
                                  startIcon={<DeleteOutlineRounded fontSize="small" />}
                                  onClick={() => handleDetachWitness(w.link_id)}
                                  disabled={actionLoading}
                                  sx={{ fontSize: '0.7rem', py: 0.2, px: 1 }}
                                >
                                  جداسازی شاهد
                                </Button>
                              )}
                            </Stack>
                          </Stack>
                          <Stack direction="row" spacing={1.5} sx={{ mt: 1 }} alignItems="flex-start">
                            {w.media_url ? (
                              <Box
                                component="img"
                                src={w.media_url}
                                alt="شاهد تصویری"
                                sx={{
                                  width: 72,
                                  height: 72,
                                  objectFit: 'cover',
                                  borderRadius: 1.5,
                                  border: '1px solid',
                                  borderColor: 'divider',
                                  cursor: 'pointer',
                                  flexShrink: 0,
                                  transition: 'transform 0.15s',
                                  '&:hover': { transform: 'scale(1.04)', borderColor: 'primary.main' },
                                }}
                                onClick={() => setPreviewImageDoc({ url: w.media_url, title: `تصویر شاهد ایتا #${w.message_id}` })}
                              />
                            ) : null}
                            <Box sx={{ flex: 1, minWidth: 0 }}>
                              {w.text ? (
                                <Typography
                                  variant="body2"
                                  sx={{
                                    p: 1,
                                    borderRadius: 1,
                                    bgcolor: 'background.paper',
                                    border: '1px solid',
                                    borderColor: 'divider',
                                    mb: 0.75,
                                    whiteSpace: 'pre-wrap',
                                    maxHeight: 120,
                                    overflowY: 'auto',
                                    fontSize: '0.8rem',
                                    lineHeight: 1.6,
                                  }}
                                >
                                  {w.text}
                                </Typography>
                              ) : null}
                              {w.note && (
                                <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
                                  یادداشت استخراج: {w.note}
                                </Typography>
                              )}
                              <Typography variant="caption" color="text.disabled" sx={{ mt: 0.5, display: 'block' }}>
                                ثبت‌شده توسط: {w.linked_by || 'سیستم'} {w.linked_at ? `در ${w.linked_at}` : ''}
                              </Typography>
                            </Box>
                          </Stack>
                        </Box>
                      ))}
                    </Stack>
                  )}
                </Paper>

                {/* Audit Trail & History */}
                <Paper variant="outlined" sx={{ p: 2, borderRadius: 2, bgcolor: 'background.paper' }}>
                  <Typography variant="subtitle2" fontWeight={800} color="primary" sx={{ mb: 1.5, display: 'flex', alignItems: 'center', gap: 1 }}>
                    <AssignmentTurnedInRounded fontSize="small" />
                    تاریخچه تغییرات، ویراستاری و حسابرسی ({auditRecords.length} رکورد)
                  </Typography>

                  {auditRecords.length === 0 ? (
                    <Typography variant="caption" color="text.secondary">
                      سابقه حسابرسی ثبت‌نشده است.
                    </Typography>
                  ) : (
                    <TableContainer sx={{ maxHeight: 250 }}>
                      <Table size="small">
                        <TableHead sx={{ bgcolor: 'action.hover' }}>
                          <TableRow>
                            <TableCell sx={{ fontWeight: 700 }}>اقدام / رویداد</TableCell>
                            <TableCell sx={{ fontWeight: 700 }}>کاربر / کارشناس</TableCell>
                            <TableCell sx={{ fontWeight: 700 }}>تغییرات و جزئیات</TableCell>
                            <TableCell sx={{ fontWeight: 700 }}>زمان</TableCell>
                          </TableRow>
                        </TableHead>
                        <TableBody>
                          {auditRecords.map((rec: any, idx: number) => (
                            <TableRow key={rec.audit_id || idx}>
                              <TableCell sx={{ fontWeight: 700, fontFamily: 'monospace' }}>{rec.action}</TableCell>
                              <TableCell>{rec.actor}</TableCell>
                              <TableCell sx={{ fontSize: '0.75rem' }}>
                                {typeof rec.diff === 'object' ? JSON.stringify(rec.diff) : String(rec.diff || '—')}
                              </TableCell>
                              <TableCell sx={{ fontSize: '0.75rem', whiteSpace: 'nowrap' }}>
                                {rec.created_at ? rec.created_at.replace('T', ' ').slice(0, 19) : '—'}
                              </TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </TableContainer>
                  )}
                </Paper>
              </Stack>
            )}

            {/* TAB 4: Smart Merge & Deduplication */}
            {activeTab === 4 && (
              <Stack spacing={2.5}>
                <Paper variant="outlined" sx={{ p: 2, borderRadius: 2, bgcolor: 'background.paper' }}>
                  <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 1.5 }}>
                    <Box>
                      <Typography variant="subtitle2" fontWeight={800} color="primary" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <CallMergeRounded fontSize="small" />
                        فهرست گزارش‌های پیشنهادی جهت ادغام و یکپارچه‌سازی هوشمند
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        سامانه با تحلیل هوشمند همپوشانی شاخصه‌های جزئی، سرفصل برنامه، حوزه قضایی و نزدیکی زمانی رویدادها، موارد مشابه را رتبه‌بندی می‌کند.
                      </Typography>
                    </Box>
                    <Button
                      variant="outlined"
                      size="small"
                      startIcon={loadingMerge ? <CircularProgress size={14} color="inherit" /> : <RefreshRounded />}
                      onClick={loadMergeCandidates}
                      disabled={loadingMerge}
                    >
                      بروزرسانی پیشنهادات
                    </Button>
                  </Stack>

                  {loadingMerge ? (
                    <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
                      <CircularProgress size={32} />
                    </Box>
                  ) : mergeCandidates.length === 0 ? (
                    <Box sx={{ p: 4, textAlign: 'center', bgcolor: 'action.hover', borderRadius: 2 }}>
                      <CheckCircleOutlineRounded color="success" sx={{ fontSize: 40, mb: 1 }} />
                      <Typography variant="body2" fontWeight={700}>
                        هیچ گزارش مشابه یا تکراری برای این پرونده یافت نشد.
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        این پرونده از نظر شاخصه‌های جزئی و کلی مستقل و یکتا است.
                      </Typography>
                    </Box>
                  ) : (
                    <Stack spacing={1.5}>
                      {mergeCandidates.map((cand: any) => (
                        <Paper
                          key={cand.event_id}
                          variant="outlined"
                          sx={{
                            p: 2,
                            borderRadius: 2,
                            border: '1px solid',
                            borderColor: cand.score >= 50 ? 'primary.light' : 'divider',
                            bgcolor: cand.score >= 50 ? 'rgba(100, 181, 246, 0.08)' : 'background.paper',
                          }}
                        >
                          <Stack direction="row" justifyContent="space-between" alignItems="flex-start">
                            <Box sx={{ flex: 1, pr: 2 }}>
                              <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 0.5 }}>
                                <Typography variant="body2" fontWeight={800}>
                                  {cand.title}
                                </Typography>
                                <Chip
                                  size="small"
                                  color={cand.score >= 70 ? 'success' : cand.score >= 40 ? 'primary' : 'default'}
                                  label={`امتیاز همسانی: ${cand.score}`}
                                  sx={{ fontWeight: 800 }}
                                />
                                {Boolean(cand.macro_match) && (
                                  <Chip size="small" color="primary" variant="filled" label="شاخصه کلی (اولویت ۱)" sx={{ fontWeight: 700, fontSize: '0.7rem' }} />
                                )}
                                {cand.micro_sim_ratio > 0 && (
                                  <Chip size="small" color="secondary" variant="outlined" label={`همسانی جزئی ${Math.round(cand.micro_sim_ratio * 100)}٪ (اولویت ۲)`} sx={{ fontWeight: 600, fontSize: '0.7rem' }} />
                                )}
                                {cand.unit_match >= 2 && (
                                  <Chip size="small" color="success" variant="outlined" label="واحد قضایی (اولویت ۳)" sx={{ fontWeight: 600, fontSize: '0.7rem' }} />
                                )}
                                <Chip size="small" label={cand.event_id} sx={{ fontFamily: 'monospace' }} />
                              </Stack>

                              <Typography variant="caption" color="text.secondary" display="block">
                                حوزه: {cand.unit_name || '—'} | تاریخ: {cand.occurred_on || '—'} | وضعیت: {cand.review_status}
                              </Typography>

                              {cand.reasons && cand.reasons.length > 0 && (
                                <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap sx={{ mt: 1 }}>
                                  {cand.reasons.map((r: string, rIdx: number) => (
                                    <Chip key={rIdx} size="small" variant="outlined" color="info" label={r} sx={{ fontSize: '0.65rem' }} />
                                  ))}
                                </Stack>
                              )}
                            </Box>

                            <Button
                              variant="contained"
                              color="primary"
                              size="small"
                              startIcon={<CallMergeRounded />}
                              onClick={() => handleMergeCandidate(cand)}
                              disabled={actionLoading}
                            >
                              ادغام در این گزارش
                            </Button>
                          </Stack>
                        </Paper>
                      ))}
                    </Stack>
                  )}
                </Paper>
              </Stack>
            )}
          </Stack>
        )}
      </DialogContent>

      {/* Footer Actions */}
      <DialogActions sx={{ p: 2, justifyContent: 'space-between', bgcolor: 'background.paper', borderTop: '1px solid', borderColor: 'divider' }}>
        {/* Left Side: Danger Deletion & Manager Actions */}
        <Stack direction="row" spacing={1}>
          <Button
            variant="outlined"
            color="error"
            size="small"
            startIcon={<DeleteForeverRounded />}
            onClick={() => setDeleteConfirmOpen(true)}
            disabled={actionLoading || saving || loading}
          >
            حذف پرونده
          </Button>

          {reviewStatus !== 'approved' && (
            <Button
              variant="contained"
              color="success"
              size="small"
              startIcon={<CheckCircleOutlineRounded />}
              onClick={handleApprove}
              disabled={actionLoading || saving || loading}
            >
              تأیید نهایی
            </Button>
          )}

          {reviewStatus !== 'conflict' && (
            <Button
              variant="outlined"
              color="warning"
              size="small"
              startIcon={<WarningAmberRounded />}
              onClick={handleRequestRevision}
              disabled={actionLoading || saving || loading}
            >
              ارجاع جهت اصلاح
            </Button>
          )}

          {reviewStatus !== 'conflict' && (
            <Button
              variant="text"
              color="error"
              size="small"
              startIcon={<BlockRounded />}
              onClick={handleMarkConflict}
              disabled={actionLoading || saving || loading}
            >
              اعلام تعارض
            </Button>
          )}
        </Stack>

        {/* Right Side: Close, Submit & Save */}
        <Stack direction="row" spacing={1} alignItems="center">
          <Button onClick={onClose} color="inherit" size="small">
            بستن (انصراف)
          </Button>
          <Button
            variant="outlined"
            color="inherit"
            size="small"
            onClick={handleResetChanges}
            disabled={!isDirty || saving || actionLoading}
            title="لغو کلیه تغییرات اعمال شده و بازگردانی به مقادیر اولیه پرونده"
          >
            لغو تغییرات (عدم ذخیره)
          </Button>
          <Button
            variant="outlined"
            color="primary"
            size="small"
            startIcon={<SendRounded />}
            onClick={handleSubmitReview}
            disabled={actionLoading || saving || loading}
          >
            ارسال به مدیر
          </Button>
          <Button
            variant="contained"
            color="primary"
            size="small"
            startIcon={saving ? <CircularProgress size={16} color="inherit" /> : <SaveRounded />}
            onClick={handleSave}
            disabled={saving || loading || actionLoading}
          >
            ذخیره پرونده
          </Button>
        </Stack>
      </DialogActions>

      {/* Complete Event Deletion Confirmation Dialog */}
      <Dialog open={deleteConfirmOpen} onClose={() => setDeleteConfirmOpen(false)} maxWidth="xs" fullWidth dir="rtl">
        <DialogTitle sx={{ fontWeight: 800, color: 'error.main', display: 'flex', alignItems: 'center', gap: 1 }}>
          <DeleteForeverRounded />
          حذف کامل و قطعی پرونده رویداد
        </DialogTitle>
        <DialogContent dividers>
          <Typography variant="body2" sx={{ mb: 1 }}>
            آیا از حذف کامل پرونده رویداد <strong>"{occasion || eventId}"</strong> اطمینان دارید؟
          </Typography>
          <Alert severity="error" sx={{ mt: 1 }}>
            با حذف این پرونده، کلیه اسناد پیوست، فایل‌های تصویری، فکت‌های ثبت‌شده، محاسبات آماری و شواهد متصل به آن به طور دائمی پاکسازی خواهند شد. این عملیات غیرقابل بازگشت است.
          </Alert>
        </DialogContent>
        <DialogActions sx={{ p: 2, justifyContent: 'space-between' }}>
          <Button onClick={() => setDeleteConfirmOpen(false)} color="inherit" size="small">
            انصراف
          </Button>
          <Button
            variant="contained"
            color="error"
            size="small"
            startIcon={actionLoading ? <CircularProgress size={16} color="inherit" /> : <DeleteForeverRounded />}
            onClick={handleDeleteEvent}
            disabled={actionLoading}
          >
            بله، پرونده را حذف کن
          </Button>
        </DialogActions>
      </Dialog>

      {/* Image Lightbox Preview Dialog */}
      <Dialog
        open={Boolean(previewImageDoc)}
        onClose={() => setPreviewImageDoc(null)}
        maxWidth="md"
        fullWidth
        dir="rtl"
      >
        <DialogTitle sx={{ p: 1.5, bgcolor: 'background.paper', borderBottom: '1px solid', borderColor: 'divider' }}>
          <Stack direction="row" justifyContent="space-between" alignItems="center">
            <Typography variant="subtitle2" fontWeight={800} noWrap>
              {previewImageDoc?.title || 'پیش‌نمایش تصویر رویداد'}
            </Typography>
            <IconButton size="small" onClick={() => setPreviewImageDoc(null)}>
              <CloseRounded fontSize="small" />
            </IconButton>
          </Stack>
        </DialogTitle>
        <DialogContent sx={{ p: 2, textAlign: 'center', bgcolor: '#111827', display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
          {previewImageDoc?.url && (
            <img
              src={previewImageDoc.url}
              alt={previewImageDoc.title}
              style={{ maxWidth: '100%', maxHeight: '75vh', objectFit: 'contain', borderRadius: 4 }}
            />
          )}
        </DialogContent>
        <DialogActions sx={{ p: 1.5, bgcolor: 'background.paper', justifyContent: 'space-between' }}>
          <Button size="small" color="inherit" onClick={() => setPreviewImageDoc(null)}>
            بستن
          </Button>
          {previewImageDoc?.url && (
            <Button
              size="small"
              variant="contained"
              color="primary"
              startIcon={<DownloadRounded />}
              onClick={() => {
                const a = document.createElement('a')
                a.href = previewImageDoc.url
                a.download = previewImageDoc.title || 'event-photo.jpg'
                a.click()
              }}
            >
              دانلود تصویر
            </Button>
          )}
        </DialogActions>
      </Dialog>
    </Dialog>
  )
}