import { type ReactNode } from 'react'
import {
  Box,
  Chip,
  IconButton,
  Stack,
  Toolbar,
  Tooltip,
  Typography,
} from '@mui/material'
import AspectRatioRounded from '@mui/icons-material/AspectRatioRounded'
import ArrowForwardRounded from '@mui/icons-material/ArrowForwardRounded'
import FilterAltRounded from '@mui/icons-material/FilterAltRounded'
import TuneRounded from '@mui/icons-material/TuneRounded'
import GroupsOutlined from '@mui/icons-material/GroupsOutlined'
import { WordPressIcon } from './WordPressIcon'
import { HeaderMessageSearch } from './HeaderMessageSearch'

export function ChatHeader({
  title,
  subtitle,
  avatar,
  selectionCount,
  liveState,
  mediaDynamic,
  mediaEnabled,
  filtersActive,
  filterEnabled,
  indexActive,
  indexEnabled,
  datePicker,
  search,
  wordpressVisible,
  wordpressEnabled,
  communityEnabled,
  composerVisible,
  onOpenChats,
  onClearSelection,
  onToggleMedia,
  onToggleFilters,
  onToggleIndex,
  onSearch,
  onOpenComposer,
}: {
  title: string
  subtitle: string
  avatar: ReactNode
  selectionCount: number
  liveState: 'idle' | 'connecting' | 'live' | 'retrying'
  mediaDynamic: boolean
  mediaEnabled: boolean
  filtersActive: boolean
  filterEnabled: boolean
  indexActive: boolean
  indexEnabled: boolean
  datePicker: ReactNode
  search: string
  wordpressVisible: boolean
  wordpressEnabled: boolean
  communityEnabled: boolean
  composerVisible: boolean
  onOpenChats: () => void
  onClearSelection: () => void
  onToggleMedia: () => void
  onToggleFilters: () => void
  onToggleIndex: () => void
  onSearch: (value: string) => void
  onOpenComposer: () => void
}) {
  return <Toolbar
    component="header"
    disableGutters
    sx={{
      minHeight: 'unset !important',
      px: { xs: 0.75, sm: 1.5 },
      paddingInlineEnd: { xs: '64px', md: '12px' }, /* Prevent hiding under floating FAB */
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

    <Stack direction="row" alignItems="center" justifyContent="flex-end" gap={0.5} flexWrap="wrap" sx={{ flex: '1 1 auto' }}>
      {selectionCount > 0 && <Chip label={`${selectionCount.toLocaleString('fa-IR')} انتخاب`} onDelete={onClearSelection} />}
      {liveState !== 'idle' && liveState !== 'live' && <Chip
        size="small"
        color={liveState === 'retrying' ? 'warning' : 'default'}
        variant="outlined"
        label={liveState === 'retrying' ? 'تلاش برای اتصال' : 'در حال اتصال'}
        aria-label="وضعیت دریافت خودکار پیام‌های جدید"
      />}
      <Tooltip title={mediaDynamic ? 'نمایش رسانه در قاب ثابت' : 'نمایش رسانه پویای تلگرامی'}><span><IconButton disabled={!mediaEnabled} color={mediaDynamic ? 'primary' : 'default'} onClick={onToggleMedia} aria-label="تغییر حالت نمایش رسانه"><AspectRatioRounded /></IconButton></span></Tooltip>
      {filterEnabled && <Tooltip title="فیلتر نمایش (مخفی در گفت‌وگوی شخصی)"><span><IconButton color={filtersActive ? 'primary' : 'default'} onClick={onToggleFilters} aria-label="فیلتر نمایش"><FilterAltRounded /></IconButton></span></Tooltip>}
      {indexEnabled && <Tooltip title="ایندکس‌گذاری محتوای منتخب"><span><IconButton color={indexActive ? 'primary' : 'default'} onClick={onToggleIndex} aria-label="ایندکس‌گذاری"><TuneRounded /></IconButton></span></Tooltip>}
      {datePicker}
      <HeaderMessageSearch value={search} onChange={onSearch} />
      {!composerVisible && <Box sx={{
        display: 'inline-flex',
        '@media (max-width: 899px)': {
          position: 'fixed',
          zIndex: theme => theme.zIndex.appBar + 1,
          top: 'max(8px, env(safe-area-inset-top))',
          insetInlineEnd: 'max(8px, env(safe-area-inset-right))',
          bgcolor: 'background.paper',
          borderRadius: '50%',
          boxShadow: 2,
        },
      }}>{wordpressVisible
        ? <Tooltip title={wordpressEnabled ? 'وردپرس' : 'ابتدا تنظیمات وردپرس را کامل کنید'}><span><IconButton sx={{ width: 48, height: 48 }} disabled={!wordpressEnabled} color="primary" onClick={onOpenComposer} aria-label="بازکردن صفحه وردپرس"><WordPressIcon /></IconButton></span></Tooltip>
        : <Tooltip title={communityEnabled ? 'عملیات گفتگو' : 'فقط برای گروه یا کانالی که در آن مالک یا مدیر هستید'}><span><IconButton sx={{ width: 48, height: 48 }} disabled={!communityEnabled} color="secondary" onClick={onOpenComposer} aria-label="بازکردن عملیات گفتگو"><GroupsOutlined /></IconButton></span></Tooltip>}</Box>}
    </Stack>
  </Toolbar>
}
