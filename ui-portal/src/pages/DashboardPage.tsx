import { useEffect, useState } from 'react'
import {
  Alert, Box, Card, CardContent, Grid, Skeleton, Table, TableBody, TableCell,
  TableContainer, TableHead, TableRow, Typography,
} from '@mui/material'
import EventAvailableIcon from '@mui/icons-material/EventAvailable'
import GroupsIcon from '@mui/icons-material/Groups'
import LocationCityIcon from '@mui/icons-material/LocationCity'
import FactCheckIcon from '@mui/icons-material/FactCheck'
import { api, type Kpis, type ProgramSheet, type VisitTopic } from '../api'
import { usePeriod } from '../components/PeriodPicker'
import { faCode, faNum } from '../periods'
import type { PageProps } from '../App'

/** داشبورد کلان — تمام شاخص‌ها تابع دورهٔ انتخاب‌شده در نوار بالا هستند (F-097) */
export default function DashboardPage({ notify }: PageProps) {
  const { range } = usePeriod()
  const [kpis, setKpis] = useState<Kpis | null>(null)
  const [sheets, setSheets] = useState<ProgramSheet[] | null>(null)
  const [topics, setTopics] = useState<VisitTopic[] | null>(null)
  const [error, setError] = useState('')

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

      <SheetStatusTable sheets={sheets} />
      <VisitTopicsTable topics={topics} />
    </Box>
  )
}

function SheetStatusTable({ sheets }: { sheets: ProgramSheet[] | null }) {
  return (
    <Card>
      <CardContent>
        <Typography variant="h6" sx={{ mb: 1.5 }}>
          وضعیت شیت‌های کاربرگ رسمی ۱۴۰۵ (برای دورهٔ انتخاب‌شده)
        </Typography>
        <TableContainer>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>کد رسمی برنامه</TableCell>
                <TableCell>عنوان شیت</TableCell>
                <TableCell align="center">رویدادهای دوره</TableCell>
                <TableCell align="center">شرکت‌کنندگان</TableCell>
                <TableCell>شرح عملیاتی (خلاصه)</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {sheets === null && (
                Array.from({ length: 8 }).map((_, i) => (
                  <TableRow key={i}><TableCell colSpan={5}><Skeleton /></TableCell></TableRow>
                ))
              )}
              {sheets?.map((s) => (
                <TableRow key={s.code} hover>
                  <TableCell><ChipCode code={s.code} /></TableCell>
                  <TableCell><strong>{s.name}</strong> — <span style={{ color: '#64748b' }}>{s.title}</span></TableCell>
                  <TableCell align="center">{faNum(s.count)}</TableCell>
                  <TableCell align="center">{s.attendees > 0 ? faNum(s.attendees) : '—'}</TableCell>
                  <TableCell sx={{ maxWidth: 380, fontSize: 12, color: '#475569' }}>
                    {s.description ? s.description.slice(0, 130) + (s.description.length > 130 ? '…' : '') : '—'}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      </CardContent>
    </Card>
  )
}

function VisitTopicsTable({ topics }: { topics: VisitTopic[] | null }) {
  return (
    <Card>
      <CardContent>
        <Typography variant="h6" sx={{ mb: 1.5 }}>
          موضوعات تکمیلی کاربرگ بازدید استانی (ردیف‌های ۲، ۴، ۶، ۸ و ۹ سند رسمی)
        </Typography>
        <TableContainer>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>ردیف سند</TableCell>
                <TableCell>عنوان موضوع</TableCell>
                <TableCell align="center">رویدادهای دوره</TableCell>
                <TableCell align="center">شرکت‌کنندگان</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {topics === null && (
                Array.from({ length: 5 }).map((_, i) => (
                  <TableRow key={i}><TableCell colSpan={4}><Skeleton /></TableCell></TableRow>
                ))
              )}
              {topics?.map((t) => (
                <TableRow key={t.ref} hover>
                  <TableCell><VisitChip label={t.row_label} /></TableCell>
                  <TableCell><strong>{t.title}</strong></TableCell>
                  <TableCell align="center">{faNum(t.count)}</TableCell>
                  <TableCell align="center">{t.attendees > 0 ? faNum(t.attendees) : '—'}</TableCell>
                </TableRow>
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
