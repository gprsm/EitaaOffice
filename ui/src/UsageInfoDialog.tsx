import {
  Alert,
  Button,
  Dialog,
  DialogContent,
  DialogTitle,
  IconButton,
  Paper,
  Stack,
  Typography,
} from '@mui/material'
import CloseRounded from '@mui/icons-material/CloseRounded'
import type { CompositionRecord, MessageItem, MessageUsage, Site } from './lib/types'

export function UsageInfoDialog({
  activeUsage,
  clearUsage,
  loadHistory,
}: {
  activeUsage: { message: MessageItem; usage: MessageUsage } | null
  clearUsage: () => void
  loadHistory: (item: any) => void
}) {
  if (!activeUsage) return null

  return (
    <Dialog open={true} onClose={clearUsage} fullWidth maxWidth="sm">
      <DialogTitle sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        سابقه انتشار پیام #{activeUsage.message.id}
        <IconButton onClick={clearUsage} size="small" aria-label="بستن">
          <CloseRounded />
        </IconButton>
      </DialogTitle>
      <DialogContent dividers>
        <Stack spacing={1.5}>
          {activeUsage.usage.compositions.length ? (
            activeUsage.usage.compositions.map(item => (
              <Paper variant="outlined" key={item.composition_key} sx={{ p: 1.5 }}>
                <Typography fontWeight={750}>{item.title || `پست ${item.post_id}`}</Typography>
                <Typography variant="caption" color="text.secondary">
                  Post ID: {item.post_id} &mdash; {item.status}
                </Typography>
                <Stack direction="row" gap={1} mt={1}>
                  <Button size="small" variant="outlined" onClick={() => loadHistory(item)}>
                    فراخوانی برای ویرایش
                  </Button>
                  {item.post_url && (
                    <Button
                      size="small"
                      variant="outlined"
                      onClick={() => window.eitaaDesktop.openExternal(item.post_url!)}
                    >
                      مشاهده در مرورگر
                    </Button>
                  )}
                </Stack>
              </Paper>
            ))
          ) : (
            <Alert
              severity="info"
              action={
                activeUsage.usage.external_url ? (
                  <Button
                    color="inherit"
                    size="small"
                    onClick={() => window.eitaaDesktop.openExternal(activeUsage.usage.external_url!)}
                  >
                    مشاهده لینک خارجی
                  </Button>
                ) : undefined
              }
            >
              این پیام در هیچ پست وردپرسی به‌طور مستقیم استفاده نشده است.
            </Alert>
          )}
        </Stack>
      </DialogContent>
    </Dialog>
  )
}
