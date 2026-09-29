import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  Alert, Box, Button, Card, CardContent, Chip, FormControl, Grid, InputLabel,
  MenuItem, Paper, Select, Skeleton, Table, TableBody, TableCell, TableHead,
  TableContainer, TablePagination, TableRow, TextField, Typography, useMediaQuery,
  useTheme,
} from '@mui/material'
import FilterAltIcon from '@mui/icons-material/FilterAlt'
import AddCircleIcon from '@mui/icons-material/AddCircle'
import { api, PROGRAM_REFS, type PortalEvent, type ProgramSheet, type VisitTopic } from '../api'
import { usePeriod } from '../components/PeriodPicker'
import { faCode, faNum } from '../periods'
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

  const table = (
    <TableContainer component={Paper} sx={{ overflowX: 'auto' }}>
      <Table size="small" sx={{ minWidth: isMobile ? 640 : 900 }}>
        <TableHead>
          <TableRow>
            <TableCell>تاریخ</TableCell>
            <TableCell>حوزه قضایی</TableCell>
            <TableCell>مناسبت / رویداد</TableCell>
            <TableCell align="center">شرکت‌کنندگان</TableCell>
            {columns.map((c) => (
              <TableCell key={c.metric} align="center" sx={{ background: '#f1f5f9', fontSize: 10.5 }}>
                {c.label}
              </TableCell>
            ))}
            <TableCell align="center">رسانه</TableCell>
            <TableCell align="center">عملیات</TableCell>
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
            <EventRow key={ev.event_id} ev={ev} columns={columns} isMobile={isMobile}
              onEdit={() => { setEditId(ev.event_id); setEntryOpen(true) }} />
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
                        <TableCell style={{ whiteSpace: 'nowrap' }}>{md.issued_on || '—'}</TableCell>
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
    </Box>
  )
}

function EventRow({ ev, columns, isMobile, onEdit }: { ev: PortalEvent; columns: { metric: string; label: string }[]; isMobile: boolean; onEdit: () => void }) {
  const attendees = ev.attendees_count
  return (
    <TableRow hover>
      <TableCell sx={{ whiteSpace: 'nowrap' }}><code>{faNum(ev.occurred_on)}</code></TableCell>
      <TableCell><strong>{ev.unit_name || 'دادگستری کل مازندران'}</strong></TableCell>
      <TableCell sx={{ maxWidth: isMobile ? 200 : 340 }}>
        <strong>{ev.occasion || 'برنامه فرهنگی'}</strong>
        {Number(ev.is_ashura_pilgrimage) === 1 && <Chip size="small" label="زیارت عاشورا" sx={{ mr: 1 }} />}
        {ev.notes && (
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.3, whiteSpace: 'normal' }}>
            {ev.notes.slice(0, 90)}{ev.notes.length > 90 ? '…' : ''}
          </Typography>
        )}
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
          <TableCell key={c.metric} align="center">
            {v > 0 ? (
              <Chip size="small" variant={v > 1 ? 'filled' : 'outlined'}
                color={v > 1 ? 'primary' : 'success'}
                label={v > 1 ? faNum(Math.round(v)) : '✓'} />
            ) : <span style={{ color: '#cbd5e1' }}>—</span>}
          </TableCell>
        )
      })}
      <TableCell align="center">{ev.media_count > 0 ? faNum(ev.media_count) : '—'}</TableCell>
      <TableCell align="center">
        <Button size="small" variant="outlined" onClick={onEdit} sx={{ minWidth: 0, px: 1 }}>
          ویرایش
        </Button>
        <Typography variant="caption" sx={{ display: 'block', direction: 'ltr', fontSize: 9.5, color: 'text.disabled' }}>
          {ev.event_id}
        </Typography>
      </TableCell>
    </TableRow>
  )
}

/** ستون‌های اختصاصی شیت از سؤالات متصل به فکت (auto_from) — بدون attendees/event_count */
function sheetDimensionColumns(sheet: ProgramSheet): { metric: string; label: string }[] {
  return sheet.questions
    .filter((q) => q.auto_from && q.auto_from !== 'attendees' && q.auto_from !== 'event_count')
    .map((q) => ({ metric: q.auto_from, label: q.label }))
}
