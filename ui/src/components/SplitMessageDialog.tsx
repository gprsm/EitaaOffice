import { useState } from 'react'
import {
  Box,
  Button,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  IconButton,
  List,
  ListItem,
  ListItemSecondaryAction,
  ListItemText,
  Stack,
  Switch,
  Typography,
} from '@mui/material'
import CloseRounded from '@mui/icons-material/CloseRounded'
import CallSplitRounded from '@mui/icons-material/CallSplitRounded'
import MergeTypeRounded from '@mui/icons-material/MergeTypeRounded'
import ImageIcon from '@mui/icons-material/Image'
import AttachFileIcon from '@mui/icons-material/AttachFile'
import type { MessageItem } from '../lib/types'

type SplitMessageDialogProps = {
  open: boolean
  onClose: () => void
  peerKey: string
  messages: MessageItem[]
  detachedMessageIds: Set<number>
  onSaveSplits: (detachedIds: number[], unifiedIds: number[]) => Promise<void>
}

export function SplitMessageDialog({
  open,
  onClose,
  messages,
  detachedMessageIds,
  onSaveSplits,
}: SplitMessageDialogProps) {
  // Local state of which message IDs are detached
  const [localDetached, setLocalDetached] = useState<Set<number>>(() => new Set(detachedMessageIds))
  const [saving, setSaving] = useState(false)

  // Sync when dialog opens
  const handleEnter = () => {
    setLocalDetached(new Set(detachedMessageIds))
  }

  const handleToggle = (id: number) => {
    setLocalDetached(prev => {
      const next = new Set(prev)
      if (next.has(id)) {
        next.delete(id)
      } else {
        next.add(id)
      }
      return next
    })
  }

  const handleDetachAll = () => {
    // Detach all except the first one (or all)
    const next = new Set<number>()
    messages.forEach(m => next.add(m.id))
    setLocalDetached(next)
  }

  const handleMergeAll = () => {
    setLocalDetached(new Set())
  }

  const handleSave = async () => {
    setSaving(true)
    try {
      const detachedToSave: number[] = []
      const unifiedToSave: number[] = []

      messages.forEach(m => {
        if (localDetached.has(m.id)) {
          detachedToSave.push(m.id)
        } else {
          unifiedToSave.push(m.id)
        }
      })

      await onSaveSplits(detachedToSave, unifiedToSave)
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
          <CallSplitRounded color="primary" />
          <Typography variant="h6" fontWeight={700}>
            تفکیک و ادغام بخش‌های پیام
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

      <DialogContent dividers sx={{ p: 2 }}>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          این کارت شامل {messages.length} بخش پیام پیوسته است. با غیرفعال‌کردن ادغام، هر بخش به عنوان یک پیام مستقل در
          صفحه گفتگو نمایش داده می‌شود.
        </Typography>

        <Stack direction="row" spacing={1} sx={{ mb: 2 }}>
          <Button
            size="small"
            variant="outlined"
            color="warning"
            startIcon={<CallSplitRounded />}
            onClick={handleDetachAll}
            disabled={saving}
          >
            تفکیک همه بخش‌ها
          </Button>
          <Button
            size="small"
            variant="outlined"
            color="info"
            startIcon={<MergeTypeRounded />}
            onClick={handleMergeAll}
            disabled={saving}
          >
            ادغام مجدد همه بخش‌ها
          </Button>
        </Stack>

        <Divider sx={{ my: 1.5 }} />

        <List disablePadding>
          {messages.map((m, index) => {
            const isDetached = localDetached.has(m.id)
            const textPreview = m.text?.trim()
              ? m.text.trim().slice(0, 120) + (m.text.trim().length > 120 ? '...' : '')
              : '(بدون متن)'

            return (
              <ListItem
                key={m.id}
                sx={{
                  border: 1,
                  borderColor: isDetached ? 'warning.light' : 'divider',
                  borderRadius: 1.5,
                  mb: 1,
                  bgcolor: isDetached ? 'warning.lighter' : 'background.paper',
                  p: 1.5,
                }}
              >
                <ListItemText
                  primary={
                    <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 0.5 }}>
                      <Typography variant="subtitle2" fontWeight={700}>
                        بخش {index + 1}
                      </Typography>
                      {m.media?.is_image && (
                        <Chip
                          size="small"
                          icon={<ImageIcon fontSize="small" />}
                          label="تصویر"
                          variant="outlined"
                          sx={{ height: 22, fontSize: '0.7rem' }}
                        />
                      )}
                      {m.media && !m.media.is_image && (
                        <Chip
                          size="small"
                          icon={<AttachFileIcon fontSize="small" />}
                          label="فایل"
                          variant="outlined"
                          sx={{ height: 22, fontSize: '0.7rem' }}
                        />
                      )}
                      <Chip
                        size="small"
                        color={isDetached ? 'warning' : 'success'}
                        label={isDetached ? 'تفکیک‌شده (مستقل)' : 'یکپارچه'}
                        sx={{ height: 20, fontSize: '0.65rem', fontWeight: 600 }}
                      />
                    </Stack>
                  }
                  secondary={
                    <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5, lineHeight: 1.6 }}>
                      {textPreview}
                    </Typography>
                  }
                />
                <ListItemSecondaryAction sx={{ left: 16, right: 'auto' }}>
                  <Stack direction="row" spacing={0.5} alignItems="center">
                    <Typography variant="caption" color="text.secondary">
                      {isDetached ? 'مستقل' : 'ادغام'}
                    </Typography>
                    <Switch
                      edge="end"
                      checked={!isDetached}
                      onChange={() => handleToggle(m.id)}
                      disabled={saving}
                      color="primary"
                    />
                  </Stack>
                </ListItemSecondaryAction>
              </ListItem>
            )
          })}
        </List>
      </DialogContent>

      <DialogActions sx={{ p: 2, justifyContent: 'space-between' }}>
        <Typography variant="caption" color="text.secondary">
          {localDetached.size > 0
            ? `${localDetached.size} بخش به صورت مستقل نمایش داده خواهد شد.`
            : 'همه بخش‌ها در یک پیام یکپارچه ادغام هستند.'}
        </Typography>
        <Stack direction="row" spacing={1}>
          <Button onClick={onClose} disabled={saving} color="inherit">
            انصراف
          </Button>
          <Button onClick={handleSave} disabled={saving} variant="contained" color="primary">
            {saving ? 'در حال ذخیره...' : 'اعمال تفکیک'}
          </Button>
        </Stack>
      </DialogActions>
    </Dialog>
  )
}
