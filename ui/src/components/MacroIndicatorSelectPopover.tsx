import { useState } from 'react'
import {
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  IconButton,
  List,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Radio,
  Stack,
  Typography,
} from '@mui/material'
import CloseRounded from '@mui/icons-material/CloseRounded'
import BookmarkRounded from '@mui/icons-material/BookmarkRounded'
import { MACRO_INDICATORS } from '../lib/indicators'

type MacroIndicatorSelectPopoverProps = {
  open: boolean
  onClose: () => void
  currentValue: string
  onSelect: (macro: string) => Promise<void>
}

export function MacroIndicatorSelectPopover({
  open,
  onClose,
  currentValue,
  onSelect,
}: MacroIndicatorSelectPopoverProps) {
  const [selected, setSelected] = useState(currentValue || '')
  const [saving, setSaving] = useState(false)

  const handleEnter = () => {
    setSelected(currentValue || '')
  }

  const handleConfirm = async () => {
    setSaving(true)
    try {
      await onSelect(selected)
      onClose()
    } finally {
      setSaving(false)
    }
  }

  const handleClear = async () => {
    setSaving(true)
    try {
      await onSelect('')
      onClose()
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog
      open={open}
      onClose={saving ? undefined : onClose}
      TransitionProps={{ onEnter: handleEnter }}
      maxWidth="sm"
      fullWidth
      dir="rtl"
    >
      <DialogTitle sx={{ m: 0, p: 2, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <Stack direction="row" spacing={1} alignItems="center">
          <BookmarkRounded color="primary" />
          <Typography variant="h6" fontWeight={700}>
            انتخاب شاخصه کلی (برنامه فرهنگی)
          </Typography>
        </Stack>
        <IconButton
          aria-label="بستن"
          onClick={onClose}
          disabled={saving}
          size="small"
          sx={{ color: 'text.secondary' }}
        >
          <CloseRounded fontSize="small" />
        </IconButton>
      </DialogTitle>

      <DialogContent dividers sx={{ p: 1 }}>
        <List disablePadding>
          {MACRO_INDICATORS.map(macro => {
            const isSelected = selected === macro
            const isNonProgram = macro === 'غیر برنامه‌ای'
            return (
              <ListItemButton
                key={macro}
                onClick={() => setSelected(macro)}
                selected={isSelected}
                sx={{
                  borderRadius: 1.5,
                  mb: 0.5,
                  py: 1,
                  px: 1.5,
                  bgcolor: isSelected ? 'action.selected' : 'transparent',
                }}
              >
                <ListItemIcon sx={{ minWidth: 36 }}>
                  <Radio
                    checked={isSelected}
                    onChange={() => setSelected(macro)}
                    size="small"
                    sx={{ p: 0.5 }}
                  />
                </ListItemIcon>
                <ListItemText
                  primary={
                    <Typography
                      variant="body2"
                      fontWeight={isSelected ? 700 : 500}
                      color={isNonProgram ? 'text.secondary' : 'text.primary'}
                    >
                      {macro}
                    </Typography>
                  }
                />
              </ListItemButton>
            )
          })}
        </List>
      </DialogContent>

      <DialogActions sx={{ p: 2, justifyContent: 'space-between' }}>
        <Button onClick={handleClear} disabled={saving || !currentValue} color="inherit" size="small">
          حذف شاخصه
        </Button>
        <Stack direction="row" spacing={1}>
          <Button onClick={onClose} disabled={saving} color="inherit">
            انصراف
          </Button>
          <Button
            onClick={handleConfirm}
            disabled={saving}
            variant="contained"
            color="primary"
          >
            {saving ? 'در حال ثبت...' : 'تأیید انتخاب'}
          </Button>
        </Stack>
      </DialogActions>
    </Dialog>
  )
}
