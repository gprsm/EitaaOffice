import { createContext, useContext, useMemo, useState, type MouseEvent, type ReactNode } from 'react'
import {
  Box, Button, Chip, Divider, ListItemIcon, ListItemText, Menu, MenuItem,
  Typography, Tooltip,
} from '@mui/material'
import CalendarMonthIcon from '@mui/icons-material/CalendarMonth'
import ArrowDropDownIcon from '@mui/icons-material/ArrowDropDown'
import CheckIcon from '@mui/icons-material/Check'
import TodayIcon from '@mui/icons-material/Today'
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

const YEARS = [1405, 1404, 1403]

/** جلالی ↔ Date برای دیت‌پیکر MUI جلالی */
const jalaliToDate = (j: Jalali): Date => {
  const [gy, gm, gd] = jalaliToGregorian(j[0], j[1], j[2])
  return new Date(gy, gm - 1, gd)
}
const dateToJalali = (d: Date): Jalali => gregorianToJalali(d.getFullYear(), d.getMonth() + 1, d.getDate())

/**
 * انتخابگر دورهٔ زمانی سبک و متمرکز:
 * - دو باکس DatePicker جلالی استاندارد (از تاریخ / تا تاریخ)
 * - منوی پاپ‌اور سریع برای دوره‌های پرکاربرد (دوماهه‌ها، شش‌ماهه، سال کامل) بدون اشغال فضای اضافی
 */
export function PeriodPicker({ compact = false }: { compact?: boolean }) {
  const { period, setPeriod } = usePeriod()
  const [menuAnchor, setMenuAnchor] = useState<HTMLElement | null>(null)
  const [menuYear, setMenuYear] = useState<number>(period.year)

  const handleOpenMenu = (e: MouseEvent<HTMLElement>) => {
    setMenuYear(period.year)
    setMenuAnchor(e.currentTarget)
  }
  const handleCloseMenu = () => setMenuAnchor(null)

  const handleSelectPreset = (year: number, presetId: string) => {
    setPeriod(presetSelection(year, presetId))
    handleCloseMenu()
  }

  const handleFromChange = (d: Date | null) => {
    if (!d) return
    const from = dateToJalali(d)
    setPeriod(customSelection(from[0], from, period.toJalali))
  }

  const handleToChange = (d: Date | null) => {
    if (!d) return
    const to = dateToJalali(d)
    setPeriod(customSelection(period.year, period.fromJalali, to))
  }

  return (
    <LocalizationProvider dateAdapter={AdapterDateFnsJalali} adapterLocale={faIR}>
      <Box sx={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: 1.2,
      }}>
        {/* بخش دو دیت‌پیکر شمسی: از تاریخ و تا تاریخ */}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
          <DatePicker
            label="از تاریخ"
            value={jalaliToDate(period.fromJalali)}
            onChange={handleFromChange}
            slotProps={{
              textField: {
                size: 'small',
                sx: { width: compact ? 135 : 155 },
              },
            }}
          />
          <Typography variant="body2" color="text.secondary" sx={{ userSelect: 'none' }}>
            تا
          </Typography>
          <DatePicker
            label="تا تاریخ"
            value={jalaliToDate(period.toJalali)}
            onChange={handleToChange}
            slotProps={{
              textField: {
                size: 'small',
                sx: { width: compact ? 135 : 155 },
              },
            }}
          />
        </Box>

        {/* دکمه انتخاب سریع دوره اداری / بازه‌های از پیش‌تعریف‌شده */}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Tooltip title="کلیک برای انتخاب سریع دوره‌های اداری (دوماهه، شش‌ماهه، سالانه)">
            <Button
              variant={period.presetId === 'custom' ? 'outlined' : 'contained'}
              color="primary"
              size={compact ? 'small' : 'medium'}
              startIcon={<CalendarMonthIcon />}
              endIcon={<ArrowDropDownIcon />}
              onClick={handleOpenMenu}
              sx={{
                fontWeight: 700,
                fontSize: { xs: 12, md: 13 },
                borderRadius: 2,
                textTransform: 'none',
                whiteSpace: 'nowrap',
              }}
            >
              {period.presetId === 'custom' ? 'بازهٔ سفارشی' : period.label}
            </Button>
          </Tooltip>

          {period.presetId === 'custom' && (
            <Chip
              size="small"
              label={period.label}
              variant="outlined"
              color="info"
              sx={{ display: { xs: 'none', sm: 'inline-flex' }, fontSize: 11.5 }}
            />
          )}
        </Box>

        {/* منوی مدرن دوره‌های از پیش‌تعریف‌شده */}
        <Menu
          anchorEl={menuAnchor}
          open={Boolean(menuAnchor)}
          onClose={handleCloseMenu}
          anchorOrigin={{ vertical: 'bottom', horizontal: 'left' }}
          transformOrigin={{ vertical: 'top', horizontal: 'left' }}
          PaperProps={{
            sx: {
              maxHeight: 460,
              minWidth: 260,
              p: 0.5,
              borderRadius: 2,
              boxShadow: '0 8px 24px rgba(0,0,0,0.12)',
            },
          }}
        >
          {/* انتخابگر سال درون منو */}
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', px: 1.5, py: 1 }}>
            <Typography variant="caption" sx={{ fontWeight: 800, color: 'text.secondary' }}>
              سال اداری:
            </Typography>
            <Box sx={{ display: 'flex', gap: 0.5 }}>
              {YEARS.map((y) => (
                <Chip
                  key={y}
                  size="small"
                  label={faNum(y)}
                  clickable
                  color={menuYear === y ? 'primary' : 'default'}
                  variant={menuYear === y ? 'filled' : 'outlined'}
                  onClick={() => setMenuYear(y)}
                  sx={{ fontWeight: menuYear === y ? 800 : 500 }}
                />
              ))}
            </Box>
          </Box>
          <Divider sx={{ my: 0.5 }} />

          {/* دوره‌های دوماهه */}
          <Typography variant="caption" sx={{ px: 2, py: 0.5, display: 'block', color: 'primary.main', fontWeight: 800 }}>
            دوره‌های دوماهه کارنامه
          </Typography>
          {periodPresets(menuYear)
            .filter((p) => p.id.startsWith('b'))
            .map((p) => {
              const active = period.presetId === p.id && period.year === menuYear
              return (
                <MenuItem
                  key={p.id}
                  selected={active}
                  onClick={() => handleSelectPreset(menuYear, p.id)}
                  sx={{ py: 0.8, borderRadius: 1 }}
                >
                  <ListItemIcon sx={{ minWidth: 28 }}>
                    {active ? <CheckIcon fontSize="small" color="primary" /> : <TodayIcon fontSize="small" sx={{ opacity: 0.35 }} />}
                  </ListItemIcon>
                  <ListItemText
                    primary={p.label}
                    primaryTypographyProps={{ fontSize: 13, fontWeight: active ? 800 : 500 }}
                  />
                </MenuItem>
              )
            })}

          <Divider sx={{ my: 0.5 }} />

          {/* دوره‌های فصلی، شش‌ماهه و سالانه */}
          <Typography variant="caption" sx={{ px: 2, py: 0.5, display: 'block', color: 'primary.main', fontWeight: 800 }}>
            دوره‌های تجمیعی و سالانه
          </Typography>
          {periodPresets(menuYear)
            .filter((p) => !p.id.startsWith('b'))
            .map((p) => {
              const active = period.presetId === p.id && period.year === menuYear
              return (
                <MenuItem
                  key={p.id}
                  selected={active}
                  onClick={() => handleSelectPreset(menuYear, p.id)}
                  sx={{ py: 0.8, borderRadius: 1 }}
                >
                  <ListItemIcon sx={{ minWidth: 28 }}>
                    {active ? <CheckIcon fontSize="small" color="primary" /> : <CalendarMonthIcon fontSize="small" sx={{ opacity: 0.35 }} />}
                  </ListItemIcon>
                  <ListItemText
                    primary={p.label}
                    primaryTypographyProps={{ fontSize: 13, fontWeight: active ? 800 : 500 }}
                  />
                </MenuItem>
              )
            })}
        </Menu>
      </Box>
    </LocalizationProvider>
  )
}
