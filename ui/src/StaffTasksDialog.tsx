import { useEffect, useState, useCallback } from 'react'
import {
  Alert,
  Box,
  Button,
  Card,
  CardActions,
  CardContent,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControl,
  Grid,
  IconButton,
  InputLabel,
  MenuItem,
  Paper,
  Select,
  Stack,
  Tab,
  Tabs,
  TextField,
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
import type { StaffTask } from './lib/types'
import { api } from './lib/api'

type Props = {
  open: boolean
  onClose: () => void
  initialMessageRef?: string
  currentUserRole?: 'admin' | 'user'
  currentUserName?: string
}

const DEFECT_LABELS: Record<string, string> = {
  missing_attendees: 'نقص در تعداد شرکت‌کنندگان',
  ambiguous_program: 'ابهام در نوع برنامه/مراسم',
  missing_occasion: 'نقص در عنوان مناسبت',
  judiciary_involvement: 'نیاز به احراز انتساب به دادگستری',
  general_defect: 'نقص عمومی در گزارش',
}

const PRIORITY_LABELS: Record<string, { label: string; color: 'default' | 'info' | 'warning' | 'error' }> = {
  low: { label: 'کم‌اهمیت', color: 'default' },
  medium: { label: 'عادی', color: 'info' },
  high: { label: 'مهم', color: 'warning' },
  urgent: { label: 'فوری', color: 'error' },
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
  const [tasks, setTasks] = useState<StaffTask[]>([])
  const [loading, setLoading] = useState(false)
  const [createOpen, setCreateOpen] = useState(false)
  const [resolveTaskId, setResolveTaskId] = useState<string | null>(null)
  const [resolveNotes, setResolveNotes] = useState('')

  // New task form state
  const [newTitle, setNewTitle] = useState('')
  const [newDefectType, setNewDefectType] = useState('missing_attendees')
  const [newPriority, setNewPriority] = useState<'low' | 'medium' | 'high' | 'urgent'>('medium')
  const [newAssignee, setNewAssignee] = useState('')
  const [newDescription, setNewDescription] = useState('')
  const [savingTask, setSavingTask] = useState(false)

  const loadTasks = useCallback(async () => {
    setLoading(true)
    try {
      const queryParams = new URLSearchParams()
      if (tab !== 'all') queryParams.set('status', tab)
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
  }, [tab])

  useEffect(() => {
    if (open) {
      void loadTasks()
    }
  }, [open, loadTasks])

  const handleCreateTask = async () => {
    if (!newTitle.trim()) return
    setSavingTask(true)
    try {
      await api('POST', '/api/v2/staff/tasks', {
        title: newTitle.trim(),
        defect_type: newDefectType,
        priority: newPriority,
        description: newDescription.trim(),
        assigned_to_name: newAssignee.trim() || 'کارمند فرهنگی',
        created_by_name: currentUserName,
        message_ref: initialMessageRef || '',
      })
      setCreateOpen(false)
      setNewTitle('')
      setNewDescription('')
      setNewAssignee('')
      void loadTasks()
    } catch (err) {
      // error handling
    } finally {
      setSavingTask(false)
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
      // error handling
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
      // error handling
    }
  }

  return (
    <Dialog
      open={open}
      onClose={onClose}
      fullScreen={fullScreen}
      maxWidth="md"
      fullWidth
      aria-labelledby="staff-tasks-title"
    >
      <DialogTitle id="staff-tasks-title" sx={{ pb: 1 }}>
        <Stack direction="row" alignItems="center" justifyContent="space-between">
          <Stack direction="row" spacing={1.5} alignItems="center">
            <AddTaskRounded color="primary" />
            <Box>
              <Typography variant="h6" fontWeight={800}>
                مدیریت نواقص و پیگیری وظایف کارمندان
              </Typography>
              <Typography variant="caption" color="text.secondary">
                ارجاع نقص‌های گزارش‌ها و پیام‌ها به کارمندان محلی و بررسی صحت رفع نقص
              </Typography>
            </Box>
          </Stack>
          <Stack direction="row" spacing={1} alignItems="center">
            <Button
              variant="contained"
              size="small"
              startIcon={<AddTaskRounded />}
              onClick={() => setCreateOpen(true)}
            >
              ثبت نقص جدید
            </Button>
            <IconButton onClick={loadTasks} disabled={loading} size="small" title="بارگذاری مجدد">
              <RefreshRounded />
            </IconButton>
            <IconButton onClick={onClose} size="small">
              <CloseRounded />
            </IconButton>
          </Stack>
        </Stack>
      </DialogTitle>

      <DialogContent dividers sx={{ bgcolor: 'background.default', p: { xs: 1.5, sm: 2.5 } }}>
        <Stack spacing={2}>
          <Tabs
            value={tab}
            onChange={(_, val) => setTab(val)}
            variant="scrollable"
            scrollButtons="auto"
          >
            <Tab label="همه وظایف" value="all" />
            <Tab label="باز / منتظر پیگیری" value="open" />
            <Tab label="در حال پیگیری" value="in_progress" />
            <Tab label="حل‌شده (منتظر تایید)" value="resolved" />
            <Tab label="مختومه / تایید مدیر" value="closed" />
          </Tabs>

          {loading ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}>
              <CircularProgress />
            </Box>
          ) : tasks.length === 0 ? (
            <Paper variant="outlined" sx={{ p: 5, textAlign: 'center' }}>
              <Typography color="text.secondary">هیچ وظیفه نقصی در این وضعیت ثبت نشده است.</Typography>
            </Paper>
          ) : (
            <Stack spacing={1.5}>
              {tasks.map((task) => {
                const prio = PRIORITY_LABELS[task.priority] || PRIORITY_LABELS.medium
                return (
                  <Card key={task.task_id} variant="outlined">
                    <CardContent sx={{ pb: 1 }}>
                      <Stack direction="row" justifyContent="space-between" alignItems="flex-start" gap={1}>
                        <Box minWidth={0}>
                          <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap">
                            <Chip
                              size="small"
                              label={prio.label}
                              color={prio.color}
                              variant="filled"
                            />
                            <Chip
                              size="small"
                              label={DEFECT_LABELS[task.defect_type] || task.defect_type}
                              variant="outlined"
                            />
                            <Typography variant="subtitle2" fontWeight={800}>
                              {task.title}
                            </Typography>
                          </Stack>
                          {task.description && (
                            <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                              {task.description}
                            </Typography>
                          )}
                          {task.resolution_notes && (
                            <Alert severity="success" sx={{ mt: 1.5, py: 0.5 }}>
                              <Typography variant="body2" fontWeight={700}>
                                توضیحات رفع نقص توسط کارمند:
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

                    <CardActions sx={{ px: 2, pb: 1.5, pt: 0, justifyContent: 'space-between', flexWrap: 'wrap' }}>
                      <Typography variant="caption" color="text.secondary">
                        مسئول: <strong>{task.assigned_to_name || 'نامشخص'}</strong> · ارجاع‌دهنده: {task.created_by_name || 'مدیر'}
                      </Typography>

                      <Stack direction="row" spacing={1}>
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
                            ثبت رفع نقص
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
                            تایید و بستن وظیفه
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

      <DialogActions sx={{ px: 2.5, py: 1.5 }}>
        <Button onClick={onClose} variant="outlined">
          بستن
        </Button>
      </DialogActions>

      {/* Create Task Modal */}
      <Dialog open={createOpen} onClose={() => setCreateOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>ثبت وظیفه پیگیری و رفع نقص پیام</DialogTitle>
        <DialogContent dividers>
          <Stack spacing={2} sx={{ pt: 1 }}>
            <TextField
              label="عنوان نقص یا موضوع پیگیری"
              value={newTitle}
              onChange={(e) => setNewTitle(e.target.value)}
              fullWidth
              size="small"
              required
            />

            <FormControl fullWidth size="small">
              <InputLabel id="defect-type-label">نوع نقص</InputLabel>
              <Select
                labelId="defect-type-label"
                value={newDefectType}
                label="نوع نقص"
                onChange={(e) => setNewDefectType(e.target.value)}
              >
                {Object.entries(DEFECT_LABELS).map(([k, v]) => (
                  <MenuItem key={k} value={k}>
                    {v}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>

            <FormControl fullWidth size="small">
              <InputLabel id="priority-label">اولویت</InputLabel>
              <Select
                labelId="priority-label"
                value={newPriority}
                label="اولویت"
                onChange={(e) => setNewPriority(e.target.value as any)}
              >
                <MenuItem value="low">کم‌اهمیت</MenuItem>
                <MenuItem value="medium">عادی</MenuItem>
                <MenuItem value="high">مهم</MenuItem>
                <MenuItem value="urgent">فوری</MenuItem>
              </Select>
            </FormControl>

            <TextField
              label="ارجاع به کارمند / رابط محلی"
              placeholder="مثال: علی محمدی"
              value={newAssignee}
              onChange={(e) => setNewAssignee(e.target.value)}
              fullWidth
              size="small"
            />

            <TextField
              label="توضیحات و دستور پیگیری"
              multiline
              rows={3}
              value={newDescription}
              onChange={(e) => setNewDescription(e.target.value)}
              fullWidth
              size="small"
            />
          </Stack>
        </DialogContent>
        <DialogActions sx={{ px: 2.5, py: 1.5 }}>
          <Button onClick={() => setCreateOpen(false)}>انصراف</Button>
          <Button
            variant="contained"
            onClick={handleCreateTask}
            disabled={savingTask || !newTitle.trim()}
          >
            {savingTask ? 'در حال ثبت…' : 'ثبت و ارجاع'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Resolve Task Modal */}
      <Dialog open={Boolean(resolveTaskId)} onClose={() => setResolveTaskId(null)} maxWidth="sm" fullWidth>
        <DialogTitle>ثبت اقدامات و رفع نقص</DialogTitle>
        <DialogContent dividers>
          <Stack spacing={2} sx={{ pt: 1 }}>
            <Typography variant="body2" color="text.secondary">
              لطفاً اقدامات انجام شده یا اطلاعات تکمیلی دریافت شده را توضیح دهید:
            </Typography>
            <TextField
              label="توضیحات رفع نقص"
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
        <DialogActions sx={{ px: 2.5, py: 1.5 }}>
          <Button onClick={() => setResolveTaskId(null)}>انصراف</Button>
          <Button
            variant="contained"
            color="success"
            onClick={handleResolveTask}
            disabled={!resolveNotes.trim()}
          >
            تایید و ثبت رفع نقص
          </Button>
        </DialogActions>
      </Dialog>
    </Dialog>
  )
}
