import { useEffect, useState } from 'react'
import {
  Autocomplete,
  Box,
  Button,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  IconButton,
  Stack,
  TextField,
  Typography,
} from '@mui/material'
import CloseRounded from '@mui/icons-material/CloseRounded'
import StyleRounded from '@mui/icons-material/StyleRounded'
import SettingsRounded from '@mui/icons-material/SettingsRounded'
import AddRounded from '@mui/icons-material/AddRounded'
import { type MicroIndicatorItem, fetchMicroIndicators } from '../lib/indicators'

type MicroIndicatorEditPopoverProps = {
  open: boolean
  onClose: () => void
  currentMicroIndicators: string[]
  onSave: (microIndicators: string[]) => Promise<void>
  onOpenManagement: () => void
}

export function MicroIndicatorEditPopover({
  open,
  onClose,
  currentMicroIndicators,
  onSave,
  onOpenManagement,
}: MicroIndicatorEditPopoverProps) {
  const [selectedList, setSelectedList] = useState<string[]>(currentMicroIndicators || [])
  const [availableItems, setAvailableItems] = useState<MicroIndicatorItem[]>([])
  const [inputValue, setInputValue] = useState('')
  const [saving, setSaving] = useState(false)

  const loadIndicators = async () => {
    try {
      const data = await fetchMicroIndicators()
      setAvailableItems(data)
    } catch {
      // ignore
    }
  }

  useEffect(() => {
    if (open) {
      setSelectedList(currentMicroIndicators || [])
      setInputValue('')
      void loadIndicators()
    }
  }, [open, currentMicroIndicators])

  const handleAdd = (value: string) => {
    const trimmed = value.trim()
    if (!trimmed) return
    if (!selectedList.includes(trimmed)) {
      setSelectedList(prev => [...prev, trimmed])
    }
    setInputValue('')
  }

  const handleDelete = (title: string) => {
    setSelectedList(prev => prev.filter(item => item !== title))
  }

  const handleToggle = (title: string) => {
    if (selectedList.includes(title)) {
      handleDelete(title)
    } else {
      handleAdd(title)
    }
  }

  const handleConfirm = async () => {
    setSaving(true)
    try {
      await onSave(selectedList)
      onClose()
    } finally {
      setSaving(false)
    }
  }

  const existingTitles = availableItems.map(item => item.title)

  return (
    <Dialog
      open={open}
      onClose={saving ? undefined : onClose}
      maxWidth="sm"
      fullWidth
      dir="rtl"
    >
      <DialogTitle sx={{ m: 0, p: 2, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <Stack direction="row" spacing={1} alignItems="center">
          <StyleRounded color="secondary" />
          <Typography variant="h6" fontWeight={700}>
            شاخصه‌های جزئی پیام
          </Typography>
        </Stack>
        <IconButton aria-label="بستن" onClick={onClose} disabled={saving} size="small" sx={{ color: 'text.secondary' }}>
          <CloseRounded fontSize="small" />
        </IconButton>
      </DialogTitle>

      <DialogContent dividers sx={{ p: 2 }}>
        {/* Currently assigned chips */}
        <Typography variant="subtitle2" fontWeight={700} sx={{ mb: 1 }}>
          شاخصه‌های جزئی انتساب‌یافته:
        </Typography>
        <Box sx={{ minHeight: 48, p: 1, border: 1, borderColor: 'divider', borderRadius: 1.5, mb: 2, bgcolor: 'background.paper' }}>
          {selectedList.length === 0 ? (
            <Typography variant="caption" color="text.secondary" sx={{ p: 1, display: 'block' }}>
              هنوز شاخصه جزئی‌ای انتخاب یا تایپ نشده است.
            </Typography>
          ) : (
            <Stack direction="row" flexWrap="wrap" gap={0.75}>
              {selectedList.map(title => (
                <Chip
                  key={title}
                  label={title}
                  size="small"
                  color="secondary"
                  variant="filled"
                  onDelete={() => handleDelete(title)}
                  sx={{ fontWeight: 500 }}
                />
              ))}
            </Stack>
          )}
        </Box>

        {/* FreeSolo typing / autocomplete input */}
        <Typography variant="subtitle2" fontWeight={700} sx={{ mb: 1 }}>
          تایپ مستقیم یا انتخاب شاخصه جدید:
        </Typography>
        <Stack direction="row" spacing={1} sx={{ mb: 2 }}>
          <Autocomplete
            freeSolo
            options={existingTitles}
            value={inputValue}
            onInputChange={(_, newInputValue) => setInputValue(newInputValue)}
            onChange={(_, newValue) => {
              if (typeof newValue === 'string' && newValue.trim()) {
                handleAdd(newValue)
              }
            }}
            fullWidth
            size="small"
            renderInput={params => (
              <TextField
                {...params}
                placeholder="عنوان شاخصه جزئی را تایپ کنید و Enter بزنید..."
                onKeyDown={e => {
                  if (e.key === 'Enter') {
                    e.preventDefault()
                    handleAdd(inputValue)
                  }
                }}
              />
            )}
          />
          <Button
            variant="contained"
            color="secondary"
            startIcon={<AddRounded />}
            onClick={() => handleAdd(inputValue)}
            disabled={!inputValue.trim()}
            sx={{ minWidth: 100 }}
          >
            افزودن
          </Button>
        </Stack>

        {/* Suggestions from catalog */}
        {availableItems.length > 0 && (
          <>
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1 }}>
              شاخصه‌های متداول (برای انتخاب سریع کلیک کنید):
            </Typography>
            <Stack direction="row" flexWrap="wrap" gap={0.5} sx={{ mb: 2 }}>
              {availableItems.slice(0, 16).map(item => {
                const isSelected = selectedList.includes(item.title)
                return (
                  <Chip
                    key={item.indicator_id}
                    label={item.title}
                    size="small"
                    variant={isSelected ? 'filled' : 'outlined'}
                    color={isSelected ? 'secondary' : 'default'}
                    onClick={() => handleToggle(item.title)}
                    sx={{ cursor: 'pointer', fontSize: '0.75rem', fontWeight: isSelected ? 600 : 400 }}
                  />
                )
              })}
            </Stack>
          </>
        )}

        <Divider sx={{ my: 1.5 }} />

        <Button
          size="small"
          variant="text"
          color="info"
          startIcon={<SettingsRounded />}
          onClick={() => {
            onClose()
            onOpenManagement()
          }}
        >
          مدیریت عناوین شاخصه‌های جزئی (فهرست کامل و ویرایش)...
        </Button>
      </DialogContent>

      <DialogActions sx={{ p: 2, justifyContent: 'space-between' }}>
        <Button onClick={() => setSelectedList([])} disabled={saving || selectedList.length === 0} color="inherit" size="small">
          پاکسازی همه
        </Button>
        <Stack direction="row" spacing={1}>
          <Button onClick={onClose} disabled={saving} color="inherit">
            انصراف
          </Button>
          <Button onClick={handleConfirm} disabled={saving} variant="contained" color="secondary">
            {saving ? 'در حال ثبت...' : 'ذخیره شاخصه‌ها'}
          </Button>
        </Stack>
      </DialogActions>
    </Dialog>
  )
}
