// Office dashboard — the office product panel (F-088/F-090, phase D).
// Shows: section cards with realization, the human approval queue
// (normalization candidates + unmatched WP posts) and the prayer visit
// dossier. All data comes from /api/v3/office/* endpoints.
import { useCallback, useEffect, useState } from 'react'
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Divider,
  Grid,
  InputBase,
  LinearProgress,
  Paper,
  Stack,
  Tab,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Tabs,
  Typography,
} from '@mui/material'
import CheckCircleOutlineRounded from '@mui/icons-material/CheckCircleOutlineRounded'
import CloseRounded from '@mui/icons-material/CloseRounded'
import RefreshRounded from '@mui/icons-material/RefreshRounded'
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
  chief_participation: 'حضور رئیس حوزه',
  imam_public_satisfaction: 'رضایت عمومی از امام جماعت',
  azan_broadcast: 'پخش اذان',
  imam_record: 'ثبت امام جماعت',
  jammat_frequency: 'تواتر نماز جماعت',
  imam_source: 'منبع امام جماعت',
  council_sessions_band: 'جلسات شورا',
}

const APPROVAL_CODES: Record<string, string[]> = {
  chief_participation: ['always', 'occasionally', 'rarely'],
  imam_public_satisfaction: ['high', 'medium', 'low'],
  azan_broadcast: ['regular', 'sometimes', 'none'],
}

const SECTION_SOURCE_LABEL: Record<string, string> = {
  workbook_1405: 'کاربرگ ۱۴۰۵',
  visit_worksheet: 'کاربرگ بازدید',
}

export default function OfficeDashboard() {
  const [loading, setLoading] = useState(false)
  const [period, setPeriod] = useState('1405')
  const [sections, setSections] = useState<OfficeSection[]>([])
  const [candidates, setCandidates] = useState<NormalizationCandidate[]>([])
  const [wpPending, setWpPending] = useState<WpPendingLink[]>([])
  const [dossier, setDossier] = useState<Dossier | null>(null)
  const [queueView, setQueueView] = useState(0)
  const [draftValues, setDraftValues] = useState<Record<string, string>>({})

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
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'خطا در دریافت داده‌های دفتر')
    } finally {
      setLoading(false)
    }
  }, [period])

  useEffect(() => {
    void load()
  }, [load])

  const reviewCandidate = async (candidateId: string, action: 'approve' | 'reject') => {
    const coded = draftValues[candidateId] ?? ''
    try {
      await api('POST', `/api/v3/office/queue/${candidateId}/review`, {
        action,
        coded_value: coded,
        reviewed_by: 'office-operator',
      })
      toast.success(action === 'approve' ? 'کدگذاری تأیید و ثبت شد' : 'کاندید رد شد')
      setDraftValues((prev) => {
        const next = { ...prev }
        delete next[candidateId]
        return next
      })
      void load()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'خطا در ثبت تصمیم')
    }
  }

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
                      value={Math.round(item.ratio * 100)}
                      sx={{ height: 6, borderRadius: 3 }}
                    />
                  </Box>
                ))}
              </CardContent>
            </Card>
          </Grid>
        ))}
      </Grid>

      {/* approval queue */}
      <Paper variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
        <Stack direction="row" spacing={2} alignItems="center" justifyContent="space-between">
          <Typography variant="h6">صف تأیید انسانی</Typography>
          <Tabs value={queueView} onChange={(_e, v) => setQueueView(v)}>
            <Tab label={`نرمال‌سازی (${candidates.length})`} />
            <Tab label={`پست‌های بی‌پیوند (${wpPending.length})`} />
          </Tabs>
        </Stack>
        <Divider sx={{ my: 1 }} />
        {queueView === 0 && (
          <TableContainer sx={{ maxHeight: 420 }}>
            <Table size="small" stickyHeader>
              <TableHead>
                <TableRow>
                  <TableCell>حوزه</TableCell>
                  <TableCell>موضوع</TableCell>
                  <TableCell>متن پاسخ</TableCell>
                  <TableCell>کد تأیید</TableCell>
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
                      {APPROVAL_CODES[candidate.metric] ? (
                        <Stack direction="row" spacing={0.5}>
                          {APPROVAL_CODES[candidate.metric].map((code) => (
                            <Chip
                              key={code}
                              size="small"
                              label={code}
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
                          onClick={() => void reviewCandidate(candidate.candidate_id, 'approve')}
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
                      <Alert severity="success">صف نرمال‌سازی خالی است</Alert>
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </TableContainer>
        )}
        {queueView === 1 && (
          <TableContainer sx={{ maxHeight: 420 }}>
            <Table size="small" stickyHeader>
              <TableHead>
                <TableRow>
                  <TableCell>پست</TableCell>
                  <TableCell>بخش پیشنهادی</TableCell>
                  <TableCell>اعتماد</TableCell>
                  <TableCell>وضعیت</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {wpPending.map((link) => (
                  <TableRow key={link.link_id}>
                    <TableCell sx={{ maxWidth: 320 }}>{link.title || link.post_slug}</TableCell>
                    <TableCell>{link.section || '—'}</TableCell>
                    <TableCell>{Math.round(link.confidence * 100)}٪</TableCell>
                    <TableCell>
                      <Chip size="small" label={link.match_status} variant="outlined" />
                    </TableCell>
                  </TableRow>
                ))}
                {wpPending.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={4}>
                      <Alert severity="success">همهٔ پست‌ها پیوند دارند</Alert>
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </Paper>

      {/* dossier */}
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
