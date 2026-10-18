import { useEffect, useState } from 'react'
import {
  Box,
  Button,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  IconButton,
  InputAdornment,
  List,
  ListItem,
  ListItemSecondaryAction,
  ListItemText,
  Stack,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material'
import CloseRounded from '@mui/icons-material/CloseRounded'
import AddRounded from '@mui/icons-material/AddRounded'
import DeleteRounded from '@mui/icons-material/DeleteRounded'
import EditRounded from '@mui/icons-material/EditRounded'
import SearchRounded from '@mui/icons-material/SearchRounded'
import CategoryRounded from '@mui/icons-material/CategoryRounded'
import CheckRounded from '@mui/icons-material/CheckRounded'
import {
  type MicroIndicatorItem,
  deleteMicroIndicator,
  fetchMicroIndicators,
  saveMicroIndicator,
  updateMicroIndicator,
} from '../lib/indicators'

type MicroIndicatorsManagementModalProps = {
  open: boolean
  onClose: () => void
  onIndicatorsChanged?: () => void
}

export function MicroIndicatorsManagementModal({
  open,
  onClose,
  onIndicatorsChanged,
}: MicroIndicatorsManagementModalProps) {
  const [items, setItems] = useState<MicroIndicatorItem[]>([])
  const [loading, setLoading] = useState(false)
  const [search, setSearch] = useState('')

  // Add new form
  const [newTitle, setNewTitle] = useState('')
  const [newCategory, setNewCategory] = useState('')
  const [adding, setAdding] = useState(false)
  const [errorMsg, setErrorMsg] = useState('')

  // Edit form state
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editTitle, setEditTitle] = useState('')
  const [editCategory, setEditCategory] = useState('')
  const [updating, setUpdating] = useState(false)

  const loadData = async () => {
    setLoading(true)
    try {
      const data = await fetchMicroIndicators()
      setItems(data)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (open) {
      void loadData()
      setSearch('')
      setNewTitle('')
      setNewCategory('')
      setEditingId(null)
      setErrorMsg('')
    }
  }, [open])

  const handleAdd = async () => {
    const trimmed = newTitle.trim()
    if (!trimmed) return
    setAdding(true)
    setErrorMsg('')
    try {
      await saveMicroIndicator({
        title: trimmed,
        category: newCategory.trim() || undefined,
      })
      setNewTitle('')
      setNewCategory('')
      await loadData()
      onIndicatorsChanged?.()
    } catch (err: any) {
      setErrorMsg(err.message || 'خطا در ثبت شاخصه جزئی')
    } finally {
      setAdding(false)
    }
  }

  const handleStartEdit = (item: MicroIndicatorItem) => {
    setEditingId(item.indicator_id)
    setEditTitle(item.title)
    setEditCategory(item.category || '')
  }

  const handleSaveEdit = async (indicatorId: string) => {
    const trimmed = editTitle.trim()
    if (!trimmed) return
    setUpdating(true)
    setErrorMsg('')
    try {
      await updateMicroIndicator(indicatorId, {
        title: trimmed,
        category: editCategory.trim() || undefined,
      })
      setEditingId(null)
      await loadData()
      onIndicatorsChanged?.()
    } catch (err: any) {
      setErrorMsg(err.message || 'خطا در ویرایش شاخصه جزئی')
    } finally {
      setUpdating(false)
    }
  }

  const handleDelete = async (indicatorId: string) => {
    if (!window.confirm('آیا از حذف این شاخصه جزئی اطمینان دارید؟')) return
    setErrorMsg('')
    try {
      await deleteMicroIndicator(indicatorId)
      await loadData()
      onIndicatorsChanged?.()
    } catch (err: any) {
      setErrorMsg(err.message || 'خطا در حذف شاخصه جزئی')
    }
  }

  const filteredItems = items.filter(item => {
    if (!search.trim()) return true
    const q = search.trim().toLowerCase()
    return (
      item.title.toLowerCase().includes(q) ||
      (item.category && item.category.toLowerCase().includes(q))
    )
  })

  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth dir="rtl">
      <DialogTitle sx={{ m: 0, p: 2, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <Stack direction="row" spacing={1} alignItems="center">
          <CategoryRounded color="secondary" />
          <Typography variant="h6" fontWeight={700}>
            مدیریت شاخصه‌های جزئی
          </Typography>
        </Stack>
        <IconButton aria-label="بستن" onClick={onClose} size="small" sx={{ color: 'text.secondary' }}>
          <CloseRounded fontSize="small" />
        </IconButton>
      </DialogTitle>

      <DialogContent dividers sx={{ p: 2 }}>
        {errorMsg && (
          <Box sx={{ mb: 2, p: 1.5, bgcolor: 'error.lighter', color: 'error.main', borderRadius: 1 }}>
            <Typography variant="body2">{errorMsg}</Typography>
          </Box>
        )}

        {/* Add new micro indicator box */}
        <Box
          sx={{
            p: 2,
            mb: 2,
            bgcolor: 'action.hover',
            borderRadius: 2,
            border: 1,
            borderColor: 'divider',
          }}
        >
          <Typography variant="subtitle2" fontWeight={700} sx={{ mb: 1.5 }}>
            تعریف شاخصه جزئی جدید
          </Typography>
          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5} alignItems="center">
            <TextField
              size="small"
              placeholder="عنوان شاخصه جزئی (مثلاً: نماز جماعت، زیارت عاشورا...)"
              value={newTitle}
              onChange={e => setNewTitle(e.target.value)}
              disabled={adding}
              sx={{ flex: 2 }}
            />
            <TextField
              size="small"
              placeholder="دسته‌بندی اختیاری (مثلاً: مذهبی)"
              value={newCategory}
              onChange={e => setNewCategory(e.target.value)}
              disabled={adding}
              sx={{ flex: 1 }}
            />
            <Button
              variant="contained"
              color="secondary"
              startIcon={adding ? <CircularProgress size={16} color="inherit" /> : <AddRounded />}
              onClick={handleAdd}
              disabled={adding || !newTitle.trim()}
              sx={{ minWidth: 120 }}
            >
              افزودن
            </Button>
          </Stack>
        </Box>

        {/* Search bar */}
        <TextField
          size="small"
          placeholder="جستجو در شاخصه‌های جزئی..."
          value={search}
          onChange={e => setSearch(e.target.value)}
          fullWidth
          sx={{ mb: 2 }}
          InputProps={{
            startAdornment: (
              <InputAdornment position="start">
                <SearchRounded fontSize="small" color="action" />
              </InputAdornment>
            ),
          }}
        />

        {/* List of items */}
        {loading ? (
          <Stack alignItems="center" sx={{ py: 4 }}>
            <CircularProgress size={28} />
          </Stack>
        ) : filteredItems.length === 0 ? (
          <Typography variant="body2" color="text.secondary" sx={{ textAlign: 'center', py: 3 }}>
            شاخصه‌ای یافت نشد.
          </Typography>
        ) : (
          <List disablePadding>
            {filteredItems.map(item => {
              const isEditing = editingId === item.indicator_id
              return (
                <ListItem
                  key={item.indicator_id}
                  sx={{
                    border: 1,
                    borderColor: 'divider',
                    borderRadius: 1.5,
                    mb: 1,
                    p: 1.5,
                    bgcolor: isEditing ? 'action.selected' : 'background.paper',
                  }}
                >
                  {isEditing ? (
                    <Stack direction="row" spacing={1} alignItems="center" sx={{ width: '100%', pr: 10 }}>
                      <TextField
                        size="small"
                        value={editTitle}
                        onChange={e => setEditTitle(e.target.value)}
                        disabled={updating}
                        sx={{ flex: 2 }}
                      />
                      <TextField
                        size="small"
                        placeholder="دسته‌بندی"
                        value={editCategory}
                        onChange={e => setEditCategory(e.target.value)}
                        disabled={updating}
                        sx={{ flex: 1 }}
                      />
                      <IconButton
                        size="small"
                        color="primary"
                        onClick={() => handleSaveEdit(item.indicator_id)}
                        disabled={updating || !editTitle.trim()}
                      >
                        <CheckRounded fontSize="small" />
                      </IconButton>
                      <IconButton size="small" onClick={() => setEditingId(null)} disabled={updating}>
                        <CloseRounded fontSize="small" />
                      </IconButton>
                    </Stack>
                  ) : (
                    <>
                      <ListItemText
                        primary={
                          <Stack direction="row" spacing={1} alignItems="center">
                            <Typography variant="body2" fontWeight={600}>
                              {item.title}
                            </Typography>
                            {item.category && (
                              <Chip
                                size="small"
                                label={item.category}
                                variant="outlined"
                                sx={{ height: 20, fontSize: '0.65rem' }}
                              />
                            )}
                            <Typography variant="caption" color="text.secondary">
                              (کاربرد: {item.usage_count || 0})
                            </Typography>
                          </Stack>
                        }
                      />
                      <ListItemSecondaryAction sx={{ left: 16, right: 'auto' }}>
                        <Stack direction="row" spacing={0.5}>
                          <Tooltip title="ویرایش">
                            <IconButton size="small" onClick={() => handleStartEdit(item)}>
                              <EditRounded fontSize="small" />
                            </IconButton>
                          </Tooltip>
                          <Tooltip title="حذف">
                            <IconButton
                              size="small"
                              color="error"
                              onClick={() => handleDelete(item.indicator_id)}
                            >
                              <DeleteRounded fontSize="small" />
                            </IconButton>
                          </Tooltip>
                        </Stack>
                      </ListItemSecondaryAction>
                    </>
                  )}
                </ListItem>
              )
            })}
          </List>
        )}
      </DialogContent>

      <DialogActions sx={{ p: 2 }}>
        <Button onClick={onClose} variant="contained" color="inherit">
          بستن
        </Button>
      </DialogActions>
    </Dialog>
  )
}
