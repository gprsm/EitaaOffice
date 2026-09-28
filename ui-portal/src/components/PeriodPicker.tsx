import { createContext, useContext, useMemo, useState, type ReactNode } from 'react'
import {
  Box, Chip, FormControl, InputLabel, MenuItem, Select, Tooltip,
} from '@mui/material'
import DateRangerIcon from '@mui/icons-material/DateRange'
import CalendarMonthIcon from '@mui/icons-material/CalendarMonth'
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider'
import { faIR } from 'date-fns-jalali/locale'
import { AdapterDateFnsJalali } from '@mui/x-date-pickers/AdapterDateFnsJalali'
import { DatePicker } from '@mui/x-date-pickers/DatePicker'
import {
  defaultSelection, periodPresets, presetSelection, customSelection, faNum,
  jalaliToIso, gregorianToJalali, jalaliToGregorian,
  type PeriodSelection, type Jalali,
} from '../periods'
import type { Range } from '../api'

interface PeriodContextValue {
  period: PeriodSelection
  range: Range
  setPeriod: (p: PeriodSelection) => void
}

const PeriodContext = createContext<PeriodContextValue | null>(null)

/** ارائه‌دهندهٔ دورهٔ زمانی مشترک — همهٔ صفحات و خروجی اکسل از این منبع می‌خوانند */
export function PeriodProvider({ children }: { children: ReactNode }) {
  const [period, setPeriod] = useState<PeriodSelection>(() => defaultSelection(1405))
  const value = useMemo<PeriodContextValue>(() => ({
    period,
    setPeriod,
    range: { fromIso: jalaliToIso(period.fromJalali), toIso: jalaliToIso(period.toJalali), label: period.label },
  }), [period])
  return <PeriodContext.Provider value={value}>{children}</PeriodContext.Provider>
}

export function usePeriod(): PeriodContextValue {
  const ctx = useContext(PeriodContext)
  if (!ctx) throw new Error('PeriodProvider missing')
  return ctx
}

const YEARS = [1403, 1404, 1405, 1406]

/** جلالی ↔ Date برای دیت‌پیکر MUI جلالی */
const jalaliToDate = (j: Jalali): Date => {
  const [gy, gm, gd] = jalaliToGregorian(j[0], j[1], j[2])
  return new Date(gy, gm - 1, gd)
}
const dateToJalali = (d: Date): Jalali => gregorianToJalali(d.getFullYear(), d.getMonth() + 1, d.getDate())

/**
 * انتخابگر دورهٔ زمانی: دوماهه ۱–۶ / چهارماهه / شش‌ماهه / سال کامل / بازهٔ سفارشی
 * بازهٔ سفارشی با دیت‌پیکر جلالی MUI X انتخاب می‌شود.
 */
export function PeriodPicker({ compact = false }: { compact?: boolean }) {
  const { period, setPeriod } = usePeriod()
  const [custom, setCustom] = useState(period.presetId === 'custom')

  const applyPreset = (presetId: string) => {
    if (presetId === 'custom') {
      setCustom(true)
      return
    }
    setCustom(false)
    setPeriod(presetSelection(period.year, presetId))
  }

  return (
    <LocalizationProvider dateAdapter={AdapterDateFnsJalali} adapterLocale={faIR}>
      <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', flexWrap: 'wrap' }}>
        <Tooltip title="دورهٔ گزارش — در همهٔ صفحات و خروجی اکسل اعمال می‌شود">
          <DateRangerIcon color="primary" />
        </Tooltip>

        <FormControl size="small" sx={{ minWidth: 110 }}>
          <InputLabel id="period-year-label">سال</InputLabel>
          <Select
            labelId="period-year-label"
            label="سال"
            value={period.year}
            onChange={(e) => {
              const year = Number(e.target.value)
              setPeriod(presetSelection(year, period.presetId === 'custom' ? 'b3' : period.presetId))
            }}
          >
            {YEARS.map((y) => (
              <MenuItem key={y} value={y}>{faNum(y)}</MenuItem>
            ))}
          </Select>
        </FormControl>

        <FormControl size="small" sx={{ minWidth: compact ? 210 : 290, maxWidth: 400 }}>
          <InputLabel id="period-preset-label">دوره</InputLabel>
          <Select
            labelId="period-preset-label"
            label="دوره"
            value={custom ? 'custom' : period.presetId}
            onChange={(e) => applyPreset(e.target.value)}
          >
            {periodPresets(period.year).map((p) => (
              <MenuItem key={p.id} value={p.id}>{p.label}</MenuItem>
            ))}
            <MenuItem value="custom">بازهٔ سفارشی…</MenuItem>
          </Select>
        </FormControl>

        {custom && (
          <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', flexWrap: 'wrap' }}>
            <DatePicker
              label="از تاریخ"
              value={jalaliToDate(period.fromJalali)}
              onChange={(d) => { if (d) setPeriod(customSelection(period.year, dateToJalali(d), period.toJalali)) }}
              slotProps={{ textField: { size: 'small', sx: { minWidth: 140 } } }}
            />
            <DatePicker
              label="تا تاریخ"
              value={jalaliToDate(period.toJalali)}
              onChange={(d) => { if (d) setPeriod(customSelection(period.year, period.fromJalali, dateToJalali(d))) }}
              slotProps={{ textField: { size: 'small', sx: { minWidth: 140 } } }}
            />
          </Box>
        )}

        <Chip
          icon={<CalendarMonthIcon />}
          label={period.label}
          color="primary"
          variant="outlined"
          size={compact ? 'small' : 'medium'}
        />
      </Box>
    </LocalizationProvider>
  )
}
