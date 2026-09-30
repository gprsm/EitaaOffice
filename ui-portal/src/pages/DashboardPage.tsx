import { useEffect, useState } from 'react'
import {
  Alert, Box, Button, Card, CardContent, Chip, Grid, Skeleton, Table, TableBody,
  TableCell, TableContainer, TableHead, TableRow, Tooltip, Typography,
} from '@mui/material'
import EventAvailableIcon from '@mui/icons-material/EventAvailable'
import GroupsIcon from '@mui/icons-material/Groups'
import LocationCityIcon from '@mui/icons-material/LocationCity'
import FactCheckIcon from '@mui/icons-material/FactCheck'
import ArrowBackIcon from '@mui/icons-material/ArrowBack'
import { api, type Kpis, type ProgramSheet, type VisitTopic } from '../api'
import { usePeriod } from '../components/PeriodPicker'
import { faCode, faNum } from '../periods'
import type { PageProps } from '../App'

/** داشبورد کلان — تمام شاخص‌ها تابع دورهٔ انتخاب‌شده در نوار بالا هستند (F-097) */
export default function DashboardPage({ notify, navigateTo }: PageProps) {
  const { range } = usePeriod()
  const [kpis, setKpis] = useState<Kpis | null>(null)
  const [sheets, setSheets] = useState<ProgramSheet[] | null>(null)
  const [topics, setTopics] = useState<VisitTopic[] | null>(null)
  const [error, setError] = useState('')

  const handleSelectSheet = (code: string) => {
    if (navigateTo) {
      navigateTo(`sheet/${code}`)
    } else {
      window.location.hash = `/sheet/${code}`
    }
  }

  useEffect(() => {
    let alive = true
    setError('')
    Promise.all([api.kpis(range), api.sheets(range), api.visitTopics(range)])
      .then(([k, s, t]) => {
        if (!alive) return
        setKpis(k)
        setSheets(s)
        setTopics(t)
      })
      .catch((err) => {
        if (!alive) return
        setError(err instanceof Error ? err.message : 'خطا در دریافت شاخص‌ها')
        notify('خطا در دریافت شاخص‌های دوره', 'error')
      })
    return () => { alive = false }
  }, [range.fromIso, range.toIso])

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2.5 }}>
      {error && <Alert severity="error">{error}</Alert>}

      <Grid container spacing={2}>
        {[
          { icon: <EventAvailableIcon />, label: 'کل رویدادهای دوره', value: kpis?.total_events },
          { icon: <GroupsIcon />, label: 'مجموع شرکت‌کنندگان', value: kpis?.total_attendees },
          { icon: <LocationCityIcon />, label: 'حوزه‌های فعال', value: kpis?.active_districts },
          { icon: <FactCheckIcon />, label: 'فکت‌های ثبت‌شده', value: kpis?.total_facts },
        ].map((card) => (
          <Grid size={{ xs: 12, sm: 6, md: 3 }} key={card.label}>
            <Card>
              <CardContent sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                <Box sx={{ color: 'primary.main' }}>{card.icon}</Box>
                <Box>
                  <Typography variant="caption" color="text.secondary">{card.label}</Typography>
                  <Typography variant="h6" sx={{ fontWeight: 800 }}>
                    {card.value === undefined ? <Skeleton width={56} /> : faNum(card.value)}
                  </Typography>
                </Box>
              </CardContent>
            </Card>
          </Grid>
        ))}
      </Grid>

      <SheetStatusTable sheets={sheets} onSelectSheet={handleSelectSheet} />
      <VisitTopicsTable topics={topics} onSelectSheet={handleSelectSheet} />
    </Box>
  )
}

function SheetStatusTable({
  sheets,
  onSelectSheet,
}: {
  sheets: ProgramSheet[] | null
  onSelectSheet: (code: string) => void
}) {
  return (
    <Card sx={{ borderRadius: 2.5, boxShadow: '0 2px 10px rgba(0,0,0,0.03)' }}>
      <CardContent>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1, flexWrap: 'wrap', gap: 1 }}>
          <Box>
            <Typography variant="h6" sx={{ fontWeight: 800 }}>
              وضعیت شیت‌های کاربرگ رسمی ۱۴۰۵ (برای دورهٔ انتخاب‌شده)
            </Typography>
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.2 }}>
              برای مشاهده تمام رویدادهای هر شیت بر اساس بازهٔ فعال، روی ردیف شیت یا دکمهٔ «مشاهده رویدادها» کلیک کنید.
            </Typography>
          </Box>
        </Box>
        <TableContainer>
          <Table size="small">
            <TableHead>
              <TableRow sx={{ bgcolor: '#f8fafc' }}>
                <TableCell sx={{ fontWeight: 800 }}>کد رسمی برنامه</TableCell>
                <TableCell sx={{ fontWeight: 800 }}>عنوان شیت</TableCell>
                <TableCell align="center" sx={{ fontWeight: 800 }}>رویدادهای دوره</TableCell>
                <TableCell align="center" sx={{ fontWeight: 800 }}>شرکت‌کنندگان</TableCell>
                <TableCell sx={{ fontWeight: 800 }}>شرح عملیاتی (خلاصه)</TableCell>
                <TableCell align="center" sx={{ fontWeight: 800, minWidth: 140 }}>عملیات</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {sheets === null && (
                Array.from({ length: 8 }).map((_, i) => (
                  <TableRow key={i}><TableCell colSpan={6}><Skeleton /></TableCell></TableRow>
                ))
              )}
              {sheets?.map((s) => (
                <Tooltip key={s.code} title={`مشاهده رویدادهای شیت ${s.name} (${s.title})`} arrow placement="top">
                  <TableRow
                    hover
                    onClick={() => onSelectSheet(s.code)}
                    sx={{
                      cursor: 'pointer',
                      transition: 'all 0.15s ease-in-out',
                      '&:hover': {
                        backgroundColor: 'rgba(30, 58, 138, 0.05) !important',
                      },
                    }}
                  >
                    <TableCell><ChipCode code={s.code} /></TableCell>
                    <TableCell>
                      <Typography
                        variant="body2"
                        component="span"
                        sx={{
                          fontWeight: 800,
                          color: 'primary.main',
                          '&:hover': { textDecoration: 'underline' },
                        }}
                      >
                        {s.name}
                      </Typography>
                      {' — '}
                      <span style={{ color: '#64748b' }}>{s.title}</span>
                    </TableCell>
                    <TableCell align="center">
                      <Chip
                        size="small"
                        label={faNum(s.count)}
                        color={s.count > 0 ? 'primary' : 'default'}
                        variant={s.count > 0 ? 'filled' : 'outlined'}
                        sx={{ fontWeight: 800, minWidth: 40 }}
                      />
                    </TableCell>
                    <TableCell align="center">{s.attendees > 0 ? faNum(s.attendees) : '—'}</TableCell>
                    <TableCell sx={{ maxWidth: 360, fontSize: 12, color: '#475569' }}>
                      {s.description ? s.description.slice(0, 125) + (s.description.length > 125 ? '…' : '') : '—'}
                    </TableCell>
                    <TableCell align="center">
                      <Button
                        size="small"
                        variant="contained"
                        color="primary"
                        endIcon={<ArrowBackIcon sx={{ fontSize: '15px !important' }} />}
                        onClick={(e) => {
                          e.stopPropagation()
                          onSelectSheet(s.code)
                        }}
                        sx={{
                          fontSize: 11.5,
                          fontWeight: 700,
                          py: 0.35,
                          px: 1.3,
                          borderRadius: 1.5,
                          boxShadow: 'none',
                          whiteSpace: 'nowrap',
                          '&:hover': { boxShadow: '0 2px 8px rgba(30, 58, 138, 0.25)' },
                        }}
                      >
                        مشاهده رویدادها
                      </Button>
                    </TableCell>
                  </TableRow>
                </Tooltip>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      </CardContent>
    </Card>
  )
}

function VisitTopicsTable({
  topics,
  onSelectSheet,
}: {
  topics: VisitTopic[] | null
  onSelectSheet: (code: string) => void
}) {
  return (
    <Card sx={{ borderRadius: 2.5, boxShadow: '0 2px 10px rgba(0,0,0,0.03)' }}>
      <CardContent>
        <Box sx={{ mb: 1 }}>
          <Typography variant="h6" sx={{ fontWeight: 800 }}>
            موضوعات تکمیلی کاربرگ بازدید استانی (ردیف‌های ۲، ۴، ۶، ۸ و ۹ سند رسمی)
          </Typography>
          <Typography variant="caption" color="text.secondary">
            روی هر موضوع کلیک کنید تا تمام رویدادهای ثبت‌شده در این بازه را مشاهده نمایید.
          </Typography>
        </Box>
        <TableContainer>
          <Table size="small">
            <TableHead>
              <TableRow sx={{ bgcolor: '#f8fafc' }}>
                <TableCell sx={{ fontWeight: 800 }}>ردیف سند</TableCell>
                <TableCell sx={{ fontWeight: 800 }}>عنوان موضوع</TableCell>
                <TableCell align="center" sx={{ fontWeight: 800 }}>رویدادهای دوره</TableCell>
                <TableCell align="center" sx={{ fontWeight: 800 }}>شرکت‌کنندگان</TableCell>
                <TableCell align="center" sx={{ fontWeight: 800, minWidth: 140 }}>عملیات</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {topics === null && (
                Array.from({ length: 5 }).map((_, i) => (
                  <TableRow key={i}><TableCell colSpan={5}><Skeleton /></TableCell></TableRow>
                ))
              )}
              {topics?.map((t) => (
                <Tooltip key={t.ref} title={`مشاهده رویدادهای موضوع ${t.title}`} arrow placement="top">
                  <TableRow
                    hover
                    onClick={() => onSelectSheet(t.ref)}
                    sx={{
                      cursor: 'pointer',
                      transition: 'all 0.15s ease-in-out',
                      '&:hover': {
                        backgroundColor: 'rgba(30, 58, 138, 0.05) !important',
                      },
                    }}
                  >
                    <TableCell><VisitChip label={t.row_label} /></TableCell>
                    <TableCell>
                      <Typography
                        variant="body2"
                        component="span"
                        sx={{
                          fontWeight: 800,
                          color: 'primary.main',
                          '&:hover': { textDecoration: 'underline' },
                        }}
                      >
                        {t.title}
                      </Typography>
                    </TableCell>
                    <TableCell align="center">
                      <Chip
                        size="small"
                        label={faNum(t.count)}
                        color={t.count > 0 ? 'primary' : 'default'}
                        variant={t.count > 0 ? 'filled' : 'outlined'}
                        sx={{ fontWeight: 800, minWidth: 40 }}
                      />
                    </TableCell>
                    <TableCell align="center">{t.attendees > 0 ? faNum(t.attendees) : '—'}</TableCell>
                    <TableCell align="center">
                      <Button
                        size="small"
                        variant="contained"
                        color="primary"
                        endIcon={<ArrowBackIcon sx={{ fontSize: '15px !important' }} />}
                        onClick={(e) => {
                          e.stopPropagation()
                          onSelectSheet(t.ref)
                        }}
                        sx={{
                          fontSize: 11.5,
                          fontWeight: 700,
                          py: 0.35,
                          px: 1.3,
                          borderRadius: 1.5,
                          boxShadow: 'none',
                          whiteSpace: 'nowrap',
                          '&:hover': { boxShadow: '0 2px 8px rgba(30, 58, 138, 0.25)' },
                        }}
                      >
                        مشاهده رویدادها
                      </Button>
                    </TableCell>
                  </TableRow>
                </Tooltip>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      </CardContent>
    </Card>
  )
}

export function ChipCode({ code }: { code: string }) {
  return (
    <Box
      component="span"
      sx={{
        display: 'inline-flex', alignItems: 'center', gap: 0.5, background: '#0f172a',
        color: '#fff', borderRadius: 999, px: 1.2, py: 0.3, fontSize: 11.5, fontWeight: 700,
      }}
    >
      {faCode(code)}
    </Box>
  )
}

export function VisitChip({ label }: { label: string }) {
  return (
    <Box
      component="span"
      sx={{
        display: 'inline-flex', alignItems: 'center', background: '#475569',
        color: '#fff', borderRadius: 999, px: 1.2, py: 0.3, fontSize: 11.5, fontWeight: 700,
      }}
    >
      {label}
    </Box>
  )
}
