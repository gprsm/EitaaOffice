import { type ReactNode } from 'react'
import { Box, Chip, IconButton, Stack, Toolbar, Tooltip, Typography } from '@mui/material'
import ArrowForwardRounded from '@mui/icons-material/ArrowForwardRounded'

export function BaleChatHeader({
  title,
  subtitle,
  avatar,
  liveState,
  onOpenChats,
}: {
  title: string
  subtitle: string
  avatar: ReactNode
  liveState: 'idle' | 'connecting' | 'retrying'
  onOpenChats: () => void
}) {
  return <Toolbar
    component="header"
    disableGutters
    sx={{
      minHeight: 'unset !important',
      px: { xs: 0.75, sm: 1.5 },
      py: 0.75,
      gap: 1,
      flexWrap: 'wrap',
      borderBottom: 1,
      borderColor: 'divider',
      bgcolor: 'background.paper',
    }}
  >
    <Stack direction="row" alignItems="center" spacing={1} sx={{ flex: '1 1 220px', minWidth: 0 }}>
      <Tooltip title="بازگشت به فهرست گفتگوها">
        <IconButton onClick={onOpenChats} aria-label="بازگشت به فهرست گفتگوها" sx={{ display: { md: 'none' } }}><ArrowForwardRounded /></IconButton>
      </Tooltip>
      {avatar}
      <Box sx={{ minWidth: 0 }}>
        <Typography variant="subtitle1" fontWeight={850} noWrap>{title}</Typography>
        <Typography variant="caption" color="text.secondary" noWrap>{subtitle}</Typography>
      </Box>
    </Stack>
    <Stack direction="row" alignItems="center" justifyContent="flex-end" gap={0.5} sx={{ flex: '1 1 auto' }}>
      {/* Successful live refresh stays silent; only connection trouble is announced. */}
      {liveState !== 'idle' && <Chip
        size="small"
        color={liveState === 'retrying' ? 'warning' : 'default'}
        variant="outlined"
        label={liveState === 'retrying' ? 'تلاش برای دریافت' : 'در حال دریافت'}
        aria-label="وضعیت دریافت خودکار پیام‌های جدید"
      />}
    </Stack>
  </Toolbar>
}
