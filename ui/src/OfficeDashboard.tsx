// Office dashboard — the cultural affairs reporting management system panel (F-088/F-090).
// Shows:
// 1. 12 section cards with realization ratios, targets, and gaps
// 2. Human approval queue with Persian chip labels and rich imam candidate review
// 3. Interactive WordPress post linking and unlinking with section assignment
// 4. Registry viewer for units (31 judicial domains) and personnel (employees & family)
// 5. Provincial visit dossier for prayer promotion
import { useCallback, useEffect, useState } from 'react'
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  FormControl,
  Grid,
  InputBase,
  InputLabel,
  LinearProgress,
  MenuItem,
  Paper,
  Select,
  Stack,
  Tab,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Tabs,
  TextField,
  Typography,
} from '@mui/material'
import CheckCircleOutlineRounded from '@mui/icons-material/CheckCircleOutlineRounded'
import CloseRounded from '@mui/icons-material/CloseRounded'
import RefreshRounded from '@mui/icons-material/RefreshRounded'
import LinkRounded from '@mui/icons-material/LinkRounded'
import LinkOffRounded from '@mui/icons-material/LinkOffRounded'
import PersonRounded from '@mui/icons-material/PersonRounded'
import { api } from './lib/api'
import { toast } from './MaterialToast'

// ---- types mirroring the v3 payloads --------------------------------------

interface SectionRealizationItem {
  plan_id: string
  title: string
  done: number
  target: number
  ratio: number
  needs_confirmation: boolean
  gap: number
}

interface OfficeSection {
  section_id: string
  title: string
  source: string
  workbook_code: string
  visit_label: string
  events_count: number
  facts_count: number
  realization: SectionRealizationItem[]
  open_gaps: number
}

interface NormalizationCandidate {
  candidate_id: string
  metric: string
  unit_name: string
  raw_text: string
  proposed_value: string
  confidence: number
  source_column: string
}

interface WpPendingLink {
  link_id: string
  post_slug: string
  title: string
  section: string
  match_status: string
  confidence: number
  event_id?: string
}

interface RegistryPerson {
  person_id: string
  kind: string
  full_name: string
  personnel_no: string
  phone: string
  relation: string
  related_personnel_no: string
  notes: string
}

interface RegistryUnit {
  unit_id: string
  name: string
  kind: string
  notes: string
}

interface DossierCell {
  label: string
  value: unknown
}

interface Dossier {
  visit_worksheet_row: {
    cells: DossierCell[]
    gaps: string[]
  }
  unit_count: number
}

const METRIC_LABELS: Record<string, string> = {
  chief_participation: 'حضور رئیس حوزه در نماز',
  imam_public_satisfaction: 'رضایت عمومی از امام جماعت',
  azan_broadcast: 'پخش اذان در اوقات شرعی',
  imam_record: 'ثبت و ساماندهی امام جماعت',
  jammat_frequency: 'تواتر برگزاری نماز جماعت',
  imam_source: 'منبع تأمین امام جماعت',
  council_sessions_band: 'جلسات شورای اقامه نماز',
}

const APPROVAL_CODES: Record<string, string[]> = {
  chief_participation: ['always', 'occasionally', 'rarely'],
  imam_public_satisfaction: ['high', 'medium', 'low'],
  azan_broadcast: ['regular', 'sometimes', 'none'],
}

const CODE_LABELS: Record<string, string> = {
  always: 'همیشه / مستمر',
  occasionally: 'گاهی / موردی',
  rarely: 'به‌ندرت',
  high: 'زیاد / مطلوب',
  medium: 'متوسط',
  low: 'کم / نیازمند پیگیری',
  regular: 'به‌صورت مرتب',
  sometimes: 'گاهی',
  none: 'خیر / ندارد',
  staff_cleric: 'روحانی شاغل دادگستری',
  invited_external: 'دعوت‌شده / غیرشاغل',
}

const SECTION_SOURCE_LABEL: Record<string, string> = {
  workbook_1405: 'کاربرگ ۱۴۰۵',
  visit_worksheet: 'کاربرگ سفر استانی',
}

const SECTION_OPTIONS: { id: string; title: string }[] = [
  { id: 'prayer', title: 'ترویج و توسعه فرهنگ اقامه نماز' },
  { id: 'trip', title: 'برگزاری اردوهای فرهنگی زیارتی' },
  { id: 'contest', title: 'برگزاری مسابقات استانی' },
  { id: 'ceremonies', title: 'برگزاری مراسم مذهبی و ملی' },
  { id: 'honor', title: 'تکریم و تجلیل از همکاران' },
  { id: 'customer_care', title: 'تشویق تکریم ارباب رجوع' },
  { id: 'charter', title: 'اجرای منشور اخلاقی' },
  { id: 'training_courses', title: 'دوره‌های آموزشی و تبیینی' },
  { id: 'content_production', title: 'تولید محتوا و کلیپ فرهنگی' },
  { id: 'counseling', title: 'خدمات مشاوره‌ای و مددکاری' },
  { id: 'education_services', title: 'خدمات آموزشی فرزندان' },
  { id: 'external_collaboration', title: 'همکاری‌های برون‌سازمانی' },
]

export default function OfficeDashboard() {
  const [loading, setLoading] = useState(false)
  const [period, setPeriod] = useState('1405')
  const [sections, setSections] = useState<OfficeSection[]>([])
  const [candidates, setCandidates] = useState<NormalizationCandidate[]>([])
  const [wpPending, setWpPending] = useState<WpPendingLink[]>([])
  const [dossier, setDossier] = useState<Dossier | null>(null)
  const [queueView, setQueueView] = useState(0)
  const [draftValues, setDraftValues] = useState<Record<string, string>>({})
  const [draftPostSection, setDraftPostSection] = useState<Record<string, string>>({})
  const [submittingLinkId, setSubmittingLinkId] = useState<string | null>(null)

  // Imam review dialog state
  const [imamModalCandidate, setImamModalCandidate] = useState<NormalizationCandidate | null>(null)
  const [imamForm, setImamForm] = useState({
    full_name: '',
    position: '',
    source_kind: 'staff_cleric',
  })

  // Registry state (persons & units)
  const [persons, setPersons] = useState<RegistryPerson[]>([])
  const [units, setUnits] = useState<RegistryUnit[]>([])
  const [personFilter, setPersonFilter] = useState<'all' | 'employee' | 'family'>('all')
  const [personSearch, setPersonSearch] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const sectionsRes = await api<{ ok: boolean; sections: OfficeSection[] }>(
        'GET',
        `/api/v3/office/sections?period=${encodeURIComponent(period)}`,
      )
      const queueRes = await api<{
        ok: boolean
        normalization: NormalizationCandidate[]
        wp_links: WpPendingLink[]
      }>('GET', '/api/v3/office/queue')
      const dossierRes = await api<{ ok: boolean; dossier: Dossier }>(
        'GET',
        `/api/v3/office/dossier?period=${encodeURIComponent(period)}`,
      )
      setSections(sectionsRes.sections || [])
      setCandidates(queueRes.normalization || [])
      setWpPending(queueRes.wp_links || [])
      setDossier(dossierRes.dossier || null)

      // Initialize draft sections for WP posts
      const drafts: Record<string, string> = {}
      for (const link of queueRes.wp_links || []) {
        drafts[link.link_id] = link.section || 'prayer'
      }
      setDraftPostSection(drafts)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'خطا در دریافت داده‌های دفتر')
    } finally {
      setLoading(false)
    }
  }, [period])

  const loadRegistry = useCallback(async () => {
    try {
      const [personsRes, unitsRes] = await Promise.all([
        api<{ ok: boolean; items: RegistryPerson[] }>('GET', '/api/v3/office/registry?kind=persons'),
        api<{ ok: boolean; items: RegistryUnit[] }>('GET', '/api/v3/office/registry?kind=units'),
      ])
      setPersons(personsRes.items || [])
      setUnits(unitsRes.items || [])
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'خطا در بارگذاری بانک اطلاعات')
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  useEffect(() => {
    if (queueView === 2) {
      void loadRegistry()
    }
  }, [queueView, loadRegistry])

  const reviewCandidate = async (
    candidateId: string,
    action: 'approve' | 'reject',
    extra?: { full_name?: string; position?: string; source_kind?: string },
  ) => {
    const coded = draftValues[candidateId] ?? ''
    try {
      await api('POST', `/api/v3/office/queue/${candidateId}/review`, {
        action,
        coded_value: coded || (extra?.full_name ? 'ثبت شده' : 'تأیید'),
        reviewed_by: 'office-operator',
        ...(extra || {}),
      })
      toast.success(action === 'approve' ? 'کدگذاری تأیید و ثبت شد' : 'کاندید رد شد')
      setDraftValues((prev) => {
        const next = { ...prev }
        delete next[candidateId]
        return next
      })
      setImamModalCandidate(null)
      void load()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'خطا در ثبت تصمیم')
    }
  }

  const handleLinkPost = async (linkId: string) => {
    const section = draftPostSection[linkId] || 'prayer'
    setSubmittingLinkId(linkId)
    try {
      await api('POST', `/api/v3/office/wp-links/${linkId}/link`, { section })
      toast.success('پست با موفقیت به بخش مربوطه پیوند شد')
      void load()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'خطا در پیوند پست')
    } finally {
      setSubmittingLinkId(null)
    }
  }

  const handleUnlinkPost = async (linkId: string) => {
    setSubmittingLinkId(linkId)
    try {
      await api('POST', `/api/v3/office/wp-links/${linkId}/unlink`, {})
      toast.success('پیوند پست با موفقیت ابطال شد')
      void load()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'خطا در ابطال پیوند پست')
    } finally {
      setSubmittingLinkId(null)
    }
  }

  const filteredPersons = persons.filter((p) => {
    if (personFilter !== 'all' && p.kind !== personFilter) return false
    if (!personSearch.trim()) return true
    const q = personSearch.trim().toLowerCase()
    return (
      p.full_name.toLowerCase().includes(q) ||
      p.personnel_no.includes(q) ||
      p.notes.toLowerCase().includes(q) ||
      p.relation.toLowerCase().includes(q)
    )
  })

  return (
    <Stack spacing={2.5}>
      {/* header bar */}
      <Paper variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
        <Stack direction="row" spacing={2} alignItems="center" justifyContent="space-between">
          <Stack direction="row" spacing={1.5} alignItems="center">
            <Button
              variant="contained"
              startIcon={<RefreshRounded />}
              onClick={() => void load()}
              disabled={loading}
            >
              بازخوانی
            </Button>
            {['1405', '1405-P1', '1405-P2', '1405-P3'].map((p) => (
              <Chip
                key={p}
                label={p}
                color={period === p ? 'primary' : 'default'}
                onClick={() => setPeriod(p)}
              />
            ))}
          </Stack>
          {loading && <CircularProgress size={22} />}
        </Stack>
      </Paper>

      {/* section cards */}
      <Grid container spacing={2}>
        {sections.map((section) => (
          <Grid size={{ xs: 12, md: 6, lg: 4 }} key={section.section_id}>
            <Card variant="outlined" sx={{ borderRadius: 2, height: '100%' }}>
              <CardContent>
                <Stack direction="row" spacing={1} alignItems="center" justifyContent="space-between">
                  <Typography variant="subtitle1" fontWeight={700}>
                    {section.title}
                  </Typography>
                  <Chip
                    size="small"
                    label={SECTION_SOURCE_LABEL[section.source] ?? section.source}
                    variant="outlined"
                  />
                </Stack>
                <Stack direction="row" spacing={1} sx={{ mt: 1 }}>
                  {section.workbook_code && (
                    <Chip size="small" label={`کد ${section.workbook_code}`} />
                  )}
                  <Chip size="small" label={`${section.events_count} رویداد`} />
                  <Chip size="small" label={`${section.facts_count} فکت`} />
                  {section.open_gaps > 0 && (
                    <Chip size="small" color="warning" label={`${section.open_gaps} شکاف`} />
                  )}
                </Stack>
                {section.realization.slice(0, 4).map((item) => (
                  <Box key={item.plan_id} sx={{ mt: 1.5 }}>
                    <Stack direction="row" justifyContent="space-between">
                      <Typography variant="caption" noWrap sx={{ maxWidth: '70%' }}>
                        {item.title}
                      </Typography>
                      <Typography variant="caption">
                        {item.done} / {item.target}
                      </Typography>
                    </Stack>
                    <LinearProgress
                      variant="determinate"
                      value={Math.min(100, Math.round(item.ratio * 100))}
                      sx={{ height: 6, borderRadius: 3 }}
                    />
                  </Box>
                ))}
              </CardContent>
            </Card>
          </Grid>
        ))}
      </Grid>

      {/* approval queue & registry tabs */}
      <Paper variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
        <Stack direction="row" spacing={2} alignItems="center" justifyContent="space-between">
          <Typography variant="h6">پایش، تأیید و داده‌های مرجع</Typography>
          <Tabs value={queueView} onChange={(_e, v) => setQueueView(v)}>
            <Tab label={`نرمال‌سازی (${candidates.length})`} />
            <Tab label={`پست‌های وردپرس (${wpPending.length})`} />
            <Tab label={`بانک اطلاعات (${persons.length || '...'})`} />
          </Tabs>
        </Stack>
        <Divider sx={{ my: 1 }} />

        {/* Tab 0: Normalization candidates */}
        {queueView === 0 && (
          <TableContainer sx={{ maxHeight: 420 }}>
            <Table size="small" stickyHeader>
              <TableHead>
                <TableRow>
                  <TableCell>حوزه قضایی</TableCell>
                  <TableCell>موضوع</TableCell>
                  <TableCell>متن پاسخ واحد</TableCell>
                  <TableCell>گزینه / مقدار تأیید</TableCell>
                  <TableCell>تصمیم</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {candidates.map((candidate) => (
                  <TableRow key={candidate.candidate_id}>
                    <TableCell>{candidate.unit_name}</TableCell>
                    <TableCell>{METRIC_LABELS[candidate.metric] ?? candidate.metric}</TableCell>
                    <TableCell sx={{ maxWidth: 280 }}>{candidate.raw_text}</TableCell>
                    <TableCell>
                      {candidate.metric === 'imam_record' ? (
                        <Button
                          size="small"
                          variant="outlined"
                          startIcon={<PersonRounded />}
                          onClick={() => {
                            setImamModalCandidate(candidate)
                            setImamForm({
                              full_name: candidate.raw_text.replace(/حجت\s*الاسلام|شیخ|آقای/g, '').trim(),
                              position: candidate.unit_name,
                              source_kind: 'staff_cleric',
                            })
                          }}
                        >
                          تکمیل مشخصات امام جماعت
                        </Button>
                      ) : APPROVAL_CODES[candidate.metric] ? (
                        <Stack direction="row" spacing={0.5}>
                          {APPROVAL_CODES[candidate.metric].map((code) => (
                            <Chip
                              key={code}
                              size="small"
                              label={CODE_LABELS[code] ?? code}
                              color={draftValues[candidate.candidate_id] === code ? 'primary' : 'default'}
                              onClick={() =>
                                setDraftValues((prev) => ({
                                  ...prev,
                                  [candidate.candidate_id]: code,
                                }))
                              }
                            />
                          ))}
                        </Stack>
                      ) : (
                        <InputBase
                          placeholder="کد یا متن تأییدشده"
                          value={draftValues[candidate.candidate_id] ?? candidate.proposed_value}
                          onChange={(e) =>
                            setDraftValues((prev) => ({
                              ...prev,
                              [candidate.candidate_id]: e.target.value,
                            }))
                          }
                          sx={{ border: 1, borderColor: 'divider', borderRadius: 1, px: 1 }}
                        />
                      )}
                    </TableCell>
                    <TableCell>
                      <Stack direction="row" spacing={0.5}>
                        <Button
                          size="small"
                          variant="contained"
                          color="success"
                          startIcon={<CheckCircleOutlineRounded />}
                          onClick={() => {
                            if (candidate.metric === 'imam_record') {
                              setImamModalCandidate(candidate)
                              setImamForm({
                                full_name: candidate.raw_text.replace(/حجت\s*الاسلام|شیخ|آقای/g, '').trim(),
                                position: candidate.unit_name,
                                source_kind: 'staff_cleric',
                              })
                            } else {
                              void reviewCandidate(candidate.candidate_id, 'approve')
                            }
                          }}
                        >
                          تأیید
                        </Button>
                        <Button
                          size="small"
                          color="error"
                          startIcon={<CloseRounded />}
                          onClick={() => void reviewCandidate(candidate.candidate_id, 'reject')}
                        >
                          رد
                        </Button>
                      </Stack>
                    </TableCell>
                  </TableRow>
                ))}
                {candidates.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={5}>
                      <Alert severity="success">صف نرمال‌سازی خالی است — همهٔ داده‌ها وضعیت‌سنجی تأیید شده‌اند</Alert>
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </TableContainer>
        )}

        {/* Tab 1: Interactive WordPress Post Links */}
        {queueView === 1 && (
          <TableContainer sx={{ maxHeight: 420 }}>
            <Table size="small" stickyHeader>
              <TableHead>
                <TableRow>
                  <TableCell>عنوان خبر / پست وردپرس</TableCell>
                  <TableCell sx={{ minWidth: 200 }}>بخش تخصیصی</TableCell>
                  <TableCell>اعتماد هوشمند</TableCell>
                  <TableCell>وضعیت پیوند</TableCell>
                  <TableCell>عملیات</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {wpPending.map((link) => (
                  <TableRow key={link.link_id}>
                    <TableCell sx={{ maxWidth: 300 }}>
                      <Typography variant="body2" fontWeight={600} noWrap title={link.title}>
                        {link.title || link.post_slug}
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        {link.post_slug}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <FormControl size="small" fullWidth>
                        <Select
                          value={draftPostSection[link.link_id] ?? link.section ?? 'prayer'}
                          onChange={(e) =>
                            setDraftPostSection((prev) => ({
                              ...prev,
                              [link.link_id]: e.target.value,
                            }))
                          }
                        >
                          {SECTION_OPTIONS.map((opt) => (
                            <MenuItem key={opt.id} value={opt.id}>
                              {opt.title}
                            </MenuItem>
                          ))}
                        </Select>
                      </FormControl>
                    </TableCell>
                    <TableCell>{Math.round(link.confidence * 100)}٪</TableCell>
                    <TableCell>
                      <Chip
                        size="small"
                        label={
                          link.match_status === 'confirmed'
                            ? 'تأییدشده'
                            : link.match_status === 'auto'
                            ? 'خودکار'
                            : link.match_status === 'candidate'
                            ? 'پیشنهاد اولیه'
                            : 'بی‌پیوند'
                        }
                        color={
                          link.match_status === 'confirmed'
                            ? 'success'
                            : link.match_status === 'auto'
                            ? 'primary'
                            : 'default'
                        }
                        variant="outlined"
                      />
                    </TableCell>
                    <TableCell>
                      <Stack direction="row" spacing={1}>
                        <Button
                          size="small"
                          variant="contained"
                          color="primary"
                          startIcon={<LinkRounded />}
                          disabled={submittingLinkId === link.link_id}
                          onClick={() => void handleLinkPost(link.link_id)}
                        >
                          ثبت پیوند
                        </Button>
                        {link.match_status !== 'unmatched' && (
                          <Button
                            size="small"
                            color="error"
                            variant="outlined"
                            startIcon={<LinkOffRounded />}
                            disabled={submittingLinkId === link.link_id}
                            onClick={() => void handleUnlinkPost(link.link_id)}
                          >
                            ابطال
                          </Button>
                        )}
                      </Stack>
                    </TableCell>
                  </TableRow>
                ))}
                {wpPending.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={5}>
                      <Alert severity="success">تمام پست‌های وردپرس پیوند شده و در پایگاه رویدادها قرار دارند</Alert>
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </TableContainer>
        )}

        {/* Tab 2: Registry (Persons & Units) */}
        {queueView === 2 && (
          <Stack spacing={2}>
            <Stack direction="row" spacing={2} alignItems="center" justifyContent="space-between">
              <Stack direction="row" spacing={1}>
                <Chip
                  label={`همه (${persons.length})`}
                  color={personFilter === 'all' ? 'primary' : 'default'}
                  onClick={() => setPersonFilter('all')}
                />
                <Chip
                  label={`کارکنان (${persons.filter((p) => p.kind === 'employee').length})`}
                  color={personFilter === 'employee' ? 'primary' : 'default'}
                  onClick={() => setPersonFilter('employee')}
                />
                <Chip
                  label={`همراهان و خانواده‌ها (${persons.filter((p) => p.kind === 'family').length})`}
                  color={personFilter === 'family' ? 'primary' : 'default'}
                  onClick={() => setPersonFilter('family')}
                />
                <Chip label={`${units.length} حوزه قضایی`} variant="outlined" />
              </Stack>
              <TextField
                size="small"
                placeholder="جستجوی نام، پرسنلی یا محل خدمت..."
                value={personSearch}
                onChange={(e) => setPersonSearch(e.target.value)}
                sx={{ width: 280 }}
              />
            </Stack>

            <TableContainer sx={{ maxHeight: 420 }}>
              <Table size="small" stickyHeader>
                <TableHead>
                  <TableRow>
                    <TableCell>نام و نام خانوادگی</TableCell>
                    <TableCell>رده / نسبت</TableCell>
                    <TableCell>شماره پرسنلی</TableCell>
                    <TableCell>شماره همراه (محلی)</TableCell>
                    <TableCell>توضیحات و مناسبت</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {filteredPersons.map((p) => (
                    <TableRow key={p.person_id}>
                      <TableCell sx={{ fontWeight: 600 }}>{p.full_name}</TableCell>
                      <TableCell>
                        <Chip
                          size="small"
                          label={
                            p.kind === 'family'
                              ? `خانواده (${p.relation === 'spouse' ? 'همسر' : p.relation === 'child' ? 'فرزند' : 'همراه'})`
                              : 'کارمند'
                          }
                          color={p.kind === 'family' ? 'secondary' : 'default'}
                        />
                      </TableCell>
                      <TableCell>{p.personnel_no || p.related_personnel_no || '—'}</TableCell>
                      <TableCell sx={{ direction: 'ltr', textAlign: 'right' }}>{p.phone || '—'}</TableCell>
                      <TableCell sx={{ maxWidth: 350 }}>{p.notes || '—'}</TableCell>
                    </TableRow>
                  ))}
                  {filteredPersons.length === 0 && (
                    <TableRow>
                      <TableCell colSpan={5}>
                        <Alert severity="info">موردی مطابق با جستجو یافت نشد</Alert>
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </TableContainer>
          </Stack>
        )}
      </Paper>

      {/* Imam candidate approval dialog */}
      {imamModalCandidate && (
        <Dialog
          open
          onClose={() => setImamModalCandidate(null)}
          maxWidth="sm"
          fullWidth
          dir="rtl"
        >
          <DialogTitle>تکمیل و تأیید مشخصات امام جماعت</DialogTitle>
          <DialogContent>
            <Stack spacing={2} sx={{ mt: 1 }}>
              <Alert severity="info">
                حوزه قضایی: <strong>{imamModalCandidate.unit_name}</strong> | متن گزارش واحد:{' '}
                <em>{imamModalCandidate.raw_text}</em>
              </Alert>
              <TextField
                label="نام و نام خانوادگی امام جماعت"
                fullWidth
                size="small"
                value={imamForm.full_name}
                onChange={(e) => setImamForm((prev) => ({ ...prev, full_name: e.target.value }))}
              />
              <TextField
                label="سمت یا محل خدمت"
                fullWidth
                size="small"
                value={imamForm.position}
                onChange={(e) => setImamForm((prev) => ({ ...prev, position: e.target.value }))}
              />
              <FormControl fullWidth size="small">
                <InputLabel id="imam-source-label">وضعیت روحانیت و استقرار</InputLabel>
                <Select
                  labelId="imam-source-label"
                  label="وضعیت روحانیت و استقرار"
                  value={imamForm.source_kind}
                  onChange={(e) => setImamForm((prev) => ({ ...prev, source_kind: e.target.value }))}
                >
                  <MenuItem value="staff_cleric">روحانی شاغل دادگستری</MenuItem>
                  <MenuItem value="invited_external">دعوت‌شده از خارج دادگستری</MenuItem>
                  <MenuItem value="none">غیرروحانی / نامشخص</MenuItem>
                </Select>
              </FormControl>
            </Stack>
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setImamModalCandidate(null)}>انصراف</Button>
            <Button
              variant="contained"
              color="success"
              onClick={() =>
                void reviewCandidate(imamModalCandidate.candidate_id, 'approve', {
                  full_name: imamForm.full_name,
                  position: imamForm.position,
                  source_kind: imamForm.source_kind,
                })
              }
            >
              تأیید و ثبت در بانک ائمه
            </Button>
          </DialogActions>
        </Dialog>
      )}

      {/* Provincial visit dossier */}
      {dossier && (
        <Paper variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
          <Typography variant="h6">پروندهٔ بازدید استانی — ردیف ترویج نماز</Typography>
          <Typography variant="caption" color="text.secondary">
            {dossier.unit_count} حوزهٔ ثبت‌شده؛ فقط شمارش تجمیعی، بدون دادهٔ شخصی
          </Typography>
          <Grid container spacing={2} sx={{ mt: 1 }}>
            {dossier.visit_worksheet_row.cells.map((cell) => (
              <Grid size={{ xs: 12, md: 4 }} key={cell.label}>
                <Paper variant="outlined" sx={{ p: 1.5, borderRadius: 2 }}>
                  <Typography variant="caption" color="text.secondary">
                    {cell.label}
                  </Typography>
                  <Box component="pre" sx={{ m: 0, fontSize: 12, whiteSpace: 'pre-wrap' }}>
                    {JSON.stringify(cell.value, null, 1)}
                  </Box>
                </Paper>
              </Grid>
            ))}
          </Grid>
          {dossier.visit_worksheet_row.gaps.length > 0 && (
            <Box sx={{ mt: 1.5 }}>
              <Typography variant="subtitle2">شکاف‌ها</Typography>
              {dossier.visit_worksheet_row.gaps.map((gap, index) => (
                <Typography key={index} variant="body2" color="warning.dark">
                  • {gap}
                </Typography>
              ))}
            </Box>
          )}
        </Paper>
      )}
    </Stack>
  )
}
