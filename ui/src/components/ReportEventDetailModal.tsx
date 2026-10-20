import React, { useEffect, useMemo, useState } from 'react'
import {
  Alert,
  Autocomplete,
  Box,
  Button,
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
  InputLabel,
  MenuItem,
  Paper,
  Select,
  Stack,
  Switch,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
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
import { api } from '../lib/api'
import { toast } from '../MaterialToast'
import {
  fetchMacroIndicators,
  fetchMicroIndicators,
  fetchProgramCatalog,
  type MicroIndicatorItem,
  type ProgramCatalogItem,
} from '../lib/indicators'
import { JalaliDateTimePicker } from './JalaliDateTimePicker'

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

export function ReportEventDetailModal({
  open,
  eventId,
  onClose,
  onSaved,
}: ReportEventDetailModalProps) {
  const [loading, setLoading] = useState<boolean>(false)
  const [saving, setSaving] = useState<boolean>(false)
  const [actionLoading, setActionLoading] = useState<boolean>(false)
  const [errorText, setErrorText] = useState<string>('')

  // Raw fetched event
  const [rawEvent, setRawEvent] = useState<Record<string, any> | null>(null)

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
  const [selectedPrograms, setSelectedPrograms] = useState<string[]>([])
  const [unitScope, setUnitScope] = useState<string>('provincial_hq')
  const [unitName, setUnitName] = useState<string>('')
  const [occurredOn, setOccurredOn] = useState<string>('')
  const [officialPresent, setOfficialPresent] = useState<boolean>(false)
  const [isAshuraPilgrimage, setIsAshuraPilgrimage] = useState<boolean>(false)
  const [notes, setNotes] = useState<string>('')

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
  const fetchEventData = async (id: string) => {
    try {
      setLoading(true)
      setErrorText('')
      const res = await api<{ ok: boolean; event: Record<string, any> }>(
        'GET',
        `/api/v3/reporting/events/${encodeURIComponent(id)}`,
      )
      const ev = res.event || {}
      setRawEvent(ev)

      setOccasion(ev.occasion || ev.custom_topic || '')
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
      setIsAshuraPilgrimage(Boolean(ev.is_ashura_pilgrimage))
      setNotes(ev.notes || '')
    } catch (err) {
      setErrorText(err instanceof Error ? err.message : 'خطا در بارگذاری اطلاعات گزارش')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (open && eventId) {
      void fetchEventData(eventId)
    } else {
      setRawEvent(null)
    }
  }, [open, eventId])

  // Save changes
  const handleSave = async () => {
    if (!eventId) return
    if (!occasion.trim()) {
      setErrorText('عنوان یا مناسبت رویداد نمی‌تواند خالی باشد.')
      return
    }
    try {
      setSaving(true)
      setErrorText('')
      await api('PUT', `/api/v3/reporting/events/${encodeURIComponent(eventId)}`, {
        if_match: rawEvent?.etag,
        fields: {
          occasion: occasion.trim(),
          macro_category: macroCategory,
          custom_topic: customTopic.trim(),
          macro_indicator: macroIndicator.trim(),
          micro_indicators: microIndicators,
          program_kinds: selectedPrograms,
          unit: unitScope,
          unit_name: unitName.trim(),
          occurred_on: occurredOn.trim(),
          official_present: officialPresent ? 1 : 0,
          is_ashura_pilgrimage: isAshuraPilgrimage ? 1 : 0,
          notes: notes.trim(),
        },
      })
      toast.success('تغییرات گزارش با موفقیت ذخیره شد.')
      onSaved?.()
      await fetchEventData(eventId)
    } catch (err) {
      setErrorText(err instanceof Error ? err.message : 'خطا در ذخیره تغییرات گزارش')
    } finally {
      setSaving(false)
    }
  }

  // Resubmit review
  const handleSubmitReview = async () => {
    if (!eventId) return
    try {
      setActionLoading(true)
      await handleSave()
      await api('POST', `/api/v3/reporting/events/${encodeURIComponent(eventId)}/submit-review`, {
        notes: 'اصلاحات انجام شد و گزارش مجدداً جهت بررسی نهایی مدیر ارسال گردید.',
      })
      toast.success('گزارش جهت بررسی نهایی برای مدیر ارسال شد.')
      onSaved?.()
      await fetchEventData(eventId)
    } catch (err) {
      setErrorText(err instanceof Error ? err.message : 'خطا در ارسال مجدد گزارش')
    } finally {
      setActionLoading(false)
    }
  }

  // Approve event (manager action)
  const handleApprove = async () => {
    if (!eventId) return
    try {
      setActionLoading(true)
      await api('POST', `/api/v3/reporting/events/${encodeURIComponent(eventId)}/approve`, {
        force_approve: true,
      })
      toast.success('گزارش با موفقیت تأیید شد.')
      onSaved?.()
      await fetchEventData(eventId)
    } catch (err) {
      setErrorText(err instanceof Error ? err.message : 'خطا در تأیید گزارش')
    } finally {
      setActionLoading(false)
    }
  }

  // Request revision (manager action)
  const handleRequestRevision = async () => {
    if (!eventId) return
    const reason = window.prompt('شرح نقص یا دستور اصلاح را وارد کنید:', rawEvent?.review_notes || '')
    if (reason === null) return
    if (!reason.trim()) {
      toast.error('شرح نقص الزامی است.')
      return
    }
    try {
      setActionLoading(true)
      await api('POST', `/api/v3/reporting/events/${encodeURIComponent(eventId)}/request-revision`, {
        reason: reason.trim(),
      })
      toast.warning('دستور اصلاح ثبت و گزارش به کارمند مربوطه ارجاع گردید.')
      onSaved?.()
      await fetchEventData(eventId)
    } catch (err) {
      setErrorText(err instanceof Error ? err.message : 'خطا در ثبت دستور اصلاح')
    } finally {
      setActionLoading(false)
    }
  }

  // Mark conflict
  const handleMarkConflict = async () => {
    if (!eventId) return
    const reason = window.prompt('علت رد یا تعارض این گزارش را وارد کنید:')
    if (reason === null) return
    if (!reason.trim()) {
      toast.error('علت رد الزامی است.')
      return
    }
    try {
      setActionLoading(true)
      await api('POST', `/api/v3/reporting/events/${encodeURIComponent(eventId)}/mark-conflict`, {
        reason: reason.trim(),
      })
      toast.info('گزارش به عنوان تعارض‌دار یا غیرقابل قبول ثبت گردید.')
      onSaved?.()
      await fetchEventData(eventId)
    } catch (err) {
      setErrorText(err instanceof Error ? err.message : 'خطا در ثبت تعارض')
    } finally {
      setActionLoading(false)
    }
  }

  const reviewStatus = rawEvent?.review_status || 'draft'
  const defectsList: Array<{ defect_code: string; title: string; description: string; severity: string }> =
    Array.isArray(rawEvent?.defects) ? rawEvent!.defects : []
  const factsList: Array<{ metric: string; value: any; value_kind: string; source: string }> =
    Array.isArray(rawEvent?.facts) ? rawEvent!.facts : []

  const statusLabel =
    reviewStatus === 'approved'
      ? 'تأیید نهایی مدیر'
      : reviewStatus === 'conflict'
      ? 'تعارض / رد شده'
      : reviewStatus === 'needs_review'
      ? (rawEvent?.revision_count ? `نیازمند بازبینی (اصلاحیه ${rawEvent.revision_count})` : 'در صف بازبینی')
      : 'پیش‌نویس اولیه'

  const statusColor: 'success' | 'error' | 'warning' | 'default' =
    reviewStatus === 'approved'
      ? 'success'
      : reviewStatus === 'conflict'
      ? 'error'
      : reviewStatus === 'needs_review'
      ? 'warning'
      : 'default'

  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle sx={{ m: 0, p: 2, display: 'flex', alignItems: 'center', justifyContent: 'space-between', bgcolor: 'primary.50' }}>
        <Stack direction="row" spacing={1.5} alignItems="center">
          <AssignmentTurnedInRounded color="primary" />
          <Box>
            <Typography variant="h6" fontWeight={800} color="primary.main">
              جزئیات و ویرایش پرونده گزارش
            </Typography>
            <Typography variant="caption" color="text.secondary">
              شناسه رویداد: {eventId || '—'}
            </Typography>
          </Box>
        </Stack>
        <Stack direction="row" spacing={1} alignItems="center">
          <Chip label={statusLabel} color={statusColor} size="small" sx={{ fontWeight: 700 }} />
          <IconButton onClick={onClose} size="small">
            <CloseRounded />
          </IconButton>
        </Stack>
      </DialogTitle>

      <DialogContent dividers sx={{ p: 2.5 }}>
        {loading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}>
            <CircularProgress />
          </Box>
        ) : (
          <Stack spacing={2.5}>
            {errorText && (
              <Alert severity="error" onClose={() => setErrorText('')}>
                {errorText}
              </Alert>
            )}

            {/* Defect Alerts / Manager Notes */}
            {(defectsList.length > 0 || rawEvent?.review_notes) && (
              <Paper
                variant="outlined"
                sx={{
                  p: 2,
                  borderRadius: 2,
                  bgcolor: defectsList.some(d => d.severity === 'blocker') ? 'error.50' : 'warning.50',
                  borderColor: defectsList.some(d => d.severity === 'blocker') ? 'error.main' : 'warning.main',
                }}
              >
                <Stack spacing={1}>
                  <Stack direction="row" spacing={1} alignItems="center">
                    <WarningAmberRounded color={defectsList.some(d => d.severity === 'blocker') ? 'error' : 'warning'} />
                    <Typography variant="subtitle2" fontWeight={800}>
                      هشدارها و نقایص گزارش‌گیری / دستور اصلاح مدیر
                    </Typography>
                  </Stack>
                  {rawEvent?.review_notes && (
                    <Typography variant="body2" sx={{ fontWeight: 600 }}>
                      <strong>شرح دستور اصلاح:</strong> {rawEvent.review_notes}
                    </Typography>
                  )}
                  {defectsList.map((d, idx) => (
                    <Typography key={idx} variant="caption" display="block" color={d.severity === 'blocker' ? 'error.main' : 'warning.dark'}>
                      • {d.title}: {d.description}
                    </Typography>
                  ))}
                </Stack>
              </Paper>
            )}

            {/* Basic Information Form */}
            <Paper variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
              <Typography variant="subtitle2" fontWeight={800} color="primary" sx={{ mb: 1.5, display: 'flex', alignItems: 'center', gap: 1 }}>
                <EventNoteRounded fontSize="small" />
                اطلاعات اصلی رویداد فرهنگی
              </Typography>

              <Grid container spacing={2}>
                <Grid size={{ xs: 12 }}>
                  <TextField
                    label="عنوان / مناسبت رویداد"
                    size="small"
                    fullWidth
                    value={occasion}
                    onChange={e => setOccasion(e.target.value)}
                    placeholder="مثال: برگزاری محفل قرآنی و ضیافت افطار همکاران"
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
                        const p = programsCatalog.find(x => x.kind === opt || x.program_code === opt)
                        return p ? `${p.program_code} - ${p.title}` : opt
                      }}
                      value={selectedPrograms}
                      onChange={(_e, val) => setSelectedPrograms(val)}
                      renderTags={(value, getTagProps) =>
                        value.map((option, index) => {
                          const p = programsCatalog.find(x => x.kind === option || x.program_code === option)
                          return (
                            <Chip
                              {...getTagProps({ index })}
                              key={option}
                              label={p ? `${p.program_code} - ${p.title}` : option}
                              size="small"
                              color="secondary"
                            />
                          )
                        })
                      }
                      renderInput={params => (
                        <TextField
                          {...params}
                          size="small"
                          label="برنامه‌ها / کاربرگ‌های متناظر"
                          placeholder="انتخاب سرفصل یا کاربرگ..."
                        />
                      )}
                    />
                  </Grid>
                )}

                <Grid size={{ xs: 12, sm: 6 }}>
                  <FormControl size="small" fullWidth>
                    <InputLabel>شاخصه کلان فرهنگی</InputLabel>
                    <Select
                      value={macroIndicator}
                      label="شاخصه کلان فرهنگی"
                      onChange={e => setMacroIndicator(e.target.value)}
                    >
                      <MenuItem value="">
                        <em>(بدون انتخاب / نامشخص)</em>
                      </MenuItem>
                      {macroOptions.map(m => (
                        <MenuItem key={m} value={m}>
                          {m}
                        </MenuItem>
                      ))}
                    </Select>
                  </FormControl>
                </Grid>

                <Grid size={{ xs: 12, sm: 6 }}>
                  <Autocomplete
                    multiple
                    freeSolo
                    options={microOptions.map(o => o.title)}
                    value={microIndicators}
                    onChange={(_e, val) => setMicroIndicators(val)}
                    renderTags={(value, getTagProps) =>
                      value.map((option, index) => (
                        <Chip
                          {...getTagProps({ index })}
                          key={option}
                          label={option}
                          size="small"
                          color="primary"
                          variant="outlined"
                        />
                      ))
                    }
                    renderInput={params => (
                      <TextField
                        {...params}
                        size="small"
                        label="شاخصه‌های جزئی (چندانتخابی)"
                        placeholder="انتخاب یا تایپ عنوان جدید..."
                      />
                    )}
                  />
                </Grid>

                <Grid size={{ xs: 12, sm: 6 }}>
                  <FormControl size="small" fullWidth>
                    <InputLabel>نوع حوزه / رده سازمانی</InputLabel>
                    <Select
                      value={unitScope}
                      label="نوع حوزه / رده سازمانی"
                      onChange={e => setUnitScope(e.target.value)}
                    >
                      {UNIT_SCOPES.map(u => (
                        <MenuItem key={u.value} value={u.value}>
                          {u.label}
                        </MenuItem>
                      ))}
                    </Select>
                  </FormControl>
                </Grid>

                <Grid size={{ xs: 12, sm: 6 }}>
                  <Autocomplete
                    freeSolo
                    options={judicialUnits.map(u => u.display_name || u.name)}
                    value={unitName}
                    onInputChange={(_e, val) => setUnitName(val)}
                    renderInput={params => (
                      <TextField
                        {...params}
                        size="small"
                        label="نام حوزه قضایی / واحد سازمانی"
                        placeholder="مثال: دادگستری شهرستان ساری"
                      />
                    )}
                  />
                </Grid>

                <Grid size={{ xs: 12, sm: 6 }}>
                  <JalaliDateTimePicker
                    value={occurredOn}
                    onChange={val => setOccurredOn(val)}
                    label="تاریخ و زمان وقوع"
                  />
                </Grid>

                <Grid size={{ xs: 12, sm: 6 }}>
                  <Stack direction="row" spacing={1} sx={{ mt: 0.5 }}>
                    <FormControlLabel
                      control={
                        <Switch
                          size="small"
                          checked={officialPresent}
                          onChange={e => setOfficialPresent(e.target.checked)}
                        />
                      }
                      label={<Typography variant="body2">حضور مقام قضایی / مسئولین</Typography>}
                    />
                    <FormControlLabel
                      control={
                        <Switch
                          size="small"
                          color="secondary"
                          checked={isAshuraPilgrimage}
                          onChange={e => setIsAshuraPilgrimage(e.target.checked)}
                        />
                      }
                      label={<Typography variant="body2">قرائت زیارت عاشورا (C12)</Typography>}
                    />
                  </Stack>
                </Grid>

                <Grid size={{ xs: 12 }}>
                  <TextField
                    label="توضیحات و مستندات تکمیلی"
                    size="small"
                    fullWidth
                    multiline
                    rows={2}
                    value={notes}
                    onChange={e => setNotes(e.target.value)}
                    placeholder="شرح جزئیات، بازخوردها و نکات مهم اجرایی..."
                  />
                </Grid>
              </Grid>
            </Paper>

            {/* Facts and Dimensions */}
            {factsList.length > 0 && (
              <Paper variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
                <Typography variant="subtitle2" fontWeight={800} color="secondary.main" sx={{ mb: 1, display: 'flex', alignItems: 'center', gap: 1 }}>
                  <LayersRounded fontSize="small" />
                  سنجه‌های آماری استخراج‌شده رویداد ({factsList.length} سنجه)
                </Typography>
                <TableContainer sx={{ maxHeight: 180 }}>
                  <Table size="small">
                    <TableHead>
                      <TableRow>
                        <TableCell sx={{ fontWeight: 700 }}>نام سنجه / ستون</TableCell>
                        <TableCell sx={{ fontWeight: 700 }}>مقدار</TableCell>
                        <TableCell sx={{ fontWeight: 700 }}>نوع داده</TableCell>
                        <TableCell sx={{ fontWeight: 700 }}>منبع استخراج</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {factsList.map((f, idx) => (
                        <TableRow key={idx}>
                          <TableCell sx={{ fontFamily: 'monospace', fontWeight: 600 }}>{f.metric}</TableCell>
                          <TableCell>
                            <Chip size="small" label={String(f.value)} variant="outlined" />
                          </TableCell>
                          <TableCell>{f.value_kind}</TableCell>
                          <TableCell>{f.source || 'ثبت سیستمی'}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              </Paper>
            )}

            {/* Eitaa Source Witnesses */}
            {rawEvent?.witnesses && rawEvent.witnesses.length > 0 && (
              <Paper variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
                <Typography variant="subtitle2" fontWeight={800} color="info.main" sx={{ mb: 1, display: 'flex', alignItems: 'center', gap: 1 }}>
                  <LayersRounded fontSize="small" />
                  شواهد و پیام‌های منبع ایتا ({rawEvent.witnesses.length} پیام منبع)
                </Typography>
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
                        <Chip size="small" variant="outlined" label={w.role === 'primary' ? 'شاهد اصلی' : 'شاهد پشتیبان'} />
                      </Stack>
                      {w.note && (
                        <Typography variant="caption" color="text.secondary" sx={{ mt: 0.5, display: 'block' }}>
                          یادداشت استخراج: {w.note}
                        </Typography>
                      )}
                      <Typography variant="caption" color="text.disabled" sx={{ mt: 0.5, display: 'block' }}>
                        ثبت‌شده توسط: {w.linked_by || 'سیستم'} {w.linked_at ? `در ${w.linked_at}` : ''}
                      </Typography>
                    </Box>
                  ))}
                </Stack>
              </Paper>
            )}

            {/* Workflow and Registration Audit Info */}
            <Paper variant="outlined" sx={{ p: 1.5, borderRadius: 2, bgcolor: 'action.hover' }}>
              <Grid container spacing={1}>
                <Grid size={{ xs: 12, sm: 4 }}>
                  <Typography variant="caption" color="text.secondary" display="block">
                    ثبت‌کننده اولیه:
                  </Typography>
                  <Typography variant="body2" fontWeight={600}>
                    {rawEvent?.registered_by_name || rawEvent?.created_by || 'سیستم'}
                  </Typography>
                </Grid>
                <Grid size={{ xs: 12, sm: 4 }}>
                  <Typography variant="caption" color="text.secondary" display="block">
                    آخرین بررسی‌کننده:
                  </Typography>
                  <Typography variant="body2" fontWeight={600}>
                    {rawEvent?.reviewed_by_name || 'هنوز بررسی نشده'}
                  </Typography>
                </Grid>
                <Grid size={{ xs: 12, sm: 4 }}>
                  <Typography variant="caption" color="text.secondary" display="block">
                    دفعات ویرایش و اصلاحیه:
                  </Typography>
                  <Typography variant="body2" fontWeight={600}>
                    {rawEvent?.revision_count || 0} نوبت
                  </Typography>
                </Grid>
              </Grid>
            </Paper>
          </Stack>
        )}
      </DialogContent>

      <DialogActions sx={{ p: 2, justifyContent: 'space-between' }}>
        <Stack direction="row" spacing={1}>
          {reviewStatus !== 'approved' && (
            <Button
              variant="contained"
              color="success"
              size="small"
              startIcon={<CheckCircleOutlineRounded />}
              onClick={handleApprove}
              disabled={actionLoading || saving || loading}
            >
              تأیید نهایی پرونده
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
              اعلام تعارض / رد
            </Button>
          )}
        </Stack>

        <Stack direction="row" spacing={1}>
          <Button onClick={onClose} color="inherit" size="small">
            بستن
          </Button>
          <Button
            variant="outlined"
            color="primary"
            size="small"
            startIcon={<SendRounded />}
            onClick={handleSubmitReview}
            disabled={actionLoading || saving || loading}
          >
            ارسال مجدد به کارتابل مدیر
          </Button>
          <Button
            variant="contained"
            color="primary"
            size="small"
            startIcon={saving ? <CircularProgress size={16} color="inherit" /> : <SaveRounded />}
            onClick={handleSave}
            disabled={saving || loading || actionLoading}
          >
            ذخیره تغییرات
          </Button>
        </Stack>
      </DialogActions>
    </Dialog>
  )
}
