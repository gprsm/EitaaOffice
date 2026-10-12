import { useEffect, useState, useMemo, useCallback } from 'react'
import {
  Box,
  Button,
  ButtonGroup,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Grid,
  IconButton,
  LinearProgress,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Tooltip,
  Typography,
  useMediaQuery,
  useTheme,
} from '@mui/material'
import CloseRounded from '@mui/icons-material/CloseRounded'
import RefreshRounded from '@mui/icons-material/RefreshRounded'
import AssessmentRounded from '@mui/icons-material/AssessmentRounded'
import CheckCircleOutlineRounded from '@mui/icons-material/CheckCircleOutlineRounded'
import WarningAmberRounded from '@mui/icons-material/WarningAmberRounded'
import AssignmentTurnedInRounded from '@mui/icons-material/AssignmentTurnedInRounded'
import PeopleAltRounded from '@mui/icons-material/PeopleAltRounded'
import type { StaffPerformanceItem, StaffPerformanceSummary } from './lib/types'
import { api } from './lib/api'

type Props = {
  open: boolean
  onClose: () => void
}

type Period = '1m' | '2m' | '6m' | '12m' | 'all'

export function StaffPerformanceDialog({ open, onClose }: Props) {
  const theme = useTheme()
  const fullScreen = useMediaQuery(theme.breakpoints.down('md'))
  const [period, setPeriod] = useState<Period>('2m')
  const [loading, setLoading] = useState(false)
  const [summary, setSummary] = useState<StaffPerformanceSummary | null>(null)
  const [staffList, setStaffList] = useState<StaffPerformanceItem[]>([])

  const dateRange = useMemo(() => {
    if (period === 'all') return { from: '', to: '' }
    const now = new Date()
    const days = period === '1m' ? 30 : period === '2m' ? 60 : period === '6m' ? 180 : 365
    const past = new Date(now.getTime() - days * 24 * 60 * 60 * 1000)
    return {
      from: past.toISOString(),
      to: now.toISOString(),
    }
  }, [period])

  const loadData = useCallback(async () => {
    setLoading(true)
    try {
      const queryParams = new URLSearchParams()
      if (dateRange.from) queryParams.set('from_date', dateRange.from)
      if (dateRange.to) queryParams.set('to_date', dateRange.to)
      const res = await api<{
        ok: boolean
        summary: StaffPerformanceSummary
        staff: StaffPerformanceItem[]
      }>('GET', `/api/v2/staff/performance?${queryParams.toString()}`)
      if (res.ok) {
        setSummary(res.summary)
        setStaffList(res.staff || [])
      }
    } catch {
      // Fallback empty
      setStaffList([])
    } finally {
      setLoading(false)
    }
  }, [dateRange])

  useEffect(() => {
    if (open) {
      void loadData()
    }
  }, [open, loadData])

  return (
    <Dialog
      open={open}
      onClose={onClose}
      fullScreen={fullScreen}
      maxWidth="lg"
      fullWidth
      aria-labelledby="staff-performance-title"
    >
      <DialogTitle id="staff-performance-title" sx={{ pb: 1 }}>
        <Stack direction="row" alignItems="center" justifyContent="space-between">
          <Stack direction="row" spacing={1.5} alignItems="center">
            <AssessmentRounded color="primary" />
            <Box>
              <Typography variant="h6" fontWeight={800}>
                ارزیابی عملکرد و دقت کارمندان در ایندکس‌گذاری
              </Typography>
              <Typography variant="caption" color="text.secondary">
                سنجش میزان مشارکت، تصحیحات و نظارت مدیر بر درستی کار کارمندان
              </Typography>
            </Box>
          </Stack>
          <Stack direction="row" spacing={1} alignItems="center">
            <IconButton onClick={loadData} disabled={loading} size="small" title="بارگذاری مجدد">
              <RefreshRounded />
            </IconButton>
            <IconButton onClick={onClose} size="small">
              <CloseRounded />
            </IconButton>
          </Stack>
        </Stack>
      </DialogTitle>

      <DialogContent dividers sx={{ bgcolor: 'background.default', p: { xs: 1.5, sm: 2.5 } }}>
        <Stack spacing={2.5}>
          {/* Period selector */}
          <Paper variant="outlined" sx={{ p: 1.5, display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 1 }}>
            <Typography variant="body2" fontWeight={700}>
              بازه زمانی سنجش عملکرد:
            </Typography>
            <ButtonGroup size="small" variant="outlined">
              <Button
                variant={period === '1m' ? 'contained' : 'outlined'}
                onClick={() => setPeriod('1m')}
              >
                ۱ ماهه
              </Button>
              <Button
                variant={period === '2m' ? 'contained' : 'outlined'}
                onClick={() => setPeriod('2m')}
              >
                ۲ ماهه
              </Button>
              <Button
                variant={period === '6m' ? 'contained' : 'outlined'}
                onClick={() => setPeriod('6m')}
              >
                ۶ ماهه
              </Button>
              <Button
                variant={period === '12m' ? 'contained' : 'outlined'}
                onClick={() => setPeriod('12m')}
              >
                ۱ ساله
              </Button>
              <Button
                variant={period === 'all' ? 'contained' : 'outlined'}
                onClick={() => setPeriod('all')}
              >
                کل تاریخچه
              </Button>
            </ButtonGroup>
          </Paper>

          {/* Summary KPIs */}
          {summary && (
            <Grid container spacing={2}>
              <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                <Card variant="outlined">
                  <CardContent sx={{ p: 2, '&:last-child': { pb: 2 } }}>
                    <Stack direction="row" spacing={1.5} alignItems="center">
                      <PeopleAltRounded color="primary" sx={{ fontSize: 32 }} />
                      <Box>
                        <Typography variant="caption" color="text.secondary">
                          تعداد کاربران فعال
                        </Typography>
                        <Typography variant="h6" fontWeight={800}>
                          {summary.total_staff.toLocaleString('fa-IR')} نفر
                        </Typography>
                      </Box>
                    </Stack>
                  </CardContent>
                </Card>
              </Grid>

              <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                <Card variant="outlined">
                  <CardContent sx={{ p: 2, '&:last-child': { pb: 2 } }}>
                    <Stack direction="row" spacing={1.5} alignItems="center">
                      <CheckCircleOutlineRounded color="success" sx={{ fontSize: 32 }} />
                      <Box>
                        <Typography variant="caption" color="text.secondary">
                          کل عملیات ایندکس
                        </Typography>
                        <Typography variant="h6" fontWeight={800}>
                          {summary.total_actions.toLocaleString('fa-IR')} عمل
                        </Typography>
                      </Box>
                    </Stack>
                  </CardContent>
                </Card>
              </Grid>

              <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                <Card variant="outlined">
                  <CardContent sx={{ p: 2, '&:last-child': { pb: 2 } }}>
                    <Stack direction="row" spacing={1.5} alignItems="center">
                      <WarningAmberRounded
                        color={summary.average_accuracy >= 85 ? 'success' : 'warning'}
                        sx={{ fontSize: 32 }}
                      />
                      <Box sx={{ width: '100%' }}>
                        <Typography variant="caption" color="text.secondary">
                          میانگین صحت کارمندان
                        </Typography>
                        <Typography variant="h6" fontWeight={800}>
                          {summary.average_accuracy.toLocaleString('fa-IR')}٪
                        </Typography>
                        <LinearProgress
                          variant="determinate"
                          value={Math.min(100, summary.average_accuracy)}
                          color={summary.average_accuracy >= 85 ? 'success' : 'warning'}
                          sx={{ height: 6, borderRadius: 3, mt: 0.5 }}
                        />
                      </Box>
                    </Stack>
                  </CardContent>
                </Card>
              </Grid>

              <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                <Card variant="outlined">
                  <CardContent sx={{ p: 2, '&:last-child': { pb: 2 } }}>
                    <Stack direction="row" spacing={1.5} alignItems="center">
                      <AssignmentTurnedInRounded color="info" sx={{ fontSize: 32 }} />
                      <Box>
                        <Typography variant="caption" color="text.secondary">
                          وظایف نقص رفع‌شده
                        </Typography>
                        <Typography variant="h6" fontWeight={800}>
                          {summary.resolved_tasks.toLocaleString('fa-IR')} از {summary.total_tasks.toLocaleString('fa-IR')}
                        </Typography>
                      </Box>
                    </Stack>
                  </CardContent>
                </Card>
              </Grid>
            </Grid>
          )}

          {/* Staff table */}
          {loading ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}>
              <CircularProgress />
            </Box>
          ) : staffList.length === 0 ? (
            <Paper variant="outlined" sx={{ p: 5, textAlign: 'center' }}>
              <Typography color="text.secondary">
                هیچ رکورد فعالیتی در این بازه زمانی یافت نشد.
              </Typography>
            </Paper>
          ) : (
            <TableContainer component={Paper} variant="outlined">
              <Table size="small">
                <TableHead sx={{ bgcolor: 'action.hover' }}>
                  <TableRow>
                    <TableCell sx={{ fontWeight: 800 }}>کارمند / مسئول</TableCell>
                    <TableCell align="center">نقش</TableCell>
                    <TableCell align="center">کل عملیات</TableCell>
                    <TableCell align="center">پذیرش</TableCell>
                    <TableCell align="center">اصلاح مدیر (نقص)</TableCell>
                    <TableCell align="center">درصد دقت</TableCell>
                    <TableCell align="center">وظایف محوله</TableCell>
                    <TableCell align="center">وظایف حل‌شده</TableCell>
                    <TableCell align="center">نرخ رفع وظایف</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {staffList.map((staff) => {
                    const isAccurate = staff.accuracy_rate >= 90
                    const isWarning = staff.accuracy_rate >= 75 && staff.accuracy_rate < 90
                    const color = isAccurate ? 'success' : isWarning ? 'warning' : 'error'
                    return (
                      <TableRow key={staff.operator_id} hover>
                        <TableCell>
                          <Typography variant="body2" fontWeight={700}>
                            {staff.operator_name || staff.operator_id}
                          </Typography>
                        </TableCell>
                        <TableCell align="center">
                          <Chip
                            size="small"
                            variant="outlined"
                            label={staff.operator_role === 'admin' ? 'مدیر' : 'کارمند'}
                            color={staff.operator_role === 'admin' ? 'primary' : 'default'}
                          />
                        </TableCell>
                        <TableCell align="center" sx={{ fontWeight: 700 }}>
                          {staff.total_actions.toLocaleString('fa-IR')}
                        </TableCell>
                        <TableCell align="center">
                          {staff.accept_count.toLocaleString('fa-IR')}
                        </TableCell>
                        <TableCell align="center">
                          <Typography
                            variant="body2"
                            color={staff.override_count > 0 ? 'error.main' : 'text.secondary'}
                            fontWeight={staff.override_count > 0 ? 800 : 400}
                          >
                            {staff.override_count.toLocaleString('fa-IR')}
                          </Typography>
                        </TableCell>
                        <TableCell align="center">
                          <Chip
                            size="small"
                            color={color}
                            variant="filled"
                            label={`${staff.accuracy_rate.toLocaleString('fa-IR')}٪`}
                            sx={{ fontWeight: 800 }}
                          />
                        </TableCell>
                        <TableCell align="center">
                          {staff.assigned_tasks.toLocaleString('fa-IR')}
                        </TableCell>
                        <TableCell align="center">
                          {staff.resolved_tasks.toLocaleString('fa-IR')}
                        </TableCell>
                        <TableCell align="center">
                          <Typography variant="body2" fontWeight={700}>
                            {staff.task_resolution_rate.toLocaleString('fa-IR')}٪
                          </Typography>
                        </TableCell>
                      </TableRow>
                    )
                  })}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </Stack>
      </DialogContent>

      <DialogActions sx={{ px: 2.5, py: 1.5 }}>
        <Button onClick={onClose} variant="outlined">
          بستن
        </Button>
      </DialogActions>
    </Dialog>
  )
}
