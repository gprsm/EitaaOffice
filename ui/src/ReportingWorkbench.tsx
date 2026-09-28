import { useEffect, useMemo, useState } from 'react'
import {
  Alert,
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
import AutoAwesomeRounded from '@mui/icons-material/AutoAwesomeRounded'
import CheckCircleOutlineRounded from '@mui/icons-material/CheckCircleOutlineRounded'
import CloseRounded from '@mui/icons-material/CloseRounded'
import DescriptionOutlined from '@mui/icons-material/DescriptionOutlined'
import EventNoteRounded from '@mui/icons-material/EventNoteRounded'
import FileDownloadRounded from '@mui/icons-material/FileDownloadRounded'
import LayersRounded from '@mui/icons-material/LayersRounded'
import RefreshRounded from '@mui/icons-material/RefreshRounded'
import SaveRounded from '@mui/icons-material/SaveRounded'
import SettingsRounded from '@mui/icons-material/SettingsRounded'
import SummarizeRounded from '@mui/icons-material/SummarizeRounded'
import WarningAmberRounded from '@mui/icons-material/WarningAmberRounded'
import { api, ApiError } from './lib/api'
import OfficeDashboard from './OfficeDashboard'
import { toast } from './MaterialToast'
import { jalaliDayLabel } from './utils/jalali'

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
  title: string
  questions: FormQuestion[]
  unresolved_star: string[]
  unresolved_human_gate: string[]
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
  created_by: string
  facts: EventFact[]
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

const PROGRAM_NAMES: Record<string, string> = {
  trip: 'اردو (۸۰۴۰۱)',
  contest: 'مسابقات (۸۰۴۰۲)',
  ceremonies: 'مراسم مذهبی، ملی و انقلابی (۸۰۴۰۳)',
  prayer: 'ترویج فرهنگ اقامه نماز (۸۰۵۰۱)',
  honor: 'تکریم و تجلیل (۸۰۴۰۶)',
  customer_care: 'تشویق ارباب رجوع (۸۰۶۰۱)',
  charter: 'منشور اخلاقی (۸۰۲۰۲)',
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

export function ReportingWorkbench({ onClose }: { onClose: () => void }) {
  const [currentTab, setCurrentTab] = useState<number>(0)
  const [loading, setLoading] = useState<boolean>(false)

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
  const [savingForm, setSavingForm] = useState<boolean>(false)

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

  // Fetch forms
  const loadForms = async () => {
    try {
      const res = await api<{ ok: boolean; forms: FormSummary[] }>('GET', '/api/v2/reporting/forms')
      setForms(res.forms || [])
      if (res.forms && res.forms[selectedFormIndex]) {
        const initialAnswers: Record<string, any> = {}
        for (const q of res.forms[selectedFormIndex].questions) {
          if (q.current_value !== null && q.current_value !== undefined) {
            initialAnswers[q.key] = q.current_value
          }
        }
        setFormAnswers(initialAnswers)
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'خطا در دریافت کاربرگ‌ها')
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
    else if (currentTab === 1) void loadForms()
    else if (currentTab === 2) {
      void loadForms()
      void loadEventsAndExports()
    } else if (currentTab === 3) void loadWatchConfig()
  }, [currentTab, candidateFilter])

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
      const res = await api<{ ok: boolean; result: any }>('POST', '/api/v2/reporting/scan', {
        limit_per_dialog: 50,
      })
      toast.success(
        `پویش انجام شد: ${res.result?.scanned || 0} پیام بررسی شد، ${res.result?.event_reports || 0} رویداد شناسایی شد.`,
      )
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
                else if (currentTab === 1) void loadForms()
                else if (currentTab === 2) {
                  void loadForms()
                  void loadEventsAndExports()
                } else if (currentTab === 3) void loadWatchConfig()
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
                <FileDownloadRounded fontSize="small" />
                <span>پیش‌نمایش تجمیع و صدور اکسل</span>
              </Stack>
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
              <Alert severity="info" sx={{ mt: 2 }}>
                موردی در این دسته یافت نشد. می‌توانید با کلیک بر روی «پویش هوشمند گفتگوها»، پیام‌های جدید را واکشی کنید.
              </Alert>
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
        {currentTab === 1 && (
          <Grid container spacing={3}>
            {/* Sidebar list of 7 forms */}
            <Grid size={{ xs: 12, md: 3.5 }}>
              <Paper variant="outlined" sx={{ borderRadius: 2, overflow: 'hidden' }}>
                <Box sx={{ p: 2, bgcolor: 'action.hover', borderBottom: 1, borderColor: 'divider' }}>
                  <Typography variant="subtitle2" fontWeight={800}>
                    برنامه‌های هفت‌گانه فرهنگی ۱۴۰۵
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
                          شناسه سیستمی: {selectedForm.program_id} | تعداد کل فیلدها: {selectedForm.questions.length}
                        </Typography>
                      </Box>
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

                    {selectedForm.unresolved_star && selectedForm.unresolved_star.length > 0 && (
                      <Alert severity="warning">
                        <strong>توجه:</strong> {selectedForm.unresolved_star.length} فیلد الزامی دارای علامت ستاره (*) در این فرم هنوز خالی هستند. صدور نهایی اکسل بدون تکمیل این فیلدها متوقف خواهد شد.
                      </Alert>
                    )}

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
        )}

        {/* ================= TAB 2: پیش‌نمایش تجمیع و صدور اکسل ================= */}
        {currentTab === 2 && (
          <Stack spacing={3}>
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

              <Box sx={{ mt: 2.5, display: 'flex', justifyContent: 'flex-end' }}>
                <Button
                  variant="contained"
                  color="primary"
                  size="large"
                  startIcon={exporting ? <CircularProgress size={20} color="inherit" /> : <FileDownloadRounded />}
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

            {/* Approved Events Table */}
            <Paper variant="outlined" sx={{ p: 2.5, borderRadius: 2 }}>
              <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 2 }}>
                <Typography variant="subtitle1" fontWeight={800}>
                  رویدادهای تأییدشدهٔ گزارش ({events.length} رویداد)
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  رویدادهایی که از طریق صف بازبینی تأیید شده‌اند و در تجمیع وارد می‌شوند.
                </Typography>
              </Stack>
              <TableContainer sx={{ maxHeight: 320 }}>
                <Table stickyHeader size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>شناسه رویداد</TableCell>
                      <TableCell>برنامه‌ها</TableCell>
                      <TableCell>تاریخ رویداد</TableCell>
                      <TableCell>واحد برگزارکننده</TableCell>
                      <TableCell>مناسبت</TableCell>
                      <TableCell>حضور مقام ارشد</TableCell>
                      <TableCell>نوع رویداد</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {events.length === 0 ? (
                      <TableRow>
                        <TableCell colSpan={7} align="center">
                          هیچ رویدادی تاکنون تأیید نشده است.
                        </TableCell>
                      </TableRow>
                    ) : (
                      events.map(ev => (
                        <TableRow key={ev.event_id}>
                          <TableCell sx={{ fontFamily: 'monospace' }}>{ev.event_id}</TableCell>
                          <TableCell>
                            {ev.program_kinds.map(p => (
                              <Chip key={p} size="small" label={PROGRAM_NAMES[p] || p} sx={{ mr: 0.5 }} />
                            ))}
                          </TableCell>
                          <TableCell>{ev.occurred_on}</TableCell>
                          <TableCell>{ev.unit_name || ev.unit}</TableCell>
                          <TableCell>{ev.occasion || '—'}</TableCell>
                          <TableCell>{ev.official_present ? 'بله' : 'خیر / نامشخص'}</TableCell>
                          <TableCell>
                            {ev.is_ashura_pilgrimage ? (
                              <Chip size="small" label="زیارت عاشورا (مستقل)" color="secondary" />
                            ) : (
                              'عادی'
                            )}
                          </TableCell>
                        </TableRow>
                      ))
                    )}
                  </TableBody>
                </Table>
              </TableContainer>
            </Paper>

            {/* History of Exports */}
            <Paper variant="outlined" sx={{ p: 2.5, borderRadius: 2 }}>
              <Typography variant="subtitle1" fontWeight={800} sx={{ mb: 2 }}>
                تاریخچه و گزارش بازرسی صدورهای گذشته
              </Typography>
              <TableContainer sx={{ maxHeight: 260 }}>
                <Table stickyHeader size="small">
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
                <TextField
                  size="small"
                  fullWidth
                  label="تاریخ برگزاری رویداد (YYYY-MM-DD)"
                  value={approveOccurredOn}
                  onChange={e => setApproveOccurredOn(e.target.value)}
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
    </Paper>
  )
}
