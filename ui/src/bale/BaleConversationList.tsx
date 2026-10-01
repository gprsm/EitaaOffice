import { type ReactNode } from 'react'
import {
  Badge,
  Box,
  CircularProgress,
  IconButton,
  InputAdornment,
  List,
  ListItemAvatar,
  ListItemButton,
  ListItemText,
  Paper,
  Stack,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material'
import CampaignOutlined from '@mui/icons-material/CampaignOutlined'
import CloseRounded from '@mui/icons-material/CloseRounded'
import GroupsOutlined from '@mui/icons-material/GroupsOutlined'
import PersonOutlineRounded from '@mui/icons-material/PersonOutlineRounded'
import SearchRounded from '@mui/icons-material/SearchRounded'
import SyncRounded from '@mui/icons-material/SyncRounded'

export type BalePeerKind = 'private' | 'group' | 'channel' | 'bot' | 'unknown'

export type BaleDialogItem = {
  peer_reference: string
  peer_kind: string
  title: string
  last_text?: string
  unread_count: number
}

const kindIcon = (kind: string) => {
  if (kind === 'group') return <GroupsOutlined fontSize="small" />
  if (kind === 'channel') return <CampaignOutlined fontSize="small" />
  return <PersonOutlineRounded fontSize="small" />
}

const kindLabel = (kind: string) => ({
  private: 'شخصی',
  group: 'گروه',
  channel: 'کانال',
  bot: 'ربات',
}[kind] || 'گفتگو')

export function BaleAvatar({ title, small = false }: { title: string; small?: boolean }) {
  const clean = title.trim()
  const initials = clean ? clean.slice(0, 2) : 'ب'
  return <Box
    aria-hidden="true"
    sx={{
      display: 'grid',
      placeItems: 'center',
      width: small ? 34 : 46,
      height: small ? 34 : 46,
      flex: '0 0 auto',
      borderRadius: '50%',
      bgcolor: 'primary.main',
      color: 'primary.contrastText',
      fontWeight: 800,
      fontSize: small ? '0.85rem' : '1rem',
    }}
  >{initials}</Box>
}

export function BaleConversationList({
  open,
  docked,
  loading,
  refreshing,
  dialogsEnabled,
  filterLabel,
  search,
  items,
  totalCount,
  activePeerKey,
  onSearch,
  onClose,
  onRefresh,
  onSelect,
}: {
  open: boolean
  docked: boolean
  loading: boolean
  refreshing: boolean
  dialogsEnabled: boolean
  filterLabel: string
  search: string
  items: BaleDialogItem[]
  totalCount: number
  activePeerKey?: string
  onSearch: (value: string) => void
  onClose: () => void
  onRefresh: () => void
  onSelect: (item: BaleDialogItem) => void
}) {
  const renderAvatar = (item: BaleDialogItem): ReactNode => <BaleAvatar title={item.title} />
  return <Paper
    component="aside"
    square
    elevation={0}
    aria-label="فهرست گفتگوهای بله"
    sx={{
      minWidth: 0,
      minHeight: 0,
      height: '100%',
      overflow: 'hidden',
      display: 'flex',
      flexDirection: 'column',
      borderInlineEnd: 1,
      borderColor: 'divider',
      bgcolor: 'background.paper',
      '@media (max-width: 899px)': {
        position: 'fixed',
        zIndex: theme => theme.zIndex.drawer,
        top: 0,
        bottom: 'calc(66px + env(safe-area-inset-bottom))',
        insetInlineStart: 0,
        width: 'min(92vw, 390px)',
        height: 'auto',
        transform: open ? 'translateX(0)' : 'translateX(-110%)',
        transition: 'transform 200ms ease',
        boxShadow: open ? '-10px 0 30px rgba(0,0,0,.25)' : 'none',
      },
    }}
  >
    <Stack direction="row" alignItems="center" gap={0.5} sx={{ p: 1, borderBottom: 1, borderColor: 'divider' }}>
      <TextField
        size="small"
        fullWidth
        label="جست‌وجوی گفتگو"
        value={search}
        onChange={event => onSearch(event.target.value)}
        InputProps={{ startAdornment: <InputAdornment position="start"><SearchRounded fontSize="small" /></InputAdornment> }}
      />
      <Tooltip title="به‌روزرسانی فهرست"><span><IconButton disabled={refreshing || !dialogsEnabled} onClick={onRefresh} aria-label="به‌روزرسانی فهرست گفتگوها">{refreshing ? <CircularProgress size={20} /> : <SyncRounded />}</IconButton></span></Tooltip>
      {!docked && <IconButton onClick={onClose} aria-label="بستن فهرست گفتگوها"><CloseRounded /></IconButton>}
    </Stack>

    <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ px: 1.5, py: 1 }}>
      <Typography variant="subtitle2">{filterLabel}</Typography>
      <Typography variant="caption" color="text.secondary">{totalCount.toLocaleString('fa-IR')} گفتگو</Typography>
    </Stack>

    <List disablePadding sx={{ flex: 1, minHeight: 0, overflowY: 'auto' }}>
      {loading && !items.length && <Stack alignItems="center" spacing={1} sx={{ py: 4 }}><CircularProgress size={28} /><Typography variant="body2" color="text.secondary">در حال دریافت گفتگوها</Typography></Stack>}
      {!loading && !items.length && <Stack alignItems="center" spacing={1} sx={{ p: 3, textAlign: 'center' }}><Typography color="text.secondary">گفتگویی در این بخش نیست.</Typography><Typography variant="caption" color="text.secondary">فهرست به‌صورت خودکار به‌روز می‌شود.</Typography></Stack>}
      {items.map(item => {
        const selected = activePeerKey === item.peer_reference
        return <ListItemButton
          key={item.peer_reference}
          selected={selected}
          onClick={() => onSelect(item)}
          sx={{ minHeight: 68, px: 1.25, gap: 0.5, borderBottom: 1, borderColor: 'divider', '&.Mui-selected': { bgcolor: 'action.selected', borderInlineStart: 4, borderInlineStartColor: 'text.secondary' } }}
        >
          <ListItemAvatar sx={{ minWidth: 54 }}>{renderAvatar(item)}</ListItemAvatar>
          <ListItemText
            primary={item.title || item.peer_reference}
            secondary={item.last_text || kindLabel(item.peer_kind)}
            primaryTypographyProps={{ fontWeight: selected ? 800 : 650, noWrap: true }}
            secondaryTypographyProps={{ noWrap: true }}
          />
          <Stack direction="row" alignItems="center" spacing={0.5}>
            {item.peer_kind !== 'private' && <Tooltip title={`${kindLabel(item.peer_kind)} — خواندن و ارسال خصوصی در این نسخه پشتیبانی نمی‌شود`}><Box sx={{ display: 'inline-flex', color: 'text.disabled' }}>{kindIcon(item.peer_kind)}</Box></Tooltip>}
            {item.unread_count > 0 && <Badge badgeContent={item.unread_count > 999 ? '999+' : item.unread_count} color="primary" max={999} />}
          </Stack>
        </ListItemButton>
      })}
    </List>
  </Paper>
}
