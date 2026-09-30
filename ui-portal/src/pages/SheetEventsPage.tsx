import { useEffect, useMemo, useState } from 'react'
import {
  Alert, Box, Button, Card, CardActions, CardContent, Chip, Collapse, Dialog, DialogActions,
  DialogContent, DialogTitle, Divider, FormControl, Grid, IconButton, InputLabel,
  Link, MenuItem, Paper, Select, Skeleton, Table, TableBody, TableCell, TableContainer,
  TableHead, TablePagination, TableRow, TextField, ToggleButton, ToggleButtonGroup,
  Tooltip, Typography, useMediaQuery, useTheme, Breadcrumbs,
} from '@mui/material'
import ArrowForwardIcon from '@mui/icons-material/ArrowForward'
import AddCircleIcon from '@mui/icons-material/AddCircle'
import EditIcon from '@mui/icons-material/Edit'
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline'
import GridViewIcon from '@mui/icons-material/GridView'
import ViewListIcon from '@mui/icons-material/ViewList'
import TableChartIcon from '@mui/icons-material/TableChart'
import DashboardIcon from '@mui/icons-material/Dashboard'
import CalendarMonthIcon from '@mui/icons-material/CalendarMonth'
import LocationCityIcon from '@mui/icons-material/LocationCity'
import GroupsIcon from '@mui/icons-material/Groups'
import EventAvailableIcon from '@mui/icons-material/EventAvailable'
import PermMediaIcon from '@mui/icons-material/PermMedia'
import ExpandMoreIcon from '@mui/icons-material/ExpandMore'
import NavigateBeforeIcon from '@mui/icons-material/NavigateBefore'
import AccountBalanceIcon from '@mui/icons-material/AccountBalance'
import FactCheckIcon from '@mui/icons-material/FactCheck'
import ShieldIcon from '@mui/icons-material/VerifiedUser'
import PolicyIcon from '@mui/icons-material/Policy'

import {
  api, MANDATE_KINDS, type Mandate, type PortalEvent, type ProgramSheet, type VisitTopic,
} from '../api'
import { usePeriod } from '../components/PeriodPicker'
import { faCode, faDate, faNum } from '../periods'
import { ChipCode, VisitChip } from './DashboardPage'
import { EventEntryDialog } from '../dialogs/EventEntryDialog'
import { NewMandateDialog } from '../dialogs/NewMandateDialog'
import type { PageProps } from '../App'

/**
 * صفحهٔ اختصاصی و زیبای رویدادهای یک شیت در بازهٔ زمانی انتخاب‌شده
 */
export default function SheetEventsPage({ notify, openExcelDialog, navigateTo, params }: PageProps) {
  const periodCtx = usePeriod()
  const muiTheme = useTheme()
  const isMobile = useMediaQuery(muiTheme.breakpoints.down('md'))

  const sheetCode = params?.code || '80401'

  const [sheets, setSheets] = useState<ProgramSheet[] | null>(null)
  const [topics, setTopics] = useState<VisitTopic[] | null>(null)
  const [sheetMandates, setSheetMandates] = useState<Mandate[]>([])
  const [districtsList, setDistrictsList] = useState<string[]>([])

  const [unit, setUnit] = useState('')
  const [search, setSearch] = useState('')
  const [valueKind, setValueKind] = useState('')
  const [hasMedia, setHasMedia] = useState(false)
  const [sort, setSort] = useState('newest')
  const [viewMode, setViewMode] = useState<'cards' | 'table'>('cards')
  const [detailsExpanded, setDetailsExpanded] = useState(false)

  const [rows, setRows] = useState<PortalEvent[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(0)
  const [pageSize, setPageSize] = useState(24)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const [entryOpen, setEntryOpen] = useState(false)
  const [editId, setEditId] = useState<string | null>(null)
  const [mandateDialogOpen, setMandateDialogOpen] = useState(false)
  const [refreshKey, setRefreshKey] = useState(0)

  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false)
  const [deletingEventId, setDeletingEventId] = useState<string | null>(null)
  const [deletingOccasion, setDeletingOccasion] = useState('')
  const [deleteBusy, setDeleteBusy] = useState(false)

  // بارگذاری لیست همهٔ شیت‌ها و تاپیک‌ها بر اساس دورهٔ زمانی
  useEffect(() => {
    let alive = true
    Promise.all([
      api.sheets(periodCtx.range),
      api.visitTopics(periodCtx.range),
      api.districts(periodCtx.range, '', 100, 0),
    ])
      .then(([s, t, d]) => {
        if (!alive) return
        setSheets(s)
        setTopics(t)
        setDistrictsList(d.rows.map((r) => r.unit_name).filter(Boolean))
      })
      .catch(() => {})
    return () => { alive = false }
  }, [periodCtx.range.fromIso, periodCtx.range.toIso])

  // مستندات ابلاغی شیت جاری
  useEffect(() => {
    let alive = true
    api.sheetMeta(sheetCode)
      .then((meta) => { if (alive) setSheetMandates(meta.mandates ?? []) })
      .catch(() => { if (alive) setSheetMandates([]) })
    return () => { alive = false }
  }, [sheetCode, refreshKey])

  // پیدا کردن شیت یا موضوع بازدید فعلی
  const currentSheet = sheets?.find((s) => s.code === sheetCode) ?? null
  const currentTopic = !currentSheet ? (topics?.find((t) => t.ref === sheetCode) ?? null) : null
  const isVisitTopic = Boolean(currentTopic)

  const sheetTitle = currentSheet
    ? `${currentSheet.name} — ${currentSheet.title}`
    : currentTopic
    ? `${currentTopic.row_label}: ${currentTopic.title}`
    : `برنامهٔ کد ${faCode(sheetCode)}`

  const sheetShortName = currentSheet?.name || currentTopic?.name || sheetCode
  const sheetDescription = currentSheet?.description || currentTopic?.intro || ''
  const policyFramework = currentSheet?.policy_framework || ''
  const monitoringCriteria = currentSheet?.monitoring_criteria || []

  // استخراج سنجه‌های اختصاصی شیت
  const [dimColumns, setDimColumns] = useState<{ metric: string; label: string }[]>([])
  useEffect(() => {
    if (!sheetCode) { setDimColumns([]); return }
    if (currentSheet) {
      const cols = currentSheet.questions
        .filter((q) => q.auto_from && q.auto_from !== 'attendees' && q.auto_from !== 'event_count')
        .map((q) => ({ metric: q.auto_from, label: q.label }))
      setDimColumns(cols)
      return
    }
    api.entryFormSpec(sheetCode)
      .then((spec) => setDimColumns(spec.sections.flatMap((sec) =>
        sec.fields.filter((f) => f.t === 'number' && f.n.startsWith('dim_'))
          .map((f) => ({ metric: f.n.slice(4), label: f.l })))))
      .catch(() => setDimColumns([]))
  }, [sheetCode, currentSheet])

  // فیلترها و واکشی رویدادها
  const filters = useMemo(() => ({
    program_code: sheetCode,
    unit_name: unit,
    search,
    date_from: periodCtx.range.fromIso,
    date_to: periodCtx.range.toIso,
    value_kind: valueKind,
    has_media: hasMedia ? '1' : '',
    sort,
  }), [sheetCode, unit, search, periodCtx.range.fromIso, periodCtx.range.toIso, valueKind, hasMedia, sort])

  useEffect(() => { setPage(0) }, [filters])

  useEffect(() => {
    let alive = true
    setLoading(true)
    api.events(filters, pageSize, page * pageSize)
      .then((res) => {
        if (!alive) return
        setRows(res.rows)
        setTotal(res.total)
        setError('')
      })
      .catch((err) => alive && setError(err instanceof Error ? err.message : 'خطا در دریافت رویدادها'))
      .finally(() => alive && setLoading(false))
    return () => { alive = false }
  }, [filters, page, pageSize, refreshKey])

  // محاسبهٔ خلاصه آماری عملکرد همین شیت در این دوره
  const totalEventsCount = currentSheet?.count ?? currentTopic?.count ?? total
  const totalAttendeesSum = useMemo(() => {
    if (currentSheet && currentSheet.attendees > 0) return currentSheet.attendees
    if (currentTopic && currentTopic.attendees > 0) return currentTopic.attendees
    return rows.reduce((sum, r) => sum + (r.attendees_count || 0), 0)
  }, [currentSheet, currentTopic, rows])

  const activeDistrictsCount = useMemo(() => {
    const set = new Set(rows.map((r) => r.unit_name).filter(Boolean))
    return set.size
  }, [rows])

  const totalMediaInView = useMemo(() => {
    return rows.reduce((sum, r) => sum + (r.media_count || 0), 0)
  }, [rows])

  // تجمیع سنجه‌های خاص این شیت در رویدادهای واکشی‌شده
  const metricTotals = useMemo(() => {
    const res: Record<string, number> = {}
    for (const c of dimColumns) {
      let s = 0
      for (const ev of rows) {
        s += ev.facts?.[c.metric]?.value ?? 0
      }
      if (s > 0) res[c.label] = s
    }
    return res
  }, [dimColumns, rows])

  const handleDeleteRequest = (eventId: string, occasion: string) => {
    setDeletingEventId(eventId)
    setDeletingOccasion(occasion)
    setDeleteConfirmOpen(true)
  }

  const confirmDeleteEvent = async () => {
    if (!deletingEventId) return
    setDeleteBusy(true)
    try {
      await api.deleteEvent(deletingEventId)
      notify('رویداد با موفقیت حذف شد', 'success')
      setDeleteConfirmOpen(false)
      setDeletingEventId(null)
      if (rows.length === 1 && page > 0) {
        setPage((p) => p - 1)
      } else {
        setRefreshKey((k) => k + 1)
      }
    } catch (err) {
      notify(err instanceof Error ? err.message : 'خطا در حذف رویداد', 'error')
    } finally {
      setDeleteBusy(false)
    }
  }

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2.5 }}>
      {/* سطر ناوبری، خرده‌نان و دکمه‌های اقدام بالا */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 1.5 }}>
        <Breadcrumbs separator={<NavigateBeforeIcon fontSize="small" sx={{ color: 'text.disabled' }} />}>
          <Link
            underline="hover"
            color="inherit"
            sx={{ cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 0.6, fontSize: 13.5, fontWeight: 600 }}
            onClick={() => navigateTo ? navigateTo('dashboard') : (window.location.hash = '/dashboard')}
          >
            <DashboardIcon sx={{ fontSize: 18, color: 'primary.main' }} />
            داشبورد کلان
          </Link>
          <Typography color="text.secondary" sx={{ fontSize: 13.5 }}>
            {isVisitTopic ? 'کاربرگ بازدید استانی' : 'شیت‌های کاربرگ رسمی ۱۴۰۵'}
          </Typography>
          <Typography color="text.primary" sx={{ fontWeight: 800, fontSize: 13.5 }}>
            {sheetShortName}
          </Typography>
        </Breadcrumbs>

        <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', flexWrap: 'wrap' }}>
          <Button
            variant="outlined"
            color="primary"
            startIcon={<ArrowForwardIcon />}
            onClick={() => navigateTo ? navigateTo('dashboard') : (window.location.hash = '/dashboard')}
            sx={{ fontWeight: 700, borderRadius: 2 }}
          >
            بازگشت به داشبورد
          </Button>
          <Button
            variant="contained"
            color="primary"
            startIcon={<AddCircleIcon />}
            onClick={() => setEntryOpen(true)}
            sx={{ fontWeight: 800, borderRadius: 2, boxShadow: '0 4px 12px rgba(30, 58, 138, 0.25)' }}
          >
            ثبت رویداد جدید
          </Button>
          <Button
            variant="outlined"
            color="inherit"
            startIcon={<TableChartIcon />}
            onClick={openExcelDialog}
            sx={{ fontWeight: 600, borderRadius: 2 }}
          >
            اکسل دوره
          </Button>
        </Box>
      </Box>

      {/* نوار جابجایی سریع بین شیت‌ها (Sheet Switcher) */}
      <Paper
        elevation={0}
        sx={{
          p: 1.2,
          px: 1.5,
          display: 'flex',
          alignItems: 'center',
          gap: 1,
          overflowX: 'auto',
          borderRadius: 2.5,
          background: '#ffffff',
          border: '1px solid #e2e8f0',
        }}
      >
        <Typography variant="caption" sx={{ fontWeight: 800, color: 'text.secondary', whiteSpace: 'nowrap', ml: 0.5 }}>
          شیت‌های ۱۴۰۵:
        </Typography>
        {sheets?.map((s) => {
          const isActive = s.code === sheetCode
          return (
            <Chip
              key={s.code}
              label={`${s.name} (${faNum(s.count)})`}
              variant={isActive ? 'filled' : 'outlined'}
              color={isActive ? 'primary' : 'default'}
              onClick={() => navigateTo ? navigateTo(`sheet/${s.code}`) : (window.location.hash = `/sheet/${s.code}`)}
              sx={{
                fontWeight: isActive ? 800 : 500,
                fontSize: 12.5,
                borderRadius: 2,
                cursor: 'pointer',
                borderColor: isActive ? 'primary.main' : '#cbd5e1',
                bgcolor: isActive ? 'primary.main' : 'transparent',
                '&:hover': {
                  bgcolor: isActive ? 'primary.dark' : 'rgba(30, 58, 138, 0.06)',
                },
              }}
            />
          )
        })}
      </Paper>

      {/* هدر کارت ویژه و چشم‌نواز مشخصات شیت */}
      <Card
        sx={{
          borderRadius: 3,
          background: 'linear-gradient(135deg, #ffffff 0%, #f8fafc 100%)',
          border: '1px solid #e2e8f0',
          boxShadow: '0 4px 20px rgba(0,0,0,0.04)',
          position: 'relative',
          overflow: 'hidden',
          '&::before': {
            content: '""',
            position: 'absolute',
            top: 0,
            right: 0,
            left: 0,
            height: '4px',
            background: 'linear-gradient(90deg, #1e3a8a 0%, #3b82f6 50%, #06b6d4 100%)',
          },
        }}
      >
        <CardContent sx={{ p: { xs: 2, md: 3 }, display: 'flex', flexDirection: 'column', gap: 1.8 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 2 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, flexWrap: 'wrap' }}>
              {isVisitTopic ? (
                <VisitChip label={currentTopic?.row_label || 'کاربرگ بازدید'} />
              ) : (
                <ChipCode code={sheetCode} />
              )}
              <Box>
                <Typography variant="h5" sx={{ fontWeight: 900, color: '#0f172a', letterSpacing: '-0.3px' }}>
                  {sheetTitle}
                </Typography>
                <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block', mt: 0.4 }}>
                  {isVisitTopic
                    ? 'کاربرگ تکمیلی بازدید استانی دادگستری کل استان مازندران'
                    : 'کاربرگ رسمی مصوب ۱۴۰۵ — منبع حقیقت گزارش‌های پایش فرهنگی'}
                </Typography>
              </Box>
            </Box>

            <Box
              sx={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 1.2,
                background: '#eff6ff',
                border: '1px solid #bfdbfe',
                borderRadius: 2,
                px: 2,
                py: 1,
              }}
            >
              <CalendarMonthIcon sx={{ color: 'primary.main', fontSize: 24 }} />
              <Box>
                <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block', fontSize: 11, fontWeight: 600 }}>
                  بازهٔ زمانی انتخابی گزارش
                </Typography>
                <Typography variant="subtitle2" sx={{ fontWeight: 800, color: 'primary.dark', direction: 'rtl' }}>
                  {periodCtx.period.label}
                </Typography>
              </Box>
            </Box>
          </Box>

          {sheetDescription && (
            <Box
              sx={{
                p: 1.5,
                borderRadius: 2,
                background: '#f8fafc',
                border: '1px solid #e2e8f0',
                lineHeight: 1.9,
                fontSize: 13.5,
                color: '#334155',
              }}
            >
              <strong style={{ color: '#0f172a' }}>شرح عملیاتی و سرفصل اقدامات مصوب: </strong>
              {sheetDescription}
            </Box>
          )}

          {/* نوار اطلاعات تکمیلی: چارچوب سیاستی و اسناد بالادستی با باز و بسته شدن */}
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', pt: 0.5 }}>
            <Button
              size="small"
              variant="text"
              color="primary"
              endIcon={<ExpandMoreIcon sx={{ transform: detailsExpanded ? 'rotate(180deg)' : 'none', transition: '0.2s' }} />}
              onClick={() => setDetailsExpanded(!detailsExpanded)}
              sx={{ fontWeight: 700 }}
            >
              {detailsExpanded ? 'بستن مشخصات سیاستی و موازین پایش' : 'مشاهده موازین پایش، چارچوب سیاستی و اسناد ابلاغی'}
            </Button>
            <Typography variant="caption" color="text.secondary">
              تعداد مستندات ابلاغی متصل: <strong>{faNum(sheetMandates.length)}</strong> سند
            </Typography>
          </Box>

          <Collapse in={detailsExpanded}>
            <Box sx={{ pt: 1.5, display: 'flex', flexDirection: 'column', gap: 1.5, borderTop: '1px dashed #cbd5e1' }}>
              {policyFramework && (
                <Typography
                  variant="body2"
                  sx={{
                    background: '#fff7ed',
                    border: '1px solid #fed7aa',
                    borderRadius: 2,
                    px: 2,
                    py: 1,
                    color: '#9a3412',
                    lineHeight: 1.8,
                  }}
                >
                  <PolicyIcon sx={{ fontSize: 18, verticalAlign: 'middle', ml: 0.8 }} />
                  <strong>چارچوب سیاستی: </strong>
                  {policyFramework}
                </Typography>
              )}

              {monitoringCriteria.length > 0 && (
                <Box sx={{ background: '#f0fdf4', border: '1px solid #bbf7d0', borderRadius: 2, p: 2 }}>
                  <Typography variant="subtitle2" sx={{ fontWeight: 800, color: '#166534', mb: 1, display: 'flex', alignItems: 'center', gap: 0.8 }}>
                    <ShieldIcon sx={{ fontSize: 18 }} />
                    موازین و سنجه‌های پایش این برنامه:
                  </Typography>
                  <Box component="ul" sx={{ m: 0, pr: 2.5, columns: { md: 2 } }}>
                    {monitoringCriteria.map((c) => (
                      <Typography key={c} component="li" variant="body2" sx={{ lineHeight: 2, color: '#14532d' }}>
                        {c}
                      </Typography>
                    ))}
                  </Box>
                </Box>
              )}

              {/* جدول اسناد ابلاغی متصل */}
              <Box sx={{ mt: 1 }}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
                  <Typography variant="subtitle2" sx={{ fontWeight: 800 }}>
                    مستندات ابلاغی ثبت‌شده برای این برنامه ({faNum(sheetMandates.length)})
                  </Typography>
                  <Button size="small" variant="outlined" onClick={() => setMandateDialogOpen(true)}>
                    ثبت سند ابلاغی جدید
                  </Button>
                </Box>
                {sheetMandates.length === 0 ? (
                  <Typography variant="caption" color="text.secondary">
                    هنوز سند ابلاغی برای این برنامه ثبت نشده است.
                  </Typography>
                ) : (
                  <TableContainer component={Paper} variant="outlined" sx={{ borderRadius: 2 }}>
                    <Table size="small">
                      <TableHead sx={{ bgcolor: '#f8fafc' }}>
                        <TableRow>
                          <TableCell>نوع سند</TableCell>
                          <TableCell>عنوان سند</TableCell>
                          <TableCell>شماره سند</TableCell>
                          <TableCell>تاریخ ابلاغ</TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {sheetMandates.map((md) => (
                          <TableRow key={md.mandate_id} hover>
                            <TableCell>
                              <Chip size="small" color="primary" variant="outlined" label={MANDATE_KINDS[md.kind] ?? md.kind} />
                            </TableCell>
                            <TableCell>
                              <strong>{md.title}</strong>
                              {md.notes && (
                                <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
                                  {md.notes}
                                </Typography>
                              )}
                            </TableCell>
                            <TableCell><code>{md.number || '—'}</code></TableCell>
                            <TableCell sx={{ whiteSpace: 'nowrap' }}>{faDate(md.issued_on)}</TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </TableContainer>
                )}
              </Box>
            </Box>
          </Collapse>
        </CardContent>
      </Card>

      {/* کارت‌های شاخص‌های کلیدی عملکرد این شیت در دوره */}
      <Grid container spacing={2}>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <StatCard
            icon={<EventAvailableIcon sx={{ fontSize: 28 }} />}
            label="کل رویدادهای شیت در دوره"
            value={totalEventsCount}
            color="#0ea5e9"
            subtext={`در بازهٔ ${periodCtx.period.label}`}
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <StatCard
            icon={<GroupsIcon sx={{ fontSize: 28 }} />}
            label="مجموع مخاطبان و شرکت‌کنندگان"
            value={totalAttendeesSum}
            unit="نفر"
            color="#10b981"
            subtext="مجموع نفرات حضوریافته"
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <StatCard
            icon={<LocationCityIcon sx={{ fontSize: 28 }} />}
            label="حوزه‌های قضایی فعال"
            value={activeDistrictsCount}
            unit="حوزه"
            color="#8b5cf6"
            subtext="شهرستان‌ها و بخش‌های تابعه"
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <StatCard
            icon={<PermMediaIcon sx={{ fontSize: 28 }} />}
            label="فایل‌ها و مستندات رسانه‌ای"
            value={totalMediaInView}
            unit="رسانه"
            color="#f59e0b"
            subtext="تصاویر و اسناد پیوست"
          />
        </Grid>
      </Grid>

      {/* کارت سنجه‌های تفکیکی خاص این شیت در صورت وجود داده */}
      {Object.keys(metricTotals).length > 0 && (
        <Card variant="outlined" sx={{ borderRadius: 2.5, bgcolor: '#fbfcfd' }}>
          <CardContent sx={{ p: 2, '&:last-child': { pb: 2 } }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1.2 }}>
              <FactCheckIcon sx={{ color: 'primary.main', fontSize: 20 }} />
              <Typography variant="subtitle2" sx={{ fontWeight: 800 }}>
                تفکیک شاخص‌های تخصصی این شیت در دورهٔ انتخابی:
              </Typography>
            </Box>
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
              {Object.entries(metricTotals).map(([label, val]) => (
                <Chip
                  key={label}
                  label={`${label}: ${faNum(Math.round(val))}`}
                  color="primary"
                  variant="outlined"
                  sx={{
                    fontWeight: 700,
                    bgcolor: '#eff6ff',
                    fontSize: 12.5,
                    px: 0.5,
                  }}
                />
              ))}
            </Box>
          </CardContent>
        </Card>
      )}

      {/* نوار جستجو و فیلترهای رویدادهای شیت */}
      <Card sx={{ borderRadius: 2.5, boxShadow: '0 2px 8px rgba(0,0,0,0.03)' }}>
        <CardContent sx={{ display: 'flex', flexWrap: 'wrap', gap: 1.5, alignItems: 'center', p: 2 }}>
          <TextField
            size="small"
            label="جستجو در رویدادها (مناسبت، شرح، حوزه…)"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            sx={{ flex: { xs: '1 1 100%', md: 2 }, minWidth: 220 }}
          />

          <FormControl size="small" sx={{ minWidth: 170, flex: { xs: '1 1 100%', sm: 1 } }}>
            <InputLabel>حوزه قضایی</InputLabel>
            <Select label="حوزه قضایی" value={unit} onChange={(e) => setUnit(e.target.value)}>
              <MenuItem value="">همهٔ حوزه‌های قضایی</MenuItem>
              {districtsList.map((d) => (
                <MenuItem key={d} value={d}>{d}</MenuItem>
              ))}
            </Select>
          </FormControl>

          <FormControl size="small" sx={{ minWidth: 130 }}>
            <InputLabel>نوع آمار</InputLabel>
            <Select label="نوع آمار" value={valueKind} onChange={(e) => setValueKind(e.target.value)}>
              <MenuItem value="">همه</MenuItem>
              <MenuItem value="verified">فقط قطعی</MenuItem>
              <MenuItem value="estimated">فقط تخمینی</MenuItem>
            </Select>
          </FormControl>

          <FormControl size="small" sx={{ minWidth: 130 }}>
            <InputLabel>مرتب‌سازی</InputLabel>
            <Select label="مرتب‌سازی" value={sort} onChange={(e) => setSort(e.target.value)}>
              <MenuItem value="newest">جدیدترین</MenuItem>
              <MenuItem value="oldest">قدیمی‌ترین</MenuItem>
              <MenuItem value="attendees">بیشترین مخاطب</MenuItem>
            </Select>
          </FormControl>

          <Chip
            label="فقط دارای رسانه/عکس"
            color={hasMedia ? 'primary' : 'default'}
            variant={hasMedia ? 'filled' : 'outlined'}
            onClick={() => setHasMedia(!hasMedia)}
            sx={{ cursor: 'pointer', fontWeight: 600 }}
          />

          <Box sx={{ mr: 'auto', display: 'flex', alignItems: 'center', gap: 1 }}>
            <ToggleButtonGroup
              size="small"
              value={viewMode}
              exclusive
              onChange={(_, m) => m && setViewMode(m)}
              aria-label="نوع نمایش"
            >
              <ToggleButton value="cards" aria-label="نمای کارتی">
                <GridViewIcon fontSize="small" sx={{ ml: 0.5 }} />
                کارت‌ها
              </ToggleButton>
              <ToggleButton value="table" aria-label="نمای جدولی">
                <ViewListIcon fontSize="small" sx={{ ml: 0.5 }} />
                جدول
              </ToggleButton>
            </ToggleButtonGroup>
          </Box>
        </CardContent>
      </Card>

      {error && <Alert severity="error">{error}</Alert>}

      {/* نمایش رویدادها — حالت کارتی یا جدولی */}
      {viewMode === 'cards' ? (
        <CardsView
          loading={loading}
          rows={rows}
          columns={dimColumns}
          onEdit={(id) => { setEditId(id); setEntryOpen(true) }}
          onDelete={handleDeleteRequest}
          onAddNew={() => setEntryOpen(true)}
          periodLabel={periodCtx.period.label}
          sheetName={sheetShortName}
        />
      ) : (
        <TableView
          loading={loading}
          rows={rows}
          columns={dimColumns}
          onEdit={(id) => { setEditId(id); setEntryOpen(true) }}
          onDelete={handleDeleteRequest}
          onAddNew={() => setEntryOpen(true)}
          periodLabel={periodCtx.period.label}
          sheetName={sheetShortName}
        />
      )}

      {/* صفحه‌بندی */}
      <TablePagination
        component="div"
        count={total}
        page={page}
        onPageChange={(_, p) => setPage(p)}
        rowsPerPage={pageSize}
        onRowsPerPageChange={(e) => { setPageSize(Number(e.target.value)); setPage(0) }}
        rowsPerPageOptions={[12, 24, 48, 96]}
        labelRowsPerPage="رویداد در صفحه:"
        labelDisplayedRows={({ from, to, count }) => `${faNum(from)}–${faNum(to)} از ${faNum(count)}`}
        sx={{
          bgcolor: '#ffffff',
          borderRadius: 2,
          border: '1px solid #e2e8f0',
        }}
      />

      {/* دیالوگ ثبت و اصلاح رویداد */}
      <EventEntryDialog
        open={entryOpen}
        initialRef={sheetCode}
        editEventId={editId}
        onClose={() => { setEntryOpen(false); setEditId(null) }}
        onSaved={() => {
          setEntryOpen(false)
          setEditId(null)
          notify(editId ? 'تغییرات رویداد با موفقیت ذخیره شد' : 'رویداد فرهنگی جدید با موفقیت ثبت شد', 'success')
          setPage(0)
          setRefreshKey((k) => k + 1)
        }}
      />

      {/* دیالوگ ثبت سند ابلاغی جدید */}
      <NewMandateDialog
        open={mandateDialogOpen}
        initialProgram={sheetCode}
        onClose={() => setMandateDialogOpen(false)}
        onSaved={(title) => {
          setMandateDialogOpen(false)
          notify(`سند ابلاغی «${title}» ثبت شد`, 'success')
          setRefreshKey((k) => k + 1)
        }}
      />

      {/* دیالوگ تأیید حذف رویداد */}
      <Dialog
        open={deleteConfirmOpen}
        onClose={() => !deleteBusy && setDeleteConfirmOpen(false)}
        maxWidth="xs"
        fullWidth
      >
        <DialogTitle sx={{ fontWeight: 800, color: 'error.main', display: 'flex', alignItems: 'center', gap: 1 }}>
          <DeleteOutlineIcon color="error" />
          تأیید حذف رویداد فرهنگی
        </DialogTitle>
        <DialogContent dividers>
          <Typography variant="body2" sx={{ lineHeight: 1.9, mt: 0.5 }}>
            آیا از حذف رویداد <strong>«{deletingOccasion}»</strong> اطمینان دارید؟
          </Typography>
          <Box sx={{ mt: 1, display: 'inline-flex', alignItems: 'center', gap: 0.5 }}>
            <Typography variant="caption" color="text.secondary">شناسه رویداد:</Typography>
            <Chip size="small" label={deletingEventId} sx={{ fontFamily: 'monospace', fontSize: 10.5 }} />
          </Box>
          <Typography
            variant="caption"
            color="error.dark"
            sx={{
              display: 'block',
              mt: 1.5,
              lineHeight: 1.7,
              background: '#fef2f2',
              p: 1.2,
              borderRadius: 1.5,
              border: '1px dashed #fca5a5',
            }}
          >
            توجه: با حذف این رویداد، کلیه سنجه‌ها و فکت‌های متصل به آن حذف شده و در کارنامه و اکسل دوره منعکس نخواهد شد.
          </Typography>
        </DialogContent>
        <DialogActions sx={{ px: 2.5, py: 1.5, justifyContent: 'space-between' }}>
          <Button onClick={() => setDeleteConfirmOpen(false)} disabled={deleteBusy} color="inherit">
            انصراف
          </Button>
          <Button
            variant="contained"
            color="error"
            onClick={confirmDeleteEvent}
            disabled={deleteBusy}
            startIcon={<DeleteOutlineIcon />}
            sx={{ fontWeight: 700 }}
          >
            {deleteBusy ? 'در حال حذف...' : 'تأیید و حذف قطعی'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  )
}

function StatCard({
  icon, label, value, unit, color, subtext,
}: {
  icon: React.ReactNode
  label: string
  value: number | undefined
  unit?: string
  color: string
  subtext?: string
}) {
  return (
    <Card sx={{ borderRadius: 2.5, border: '1px solid #e2e8f0', boxShadow: '0 2px 8px rgba(0,0,0,0.03)' }}>
      <CardContent sx={{ p: 2, '&:last-child': { pb: 2 } }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
          <Box
            sx={{
              width: 48,
              height: 48,
              borderRadius: 2,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              bgcolor: `${color}15`,
              color,
              flexShrink: 0,
            }}
          >
            {icon}
          </Box>
          <Box sx={{ minWidth: 0, flex: 1 }}>
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', fontWeight: 600 }}>
              {label}
            </Typography>
            <Typography variant="h5" sx={{ fontWeight: 900, color: '#0f172a', mt: 0.2 }}>
              {value === undefined ? <Skeleton width={60} /> : faNum(value)}
              {unit && <Typography component="span" variant="caption" sx={{ mr: 0.5, color: 'text.secondary', fontWeight: 500 }}>{unit}</Typography>}
            </Typography>
            {subtext && (
              <Typography variant="caption" sx={{ color: 'text.disabled', display: 'block', fontSize: 10.5 }}>
                {subtext}
              </Typography>
            )}
          </Box>
        </Box>
      </CardContent>
    </Card>
  )
}

function CardsView({
  loading, rows, columns, onEdit, onDelete, onAddNew, periodLabel, sheetName,
}: {
  loading: boolean
  rows: PortalEvent[]
  columns: { metric: string; label: string }[]
  onEdit: (id: string) => void
  onDelete: (id: string, occasion: string) => void
  onAddNew: () => void
  periodLabel: string
  sheetName: string
}) {
  if (loading && rows.length === 0) {
    return (
      <Grid container spacing={2}>
        {Array.from({ length: 6 }).map((_, i) => (
          <Grid size={{ xs: 12, sm: 6, lg: 4 }} key={i}>
            <Skeleton variant="rounded" height={220} sx={{ borderRadius: 2.5 }} />
          </Grid>
        ))}
      </Grid>
    )
  }

  if (!loading && rows.length === 0) {
    return (
      <Paper sx={{ p: 5, textAlign: 'center', borderRadius: 3, border: '1px dashed #cbd5e1', bgcolor: '#f8fafc' }}>
        <EventAvailableIcon sx={{ fontSize: 48, color: '#94a3b8', mb: 1.5 }} />
        <Typography variant="h6" sx={{ fontWeight: 800, color: '#334155' }}>
          رویدادی برای شیت «{sheetName}» در بازهٔ «{periodLabel}» یافت نشد.
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5, mb: 2.5 }}>
          می‌توانید بازهٔ زمانی بالای صفحه را تغییر دهید یا رویداد جدیدی برای این شیت ثبت نمایید.
        </Typography>
        <Button variant="contained" color="primary" startIcon={<AddCircleIcon />} onClick={onAddNew}>
          ثبت اولین رویداد برای این شیت
        </Button>
      </Paper>
    )
  }

  return (
    <Grid container spacing={2}>
      {rows.map((ev) => (
        <Grid size={{ xs: 12, sm: 6, lg: 4 }} key={ev.event_id}>
          <EventGridCard ev={ev} columns={columns} onEdit={() => onEdit(ev.event_id)} onDelete={onDelete} />
        </Grid>
      ))}
    </Grid>
  )
}

function EventGridCard({
  ev, columns, onEdit, onDelete,
}: {
  ev: PortalEvent
  columns: { metric: string; label: string }[]
  onEdit: () => void
  onDelete: (id: string, occasion: string) => void
}) {
  const [expanded, setExpanded] = useState(false)
  const attendees = ev.attendees_count
  const title = ev.occasion || 'برنامه فرهنگی'
  const activeMetrics = columns.filter((c) => (ev.facts?.[c.metric]?.value ?? 0) > 0)
  const isAshura = Number(ev.is_ashura_pilgrimage) === 1

  return (
    <Card
      sx={{
        borderRadius: 2.5,
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        border: '1px solid #e2e8f0',
        transition: 'all 0.2s ease-in-out',
        boxShadow: '0 2px 6px rgba(0,0,0,0.03)',
        '&:hover': {
          borderColor: 'primary.main',
          boxShadow: '0 8px 24px rgba(30, 58, 138, 0.08)',
          transform: 'translateY(-2px)',
        },
      }}
    >
      <CardContent sx={{ p: 2, flex: 1, display: 'flex', flexDirection: 'column', gap: 1.2 }}>
        {/* سطر اول: حوزه قضایی و تاریخ */}
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 1 }}>
          <Chip
            icon={<AccountBalanceIcon sx={{ fontSize: '14px !important' }} />}
            label={ev.unit_name || 'دادگستری کل مازندران'}
            size="small"
            sx={{ fontWeight: 700, bgcolor: '#f1f5f9', fontSize: 11.5 }}
          />
          <Chip
            icon={<CalendarMonthIcon sx={{ fontSize: '14px !important' }} />}
            label={faDate(ev.occurred_on)}
            size="small"
            variant="outlined"
            sx={{ fontSize: 11.5, fontWeight: 600 }}
          />
        </Box>

        {/* عنوان رویداد / مناسبت */}
        <Typography
          variant="subtitle1"
          onClick={onEdit}
          sx={{
            fontWeight: 800,
            fontSize: 15,
            color: '#0f172a',
            cursor: 'pointer',
            lineHeight: 1.4,
            '&:hover': { color: 'primary.main', textDecoration: 'underline' },
          }}
        >
          {title}
        </Typography>

        {/* برچسب‌های آماری: مخاطبان، رسانه و تگ‌های خاص */}
        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.8, alignItems: 'center' }}>
          {attendees !== null && attendees !== undefined ? (
            <Chip
              size="small"
              icon={<GroupsIcon sx={{ fontSize: '14px !important' }} />}
              label={`${faNum(attendees)} نفر${ev.attendees_value_kind === 'estimated' ? ' (تخمینی)' : ''}`}
              color={ev.attendees_value_kind === 'estimated' ? 'warning' : 'primary'}
              variant="outlined"
              sx={{ fontWeight: 700, fontSize: 11.5 }}
            />
          ) : (
            <Chip size="small" label="بدون آمار مخاطب" variant="outlined" sx={{ fontSize: 11, color: 'text.disabled' }} />
          )}

          {ev.media_count > 0 && (
            <Chip
              size="small"
              icon={<PermMediaIcon sx={{ fontSize: '13px !important' }} />}
              label={`${faNum(ev.media_count)} رسانه`}
              variant="outlined"
              color="info"
              sx={{ fontSize: 11, fontWeight: 600 }}
            />
          )}

          {isAshura && (
            <Chip size="small" label="زیارت عاشورا" color="secondary" sx={{ fontSize: 11, fontWeight: 700 }} />
          )}

          {Number(ev.official_present) === 1 && (
            <Chip size="small" label="حضور مسئولین" variant="outlined" sx={{ fontSize: 10.5 }} />
          )}

          {Number(ev.had_reception) === 1 && (
            <Chip size="small" label="پذیرایی" variant="outlined" sx={{ fontSize: 10.5 }} />
          )}
        </Box>

        {/* فکت‌ها و سنجه‌های اختصاصی شیت */}
        {activeMetrics.length > 0 && (
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.6, pt: 0.8, borderTop: '1px dashed #e2e8f0' }}>
            {activeMetrics.map((c) => {
              const v = ev.facts?.[c.metric]?.value ?? 0
              return (
                <Chip
                  key={c.metric}
                  size="small"
                  color="success"
                  variant="outlined"
                  label={`${c.label}: ${faNum(Math.round(v))}`}
                  sx={{ fontSize: 11, bgcolor: '#f0fdf4', fontWeight: 600 }}
                />
              )
            })}
          </Box>
        )}

        {/* شرح و توضیحات رویداد */}
        {ev.notes && (
          <Box sx={{ mt: 'auto', pt: 0.5 }}>
            <Typography
              variant="body2"
              color="text.secondary"
              sx={{
                fontSize: 12.5,
                lineHeight: 1.6,
                color: '#475569',
                display: '-webkit-box',
                WebkitLineClamp: expanded ? 'unset' : 2,
                WebkitBoxOrient: 'vertical',
                overflow: 'hidden',
              }}
            >
              {ev.notes}
            </Typography>
            {ev.notes.length > 90 && (
              <Typography
                component="span"
                variant="caption"
                onClick={() => setExpanded(!expanded)}
                sx={{
                  color: 'primary.main',
                  cursor: 'pointer',
                  fontWeight: 700,
                  fontSize: 11,
                  display: 'inline-block',
                  mt: 0.3,
                  '&:hover': { textDecoration: 'underline' },
                }}
              >
                {expanded ? 'بستن متن' : 'نمایش کامل متن'}
              </Typography>
            )}
          </Box>
        )}
      </CardContent>

      <Divider />

      <CardActions sx={{ px: 2, py: 1, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Box sx={{ display: 'flex', gap: 0.8 }}>
          <Button
            size="small"
            variant="outlined"
            color="primary"
            startIcon={<EditIcon sx={{ fontSize: '14px !important' }} />}
            onClick={onEdit}
            sx={{ fontWeight: 700, fontSize: 11.5, py: 0.3, px: 1.2, borderRadius: 1.5 }}
          >
            اصلاح رویداد
          </Button>
          <Button
            size="small"
            variant="outlined"
            color="error"
            startIcon={<DeleteOutlineIcon sx={{ fontSize: '14px !important' }} />}
            onClick={() => onDelete(ev.event_id, title)}
            sx={{ fontWeight: 700, fontSize: 11.5, py: 0.3, px: 1, borderRadius: 1.5 }}
          >
            حذف
          </Button>
        </Box>
        <Typography variant="caption" sx={{ fontFamily: 'monospace', fontSize: 10, color: 'text.disabled', direction: 'ltr' }}>
          {ev.event_id}
        </Typography>
      </CardActions>
    </Card>
  )
}

function TableView({
  loading, rows, columns, onEdit, onDelete, onAddNew, periodLabel, sheetName,
}: {
  loading: boolean
  rows: PortalEvent[]
  columns: { metric: string; label: string }[]
  onEdit: (id: string) => void
  onDelete: (id: string, occasion: string) => void
  onAddNew: () => void
  periodLabel: string
  sheetName: string
}) {
  return (
    <TableContainer component={Paper} sx={{ borderRadius: 2.5, border: '1px solid #e2e8f0', overflowX: 'auto' }}>
      <Table size="small" sx={{ minWidth: 900 }}>
        <TableHead sx={{ bgcolor: '#f8fafc' }}>
          <TableRow>
            <TableCell sx={{ fontWeight: 800 }}>تاریخ</TableCell>
            <TableCell sx={{ fontWeight: 800 }}>حوزه قضایی</TableCell>
            <TableCell sx={{ fontWeight: 800 }}>مناسبت / رویداد</TableCell>
            <TableCell align="center" sx={{ fontWeight: 800 }}>مخاطبان</TableCell>
            {columns.map((c) => (
              <TableCell
                key={c.metric}
                align="center"
                sx={{
                  background: '#f1f5f9',
                  fontSize: 11,
                  fontWeight: 800,
                  minWidth: 85,
                  maxWidth: 120,
                  px: 1,
                  borderLeft: '1px solid #e2e8f0',
                }}
              >
                {c.label}
              </TableCell>
            ))}
            <TableCell align="center" sx={{ fontWeight: 800, minWidth: 65 }}>رسانه</TableCell>
            <TableCell
              align="center"
              sx={{
                position: 'sticky',
                left: 0,
                background: '#f8fafc',
                zIndex: 3,
                minWidth: 125,
                boxShadow: '-3px 0 8px -2px rgba(0,0,0,0.12)',
                borderRight: '1px solid #cbd5e1',
                fontWeight: 800,
              }}
            >
              عملیات
            </TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {loading && rows.length === 0 && (
            Array.from({ length: 6 }).map((_, i) => (
              <TableRow key={i}><TableCell colSpan={7 + columns.length}><Skeleton /></TableCell></TableRow>
            ))
          )}
          {!loading && rows.length === 0 && (
            <TableRow>
              <TableCell colSpan={7 + columns.length} align="center" sx={{ py: 6 }}>
                <Typography variant="body1" sx={{ fontWeight: 700, color: 'text.secondary', mb: 1 }}>
                  رویدادی برای شیت «{sheetName}» در بازهٔ «{periodLabel}» یافت نشد.
                </Typography>
                <Button variant="outlined" color="primary" startIcon={<AddCircleIcon />} onClick={onAddNew}>
                  ثبت رویداد جدید
                </Button>
              </TableCell>
            </TableRow>
          )}
          {rows.map((ev) => {
            const attendees = ev.attendees_count
            const title = ev.occasion || 'برنامه فرهنگی'
            return (
              <TableRow key={ev.event_id} hover>
                <TableCell sx={{ whiteSpace: 'nowrap' }}><code>{faDate(ev.occurred_on)}</code></TableCell>
                <TableCell><strong>{ev.unit_name || 'دادگستری کل مازندران'}</strong></TableCell>
                <TableCell sx={{ minWidth: 240, maxWidth: 360 }}>
                  <Typography
                    component="span"
                    onClick={() => onEdit(ev.event_id)}
                    sx={{
                      fontWeight: 800,
                      fontSize: 13.5,
                      cursor: 'pointer',
                      color: 'primary.main',
                      '&:hover': { textDecoration: 'underline' },
                    }}
                  >
                    {title}
                  </Typography>
                  {Number(ev.is_ashura_pilgrimage) === 1 && (
                    <Chip size="small" label="زیارت عاشورا" sx={{ mr: 0.5 }} />
                  )}
                  {ev.notes && (
                    <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.3, lineHeight: 1.5 }}>
                      {ev.notes.slice(0, 85)}{ev.notes.length > 85 ? '…' : ''}
                    </Typography>
                  )}
                </TableCell>
                <TableCell align="center">
                  {attendees !== null && attendees !== undefined ? (
                    <Chip
                      size="small"
                      color={ev.attendees_value_kind === 'estimated' ? 'warning' : 'primary'}
                      variant="outlined"
                      label={`${faNum(attendees)} نفر`}
                    />
                  ) : '—'}
                </TableCell>
                {columns.map((c) => {
                  const v = ev.facts?.[c.metric]?.value ?? 0
                  return (
                    <TableCell
                      key={c.metric}
                      align="center"
                      sx={{ minWidth: 85, maxWidth: 120, px: 1, borderLeft: '1px solid #f1f5f9' }}
                    >
                      {v > 0 ? (
                        <Chip
                          size="small"
                          variant={v > 1 ? 'filled' : 'outlined'}
                          color={v > 1 ? 'primary' : 'success'}
                          label={v > 1 ? faNum(Math.round(v)) : '✓'}
                        />
                      ) : <span style={{ color: '#cbd5e1' }}>—</span>}
                    </TableCell>
                  )
                })}
                <TableCell align="center" sx={{ minWidth: 65 }}>
                  {ev.media_count > 0 ? faNum(ev.media_count) : '—'}
                </TableCell>
                <TableCell
                  align="center"
                  sx={{
                    position: 'sticky',
                    left: 0,
                    background: '#ffffff',
                    zIndex: 2,
                    minWidth: 125,
                    boxShadow: '-3px 0 8px -2px rgba(0,0,0,0.12)',
                    borderRight: '1px solid #e2e8f0',
                    py: 1,
                  }}
                >
                  <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 0.5 }}>
                    <Box sx={{ display: 'flex', gap: 0.6, alignItems: 'center' }}>
                      <Button
                        size="small"
                        variant="contained"
                        color="primary"
                        onClick={() => onEdit(ev.event_id)}
                        startIcon={<EditIcon sx={{ fontSize: '13px !important' }} />}
                        sx={{ minWidth: 0, px: 1.2, py: 0.35, fontSize: 11.5, fontWeight: 700, whiteSpace: 'nowrap' }}
                      >
                        اصلاح
                      </Button>
                      <IconButton
                        size="small"
                        color="error"
                        onClick={() => onDelete(ev.event_id, title)}
                        title="حذف رویداد"
                        sx={{ p: 0.45, border: '1px solid #fee2e2', borderRadius: 1 }}
                      >
                        <DeleteOutlineIcon sx={{ fontSize: 16 }} />
                      </IconButton>
                    </Box>
                    <Typography variant="caption" sx={{ display: 'block', direction: 'ltr', fontSize: 9.5, color: 'text.disabled' }}>
                      {ev.event_id}
                    </Typography>
                  </Box>
                </TableCell>
              </TableRow>
            )
          })}
        </TableBody>
      </Table>
    </TableContainer>
  )
}
