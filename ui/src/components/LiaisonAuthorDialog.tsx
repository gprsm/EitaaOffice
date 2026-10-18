import React, { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Alert,
  Autocomplete,
  Avatar,
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
  Divider,
  FormControlLabel,
  IconButton,
  InputAdornment,
  LinearProgress,
  Paper,
  Stack,
  Switch,
  Tab,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Tabs,
  TextField,
  Tooltip,
  Typography,
  useMediaQuery,
  useTheme,
} from '@mui/material'
import CloseRounded from '@mui/icons-material/CloseRounded'
import PersonRounded from '@mui/icons-material/PersonRounded'
import AccountBalanceRounded from '@mui/icons-material/AccountBalanceRounded'
import PhoneRounded from '@mui/icons-material/PhoneRounded'
import ChatRounded from '@mui/icons-material/ChatRounded'
import PostAddRounded from '@mui/icons-material/PostAddRounded'
import CheckCircleRounded from '@mui/icons-material/CheckCircleRounded'
import BarChartRounded from '@mui/icons-material/BarChartRounded'
import AssessmentRounded from '@mui/icons-material/AssessmentRounded'
import ContentCopyRounded from '@mui/icons-material/ContentCopyRounded'
import RefreshRounded from '@mui/icons-material/RefreshRounded'
import SaveRounded from '@mui/icons-material/SaveRounded'
import DeleteOutlineRounded from '@mui/icons-material/DeleteOutlineRounded'
import { api } from '../lib/api'
import type { JudicialUnitItem, LiaisonItem } from './JudicialUnitsManagementModal'

export interface TopicFrequencyItem {
  topic: string
  count: number
  percentage: number
}

export interface RecentReportItem {
  event_id: string
  occurred_on: string
  occasion: string
  review_status: string
  unit_name: string
}

export interface LiaisonProfileData {
  liaison: LiaisonItem | null
  unit: JudicialUnitItem | null
  liaison_name: string
  unit_display_name: string
  display_title: string
  is_liaison: boolean
  time_window_days: number
  messages_count: number
  monthly_messages: Array<{ month: string; count: number }>
  reports_count: number
  reports_by_status: {
    approved: number
    needs_review: number
    revision_requested: number
    conflict: number
    draft: number
  }
  topic_frequency: TopicFrequencyItem[]
  unit_total_reports: number
  unit_participation_percentage: number
  unit_topic_frequency: TopicFrequencyItem[]
  recent_reports: RecentReportItem[]
}

interface Props {
  open: boolean
  onClose: () => void
  authorName: string
  authorUsername?: string
  authorUserId?: string
  senderKey?: string
  onLiaisonUpdated?: () => void
  onDirectMessage?: (author: { name: string; username?: string; userId?: string; senderKey?: string }) => void
  onQuickRegisterReport?: (prefill: { authorName: string; judicialUnit: string }) => void
}

export function LiaisonAuthorDialog({
  open,
  onClose,
  authorName,
  authorUsername = '',
  authorUserId = '',
  senderKey = '',
  onLiaisonUpdated,
  onDirectMessage,
  onQuickRegisterReport,
}: Props) {
  const theme = useTheme()
  const fullScreen = useMediaQuery(theme.breakpoints.down('sm'))

  const [tab, setTab] = useState(0) // 0: Profile & Analytics, 1: Assignment Settings
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [errorText, setErrorText] = useState('')
  const [successText, setSuccessText] = useState('')
  const [copiedPhone, setCopiedPhone] = useState(false)

  // Units list
  const [units, setUnits] = useState<JudicialUnitItem[]>([])

  // Profile data
  const [profile, setProfile] = useState<LiaisonProfileData | null>(null)
  const [timeWindowDays, setTimeWindowDays] = useState(365)

  // Edit / Assignment form state
  const [isLiaison, setIsLiaison] = useState(false)
  const [selectedUnit, setSelectedUnit] = useState<JudicialUnitItem | null>(null)
  const [fullName, setFullName] = useState(authorName)
  const [phone, setPhone] = useState('')
  const [matchKeywords, setMatchKeywords] = useState('')
  const [notes, setNotes] = useState('')

  const loadData = useCallback(async (days = timeWindowDays) => {
    setLoading(true)
    setErrorText('')
    try {
      // 1. Fetch units if not loaded
      const unitsRes = await api<{ units: JudicialUnitItem[]; counties: string[] }>('GET', '/api/v3/reporting/units')
      const allUnits = unitsRes.units || []
      setUnits(allUnits)

      // 2. Fetch profile analytics
      const params = new URLSearchParams()
      params.set('days', String(days))
      if (senderKey) params.set('sender_key', senderKey)
      if (authorUsername) params.set('username', authorUsername)
      if (authorUserId) params.set('user_id', authorUserId)
      if (authorName) params.set('full_name', authorName)

      const profRes = await api<{ ok: boolean; profile: LiaisonProfileData }>(
        'GET',
        `/api/v3/reporting/liaisons/profile?${params.toString()}`,
      )
      const p = profRes.profile
      setProfile(p)

      // Initialize form fields
      setIsLiaison(p.is_liaison)
      setFullName(p.liaison?.full_name || authorName)
      setPhone(p.liaison?.phone || '')
      setMatchKeywords(p.liaison?.match_keywords || '')
      setNotes(p.liaison?.notes || '')

      if (p.unit) {
        setSelectedUnit(p.unit)
      } else if (p.liaison?.unit_id) {
        const found = allUnits.find(u => u.unit_id === p.liaison?.unit_id)
        if (found) setSelectedUnit(found)
      }
    } catch (err) {
      setErrorText(err instanceof Error ? err.message : 'خطا در دریافت اطلاعات کارنامه رابط')
    } finally {
      setLoading(false)
    }
  }, [authorName, authorUserId, authorUsername, senderKey, timeWindowDays])

  useEffect(() => {
    if (open) {
      setTab(0)
      void loadData(timeWindowDays)
    }
  }, [open, loadData, timeWindowDays])

  const handleSaveLiaison = async () => {
    if (!isLiaison) {
      // If toggled off, unlink
      await handleUnlink()
      return
    }
    if (!selectedUnit) {
      setErrorText('لطفاً یک حوزه قضایی برای این رابط انتخاب کنید.')
      return
    }

    setSaving(true)
    setErrorText('')
    setSuccessText('')
    try {
      await api('POST', '/api/v3/reporting/liaisons/assign-author', {
        unit_id: selectedUnit.unit_id,
        full_name: fullName.trim() || authorName,
        sender_key: senderKey,
        eitaa_username: authorUsername.replace(/^@/, ''),
        eitaa_user_id: authorUserId,
        phone: phone.trim(),
        match_keywords: matchKeywords.trim(),
        notes: notes.trim(),
      })
      setSuccessText('مشخصات رابط فرهنگی با موفقیت ثبت و ذخیره شد.')
      onLiaisonUpdated?.()
      await loadData()
    } catch (err) {
      setErrorText(err instanceof Error ? err.message : 'خطا در ثبت انتساب رابط')
    } finally {
      setSaving(false)
    }
  }

  const handleUnlink = async () => {
    setSaving(true)
    setErrorText('')
    setSuccessText('')
    try {
      await api('POST', '/api/v3/reporting/liaisons/unlink-author', {
        sender_key: senderKey,
        liaison_id: profile?.liaison?.liaison_id || '',
      })
      setSuccessText('انتساب به عنوان رابط فرهنگی لغو شد.')
      setIsLiaison(false)
      setSelectedUnit(null)
      onLiaisonUpdated?.()
      await loadData()
    } catch (err) {
      setErrorText(err instanceof Error ? err.message : 'خطا در لغو انتساب رابط')
    } finally {
      setSaving(false)
    }
  }

  const handleCopyPhone = () => {
    if (phone) {
      void navigator.clipboard.writeText(phone)
      setCopiedPhone(true)
      setTimeout(() => setCopiedPhone(false), 2000)
    }
  }

  // Standardized display title per user specification
  const displayTitle = useMemo(() => {
    if (isLiaison && selectedUnit) {
      return `${fullName.trim() || authorName} - حوزه قضایی ${selectedUnit.display_name}`
    }
    if (profile?.is_liaison && profile.unit_display_name) {
      return `${profile.liaison_name} - حوزه قضایی ${profile.unit_display_name}`
    }
    return authorName
  }, [authorName, fullName, isLiaison, profile, selectedUnit])

  return (
    <Dialog
      open={open}
      onClose={onClose}
      fullScreen={fullScreen}
      fullWidth
      maxWidth="md"
      aria-labelledby="liaison-dialog-title"
    >
      <DialogTitle
        id="liaison-dialog-title"
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          pb: 1.5,
          bgcolor: 'background.paper',
        }}
      >
        <Stack direction="row" spacing={1.5} alignItems="center" sx={{ minWidth: 0 }}>
          <Avatar sx={{ bgcolor: isLiaison ? 'primary.main' : 'grey.600', width: 40, height: 40, fontWeight: 800 }}>
            {authorName.slice(0, 2)}
          </Avatar>
          <Box sx={{ minWidth: 0 }}>
            <Typography variant="h6" fontWeight={800} noWrap>
              {displayTitle}
            </Typography>
            <Stack direction="row" spacing={1} alignItems="center">
              {authorUsername && (
                <Typography variant="caption" color="text.secondary" dir="ltr">
                  @{authorUsername.replace(/^@/, '')}
                </Typography>
              )}
              {isLiaison ? (
                <Chip
                  size="small"
                  color="primary"
                  icon={<CheckCircleRounded fontSize="small" />}
                  label="رابط فرهنگی تاییدشده"
                  sx={{ height: 22, fontSize: '0.72rem' }}
                />
              ) : (
                <Chip
                  size="small"
                  variant="outlined"
                  label="کاربر عادی (غیر رابط)"
                  sx={{ height: 22, fontSize: '0.72rem' }}
                />
              )}
            </Stack>
          </Box>
        </Stack>
        <IconButton onClick={onClose} aria-label="بستن"><CloseRounded /></IconButton>
      </DialogTitle>

      <Divider />

      {/* Tabs */}
      <Box sx={{ px: 3, pt: 1, bgcolor: 'background.paper' }}>
        <Tabs value={tab} onChange={(_, val) => { setTab(val); setErrorText(''); setSuccessText('') }}>
          <Tab
            icon={<AssessmentRounded sx={{ mr: 1, verticalAlign: 'middle' }} />}
            iconPosition="start"
            label="کارنامه و تحلیل فعالیت‌ها (پروفایل)"
          />
          <Tab
            icon={<AccountBalanceRounded sx={{ mr: 1, verticalAlign: 'middle' }} />}
            iconPosition="start"
            label="تنظیمات و انتساب حوزه قضایی"
          />
        </Tabs>
      </Box>

      <DialogContent sx={{ p: { xs: 2, sm: 3 }, bgcolor: 'background.default', minHeight: 460 }}>
        {errorText && <Alert severity="error" onClose={() => setErrorText('')} sx={{ mb: 2 }}>{errorText}</Alert>}
        {successText && <Alert severity="success" onClose={() => setSuccessText('')} sx={{ mb: 2 }}>{successText}</Alert>}

        {loading ? (
          <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', py: 8 }}>
            <CircularProgress size={36} />
            <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
              در حال دریافت کارنامه و سوابق فعالیت‌های رابط...
            </Typography>
          </Box>
        ) : (
          <>
            {/* Quick action bar */}
            <Paper variant="outlined" sx={{ p: 1.5, mb: 2.5, bgcolor: 'background.paper' }}>
              <Stack
                direction={{ xs: 'column', sm: 'row' }}
                spacing={1}
                alignItems={{ xs: 'stretch', sm: 'center' }}
                justifyContent="space-between"
              >
                <Stack direction="row" spacing={1} flexWrap="wrap">
                  {onDirectMessage && (
                    <Button
                      variant="outlined"
                      size="small"
                      startIcon={<ChatRounded />}
                      onClick={() => {
                        onDirectMessage({
                          name: authorName,
                          username: authorUsername,
                          userId: authorUserId,
                          senderKey,
                        })
                        onClose()
                      }}
                    >
                      ارسال پیام خصوصی به رابط
                    </Button>
                  )}
                  {onQuickRegisterReport && selectedUnit && (
                    <Button
                      variant="contained"
                      size="small"
                      color="primary"
                      startIcon={<PostAddRounded />}
                      onClick={() => {
                        onQuickRegisterReport({
                          authorName: fullName || authorName,
                          judicialUnit: selectedUnit.display_name,
                        })
                        onClose()
                      }}
                    >
                      ثبت گزارش برای این پیام
                    </Button>
                  )}
                </Stack>

                {phone && (
                  <Stack direction="row" spacing={0.5} alignItems="center">
                    <Tooltip title={copiedPhone ? 'کپی شد!' : 'کپی شماره تماس'}>
                      <Chip
                        icon={<PhoneRounded fontSize="small" />}
                        label={phone}
                        onClick={handleCopyPhone}
                        onDelete={handleCopyPhone}
                        deleteIcon={<ContentCopyRounded fontSize="small" />}
                        variant="outlined"
                        color="primary"
                        sx={{ direction: 'ltr', fontWeight: 700 }}
                      />
                    </Tooltip>
                  </Stack>
                )}
              </Stack>
            </Paper>

            {/* TAB 0: PROFILE & ANALYTICS */}
            {tab === 0 && (
              <Stack spacing={2.5}>
                {/* Time range selector */}
                <Stack direction="row" alignItems="center" justifyContent="space-between" flexWrap="wrap" gap={1}>
                  <Typography variant="subtitle2" fontWeight={800} color="text.secondary">
                    تحلیل فعالیت‌ها در بازه زمانی:
                  </Typography>
                  <ButtonGroup size="small" variant="outlined">
                    <Button
                      variant={timeWindowDays === 90 ? 'contained' : 'outlined'}
                      onClick={() => { setTimeWindowDays(90); void loadData(90) }}
                    >
                      ۳ ماهه
                    </Button>
                    <Button
                      variant={timeWindowDays === 180 ? 'contained' : 'outlined'}
                      onClick={() => { setTimeWindowDays(180); void loadData(180) }}
                    >
                      ۶ ماهه
                    </Button>
                    <Button
                      variant={timeWindowDays === 365 ? 'contained' : 'outlined'}
                      onClick={() => { setTimeWindowDays(365); void loadData(365) }}
                    >
                      یک‌ساله اخیر
                    </Button>
                  </ButtonGroup>
                </Stack>

                {/* Key Metric Summary Cards */}
                <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr 1fr', sm: 'repeat(4, 1fr)' }, gap: 2 }}>
                  <Card variant="outlined" sx={{ textAlign: 'center', py: 1, bgcolor: 'background.paper' }}>
                    <CardContent sx={{ p: '12px !important' }}>
                      <Typography variant="caption" color="text.secondary">
                        تعداد کل پیام‌ها
                      </Typography>
                      <Typography variant="h5" fontWeight={900} color="primary.main" sx={{ mt: 0.5 }}>
                        {profile?.messages_count || 0}
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        در پیام‌رسان ایتا
                      </Typography>
                    </CardContent>
                  </Card>

                  <Card variant="outlined" sx={{ textAlign: 'center', py: 1, bgcolor: 'background.paper' }}>
                    <CardContent sx={{ p: '12px !important' }}>
                      <Typography variant="caption" color="text.secondary">
                        گزارش‌های ثبت‌شده
                      </Typography>
                      <Typography variant="h5" fontWeight={900} color="success.main" sx={{ mt: 0.5 }}>
                        {profile?.reports_count || 0}
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        پرونده رویداد
                      </Typography>
                    </CardContent>
                  </Card>

                  <Card variant="outlined" sx={{ textAlign: 'center', py: 1, bgcolor: 'background.paper' }}>
                    <CardContent sx={{ p: '12px !important' }}>
                      <Typography variant="caption" color="text.secondary">
                        سهم از کل واحد قضایی
                      </Typography>
                      <Typography variant="h5" fontWeight={900} color="info.main" sx={{ mt: 0.5 }}>
                        {profile?.unit_participation_percentage || 0}٪
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        {profile?.unit_total_reports ? `از ${profile.unit_total_reports} گزارش واحد` : 'حوزه قضایی'}
                      </Typography>
                    </CardContent>
                  </Card>

                  <Card variant="outlined" sx={{ textAlign: 'center', py: 1, bgcolor: 'background.paper' }}>
                    <CardContent sx={{ p: '12px !important' }}>
                      <Typography variant="caption" color="text.secondary">
                        وضعیت گزارش‌ها
                      </Typography>
                      <Typography variant="h6" fontWeight={800} color="text.primary" sx={{ mt: 0.5 }}>
                        {profile?.reports_by_status?.approved || 0} <Typography component="span" variant="caption" color="success.main">تایید</Typography>
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        {profile?.reports_by_status?.needs_review || 0} در بررسی · {profile?.reports_by_status?.draft || 0} پیش‌نویس
                      </Typography>
                    </CardContent>
                  </Card>
                </Box>

                {/* Topic Breakdown Chart */}
                <Paper variant="outlined" sx={{ p: 2, bgcolor: 'background.paper' }}>
                  <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1.5 }}>
                    <BarChartRounded color="primary" />
                    <Typography variant="subtitle1" fontWeight={800}>
                      چارت فراوانی موضوعات گزارش‌های رابط
                    </Typography>
                  </Stack>

                  {(!profile?.topic_frequency || profile.topic_frequency.length === 0) ? (
                    <Box sx={{ py: 3, textAlign: 'center', color: 'text.secondary' }}>
                      <Typography variant="body2">
                        هنوز گزارشی با موضوع مشخص برای این کاربر در این بازه ثبت نشده است.
                      </Typography>
                    </Box>
                  ) : (
                    <Stack spacing={1.5}>
                      {profile.topic_frequency.map((t, idx) => (
                        <Box key={t.topic}>
                          <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 0.5 }}>
                            <Typography variant="body2" fontWeight={700}>
                              {idx + 1}. {t.topic}
                            </Typography>
                            <Stack direction="row" spacing={1} alignItems="center">
                              <Chip
                                size="small"
                                label={`${t.count} گزارش`}
                                sx={{ height: 20, fontSize: '0.72rem' }}
                              />
                              <Typography variant="caption" fontWeight={800} color="primary.main">
                                {t.percentage}٪
                              </Typography>
                            </Stack>
                          </Stack>
                          <LinearProgress
                            variant="determinate"
                            value={Math.min(100, t.percentage)}
                            sx={{
                              height: 8,
                              borderRadius: 4,
                              bgcolor: 'action.hover',
                              '& .MuiLinearProgress-bar': {
                                borderRadius: 4,
                                bgcolor: idx === 0 ? 'primary.main' : idx === 1 ? 'info.main' : 'success.main',
                              },
                            }}
                          />
                        </Box>
                      ))}
                    </Stack>
                  )}
                </Paper>

                {/* Comparative Unit Topic Breakdown */}
                {profile?.unit_topic_frequency && profile.unit_topic_frequency.length > 0 && (
                  <Paper variant="outlined" sx={{ p: 2, bgcolor: 'background.paper' }}>
                    <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1.5 }}>
                      <AccountBalanceRounded color="secondary" />
                      <Typography variant="subtitle1" fontWeight={800}>
                        مقایسه با فراوانی کل حوزه قضایی ({profile.unit_display_name})
                      </Typography>
                    </Stack>
                    <Stack spacing={1.5}>
                      {profile.unit_topic_frequency.slice(0, 5).map((ut) => (
                        <Box key={ut.topic}>
                          <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 0.5 }}>
                            <Typography variant="body2">
                              {ut.topic}
                            </Typography>
                            <Typography variant="caption" color="text.secondary">
                              {ut.count} مورد ({ut.percentage}٪)
                            </Typography>
                          </Stack>
                          <LinearProgress
                            variant="determinate"
                            value={Math.min(100, ut.percentage)}
                            color="secondary"
                            sx={{ height: 6, borderRadius: 3, bgcolor: 'action.hover' }}
                          />
                        </Box>
                      ))}
                    </Stack>
                  </Paper>
                )}

                {/* Recent Reports Table */}
                {profile?.recent_reports && profile.recent_reports.length > 0 && (
                  <Paper variant="outlined" sx={{ p: 2, bgcolor: 'background.paper' }}>
                    <Typography variant="subtitle1" fontWeight={800} sx={{ mb: 1.5 }}>
                      آخرین گزارش‌های ثبت‌شده این رابط
                    </Typography>
                    <TableContainer>
                      <Table size="small">
                        <TableHead>
                          <TableRow>
                            <TableCell sx={{ fontWeight: 800 }}>تاریخ رویداد</TableCell>
                            <TableCell sx={{ fontWeight: 800 }}>مناسبت / موضوع</TableCell>
                            <TableCell sx={{ fontWeight: 800 }}>حوزه قضایی</TableCell>
                            <TableCell sx={{ fontWeight: 800, textAlign: 'center' }}>وضعیت</TableCell>
                          </TableRow>
                        </TableHead>
                        <TableBody>
                          {profile.recent_reports.map((r) => (
                            <TableRow key={r.event_id} hover>
                              <TableCell dir="ltr" align="right">{r.occurred_on}</TableCell>
                              <TableCell sx={{ fontWeight: 700 }}>{r.occasion}</TableCell>
                              <TableCell>{r.unit_name || profile.unit_display_name}</TableCell>
                              <TableCell align="center">
                                <Chip
                                  size="small"
                                  label={
                                    r.review_status === 'approved' ? 'تاییدشده' :
                                    r.review_status === 'needs_review' ? 'در بررسی' :
                                    r.review_status === 'conflict' ? 'تعارض' : 'پیش‌نویس'
                                  }
                                  color={
                                    r.review_status === 'approved' ? 'success' :
                                    r.review_status === 'needs_review' ? 'warning' :
                                    r.review_status === 'conflict' ? 'error' : 'default'
                                  }
                                  sx={{ height: 22, fontSize: '0.72rem' }}
                                />
                              </TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </TableContainer>
                  </Paper>
                )}
              </Stack>
            )}

            {/* TAB 1: ASSIGNMENT SETTINGS */}
            {tab === 1 && (
              <Stack spacing={2.5}>
                <Paper variant="outlined" sx={{ p: 2, bgcolor: 'background.paper' }}>
                  <FormControlLabel
                    control={
                      <Switch
                        checked={isLiaison}
                        onChange={e => setIsLiaison(e.target.checked)}
                        color="primary"
                      />
                    }
                    label={
                      <Box>
                        <Typography variant="subtitle1" fontWeight={800}>
                          این کاربر رابط فرهنگی است
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          با فعال‌سازی این گزینه، پیام‌ها و گزارش‌های این نویسنده به صورت خودکار به حوزه قضایی متناظر پیوند می‌خورد.
                        </Typography>
                      </Box>
                    }
                  />
                </Paper>

                {isLiaison && (
                  <Paper variant="outlined" sx={{ p: 2.5, bgcolor: 'background.paper' }}>
                    <Typography variant="subtitle1" fontWeight={800} sx={{ mb: 2 }}>
                      انتخاب حوزه قضایی و مشخصات رابط
                    </Typography>

                    <Stack spacing={2}>
                      <Autocomplete
                        options={units}
                        groupBy={option => option.county || 'سایر'}
                        getOptionLabel={option => option.display_name || option.name}
                        isOptionEqualToValue={(option, val) => option.unit_id === val.unit_id}
                        value={selectedUnit}
                        onChange={(_, val) => setSelectedUnit(val)}
                        renderInput={params => (
                          <TextField
                            {...params}
                            label="حوزه یا واحد قضایی (با قابلیت سرچ)"
                            placeholder="جستجوی نام شهرستان یا واحد (مثلاً ساری - دادگستری)..."
                            required
                            helperText="حوزه‌ها بر اساس شهرستان دسته‌بندی شده‌اند."
                          />
                        )}
                      />

                      <TextField
                        label="نام و نام خانوادگی رابط"
                        value={fullName}
                        onChange={e => setFullName(e.target.value)}
                        required
                        fullWidth
                      />

                      <TextField
                        label="شماره تماس (پیش‌فرض از مخاطبین محلی)"
                        value={phone}
                        onChange={e => setPhone(e.target.value)}
                        placeholder="0911..."
                        fullWidth
                        InputProps={{
                          startAdornment: <InputAdornment position="start"><PhoneRounded fontSize="small" /></InputAdornment>,
                        }}
                      />

                      <TextField
                        label="کلمات کلیدی برای تطبیق خودکار (با ویرگول جدا کنید)"
                        value={matchKeywords}
                        onChange={e => setMatchKeywords(e.target.value)}
                        placeholder="نام خانوادگی، نام واحد، شهرستان..."
                        helperText="در صورتی که پیام فاقد آی‌دی دقیق باشد، با این کلمات به عنوان گزارش این رابط شناخته می‌شود."
                        fullWidth
                      />

                      <TextField
                        label="یادداشت‌های داخلی"
                        value={notes}
                        onChange={e => setNotes(e.target.value)}
                        multiline
                        rows={2}
                        fullWidth
                      />

                      {/* Display title preview */}
                      <Alert severity="info" icon={<PersonRounded />} sx={{ mt: 1 }}>
                        <Typography variant="caption" color="text.secondary" display="block">
                          پیش‌نمایش عنوان نمایشی نویسنده در تمام پیام‌ها و گزارش‌ها:
                        </Typography>
                        <Typography variant="subtitle2" fontWeight={800} color="primary.main">
                          {selectedUnit ? `${fullName || authorName} - حوزه قضایی ${selectedUnit.display_name}` : fullName || authorName}
                        </Typography>
                      </Alert>
                    </Stack>
                  </Paper>
                )}

                {profile?.is_liaison && (
                  <Stack direction="row" justifyContent="flex-end">
                    <Button
                      color="error"
                      variant="outlined"
                      startIcon={<DeleteOutlineRounded />}
                      onClick={handleUnlink}
                      disabled={saving}
                    >
                      لغو انتساب به عنوان رابط
                    </Button>
                  </Stack>
                )}
              </Stack>
            )}
          </>
        )}
      </DialogContent>

      <Divider />

      <DialogActions sx={{ px: 3, py: 2, justifyContent: 'space-between', bgcolor: 'background.paper' }}>
        <Button onClick={onClose} color="inherit">
          بستن
        </Button>
        {tab === 1 && (
          <Button
            variant="contained"
            color="primary"
            startIcon={saving ? <CircularProgress size={18} color="inherit" /> : <SaveRounded />}
            onClick={handleSaveLiaison}
            disabled={saving || (isLiaison && !selectedUnit)}
          >
            ذخیره تغییرات رابط
          </Button>
        )}
      </DialogActions>
    </Dialog>
  )
}
