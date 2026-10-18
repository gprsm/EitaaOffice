import React, { useEffect, useMemo, useState } from 'react'
import {
  Box,
  Button,
  ButtonBase,
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
import AccessTimeRounded from '@mui/icons-material/AccessTimeRounded'
import ChevronLeftRounded from '@mui/icons-material/ChevronLeftRounded'
import ChevronRightRounded from '@mui/icons-material/ChevronRightRounded'
import TodayRounded from '@mui/icons-material/TodayRounded'
import CheckRounded from '@mui/icons-material/CheckRounded'
import {
  formatJalaliDate,
  formatJalaliDateTime,
  formatJalaliTime,
  JALALI_MONTH_NAMES,
  JALALI_WEEKDAYS_SHORT,
  jalaliMonthLength,
  jalaliParts,
  jalaliYmd,
  parseJalaliDate,
  parseJalaliDateTime,
  toLatinDigits,
  toPersianDigits,
} from '../utils/jalaliDateTime'

export type JalaliDateTimePickerProps = {
  value: string
  onChange: (value: string) => void
  label?: string
  required?: boolean
  disabled?: boolean
  error?: boolean
  helperText?: string
  size?: 'small' | 'medium'
  fullWidth?: boolean
  showTime?: boolean
}

export function JalaliDateTimePicker({
  value,
  onChange,
  label = 'تاریخ و زمان وقوع (جلالی)',
  required = false,
  disabled = false,
  error = false,
  helperText = 'مثال: 1405/07/24 17:20',
  size = 'small',
  fullWidth = true,
  showTime = true,
}: JalaliDateTimePickerProps) {
  const [anchorEl, setAnchorEl] = useState<HTMLElement | null>(null)
  const open = Boolean(anchorEl)

  // Current real-world Jalali parts for "Today" indicator
  const now = useMemo(() => jalaliParts(), [])

  // Parse internal date and time from props.value
  const parsedValue = useMemo(() => {
    if (!value) return null
    return parseJalaliDateTime(value) || parseJalaliDate(value)
  }, [value])

  const initialParts = useMemo(() => {
    return parsedValue ? jalaliParts(parsedValue) : jalaliParts()
  }, [parsedValue])

  const [viewYear, setViewYear] = useState(initialParts.year)
  const [viewMonth, setViewMonth] = useState(initialParts.month)
  const [selectedDay, setSelectedDay] = useState(initialParts.day)
  const [selectedHour, setSelectedHour] = useState(initialParts.hour)
  const [selectedMinute, setSelectedMinute] = useState(initialParts.minute)

  // When popover opens or prop value updates, synchronize picker state
  useEffect(() => {
    if (parsedValue) {
      const p = jalaliParts(parsedValue)
      setViewYear(p.year)
      setViewMonth(p.month)
      setSelectedDay(p.day)
      setSelectedHour(p.hour)
      setSelectedMinute(p.minute)
    }
  }, [parsedValue, open])

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
  const firstDayOfMonth = parseJalaliDate(jalaliYmd(viewYear, viewMonth, 1))
  const dayOffset = firstDayOfMonth ? (firstDayOfMonth.getDay() + 1) % 7 : 0
  const daysInMonth = jalaliMonthLength(viewYear, viewMonth)
  const daysArray = Array.from({ length: daysInMonth }, (_, i) => i + 1)

  // Apply changes to parent
  const applySelection = (y: number, m: number, d: number, hh: number, mm: number) => {
    const dateStr = jalaliYmd(y, m, d)
    if (showTime) {
      const timeStr = `${String(hh).padStart(2, '0')}:${String(mm).padStart(2, '0')}`
      onChange(`${dateStr} ${timeStr}`)
    } else {
      onChange(dateStr)
    }
  }

  const handleDayClick = (day: number) => {
    setSelectedDay(day)
    applySelection(viewYear, viewMonth, day, selectedHour, selectedMinute)
  }

  const handleHourChange = (newHour: number) => {
    setSelectedHour(newHour)
    applySelection(viewYear, viewMonth, selectedDay, newHour, selectedMinute)
  }

  const handleMinuteChange = (newMinute: number) => {
    setSelectedMinute(newMinute)
    applySelection(viewYear, viewMonth, selectedDay, selectedHour, newMinute)
  }

  const handleSetNow = () => {
    const current = jalaliParts(new Date())
    setViewYear(current.year)
    setViewMonth(current.month)
    setSelectedDay(current.day)
    setSelectedHour(current.hour)
    setSelectedMinute(current.minute)
    if (showTime) {
      onChange(formatJalaliDateTime(new Date()))
    } else {
      onChange(formatJalaliDate(new Date()))
    }
  }

  return (
    <>
      <TextField
        label={label}
        value={value}
        onChange={e => onChange(toLatinDigits(e.target.value))}
        required={required}
        disabled={disabled}
        error={error}
        helperText={helperText}
        size={size}
        fullWidth={fullWidth}
        slotProps={{
          input: {
            endAdornment: (
              <InputAdornment position="end">
                <Tooltip title="انتخاب تاریخ و زمان شمسی">
                  <IconButton
                    size="small"
                    edge="end"
                    disabled={disabled}
                    onClick={e => setAnchorEl(anchorEl ? null : e.currentTarget)}
                    aria-label="انتخاب تاریخ و زمان شمسی"
                    color={value ? 'primary' : 'default'}
                  >
                    {showTime ? <AccessTimeRounded fontSize="small" /> : <CalendarMonthRounded fontSize="small" />}
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
              width: 'min(92vw, 360px)',
              p: 2,
              borderRadius: 3,
              boxShadow: '0 8px 32px rgba(0,0,0,0.24)',
            },
          },
        }}
      >
        <Stack spacing={1.5}>
          {/* Header Month / Year Navigation */}
          <Stack direction="row" alignItems="center" justifyContent="space-between">
            <Tooltip title="ماه بعد">
              <IconButton onClick={() => moveMonth(1)} size="small" aria-label="ماه بعد">
                <ChevronRightRounded />
              </IconButton>
            </Tooltip>

            <Typography variant="subtitle1" fontWeight={800}>
              {JALALI_MONTH_NAMES[viewMonth - 1]} {toPersianDigits(viewYear)}
            </Typography>

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
                viewYear === (parsedValue ? jalaliParts(parsedValue).year : viewYear) &&
                viewMonth === (parsedValue ? jalaliParts(parsedValue).month : viewMonth) &&
                day === selectedDay

              const isToday =
                viewYear === now.year &&
                viewMonth === now.month &&
                day === now.day

              return (
                <ButtonBase
                  key={`day-${day}`}
                  onClick={() => handleDayClick(day)}
                  sx={{
                    aspectRatio: '1',
                    borderRadius: '50%',
                    bgcolor: isSelected ? 'primary.main' : 'transparent',
                    color: isSelected ? 'primary.contrastText' : 'text.primary',
                    border: isToday && !isSelected ? 1 : 0,
                    borderColor: 'primary.main',
                    fontWeight: isSelected || isToday ? 800 : 500,
                    fontSize: '0.85rem',
                    transition: 'all 0.15s ease',
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

          {/* Time Picker Controls */}
          {showTime && (
            <>
              <Divider sx={{ my: 0.5 }} />
              <Stack direction="row" alignItems="center" justifyContent="center" spacing={1.5}>
                <AccessTimeRounded fontSize="small" color="action" />
                <Typography variant="body2" color="text.secondary" fontWeight={600}>
                  ساعت:
                </Typography>
                <Select
                  size="small"
                  value={selectedHour}
                  onChange={e => handleHourChange(Number(e.target.value))}
                  sx={{ minWidth: 68, fontSize: '0.875rem' }}
                >
                  {Array.from({ length: 24 }, (_, i) => (
                    <MenuItem key={`hour-${i}`} value={i}>
                      {String(i).padStart(2, '0')}
                    </MenuItem>
                  ))}
                </Select>
                <Typography variant="body2" fontWeight={800}>
                  :
                </Typography>
                <Select
                  size="small"
                  value={selectedMinute}
                  onChange={e => handleMinuteChange(Number(e.target.value))}
                  sx={{ minWidth: 68, fontSize: '0.875rem' }}
                >
                  {Array.from({ length: 60 }, (_, i) => (
                    <MenuItem key={`min-${i}`} value={i}>
                      {String(i).padStart(2, '0')}
                    </MenuItem>
                  ))}
                </Select>
              </Stack>
            </>
          )}

          {/* Action Buttons */}
          <Divider sx={{ my: 0.5 }} />
          <Stack direction="row" alignItems="center" justifyContent="space-between">
            <Button
              size="small"
              variant="text"
              startIcon={<TodayRounded />}
              onClick={handleSetNow}
            >
              هم‌اکنون
            </Button>
            <Button
              size="small"
              variant="contained"
              startIcon={<CheckRounded />}
              onClick={() => setAnchorEl(null)}
            >
              تأیید
            </Button>
          </Stack>
        </Stack>
      </Popover>
    </>
  )
}
