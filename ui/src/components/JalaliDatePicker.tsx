import React, { useEffect, useMemo, useState } from 'react'
import {
  Box,
  Button,
  ButtonBase,
  Chip,
  Divider,
  IconButton,
  InputAdornment,
  MenuItem,
  Popover,
  Select,
  Stack,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material'
import CalendarMonthRounded from '@mui/icons-material/CalendarMonthRounded'
import ChevronLeftRounded from '@mui/icons-material/ChevronLeftRounded'
import ChevronRightRounded from '@mui/icons-material/ChevronRightRounded'
import TodayRounded from '@mui/icons-material/TodayRounded'
import ClearRounded from '@mui/icons-material/ClearRounded'
import {
  formatJalaliDate,
  gregorianToJalali,
  JALALI_MONTH_NAMES,
  JALALI_WEEKDAYS_SHORT,
  jalaliMonthLength,
  jalaliParts,
  jalaliToGregorian,
  jalaliYmd,
  parseJalaliDate,
  toIsoDateString,
  toJalaliString,
  toLatinDigits,
  toPersianDigits,
} from '../utils/jalaliDateTime'

export type JalaliDatePickerProps = {
  value: string
  onChange: (value: string) => void
  label?: string
  required?: boolean
  disabled?: boolean
  error?: boolean
  helperText?: string
  size?: 'small' | 'medium'
  fullWidth?: boolean
  outputFormat?: 'iso' | 'jalali'
  placeholder?: string
}

const YEAR_OPTIONS = Array.from({ length: 41 }, (_, i) => 1380 + i) // 1380 to 1420

export function JalaliDatePicker({
  value,
  onChange,
  label = 'تاریخ (شمسی)',
  required = false,
  disabled = false,
  error = false,
  helperText = 'مثال: ۱۴۰۵/۰۷/۲۷',
  size = 'small',
  fullWidth = true,
  outputFormat = 'iso',
  placeholder = '۱۴۰۵/۰۷/۲۷',
}: JalaliDatePickerProps) {
  const [anchorEl, setAnchorEl] = useState<HTMLElement | null>(null)
  const open = Boolean(anchorEl)

  // Current real-world Jalali parts for "Today" indicator
  const now = useMemo(() => jalaliParts(), [])

  // Normalized Jalali representation of the prop value (YYYY/MM/DD)
  const jalaliValue = useMemo(() => toJalaliString(value), [value])

  // Parse internal date from value
  const parsedValue = useMemo(() => {
    if (!jalaliValue) return null
    return parseJalaliDate(jalaliValue)
  }, [jalaliValue])

  const initialParts = useMemo(() => {
    if (parsedValue) {
      const p = jalaliParts(parsedValue)
      return { year: p.year, month: p.month, day: p.day }
    }
    return { year: now.year, month: now.month, day: now.day }
  }, [parsedValue, now])

  const [viewYear, setViewYear] = useState<number>(initialParts.year)
  const [viewMonth, setViewMonth] = useState<number>(initialParts.month)
  const [selectedDay, setSelectedDay] = useState<number | null>(parsedValue ? initialParts.day : null)
  const [displayInput, setDisplayInput] = useState<string>(jalaliValue ? toPersianDigits(jalaliValue) : '')

  // Keep input text synchronized with prop changes
  useEffect(() => {
    if (jalaliValue) {
      setDisplayInput(toPersianDigits(jalaliValue))
      const parts = jalaliValue.split('/')
      if (parts.length === 3) {
        const y = Number(parts[0])
        const m = Number(parts[1])
        const d = Number(parts[2])
        if (y >= 1380 && y <= 1430) setViewYear(y)
        if (m >= 1 && m <= 12) setViewMonth(m)
        setSelectedDay(d)
      }
    } else {
      setDisplayInput('')
      setSelectedDay(null)
    }
  }, [jalaliValue])

  // Month navigation
  const moveMonth = (delta: number) => {
    let nextMonth = viewMonth + delta
    let nextYear = viewYear
    if (nextMonth < 1) {
      nextMonth = 12
      nextYear -= 1
    } else if (nextMonth > 12) {
      nextMonth = 1
      nextYear += 1
    }
    setViewMonth(nextMonth)
    setViewYear(nextYear)
  }

  // Calculate calendar grid metrics
  const firstDayGreg = parseJalaliDate(jalaliYmd(viewYear, viewMonth, 1))
  const dayOffset = firstDayGreg ? (firstDayGreg.getDay() + 1) % 7 : 0
  const daysInMonth = jalaliMonthLength(viewYear, viewMonth)
  const daysArray = Array.from({ length: daysInMonth }, (_, i) => i + 1)

  // Emit change in chosen format
  const emitChange = (y: number, m: number, d: number) => {
    const jalaliStr = jalaliYmd(y, m, d)
    if (outputFormat === 'jalali') {
      onChange(jalaliStr)
    } else {
      const isoStr = toIsoDateString(jalaliStr)
      onChange(isoStr)
    }
  }

  const handleDayClick = (day: number) => {
    setSelectedDay(day)
    emitChange(viewYear, viewMonth, day)
    setAnchorEl(null)
  }

  const handleSetToday = () => {
    setViewYear(now.year)
    setViewMonth(now.month)
    setSelectedDay(now.day)
    emitChange(now.year, now.month, now.day)
    setAnchorEl(null)
  }

  const handleClear = () => {
    setSelectedDay(null)
    setDisplayInput('')
    onChange('')
    setAnchorEl(null)
  }

  // Manual typing in text field
  const handleInputChange = (raw: string) => {
    const latin = toLatinDigits(raw)
    setDisplayInput(raw)
    const clean = latin.replace(/-/g, '/').trim()
    const match = clean.match(/^(\d{4})\/(\d{1,2})\/(\d{1,2})$/)
    if (match) {
      const y = Number(match[1])
      const m = Number(match[2])
      const d = Number(match[3])
      if (y >= 1380 && y <= 1430 && m >= 1 && m <= 12 && d >= 1 && d <= 31) {
        setViewYear(y)
        setViewMonth(m)
        setSelectedDay(d)
        emitChange(y, m, d)
      }
    }
  }

  return (
    <>
      <TextField
        label={label}
        value={displayInput}
        onChange={e => handleInputChange(e.target.value)}
        required={required}
        disabled={disabled}
        error={error}
        helperText={helperText}
        size={size}
        fullWidth={fullWidth}
        placeholder={placeholder}
        slotProps={{
          input: {
            endAdornment: (
              <InputAdornment position="end">
                {Boolean(displayInput) && !required && (
                  <Tooltip title="پاک کردن تاریخ">
                    <IconButton size="small" edge="end" disabled={disabled} onClick={handleClear} sx={{ mr: 0.5 }}>
                      <ClearRounded fontSize="small" />
                    </IconButton>
                  </Tooltip>
                )}
                <Tooltip title="باز کردن تقویم خورشیدی">
                  <IconButton
                    size="small"
                    edge="end"
                    disabled={disabled}
                    onClick={e => setAnchorEl(anchorEl ? null : e.currentTarget)}
                    aria-label="باز کردن تقویم خورشیدی"
                    color={value ? 'primary' : 'default'}
                  >
                    <CalendarMonthRounded fontSize="small" />
                  </IconButton>
                </Tooltip>
              </InputAdornment>
            ),
          },
        }}
      />

      <Popover
        open={open}
        anchorEl={anchorEl}
        onClose={() => setAnchorEl(null)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
        transformOrigin={{ vertical: 'top', horizontal: 'center' }}
        slotProps={{
          paper: {
            sx: {
              width: 'min(92vw, 340px)',
              p: 2,
              borderRadius: 3,
              boxShadow: '0 8px 32px rgba(0,0,0,0.24)',
            },
          },
        }}
      >
        <Stack spacing={1.5}>
          {/* Header Month / Year Selectors */}
          <Stack direction="row" alignItems="center" justifyContent="space-between" spacing={1}>
            <Tooltip title="ماه بعد">
              <IconButton onClick={() => moveMonth(1)} size="small" aria-label="ماه بعد">
                <ChevronRightRounded />
              </IconButton>
            </Tooltip>

            <Stack direction="row" spacing={1} sx={{ flex: 1, justifyContent: 'center' }}>
              {/* Month Dropdown */}
              <Select
                size="small"
                value={viewMonth}
                onChange={e => setViewMonth(Number(e.target.value))}
                sx={{ fontSize: '0.875rem', fontWeight: 700 }}
              >
                {JALALI_MONTH_NAMES.map((name, idx) => (
                  <MenuItem key={idx + 1} value={idx + 1}>
                    {name}
                  </MenuItem>
                ))}
              </Select>

              {/* Year Dropdown */}
              <Select
                size="small"
                value={viewYear}
                onChange={e => setViewYear(Number(e.target.value))}
                sx={{ fontSize: '0.875rem', fontWeight: 700 }}
              >
                {YEAR_OPTIONS.map(y => (
                  <MenuItem key={y} value={y}>
                    {toPersianDigits(y)}
                  </MenuItem>
                ))}
              </Select>
            </Stack>

            <Tooltip title="ماه قبل">
              <IconButton onClick={() => moveMonth(-1)} size="small" aria-label="ماه قبل">
                <ChevronLeftRounded />
              </IconButton>
            </Tooltip>
          </Stack>

          {/* Weekdays Row */}
          <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: 0.5, textAlign: 'center' }}>
            {JALALI_WEEKDAYS_SHORT.map(wd => (
              <Typography key={wd} variant="caption" color="text.secondary" fontWeight={700}>
                {wd}
              </Typography>
            ))}

            {/* Empty slots before first day */}
            {Array.from({ length: dayOffset }).map((_, i) => (
              <Box key={`offset-${i}`} />
            ))}

            {/* Month Days */}
            {daysArray.map(day => {
              const isSelected =
                selectedDay === day &&
                viewMonth === (parsedValue ? jalaliParts(parsedValue).month : viewMonth) &&
                viewYear === (parsedValue ? jalaliParts(parsedValue).year : viewYear)

              const isToday = viewYear === now.year && viewMonth === now.month && day === now.day

              return (
                <ButtonBase
                  key={day}
                  onClick={() => handleDayClick(day)}
                  sx={{
                    aspectRatio: '1',
                    borderRadius: 2,
                    fontSize: '0.85rem',
                    fontWeight: isSelected || isToday ? 800 : 500,
                    bgcolor: isSelected
                      ? 'primary.main'
                      : isToday
                      ? 'primary.light'
                      : 'transparent',
                    color: isSelected
                      ? 'primary.contrastText'
                      : isToday
                      ? 'primary.dark'
                      : 'text.primary',
                    border: isToday && !isSelected ? 1 : 0,
                    borderColor: 'primary.main',
                    transition: 'all 0.15s',
                    '&:hover': {
                      bgcolor: isSelected ? 'primary.dark' : 'action.hover',
                    },
                  }}
                >
                  {toPersianDigits(day)}
                </ButtonBase>
              )
            })}
          </Box>

          <Divider />

          {/* Footer Quick Actions */}
          <Stack direction="row" justifyContent="space-between" alignItems="center">
            <Button
              size="small"
              variant="text"
              startIcon={<TodayRounded fontSize="small" />}
              onClick={handleSetToday}
            >
              امروز ({toPersianDigits(now.day)} {JALALI_MONTH_NAMES[now.month - 1]})
            </Button>
            {!required && (
              <Button size="small" color="inherit" onClick={handleClear}>
                پاک کردن
              </Button>
            )}
          </Stack>
        </Stack>
      </Popover>
    </>
  )
}

/**
 * Reusable Modular Jalali Date Range Picker with Presets.
 */
export type JalaliDateRangePickerProps = {
  startDate: string
  endDate: string
  onRangeChange: (start: string, end: string) => void
  label?: string
  outputFormat?: 'iso' | 'jalali'
}

export function JalaliDateRangePicker({
  startDate,
  endDate,
  onRangeChange,
  label = 'بازه زمانی (شمسی)',
  outputFormat = 'iso',
}: JalaliDateRangePickerProps) {
  const now = useMemo(() => jalaliParts(), [])

  const applyPreset = (preset: 'today' | 'this_week' | 'this_month' | 'this_quarter' | 'this_year') => {
    if (preset === 'today') {
      const todayJalali = jalaliYmd(now.year, now.month, now.day)
      const out = outputFormat === 'iso' ? toIsoDateString(todayJalali) : todayJalali
      onRangeChange(out, out)
    } else if (preset === 'this_month') {
      const startJalali = jalaliYmd(now.year, now.month, 1)
      const endJalali = jalaliYmd(now.year, now.month, jalaliMonthLength(now.year, now.month))
      onRangeChange(
        outputFormat === 'iso' ? toIsoDateString(startJalali) : startJalali,
        outputFormat === 'iso' ? toIsoDateString(endJalali) : endJalali
      )
    } else if (preset === 'this_year') {
      const startJalali = jalaliYmd(now.year, 1, 1)
      const endJalali = jalaliYmd(now.year, 12, jalaliMonthLength(now.year, 12))
      onRangeChange(
        outputFormat === 'iso' ? toIsoDateString(startJalali) : startJalali,
        outputFormat === 'iso' ? toIsoDateString(endJalali) : endJalali
      )
    }
  }

  return (
    <Stack spacing={1.5}>
      <Typography variant="caption" color="text.secondary" fontWeight={700}>
        {label}
      </Typography>
      <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5} alignItems="center">
        <JalaliDatePicker
          label="از تاریخ"
          value={startDate}
          onChange={val => onRangeChange(val, endDate)}
          outputFormat={outputFormat}
          size="small"
        />
        <Typography variant="body2" color="text.secondary">
          تا
        </Typography>
        <JalaliDatePicker
          label="تا تاریخ"
          value={endDate}
          onChange={val => onRangeChange(startDate, val)}
          outputFormat={outputFormat}
          size="small"
        />
      </Stack>
      <Stack direction="row" spacing={1} flexWrap="wrap">
        <Chip size="small" label="امروز" onClick={() => applyPreset('today')} clickable variant="outlined" />
        <Chip size="small" label="ماه جاری" onClick={() => applyPreset('this_month')} clickable variant="outlined" />
        <Chip size="small" label="سال جاری" onClick={() => applyPreset('this_year')} clickable variant="outlined" />
      </Stack>
    </Stack>
  )
}
