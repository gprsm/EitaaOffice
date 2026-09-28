import { useEffect, useState } from 'react'
import {
  Alert, Box, Button, Card, CardContent, LinearProgress, Table, TableBody,
  TableCell, TableContainer, TableHead, TablePagination, TableRow, TextField,
  Typography, Paper,
} from '@mui/material'
import { api, type DistrictRow } from '../api'
import { usePeriod } from '../components/PeriodPicker'
import { faNum } from '../periods'

/** ماتریس شهرستان‌ها — آمار مشارکت حوزه‌ها در دورهٔ انتخاب‌شده (F-097) */
export default function DistrictsPage() {
  const { range } = usePeriod()
  const [search, setSearch] = useState('')
  const [rows, setRows] = useState<DistrictRow[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(0)
  const [pageSize, setPageSize] = useState(15)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [totalEvents, setTotalEvents] = useState(0)

  useEffect(() => { setPage(0) }, [range.fromIso, range.toIso, search])

  useEffect(() => {
    let alive = true
    setLoading(true)
    api.districts(range, search, pageSize, page * pageSize)
      .then((res) => {
        if (!alive) return
        setRows(res.rows)
        setTotal(res.total)
        setError('')
        if (page === 0 && !search) {
          setTotalEvents(res.rows.reduce((sum, r) => sum + r.total_events, 0))
        }
      })
      .catch((err) => alive && setError(err instanceof Error ? err.message : 'خطا در دریافت حوزه‌ها'))
      .finally(() => alive && setLoading(false))
    return () => { alive = false }
  }, [range.fromIso, range.toIso, search, page, pageSize])

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      <Card>
        <CardContent sx={{ display: 'flex', gap: 1.5, flexWrap: 'wrap', alignItems: 'center' }}>
          <TextField size="small" label="جستجوی حوزه قضایی" value={search}
            onChange={(e) => setSearch(e.target.value)} sx={{ flex: 1, minWidth: 220 }} />
        </CardContent>
      </Card>

      {error && <Alert severity="error">{error}</Alert>}
      {loading && rows.length === 0 && <LinearProgress />}

      <TableContainer component={Paper}>
        <Table size="small" sx={{ minWidth: 720 }}>
          <TableHead>
            <TableRow>
              <TableCell>رتبه</TableCell>
              <TableCell>حوزه قضایی</TableCell>
              <TableCell align="center">رویدادهای دوره</TableCell>
              <TableCell align="center">سهم از استان</TableCell>
              <TableCell align="center">تنوع برنامه‌ها</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {rows.map((d, i) => {
              const percent = totalEvents > 0 ? Math.round((d.total_events / totalEvents) * 1000) / 10 : 0
              return (
                <TableRow key={d.unit_name} hover>
                  <TableCell><strong>{faNum(page * pageSize + i + 1)}</strong></TableCell>
                  <TableCell><strong>{d.unit_name}</strong></TableCell>
                  <TableCell align="center">{faNum(d.total_events)}</TableCell>
                  <TableCell align="center">{faNum(percent)}٪</TableCell>
                  <TableCell align="center">{faNum(d.program_variety)}</TableCell>
                </TableRow>
              )
            })}
            {rows.length === 0 && !loading && (
              <TableRow><TableCell colSpan={5} align="center" sx={{ py: 4, color: 'text.secondary' }}>
                حوزه‌ای یافت نشد.
              </TableCell></TableRow>
            )}
          </TableBody>
        </Table>
      </TableContainer>

      <TablePagination
        component="div"
        count={total}
        page={page}
        onPageChange={(_, p) => setPage(p)}
        rowsPerPage={pageSize}
        onRowsPerPageChange={(e) => { setPageSize(Number(e.target.value)); setPage(0) }}
        rowsPerPageOptions={[15, 30, 50]}
        labelRowsPerPage="سطر در صفحه:"
        labelDisplayedRows={({ from, to, count }) => `${faNum(from)}–${faNum(to)} از ${faNum(count)}`}
      />
    </Box>
  )
}

