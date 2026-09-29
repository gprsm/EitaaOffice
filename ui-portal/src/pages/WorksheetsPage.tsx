import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  Alert, Box, Button, Card, CardContent, Chip, Dialog, DialogActions, DialogContent,
  DialogTitle, FormControl, Grid, IconButton, InputLabel, MenuItem, Paper, Select,
  Skeleton, Table, TableBody, TableCell, TableHead, TableContainer, TablePagination,
  TableRow, TextField, Typography, useMediaQuery, useTheme,
} from '@mui/material'
import FilterAltIcon from '@mui/icons-material/FilterAlt'
import AddCircleIcon from '@mui/icons-material/AddCircle'
import EditIcon from '@mui/icons-material/Edit'
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline'
import { api, PROGRAM_REFS, type PortalEvent, type ProgramSheet, type VisitTopic } from '../api'
import { usePeriod } from '../components/PeriodPicker'
import { faCode, faDate, faNum } from '../periods'
import { ChipCode, VisitChip } from './DashboardPage'
import { EventEntryDialog } from '../dialogs/EventEntryDialog'
import { NewMandateDialog } from '../dialogs/NewMandateDialog'
import { api as apiClient, MANDATE_KINDS, type Mandate } from '../api'
import type { PageProps } from '../App'

/** کارتابل رویدادها — فیلترها + دورهٔ مشترک + ستون‌های اختصاصی شیت (F-097) */
export default function WorksheetsPage({ notify, openExcelDialog }: PageProps) {
  const periodCtx = usePeriod()
  const muiTheme = useTheme()
  const isMobile = useMediaQuery(muiTheme.breakpoints.down('md'))

  const [program, setProgram] = useState('')
  const [unit, setUnit] = useState('')
  const [search, setSearch] = useState('')
  const [valueKind, setValueKind] = useState('')
  const [minAttendees, setMinAttendees] = useState('')
  const [hasMedia, setHasMedia] = useState(false)
  const [sort, setSort] = useState('newest')
  const [occasionClass, setOccasionClass] = useState('')

  const [sheets, setSheets] = useState<ProgramSheet[] | null>(null)
  const [topics, setTopics] = useState<VisitTopic[] | null>(null)
  const [rows, setRows] = useState<PortalEvent[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(0)
  const [pageSize, setPageSize] = useState(25)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const [entryOpen, setEntryOpen] = useState(false)
  const [editId, setEditId] = useState<string | null>(null)
  const [refreshKey, setRefreshKey] = useState(0)
  const [sheetMandates, setSheetMandates] = useState<Mandate[]>([])
  const [mandateDialogOpen, setMandateDialogOpen] = useState(false)

  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false)
  const [deletingEventId, setDeletingEventId] = useState<string | null>(null)
  const [deletingOccasion, setDeletingOccasion] = useState('')
  const [deleteBusy, setDeleteBusy] = useState(false)

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

  useEffect(() => {
    api.sheets(periodCtx.range).then(setSheets).catch(() => setSheets([]))
    api.visitTopics(periodCtx.range).then(setTopics).catch(() => setTopics([]))
  }, [periodCtx.range.fromIso, periodCtx.range.toIso])

  const filters = useMemo(() => ({
    program_code: program,
    unit_name: unit,
    search,
    date_from: periodCtx.range.fromIso,
    date_to: periodCtx.range.toIso,
    value_kind: valueKind,
    min_attendees: minAttendees,
    has_media: hasMedia ? '1' : '',
    occasion_class: occasionClass,
    sort,
  }), [program, unit, search, periodCtx.range.fromIso, periodCtx.range.toIso, valueKind, minAttendees, hasMedia, occasionClass, sort])

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

  const selectedSheet = sheets?.find((s) => s.code === program) ?? null
  const selectedTopic = topics?.find((t) => t.ref === program) ?? null
  const dimensionColumns = selectedSheet ? sheetDimensionColumns(selectedSheet) : []

  // مستندات ابلاغی شیت انتخاب‌شده (کارت شیت)
  useEffect(() => {
    if (!program) { setSheetMandates([]); return }
    let alive = true
    apiClient.sheetMeta(program)
      .then((meta) => { if (alive) setSheetMandates(meta.mandates ?? []) })
      .catch(() => { if (alive) setSheetMandates([]) })
    return () => { alive = false }
  }, [program, refreshKey])

  // سنجه‌های اختصاصی شیت از تعاریف فرم (spec) — هم‌مصدر با فرم ثبت
  const [dimColumns, setDimColumns] = useState<{ metric: string; label: string }[]>([])
  useEffect(() => {
    const ref = program || ''
    if (!ref) { setDimColumns([]); return }
    if (selectedSheet) { setDimColumns(sheetDimensionColumns(selectedSheet)); return }
    api.entryFormSpec(ref)
      .then((spec) => setDimColumns(spec.sections.flatMap((sec) =>
        sec.fields.filter((f) => f.t === 'number' && f.n.startsWith('dim_'))
          .map((f) => ({ metric: f.n.slice(4), label: f.l })))))
      .catch(() => setDimColumns([]))
  }, [program, selectedSheet])

  const columns = program === '' ? [] : dimColumns

  const table = isMobile ? (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
      {loading && rows.length === 0 && (
        Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} variant="rounded" height={100} sx={{ borderRadius: 2 }} />
        ))
      )}
      {!loading && rows.length === 0 && (
        <Paper sx={{ p: 4, textAlign: 'center', color: 'text.secondary', borderRadius: 2 }}>
          رویدادی در این دوره و فیلترها یافت نشد.
        </Paper>
      )}
      {rows.map((ev) => (
        <MobileEventCard
          key={ev.event_id}
          ev={ev}
          columns={columns}
          onEdit={() => { setEditId(ev.event_id); setEntryOpen(true) }}
          onDelete={handleDeleteRequest}
        />
      ))}
    </Box>
  ) : (
    <TableContainer component={Paper} sx={{ overflowX: 'auto' }}>
      <Table size="small" sx={{ minWidth: 900 }}>
        <TableHead>
          <TableRow>
            <TableCell>تاریخ</TableCell>
            <TableCell>حوزه قضایی</TableCell>
            <TableCell>مناسبت / رویداد</TableCell>
            <TableCell align="center">شرکت‌کنندگان</TableCell>
            {columns.map((c) => (
              <TableCell
                key={c.metric}
                align="center"
                sx={{
                  background: '#f1f5f9',
                  fontSize: 11,
                  fontWeight: 700,
                  minWidth: 90,
                  maxWidth: 130,
                  px: 1,
                  py: 1.2,
                  lineHeight: 1.4,
                  borderLeft: '1px solid #e2e8f0',
                }}
              >
                {c.label}
              </TableCell>
            ))}
            <TableCell align="center" sx={{ minWidth: 65 }}>رسانه</TableCell>
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
                fontWeight: 700,
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
            <TableRow><TableCell colSpan={7 + columns.length} align="center" sx={{ py: 5, color: 'text.secondary' }}>
              رویدادی در این دوره و فیلترها یافت نشد.
            </TableCell></TableRow>
          )}
          {rows.map((ev) => (
            <EventRow key={ev.event_id} ev={ev} columns={columns} isMobile={false}
              onEdit={() => { setEditId(ev.event_id); setEntryOpen(true) }}
              onDelete={handleDeleteRequest} />
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  )

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      {/* نوار فیلتر */}
      <Card>
        <CardContent sx={{ display: 'flex', flexWrap: 'wrap', gap: 1.5, alignItems: 'center' }}>
          <FormControl size="small" sx={{ minWidth: 220, flex: { md: 1.4 } }}>
            <InputLabel>محور گزارش</InputLabel>
            <Select label="محور گزارش" value={program} onChange={(e) => setProgram(e.target.value)}>
              <MenuItem value="">همهٔ محورها</MenuItem>
              {sheets?.map((s) => (
                <MenuItem key={s.code} value={s.code}>{faCode(s.code)} — {s.name} ({faNum(s.count)})</MenuItem>
              ))}
              {topics?.length ? <MenuItem disabled value="-">— کاربرگ بازدید استانی —</MenuItem> : null}
              {topics?.map((t) => (
                <MenuItem key={t.ref} value={t.ref}>{t.row_label} — {t.name} ({faNum(t.count)})</MenuItem>
              ))}
            </Select>
          </FormControl>

          <TextField size="small" label="جستجو (مناسبت، شرح، حوزه…)" value={search}
            onChange={(e) => setSearch(e.target.value)} sx={{ flex: { md: 1.6 }, minWidth: 200 }} />

          <TextField size="small" label="حداقل مخاطب" value={minAttendees}
            onChange={(e) => setMinAttendees(e.target.value)} sx={{ width: 120 }} />

          <FormControl size="small" sx={{ minWidth: 130 }}>
            <InputLabel>نوع آمار</InputLabel>
            <Select label="نوع آمار" value={valueKind} onChange={(e) => setValueKind(e.target.value)}>
              <MenuItem value="">همه</MenuItem>
              <MenuItem value="verified">قطعی</MenuItem>
              <MenuItem value="estimated">تخمینی</MenuItem>
            </Select>
          </FormControl>

          {program === '80403' && (
            <FormControl size="small" sx={{ minWidth: 130 }}>
              <InputLabel>ردهٔ مراسم</InputLabel>
              <Select label="ردهٔ مراسم" value={occasionClass} onChange={(e) => setOccasionClass(e.target.value)}>
                <MenuItem value="">همه</MenuItem>
                <MenuItem value="national">ملی</MenuItem>
                <MenuItem value="religious">مذهبی</MenuItem>
                <MenuItem value="revolutionary">انقلابی</MenuItem>
                <MenuItem value="standard">سایر</MenuItem>
              </Select>
            </FormControl>
          )}

          <FormControl size="small" sx={{ minWidth: 140 }}>
            <InputLabel>مرتب‌سازی</InputLabel>
            <Select label="مرتب‌سازی" value={sort} onChange={(e) => setSort(e.target.value)}>
              <MenuItem value="newest">جدیدترین</MenuItem>
              <MenuItem value="oldest">قدیمی‌ترین</MenuItem>
              <MenuItem value="attendees">بیشترین مخاطب</MenuItem>
            </Select>
          </FormControl>

          <Chip
            label="فقط دارای رسانه/سند"
            color={hasMedia ? 'primary' : 'default'}
            variant={hasMedia ? 'filled' : 'outlined'}
            onClick={() => setHasMedia(!hasMedia)}
          />

          <Button
            variant="contained" startIcon={<AddCircleIcon />}
            onClick={() => setEntryOpen(true)}
          >
            ثبت رویداد
          </Button>
        </CardContent>
      </Card>

      {error && <Alert severity="error">{error}</Alert>}

      {/* کارت شیت انتخاب‌شده: شرح عملیاتی، موازین پایش، چارچوب سیاستی */}
      {selectedSheet && (
        <Card>
          <CardContent sx={{ display: 'flex', flexDirection: 'column', gap: 1.2 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
              <ChipCode code={selectedSheet.code} />
              <Typography variant="subtitle1" sx={{ fontWeight: 800 }}>{selectedSheet.title}</Typography>
              <Chip size="small" color="success" variant="outlined" label={`${faNum(selectedSheet.count)} رویداد در دوره`} />
            </Box>
            {selectedSheet.policy_framework && (
              <Typography variant="body2" sx={{ background: '#fff7ed', border: '1px solid #fed7aa', borderRadius: 2, px: 1.5, py: 0.8, color: '#9a3412' }}>
                چارچوب سیاستی: {selectedSheet.policy_framework}
              </Typography>
            )}
            {selectedSheet.description && (
              <Typography variant="body2" sx={{ lineHeight: 2 }}>شرح عملیاتی: {selectedSheet.description}</Typography>
            )}
            {selectedSheet.monitoring_criteria.length > 0 && (
              <Box component="ul" sx={{ m: 0, pr: 2, columns: { md: 2 } }}>
                {selectedSheet.monitoring_criteria.map((c) => (
                  <Typography key={c} component="li" variant="body2" sx={{ lineHeight: 2 }}>{c}</Typography>
                ))}
              </Box>
            )}
            {/* مستندات ابلاغی همان شیت */}
            <Box sx={{ borderTop: '1px dashed #dbe4ee', pt: 1.2, mt: 0.5 }}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
                <Typography variant="subtitle2">
                  مستندات ابلاغی این برنامه ({faNum(sheetMandates.length)} سند)
                </Typography>
                <Button size="small" variant="outlined" onClick={() => setMandateDialogOpen(true)}>
                  ثبت مستند ابلاغی
                </Button>
              </Box>
              {sheetMandates.length === 0 ? (
                <Typography variant="caption" color="text.secondary">
                  هنوز سند ابلاغی برای این کد برنامه ثبت نشده است.
                </Typography>
              ) : (
                <Table size="small" aria-label="مستندات ابلاغی شیت">
                  <TableHead>
                    <TableRow>
                      <TableCell>نوع سند</TableCell>
                      <TableCell>عنوان</TableCell>
                      <TableCell>شماره</TableCell>
                      <TableCell>تاریخ ابلاغ</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {sheetMandates.map((md) => (
                      <TableRow key={md.mandate_id} hover>
                        <TableCell><Chip size="small" color="primary" variant="outlined"
                          label={MANDATE_KINDS[md.kind] ?? md.kind} /></TableCell>
                        <TableCell>
                          <strong>{md.title}</strong>
                          {md.notes && (
                            <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
                              {md.notes.slice(0, 110)}{md.notes.length > 110 ? '…' : ''}
                            </Typography>
                          )}
                        </TableCell>
                        <TableCell><code>{md.number || '—'}</code></TableCell>
                        <TableCell style={{ whiteSpace: 'nowrap' }}>{faDate(md.issued_on)}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </Box>
          </CardContent>
        </Card>
      )}
      {selectedTopic && (
        <Card>
          <CardContent sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <VisitChip label={selectedTopic.row_label} />
              <Typography variant="subtitle1" sx={{ fontWeight: 800 }}>{selectedTopic.title}</Typography>
              <Chip size="small" color="success" variant="outlined" label={`${faNum(selectedTopic.count)} رویداد در دوره`} />
            </Box>
            {selectedTopic.intro && (
              <Typography variant="body2" sx={{ lineHeight: 2 }}>{selectedTopic.intro}</Typography>
            )}
          </CardContent>
        </Card>
      )}

      {table}

      <TablePagination
        component="div"
        count={total}
        page={page}
        onPageChange={(_, p) => setPage(p)}
        rowsPerPage={pageSize}
        onRowsPerPageChange={(e) => { setPageSize(Number(e.target.value)); setPage(0) }}
        rowsPerPageOptions={[25, 50, 100]}
        labelRowsPerPage="سطر در صفحه:"
        labelDisplayedRows={({ from, to, count }) => `${faNum(from)}–${faNum(to)} از ${faNum(count)}`}
      />

      <EventEntryDialog
        open={entryOpen}
        initialRef={program}
        editEventId={editId}
        onClose={() => { setEntryOpen(false); setEditId(null) }}
        onSaved={() => {
          setEntryOpen(false)
          setEditId(null)
          notify(editId ? 'تغییرات رویداد ذخیره شد' : 'رویداد فرهنگی جدید در کارتابل ثبت شد', 'success')
          setPage(0)
          setRefreshKey((k) => k + 1)
        }}
      />
      <NewMandateDialog
        open={mandateDialogOpen}
        initialProgram={program || '80401'}
        onClose={() => setMandateDialogOpen(false)}
        onSaved={(title) => {
          setMandateDialogOpen(false)
          notify(`سند «${title}» ثبت شد`, 'success')
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

function NotesCell({ notes, onOpenEdit }: { notes: string; onOpenEdit: () => void }) {
  const [expanded, setExpanded] = useState(false)
  const isLong = notes.length > 90

  return (
    <Box sx={{ mt: 0.4 }}>
      <Typography
        variant="caption"
        color="text.secondary"
        sx={{
          display: 'block',
          lineHeight: 1.5,
          whiteSpace: expanded ? 'pre-wrap' : 'normal',
          cursor: isLong ? 'pointer' : 'default',
        }}
        onClick={() => isLong && setExpanded(!expanded)}
        title={isLong ? (expanded ? 'بستن متن کامل' : 'کلیک برای نمایش کامل متن در جدول') : ''}
      >
        {expanded || !isLong ? notes : `${notes.slice(0, 90)}…`}
      </Typography>
      {isLong && (
        <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', mt: 0.2 }}>
          <Typography
            component="span"
            variant="caption"
            onClick={() => setExpanded(!expanded)}
            sx={{
              fontSize: 10,
              color: 'primary.main',
              cursor: 'pointer',
              userSelect: 'none',
              fontWeight: 700,
              '&:hover': { textDecoration: 'underline' },
            }}
          >
            {expanded ? '▲ بستن متن' : '▼ نمایش کامل متن'}
          </Typography>
          <Typography
            component="span"
            variant="caption"
            onClick={onOpenEdit}
            sx={{
              fontSize: 10,
              color: 'text.secondary',
              cursor: 'pointer',
              userSelect: 'none',
              '&:hover': { color: 'primary.main', textDecoration: 'underline' },
            }}
          >
            (ویرایش / اصلاح)
          </Typography>
        </Box>
      )}
    </Box>
  )
}

function EventRow({
  ev, columns, isMobile, onEdit, onDelete,
}: {
  ev: PortalEvent
  columns: { metric: string; label: string }[]
  isMobile: boolean
  onEdit: () => void
  onDelete: (eventId: string, occasion: string) => void
}) {
  const attendees = ev.attendees_count
  const title = ev.occasion || 'برنامه فرهنگی'

  return (
    <TableRow hover>
      <TableCell sx={{ whiteSpace: 'nowrap' }}><code>{faDate(ev.occurred_on)}</code></TableCell>
      <TableCell><strong>{ev.unit_name || 'دادگستری کل مازندران'}</strong></TableCell>
      <TableCell sx={{ maxWidth: isMobile ? 220 : 380, minWidth: 260 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, flexWrap: 'wrap' }}>
          <Typography
            component="span"
            onClick={onEdit}
            sx={{
              fontWeight: 800,
              fontSize: 14,
              cursor: 'pointer',
              color: 'primary.main',
              display: 'inline-flex',
              alignItems: 'center',
              gap: 0.5,
              '&:hover': { textDecoration: 'underline', color: 'primary.dark' },
            }}
            title="کلیک برای مشاهده کامل محتوا و ویرایش گزارش"
          >
            {title}
          </Typography>
          {Number(ev.is_ashura_pilgrimage) === 1 && <Chip size="small" label="زیارت عاشورا" sx={{ mr: 0.5 }} />}
        </Box>
        {ev.notes && (
          <NotesCell notes={ev.notes} onOpenEdit={onEdit} />
        )}

        {/* دکمه‌های اقدام سریع و مستقیم — همیشه در دید کامل کاربر بدون نیاز به اسکرول افقی */}
        <Box sx={{ display: 'flex', gap: 1, mt: 1, alignItems: 'center', flexWrap: 'wrap' }}>
          <Button
            size="small"
            variant="outlined"
            color="primary"
            startIcon={<EditIcon sx={{ fontSize: '14px !important' }} />}
            onClick={onEdit}
            sx={{ py: 0.35, px: 1.2, fontSize: 11.5, fontWeight: 700, borderRadius: 1.5, whiteSpace: 'nowrap' }}
          >
            اصلاح رویداد
          </Button>
          <Button
            size="small"
            variant="outlined"
            color="error"
            startIcon={<DeleteOutlineIcon sx={{ fontSize: '14px !important' }} />}
            onClick={() => onDelete(ev.event_id, title)}
            sx={{ py: 0.35, px: 1, fontSize: 11.5, fontWeight: 700, borderRadius: 1.5, whiteSpace: 'nowrap' }}
          >
            حذف
          </Button>
        </Box>
      </TableCell>
      <TableCell align="center">
        {attendees !== null && attendees !== undefined ? (
          <Chip
            size="small"
            color={ev.attendees_value_kind === 'estimated' ? 'warning' : 'primary'}
            variant="outlined"
            label={`${faNum(attendees)} نفر${ev.attendees_value_kind === 'estimated' ? ' (تخمینی)' : ''}`}
          />
        ) : '—'}
      </TableCell>
      {columns.map((c) => {
        const v = ev.facts?.[c.metric]?.value ?? 0
        return (
          <TableCell
            key={c.metric}
            align="center"
            sx={{ minWidth: 90, maxWidth: 130, px: 1, borderLeft: '1px solid #f1f5f9' }}
          >
            {v > 0 ? (
              <Chip size="small" variant={v > 1 ? 'filled' : 'outlined'}
                color={v > 1 ? 'primary' : 'success'}
                label={v > 1 ? faNum(Math.round(v)) : '✓'} />
            ) : <span style={{ color: '#cbd5e1' }}>—</span>}
          </TableCell>
        )
      })}
      <TableCell align="center" sx={{ minWidth: 65 }}>{ev.media_count > 0 ? faNum(ev.media_count) : '—'}</TableCell>
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
              onClick={onEdit}
              startIcon={<EditIcon sx={{ fontSize: '13px !important' }} />}
              sx={{ minWidth: 0, px: 1.2, py: 0.35, fontSize: 11.5, fontWeight: 700, whiteSpace: 'nowrap' }}
            >
              اصلاح رویداد
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
}

function MobileEventCard({
  ev, columns, onEdit, onDelete,
}: {
  ev: PortalEvent
  columns: { metric: string; label: string }[]
  onEdit: () => void
  onDelete: (eventId: string, occasion: string) => void
}) {
  const attendees = ev.attendees_count
  const title = ev.occasion || 'برنامه فرهنگی'
  const activeMetrics = columns.filter((c) => (ev.facts?.[c.metric]?.value ?? 0) > 0)

  return (
    <Card variant="outlined" sx={{ borderRadius: 2, background: '#ffffff', boxShadow: '0 1px 3px rgba(0,0,0,0.05)' }}>
      <CardContent sx={{ p: 2, '&:last-child': { pb: 2 } }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 1, mb: 1.2 }}>
          <Box sx={{ flex: 1, minWidth: 160 }}>
            <Typography variant="subtitle2" sx={{ fontWeight: 800, fontSize: 14.5 }}>
              {title}
            </Typography>
            <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block', mt: 0.3 }}>
              {ev.unit_name || 'دادگستری کل مازندران'}
            </Typography>
          </Box>
          <Box sx={{ display: 'flex', gap: 0.8, alignItems: 'center', flexShrink: 0 }}>
            <Button
              size="small"
              variant="outlined"
              color="primary"
              onClick={onEdit}
              startIcon={<EditIcon sx={{ fontSize: '14px !important' }} />}
              sx={{ py: 0.35, px: 1.2, fontSize: 11.5, fontWeight: 700, borderRadius: 1.5, whiteSpace: 'nowrap' }}
            >
              اصلاح رویداد
            </Button>
            <Button
              size="small"
              variant="outlined"
              color="error"
              onClick={() => onDelete(ev.event_id, title)}
              startIcon={<DeleteOutlineIcon sx={{ fontSize: '14px !important' }} />}
              sx={{ py: 0.35, px: 1, fontSize: 11.5, fontWeight: 700, borderRadius: 1.5, whiteSpace: 'nowrap' }}
            >
              حذف
            </Button>
          </Box>
        </Box>

        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.8, alignItems: 'center', mb: 1 }}>
          <Chip size="small" label={faDate(ev.occurred_on)} variant="outlined" sx={{ fontSize: 11.5 }} />
          {attendees !== null && attendees !== undefined && (
            <Chip
              size="small"
              color={ev.attendees_value_kind === 'estimated' ? 'warning' : 'primary'}
              variant="outlined"
              label={`${faNum(attendees)} نفر${ev.attendees_value_kind === 'estimated' ? ' (تخمینی)' : ''}`}
              sx={{ fontSize: 11.5 }}
            />
          )}
          {Number(ev.is_ashura_pilgrimage) === 1 && (
            <Chip size="small" label="زیارت عاشورا" color="info" sx={{ fontSize: 11.5 }} />
          )}
          {ev.media_count > 0 && (
            <Chip size="small" label={`${faNum(ev.media_count)} رسانه`} variant="outlined" sx={{ fontSize: 11 }} />
          )}
        </Box>

        {ev.notes && (
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1, lineHeight: 1.6 }}>
            {ev.notes.slice(0, 110)}{ev.notes.length > 110 ? '…' : ''}
          </Typography>
        )}

        {activeMetrics.length > 0 && (
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.6, pt: 1, borderTop: '1px dashed #e2e8f0' }}>
            {activeMetrics.map((c) => {
              const v = ev.facts?.[c.metric]?.value ?? 0
              return (
                <Chip
                  key={c.metric}
                  size="small"
                  color="success"
                  variant="outlined"
                  label={`${c.label}: ${faNum(Math.round(v))}`}
                  sx={{ fontSize: 11, background: '#f0fdf4' }}
                />
              )
            })}
          </Box>
        )}
      </CardContent>
    </Card>
  )
}

/** ستون‌های اختصاصی شیت از سؤالات متصل به فکت (auto_from) — بدون attendees/event_count */
function sheetDimensionColumns(sheet: ProgramSheet): { metric: string; label: string }[] {
  return sheet.questions
    .filter((q) => q.auto_from && q.auto_from !== 'attendees' && q.auto_from !== 'event_count')
    .map((q) => ({ metric: q.auto_from, label: q.label }))
}
