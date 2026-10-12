import { useEffect, useState, useCallback, useMemo } from 'react'
import {
  Alert,
  Box,
  Button,
  Card,
  CardActions,
  CardContent,
  Checkbox,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  FormControl,
  FormControlLabel,
  Grid,
  IconButton,
  InputLabel,
  LinearProgress,
  MenuItem,
  OutlinedInput,
  Paper,
  Radio,
  RadioGroup,
  Select,
  Stack,
  Switch,
  Tab,
  Tabs,
  TextField,
  ToggleButton,
  ToggleButtonGroup,
  Tooltip,
  Typography,
  useMediaQuery,
  useTheme,
} from '@mui/material'
import CloseRounded from '@mui/icons-material/CloseRounded'
import RefreshRounded from '@mui/icons-material/RefreshRounded'
import AddTaskRounded from '@mui/icons-material/AddTaskRounded'
import CheckCircleRounded from '@mui/icons-material/CheckCircleRounded'
import ReplayRounded from '@mui/icons-material/ReplayRounded'
import AssignmentTurnedInRounded from '@mui/icons-material/AssignmentTurnedInRounded'
import WarningRounded from '@mui/icons-material/WarningRounded'
import SwapHorizRounded from '@mui/icons-material/SwapHorizRounded'
import MenuBookRounded from '@mui/icons-material/MenuBookRounded'
import CampaignRounded from '@mui/icons-material/CampaignRounded'
import AccessTimeFilledRounded from '@mui/icons-material/AccessTimeFilledRounded'
import PlaylistAddCheckRounded from '@mui/icons-material/PlaylistAddCheckRounded'
import AddCircleOutlineRounded from '@mui/icons-material/AddCircleOutlineRounded'
import DeleteOutlineRounded from '@mui/icons-material/DeleteOutlineRounded'
import BusinessRounded from '@mui/icons-material/BusinessRounded'
import PersonRounded from '@mui/icons-material/PersonRounded'
import type { StaffTask, StaffTaskChecklistItem } from './lib/types'
import { api } from './lib/api'

type Props = {
  open: boolean
  onClose: () => void
  initialMessageRef?: string
  currentUserRole?: 'admin' | 'user'
  currentUserName?: string
}

export const WORKBOOK_APPROVED_PROGRAMS = [
  { code: '80401', title: '۸۰۴۰۱ - اردو (فرهنگی، زیارتی و سیاحتی)' },
  { code: '80402', title: '۸۰۴۰۲ - مسابقات (قرآن، عترت، نماز، فرهنگی و ورزشی)' },
  { code: '80403', title: '۸۰۴۰۳ - مراسم مذهبی، ملی و انقلابی' },
  { code: '80501', title: '۸۰۵۰۱ - ترویج و توسعه فرهنگ اقامه نماز' },
  { code: '80406', title: '۸۰۴۰۶ - تکریم و تجلیل (همکاران، ایثارگران، بازنشستگان و نخبگان)' },
  { code: '80601', title: '۸۰۶۰۱ - تشویق ارباب رجوع' },
  { code: '80202', title: '۸۰۲۰۲ - منشور اخلاقی' },
  { code: '80000', title: '۸۰۰۰۰ - قالب گزارش عملکرد (روایی-مالی)' },
]

export const TASK_KIND_LABELS: Record<string, string> = {
  defect_resolution: 'رفع نقص اطلاعات یا مستندات',
  event_registration: 'ثبت و تکمیل شناسنامه رویداد',
  field_execution: 'اجرای میدانی یا پشتیبانی مراسم',
  media_production: 'تولید محتوا، عکاسی و تدوین',
  inquiry_followup: 'پیگیری از حوزه‌های قضایی تابعه',
  general: 'امور محوله اداری و عمومی',
}

export const DEFECT_LABELS: Record<string, string> = {
  missing_attendees: 'نقص در تعداد شرکت‌کنندگان',
  ambiguous_program: 'ابهام در نوع برنامه/مراسم',
  missing_occasion: 'نقص در عنوان مناسبت',
  judiciary_involvement: 'نیاز به احراز انتساب به دادگستری',
  general_defect: 'نقص عمومی در گزارش',
}

export const UNIT_SCOPE_LABELS: Record<string, string> = {
  provincial_hq: 'ستاد دادگستری کل استان',
  judicial_domain: 'حوزه قضایی شهرستان / دادگستری شهرستان',
  specialized_court: 'دادگاه‌های صلح / تجدیدنظر / انقلاب',
  affiliated_org: 'سازمان‌های تابعه قوه قضائیه',
}

export const PRIORITY_LABELS: Record<string, { label: string; color: 'default' | 'info' | 'warning' | 'error' }> = {
  low: { label: 'کم‌اهمیت', color: 'default' },
  medium: { label: 'عادی', color: 'info' },
  high: { label: 'مهم', color: 'warning' },
  urgent: { label: 'فوری', color: 'error' },
}

interface UserOption {
  app_user_id: string
  display_name: string
  username: string
}

export function StaffTasksDialog({
  open,
  onClose,
  initialMessageRef,
  currentUserRole = 'admin',
  currentUserName = 'مدیر سیستم',
}: Props) {
  const theme = useTheme()
  const fullScreen = useMediaQuery(theme.breakpoints.down('md'))
  const [tab, setTab] = useState<'all' | 'open' | 'in_progress' | 'resolved' | 'closed'>('all')
  const [macroFilter, setMacroFilter] = useState<'all' | 'workbook_approved' | 'other_cultural'>('all')
  const [showOverdueOnly, setShowOverdueOnly] = useState(false)
  const [tasks, setTasks] = useState<StaffTask[]>([])
  const [loading, setLoading] = useState(false)
  const [users, setUsers] = useState<UserOption[]>([])

  // Create Task Modal State
  const [createOpen, setCreateOpen] = useState(false)
  const [macroCategory, setMacroCategory] = useState<'workbook_approved' | 'other_cultural'>('workbook_approved')
  const [selectedProgramCodes, setSelectedProgramCodes] = useState<string[]>([])
  const [customTopic, setCustomTopic] = useState('')
  const [taskKind, setTaskKind] = useState<string>('defect_resolution')
  const [newTitle, setNewTitle] = useState('')
  const [newDescription, setNewDescription] = useState('')
  const [newDefectType, setNewDefectType] = useState('missing_attendees')
  const [newPriority, setNewPriority] = useState<'low' | 'medium' | 'high' | 'urgent'>('medium')
  const [unitScope, setUnitScope] = useState('provincial_hq')
  const [unitName, setUnitName] = useState('')
  const [assignedUserId, setAssignedUserId] = useState('')
  const [assignedUserName, setAssignedUserName] = useState('')
  const [dueDate, setDueDate] = useState('')
  const [checklistItems, setChecklistItems] = useState<{ id: string; text: string; done: boolean }[]>([
    { id: '1', text: 'بررسی صحت مستندات و انطباق با دستورالعمل', done: false },
    { id: '2', text: 'ثبت دقیق آمار مخاطبان و شاخص‌ها در سامانه', done: false },
  ])
  const [newChecklistText, setNewChecklistText] = useState('')
  const [requiresApproval, setRequiresApproval] = useState(true)
  const [savingTask, setSavingTask] = useState(false)

  // Resolve Modal State
  const [resolveTaskId, setResolveTaskId] = useState<string | null>(null)
  const [resolveNotes, setResolveNotes] = useState('')

  // Reassign Modal State
  const [reassignTaskId, setReassignTaskId] = useState<string | null>(null)
  const [reassignTargetUserId, setReassignTargetUserId] = useState('')
  const [reassignTargetName, setReassignTargetName] = useState('')
  const [reassignReason, setReassignReason] = useState('')
  const [reassigning, setReassigning] = useState(false)

  const loadTasks = useCallback(async () => {
    setLoading(true)
    try {
      const queryParams = new URLSearchParams()
      if (tab !== 'all') queryParams.set('status', tab)
      if (macroFilter !== 'all') queryParams.set('macro_category', macroFilter)
      const res = await api<{ ok: boolean; tasks: StaffTask[] }>(
        'GET',
        `/api/v2/staff/tasks?${queryParams.toString()}`
      )
      if (res.ok) {
        setTasks(res.tasks || [])
      }
    } catch {
      setTasks([])
    } finally {
      setLoading(false)
    }
  }, [tab, macroFilter])

  useEffect(() => {
    if (open) {
      void loadTasks()
      api<{ ok: boolean; users?: UserOption[] }>('GET', '/api/v2/app-users')
        .then((res) => {
          if (res.ok && Array.isArray(res.users)) {
            setUsers(res.users)
          }
        })
        .catch(() => {})
    }
  }, [open, loadTasks])

  const filteredTasks = useMemo(() => {
    if (!showOverdueOnly) return tasks
    const now = new Date()
    return tasks.filter((t) => {
      if (!t.due_date || t.status === 'closed' || t.status === 'resolved') return false
      return new Date(t.due_date) < now
    })
  }, [tasks, showOverdueOnly])

  const isTaskOverdue = (task: StaffTask) => {
    if (!task.due_date || task.status === 'closed' || task.status === 'resolved') return false
    return new Date(task.due_date) < new Date()
  }

  const handleCreateTask = async () => {
    if (!newTitle.trim()) return
    setSavingTask(true)
    try {
      await api('POST', '/api/v2/staff/tasks', {
        title: newTitle.trim(),
        description: newDescription.trim(),
        defect_type: taskKind === 'defect_resolution' ? newDefectType : 'general',
        priority: newPriority,
        macro_category: macroCategory,
        program_codes: macroCategory === 'workbook_approved' ? selectedProgramCodes : [],
        custom_topic: macroCategory === 'other_cultural' ? customTopic.trim() : '',
        task_kind: taskKind,
        unit_scope: unitScope,
        unit_name: unitName.trim(),
        assigned_to_user_id: assignedUserId.trim(),
        assigned_to_name: assignedUserName.trim() || 'کارمند فرهنگی',
        created_by_name: currentUserName,
        due_date: dueDate.trim() || null,
        checklist: checklistItems,
        requires_manager_approval: requiresApproval,
        event_id: initialMessageRef || '',
      })
      setCreateOpen(false)
      // Reset form
      setNewTitle('')
      setNewDescription('')
      setSelectedProgramCodes([])
      setCustomTopic('')
      setAssignedUserId('')
      setAssignedUserName('')
      setDueDate('')
      setChecklistItems([
        { id: '1', text: 'بررسی صحت مستندات و انطباق با دستورالعمل', done: false },
        { id: '2', text: 'ثبت دقیق آمار مخاطبان و شاخص‌ها در سامانه', done: false },
      ])
      void loadTasks()
    } catch {
      // error handled
    } finally {
      setSavingTask(false)
    }
  }

  const handleChecklistToggle = async (task: StaffTask, itemId: string) => {
    const currentList = task.checklist || []
    const updated = currentList.map((item) =>
      item.id === itemId ? { ...item, done: !item.done } : item
    )
    // Optimistic local update
    setTasks((prev) =>
      prev.map((t) => (t.task_id === task.task_id ? { ...t, checklist: updated } : t))
    )
    try {
      await api('POST', '/api/v2/staff/tasks/checklist', {
        task_id: task.task_id,
        checklist: updated,
      })
    } catch {
      void loadTasks()
    }
  }

  const handleResolveTask = async () => {
    if (!resolveTaskId) return
    try {
      await api('POST', '/api/v2/staff/tasks/resolve', {
        task_id: resolveTaskId,
        resolution_notes: resolveNotes.trim(),
        resolved_by: currentUserName,
      })
      setResolveTaskId(null)
      setResolveNotes('')
      void loadTasks()
    } catch {
      // error
    }
  }

  const handleCloseTask = async (taskId: string, approved: boolean) => {
    try {
      await api('POST', '/api/v2/staff/tasks/close', {
        task_id: taskId,
        approved,
        closed_by: currentUserName,
      })
      void loadTasks()
    } catch {
      // error
    }
  }

  const handleReassignTask = async () => {
    if (!reassignTaskId || !reassignTargetName.trim()) return
    setReassigning(true)
    try {
      await api('POST', '/api/v2/staff/tasks/reassign', {
        task_id: reassignTaskId,
        assigned_to_user_id: reassignTargetUserId,
        assigned_to_name: reassignTargetName.trim(),
        reassigned_by_name: currentUserName,
        reason: reassignReason.trim() || 'ارجاع به علت عدم اقدام در مهلت مقرر یا انتقال وظیفه',
      })
      setReassignTaskId(null)
      setReassignTargetUserId('')
      setReassignTargetName('')
      setReassignReason('')
      void loadTasks()
    } catch {
      // error
    } finally {
      setReassigning(false)
    }
  }

  const addChecklistItem = () => {
    if (!newChecklistText.trim()) return
    setChecklistItems((prev) => [
      ...prev,
      { id: String(Date.now()), text: newChecklistText.trim(), done: false },
    ])
    setNewChecklistText('')
  }

  const removeChecklistItem = (id: string) => {
    setChecklistItems((prev) => prev.filter((item) => item.id !== id))
  }

  const applyDatePreset = (days: number) => {
    const target = new Date()
    target.setDate(target.getDate() + days)
    const yyyy = target.getFullYear()
    const mm = String(target.getMonth() + 1).padStart(2, '0')
    const dd = String(target.getDate()).padStart(2, '0')
    setDueDate(`${yyyy}-${mm}-${dd}`)
  }

  return (
    <Dialog
      open={open}
      onClose={onClose}
      fullScreen={fullScreen}
      maxWidth="lg"
      fullWidth
      aria-labelledby="staff-tasks-title"
    >
      <DialogTitle id="staff-tasks-title" sx={{ pb: 1, borderBottom: 1, borderColor: 'divider' }}>
        <Stack direction="row" alignItems="center" justifyContent="space-between" flexWrap="wrap" gap={1}>
          <Stack direction="row" spacing={1.5} alignItems="center">
            <AddTaskRounded color="primary" sx={{ fontSize: 32 }} />
            <Box>
              <Typography variant="h6" fontWeight={800}>
                مرکز هدایت و مدیریت وظایف سازمانی کارکنان
              </Typography>
              <Typography variant="caption" color="text.secondary">
                چارچوب کلان‌برنامه‌ها (مصوب کاربرگ ۱۴۰۵ / سایر برنامه‌های فرهنگی)، قلمرو ماده ۲۳ و کنترل بازبینی
              </Typography>
            </Box>
          </Stack>
          <Stack direction="row" spacing={1} alignItems="center">
            {currentUserRole === 'admin' && (
              <Button
                variant="contained"
                size="small"
                startIcon={<AddTaskRounded />}
                onClick={() => setCreateOpen(true)}
              >
                تعریف وظیفه جدید
              </Button>
            )}
            <IconButton onClick={loadTasks} disabled={loading} size="small" title="بارگذاری مجدد">
              <RefreshRounded />
            </IconButton>
            <IconButton onClick={onClose} size="small">
              <CloseRounded />
            </IconButton>
          </Stack>
        </Stack>
      </DialogTitle>

      <DialogContent sx={{ bgcolor: 'background.default', p: { xs: 1.5, sm: 2.5 } }}>
        <Stack spacing={2}>
          {/* Macro Category Filter Bar */}
          <Paper variant="outlined" sx={{ p: 1.5, display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 1.5 }}>
            <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap">
              <Typography variant="body2" fontWeight={700} sx={{ mr: 1 }}>
                سرفصل کلان:
              </Typography>
              <ToggleButtonGroup
                value={macroFilter}
                exclusive
                size="small"
                onChange={(_, val) => val && setMacroFilter(val)}
              >
                <ToggleButton value="all">
                  همه عناوین
                </ToggleButton>
                <ToggleButton value="workbook_approved" sx={{ gap: 0.5 }}>
                  <MenuBookRounded fontSize="small" />
                  برنامه‌های مصوب کاربرگ ۱۴۰۵
                </ToggleButton>
                <ToggleButton value="other_cultural" sx={{ gap: 0.5 }}>
                  <CampaignRounded fontSize="small" />
                  سایر برنامه‌های فرهنگی
                </ToggleButton>
              </ToggleButtonGroup>
            </Stack>

            <FormControlLabel
              control={
                <Switch
                  checked={showOverdueOnly}
                  onChange={(e) => setShowOverdueOnly(e.target.checked)}
                  color="error"
                  size="small"
                />
              }
              label={
                <Typography variant="body2" color={showOverdueOnly ? 'error.main' : 'text.secondary'} fontWeight={600}>
                  فقط وظایف دارای تاخیر / مهلت‌گذشته
                </Typography>
              }
            />
          </Paper>

          {/* Status Tabs */}
          <Tabs
            value={tab}
            onChange={(_, val) => setTab(val)}
            variant="scrollable"
            scrollButtons="auto"
          >
            <Tab label="همه وظایف" value="all" />
            <Tab label="باز / منتظر اقدام" value="open" />
            <Tab label="در جریان پیگیری" value="in_progress" />
            <Tab label="حل‌شده (منتظر تایید مدیر)" value="resolved" />
            <Tab label="مختومه / تایید نهایی" value="closed" />
          </Tabs>

          {loading ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
              <CircularProgress />
            </Box>
          ) : filteredTasks.length === 0 ? (
            <Paper variant="outlined" sx={{ p: 6, textAlign: 'center' }}>
              <Typography color="text.secondary">هیچ وظیفه‌ای با این مشخصات و فیلتر یافت نشد.</Typography>
            </Paper>
          ) : (
            <Stack spacing={2}>
              {filteredTasks.map((task) => {
                const prio = PRIORITY_LABELS[task.priority] || PRIORITY_LABELS.medium
                const overdue = isTaskOverdue(task)
                const isWorkbook = (task.macro_category || 'workbook_approved') === 'workbook_approved'
                const checklist = task.checklist || []
                const completedChecklistCount = checklist.filter((c) => c.done).length

                return (
                  <Card
                    key={task.task_id}
                    variant="outlined"
                    sx={{
                      borderColor: overdue ? 'error.main' : undefined,
                      borderWidth: overdue ? 1.5 : 1,
                      transition: 'all 0.2s ease',
                      '&:hover': { boxShadow: 2 },
                    }}
                  >
                    <CardContent sx={{ pb: 1.5 }}>
                      <Stack direction="row" justifyContent="space-between" alignItems="flex-start" gap={1.5} flexWrap="wrap">
                        <Box minWidth={0} sx={{ flex: 1 }}>
                          {/* Badges row */}
                          <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" sx={{ mb: 1, gap: 0.5 }}>
                            <Chip
                              size="small"
                              icon={isWorkbook ? <MenuBookRounded /> : <CampaignRounded />}
                              label={isWorkbook ? 'مصوب کاربرگ ۱۴۰۵' : 'سایر برنامه‌های فرهنگی'}
                              color={isWorkbook ? 'primary' : 'secondary'}
                              variant="filled"
                            />

                            <Chip
                              size="small"
                              label={prio.label}
                              color={prio.color}
                              variant="outlined"
                            />

                            <Chip
                              size="small"
                              label={TASK_KIND_LABELS[task.task_kind || 'general'] || 'امور محوله'}
                              variant="outlined"
                              sx={{ bgcolor: 'action.hover' }}
                            />

                            {task.unit_name && (
                              <Chip
                                size="small"
                                icon={<BusinessRounded />}
                                label={`${UNIT_SCOPE_LABELS[task.unit_scope || 'provincial_hq'] || 'واحد'}: ${task.unit_name}`}
                                variant="outlined"
                              />
                            )}

                            {overdue && (
                              <Chip
                                size="small"
                                icon={<AccessTimeFilledRounded />}
                                label={`مهلت گذشته (${task.due_date})`}
                                color="error"
                                variant="filled"
                              />
                            )}
                            {!overdue && task.due_date && (
                              <Chip
                                size="small"
                                icon={<AccessTimeFilledRounded />}
                                label={`سررسید: ${task.due_date}`}
                                variant="outlined"
                              />
                            )}
                          </Stack>

                          {/* Title */}
                          <Typography variant="h6" fontWeight={800} sx={{ fontSize: '1.05rem', mb: 0.5 }}>
                            {task.title}
                          </Typography>

                          {/* Multi-program dimension chips if workbook_approved */}
                          {isWorkbook && Array.isArray(task.program_codes) && task.program_codes.length > 0 && (
                            <Stack direction="row" spacing={0.5} flexWrap="wrap" sx={{ mb: 1 }}>
                              <Typography variant="caption" color="text.secondary" sx={{ alignSelf: 'center', ml: 0.5 }}>
                                ابعاد برنامه‌ای:
                              </Typography>
                              {task.program_codes.map((code) => {
                                const prog = WORKBOOK_APPROVED_PROGRAMS.find((p) => p.code === code)
                                return (
                                  <Chip
                                    key={code}
                                    size="small"
                                    label={prog ? prog.title : `کد ${code}`}
                                    variant="outlined"
                                    color="info"
                                    sx={{ fontSize: '0.75rem' }}
                                  />
                                )
                              })}
                            </Stack>
                          )}

                          {/* Custom Topic if other_cultural */}
                          {!isWorkbook && task.custom_topic && (
                            <Box sx={{ mb: 1 }}>
                              <Typography variant="body2" sx={{ fontWeight: 600, color: 'secondary.main' }}>
                                محور برنامه: {task.custom_topic}
                              </Typography>
                            </Box>
                          )}

                          {/* Description */}
                          {task.description && (
                            <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5, whiteSpace: 'pre-line' }}>
                              {task.description}
                            </Typography>
                          )}

                          {/* Deliverables Checklist */}
                          {checklist.length > 0 && (
                            <Box sx={{ mt: 1.5, p: 1.5, bgcolor: 'background.paper', borderRadius: 1, border: 1, borderColor: 'divider' }}>
                              <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 1 }}>
                                <Typography variant="caption" fontWeight={700} color="text.secondary" sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                                  <PlaylistAddCheckRounded fontSize="small" />
                                  چک‌لیست اقلام تحویلی و بازبینی ({completedChecklistCount} از {checklist.length})
                                </Typography>
                                <LinearProgress
                                  variant="determinate"
                                  value={(completedChecklistCount / checklist.length) * 100}
                                  sx={{ width: 80, height: 6, borderRadius: 3 }}
                                />
                              </Stack>
                              <Stack spacing={0.5}>
                                {checklist.map((item) => (
                                  <FormControlLabel
                                    key={item.id}
                                    control={
                                      <Checkbox
                                        size="small"
                                        checked={item.done}
                                        onChange={() => handleChecklistToggle(task, item.id)}
                                      />
                                    }
                                    label={
                                      <Typography
                                        variant="body2"
                                        sx={{
                                          textDecoration: item.done ? 'line-through' : 'none',
                                          color: item.done ? 'text.secondary' : 'text.primary',
                                        }}
                                      >
                                        {item.text}
                                      </Typography>
                                    }
                                  />
                                ))}
                              </Stack>
                            </Box>
                          )}

                          {/* Resolution Notes */}
                          {task.resolution_notes && (
                            <Alert severity="info" sx={{ mt: 1.5, py: 0.5, whiteSpace: 'pre-line' }}>
                              <Typography variant="caption" fontWeight={700} display="block">
                                گزارش و یادداشت‌های اقدام:
                              </Typography>
                              <Typography variant="body2">{task.resolution_notes}</Typography>
                            </Alert>
                          )}
                        </Box>

                        <Chip
                          size="small"
                          label={
                            task.status === 'open'
                              ? 'باز'
                              : task.status === 'in_progress'
                              ? 'در جریان'
                              : task.status === 'resolved'
                              ? 'حل‌شده'
                              : 'مختومه'
                          }
                          color={
                            task.status === 'closed'
                              ? 'success'
                              : task.status === 'resolved'
                              ? 'info'
                              : task.status === 'in_progress'
                              ? 'warning'
                              : 'default'
                          }
                        />
                      </Stack>
                    </CardContent>

                    <CardActions sx={{ px: 2, pb: 1.5, pt: 0, justifyContent: 'space-between', flexWrap: 'wrap', gap: 1 }}>
                      <Typography variant="caption" color="text.secondary">
                        مسئول: <strong>{task.assigned_to_name || 'نامشخص'}</strong> · ارجاع‌دهنده: {task.created_by_name || 'مدیر'} · ثبت: {task.created_at.slice(0, 10)}
                      </Typography>

                      <Stack direction="row" spacing={1} flexWrap="wrap">
                        {/* Reassign action for managers if task is not closed */}
                        {currentUserRole === 'admin' && task.status !== 'closed' && (
                          <Button
                            size="small"
                            variant="outlined"
                            color="secondary"
                            startIcon={<SwapHorizRounded />}
                            onClick={() => {
                              setReassignTaskId(task.task_id)
                              setReassignTargetUserId('')
                              setReassignTargetName('')
                              setReassignReason('')
                            }}
                          >
                            ارجاع به دیگری
                          </Button>
                        )}

                        {task.status !== 'closed' && (
                          <Button
                            size="small"
                            variant="outlined"
                            color="info"
                            startIcon={<AssignmentTurnedInRounded />}
                            onClick={() => {
                              setResolveTaskId(task.task_id)
                              setResolveNotes(task.resolution_notes || '')
                            }}
                          >
                            ثبت اقدامات و رفع نقص
                          </Button>
                        )}

                        {currentUserRole === 'admin' && task.status === 'resolved' && (
                          <Button
                            size="small"
                            variant="contained"
                            color="success"
                            startIcon={<CheckCircleRounded />}
                            onClick={() => handleCloseTask(task.task_id, true)}
                          >
                            تایید و مختومه کردن
                          </Button>
                        )}

                        {currentUserRole === 'admin' && task.status === 'closed' && (
                          <Button
                            size="small"
                            variant="text"
                            color="warning"
                            startIcon={<ReplayRounded />}
                            onClick={() => handleCloseTask(task.task_id, false)}
                          >
                            بازگشایی مجدد
                          </Button>
                        )}
                      </Stack>
                    </CardActions>
                  </Card>
                )
              })}
            </Stack>
          )}
        </Stack>
      </DialogContent>

      <DialogActions sx={{ px: 2.5, py: 1.5, borderTop: 1, borderColor: 'divider' }}>
        <Button onClick={onClose} variant="outlined">
          بستن
        </Button>
      </DialogActions>

      {/* Enterprise Create Task Modal */}
      <Dialog
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        maxWidth="md"
        fullWidth
        fullScreen={fullScreen}
      >
        <DialogTitle sx={{ pb: 1, borderBottom: 1, borderColor: 'divider' }}>
          <Stack direction="row" alignItems="center" spacing={1}>
            <AddTaskRounded color="primary" />
            <Box>
              <Typography variant="h6" fontWeight={800}>
                تعریف و ارجاع وظیفه / ماموریت سازمانی
              </Typography>
              <Typography variant="caption" color="text.secondary">
                انتساب دقیق به سرفصل‌های کلان، ماده ۲۳ دادگستری و استانداردهای پایش
              </Typography>
            </Box>
          </Stack>
        </DialogTitle>
        <DialogContent dividers sx={{ p: 2.5 }}>
          <Stack spacing={2.5}>
            {/* Section 1: Macro Category */}
            <Paper variant="outlined" sx={{ p: 2, bgcolor: 'background.default' }}>
              <Typography variant="subtitle2" fontWeight={800} color="primary.main" sx={{ mb: 1 }}>
                ۱. سرفصل کلان و قلمرو راهبردی برنامه
              </Typography>
              <RadioGroup
                row
                value={macroCategory}
                onChange={(e) => setMacroCategory(e.target.value as any)}
                sx={{ mb: 1.5 }}
              >
                <FormControlLabel
                  value="workbook_approved"
                  control={<Radio size="small" />}
                  label="برنامه‌های مصوب و ابلاغی (کاربرگ رسمی ۱۴۰۵)"
                />
                <FormControlLabel
                  value="other_cultural"
                  control={<Radio size="small" />}
                  label="سایر فعالیت‌های فرهنگی (اقدامات آزاد و خارج از شیت‌ها)"
                />
              </RadioGroup>

              {macroCategory === 'workbook_approved' ? (
                <FormControl fullWidth size="small">
                  <InputLabel id="program-codes-select-label">ابعاد برنامه‌های عملیاتی کاربرگ (چندانتخابی)</InputLabel>
                  <Select
                    labelId="program-codes-select-label"
                    multiple
                    value={selectedProgramCodes}
                    onChange={(e) => {
                      const val = e.target.value
                      setSelectedProgramCodes(typeof val === 'string' ? val.split(',') : val)
                    }}
                    input={<OutlinedInput label="ابعاد برنامه‌های عملیاتی کاربرگ (چندانتخابی)" />}
                    renderValue={(selected) => (
                      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                        {selected.map((value) => {
                          const p = WORKBOOK_APPROVED_PROGRAMS.find((item) => item.code === value)
                          return <Chip key={value} label={p ? p.title : value} size="small" />
                        })}
                      </Box>
                    )}
                  >
                    {WORKBOOK_APPROVED_PROGRAMS.map((prog) => (
                      <MenuItem key={prog.code} value={prog.code}>
                        <Checkbox checked={selectedProgramCodes.indexOf(prog.code) > -1} size="small" />
                        <Typography variant="body2">{prog.title}</Typography>
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
              ) : (
                <TextField
                  label="عنوان یا محور آزاد فعالیت فرهنگی"
                  placeholder="مثال: پویش همدلی و کمک مومنانه / نمایشگاه دستاوردها / موکب اربعین"
                  value={customTopic}
                  onChange={(e) => setCustomTopic(e.target.value)}
                  fullWidth
                  size="small"
                  required
                />
              )}
            </Paper>

            {/* Section 2: Task Identity & Nature */}
            <Paper variant="outlined" sx={{ p: 2, bgcolor: 'background.default' }}>
              <Typography variant="subtitle2" fontWeight={800} color="primary.main" sx={{ mb: 1.5 }}>
                ۲. هویت و ماهیت وظیفه
              </Typography>
              <Grid container spacing={2}>
                <Grid size={{ xs: 12, sm: 8 }}>
                  <TextField
                    label="عنوان دقیق وظیفه / ماموریت"
                    placeholder="مثال: تکمیل اطلاعات و مستندات اردوی خانوادگی مشهد"
                    value={newTitle}
                    onChange={(e) => setNewTitle(e.target.value)}
                    fullWidth
                    size="small"
                    required
                  />
                </Grid>
                <Grid size={{ xs: 12, sm: 4 }}>
                  <FormControl fullWidth size="small">
                    <InputLabel id="task-kind-label">ماهیت کار</InputLabel>
                    <Select
                      labelId="task-kind-label"
                      value={taskKind}
                      label="ماهیت کار"
                      onChange={(e) => setTaskKind(e.target.value)}
                    >
                      {Object.entries(TASK_KIND_LABELS).map(([k, v]) => (
                        <MenuItem key={k} value={k}>
                          {v}
                        </MenuItem>
                      ))}
                    </Select>
                  </FormControl>
                </Grid>

                {taskKind === 'defect_resolution' && (
                  <Grid size={{ xs: 12, sm: 6 }}>
                    <FormControl fullWidth size="small">
                      <InputLabel id="defect-type-label">نوع نقص گزارش</InputLabel>
                      <Select
                        labelId="defect-type-label"
                        value={newDefectType}
                        label="نوع نقص گزارش"
                        onChange={(e) => setNewDefectType(e.target.value)}
                      >
                        {Object.entries(DEFECT_LABELS).map(([k, v]) => (
                          <MenuItem key={k} value={k}>
                            {v}
                          </MenuItem>
                        ))}
                      </Select>
                    </FormControl>
                  </Grid>
                )}

                <Grid size={{ xs: 12, sm: taskKind === 'defect_resolution' ? 6 : 12 }}>
                  <FormControl fullWidth size="small">
                    <InputLabel id="priority-label">اولویت اقدام</InputLabel>
                    <Select
                      labelId="priority-label"
                      value={newPriority}
                      label="اولویت اقدام"
                      onChange={(e) => setNewPriority(e.target.value as any)}
                    >
                      <MenuItem value="low">کم‌اهمیت</MenuItem>
                      <MenuItem value="medium">عادی</MenuItem>
                      <MenuItem value="high">مهم</MenuItem>
                      <MenuItem value="urgent">فوری</MenuItem>
                    </Select>
                  </FormControl>
                </Grid>

                <Grid size={{ xs: 12 }}>
                  <TextField
                    label="توضیحات و دستورالعمل اجرایی مدیر"
                    placeholder="شرح انتظارات، الزامات اجرایی و نکات تکمیلی..."
                    multiline
                    rows={3}
                    value={newDescription}
                    onChange={(e) => setNewDescription(e.target.value)}
                    fullWidth
                    size="small"
                  />
                </Grid>
              </Grid>
            </Paper>

            {/* Section 3: Unit Scope (Article 23) */}
            <Paper variant="outlined" sx={{ p: 2, bgcolor: 'background.default' }}>
              <Typography variant="subtitle2" fontWeight={800} color="primary.main" sx={{ mb: 1.5 }}>
                ۳. حوزه جغرافیایی و سازمانی (ماده ۲۳ آیین‌نامه)
              </Typography>
              <Grid container spacing={2}>
                <Grid size={{ xs: 12, sm: 6 }}>
                  <FormControl fullWidth size="small">
                    <InputLabel id="unit-scope-label">قلمرو سازمانی</InputLabel>
                    <Select
                      labelId="unit-scope-label"
                      value={unitScope}
                      label="قلمرو سازمانی"
                      onChange={(e) => setUnitScope(e.target.value)}
                    >
                      {Object.entries(UNIT_SCOPE_LABELS).map(([k, v]) => (
                        <MenuItem key={k} value={k}>
                          {v}
                        </MenuItem>
                      ))}
                    </Select>
                  </FormControl>
                </Grid>
                <Grid size={{ xs: 12, sm: 6 }}>
                  <TextField
                    label="نام دقیق حوزه قضایی / شهرستان"
                    placeholder="مثال: دادگستری کاشان / دادگاه صلح نجف‌آباد / ستاد استان"
                    value={unitName}
                    onChange={(e) => setUnitName(e.target.value)}
                    fullWidth
                    size="small"
                  />
                </Grid>
              </Grid>
            </Paper>

            {/* Section 4: Assignee & Due Date (SLA) */}
            <Paper variant="outlined" sx={{ p: 2, bgcolor: 'background.default' }}>
              <Typography variant="subtitle2" fontWeight={800} color="primary.main" sx={{ mb: 1.5 }}>
                ۴. انتساب سازمانی و سررسید زمانی (SLA)
              </Typography>
              <Grid container spacing={2}>
                <Grid size={{ xs: 12, sm: 6 }}>
                  {users.length > 0 ? (
                    <FormControl fullWidth size="small">
                      <InputLabel id="assignee-select-label">ارجاع به کارمند / رابط</InputLabel>
                      <Select
                        labelId="assignee-select-label"
                        value={assignedUserId}
                        label="ارجاع به کارمند / رابط"
                        onChange={(e) => {
                          const uid = e.target.value
                          setAssignedUserId(uid)
                          const u = users.find((item) => item.app_user_id === uid)
                          if (u) setAssignedUserName(u.display_name || u.username)
                        }}
                      >
                        {users.map((u) => (
                          <MenuItem key={u.app_user_id} value={u.app_user_id}>
                            {u.display_name || u.username} ({u.username})
                          </MenuItem>
                        ))}
                      </Select>
                    </FormControl>
                  ) : (
                    <TextField
                      label="نام کارمند / رابط مسئول"
                      placeholder="مثال: علی محمدی"
                      value={assignedUserName}
                      onChange={(e) => setAssignedUserName(e.target.value)}
                      fullWidth
                      size="small"
                    />
                  )}
                </Grid>
                <Grid size={{ xs: 12, sm: 6 }}>
                  <Stack spacing={1}>
                    <TextField
                      label="مهلت اقدام (سررسید YYYY-MM-DD)"
                      type="date"
                      value={dueDate}
                      onChange={(e) => setDueDate(e.target.value)}
                      fullWidth
                      size="small"
                      InputLabelProps={{ shrink: true }}
                    />
                    <Stack direction="row" spacing={1}>
                      <Button size="small" variant="text" onClick={() => applyDatePreset(1)}>
                        +۱ روز
                      </Button>
                      <Button size="small" variant="text" onClick={() => applyDatePreset(3)}>
                        +۳ روز
                      </Button>
                      <Button size="small" variant="text" onClick={() => applyDatePreset(7)}>
                        +۱ هفته
                      </Button>
                    </Stack>
                  </Stack>
                </Grid>
              </Grid>
            </Paper>

            {/* Section 5: Deliverables Checklist */}
            <Paper variant="outlined" sx={{ p: 2, bgcolor: 'background.default' }}>
              <Typography variant="subtitle2" fontWeight={800} color="primary.main" sx={{ mb: 1 }}>
                ۵. چک‌لیست اقلام تحویلی و تایید نهایی
              </Typography>
              <Typography variant="caption" color="text.secondary" display="block" sx={{ mb: 1.5 }}>
                تعریف سنجه‌های روشن جهت بررسی دقیق کار قبل از تایید مدیر
              </Typography>

              <Stack spacing={1} sx={{ mb: 1.5 }}>
                {checklistItems.map((item, idx) => (
                  <Stack key={item.id} direction="row" spacing={1} alignItems="center">
                    <Typography variant="body2" sx={{ minWidth: 20 }}>
                      {idx + 1}.
                    </Typography>
                    <Typography variant="body2" sx={{ flex: 1 }}>
                      {item.text}
                    </Typography>
                    <IconButton size="small" color="error" onClick={() => removeChecklistItem(item.id)}>
                      <DeleteOutlineRounded fontSize="small" />
                    </IconButton>
                  </Stack>
                ))}
              </Stack>

              <Stack direction="row" spacing={1}>
                <TextField
                  placeholder="عنوان آیتم تحویلی جدید (مثال: بارگذاری عکس باکیفیت و صورتجلسه)"
                  value={newChecklistText}
                  onChange={(e) => setNewChecklistText(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      e.preventDefault()
                      addChecklistItem()
                    }
                  }}
                  size="small"
                  fullWidth
                />
                <Button variant="outlined" size="small" startIcon={<AddCircleOutlineRounded />} onClick={addChecklistItem}>
                  افزودن
                </Button>
              </Stack>

              <Divider sx={{ my: 1.5 }} />

              <FormControlLabel
                control={
                  <Checkbox
                    checked={requiresApproval}
                    onChange={(e) => setRequiresApproval(e.target.checked)}
                    size="small"
                    color="primary"
                  />
                }
                label={
                  <Typography variant="body2" fontWeight={600}>
                    الزام به تایید و کنترل کیفیت توسط مدیر پیش از مختومه شدن وظیفه
                  </Typography>
                }
              />
            </Paper>
          </Stack>
        </DialogContent>
        <DialogActions sx={{ px: 2.5, py: 1.5, borderTop: 1, borderColor: 'divider' }}>
          <Button onClick={() => setCreateOpen(false)}>انصراف</Button>
          <Button
            variant="contained"
            onClick={handleCreateTask}
            disabled={savingTask || !newTitle.trim()}
          >
            {savingTask ? 'در حال ثبت…' : 'ثبت و ابلاغ وظیفه'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Resolve Task Modal */}
      <Dialog open={Boolean(resolveTaskId)} onClose={() => setResolveTaskId(null)} maxWidth="sm" fullWidth>
        <DialogTitle sx={{ borderBottom: 1, borderColor: 'divider' }}>ثبت اقدامات و رفع نقص</DialogTitle>
        <DialogContent sx={{ pt: 2 }}>
          <Stack spacing={2}>
            <Typography variant="body2" color="text.secondary">
              لطفاً اقدامات انجام شده، مستندات دریافت شده یا توضیحات رفع ابهام را با ذکر جزئیات وارد فرمایید:
            </Typography>
            <TextField
              label="گزارش اقدام کارمند"
              multiline
              rows={4}
              value={resolveNotes}
              onChange={(e) => setResolveNotes(e.target.value)}
              fullWidth
              size="small"
              required
            />
          </Stack>
        </DialogContent>
        <DialogActions sx={{ px: 2.5, py: 1.5, borderTop: 1, borderColor: 'divider' }}>
          <Button onClick={() => setResolveTaskId(null)}>انصراف</Button>
          <Button
            variant="contained"
            color="success"
            onClick={handleResolveTask}
            disabled={!resolveNotes.trim()}
          >
            تایید و ثبت اقدامات
          </Button>
        </DialogActions>
      </Dialog>

      {/* Reassign Task Modal */}
      <Dialog open={Boolean(reassignTaskId)} onClose={() => setReassignTaskId(null)} maxWidth="sm" fullWidth>
        <DialogTitle sx={{ borderBottom: 1, borderColor: 'divider' }}>
          <Stack direction="row" spacing={1} alignItems="center">
            <SwapHorizRounded color="secondary" />
            <Typography variant="h6" fontWeight={800}>
              ارجاع مجدد وظیفه به کارمند دیگر
            </Typography>
          </Stack>
        </DialogTitle>
        <DialogContent sx={{ pt: 2 }}>
          <Stack spacing={2}>
            <Alert severity="warning" sx={{ py: 0.5 }}>
              در صورت عدم اقدام در موعد مقرر، مرخصی یا نیاز به جابجایی مسئولیت، می‌توانید این ماموریت را به کارمند دیگری محول فرمایید.
            </Alert>

            {users.length > 0 ? (
              <FormControl fullWidth size="small">
                <InputLabel id="reassign-user-select-label">انتخاب کارمند جدید</InputLabel>
                <Select
                  labelId="reassign-user-select-label"
                  value={reassignTargetUserId}
                  label="انتخاب کارمند جدید"
                  onChange={(e) => {
                    const uid = e.target.value
                    setReassignTargetUserId(uid)
                    const u = users.find((item) => item.app_user_id === uid)
                    if (u) setReassignTargetName(u.display_name || u.username)
                  }}
                >
                  {users.map((u) => (
                    <MenuItem key={u.app_user_id} value={u.app_user_id}>
                      {u.display_name || u.username} ({u.username})
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            ) : (
              <TextField
                label="نام کارمند جدید"
                placeholder="مثال: رضا احمدی"
                value={reassignTargetName}
                onChange={(e) => setReassignTargetName(e.target.value)}
                fullWidth
                size="small"
                required
              />
            )}

            <TextField
              label="علت ارجاع مجدد"
              placeholder="مثال: عدم اقدام در مهلت مقرر / مرخصی کارمند قبلی / تغییر حوزه مسئولیت"
              multiline
              rows={3}
              value={reassignReason}
              onChange={(e) => setReassignReason(e.target.value)}
              fullWidth
              size="small"
            />
          </Stack>
        </DialogContent>
        <DialogActions sx={{ px: 2.5, py: 1.5, borderTop: 1, borderColor: 'divider' }}>
          <Button onClick={() => setReassignTaskId(null)}>انصراف</Button>
          <Button
            variant="contained"
            color="secondary"
            onClick={handleReassignTask}
            disabled={reassigning || !reassignTargetName.trim()}
          >
            {reassigning ? 'در حال ارجاع…' : 'تایید و ارجاع مجدد'}
          </Button>
        </DialogActions>
      </Dialog>
    </Dialog>
  )
}
