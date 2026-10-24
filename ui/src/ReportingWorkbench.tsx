import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Alert,
  Autocomplete,
  Badge,
  Box,
  Button,
  Card,
  CardActions,
  CardContent,
  CardHeader,
  Checkbox,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  FormControl,
  FormControlLabel,
  FormLabel,
  Grid,
  IconButton,
  InputLabel,
  LinearProgress,
  MenuItem,
  Paper,
  Radio,
  RadioGroup,
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
import AddCircleOutlineRounded from '@mui/icons-material/AddCircleOutlineRounded'
import BarChartRounded from '@mui/icons-material/BarChartRounded'
import AssignmentTurnedInRounded from '@mui/icons-material/AssignmentTurnedInRounded'
import AutoAwesomeRounded from '@mui/icons-material/AutoAwesomeRounded'
import CheckCircleOutlineRounded from '@mui/icons-material/CheckCircleOutlineRounded'
import CloseRounded from '@mui/icons-material/CloseRounded'
import DeleteOutlineRounded from '@mui/icons-material/DeleteOutlineRounded'
import EditRounded from '@mui/icons-material/EditRounded'
import FormatListBulletedRounded from '@mui/icons-material/FormatListBulletedRounded'
import DescriptionOutlined from '@mui/icons-material/DescriptionOutlined'
import EventNoteRounded from '@mui/icons-material/EventNoteRounded'
import FileDownloadRounded from '@mui/icons-material/FileDownloadRounded'
import FolderZipRounded from '@mui/icons-material/FolderZipRounded'
import LayersRounded from '@mui/icons-material/LayersRounded'
import MenuBookRounded from '@mui/icons-material/MenuBookRounded'
import PolicyRounded from '@mui/icons-material/PolicyRounded'
import RefreshRounded from '@mui/icons-material/RefreshRounded'
import SaveRounded from '@mui/icons-material/SaveRounded'
import SettingsRounded from '@mui/icons-material/SettingsRounded'
import SummarizeRounded from '@mui/icons-material/SummarizeRounded'
import VisibilityRounded from '@mui/icons-material/VisibilityRounded'
import WarningAmberRounded from '@mui/icons-material/WarningAmberRounded'
import { api, ApiError } from './lib/api'
import OfficeDashboard from './OfficeDashboard'
import { toast } from './MaterialToast'
import { jalaliDayLabel } from './utils/jalali'
import { formatJalaliDate } from './utils/jalaliDateTime'
import { JalaliDatePicker, JalaliDateRangePicker } from './components/JalaliDatePicker'
import { ReportEventDetailModal } from './components/ReportEventDetailModal'
import { JudicialUnitsManagementModal } from './components/JudicialUnitsManagementModal'
import {
  fetchMacroIndicators,
  fetchMicroIndicators,
  fetchProgramCatalog,
  type MicroIndicatorItem,
  type ProgramCatalogItem,
} from './lib/indicators'

export interface CandidateItem {
  candidate_id: string
  dialog_label: string
  platform: string
  peer_id: string
  top_message_id: number
  message_ref: string
  matched_programs: string[]
  candidate_kind: string
  attendee_count: number | null
  confidence: number
  unit_hints: string[]
  status: 'pending' | 'approved' | 'rejected'
  suggested_at: string
  indexed_at: string
  rejection_reason?: string
  reviewed_by?: string
  review_notes?: string
}

export interface FormQuestion {
  key: string
  label: string
  qtype: 'count' | 'text' | 'bool' | 'choice' | 'attendees' | 'currency'
  star: boolean
  human_gate: boolean
  choices: string[]
  auto_from: string
  current_value: any
}

export interface FormSummary {
  program_id: string
  program_code?: string
  title: string
  operational_description?: string
  monitoring_criteria?: string[]
  policy_framework?: string
  questions: FormQuestion[]
  unresolved_star: string[]
  unresolved_human_gate: string[]
}

export interface MandateItem {
  mandate_id: string
  program_code: string
  kind: string
  title: string
  number: string
  issued_on: string
  document_ref: string
  notes: string
}

export const MANDATE_KIND_LABELS: Record<string, string> = {
  circular: 'بخشنامه',
  directive: 'دستورالعمل',
  guideline: 'شیوه‌نامه',
  correspondence: 'مکاتبه اداری',
  resolution: 'مصوبه',
  agreement: 'تفاهم‌نامه',
  policy: 'سیاست کلی',
  transformation_doc: 'سند تحول',
  law: 'قانون / آیین‌نامه',
}

export interface EventFact {
  metric: string
  value: any
  value_kind: string
  source: string
  created_by: string
}

export interface ReportedEventItem {
  event_id: string
  program_kinds: string[]
  occurred_on: string
  unit: string
  unit_name: string
  occasion: string
  occasion_class?: string | null
  official_present: boolean | null
  is_ashura_pilgrimage: boolean
  macro_category?: 'workbook_approved' | 'other_cultural'
  custom_topic?: string
  created_by: string
  review_status?: 'draft' | 'needs_review' | 'approved' | 'conflict'
  registered_by_id?: string
  registered_by_name?: string
  reviewed_by_id?: string
  reviewed_by_name?: string
  reviewed_at?: string | null
  review_notes?: string
  revision_count?: number
  defects?: Array<{
    defect_code: string
    severity: 'blocker' | 'warning' | 'info'
    title: string
    description: string
    field_name: string
  }>
  facts: EventFact[]
  notes?: string
  macro_indicator?: string
  micro_indicators?: string[]
}

export interface DialogTargetConfig {
  label: string
  match_keywords: string[]
  enabled: boolean
}

export interface ExportAuditItem {
  export_id: string
  file_name: string
  destination: string
  exported_by: string
  exported_at: string
  events_count: number
  sha256?: string
  unresolved_star_count?: number
}

export const PROGRAM_NAMES: Record<string, string> = {
  trip: '80401 - اردو',
  contest: '80402 - مسابقات',
  ceremonies: '80403 - مراسم مذهبی، ملی و انقلابی',
  prayer: '80501 - ترویج و توسعه فرهنگ اقامه نماز',
  honor: '80406 - تکریم و تجلیل',
  customer_care: '80601 - تشویق ارباب رجوع',
  charter: '80202 - منشور اخلاقی',
  narrative: '80000 - قالب گزارش عملکرد (روایی-مالی)',
}

export interface ProgramBadgeStyle {
  bg: string
  color: string
  border: string
  dot: string
}

export const PROGRAM_STYLES: Record<string, ProgramBadgeStyle> = {
  prayer: { bg: '#ecfdf5', color: '#065f46', border: '#a7f3d0', dot: '#10b981' },
  '80501': { bg: '#ecfdf5', color: '#065f46', border: '#a7f3d0', dot: '#10b981' },
  contest: { bg: '#ecfeff', color: '#155e75', border: '#a5f3fc', dot: '#06b6d4' },
  '80402': { bg: '#ecfeff', color: '#155e75', border: '#a5f3fc', dot: '#06b6d4' },
  quran_competitions: { bg: '#ecfeff', color: '#155e75', border: '#a5f3fc', dot: '#06b6d4' },
  trip: { bg: '#fffbeb', color: '#92400e', border: '#fde68a', dot: '#f59e0b' },
  '80401': { bg: '#fffbeb', color: '#92400e', border: '#fde68a', dot: '#f59e0b' },
  ceremonies: { bg: '#f5f3ff', color: '#5b21b6', border: '#ddd6fe', dot: '#8b5cf6' },
  '80403': { bg: '#f5f3ff', color: '#5b21b6', border: '#ddd6fe', dot: '#8b5cf6' },
  honor: { bg: '#fff1f2', color: '#9f1239', border: '#fecdd3', dot: '#f43f5e' },
  '80406': { bg: '#fff1f2', color: '#9f1239', border: '#fecdd3', dot: '#f43f5e' },
  appreciation: { bg: '#fff1f2', color: '#9f1239', border: '#fecdd3', dot: '#f43f5e' },
  customer_care: { bg: '#fef2f2', color: '#b91c1c', border: '#fca5a5', dot: '#ef4444' },
  '80601': { bg: '#fef2f2', color: '#b91c1c', border: '#fca5a5', dot: '#ef4444' },
  charter: { bg: '#eff6ff', color: '#1e40af', border: '#bfdbfe', dot: '#3b82f6' },
  '80202': { bg: '#eff6ff', color: '#1e40af', border: '#bfdbfe', dot: '#3b82f6' },
  marriage: { bg: '#fdf4ff', color: '#86198f', border: '#f5d0fe', dot: '#d946ef' },
  narrative: { bg: '#f0fdf4', color: '#166534', border: '#bbf7d0', dot: '#22c55e' },
  '80000': { bg: '#f0fdf4', color: '#166534', border: '#bbf7d0', dot: '#22c55e' },
  other_cultural: { bg: '#f8fafc', color: '#334155', border: '#cbd5e1', dot: '#64748b' },
}

const FALLBACK_STYLES: ProgramBadgeStyle[] = [
  { bg: '#fef3c7', color: '#78350f', border: '#fde68a', dot: '#d97706' },
  { bg: '#e0e7ff', color: '#312e81', border: '#c7d2fe', dot: '#4f46e5' },
  { bg: '#fce7f3', color: '#831843', border: '#fbcfe8', dot: '#db2777' },
  { bg: '#dcfce7', color: '#14532d', border: '#bbf7d0', dot: '#16a34a' },
  { bg: '#ffedd5', color: '#7c2d12', border: '#fed7aa', dot: '#ea580c' },
  { bg: '#e0f2fe', color: '#0c4a6e', border: '#bae6fd', dot: '#0284c7' },
]

export function getProgramBadgeStyle(code: string): ProgramBadgeStyle {
  if (!code) return PROGRAM_STYLES.other_cultural
  if (PROGRAM_STYLES[code]) return PROGRAM_STYLES[code]
  let hash = 0
  for (let i = 0; i < code.length; i++) hash = (hash << 5) - hash + code.charCodeAt(i)
  const idx = Math.abs(hash) % FALLBACK_STYLES.length
  return FALLBACK_STYLES[idx]
}

export function formatDisplayJalaliDate(dateStr?: string): string {
  if (!dateStr) return '—'
  const trimmed = String(dateStr).trim()
  if (trimmed.startsWith('14') || trimmed.startsWith('13')) {
    return trimmed.replace(/-/g, '/')
  }
  try {
    return formatJalaliDate(trimmed)
  } catch {
    return trimmed
  }
}


const UNIT_SCOPES: Array<{ value: string; label: string }> = [
  { value: 'provincial_hq', label: 'ستاد دادگستری کل استان' },
  { value: 'courthouse', label: 'دادگستری / حوزه قضایی شهرستان' },
  { value: 'special_council', label: 'شورای حل اختلاف' },
  { value: 'province_wide', label: 'استانی / مشترک' },
]

function SheetSpecificDimensions({
  program,
  facts,
  onChange,
}: {
  program: string
  facts: Record<string, any>
  onChange: (key: string, value: any) => void
}) {
  const setFact = (k: string, v: any) => onChange(k, v)
  const toggleFact = (k: string) => onChange(k, facts[k] ? 0 : 1)

  return (
    <Paper
      variant="outlined"
      sx={{
        p: 2,
        borderRadius: 2,
        bgcolor: 'action.hover',
        borderStyle: 'dashed',
        borderColor: 'primary.main',
      }}
    >
      <Stack spacing={1.5}>
        <Stack direction="row" spacing={1} alignItems="center">
          <LayersRounded fontSize="small" color="primary" />
          <Typography variant="subtitle2" fontWeight={800} color="primary.main">
            ابعاد و سنجه‌های اختصاصی: {PROGRAM_NAMES[program] || program}
          </Typography>
        </Stack>
        <Typography variant="caption" color="text.secondary">
          این مقادیر مستقیماً در ستون‌های تخصصی این شیت در کاربرگ و خروجی گزارش ۱۴۰۵ لحاظ خواهند شد.
        </Typography>
        <Divider sx={{ my: 0.5 }} />

        {/* 1. TRIP */}
        {program === 'trip' && (
          <Stack spacing={2}>
            <Box>
              <FormLabel component="legend" sx={{ fontSize: '0.8rem', fontWeight: 700, mb: 0.5 }}>
                جامعه هدف و نوع اردو:
              </FormLabel>
              <RadioGroup
                row
                value={
                  facts.trip_type_marriage ? 'marriage' : facts.trip_type_family ? 'family' : 'staff'
                }
                onChange={e => {
                  const val = e.target.value
                  onChange('trip_type_staff', val === 'staff' ? 1 : 0)
                  onChange('trip_type_family', val === 'family' ? 1 : 0)
                  onChange('trip_type_marriage', val === 'marriage' ? 1 : 0)
                }}
              >
                <FormControlLabel value="staff" control={<Radio size="small" />} label={<Typography variant="body2">کارکنان (اداری/قضایی)</Typography>} />
                <FormControlLabel value="family" control={<Radio size="small" />} label={<Typography variant="body2">خانواده کارکنان</Typography>} />
                <FormControlLabel value="marriage" control={<Radio size="small" />} label={<Typography variant="body2">فرزندآوری و ازدواج</Typography>} />
              </RadioGroup>
            </Box>

            <Box>
              <Typography variant="caption" fontWeight={700} color="text.secondary" gutterBottom>
                فرایندها و الزامات اجرایی اردو:
              </Typography>
              <Grid container spacing={1}>
                {[
                  { key: 'mou_count', label: 'انعقاد تفاهم‌نامه' },
                  { key: 'announcement_count', label: 'اطلاع‌رسانی (پوستر/گروه)' },
                  { key: 'list_count', label: 'تنظیم لیست شرکت‌کنندگان' },
                  { key: 'schedule_count', label: 'سین برنامه تفصیلی' },
                  { key: 'vehicle_count', label: 'هماهنگی خودرو/اتوبوس' },
                  { key: 'insurance_count', label: 'پوشش کامل بیمه حوادث' },
                  { key: 'reception_count', label: 'پذیرایی' },
                ].map(item => (
                  <Grid size={{ xs: 12, sm: 6 }} key={item.key}>
                    <FormControlLabel
                      control={<Checkbox size="small" checked={Boolean(facts[item.key])} onChange={() => toggleFact(item.key)} />}
                      label={<Typography variant="body2">{item.label}</Typography>}
                    />
                  </Grid>
                ))}
              </Grid>
            </Box>
          </Stack>
        )}

        {/* 2. CONTEST */}
        {program === 'contest' && (
          <Stack spacing={2}>
            <Box>
              <FormLabel component="legend" sx={{ fontSize: '0.8rem', fontWeight: 700, mb: 0.5 }}>
                رده مسابقه:
              </FormLabel>
              <RadioGroup
                row
                value={facts.is_quran ? 'quran' : 'cultural'}
                onChange={e => onChange('is_quran', e.target.value === 'quran')}
              >
                <FormControlLabel value="cultural" control={<Radio size="small" />} label={<Typography variant="body2">فرهنگی / ورزشی / هنری</Typography>} />
                <FormControlLabel value="quran" control={<Radio size="small" />} label={<Typography variant="body2">مسابقات قرآن و عترت</Typography>} />
              </RadioGroup>
            </Box>

            {facts.is_quran ? (
              <Stack spacing={1.5}>
                <TextField
                  size="small"
                  fullWidth
                  type="number"
                  label="تعداد شرکت‌کنندگان مسابقات قرآنی"
                  value={facts.quran_attendees || ''}
                  onChange={e => setFact('quran_attendees', e.target.value ? Number(e.target.value) : 0)}
                />
                <Grid container spacing={1}>
                  {[
                    { key: 'quran_staff', label: 'تشکیل ستاد مسابقات' },
                    { key: 'quran_announcement', label: 'اطلاع‌رسانی' },
                    { key: 'quran_questions', label: 'طراحی سؤالات' },
                    { key: 'quran_judging', label: 'داوری اساتید' },
                    { key: 'quran_awards', label: 'تقدیر و جوایز' },
                    { key: 'quran_reception', label: 'پذیرایی' },
                  ].map(item => (
                    <Grid size={{ xs: 12, sm: 6 }} key={item.key}>
                      <FormControlLabel
                        control={<Checkbox size="small" checked={Boolean(facts[item.key])} onChange={() => toggleFact(item.key)} />}
                        label={<Typography variant="body2">{item.label}</Typography>}
                      />
                    </Grid>
                  ))}
                </Grid>
              </Stack>
            ) : (
              <Stack spacing={1.5}>
                <Grid container spacing={2}>
                  <Grid size={{ xs: 12, sm: 6 }}>
                    <FormControl size="small" fullWidth>
                      <InputLabel>رشته مسابقه</InputLabel>
                      <Select
                        value={facts.contest_type_artistic ? 'artistic' : facts.contest_type_sports ? 'sports' : 'literary'}
                        label="رشته مسابقه"
                        onChange={e => {
                          const val = e.target.value
                          onChange('contest_type_literary', val === 'literary' ? 1 : 0)
                          onChange('contest_type_artistic', val === 'artistic' ? 1 : 0)
                          onChange('contest_type_sports', val === 'sports' ? 1 : 0)
                        }}
                      >
                        <MenuItem value="sports">ورزشی</MenuItem>
                        <MenuItem value="literary">ادبی</MenuItem>
                        <MenuItem value="artistic">هنری</MenuItem>
                      </Select>
                    </FormControl>
                  </Grid>
                  <Grid size={{ xs: 12, sm: 6 }}>
                    <FormControl size="small" fullWidth>
                      <InputLabel>جامعه مخاطب</InputLabel>
                      <Select
                        value={facts.audience_family ? 'family' : facts.audience_women ? 'women' : facts.audience_children ? 'children' : 'staff'}
                        label="جامعه مخاطب"
                        onChange={e => {
                          const val = e.target.value
                          onChange('audience_staff', val === 'staff' ? 1 : 0)
                          onChange('audience_family', val === 'family' ? 1 : 0)
                          onChange('audience_women', val === 'women' ? 1 : 0)
                          onChange('audience_children', val === 'children' ? 1 : 0)
                        }}
                      >
                        <MenuItem value="staff">کارکنان</MenuItem>
                        <MenuItem value="family">خانواده</MenuItem>
                        <MenuItem value="women">بانوان</MenuItem>
                        <MenuItem value="children">فرزندان</MenuItem>
                      </Select>
                    </FormControl>
                  </Grid>
                </Grid>

                <Grid container spacing={1}>
                  {[
                    { key: 'staff_count', label: 'تشکیل ستاد' },
                    { key: 'announcement_count', label: 'اطلاع‌رسانی' },
                    { key: 'questions_count', label: 'طراحی سؤالات' },
                    { key: 'judging_count', label: 'داوری' },
                    { key: 'awards_count', label: 'تقدیر از برگزیدگان' },
                    { key: 'reception_count', label: 'پذیرایی' },
                  ].map(item => (
                    <Grid size={{ xs: 12, sm: 6 }} key={item.key}>
                      <FormControlLabel
                        control={<Checkbox size="small" checked={Boolean(facts[item.key])} onChange={() => toggleFact(item.key)} />}
                        label={<Typography variant="body2">{item.label}</Typography>}
                      />
                    </Grid>
                  ))}
                </Grid>
              </Stack>
            )}
          </Stack>
        )}

        {/* 3. CEREMONIES */}
        {program === 'ceremonies' && (
          <Stack spacing={2}>
            <Grid container spacing={2}>
              <Grid size={{ xs: 12, sm: 6 }}>
                <FormControl size="small" fullWidth>
                  <InputLabel>نوع مناسبت مراسم</InputLabel>
                  <Select
                    value={facts.ceremony_kind || 'religious'}
                    label="نوع مناسبت مراسم"
                    onChange={e => {
                      const val = e.target.value
                      onChange('ceremony_kind', val)
                      onChange('ceremony_religious', val === 'religious' ? 1 : 0)
                      onChange('ceremony_national', val === 'national' ? 1 : 0)
                      onChange('ceremony_revolutionary', val === 'revolutionary' ? 1 : 0)
                    }}
                  >
                    <MenuItem value="religious">مذهبی (اعیاد/شهادت‌ها)</MenuItem>
                    <MenuItem value="national">ملی</MenuItem>
                    <MenuItem value="revolutionary">انقلابی (دهه فجر و ...)</MenuItem>
                  </Select>
                </FormControl>
              </Grid>
              <Grid size={{ xs: 12, sm: 6 }}>
                <Paper
                  variant="outlined"
                  sx={{
                    p: 1,
                    borderRadius: 1.5,
                    bgcolor: facts.is_ashura_pilgrimage ? 'secondary.50' : 'background.paper',
                    borderColor: facts.is_ashura_pilgrimage ? 'secondary.main' : 'divider',
                  }}
                >
                  <FormControlLabel
                    control={
                      <Checkbox
                        size="small"
                        color="secondary"
                        checked={Boolean(facts.is_ashura_pilgrimage)}
                        onChange={e => onChange('is_ashura_pilgrimage', e.target.checked)}
                      />
                    }
                    label={
                      <Typography variant="body2" fontWeight={facts.is_ashura_pilgrimage ? 700 : 400}>
                        مراسم قرائت زیارت عاشورا (آمار مستقل طبق بند C12)
                      </Typography>
                    }
                  />
                </Paper>
              </Grid>
            </Grid>

            <Grid container spacing={1}>
              {[
                { key: 'speaker_count', label: 'هماهنگی با سخنران/مداح/مجری' },
                { key: 'space_setup_count', label: 'فضاسازی محیطی و بنر' },
                { key: 'culture_pack_count', label: 'توزیع بسته فرهنگی' },
                { key: 'reception_count', label: 'پذیرایی' },
              ].map(item => (
                <Grid size={{ xs: 12, sm: 6 }} key={item.key}>
                  <FormControlLabel
                    control={<Checkbox size="small" checked={Boolean(facts[item.key])} onChange={() => toggleFact(item.key)} />}
                    label={<Typography variant="body2">{item.label}</Typography>}
                  />
                </Grid>
              ))}
            </Grid>
          </Stack>
        )}

        {/* 4. PRAYER */}
        {program === 'prayer' && (
          <Stack spacing={2}>
            <Grid container spacing={2}>
              <Grid size={{ xs: 12, sm: 6 }}>
                <TextField
                  size="small"
                  fullWidth
                  type="number"
                  label="تعداد افراد نومکلف (جشن تکلیف)"
                  value={facts.nominee_count || ''}
                  onChange={e => setFact('nominee_count', e.target.value ? Number(e.target.value) : 0)}
                />
              </Grid>
              <Grid size={{ xs: 12, sm: 6 }}>
                <TextField
                  size="small"
                  fullWidth
                  type="number"
                  label="تعداد هدایای جشن تکلیف"
                  value={facts.gift_count || ''}
                  onChange={e => setFact('gift_count', e.target.value ? Number(e.target.value) : 0)}
                />
              </Grid>
            </Grid>
            <Grid container spacing={1}>
              {[
                { key: 'invitation_count', label: 'دعوت‌نامه و فراخوان جشن تکلیف' },
                { key: 'space_setup_count', label: 'فضاسازی محیطی و محراب' },
                { key: 'imam_bank_count', label: 'ثبت در بانک اطلاعات ائمه جماعات' },
                { key: 'reception_count', label: 'پذیرایی جشن' },
              ].map(item => (
                <Grid size={{ xs: 12, sm: 6 }} key={item.key}>
                  <FormControlLabel
                    control={<Checkbox size="small" checked={Boolean(facts[item.key])} onChange={() => toggleFact(item.key)} />}
                    label={<Typography variant="body2">{item.label}</Typography>}
                  />
                </Grid>
              ))}
            </Grid>
          </Stack>
        )}

        {/* 5. HONOR */}
        {program === 'honor' && (
          <Stack spacing={2}>
            <Grid container spacing={2}>
              <Grid size={{ xs: 12, sm: 4 }}>
                <TextField
                  size="small"
                  fullWidth
                  type="number"
                  label="تعداد همکاران تقدیرشده"
                  value={facts.honoree_count || ''}
                  onChange={e => setFact('honoree_count', e.target.value ? Number(e.target.value) : 0)}
                />
              </Grid>
              <Grid size={{ xs: 12, sm: 4 }}>
                <FormControl size="small" fullWidth>
                  <InputLabel>جامعه همکاران</InputLabel>
                  <Select
                    value={facts.audience_judicial ? 'judicial' : 'administrative'}
                    label="جامعه همکاران"
                    onChange={e => {
                      const val = e.target.value
                      onChange('audience_administrative', val === 'administrative' ? 1 : 0)
                      onChange('audience_judicial', val === 'judicial' ? 1 : 0)
                    }}
                  >
                    <MenuItem value="administrative">کادر اداری</MenuItem>
                    <MenuItem value="judicial">کادر قضایی</MenuItem>
                  </Select>
                </FormControl>
              </Grid>
              <Grid size={{ xs: 12, sm: 4 }}>
                <TextField
                  size="small"
                  fullWidth
                  type="number"
                  label="تعداد هدایای اعطایی"
                  value={facts.gift_count || ''}
                  onChange={e => setFact('gift_count', e.target.value ? Number(e.target.value) : 0)}
                />
              </Grid>
            </Grid>
            <FormControlLabel
              control={
                <Switch
                  checked={facts.standalone_titled !== false}
                  onChange={e => onChange('standalone_titled', e.target.checked)}
                />
              }
              label={
                <Typography variant="body2">
                  آیا مراسم مستقل و با عنوان مشخص تکریم و تجلیل برگزار شد؟ (شرط پذیرش آمار مستقل)
                </Typography>
              }
            />
          </Stack>
        )}

        {/* 6. CUSTOMER_CARE */}
        {program === 'customer_care' && (
          <Stack spacing={2}>
            <Grid container spacing={2}>
              <Grid size={{ xs: 12, sm: 6 }}>
                <TextField
                  size="small"
                  fullWidth
                  type="number"
                  label="تعداد کارمندان تشویق‌شده"
                  value={facts.honoree_count || ''}
                  onChange={e => setFact('honoree_count', e.target.value ? Number(e.target.value) : 0)}
                />
              </Grid>
              <Grid size={{ xs: 12, sm: 6 }}>
                <FormControl size="small" fullWidth>
                  <InputLabel>بخش کارکنان</InputLabel>
                  <Select
                    value={facts.audience_judicial ? 'judicial' : 'administrative'}
                    label="بخش کارکنان"
                    onChange={e => {
                      const val = e.target.value
                      onChange('audience_administrative', val === 'administrative' ? 1 : 0)
                      onChange('audience_judicial', val === 'judicial' ? 1 : 0)
                    }}
                  >
                    <MenuItem value="administrative">کادر اداری</MenuItem>
                    <MenuItem value="judicial">کادر قضایی</MenuItem>
                  </Select>
                </FormControl>
              </Grid>
            </Grid>
          </Stack>
        )}

        {/* 7. CHARTER */}
        {program === 'charter' && (
          <Stack spacing={2}>
            <Grid container spacing={2}>
              <Grid size={{ xs: 12, sm: 6 }}>
                <TextField
                  size="small"
                  fullWidth
                  type="number"
                  label="تعداد تابلوهای منشور نصب‌شده"
                  value={facts.board_count || ''}
                  onChange={e => setFact('board_count', e.target.value ? Number(e.target.value) : 0)}
                />
              </Grid>
              <Grid size={{ xs: 12, sm: 6 }}>
                <TextField
                  size="small"
                  fullWidth
                  type="number"
                  label="مکاتبات و ابلاغیه‌های اداری"
                  value={facts.correspondence_count || ''}
                  onChange={e => setFact('correspondence_count', e.target.value ? Number(e.target.value) : 0)}
                />
              </Grid>
            </Grid>
            <Grid container spacing={1}>
              {[
                { key: 'republish_count', label: 'بازنشر مفاد منشور در کانال/گروه مجازی' },
                { key: 'other_action_count', label: 'سایر اقدامات فرهنگی و نظارتی' },
              ].map(item => (
                <Grid size={{ xs: 12, sm: 6 }} key={item.key}>
                  <FormControlLabel
                    control={<Checkbox size="small" checked={Boolean(facts[item.key])} onChange={() => toggleFact(item.key)} />}
                    label={<Typography variant="body2">{item.label}</Typography>}
                  />
                </Grid>
              ))}
            </Grid>
          </Stack>
        )}
      </Stack>
    </Paper>
  )
}

export function ReportingWorkbench({
  onClose,
  initialTab = 0,
  initialEventId = null,
}: {
  onClose: () => void
  initialTab?: number
  initialEventId?: string | null
}) {
  const [currentTab, setCurrentTab] = useState<number>(() => {
    if (initialEventId) return 1
    if (initialTab === 3) return 1
    if (initialTab > 3) return initialTab - 1
    return initialTab
  })
  const [cartableSubTab, setCartableSubTab] = useState<'cartable' | 'export_workbook'>(() => {
    return initialTab === 3 ? 'export_workbook' : 'cartable'
  })
  const [loading, setLoading] = useState<boolean>(false)

  // Catalog state
  const [programsCatalog, setProgramsCatalog] = useState<ProgramCatalogItem[]>([])
  const [macroOptions, setMacroOptions] = useState<string[]>([])
  const [microOptions, setMicroOptions] = useState<MicroIndicatorItem[]>([])
  const [judicialUnits, setJudicialUnits] = useState<Array<{ display_name: string; name: string }>>([])

  // Dynamic lookup for program name
  const getProgramTitle = useCallback(
    (codeOrKind: string) => {
      const clean = String(codeOrKind || '').trim().toLowerCase()
      const found = programsCatalog.find(
        p => p.program_code === codeOrKind || p.kind.toLowerCase() === clean,
      )
      if (found) {
        return `${found.program_code} - ${found.title}`
      }
      return PROGRAM_NAMES[codeOrKind] || codeOrKind
    },
    [programsCatalog],
  )

  // Cartable and archive state (Tab 1)
  const [cartableEvents, setCartableEvents] = useState<ReportedEventItem[]>([])
  const [loadingCartable, setLoadingCartable] = useState<boolean>(false)
  const [filterSearch, setFilterSearch] = useState<string>('')
  const [filterStatus, setFilterStatus] = useState<string>('all')
  const [filterProgram, setFilterProgram] = useState<string>('all')
  const [filterMacro, setFilterMacro] = useState<string>('all')
  const [filterMicro, setFilterMicro] = useState<string>('all')
  const [filterUnit, setFilterUnit] = useState<string>('all')
  const [exportingFiltered, setExportingFiltered] = useState<boolean>(false)
  const [lastFilteredExportResult, setLastFilteredExportResult] = useState<{ path: string; fileName: string; count: number } | null>(null)
  const [detailModalEventId, setDetailModalEventId] = useState<string | null>(initialEventId)
  const [unitsModalOpen, setUnitsModalOpen] = useState(false)
  const [unitsModalTab, setUnitsModalTab] = useState(0)

  const cartableSummary = useMemo(() => {
    let totalParticipants = 0
    let colleaguesCount = 0
    let familyCount = 0
    let surveySum = 0
    let surveyCount = 0
    const uniqueUnits = new Set<string>()

    for (const ev of cartableEvents) {
      if (ev.unit_name) uniqueUnits.add(ev.unit_name)
      else if (ev.unit) uniqueUnits.add(ev.unit)

      if (Array.isArray(ev.facts)) {
        for (const f of ev.facts) {
          const m = f.metric
          const val = Number(f.value) || 0
          if (m === 'attendees' || m === 'participant_count' || m === 'trip_attendees' || m === 'audience_count' || m === 'total_participants') {
            totalParticipants += val
          } else if (m === 'honoree_count' || m === 'encouraged_count') {
            totalParticipants += val
          } else if (m === 'colleagues_count') {
            colleaguesCount += val
          } else if (m === 'family_count') {
            familyCount += val
          } else if (m === 'survey_rating' || m === 'survey_score' || m === 'satisfaction_score' || m === 'survey_score_pct') {
            if (val > 0) {
              surveySum += val
              surveyCount += 1
            }
          }
        }
      }
    }

    const avgSurvey = surveyCount > 0 ? (surveySum / surveyCount) : 0
    return {
      totalEvents: cartableEvents.length,
      totalParticipants,
      colleaguesCount,
      familyCount,
      uniqueUnitsCount: uniqueUnits.size,
      surveyCount,
      avgSurvey: Math.round(avgSurvey * 10) / 10,
    }
  }, [cartableEvents])

  // Single worksheet vs entire province export state
  const [exportScope, setExportScope] = useState<'all' | 'single'>('all')
  const [selectedSingleProgram, setSelectedSingleProgram] = useState<string>('trip')

  // Load catalogs on mount
  useEffect(() => {
    let active = true
    async function loadAllCatalogs() {
      try {
        const [progs, macros, micros, unitsRes] = await Promise.all([
          fetchProgramCatalog({ include_inactive: true }),
          fetchMacroIndicators(),
          fetchMicroIndicators(),
          api<{ units: Array<{ display_name: string; name: string }> }>('GET', '/api/v3/reporting/units').catch(
            () => ({ units: [] }),
          ),
        ])
        if (active) {
          setProgramsCatalog(progs)
          setMacroOptions(macros)
          setMicroOptions(micros)
          setJudicialUnits(unitsRes.units || [])
        }
      } catch (err) {
        console.error('Error loading catalogs in workbench:', err)
      }
    }
    void loadAllCatalogs()
    return () => {
      active = false
    }
  }, [])

  // Load cartable events from /api/v3/reporting/events
  const loadEventsCartable = useCallback(async () => {
    try {
      setLoadingCartable(true)
      const params = new URLSearchParams()
      params.set('limit', '300')
      if (filterStatus && filterStatus !== 'all') params.set('review_status', filterStatus)
      if (filterProgram && filterProgram !== 'all') params.set('program_code', filterProgram)
      if (filterMacro && filterMacro !== 'all') params.set('macro_indicator', filterMacro)
      if (filterMicro && filterMicro !== 'all') params.set('micro_indicator', filterMicro)
      if (filterUnit && filterUnit !== 'all') params.set('unit_name', filterUnit)
      if (filterSearch.trim()) params.set('search', filterSearch.trim())

      const res = await api<{ ok: boolean; events: ReportedEventItem[] }>(
        'GET',
        `/api/v3/reporting/events?${params.toString()}`,
      )
      setCartableEvents(res.events || [])
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'خطا در بارگذاری کارتابل گزارش‌ها')
    } finally {
      setLoadingCartable(false)
    }
  }, [filterStatus, filterProgram, filterMacro, filterMicro, filterUnit, filterSearch])

  // Export filtered events
  const handleExportFilteredEvents = async () => {
    try {
      setExportingFiltered(true)
      const payload: Record<string, any> = {}
      if (filterStatus && filterStatus !== 'all') payload.review_status = filterStatus
      if (filterProgram && filterProgram !== 'all') payload.program_code = filterProgram
      if (filterMacro && filterMacro !== 'all') payload.macro_indicator = filterMacro
      if (filterMicro && filterMicro !== 'all') payload.micro_indicator = filterMicro
      if (filterUnit && filterUnit !== 'all') payload.unit_name = filterUnit
      if (filterSearch.trim()) payload.search = filterSearch.trim()

      const res = await api<{ ok: boolean; file_name: string; path: string; count: number; media_url?: string }>(
        'POST',
        '/api/v3/reporting/events/export-excel',
        payload,
      )
      setLastFilteredExportResult({ path: res.path, fileName: res.file_name, count: res.count || 0 })
      toast.success(`خروجی اکسل گزارش‌ها با موفقیت ایجاد شد: ${res.file_name} (${res.count || 0} رکورد)`)
      if (res.media_url) {
        window.open(res.media_url, '_blank')
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'خطا در صدور خروجی اکسل گزارش‌ها')
    } finally {
      setExportingFiltered(false)
    }
  }

  const [exportingBundle, setExportingBundle] = useState<boolean>(false)

  // Export full dossier bundle (ZIP of Excel + photos + documents)
  const handleExportDossierBundle = async () => {
    try {
      setExportingBundle(true)
      const payload: Record<string, any> = {}
      if (filterStatus && filterStatus !== 'all') payload.review_status = filterStatus
      if (filterProgram && filterProgram !== 'all') payload.program_code = filterProgram
      if (filterMacro && filterMacro !== 'all') payload.macro_indicator = filterMacro
      if (filterMicro && filterMicro !== 'all') payload.micro_indicator = filterMicro
      if (filterUnit && filterUnit !== 'all') payload.unit_name = filterUnit
      if (filterSearch.trim()) payload.search = filterSearch.trim()

      const res = await api<{ ok: boolean; file_name: string; path: string; total_events: number; total_documents: number; media_url?: string }>(
        'POST',
        '/api/v3/reporting/events/export-dossier-bundle',
        payload,
      )
      toast.success(`بسته جامع اسناد و پوشه رویدادها صادر شد: ${res.file_name} (${res.total_events} رویداد، ${res.total_documents} سند پیوست)`)
      if (res.media_url) {
        window.open(res.media_url, '_blank')
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'خطا در صدور بسته اسناد و رویدادها')
    } finally {
      setExportingBundle(false)
    }
  }

  // Candidate review state
  const [candidates, setCandidates] = useState<CandidateItem[]>([])
  const [candidateFilter, setCandidateFilter] = useState<'pending' | 'approved' | 'rejected' | 'all'>('pending')
  const [scanning, setScanning] = useState<boolean>(false)
  const [approveDialog, setApproveDialog] = useState<CandidateItem | null>(null)
  const [manualEventDialogOpen, setManualEventDialogOpen] = useState<boolean>(false)
  const [rejectDialog, setRejectDialog] = useState<CandidateItem | null>(null)

  // Approve & Manual event form state
  const [approveProgram, setApproveProgram] = useState<string>('ceremonies')
  const [approveAttendees, setApproveAttendees] = useState<string>('')
  const [approveOccurredOn, setApproveOccurredOn] = useState<string>(() => new Date().toISOString().slice(0, 10))
  const [approveUnit, setApproveUnit] = useState<string>('provincial_hq')
  const [approveUnitName, setApproveUnitName] = useState<string>('')
  const [approveOfficialPresent, setApproveOfficialPresent] = useState<boolean>(false)
  const [approveNotes, setApproveNotes] = useState<string>('')
  const [dimensionFacts, setDimensionFacts] = useState<Record<string, any>>({})
  const [submittingEvent, setSubmittingEvent] = useState<boolean>(false)
  const [rejectionReason, setRejectionReason] = useState<string>('')
  const [suggestionData, setSuggestionData] = useState<{ reasoning: string; hints: Record<string, any> } | null>(null)
  const [loadingSuggestion, setLoadingSuggestion] = useState<boolean>(false)

  // Forms state
  const [forms, setForms] = useState<FormSummary[]>([])
  const [selectedFormIndex, setSelectedFormIndex] = useState<number>(0)
  const [formAnswers, setFormAnswers] = useState<Record<string, any>>({})
  const [formDateFrom, setFormDateFrom] = useState<string>('')
  const [formDateTo, setFormDateTo] = useState<string>('')
  const [matchingEventsCount, setMatchingEventsCount] = useState<number | null>(null)
  const [loadingForms, setLoadingForms] = useState<boolean>(false)
  const [formEventsDialogOpen, setFormEventsDialogOpen] = useState<boolean>(false)
  const [formEventsList, setFormEventsList] = useState<ReportedEventItem[]>([])
  const [loadingFormEvents, setLoadingFormEvents] = useState<boolean>(false)
  const [savingForm, setSavingForm] = useState<boolean>(false)

  // Mandates state
  const [mandates, setMandates] = useState<MandateItem[]>([])
  const [loadingMandates, setLoadingMandates] = useState<boolean>(false)
  const [newMandateOpen, setNewMandateOpen] = useState<boolean>(false)
  const [allMandatesDialogOpen, setAllMandatesDialogOpen] = useState<boolean>(false)
  const [allMandatesList, setAllMandatesList] = useState<MandateItem[]>([])
  const [loadingAllMandates, setLoadingAllMandates] = useState<boolean>(false)

  // New mandate form state
  const [mandateFormKind, setMandateFormKind] = useState<string>('circular')
  const [mandateFormTitle, setMandateFormTitle] = useState<string>('')
  const [mandateFormNumber, setMandateFormNumber] = useState<string>('')
  const [mandateFormIssuedOn, setMandateFormIssuedOn] = useState<string>('')
  const [mandateFormDocRef, setMandateFormDocRef] = useState<string>('')
  const [mandateFormNotes, setMandateFormNotes] = useState<string>('')
  const [savingMandate, setSavingMandate] = useState<boolean>(false)

  // Aggregated Preview & Export state
  const [events, setEvents] = useState<ReportedEventItem[]>([])
  const [exportsList, setExportsList] = useState<ExportAuditItem[]>([])
  const [exportProvince, setExportProvince] = useState<string>('مازندران')
  const [exportPeriod, setExportPeriod] = useState<string>('۱۴۰۵')
  const [exportForceUnresolved, setExportForceUnresolved] = useState<boolean>(false)
  const [exporting, setExporting] = useState<boolean>(false)
  const [lastExportResult, setLastExportResult] = useState<{ path: string; fileName: string } | null>(null)
  const [exportBlockers, setExportBlockers] = useState<Array<{ program_id: string; missing_star_keys: string[] }>>([])

  // Watch settings state
  const [watchTargets, setWatchTargets] = useState<DialogTargetConfig[]>([])
  const [newTargetLabel, setNewTargetLabel] = useState<string>('')
  const [newTargetKeywords, setNewTargetKeywords] = useState<string>('')
  const [savingSettings, setSavingSettings] = useState<boolean>(false)

  const [revisionDialogEvent, setRevisionDialogEvent] = useState<ReportedEventItem | null>(null)
  const [revisionReason, setRevisionReason] = useState<string>('')
  const [defectDialogEvent, setDefectDialogEvent] = useState<ReportedEventItem | null>(null)
  const [workflowActionLoading, setWorkflowActionLoading] = useState<boolean>(false)

  const handleApproveEvent = async (eventId: string) => {
    try {
      setWorkflowActionLoading(true)
      await api('POST', `/api/v3/reporting/events/${eventId}/approve`, {})
      toast.success('رویداد توسط مدیر تأیید شد.')
      void loadEventsAndExports()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'خطا در تأیید رویداد')
    } finally {
      setWorkflowActionLoading(false)
    }
  }

  const handleRequestRevision = async (eventId: string, reason: string) => {
    if (!reason.trim()) {
      toast.error('لطفاً شرح نقص یا دستور اصلاح را وارد کنید.')
      return
    }
    try {
      setWorkflowActionLoading(true)
      await api('POST', `/api/v3/reporting/events/${eventId}/request-revision`, { reason })
      toast.success('ایراد گزارش شد و تسک رفع نقص به کارمند مربوطه ارجاع گردید.')
      setRevisionDialogEvent(null)
      setRevisionReason('')
      void loadEventsAndExports()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'خطا در ارجاع نقص رویداد')
    } finally {
      setWorkflowActionLoading(false)
    }
  }

  const handleMarkConflict = async (eventId: string, reason: string) => {
    if (!reason.trim()) {
      toast.error('ثبت دلیل رد یا تعارض الزامی است.')
      return
    }
    try {
      setWorkflowActionLoading(true)
      await api('POST', `/api/v3/reporting/events/${eventId}/mark-conflict`, { reason })
      toast.success('رویداد به دلیل تعارض مسدود شد.')
      void loadEventsAndExports()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'خطا در علامت‌گذاری تعارض')
    } finally {
      setWorkflowActionLoading(false)
    }
  }

  // Fetch candidates
  const loadCandidates = async () => {
    try {
      setLoading(true)
      const res = await api<{ ok: boolean; candidates: CandidateItem[] }>(
        'GET',
        `/api/v2/reporting/candidates?status=${candidateFilter}`,
      )
      setCandidates(res.candidates || [])
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'خطا در دریافت صف بازبینی')
    } finally {
      setLoading(false)
    }
  }

  // Fetch mandates for current program code
  const loadMandatesForForm = async (code: string) => {
    if (!code) {
      setMandates([])
      return
    }
    try {
      setLoadingMandates(true)
      const res = await api<{ ok: boolean; mandates: MandateItem[] }>(
        'GET',
        `/api/v2/reporting/mandates?program_code=${encodeURIComponent(code)}`,
      )
      setMandates(res.mandates || [])
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'خطا در دریافت مستندات ابلاغی برنامه')
    } finally {
      setLoadingMandates(false)
    }
  }

  // Fetch all mandates across all programs
  const loadAllMandates = async () => {
    try {
      setLoadingAllMandates(true)
      const res = await api<{ ok: boolean; mandates: MandateItem[] }>(
        'GET',
        '/api/v2/reporting/mandates',
      )
      setAllMandatesList(res.mandates || [])
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'خطا در دریافت کل مستندات ابلاغی')
    } finally {
      setLoadingAllMandates(false)
    }
  }

  // Submit new mandate
  const handleSaveMandate = async () => {
    if (!mandateFormTitle.trim()) {
      toast.error('عنوان مستند ابلاغی الزامی است')
      return
    }
    const currentCode = forms[selectedFormIndex]?.program_code || ''
    if (!currentCode) {
      toast.error('کد برنامه نامشخص است')
      return
    }
    try {
      setSavingMandate(true)
      await api('POST', '/api/v2/reporting/mandates', {
        program_code: currentCode,
        kind: mandateFormKind,
        title: mandateFormTitle.trim(),
        number: mandateFormNumber.trim(),
        issued_on: mandateFormIssuedOn.trim(),
        document_ref: mandateFormDocRef.trim(),
        notes: mandateFormNotes.trim(),
      })
      toast.success('مستند ابلاغی با موفقیت ثبت شد')
      setNewMandateOpen(false)
      setMandateFormTitle('')
      setMandateFormNumber('')
      setMandateFormIssuedOn('')
      setMandateFormDocRef('')
      setMandateFormNotes('')
      await loadMandatesForForm(currentCode)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'خطا در ذخیره مستند ابلاغی')
    } finally {
      setSavingMandate(false)
    }
  }

  // Delete mandate
  const handleDeleteMandate = async (mandateId: string) => {
    try {
      await api('DELETE', `/api/v2/reporting/mandates/${mandateId}`)
      toast.success('مستند ابلاغی حذف شد')
      const currentCode = forms[selectedFormIndex]?.program_code || ''
      if (currentCode) {
        await loadMandatesForForm(currentCode)
      }
      if (allMandatesDialogOpen) {
        await loadAllMandates()
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'خطا در حذف مستند ابلاغی')
    }
  }

  // Fetch forms
  const loadForms = async (customDateFrom?: string, customDateTo?: string) => {
    try {
      setLoadingForms(true)
      const dFrom = customDateFrom !== undefined ? customDateFrom : formDateFrom
      const dTo = customDateTo !== undefined ? customDateTo : formDateTo
      const params = new URLSearchParams({ all: '1' })
      if (dFrom) params.set('date_from', dFrom)
      if (dTo) params.set('date_to', dTo)
      const res = await api<{
        ok: boolean
        forms: FormSummary[]
        total_events?: number
        date_from?: string
        date_to?: string
      }>('GET', `/api/v2/reporting/forms?${params.toString()}`)
      setForms(res.forms || [])
      if (res.total_events !== undefined) {
        setMatchingEventsCount(res.total_events)
      } else {
        setMatchingEventsCount(null)
      }
      if (res.forms && res.forms[selectedFormIndex]) {
        const initialAnswers: Record<string, any> = {}
        for (const q of res.forms[selectedFormIndex].questions) {
          if (q.current_value !== null && q.current_value !== undefined) {
            initialAnswers[q.key] = q.current_value
          }
        }
        setFormAnswers(initialAnswers)
        if (res.forms[selectedFormIndex].program_code) {
          void loadMandatesForForm(res.forms[selectedFormIndex].program_code!)
        }
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'خطا در دریافت کاربرگ‌ها')
    } finally {
      setLoadingForms(false)
    }
  }

  // Fetch events & exports
  const loadEventsAndExports = async () => {
    try {
      const [eventsRes, exportsRes] = await Promise.all([
        api<{ ok: boolean; events: ReportedEventItem[] }>('GET', '/api/v2/reporting/events'),
        api<{ ok: boolean; exports: ExportAuditItem[] }>('GET', '/api/v2/reporting/exports'),
      ])
      setEvents(eventsRes.events || [])
      setExportsList(exportsRes.exports || [])
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'خطا در دریافت رویدادها یا تاریخچه صدور')
    }
  }

  // Fetch watch config
  const loadWatchConfig = async () => {
    try {
      const res = await api<{ ok: boolean; config: any; targets: DialogTargetConfig[] }>(
        'GET',
        '/api/v2/reporting/config',
      )
      setWatchTargets(res.targets || [])
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'خطا در دریافت تنظیمات رصد')
    }
  }

  useEffect(() => {
    if (currentTab === 0) void loadCandidates()
    else if (currentTab === 1) {
      void loadEventsCartable()
      if (cartableSubTab === 'export_workbook') {
        void loadForms()
        void loadEventsAndExports()
      }
    }
    else if (currentTab === 2) void loadForms()
    else if (currentTab === 3) void loadWatchConfig()
  }, [currentTab, cartableSubTab, candidateFilter, loadEventsCartable])

  // Sync selected form answers when tab or selectedFormIndex changes
  useEffect(() => {
    if (forms[selectedFormIndex]) {
      const answers: Record<string, any> = {}
      for (const q of forms[selectedFormIndex].questions) {
        if (q.current_value !== null && q.current_value !== undefined) {
          answers[q.key] = q.current_value
        }
      }
      setFormAnswers(answers)
      if (forms[selectedFormIndex].program_code) {
        void loadMandatesForForm(forms[selectedFormIndex].program_code!)
      }
    }
  }, [selectedFormIndex, forms])

  // Unresolved stars count across all forms
  const totalUnresolvedStars = useMemo(() => {
    return forms.reduce((acc, f) => acc + (f.unresolved_star?.length || 0), 0)
  }, [forms])

  const pendingCandidatesCount = useMemo(() => {
    return candidates.filter(c => c.status === 'pending').length
  }, [candidates])

  // Scan dialogs
  const handleScan = async () => {
    try {
      setScanning(true)
      const res = await api<{ ok: boolean; result: any; note?: string }>('POST', '/api/v2/reporting/scan', {
        limit_per_dialog: 50,
      })
      if (res.note === 'runtime_not_available') {
        toast.warning('نشست پیام‌رسان در دسترس نیست یا گفتگوی فعالی در فهرست رصد پیدا نشد.')
      } else {
        toast.success(
          `پویش انجام شد: ${res.result?.scanned || 0} پیام بررسی شد، ${res.result?.event_reports || 0} رویداد شناسایی شد.`,
        )
      }
      await loadCandidates()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'خطا در انجام پویش خودکار')
    } finally {
      setScanning(false)
    }
  }

  // Open Approve Dialog
  const openApprove = (candidate: CandidateItem) => {
    setApproveDialog(candidate)
    setManualEventDialogOpen(false)
    const firstProg = candidate.matched_programs[0] || 'ceremonies'
    setApproveProgram(firstProg)
    setApproveAttendees(candidate.attendee_count !== null ? String(candidate.attendee_count) : '')
    setApproveUnit('provincial_hq')
    setApproveUnitName(candidate.unit_hints[0] || '')
    setApproveOfficialPresent(false)
    setApproveNotes('')
    setSuggestionData(null)
    setDimensionFacts({
      is_ashura_pilgrimage: candidate.candidate_kind === 'ashura_pilgrimage',
    })
  }

  // Open Manual Event Dialog
  const openManualEvent = () => {
    setApproveDialog(null)
    setManualEventDialogOpen(true)
    setApproveProgram('ceremonies')
    setApproveAttendees('')
    setApproveOccurredOn(new Date().toISOString().slice(0, 10))
    setApproveUnit('provincial_hq')
    setApproveUnitName('')
    setApproveOfficialPresent(false)
    setApproveNotes('')
    setSuggestionData(null)
    setDimensionFacts({})
  }

  // Fetch AI Suggester proposal
  const fetchSuggestion = async (candidate: CandidateItem) => {
    try {
      setLoadingSuggestion(true)
      const res = await api<{ ok: boolean; suggestion: any }>(
        'POST',
        `/api/v2/reporting/candidates/${candidate.candidate_id}/suggest`,
        { dialog_label: candidate.dialog_label },
      )
      if (res.ok && res.suggestion) {
        const s = res.suggestion
        if (s.recommended_program) setApproveProgram(s.recommended_program)
        if (s.extracted_attendees !== null && s.extracted_attendees !== undefined) {
          setApproveAttendees(String(s.extracted_attendees))
        }
        if (s.extracted_unit_scope) setApproveUnit(s.extracted_unit_scope)
        if (s.extracted_unit_name) setApproveUnitName(s.extracted_unit_name)
        if (s.official_present_suggested !== null && s.official_present_suggested !== undefined) {
          setApproveOfficialPresent(Boolean(s.official_present_suggested))
        }
        setSuggestionData({
          reasoning: s.reasoning,
          hints: s.star_field_hints || {},
        })
        toast.info('پیشنهاد هوشمند عامل اعمال شد. لطفاً بازبینی نمایید.')
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'خطا در دریافت پیشنهاد عامل هوشمند')
    } finally {
      setLoadingSuggestion(false)
    }
  }

  // Submit Approval or Manual Event
  const submitEventForm = async () => {
    if (!approveDialog && !manualEventDialogOpen) return
    try {
      setSubmittingEvent(true)
      const attendees = approveAttendees.trim() ? Number(approveAttendees) : null
      const payload: Record<string, any> = {
        program_id: approveProgram,
        occurred_on: approveOccurredOn,
        unit: approveUnit,
        unit_name: approveUnitName,
        official_present: approveOfficialPresent,
        attendee_count: attendees,
        is_ashura_pilgrimage: Boolean(dimensionFacts.is_ashura_pilgrimage),
        is_standalone_titled: dimensionFacts.standalone_titled !== false,
        occasion_class: dimensionFacts.occasion_class || (approveProgram === 'ceremonies' ? (dimensionFacts.ceremony_kind || 'religious') : null),
        dimension_facts: dimensionFacts,
        notes: approveNotes,
      }

      if (approveDialog) {
        payload.action = 'approve'
        await api('POST', `/api/v2/reporting/candidates/${approveDialog.candidate_id}/review`, payload)
        toast.success('رویداد با تمام ابعاد اختصاصی شیت با موفقیت تأیید و در آمار ثبت شد.')
        setApproveDialog(null)
        await loadCandidates()
      } else {
        await api('POST', '/api/v2/reporting/events', payload)
        toast.success('رویداد فرهنگی جدید با ابعاد اختصاصی شیت با موفقیت ایجاد شد.')
        setManualEventDialogOpen(false)
      }
      void loadEventsAndExports()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'خطا در ثبت رویداد')
    } finally {
      setSubmittingEvent(false)
    }
  }

  // Open Reject Dialog
  const openReject = (candidate: CandidateItem) => {
    setRejectDialog(candidate)
    setRejectionReason('')
  }

  // Submit Rejection
  const submitReject = async () => {
    if (!rejectDialog) return
    try {
      await api('POST', `/api/v2/reporting/candidates/${rejectDialog.candidate_id}/review`, {
        action: 'reject',
        reason: rejectionReason.trim(),
      })
      toast.info('نامزد گزارش رد شد.')
      setRejectDialog(null)
      await loadCandidates()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'خطا در رد نامزد گزارش')
    }
  }

  // Load underlying events contributing to active workbook
  const loadEventsForActiveForm = async () => {
    const activeForm = forms[selectedFormIndex]
    if (!activeForm) return
    try {
      setLoadingFormEvents(true)
      setFormEventsDialogOpen(true)
      const params = new URLSearchParams()
      const progCode = activeForm.program_code || activeForm.program_id
      params.set('program_code', progCode)
      if (formDateFrom) params.set('date_from', formDateFrom)
      if (formDateTo) params.set('date_to', formDateTo)
      params.set('limit', '500')
      const res = await api<{ ok: boolean; events: ReportedEventItem[] }>(
        'GET',
        `/api/v2/reporting/events?${params.toString()}`
      )
      setFormEventsList(res.events || [])
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'خطا در دریافت ریز گزارش‌های کاربرگ')
    } finally {
      setLoadingFormEvents(false)
    }
  }

  // Save current form
  const handleSaveForm = async () => {
    const activeForm = forms[selectedFormIndex]
    if (!activeForm) return
    try {
      setSavingForm(true)
      const res = await api<{ ok: boolean; program_id: string; unresolved_star: string[] }>(
        'PUT',
        `/api/v2/reporting/forms/${activeForm.program_id}`,
        { answers: formAnswers },
      )
      toast.success(`کاربرگ ${activeForm.title} ذخیره شد.`)
      // update local unresolved_star for this form
      setForms(prev =>
        prev.map(f => (f.program_id === activeForm.program_id ? { ...f, unresolved_star: res.unresolved_star } : f)),
      )
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'خطا در ذخیره کاربرگ')
    } finally {
      setSavingForm(false)
    }
  }

  // Execute Excel Export
  const handleExport = async () => {
    try {
      setExporting(true)
      setExportBlockers([])
      const res = await api<{ ok: boolean; export_path: string; file_name: string }>(
        'POST',
        '/api/v2/reporting/export',
        {
          province_name: exportProvince,
          report_period: exportPeriod,
          allow_unresolved_star: exportForceUnresolved,
          single_program: exportScope === 'single' ? selectedSingleProgram : undefined,
          date_from: formDateFrom || undefined,
          date_to: formDateTo || undefined,
        },
      )
      setLastExportResult({ path: res.export_path, fileName: res.file_name })
      toast.success(`فایل اکسل با موفقیت صادر شد: ${res.file_name}`)
      await loadEventsAndExports()
    } catch (err) {
      if (err instanceof ApiError && err.code === 'unresolved_star_cells') {
        const blockers = (err.context?.blockers as any) || []
        setExportBlockers(blockers)
        toast.error('صدور متوقف شد: خانه‌های ستاره‌دار الزامی هنوز تکمیل نشده‌اند.')
      } else {
        toast.error(err instanceof Error ? err.message : 'خطا در صدور فایل اکسل')
      }
    } finally {
      setExporting(false)
    }
  }

  // Save Watch Settings
  const handleSaveWatchSettings = async () => {
    try {
      setSavingSettings(true)
      await api('PUT', '/api/v2/reporting/config', {
        targets: watchTargets,
      })
      toast.success('تنظیمات رصد گفتگوها به‌روزرسانی شد.')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'خطا در ذخیره تنظیمات رصد')
    } finally {
      setSavingSettings(false)
    }
  }

  // Add Watch Target
  const handleAddWatchTarget = () => {
    const label = newTargetLabel.trim()
    if (!label) return
    const kws = newTargetKeywords
      .split(/[,،]+/)
      .map(k => k.trim())
      .filter(Boolean)
    setWatchTargets(prev => [...prev, { label, match_keywords: kws, enabled: true }])
    setNewTargetLabel('')
    setNewTargetKeywords('')
  }

  const selectedForm = forms[selectedFormIndex]

  return (
    <Paper
      square
      elevation={0}
      sx={{
        width: '100%',
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        bgcolor: 'background.default',
        overflow: 'hidden',
      }}
    >
      {/* Header */}
      <Box
        sx={{
          px: 3,
          py: 2,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          borderBottom: 1,
          borderColor: 'divider',
          bgcolor: 'background.paper',
        }}
      >
        <Stack direction="row" spacing={1.5} alignItems="center">
          <SummarizeRounded color="primary" sx={{ fontSize: 32 }} />
          <Box>
            <Typography variant="h6" fontWeight={800}>
              سامانه مدیریت گزارش‌های فرهنگی ۱۴۰۵
            </Typography>
            <Typography variant="caption" color="text.secondary">
              پایش و ایندکس‌گذاری هوشمند پیام‌ها، کاربرگ‌های هفت‌گانه و صدور استاندارد اکسل تجمیعی
            </Typography>
          </Box>
        </Stack>
        <Stack direction="row" spacing={1} alignItems="center">
          <Tooltip title="به‌روزرسانی داده‌ها">
            <IconButton
              onClick={() => {
                if (currentTab === 0) void loadCandidates()
                else if (currentTab === 1) {
                  void loadEventsCartable()
                  if (cartableSubTab === 'export_workbook') {
                    void loadForms()
                    void loadEventsAndExports()
                  }
                }
                else if (currentTab === 2) void loadForms()
                else if (currentTab === 3) void loadWatchConfig()
              }}
              disabled={loading}
            >
              <RefreshRounded />
            </IconButton>
          </Tooltip>
          <IconButton onClick={onClose} aria-label="بستن سامانه گزارش‌ها">
            <CloseRounded />
          </IconButton>
        </Stack>
      </Box>

      {/* Tabs */}
      <Box sx={{ borderBottom: 1, borderColor: 'divider', bgcolor: 'background.paper', px: 2 }}>
        <Tabs
          value={currentTab}
          onChange={(_e, val) => setCurrentTab(val)}
          indicatorColor="primary"
          textColor="primary"
          variant="scrollable"
          scrollButtons="auto"
        >
          <Tab
            label={
              <Badge badgeContent={pendingCandidatesCount} color="error" sx={{ pr: 1.5 }}>
                <Stack direction="row" spacing={1} alignItems="center">
                  <AutoAwesomeRounded fontSize="small" />
                  <span>صف بازبینی هوشمند</span>
                </Stack>
              </Badge>
            }
          />
          <Tab
            label={
              <Badge badgeContent={cartableEvents.filter(e => e.review_status === 'needs_review').length} color="warning" sx={{ pr: 1.5 }}>
                <Stack direction="row" spacing={1} alignItems="center">
                  <AssignmentTurnedInRounded fontSize="small" />
                  <span>کارتابل و صدور گزارش‌ها</span>
                </Stack>
              </Badge>
            }
          />
          <Tab
            label={
              <Badge badgeContent={totalUnresolvedStars} color="warning" sx={{ pr: 1.5 }}>
                <Stack direction="row" spacing={1} alignItems="center">
                  <DescriptionOutlined fontSize="small" />
                  <span>کاربرگ‌های هفت‌گانه</span>
                </Stack>
              </Badge>
            }
          />
          <Tab
            label={
              <Stack direction="row" spacing={1} alignItems="center">
                <SettingsRounded fontSize="small" />
                <span>تنظیمات رصد گفتگوها</span>
              </Stack>
            }
          />
          <Tab
            label={
              <Stack direction="row" spacing={1} alignItems="center">
                <SummarizeRounded fontSize="small" />
                <span>داشبورد دفتر</span>
              </Stack>
            }
          />
        </Tabs>
      </Box>

      {/* Main Tab Content */}
      <Box sx={{ flex: 1, overflow: 'auto', p: 3 }}>
        {/* ================= TAB 0: صف بازبینی هوشمند ================= */}
        {currentTab === 0 && (
          <Stack spacing={2.5}>
            {/* Action Bar */}
            <Paper variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
              <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2} justifyContent="space-between" alignItems="center">
                <Stack direction="row" spacing={1.5} alignItems="center">
                  <Button
                    variant="contained"
                    color="primary"
                    startIcon={scanning ? <CircularProgress size={18} color="inherit" /> : <AutoAwesomeRounded />}
                    onClick={handleScan}
                    disabled={scanning}
                  >
                    {scanning ? 'در حال پویش خودکار گفتگوها…' : 'پویش هوشمند گفتگوها'}
                  </Button>
                  <Button
                    variant="outlined"
                    color="primary"
                    startIcon={<AddCircleOutlineRounded />}
                    onClick={openManualEvent}
                  >
                    ثبت رویداد جدید (دستی)
                  </Button>
                  <Typography variant="body2" color="text.secondary">
                    پیام‌های جدید کانال‌ها و گروه‌های تحت رصد برای کشف گزارش رویدادها تحلیل می‌شوند.
                  </Typography>
                </Stack>

                <Stack direction="row" spacing={1} alignItems="center">
                  <Typography variant="body2" color="text.secondary">
                    وضعیت:
                  </Typography>
                  <Select
                    size="small"
                    value={candidateFilter}
                    onChange={e => setCandidateFilter(e.target.value as any)}
                    sx={{ minWidth: 140 }}
                  >
                    <MenuItem value="pending">در انتظار بازبینی</MenuItem>
                    <MenuItem value="approved">تأیید شده</MenuItem>
                    <MenuItem value="rejected">رد شده</MenuItem>
                    <MenuItem value="all">همه</MenuItem>
                  </Select>
                </Stack>
              </Stack>
            </Paper>

            {/* Candidates List */}
            {loading && <LinearProgress />}
            {candidates.length === 0 && !loading ? (
              <Paper variant="outlined" sx={{ p: 4, textAlign: 'center', borderRadius: 2, bgcolor: '#fafafa', mt: 2 }}>
                <AutoAwesomeRounded sx={{ fontSize: 48, color: 'text.secondary', mb: 1.5 }} />
                <Typography variant="subtitle1" fontWeight={800} gutterBottom>
                  صف بازبینی هوشمند در حال حاضر خالی است
                </Typography>
                <Typography variant="body2" color="text.secondary" sx={{ maxWidth: 640, mx: 'auto', mb: 2.5 }}>
                  این سربرگ مخصوص «پیش‌نویس‌ها و پیام‌های شناسایی‌شده خودکار از گفتگوهای ایتا» است. برای کشف و بارگذاری خودکار پیام‌ها، ابتدا کانال‌ها و گروه‌های هدف را در تب «تنظیمات رصد گفتگوها» ثبت کنید و سپس روی دکمه «پویش هوشمند گفتگوها» کلیک نمایید.
                  <br />
                  <Typography component="span" variant="caption" sx={{ color: 'primary.main', fontWeight: 700, mt: 1, display: 'block' }}>
                    نکته: رویدادهایی که از روی پیام‌ها یا فرم دستی ثبت قطعی شده‌اند، مستقیماً در سربرگ <strong>«کارتابل و آرشیو گزارش‌ها»</strong> فهرست شده‌اند.
                  </Typography>
                </Typography>
                <Stack direction="row" spacing={1.5} justifyContent="center" flexWrap="wrap">
                  <Button
                    variant="contained"
                    color="primary"
                    startIcon={scanning ? <CircularProgress size={16} color="inherit" /> : <AutoAwesomeRounded />}
                    onClick={handleScan}
                    disabled={scanning}
                  >
                    {scanning ? 'در حال پویش خودکار گفتگوها…' : 'پویش هوشمند گفتگوها'}
                  </Button>
                  <Button
                    variant="outlined"
                    onClick={() => setCurrentTab(3)}
                  >
                    تنظیم کانال‌های رصد (تب ۳)
                  </Button>
                  <Button
                    variant="outlined"
                    color="secondary"
                    onClick={() => setCurrentTab(1)}
                  >
                    مشاهده کارتابل گزارش‌های ثبت‌شده (تب ۱)
                  </Button>
                </Stack>
              </Paper>
            ) : (
              <Grid container spacing={2}>
                {candidates.map(candidate => (
                  <Grid size={{ xs: 12, md: 6, lg: 4 }} key={candidate.candidate_id}>
                    <Card
                      variant="outlined"
                      sx={{
                        height: '100%',
                        display: 'flex',
                        flexDirection: 'column',
                        borderRadius: 2,
                        borderColor:
                          candidate.status === 'approved'
                            ? 'success.main'
                            : candidate.status === 'rejected'
                            ? 'text.disabled'
                            : 'primary.light',
                      }}
                    >
                      <CardHeader
                        title={
                          <Typography variant="subtitle1" fontWeight={700}>
                            {candidate.dialog_label || 'گفتگوی نامشخص'}
                          </Typography>
                        }
                        subheader={
                          <Typography variant="caption" color="text.secondary">
                            شناسه پیام: {candidate.message_ref} | پلتفرم: {candidate.platform}
                          </Typography>
                        }
                        action={
                          <Chip
                            size="small"
                            label={
                              candidate.status === 'approved'
                                ? 'تأیید شده'
                                : candidate.status === 'rejected'
                                ? 'رد شده'
                                : 'نیازمند بررسی'
                            }
                            color={
                              candidate.status === 'approved'
                                ? 'success'
                                : candidate.status === 'rejected'
                                ? 'default'
                                : 'warning'
                            }
                          />
                        }
                      />
                      <Divider />
                      <CardContent sx={{ flex: 1 }}>
                        <Stack spacing={1.5}>
                          {/* Program & Kind chips */}
                          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                            {candidate.matched_programs.map(p => (
                              <Chip
                                key={p}
                                size="small"
                                label={PROGRAM_NAMES[p] || p}
                                color="primary"
                                variant="outlined"
                              />
                            ))}
                            {candidate.candidate_kind === 'ashura_pilgrimage' && (
                              <Chip
                                size="small"
                                label="زیارت عاشورا (آمار مستقل)"
                                color="secondary"
                              />
                            )}
                          </Box>

                          {/* Details */}
                          {candidate.attendee_count !== null && (
                            <Typography variant="body2" color="text.primary">
                              <strong>شمار شرکت‌کنندگان تخمینی:</strong> {candidate.attendee_count} نفر
                            </Typography>
                          )}

                          {candidate.unit_hints.length > 0 && (
                            <Typography variant="caption" color="text.secondary">
                              <strong>واحد / نشانه‌ها:</strong> {candidate.unit_hints.join('، ')}
                            </Typography>
                          )}

                          <Typography variant="caption" color="text.secondary">
                            <strong>دقت شناسایی:</strong> {(candidate.confidence * 100).toFixed(0)}%
                          </Typography>

                          {candidate.rejection_reason && (
                            <Alert severity="error" sx={{ py: 0.5, px: 1 }}>
                              دلیل رد: {candidate.rejection_reason}
                            </Alert>
                          )}
                        </Stack>
                      </CardContent>

                      {/* Actions */}
                      {candidate.status === 'pending' && (
                        <>
                          <Divider />
                          <CardActions sx={{ justifyContent: 'flex-end', px: 2, py: 1 }}>
                            <Button
                              size="small"
                              color="error"
                              onClick={() => openReject(candidate)}
                            >
                              رد گزارش
                            </Button>
                            <Button
                              size="small"
                              variant="contained"
                              color="success"
                              onClick={() => openApprove(candidate)}
                            >
                              تأیید و ثبت رویداد
                            </Button>
                          </CardActions>
                        </>
                      )}
                    </Card>
                  </Grid>
                ))}
              </Grid>
            )}
          </Stack>
        )}

        {/* ================= TAB 1: کاربرگ‌ها و فرم‌های هفت‌گانه ================= */}
                {/* ================= TAB 1: کارتابل و آرشیو گزارش‌ها ================= */}
        {currentTab === 1 && (
          <Stack spacing={2.5}>
            {/* Filter Bar */}
            <Paper variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
              <Stack spacing={2}>
                <Stack direction={{ xs: 'column', md: 'row' }} spacing={1.5} alignItems={{ xs: 'stretch', md: 'center' }} justifyContent="space-between">
                  <Stack direction="row" spacing={1} alignItems="center">
                    <AssignmentTurnedInRounded color="primary" />
                    <Box>
                      <Typography variant="subtitle1" fontWeight={800}>
                        کارتابل و صدور گزارش‌ها
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        بازبینی پرونده‌ها، فیلتر پیشرفته، رفع نقص و پیش‌نمایش تجمیع و صدور اکسل الگوی رسمی استان (۱۴۰۵)
                      </Typography>
                    </Box>
                  </Stack>
                  <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, alignItems: 'center', width: { xs: '100%', md: 'auto' }, justifyContent: { xs: 'flex-start', md: 'flex-end' } }}>
                    <Button
                      variant={cartableSubTab === 'export_workbook' ? 'contained' : 'outlined'}
                      color="primary"
                      size="small"
                      startIcon={<FileDownloadRounded />}
                      onClick={() => {
                        setCartableSubTab('export_workbook')
                        void loadForms()
                        void loadEventsAndExports()
                      }}
                      sx={{ fontWeight: 800 }}
                    >
                      پیش‌نمایش تجمیع و صدور اکسل
                    </Button>
                    <Button
                      variant="outlined"
                      color="info"
                      size="small"
                      startIcon={<BarChartRounded />}
                      onClick={() => {
                        setUnitsModalTab(3)
                        setUnitsModalOpen(true)
                      }}
                    >
                      بانک اطلاعات پایه و ظرفیت‌سنجی
                    </Button>
                    <Button
                      variant="outlined"
                      color="secondary"
                      size="small"
                      startIcon={exportingBundle ? <CircularProgress size={16} color="inherit" /> : <FolderZipRounded />}
                      onClick={handleExportDossierBundle}
                      disabled={exportingBundle || loadingCartable}
                    >
                      صدور بسته اسناد و تصاویر (ZIP)
                    </Button>
                    <Button
                      variant="outlined"
                      color="primary"
                      size="small"
                      startIcon={exportingFiltered ? <CircularProgress size={16} color="inherit" /> : <FileDownloadRounded />}
                      onClick={handleExportFilteredEvents}
                      disabled={exportingFiltered || loadingCartable}
                    >
                      خروجی فهرست سوابق (Excel)
                    </Button>
                    <IconButton size="small" onClick={() => {
                      void loadEventsCartable()
                      if (cartableSubTab === 'export_workbook') {
                        void loadForms()
                        void loadEventsAndExports()
                      }
                    }} disabled={loadingCartable}>
                      <RefreshRounded />
                    </IconButton>
                  </Box>
                </Stack>

                <Divider />

                {/* Sub-view switcher tabs */}
                <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
                  <Tabs
                    value={cartableSubTab}
                    onChange={(_e, val) => {
                      setCartableSubTab(val)
                      if (val === 'export_workbook') {
                        void loadForms()
                        void loadEventsAndExports()
                      } else {
                        void loadEventsCartable()
                      }
                    }}
                    textColor="primary"
                    indicatorColor="primary"
                    variant="scrollable"
                    scrollButtons="auto"
                  >
                    <Tab
                      value="cartable"
                      label={
                        <Stack direction="row" spacing={1} alignItems="center">
                          <AssignmentTurnedInRounded fontSize="small" />
                          <Typography variant="body2" fontWeight={700}>
                            سوابق و پرونده‌های رویدادها ({cartableEvents.length})
                          </Typography>
                        </Stack>
                      }
                    />
                    <Tab
                      value="export_workbook"
                      label={
                        <Badge
                          badgeContent={totalUnresolvedStars > 0 ? totalUnresolvedStars : 0}
                          color="warning"
                          sx={{ pr: totalUnresolvedStars > 0 ? 1.5 : 0 }}
                        >
                          <Stack direction="row" spacing={1} alignItems="center">
                            <FileDownloadRounded fontSize="small" />
                            <Typography variant="body2" fontWeight={700}>
                              پیش‌نمایش تجمیع و صدور اکسل فایل الگو (۱۴۰۵)
                            </Typography>
                          </Stack>
                        </Badge>
                      }
                    />
                  </Tabs>
                </Box>
                {cartableSubTab === 'cartable' && (
                  <>


                <Divider />

                {/* Filters Grid */}
                <Grid container spacing={1.5} alignItems="center">
                  <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                    <TextField
                      size="small"
                      fullWidth
                      label="جستجو در سوابق"
                      placeholder="عنوان، شرح، واحد، مناسبت..."
                      value={filterSearch}
                      onChange={e => setFilterSearch(e.target.value)}
                    />
                  </Grid>

                  <Grid size={{ xs: 12, sm: 6, md: 2 }}>
                    <FormControl size="small" fullWidth>
                      <InputLabel>وضعیت پرونده</InputLabel>
                      <Select
                        label="وضعیت پرونده"
                        value={filterStatus}
                        onChange={e => setFilterStatus(e.target.value)}
                      >
                        <MenuItem value="all">همه وضعیت‌ها</MenuItem>
                        <MenuItem value="approved">تأیید نهایی مدیر</MenuItem>
                        <MenuItem value="needs_review">نیازمند بازبینی / اصلاح</MenuItem>
                        <MenuItem value="conflict">تعارض / رد شده</MenuItem>
                        <MenuItem value="draft">پیش‌نویس اولیه</MenuItem>
                      </Select>
                    </FormControl>
                  </Grid>

                  <Grid size={{ xs: 12, sm: 6, md: 2.5 }}>
                    <FormControl size="small" fullWidth>
                      <InputLabel>سرفصل / برنامه</InputLabel>
                      <Select
                        label="سرفصل / برنامه"
                        value={filterProgram}
                        onChange={e => setFilterProgram(e.target.value)}
                      >
                        <MenuItem value="all">همه برنامه‌ها</MenuItem>
                        {programsCatalog.map(p => (
                          <MenuItem key={p.program_code} value={p.program_code}>
                            {p.program_code} - {p.title}
                          </MenuItem>
                        ))}
                      </Select>
                    </FormControl>
                  </Grid>

                  <Grid size={{ xs: 12, sm: 6, md: 2.5 }}>
                    <FormControl size="small" fullWidth>
                      <InputLabel>شاخصه کلان</InputLabel>
                      <Select
                        label="شاخصه کلان"
                        value={filterMacro}
                        onChange={e => setFilterMacro(e.target.value)}
                      >
                        <MenuItem value="all">همه شاخصه‌ها</MenuItem>
                        {macroOptions.map(m => (
                          <MenuItem key={m} value={m}>
                            {m}
                          </MenuItem>
                        ))}
                      </Select>
                    </FormControl>
                  </Grid>

                  <Grid size={{ xs: 12, sm: 6, md: 2 }}>
                    <Autocomplete
                      freeSolo
                      size="small"
                      options={microOptions.map(m => m.title)}
                      value={filterMicro === 'all' ? '' : filterMicro}
                      onChange={(_e: unknown, val: string | null) => setFilterMicro(val || 'all')}
                      onInputChange={(_e: unknown, val: string) => {
                        if (!val) setFilterMicro('all')
                      }}
                      renderInput={(params: any) => (
                        <TextField {...params} label="شاخصه جزئی" placeholder="فیلتر شاخصه جزئی..." />
                      )}
                    />
                  </Grid>

                  <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                    <Autocomplete
                      freeSolo
                      size="small"
                      options={judicialUnits.map(u => u.display_name || u.name)}
                      value={filterUnit === 'all' ? '' : filterUnit}
                      onChange={(_e: unknown, val: string | null) => setFilterUnit(val || 'all')}
                      onInputChange={(_e: unknown, val: string) => {
                        if (!val) setFilterUnit('all')
                      }}
                      renderInput={(params: any) => (
                        <TextField {...params} label="حوزه قضایی / شهرستان" placeholder="فیلتر شهرستان..." />
                      )}
                    />
                  </Grid>

                  <Grid size={{ xs: 12, sm: 6, md: 2 }}>
                    <Button
                      variant="outlined"
                      size="small"
                      fullWidth
                      onClick={() => {
                        setFilterSearch('')
                        setFilterStatus('all')
                        setFilterProgram('all')
                        setFilterMacro('all')
                        setFilterMicro('all')
                        setFilterUnit('all')
                      }}
                    >
                      حذف تمام فیلترها
                    </Button>
                  </Grid>
                </Grid>

                  </>
                )}
              </Stack>
            </Paper>

            {cartableSubTab === 'cartable' && (
              <>


            {lastFilteredExportResult && (
              <Alert severity="success" onClose={() => setLastFilteredExportResult(null)} sx={{ borderRadius: 2 }}>
                فایل اکسل گزارش‌های فیلترشده با موفقیت ایجاد شد: <strong>{lastFilteredExportResult.fileName}</strong> ({lastFilteredExportResult.count} رکورد)
                <br />
                <Typography variant="caption" color="text.secondary">
                  مسیر ذخیره محلی: {lastFilteredExportResult.path}
                </Typography>
              </Alert>
            )}

            {/* Live Aggregation Summary KPI Cards */}
            <Grid container spacing={1.5}>
              <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                <Card variant="outlined" sx={{ p: 1.5, textAlign: 'center', bgcolor: 'background.paper', borderRadius: 2, borderColor: 'primary.light' }}>
                  <Typography variant="caption" color="text.secondary">تعداد رویدادهای فیلترشده</Typography>
                  <Typography variant="h6" fontWeight={800} color="primary.main">
                    {cartableSummary.totalEvents.toLocaleString('fa-IR')} <Typography component="span" variant="caption">رویداد</Typography>
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    {filterProgram !== 'all' ? `سرفصل: ${filterProgram}` : 'تمامی سرفصل‌ها'}
                  </Typography>
                </Card>
              </Grid>
              <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                <Card variant="outlined" sx={{ p: 1.5, textAlign: 'center', bgcolor: 'background.paper', borderRadius: 2, borderColor: 'success.light' }}>
                  <Typography variant="caption" color="text.secondary">مجموع مخاطبان / شرکت‌کنندگان</Typography>
                  <Typography variant="h6" fontWeight={800} color="success.main">
                    {cartableSummary.totalParticipants.toLocaleString('fa-IR')} <Typography component="span" variant="caption">نفر</Typography>
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    {cartableSummary.colleaguesCount > 0
                      ? `${cartableSummary.colleaguesCount.toLocaleString('fa-IR')} همکار + ${cartableSummary.familyCount.toLocaleString('fa-IR')} خانواده`
                      : 'محاسبه از فکت‌های ثبت‌شده'}
                  </Typography>
                </Card>
              </Grid>
              <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                <Card variant="outlined" sx={{ p: 1.5, textAlign: 'center', bgcolor: 'background.paper', borderRadius: 2, borderColor: 'warning.light' }}>
                  <Typography variant="caption" color="text.secondary">میانگین رضایت‌مندی / نظرسنجی</Typography>
                  <Typography variant="h6" fontWeight={800} color="warning.main">
                    {cartableSummary.surveyCount > 0 ? `${cartableSummary.avgSurvey}٪` : 'فاقد ارزیابی'}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    {cartableSummary.surveyCount > 0 ? `سنجش بر مبنای ${cartableSummary.surveyCount} ارزیابی` : 'نظرسنجی ثبت‌نشده'}
                  </Typography>
                </Card>
              </Grid>
              <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                <Card variant="outlined" sx={{ p: 1.5, textAlign: 'center', bgcolor: 'background.paper', borderRadius: 2, borderColor: 'info.light' }}>
                  <Typography variant="caption" color="text.secondary">حوزه‌های قضایی درگیر</Typography>
                  <Typography variant="h6" fontWeight={800} color="info.main">
                    {cartableSummary.uniqueUnitsCount.toLocaleString('fa-IR')} <Typography component="span" variant="caption">حوزه</Typography>
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    از کل حوزه‌های فعال استان
                  </Typography>
                </Card>
              </Grid>
            </Grid>

            {/* Events Cartable Table */}
            <Paper variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
              <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 1.5 }}>
                <Typography variant="subtitle2" fontWeight={800}>
                  فهرست گزارش‌های ثبت‌شده ({cartableEvents.length} رویداد)
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  برای بازبینی کامل، اصلاح نقایص، بررسی شواهد ایتا و ویرایش، روی هر ردیف یا دکمه مشاهده کلیک کنید.
                </Typography>
              </Stack>

              <TableContainer sx={{ maxHeight: 520, overflowX: 'auto' }}>
                <Table stickyHeader size="small" sx={{ minWidth: 900 }}>
                  <TableHead>
                    <TableRow sx={{ bgcolor: 'action.hover' }}>
                      <TableCell sx={{ fontWeight: 700, width: 45 }}>#</TableCell>
                      <TableCell sx={{ fontWeight: 800 }}>عنوان و مناسبت رویداد</TableCell>
                      <TableCell sx={{ fontWeight: 700 }}>سرفصل / برنامه</TableCell>
                      <TableCell sx={{ fontWeight: 700 }}>شاخصه کلی و جزئی</TableCell>
                      <TableCell sx={{ fontWeight: 700 }}>تاریخ وقوع (شمسی)</TableCell>
                      <TableCell sx={{ fontWeight: 700 }}>حوزه قضایی / شهرستان</TableCell>
                      <TableCell sx={{ fontWeight: 700 }}>شناسه پرونده</TableCell>
                      <TableCell sx={{ fontWeight: 700 }}>ثبت‌کننده</TableCell>
                      <TableCell sx={{ fontWeight: 700 }} align="center">وضعیت پرونده</TableCell>
                      <TableCell sx={{ fontWeight: 700 }} align="center">کیفیت / نقایص</TableCell>
                      <TableCell sx={{ fontWeight: 700 }} align="center">عملیات</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {loadingCartable ? (
                      <TableRow>
                        <TableCell colSpan={11} align="center" sx={{ py: 4 }}>
                          <CircularProgress size={28} />
                          <Typography variant="caption" display="block" sx={{ mt: 1 }}>
                            در حال دریافت پرونده‌های گزارش...
                          </Typography>
                        </TableCell>
                      </TableRow>
                    ) : cartableEvents.length === 0 ? (
                      <TableRow>
                        <TableCell colSpan={11} align="center" sx={{ py: 4 }}>
                          <Typography variant="body2" color="text.secondary">
                            هیچ رویدادی مطابق با فیلترهای جاری یافت نشد.
                          </Typography>
                        </TableCell>
                      </TableRow>
                    ) : (
                      cartableEvents.map((ev, idx) => {
                        const statusLabel =
                          ev.review_status === 'approved'
                            ? 'تأیید مدیر'
                            : ev.review_status === 'conflict'
                            ? 'تعارض / رد'
                            : ev.review_status === 'needs_review'
                            ? (ev.revision_count && ev.revision_count > 0 ? `اصلاحیه (${ev.revision_count})` : 'در انتظار بررسی')
                            : 'پیش‌نویس'
                        const statusColor =
                          ev.review_status === 'approved'
                            ? 'success'
                            : ev.review_status === 'conflict'
                            ? 'error'
                            : ev.review_status === 'needs_review'
                            ? 'warning'
                            : 'default'

                        const creator = ev.registered_by_name || ev.registered_by_id || ev.created_by || 'نامشخص'
                        const defects = Array.isArray(ev.defects) ? ev.defects : []
                        const hasBlockers = defects.some((d: any) => d.severity === 'blocker')
                        const defectCount = defects.length

                        return (
                          <TableRow
                            key={ev.event_id}
                            hover
                            sx={{
                              cursor: 'pointer',
                              transition: 'background-color 0.15s',
                              '&:hover': { bgcolor: 'action.hover' },
                            }}
                            onClick={() => setDetailModalEventId(ev.event_id)}
                          >
                            <TableCell sx={{ fontWeight: 600 }}>{idx + 1}</TableCell>

                            {/* 1. Title / Occasion as First Primary Column */}
                            <TableCell sx={{ maxWidth: 260 }}>
                              <Typography variant="body2" fontWeight={800} color="primary.main" noWrap title={ev.occasion || ''}>
                                {ev.occasion || '—'}
                              </Typography>
                              {ev.notes && (
                                <Typography variant="caption" color="text.secondary" noWrap display="block" title={ev.notes}>
                                  {ev.notes}
                                </Typography>
                              )}
                            </TableCell>

                            {/* 2. Program with Custom Color Coding */}
                            <TableCell sx={{ minWidth: 150 }}>
                              {ev.macro_category === 'other_cultural' ? (
                                <Chip
                                  size="small"
                                  label={ev.custom_topic ? `سایر: ${ev.custom_topic}` : 'سایر فعالیت‌های فرهنگی'}
                                  sx={{
                                    mr: 0.5,
                                    mb: 0.5,
                                    fontWeight: 700,
                                    fontSize: '0.75rem',
                                    bgcolor: PROGRAM_STYLES.other_cultural.bg,
                                    color: PROGRAM_STYLES.other_cultural.color,
                                    border: `1px solid ${PROGRAM_STYLES.other_cultural.border}`,
                                  }}
                                />
                              ) : (
                                ev.program_kinds.map((p: string) => {
                                  const pStyle = getProgramBadgeStyle(p)
                                  return (
                                    <Chip
                                      key={p}
                                      size="small"
                                      label={getProgramTitle(p)}
                                      sx={{
                                        mr: 0.5,
                                        mb: 0.5,
                                        fontSize: '0.75rem',
                                        fontWeight: 700,
                                        bgcolor: pStyle.bg,
                                        color: pStyle.color,
                                        border: `1px solid ${pStyle.border}`,
                                      }}
                                    />
                                  )
                                })
                              )}
                            </TableCell>

                            {/* 3. Indicators */}
                            <TableCell sx={{ maxWidth: 200 }}>
                              {ev.macro_indicator && (
                                <Chip
                                  size="small"
                                  label={ev.macro_indicator}
                                  sx={{ mr: 0.5, mb: 0.5, bgcolor: 'primary.50', fontWeight: 600, fontSize: '0.7rem' }}
                                />
                              )}
                              {Array.isArray(ev.micro_indicators) &&
                                ev.micro_indicators.map((m: string) => (
                                  <Chip
                                    key={m}
                                    size="small"
                                    label={m}
                                    variant="outlined"
                                    sx={{ mr: 0.5, mb: 0.5, fontSize: '0.65rem' }}
                                  />
                                ))}
                            </TableCell>

                            {/* 4. Solar Date */}
                            <TableCell sx={{ fontSize: '0.85rem', whiteSpace: 'nowrap', fontWeight: 700 }}>
                              {formatDisplayJalaliDate(ev.occurred_on)}
                            </TableCell>

                            {/* 5. Judicial Unit */}
                            <TableCell sx={{ fontSize: '0.8rem' }}>
                              {ev.unit_name || ev.unit}
                            </TableCell>

                            {/* 6. Event ID */}
                            <TableCell sx={{ fontFamily: 'monospace', fontWeight: 600, fontSize: '0.75rem' }}>
                              {ev.event_id}
                            </TableCell>
                            <TableCell>
                              <Typography variant="caption" fontWeight={600} display="block">
                                {creator}
                              </Typography>
                              {ev.reviewed_by_name && (
                                <Typography variant="caption" color="text.secondary" display="block">
                                  تأیید: {ev.reviewed_by_name}
                                </Typography>
                              )}
                            </TableCell>
                            <TableCell align="center">
                              <Chip
                                size="small"
                                label={statusLabel}
                                color={statusColor}
                                variant={ev.review_status === 'approved' ? 'filled' : 'outlined'}
                                sx={{ fontWeight: 700 }}
                              />
                            </TableCell>
                            <TableCell align="center">
                              {defectCount > 0 ? (
                                <Chip
                                  size="small"
                                  color={hasBlockers ? 'error' : 'warning'}
                                  label={`${defectCount} نقص/هشدار`}
                                  onClick={e => {
                                    e.stopPropagation()
                                    setDefectDialogEvent(ev)
                                  }}
                                  sx={{ fontWeight: 700, fontSize: '0.7rem', cursor: 'pointer' }}
                                />
                              ) : (
                                <Chip size="small" color="success" variant="outlined" label="بدون نقص" sx={{ fontSize: '0.7rem' }} />
                              )}
                            </TableCell>
                            <TableCell align="center" onClick={e => e.stopPropagation()}>
                              <Stack direction="row" spacing={0.5} justifyContent="center" alignItems="center">
                                <Button
                                  size="small"
                                  variant="outlined"
                                  color="primary"
                                  onClick={() => setDetailModalEventId(ev.event_id)}
                                  sx={{ fontSize: '0.75rem', px: 1, minWidth: 'auto' }}
                                >
                                  مشاهده و ویرایش
                                </Button>
                                {ev.review_status !== 'approved' && (
                                  <Tooltip title="تأیید سریع رویداد">
                                    <Button
                                      size="small"
                                      variant="contained"
                                      color="success"
                                      disabled={workflowActionLoading}
                                      onClick={() => void handleApproveEvent(ev.event_id)}
                                      sx={{ fontSize: '0.75rem', px: 1, minWidth: 'auto' }}
                                    >
                                      تأیید
                                    </Button>
                                  </Tooltip>
                                )}
                                <Tooltip title="حذف کامل این پرونده">
                                  <IconButton
                                    size="small"
                                    color="error"
                                    onClick={async () => {
                                      if (window.confirm(`آیا از حذف کامل پرونده "${ev.occasion || ev.event_id}" اطمینان دارید؟`)) {
                                        try {
                                          await api('DELETE', `/api/v3/reporting/events/${encodeURIComponent(ev.event_id)}`)
                                          toast.success('پرونده رویداد با موفقیت حذف گردید.')
                                          void loadEventsCartable()
                                          void loadEventsAndExports()
                                        } catch (err) {
                                          toast.error(err instanceof Error ? err.message : 'خطا در حذف رویداد')
                                        }
                                      }
                                    }}
                                  >
                                    <DeleteOutlineRounded fontSize="small" />
                                  </IconButton>
                                </Tooltip>
                              </Stack>
                            </TableCell>
                          </TableRow>
                        )
                      })
                    )}
                  </TableBody>
                </Table>

              </TableContainer>
            </Paper>
              </>
            )}

            {cartableSubTab === 'export_workbook' && (
              <Stack spacing={2.5}>
            {/* Export Readiness Card */}
            <Paper variant="outlined" sx={{ p: 3, borderRadius: 2 }}>
              <Typography variant="h6" fontWeight={800} gutterBottom>
                صدور فایل اکسل گزارش نهایی استان
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                این گزارش فایل الگو (Template) را بدون تغییر حفظ کرده و یک نسخهٔ جدید با فرمت استاندارد در پوشهٔ خروجی ثبت می‌کند.
              </Typography>

              {totalUnresolvedStars > 0 ? (
                <Alert severity="warning" sx={{ mb: 2 }}>
                  <strong>هشدار خانه‌های ستاره‌دار الزامی:</strong> در مجموع {totalUnresolvedStars} فیلد ستاره‌دار در کاربرگ‌ها خالی مانده است. مطابق ضوابط دستورالعمل ۱۴۰۵، صدور نهایی قبل از تکمیل این موارد توصیه نمی‌شود مگر با فعال‌سازی گزینهٔ صدور اضطراری.
                </Alert>
              ) : (
                <Alert severity="success" sx={{ mb: 2 }}>
                  تمام فیلدهای ستاره‌دار کاربرگ‌های هفت‌گانه کامل هستند و سامانه آماده صدور نهایی بدون نقص است.
                </Alert>
              )}

              {exportBlockers.length > 0 && (
                <Alert severity="error" sx={{ mb: 2 }}>
                  <strong>خانه‌های مانع صدور:</strong>
                  <ul>
                    {exportBlockers.map(b => (
                      <li key={b.program_id}>
                        {PROGRAM_NAMES[b.program_id] || b.program_id}: فیلدهای {b.missing_star_keys.join('، ')}
                      </li>
                    ))}
                  </ul>
                </Alert>
              )}

              <Grid container spacing={2} alignItems="center">
                <Grid size={{ xs: 12 }}>
                  <FormControl component="fieldset">
                    <FormLabel component="legend" sx={{ fontWeight: 700, fontSize: '0.85rem', mb: 0.5 }}>
                      دامنه و نحوه صدور اکسل:
                    </FormLabel>
                    <RadioGroup
                      row
                      value={exportScope}
                      onChange={e => setExportScope(e.target.value as 'all' | 'single')}
                    >
                      <FormControlLabel
                        value="all"
                        control={<Radio size="small" />}
                        label={<Typography variant="body2" fontWeight={700}>صدور جامع استانی (فایل تجمیعی کامل سال ۱۴۰۵)</Typography>}
                      />
                      <FormControlLabel
                        value="single"
                        control={<Radio size="small" />}
                        label={<Typography variant="body2" fontWeight={700}>صدور تک‌کاربرگ تفکیکی (Single Worksheet)</Typography>}
                      />
                    </RadioGroup>
                  </FormControl>
                </Grid>

                {exportScope === 'single' && (
                  <Grid size={{ xs: 12 }}>
                    <FormControl size="small" fullWidth>
                      <InputLabel>انتخاب کاربرگ جهت صدور شیت مستقل</InputLabel>
                      <Select
                        label="انتخاب کاربرگ جهت صدور شیت مستقل"
                        value={selectedSingleProgram}
                        onChange={e => setSelectedSingleProgram(e.target.value)}
                      >
                        {programsCatalog
                          .filter(p => p.workbook_sheet)
                          .map(p => (
                            <MenuItem key={p.program_code} value={p.kind || p.program_code}>
                              {p.program_code} - {p.title} (شیت الگوی: {p.workbook_sheet})
                            </MenuItem>
                          ))}
                      </Select>
                    </FormControl>
                  </Grid>
                )}

                <Grid size={{ xs: 12, sm: 4 }}>
                  <TextField
                    label="نام استان"
                    size="small"
                    fullWidth
                    value={exportProvince}
                    onChange={e => setExportProvince(e.target.value)}
                  />
                </Grid>
                <Grid size={{ xs: 12, sm: 4 }}>
                  <TextField
                    label="دورهٔ گزارش"
                    size="small"
                    fullWidth
                    value={exportPeriod}
                    onChange={e => setExportPeriod(e.target.value)}
                  />
                </Grid>
                <Grid size={{ xs: 12, sm: 4 }}>
                  <FormControlLabel
                    control={
                      <Checkbox
                        checked={exportForceUnresolved}
                        onChange={e => setExportForceUnresolved(e.target.checked)}
                      />
                    }
                    label="اجازه صدور با فیلدهای ستاره‌دار ناقص"
                  />
                </Grid>
              </Grid>

              <Box sx={{ mt: 2.5, display: 'flex', justifyContent: { xs: 'stretch', sm: 'flex-end' } }}>
                <Button
                  variant="contained"
                  color="primary"
                  size="large"
                  startIcon={exporting ? <CircularProgress size={20} color="inherit" /> : <FileDownloadRounded />}
                  sx={{ width: { xs: '100%', sm: 'auto' }, fontWeight: 800 }}
                  onClick={handleExport}
                  disabled={exporting}
                >
                  {exporting ? 'در حال ایجاد فایل اکسل…' : 'صدور فایل اکسل نهایی'}
                </Button>
              </Box>

              {lastExportResult && (
                <Alert severity="success" sx={{ mt: 2 }}>
                  فایل با موفقیت صادر شد: <strong>{lastExportResult.fileName}</strong>
                  <br />
                  <Typography variant="caption" color="text.secondary">
                    مسیر ذخیره محلی: {lastExportResult.path}
                  </Typography>
                </Alert>
              )}
            </Paper>

            {/* Workbook Aggregations Preview Matrix */}
            <Paper variant="outlined" sx={{ p: { xs: 1.5, sm: 2.5 }, borderRadius: 2 }}>
              <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 2 }} flexWrap="wrap" gap={1}>
                <Box>
                  <Typography variant="subtitle1" fontWeight={800}>
                    پیش‌نمایش تجمیعی کاربرگ‌های هفت‌گانه مصوب (الگوی ۱۴۰۵)
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    وضعیت آماده‌سازی سلول‌ها، ارقام و پرونده‌های متناظر استان برای درج در فایل الگو
                  </Typography>
                </Box>
                <Chip
                  color={totalUnresolvedStars === 0 ? "success" : "warning"}
                  variant="outlined"
                  label={totalUnresolvedStars === 0 ? "کلیه کاربرگ‌ها تکمیل است" : `${totalUnresolvedStars} فیلد ستاره‌دار باز`}
                  sx={{ fontWeight: 700 }}
                />
              </Stack>
              <TableContainer sx={{ maxHeight: 380, overflowX: 'auto' }}>
                <Table stickyHeader size="small" sx={{ minWidth: 700 }}>
                  <TableHead>
                    <TableRow sx={{ bgcolor: 'action.hover' }}>
                      <TableCell sx={{ fontWeight: 700, width: 90 }}>کد سرفصل</TableCell>
                      <TableCell sx={{ fontWeight: 800 }}>عنوان برنامه و کاربرگ</TableCell>
                      <TableCell sx={{ fontWeight: 700 }}>شیت الگو در اکسل</TableCell>
                      <TableCell sx={{ fontWeight: 700 }} align="center">پرونده‌های مرتبط</TableCell>
                      <TableCell sx={{ fontWeight: 700 }} align="center">فیلدهای الزامی (ستاره‌دار)</TableCell>
                      <TableCell sx={{ fontWeight: 700 }} align="center">وضعیت شیت</TableCell>
                      <TableCell sx={{ fontWeight: 700 }} align="center">عملیات</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {programsCatalog.filter(p => p.workbook_sheet).map(p => {
                      const formObj = forms.find(f => f.program_id === p.kind || f.program_code === p.program_code)
                      const missingStars = formObj?.unresolved_star?.length || 0
                      const relEvents = cartableEvents.filter(ev =>
                        ev.program_kinds.includes(p.kind) || ev.program_kinds.includes(p.program_code)
                      ).length
                      const isReady = missingStars === 0
                      return (
                        <TableRow key={p.program_code} hover>
                          <TableCell sx={{ fontWeight: 700, fontFamily: 'monospace' }}>{p.program_code}</TableCell>
                          <TableCell sx={{ fontWeight: 700 }}>{p.title}</TableCell>
                          <TableCell>
                            <Chip size="small" variant="outlined" label={`شیت ${p.workbook_sheet}`} color="info" />
                          </TableCell>
                          <TableCell align="center">
                            <Chip size="small" label={`${relEvents} پرونده`} color={relEvents > 0 ? 'primary' : 'default'} variant="outlined" />
                          </TableCell>
                          <TableCell align="center">
                            {missingStars > 0 ? (
                              <Chip size="small" label={`${missingStars} فیلد خالی`} color="warning" />
                            ) : (
                              <Chip size="small" label="تکمیل شده" color="success" />
                            )}
                          </TableCell>
                          <TableCell align="center">
                            <Chip
                              size="small"
                              label={isReady ? 'آماده صدور' : 'نیازمند تکمیل'}
                              color={isReady ? 'success' : 'warning'}
                              variant={isReady ? 'filled' : 'outlined'}
                              sx={{ fontWeight: 700 }}
                            />
                          </TableCell>
                          <TableCell align="center">
                            <Button
                              size="small"
                              variant="text"
                              color="primary"
                              onClick={() => {
                                const formIdx = forms.findIndex(f => f.program_id === p.kind || f.program_code === p.program_code)
                                if (formIdx >= 0) setSelectedFormIndex(formIdx)
                                setCurrentTab(2)
                              }}
                              sx={{ fontSize: '0.75rem', py: 0.2 }}
                            >
                              ویرایش کاربرگ
                            </Button>
                          </TableCell>
                        </TableRow>
                      )
                    })}
                  </TableBody>
                </Table>
              </TableContainer>
            </Paper>

            {/* History of Exports */}
            <Paper variant="outlined" sx={{ p: 2.5, borderRadius: 2 }}>
              <Typography variant="subtitle1" fontWeight={800} sx={{ mb: 2 }}>
                تاریخچه و گزارش بازرسی صدورهای گذشته
              </Typography>
              <TableContainer sx={{ maxHeight: 280, overflowX: 'auto' }}>
                <Table stickyHeader size="small" sx={{ minWidth: 650 }}>
                  <TableHead>
                    <TableRow>
                      <TableCell>نام فایل</TableCell>
                      <TableCell>مسئول صدور</TableCell>
                      <TableCell>زمان صدور</TableCell>
                      <TableCell>تعداد رویداد</TableCell>
                      <TableCell>خانه‌های ستاره‌دار ناقص</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {exportsList.length === 0 ? (
                      <TableRow>
                        <TableCell colSpan={5} align="center">
                          هنوز صادراتی ثبت نشده است.
                        </TableCell>
                      </TableRow>
                    ) : (
                      exportsList.map(exp => (
                        <TableRow key={exp.export_id}>
                          <TableCell sx={{ fontWeight: 600 }}>{exp.file_name}</TableCell>
                          <TableCell>{exp.exported_by}</TableCell>
                          <TableCell>{exp.exported_at ? jalaliDayLabel(exp.exported_at) : '—'}</TableCell>
                          <TableCell>{exp.events_count}</TableCell>
                          <TableCell>
                            {exp.unresolved_star_count && exp.unresolved_star_count > 0 ? (
                              <Chip size="small" label={`${exp.unresolved_star_count} ستاره ناقص`} color="warning" />
                            ) : (
                              <Chip size="small" label="کامل" color="success" />
                            )}
                          </TableCell>
                        </TableRow>
                      ))
                    )}
                  </TableBody>
                </Table>
              </TableContainer>
            </Paper>
              </Stack>
            )}
          </Stack>
        )}

        {currentTab === 2 && (
          <Stack spacing={2.5}>
            {/* Date filter bar for workbooks */}
            <Paper variant="outlined" sx={{ p: 2, borderRadius: 2, bgcolor: 'background.paper' }}>
              <Stack spacing={1.5}>
                <Stack direction={{ xs: 'column', md: 'row' }} spacing={1.5} alignItems="center" justifyContent="space-between">
                  <Stack direction="row" spacing={1} alignItems="center">
                    <EventNoteRounded color="primary" />
                    <Box>
                      <Typography variant="subtitle2" fontWeight={800}>
                        فیلتر بازهٔ زمانی و محاسبهٔ خودکار مقادیر کاربرگ‌ها
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        با انتخاب بازهٔ تاریخی، اقلام آماری و محاسباتی کاربرگ‌ها بر اساس رویدادهای واقع در همان بازه بازشمارش می‌شوند.
                      </Typography>
                    </Box>
                  </Stack>
                  <Stack direction="row" spacing={1} alignItems="center">
                    {matchingEventsCount !== null && (
                      <Chip
                        size="small"
                        icon={<CheckCircleOutlineRounded fontSize="small" />}
                        label={`رویدادهای تطبیق‌یافته: ${matchingEventsCount} مورد`}
                        color={matchingEventsCount > 0 ? 'primary' : 'default'}
                        variant="outlined"
                        sx={{ fontWeight: 700 }}
                      />
                    )}
                    {(formDateFrom || formDateTo) ? (
                      <Chip
                        size="small"
                        color="secondary"
                        label="بازه تاریخی فعال است"
                        onDelete={() => {
                          setFormDateFrom('')
                          setFormDateTo('')
                          void loadForms('', '')
                        }}
                      />
                    ) : (
                      <Chip
                        size="small"
                        variant="outlined"
                        label="کل دوره (بدون فیلتر تاریخ)"
                        sx={{ color: 'text.secondary' }}
                      />
                    )}
                  </Stack>
                </Stack>

                <Divider sx={{ my: 0.5 }} />

                <Grid container spacing={1.5} alignItems="flex-end">
                  <Grid size={{ xs: 12, md: 7 }}>
                    <JalaliDateRangePicker
                      startDate={formDateFrom}
                      endDate={formDateTo}
                      onRangeChange={(start, end) => {
                        setFormDateFrom(start)
                        setFormDateTo(end)
                      }}
                      label="انتخاب بازه تاریخی برگزاری رویدادها (شمسی)"
                    />
                  </Grid>
                  <Grid size={{ xs: 12, md: 5 }}>
                    <Stack direction="row" spacing={1} sx={{ mt: { xs: 1, md: 0 } }}>
                      <Button
                        variant="contained"
                        color="primary"
                        size="small"
                        startIcon={loadingForms ? <CircularProgress size={16} color="inherit" /> : <RefreshRounded />}
                        onClick={() => void loadForms(formDateFrom, formDateTo)}
                        disabled={loadingForms}
                        sx={{ flex: 1, py: 0.8 }}
                      >
                        {loadingForms ? 'در حال بازشمارش…' : 'اعمال بازه و محاسبه مجدد مقادیر'}
                      </Button>
                      {(formDateFrom || formDateTo) && (
                        <Button
                          variant="outlined"
                          color="inherit"
                          size="small"
                          onClick={() => {
                            setFormDateFrom('')
                            setFormDateTo('')
                            void loadForms('', '')
                          }}
                          disabled={loadingForms}
                          sx={{ py: 0.8 }}
                        >
                          مشاهده کل دوره
                        </Button>
                      )}
                    </Stack>
                  </Grid>
                </Grid>
              </Stack>
            </Paper>

            <Grid container spacing={3}>
            {/* Sidebar list of 8 forms */}
            <Grid size={{ xs: 12, md: 3.5 }}>
              <Paper variant="outlined" sx={{ borderRadius: 2, overflow: 'hidden' }}>
                <Box sx={{ p: 2, bgcolor: 'action.hover', borderBottom: 1, borderColor: 'divider' }}>
                  <Typography variant="subtitle2" fontWeight={800}>
                    کاربرگ‌های عملیاتی فرهنگی (۸ گانه)
                  </Typography>
                </Box>
                <Stack divider={<Divider />}>
                  {forms.map((f, idx) => (
                    <Box
                      key={f.program_id}
                      onClick={() => setSelectedFormIndex(idx)}
                      sx={{
                        p: 1.5,
                        cursor: 'pointer',
                        bgcolor: selectedFormIndex === idx ? 'primary.light' : 'transparent',
                        color: selectedFormIndex === idx ? 'primary.contrastText' : 'text.primary',
                        transition: 'background 0.2s',
                        '&:hover': {
                          bgcolor: selectedFormIndex === idx ? 'primary.light' : 'action.hover',
                        },
                      }}
                    >
                      <Stack direction="row" justifyContent="space-between" alignItems="center">
                        <Typography variant="body2" fontWeight={selectedFormIndex === idx ? 800 : 500}>
                          {f.title}
                        </Typography>
                        {f.unresolved_star && f.unresolved_star.length > 0 && (
                          <Chip
                            size="small"
                            label={`${f.unresolved_star.length} ستاره`}
                            color={selectedFormIndex === idx ? 'default' : 'warning'}
                            sx={{ height: 20, fontSize: '0.7rem' }}
                          />
                        )}
                      </Stack>
                    </Box>
                  ))}
                </Stack>
              </Paper>
            </Grid>

            {/* Form Fields Editor */}
            <Grid size={{ xs: 12, md: 8.5 }}>
              {selectedForm ? (
                <Paper variant="outlined" sx={{ p: 3, borderRadius: 2 }}>
                  <Stack spacing={2.5}>
                    <Stack direction="row" justifyContent="space-between" alignItems="center">
                      <Box>
                        <Typography variant="h6" fontWeight={800}>
                          {selectedForm.title}
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          کد عملیاتی: {selectedForm.program_code || selectedForm.program_id} | شناسه سیستمی: {selectedForm.program_id} | تعداد کل فیلدها: {selectedForm.questions.length}
                        </Typography>
                      </Box>
                      <Stack direction="row" spacing={1} alignItems="center">
                        <Button
                          variant="outlined"
                          color="info"
                          startIcon={<FormatListBulletedRounded />}
                          onClick={() => void loadEventsForActiveForm()}
                          sx={{ fontWeight: 700 }}
                        >
                          ریز گزارش‌های متناظر
                        </Button>
                        <Button
                          variant="contained"
                          color="primary"
                          startIcon={savingForm ? <CircularProgress size={18} color="inherit" /> : <SaveRounded />}
                          onClick={handleSaveForm}
                          disabled={savingForm}
                        >
                          {savingForm ? 'در حال ذخیره…' : 'ذخیره کاربرگ'}
                        </Button>
                      </Stack>
                    </Stack>

                    {selectedForm.unresolved_star && selectedForm.unresolved_star.length > 0 && (
                      <Alert severity="warning">
                        <strong>توجه:</strong> {selectedForm.unresolved_star.length} فیلد الزامی دارای علامت ستاره (*) در این فرم هنوز خالی هستند. صدور نهایی اکسل بدون تکمیل این فیلدها متوقف خواهد شد.
                      </Alert>
                    )}

                    {/* Operational Description & Mandates Registry Card */}
                    <Card
                      variant="outlined"
                      sx={{
                        borderRadius: 2,
                        bgcolor: 'background.default',
                        borderColor: 'primary.light',
                      }}
                    >
                      <CardContent sx={{ pb: 1.5 }}>
                        <Stack spacing={2}>
                          {/* Program Header with Code badge & Policy framework */}
                          <Stack direction="row" justifyContent="space-between" alignItems="center" flexWrap="wrap" gap={1}>
                            <Stack direction="row" spacing={1} alignItems="center">
                              <Chip
                                label={`کد برنامه: ${selectedForm.program_code || selectedForm.program_id}`}
                                color="primary"
                                sx={{ fontWeight: 800, fontSize: '0.85rem' }}
                              />
                              <Typography variant="subtitle1" fontWeight={800} color="primary.main">
                                شرح عملیاتی و موازین پایش برنامه
                              </Typography>
                            </Stack>
                            {selectedForm.policy_framework && (
                              <Chip
                                icon={<PolicyRounded fontSize="small" />}
                                label={selectedForm.policy_framework}
                                variant="outlined"
                                color="secondary"
                                size="small"
                                sx={{ fontWeight: 600 }}
                              />
                            )}
                          </Stack>

                          {/* Operational Description */}
                          {selectedForm.operational_description && (
                            <Box
                              sx={{
                                p: 1.75,
                                bgcolor: 'action.hover',
                                borderRadius: 1.5,
                                borderRight: 4,
                                borderColor: 'primary.main',
                              }}
                            >
                              <Typography variant="body2" sx={{ lineHeight: 1.8, color: 'text.primary', fontWeight: 500 }}>
                                {selectedForm.operational_description}
                              </Typography>
                            </Box>
                          )}

                          {/* Monitoring criteria */}
                          {selectedForm.monitoring_criteria && selectedForm.monitoring_criteria.length > 0 && (
                            <Box>
                              <Typography variant="caption" fontWeight={800} color="text.secondary" gutterBottom display="block">
                                موازین و شاخص‌های نظارتی و پایش برنامه:
                              </Typography>
                              <Grid container spacing={1}>
                                {selectedForm.monitoring_criteria.map((crit, idx) => (
                                  <Grid size={{ xs: 12, md: 6 }} key={idx}>
                                    <Stack direction="row" spacing={1} alignItems="flex-start">
                                      <CheckCircleOutlineRounded fontSize="small" color="success" sx={{ mt: 0.2, flexShrink: 0 }} />
                                      <Typography variant="caption" color="text.secondary" sx={{ lineHeight: 1.6 }}>
                                        {crit}
                                      </Typography>
                                    </Stack>
                                  </Grid>
                                ))}
                              </Grid>
                            </Box>
                          )}

                          <Divider sx={{ my: 0.5 }} />

                          {/* Mandates and Upstream Documents Header */}
                          <Stack direction="row" justifyContent="space-between" alignItems="center" flexWrap="wrap" gap={1}>
                            <Stack direction="row" spacing={1} alignItems="center">
                              <MenuBookRounded color="primary" fontSize="small" />
                              <Typography variant="subtitle2" fontWeight={800}>
                                مستندات ابلاغی و اسناد بالادستی (کد {selectedForm.program_code || selectedForm.program_id})
                              </Typography>
                              <Badge badgeContent={mandates.length} color="primary" sx={{ ml: 1 }} />
                            </Stack>
                            <Stack direction="row" spacing={1}>
                              <Button
                                size="small"
                                variant="outlined"
                                color="primary"
                                startIcon={<VisibilityRounded />}
                                onClick={() => {
                                  void loadAllMandates()
                                  setAllMandatesDialogOpen(true)
                                }}
                              >
                                دید تجمیعی اسناد بالادستی
                              </Button>
                              <Button
                                size="small"
                                variant="contained"
                                color="secondary"
                                startIcon={<AddCircleOutlineRounded />}
                                onClick={() => setNewMandateOpen(true)}
                              >
                                ثبت مستند ابلاغی جدید
                              </Button>
                            </Stack>
                          </Stack>

                          {/* Mandates Table / List */}
                          {loadingMandates ? (
                            <LinearProgress sx={{ my: 1, borderRadius: 1 }} />
                          ) : mandates.length === 0 ? (
                            <Alert severity="info" variant="outlined" sx={{ py: 0.75 }}>
                              هیچ مستند ابلاغی یا بخشنامه‌ای برای این کد برنامه ثبت نشده است. با دکمه «ثبت مستند ابلاغی جدید» می‌توانید مصوبات و بخشنامه‌های مربوطه را ضمیمه کنید.
                            </Alert>
                          ) : (
                            <TableContainer component={Paper} variant="outlined" sx={{ borderRadius: 1.5 }}>
                              <Table size="small">
                                <TableHead sx={{ bgcolor: 'action.hover' }}>
                                  <TableRow>
                                    <TableCell sx={{ fontWeight: 800, width: '15%' }}>نوع سند</TableCell>
                                    <TableCell sx={{ fontWeight: 800, width: '35%' }}>عنوان و شرح مصوبه/ابلاغ</TableCell>
                                    <TableCell sx={{ fontWeight: 800, width: '20%' }}>شماره / تاریخ صدور</TableCell>
                                    <TableCell sx={{ fontWeight: 800, width: '20%' }}>مرجع ابلاغ / پیوست</TableCell>
                                    <TableCell sx={{ fontWeight: 800, width: '10%' }} align="center">عملیات</TableCell>
                                  </TableRow>
                                </TableHead>
                                <TableBody>
                                  {mandates.map(m => (
                                    <TableRow key={m.mandate_id} hover>
                                      <TableCell>
                                        <Chip
                                          size="small"
                                          label={MANDATE_KIND_LABELS[m.kind] || m.kind}
                                          color="primary"
                                          variant="outlined"
                                          sx={{ height: 22, fontSize: '0.7rem' }}
                                        />
                                      </TableCell>
                                      <TableCell>
                                        <Typography variant="body2" fontWeight={700}>
                                          {m.title}
                                        </Typography>
                                        {m.notes && (
                                          <Typography variant="caption" color="text.secondary" display="block">
                                            {m.notes}
                                          </Typography>
                                        )}
                                      </TableCell>
                                      <TableCell>
                                        <Typography variant="caption" display="block" fontWeight={600}>
                                          {m.number ? `شماره: ${m.number}` : 'فاقد شماره'}
                                        </Typography>
                                        {m.issued_on && (
                                          <Typography variant="caption" color="text.secondary" display="block">
                                            تاریخ: {m.issued_on}
                                          </Typography>
                                        )}
                                      </TableCell>
                                      <TableCell>
                                        <Typography variant="caption" color="text.secondary">
                                          {m.document_ref || '---'}
                                        </Typography>
                                      </TableCell>
                                      <TableCell align="center">
                                        <Tooltip title="حذف مستند ابلاغی">
                                          <IconButton
                                            size="small"
                                            color="error"
                                            onClick={() => handleDeleteMandate(m.mandate_id)}
                                          >
                                            <DeleteOutlineRounded fontSize="small" />
                                          </IconButton>
                                        </Tooltip>
                                      </TableCell>
                                    </TableRow>
                                  ))}
                                </TableBody>
                              </Table>
                            </TableContainer>
                          )}
                        </Stack>
                      </CardContent>
                    </Card>

                    <Divider />

                    {/* Question inputs */}
                    <Grid container spacing={2}>
                      {selectedForm.questions.map(q => {
                        const isUnresolved = selectedForm.unresolved_star?.includes(q.key)
                        const val = formAnswers[q.key] ?? ''

                        return (
                          <Grid size={{ xs: 12, sm: q.qtype === 'bool' ? 6 : q.qtype === 'count' ? 4 : 6 }} key={q.key}>
                            <Paper
                              variant="outlined"
                              sx={{
                                p: 1.5,
                                borderRadius: 1.5,
                                borderColor: isUnresolved ? 'warning.main' : 'divider',
                                bgcolor: isUnresolved ? 'warning.50' : 'background.paper',
                              }}
                            >
                              <Stack spacing={1}>
                                <Stack direction="row" justifyContent="space-between" alignItems="center">
                                  <Typography variant="body2" fontWeight={600}>
                                    {q.label} {q.star && <span style={{ color: 'red' }}>*</span>}
                                  </Typography>
                                  <Stack direction="row" spacing={0.5}>
                                    {q.auto_from && (
                                      <Chip size="small" label="اتوماتیک" color="info" variant="outlined" sx={{ height: 18, fontSize: '0.65rem' }} />
                                    )}
                                    {q.human_gate && (
                                      <Chip size="small" label="ورود انسانی" color="secondary" variant="outlined" sx={{ height: 18, fontSize: '0.65rem' }} />
                                    )}
                                  </Stack>
                                </Stack>

                                {q.qtype === 'bool' ? (
                                  <FormControlLabel
                                    control={
                                      <Switch
                                        checked={Boolean(val)}
                                        onChange={e =>
                                          setFormAnswers(prev => ({ ...prev, [q.key]: e.target.checked }))
                                        }
                                      />
                                    }
                                    label={val ? 'بله / انجام شده' : 'خیر / ثبت نشده'}
                                  />
                                ) : q.qtype === 'choice' ? (
                                  <FormControl size="small" fullWidth>
                                    <Select
                                      value={String(val || '')}
                                      onChange={e =>
                                        setFormAnswers(prev => ({ ...prev, [q.key]: e.target.value }))
                                      }
                                    >
                                      {q.choices.map(c => (
                                        <MenuItem key={c} value={c}>
                                          {c}
                                        </MenuItem>
                                      ))}
                                    </Select>
                                  </FormControl>
                                ) : (
                                  <TextField
                                    size="small"
                                    fullWidth
                                    type={q.qtype === 'count' || q.qtype === 'attendees' || q.qtype === 'currency' ? 'number' : 'text'}
                                    value={val}
                                    onChange={e => {
                                      const raw = e.target.value
                                      const parsed =
                                        q.qtype === 'count' || q.qtype === 'attendees' || q.qtype === 'currency'
                                          ? raw === '' ? '' : Number(raw)
                                          : raw
                                      setFormAnswers(prev => ({ ...prev, [q.key]: parsed }))
                                    }}
                                    placeholder={q.star ? 'تکمیل الزامی است' : 'اختیاری'}
                                  />
                                )}
                              </Stack>
                            </Paper>
                          </Grid>
                        )
                      })}
                    </Grid>
                  </Stack>
                </Paper>
              ) : (
                <Alert severity="info">یک کاربرگ را از لیست سمت راست انتخاب کنید.</Alert>
              )}
            </Grid>
          </Grid>
          </Stack>
        )}

        {/* ================= TAB 4: داشبورد دفتر ================= */}
        {currentTab === 4 && <OfficeDashboard />}
        {/* ================= TAB 3: تنظیمات رصد گفتگوها ================= */}
        {currentTab === 3 && (
          <Stack spacing={3}>
            {/* Targets Table */}
            <Paper variant="outlined" sx={{ p: 3, borderRadius: 2 }}>
              <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 2 }}>
                <Box>
                  <Typography variant="h6" fontWeight={800}>
                    کانال‌ها و گروه‌های تحت رصد گزارش‌گیری
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    این گفتگوها برای استخراج خودکار رویدادها، متون خبری، نماز، تکریم و زیارت عاشورا پایش می‌شوند.
                  </Typography>
                </Box>
                <Button
                  variant="contained"
                  color="primary"
                  startIcon={savingSettings ? <CircularProgress size={18} color="inherit" /> : <SaveRounded />}
                  onClick={handleSaveWatchSettings}
                  disabled={savingSettings}
                >
                  {savingSettings ? 'در حال ذخیره…' : 'ذخیره تنظیمات'}
                </Button>
              </Stack>

              <TableContainer>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>عنوان گفتگو</TableCell>
                      <TableCell>کلمات کلیدی فیلتر</TableCell>
                      <TableCell align="center">وضعیت رصد فعال</TableCell>
                      <TableCell align="center">عملیات</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {watchTargets.length === 0 ? (
                      <TableRow>
                        <TableCell colSpan={4} align="center">
                          هیچ گفتگویی در فهرست رصد تعریف نشده است.
                        </TableCell>
                      </TableRow>
                    ) : (
                      watchTargets.map((target, idx) => (
                        <TableRow key={idx}>
                          <TableCell sx={{ fontWeight: 600 }}>{target.label}</TableCell>
                          <TableCell>
                            {target.match_keywords.length > 0
                              ? target.match_keywords.map(k => (
                                  <Chip key={k} size="small" label={k} sx={{ mr: 0.5 }} />
                                ))
                              : <Typography variant="caption" color="text.secondary">همه پیام‌ها</Typography>}
                          </TableCell>
                          <TableCell align="center">
                            <Switch
                              checked={target.enabled}
                              onChange={e => {
                                const next = [...watchTargets]
                                next[idx].enabled = e.target.checked
                                setWatchTargets(next)
                              }}
                            />
                          </TableCell>
                          <TableCell align="center">
                            <Button
                              size="small"
                              color="error"
                              onClick={() => {
                                setWatchTargets(prev => prev.filter((_, i) => i !== idx))
                              }}
                            >
                              حذف
                            </Button>
                          </TableCell>
                        </TableRow>
                      ))
                    )}
                  </TableBody>
                </Table>
              </TableContainer>

              <Divider sx={{ my: 3 }} />

              {/* Add New Target */}
              <Typography variant="subtitle2" fontWeight={800} gutterBottom>
                افزودن گفتگوی جدید به فهرست رصد
              </Typography>
              <Grid container spacing={2} alignItems="center">
                <Grid size={{ xs: 12, sm: 5 }}>
                  <TextField
                    size="small"
                    fullWidth
                    label="نام یا عنوان گفتگو (کانال/گروه)"
                    value={newTargetLabel}
                    onChange={e => setNewTargetLabel(e.target.value)}
                    placeholder="مثال: کانال اطلاع‌رسانی دادگستری استان"
                  />
                </Grid>
                <Grid size={{ xs: 12, sm: 5 }}>
                  <TextField
                    size="small"
                    fullWidth
                    label="کلمات کلیدی فیلتر (با کاما جدا کنید)"
                    value={newTargetKeywords}
                    onChange={e => setNewTargetKeywords(e.target.value)}
                    placeholder="فرهنگی، نماز، مراسم، تکریم، عاشورا"
                  />
                </Grid>
                <Grid size={{ xs: 12, sm: 2 }}>
                  <Button
                    variant="outlined"
                    fullWidth
                    onClick={handleAddWatchTarget}
                    disabled={!newTargetLabel.trim()}
                  >
                    افزودن گفتگو
                  </Button>
                </Grid>
              </Grid>
            </Paper>
          </Stack>
        )}
      </Box>

      {/* Approve Candidate or Manual Event Dialog */}
      <Dialog
        open={Boolean(approveDialog) || manualEventDialogOpen}
        onClose={() => {
          setApproveDialog(null)
          setManualEventDialogOpen(false)
        }}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle sx={{ fontWeight: 800 }}>
          {approveDialog ? 'تأیید و ثبت نهایی رویداد در گزارش (با ابعاد اختصاصی شیت)' : 'ثبت رویداد فرهنگی جدید در گزارش'}
        </DialogTitle>
        <DialogContent dividers>
          <Stack spacing={2} sx={{ mt: 1 }}>
            {approveDialog && (
              <Stack direction="row" justifyContent="space-between" alignItems="center">
                <Alert severity="info" sx={{ flex: 1, mr: 1, py: 0.5 }}>
                  گفتگو: <strong>{approveDialog.dialog_label}</strong> | پیام: {approveDialog.message_ref}
                </Alert>
                <Button
                  variant="outlined"
                  color="secondary"
                  size="small"
                  startIcon={loadingSuggestion ? <CircularProgress size={16} color="inherit" /> : <AutoAwesomeRounded />}
                  onClick={() => void fetchSuggestion(approveDialog)}
                  disabled={loadingSuggestion}
                >
                  {loadingSuggestion ? 'تحلیل عامل…' : 'پیشنهاد هوشمند عامل'}
                </Button>
              </Stack>
            )}

            {suggestionData && (
              <Alert severity="success" icon={<AutoAwesomeRounded />} sx={{ py: 0.5 }}>
                <strong>پیشنهاد عامل هوشمند:</strong> {suggestionData.reasoning}
              </Alert>
            )}

            <Grid container spacing={2}>
              <Grid size={{ xs: 12, sm: 6 }}>
                <FormControl fullWidth size="small">
                  <InputLabel>برنامه فرهنگی متناظر</InputLabel>
                  <Select
                    value={approveProgram}
                    label="برنامه فرهنگی متناظر"
                    onChange={e => setApproveProgram(e.target.value)}
                  >
                    {Object.entries(PROGRAM_NAMES).map(([id, name]) => (
                      <MenuItem key={id} value={id}>
                        {name}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
              </Grid>

              <Grid size={{ xs: 12, sm: 6 }}>
                <JalaliDatePicker
                  size="small"
                  fullWidth
                  label="تاریخ برگزاری رویداد (شمسی)"
                  value={approveOccurredOn}
                  onChange={val => setApproveOccurredOn(val)}
                  outputFormat="iso"
                />
              </Grid>

              <Grid size={{ xs: 12, sm: 6 }}>
                <FormControl fullWidth size="small">
                  <InputLabel>دامنه واحد برگزارکننده</InputLabel>
                  <Select
                    value={approveUnit}
                    label="دامنه واحد برگزارکننده"
                    onChange={e => setApproveUnit(e.target.value)}
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
                <TextField
                  size="small"
                  fullWidth
                  label="نام دقیق واحد یا حوزه قضایی"
                  value={approveUnitName}
                  onChange={e => setApproveUnitName(e.target.value)}
                  placeholder="مثال: حوزه قضایی بابل / ستاد مرکزی ساری"
                />
              </Grid>

              <Grid size={{ xs: 12, sm: 6 }}>
                <TextField
                  size="small"
                  fullWidth
                  type="number"
                  label="تعداد شرکت‌کنندگان (در صورت مشخص بودن)"
                  value={approveAttendees}
                  onChange={e => setApproveAttendees(e.target.value)}
                  placeholder="مثال: ۸۵"
                />
              </Grid>

              <Grid size={{ xs: 12, sm: 6 }}>
                <FormControlLabel
                  control={
                    <Checkbox
                      checked={approveOfficialPresent}
                      onChange={e => setApproveOfficialPresent(e.target.checked)}
                    />
                  }
                  label="حضور رئیس‌کل یا مقام استانی در مراسم"
                />
              </Grid>
            </Grid>

            {/* DYNAMIC SHEET DIMENSIONS ACCORDING TO SELECTED PROGRAM */}
            <SheetSpecificDimensions
              program={approveProgram}
              facts={dimensionFacts}
              onChange={(k, v) => setDimensionFacts(prev => ({ ...prev, [k]: v }))}
            />

            <TextField
              size="small"
              fullWidth
              multiline
              rows={2}
              label="یادداشت و توضیحات تکمیلی"
              value={approveNotes}
              onChange={e => setApproveNotes(e.target.value)}
              placeholder="توضیحات تکمیلی یا مشاهدات..."
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button
            onClick={() => {
              setApproveDialog(null)
              setManualEventDialogOpen(false)
            }}
          >
            انصراف
          </Button>
          <Button
            variant="contained"
            color="success"
            onClick={submitEventForm}
            disabled={submittingEvent}
            startIcon={submittingEvent ? <CircularProgress size={16} color="inherit" /> : undefined}
          >
            {approveDialog ? 'تأیید نهایی و درج در آمار' : 'ثبت رویداد جدید'}
          </Button>
        </DialogActions>



      </Dialog>

      {/* Reject Candidate Dialog */}
      <Dialog open={Boolean(rejectDialog)} onClose={() => setRejectDialog(null)} maxWidth="xs" fullWidth>
        <DialogTitle sx={{ fontWeight: 800 }}>رد نامزد گزارش</DialogTitle>
        <DialogContent dividers>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <Typography variant="body2">
              آیا از رد این پیام به عنوان گزارش رویداد اطمینان دارید؟
            </Typography>
            <TextField
              size="small"
              fullWidth
              multiline
              rows={3}
              label="دلیل رد (اختیاری)"
              value={rejectionReason}
              onChange={e => setRejectionReason(e.target.value)}
              placeholder="مثال: پیام تبلیغاتی، متن فاقد گزارش برگزاری رویداد واقعی است..."
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setRejectDialog(null)}>انصراف</Button>
          <Button variant="contained" color="error" onClick={submitReject}>
            رد گزارش
          </Button>
        </DialogActions>

      </Dialog>

      {/* Dialog for Adding New Mandate */}
      <Dialog
        open={newMandateOpen}
        onClose={() => setNewMandateOpen(false)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle sx={{ fontWeight: 800 }}>
          ثبت مستند ابلاغی جدید
        </DialogTitle>
        <DialogContent dividers>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <Box>
              <Typography variant="caption" color="text.secondary">
                کد و عنوان برنامه متناظر:
              </Typography>
              <Typography variant="subtitle2" fontWeight={800} color="primary.main">
                {selectedForm ? `${selectedForm.program_code || selectedForm.program_id} - ${selectedForm.title}` : '---'}
              </Typography>
            </Box>

            <FormControl fullWidth size="small">
              <InputLabel>نوع سند ابلاغی</InputLabel>
              <Select
                value={mandateFormKind}
                label="نوع سند ابلاغی"
                onChange={e => setMandateFormKind(e.target.value)}
              >
                {Object.entries(MANDATE_KIND_LABELS).map(([k, label]) => (
                  <MenuItem key={k} value={k}>
                    {label}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>

            <TextField
              size="small"
              fullWidth
              required
              label="عنوان مستند ابلاغی / بخشنامه"
              value={mandateFormTitle}
              onChange={e => setMandateFormTitle(e.target.value)}
              placeholder="مثال: دستورالعمل اجرایی برنامه‌های فرهنگی و مذهبی سال ۱۴۰۵"
            />

            <Grid container spacing={2}>
              <Grid size={{ xs: 12, sm: 6 }}>
                <TextField
                  size="small"
                  fullWidth
                  label="شماره ابلاغ / نامه"
                  value={mandateFormNumber}
                  onChange={e => setMandateFormNumber(e.target.value)}
                  placeholder="مثال: ۱۴۰۵/ف/۱۰۲"
                />
              </Grid>
              <Grid size={{ xs: 12, sm: 6 }}>
                <TextField
                  size="small"
                  fullWidth
                  label="تاریخ صدور / ابلاغ"
                  value={mandateFormIssuedOn}
                  onChange={e => setMandateFormIssuedOn(e.target.value)}
                  placeholder="مثال: ۱۴۰۲/۰۳/۱۵"
                />
              </Grid>
            </Grid>

            <TextField
              size="small"
              fullWidth
              label="مرجع صادرکننده یا کد پیوست"
              value={mandateFormDocRef}
              onChange={e => setMandateFormDocRef(e.target.value)}
              placeholder="مثال: معاونت منابع انسانی و امور فرهنگی / ستاد مرکزی"
            />

            <TextField
              size="small"
              fullWidth
              multiline
              rows={3}
              label="مفاد کلیدی و توضیحات"
              value={mandateFormNotes}
              onChange={e => setMandateFormNotes(e.target.value)}
              placeholder="شرح تکالیف ابلاغی، جامعه هدف و الزامات گزارش‌دهی"
            />
          </Stack>
        </DialogContent>
        <DialogActions sx={{ px: 3, py: 2 }}>
          <Button onClick={() => setNewMandateOpen(false)}>
            انصراف
          </Button>
          <Button
            variant="contained"
            color="primary"
            onClick={handleSaveMandate}
            disabled={savingMandate}
            startIcon={savingMandate ? <CircularProgress size={18} color="inherit" /> : <SaveRounded />}
          >
            {savingMandate ? 'در حال ثبت…' : 'ثبت و ذخیره مستند'}
          </Button>
        </DialogActions>

      </Dialog>

      {/* Dialog for Consolidated View of All Mandates */}
      <Dialog
        open={allMandatesDialogOpen}
        onClose={() => setAllMandatesDialogOpen(false)}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle sx={{ fontWeight: 800, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Stack direction="row" spacing={1} alignItems="center">
            <MenuBookRounded color="primary" />
            <Typography variant="h6" fontWeight={800}>
              سامانه تجمیعی اسناد بالادستی و مستندات ابلاغی کل برنامه‌ها
            </Typography>
          </Stack>
          <IconButton size="small" onClick={() => setAllMandatesDialogOpen(false)}>
            <CloseRounded />
          </IconButton>
        </DialogTitle>
        <DialogContent dividers>
          {loadingAllMandates ? (
            <Box sx={{ p: 4, textAlign: 'center' }}>
              <CircularProgress />
              <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                در حال بارگذاری کل مستندات ابلاغی…
              </Typography>
            </Box>
          ) : allMandatesList.length === 0 ? (
            <Alert severity="info">هیچ مستند ابلاغی در سامانه ثبت نشده است.</Alert>
          ) : (
            <Stack spacing={3}>
              {/* Group by program_code */}
              {Array.from(new Set(allMandatesList.map(m => m.program_code || 'other'))).map(pCode => {
                const groupMandates = allMandatesList.filter(m => (m.program_code || 'other') === pCode)
                const matchingForm = forms.find(f => (f.program_code || f.program_id) === pCode)
                const groupTitle = matchingForm?.title || PROGRAM_NAMES[pCode] || `کد برنامه ${pCode}`

                return (
                  <Paper key={pCode} variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
                    <Stack spacing={1.5}>
                      <Stack direction="row" justifyContent="space-between" alignItems="center">
                        <Stack direction="row" spacing={1} alignItems="center">
                          <Chip label={pCode} color="primary" size="small" sx={{ fontWeight: 800 }} />
                          <Typography variant="subtitle2" fontWeight={800}>
                            {groupTitle}
                          </Typography>
                        </Stack>
                        <Chip label={`${groupMandates.length} مستند`} size="small" variant="outlined" />
                      </Stack>
                      <TableContainer component={Paper} variant="outlined" sx={{ borderRadius: 1 }}>
                        <Table size="small">
                          <TableHead sx={{ bgcolor: 'action.hover' }}>
                            <TableRow>
                              <TableCell sx={{ fontWeight: 700, width: '15%' }}>نوع</TableCell>
                              <TableCell sx={{ fontWeight: 700, width: '35%' }}>عنوان و شرح</TableCell>
                              <TableCell sx={{ fontWeight: 700, width: '20%' }}>شماره / تاریخ</TableCell>
                              <TableCell sx={{ fontWeight: 700, width: '20%' }}>مرجع ابلاغ</TableCell>
                              <TableCell sx={{ fontWeight: 700, width: '10%' }} align="center">حذف</TableCell>
                            </TableRow>
                          </TableHead>
                          <TableBody>
                            {groupMandates.map(m => (
                              <TableRow key={m.mandate_id} hover>
                                <TableCell>
                                  <Chip
                                    size="small"
                                    label={MANDATE_KIND_LABELS[m.kind] || m.kind}
                                    color="primary"
                                    variant="outlined"
                                    sx={{ height: 20, fontSize: '0.65rem' }}
                                  />
                                </TableCell>
                                <TableCell>
                                  <Typography variant="body2" fontWeight={600}>
                                    {m.title}
                                  </Typography>
                                  {m.notes && (
                                    <Typography variant="caption" color="text.secondary" display="block">
                                      {m.notes}
                                    </Typography>
                                  )}
                                </TableCell>
                                <TableCell>
                                  <Typography variant="caption" display="block">
                                    {m.number || 'فاقد شماره'}
                                  </Typography>
                                  {m.issued_on && (
                                    <Typography variant="caption" color="text.secondary" display="block">
                                      {m.issued_on}
                                    </Typography>
                                  )}
                                </TableCell>
                                <TableCell>
                                  <Typography variant="caption" color="text.secondary">
                                    {m.document_ref || '---'}
                                  </Typography>
                                </TableCell>
                                <TableCell align="center">
                                  <Tooltip title="حذف مستند">
                                    <IconButton
                                      size="small"
                                      color="error"
                                      onClick={() => handleDeleteMandate(m.mandate_id)}
                                    >
                                      <DeleteOutlineRounded fontSize="small" />
                                    </IconButton>
                                  </Tooltip>
                                </TableCell>
                              </TableRow>
                            ))}
                          </TableBody>
                        </Table>
                      </TableContainer>
                    </Stack>
                  </Paper>
                )
              })}
            </Stack>
          )}
        </DialogContent>
        <DialogActions sx={{ px: 3, py: 1.5 }}>
          <Button onClick={() => setAllMandatesDialogOpen(false)} variant="contained">
            بستن
          </Button>
        </DialogActions>

      </Dialog>

      {/* Revision Request Dialog */}
      {revisionDialogEvent && (
        <Dialog open onClose={() => setRevisionDialogEvent(null)} maxWidth="sm" fullWidth>
          <DialogTitle sx={{ fontWeight: 800 }}>
            ارجاع نقص و اصلاح پرونده ({revisionDialogEvent.event_id})
          </DialogTitle>
          <DialogContent dividers>
            <Stack spacing={2}>
              <Typography variant="body2" color="text.secondary">
                دستور اصلاح یا شرح ایراد را برای مسئول ثبت رویداد وارد کنید. یک وظیفه در کارتابل کارمند ثبت خواهد شد.
              </Typography>
              {revisionDialogEvent.defects && revisionDialogEvent.defects.length > 0 && (
                <Box sx={{ p: 1.5, bgcolor: 'action.hover', borderRadius: 1.5 }}>
                  <Typography variant="caption" fontWeight={700} sx={{ mb: 1, display: 'block' }}>
                    نقایص کشف‌شده توسط موتور ارزیابی خودکار:
                  </Typography>
                  <Stack spacing={0.5}>
                    {revisionDialogEvent.defects.map(d => (
                      <Chip
                        key={d.defect_code}
                        size="small"
                        color={d.severity === 'blocker' ? 'error' : 'warning'}
                        label={`${d.title}: ${d.description}`}
                        onClick={() => setRevisionReason(prev => (prev ? `${prev}\n- ${d.description}` : `- ${d.description}`))}
                        sx={{ cursor: 'pointer', height: 'auto', '& .MuiChip-label': { whiteSpace: 'normal', py: 0.5 } }}
                      />
                    ))}
                  </Stack>
                </Box>
              )}
              <TextField
                label="دستور اصلاح / شرح نقص"
                value={revisionReason}
                onChange={e => setRevisionReason(e.target.value)}
                multiline
                minRows={3}
                fullWidth
                placeholder="مثال: تعداد مخاطبان ثبت نشده است؛ لطفاً پیوست نامهٔ رسمی پیوست شود."
              />
            </Stack>
          </DialogContent>
          <DialogActions sx={{ px: 2.5, py: 1.5 }}>
            <Button onClick={() => setRevisionDialogEvent(null)}>انصراف</Button>
            <Button
              variant="contained"
              color="warning"
              disabled={workflowActionLoading || !revisionReason.trim()}
              onClick={() => void handleRequestRevision(revisionDialogEvent.event_id, revisionReason)}
            >
              ثبت و ارجاع وظیفه به کارمند
            </Button>
          </DialogActions>
  
      </Dialog>
      )}

      {/* Defect Audit Detail Dialog */}
      {defectDialogEvent && (
        <Dialog open onClose={() => setDefectDialogEvent(null)} maxWidth="md" fullWidth>
          <DialogTitle sx={{ fontWeight: 800 }}>
            ارزیابی کیفی پروندهٔ رویداد ({defectDialogEvent.event_id})
          </DialogTitle>
          <DialogContent dividers>
            <Stack spacing={2}>
              {defectDialogEvent.defects && defectDialogEvent.defects.length > 0 ? (
                defectDialogEvent.defects.map((d, idx) => (
                  <Paper key={idx} variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
                    <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1 }}>
                      <Chip
                        size="small"
                        color={d.severity === 'blocker' ? 'error' : d.severity === 'warning' ? 'warning' : 'info'}
                        label={d.severity === 'blocker' ? 'مانع تایید' : d.severity === 'warning' ? 'هشدار کیفی' : 'راهنما'}
                      />
                      <Typography variant="subtitle2" fontWeight={800}>{d.title}</Typography>
                    </Stack>
                    <Typography variant="body2" color="text.secondary">
                      {d.description}
                    </Typography>
                  </Paper>
                ))
              ) : (
                <Alert severity="success">هیچ نقصی در این پرونده شناسایی نشد.</Alert>
              )}
            </Stack>
          </DialogContent>
          <DialogActions sx={{ px: 2.5, py: 1.5 }}>
            <Button onClick={() => setDefectDialogEvent(null)}>بستن</Button>
          </DialogActions>
  
      </Dialog>
      )}
    
      {/* Dialog for viewing underlying events contributing to this workbook */}
      <Dialog
        open={formEventsDialogOpen}
        onClose={() => setFormEventsDialogOpen(false)}
        maxWidth="lg"
        fullWidth
      >
        <DialogTitle sx={{ pb: 1 }}>
          <Stack direction="row" justifyContent="space-between" alignItems="center">
            <Stack direction="row" spacing={1.5} alignItems="center">
              <FormatListBulletedRounded color="primary" />
              <Box>
                <Typography variant="subtitle1" fontWeight={800}>
                  ریز گزارش‌ها و رویدادهای متناظر: {selectedForm?.title}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  فهرست رویدادهای ثبت‌شده در این برنامه که در محاسبهٔ مقادیر تجمیعی این کاربرگ نقش دارند.
                  {(formDateFrom || formDateTo) && (
                    <span style={{ marginRight: 8, color: '#0288d1', fontWeight: 700 }}>
                      (محدود به بازهٔ تاریخی: {formDateFrom ? `از ${formDateFrom}` : ''} {formDateTo ? `تا ${formDateTo}` : ''})
                    </span>
                  )}
                </Typography>
              </Box>
            </Stack>
            <IconButton onClick={() => setFormEventsDialogOpen(false)} size="small">
              <CloseRounded />
            </IconButton>
          </Stack>
        </DialogTitle>
        <DialogContent dividers sx={{ p: 2 }}>
          {loadingFormEvents ? (
            <Box sx={{ py: 6, textAlign: 'center' }}>
              <CircularProgress size={36} />
              <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
                در حال بارگذاری سوابق رویدادهای متناظر…
              </Typography>
            </Box>
          ) : formEventsList.length === 0 ? (
            <Box sx={{ py: 4, textAlign: 'center' }}>
              <Alert severity="info" variant="outlined" sx={{ justifyContent: 'center', mb: 2 }}>
                هیچ رویدادی برای سرفصل «{selectedForm?.title}» در این بازهٔ زمانی ثبت نشده است.
              </Alert>
              <Button
                variant="contained"
                color="primary"
                startIcon={<AddCircleOutlineRounded />}
                onClick={() => {
                  setFormEventsDialogOpen(false)
                  openManualEvent()
                }}
              >
                ثبت رویداد جدید (دستی)
              </Button>
            </Box>
          ) : (
            <TableContainer component={Paper} variant="outlined" sx={{ maxHeight: 480, borderRadius: 2 }}>
              <Table size="small" stickyHeader>
                <TableHead sx={{ bgcolor: 'action.hover' }}>
                  <TableRow>
                    <TableCell sx={{ fontWeight: 800, width: 48 }}>#</TableCell>
                    <TableCell sx={{ fontWeight: 800 }}>عنوان و مناسبت رویداد</TableCell>
                    <TableCell sx={{ fontWeight: 800 }}>واحد سازمانی</TableCell>
                    <TableCell sx={{ fontWeight: 800 }}>تاریخ برگزاری</TableCell>
                    <TableCell sx={{ fontWeight: 800, textAlign: 'center' }}>شرکت‌کنندگان</TableCell>
                    <TableCell sx={{ fontWeight: 800, textAlign: 'center' }}>وضعیت بازبینی</TableCell>
                    <TableCell sx={{ fontWeight: 800, textAlign: 'center' }}>عملیات</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {formEventsList.map((ev, idx) => {
                    const attendeesFact = ev.facts?.find(f => f.metric === 'attendees' || f.metric === 'participants_count' || f.metric === 'quran_attendees')
                    const attendeeNum = attendeesFact ? Number(attendeesFact.value) || 0 : 0
                    return (
                      <TableRow
                        key={ev.event_id}
                        hover
                        sx={{
                          cursor: 'pointer',
                          '&:hover': { bgcolor: 'action.hover' },
                        }}
                        onClick={() => setDetailModalEventId(ev.event_id)}
                      >
                        <TableCell sx={{ fontWeight: 600 }}>{idx + 1}</TableCell>
                        <TableCell>
                          <Typography variant="body2" fontWeight={700}>
                            {ev.occasion || 'بدون عنوان'}
                          </Typography>
                          {ev.notes && (
                            <Typography variant="caption" color="text.secondary" noWrap sx={{ maxWidth: 320, display: 'block' }}>
                              {ev.notes}
                            </Typography>
                          )}
                        </TableCell>
                        <TableCell>
                          <Chip
                            size="small"
                            variant="outlined"
                            label={ev.unit_name || ev.unit || 'نامشخص'}
                            sx={{ height: 22, fontSize: '0.75rem' }}
                          />
                        </TableCell>
                        <TableCell>
                          <Typography variant="caption" fontWeight={600}>
                            {ev.occurred_on ? jalaliDayLabel(ev.occurred_on) : '—'}
                          </Typography>
                        </TableCell>
                        <TableCell align="center">
                          <Typography variant="body2" fontWeight={700} color={attendeeNum > 0 ? 'primary.main' : 'text.secondary'}>
                            {attendeeNum > 0 ? `${attendeeNum} نفر` : '—'}
                          </Typography>
                        </TableCell>
                        <TableCell align="center">
                          <Chip
                            size="small"
                            color={(ev.review_status as any) === 'approved' ? 'success' : ((ev.review_status as any) === 'rejected' || (ev.review_status as any) === 'conflict') ? 'error' : 'warning'}
                            label={(ev.review_status as any) === 'approved' ? 'تأیید شده' : ((ev.review_status as any) === 'rejected' || (ev.review_status as any) === 'conflict') ? 'رد / تعارض' : 'نیازمند بررسی'}
                            sx={{ height: 22, fontSize: '0.7rem', fontWeight: 600 }}
                          />
                        </TableCell>
                        <TableCell align="center" onClick={e => e.stopPropagation()}>
                          <Button
                            size="small"
                            variant="contained"
                            color="primary"
                            startIcon={<EditRounded />}
                            onClick={() => setDetailModalEventId(ev.event_id)}
                            sx={{ fontSize: '0.75rem', px: 1.5, py: 0.4 }}
                          >
                            مشاهده و اصلاح
                          </Button>
                        </TableCell>
                      </TableRow>
                    )
                  })}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </DialogContent>
        <DialogActions sx={{ px: 3, py: 1.5, justifyContent: 'space-between' }}>
          <Typography variant="caption" color="text.secondary">
            مجموعاً {formEventsList.length} رویداد تطبیق‌یافته در این کاربرگ
          </Typography>
          <Button onClick={() => setFormEventsDialogOpen(false)} variant="outlined">
            بستن
          </Button>
        </DialogActions>
      </Dialog>

      {/* Report Event Detail & Defect Editing Modal */}
      <ReportEventDetailModal
        open={Boolean(detailModalEventId)}
        eventId={detailModalEventId}
        onClose={() => setDetailModalEventId(null)}
        onSaved={() => {
          void loadEventsCartable()
          void loadEventsAndExports()
          void loadForms(formDateFrom, formDateTo)
          if (formEventsDialogOpen) {
            void loadEventsForActiveForm()
          }
        }}
      />

      {/* Judicial Units & Master Baseline Management Modal */}
      {unitsModalOpen && (
        <JudicialUnitsManagementModal
          open={unitsModalOpen}
          onClose={() => setUnitsModalOpen(false)}
          initialTab={unitsModalTab}
          onDataChanged={() => {
            void loadEventsCartable()
          }}
        />
      )}
    </Paper>

  )
}
