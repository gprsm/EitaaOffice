import { type ReactNode, useState } from 'react'
import {
  Alert,
  Badge,
  Box,
  CircularProgress,
  IconButton,
  InputAdornment,
  List,
  ListItemAvatar,
  ListItemButton,
  ListItemText,
  Menu,
  MenuItem,
  Paper,
  Stack,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material'
import AddCommentRounded from '@mui/icons-material/AddCommentRounded'
import CloseRounded from '@mui/icons-material/CloseRounded'
import MoreVertRounded from '@mui/icons-material/MoreVertRounded'
import SearchRounded from '@mui/icons-material/SearchRounded'
import StarBorderRounded from '@mui/icons-material/StarBorderRounded'
import StarRounded from '@mui/icons-material/StarRounded'
import SyncRounded from '@mui/icons-material/SyncRounded'
import type { DialogItem, DisplayKind } from './lib/types'

const displayKindLabel = (kind: DisplayKind) => ({
  channel: 'کانال',
  group: 'گروه',
  personal: 'شخصی',
}[kind])

export function ConversationListPage({
  open,
  docked,
  loading,
  syncing,
  dialogsEnabled,
  filterLabel,
  search,
  items,
  totalFiltered,
  activePeerKey,
  renderAvatar,
  titleFor,
  onSearch,
  onClose,
  onSync,
  onAdd,
  onSelect,
  onFavorite,
  onDisplayKind,
}: {
  open: boolean
  docked: boolean
  loading: boolean
  syncing: boolean
  dialogsEnabled: boolean
  filterLabel: string
  search: string
  items: DialogItem[]
  totalFiltered: number
  activePeerKey?: string
  renderAvatar: (item: DialogItem) => ReactNode
  titleFor: (item: DialogItem) => string
  onSearch: (value: string) => void
  onClose: () => void
  onSync: () => void
  onAdd: () => void
  onSelect: (item: DialogItem) => void
  onFavorite: (item: DialogItem) => void
  onDisplayKind: (item: DialogItem, kind: DisplayKind) => void
}) {
  const [menuAnchor, setMenuAnchor] = useState<HTMLElement | null>(null)
  const [menuDialog, setMenuDialog] = useState<DialogItem | null>(null)
  const openMenu = (event: React.MouseEvent<HTMLElement>, item: DialogItem) => {
    event.stopPropagation()
    setMenuAnchor(event.currentTarget)
    setMenuDialog(item)
  }
  const closeMenu = () => { setMenuAnchor(null); setMenuDialog(null) }

  return <Paper
    component="aside"
    square
    elevation={0}
    aria-label="فهرست گفتگوها"
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
      <Tooltip title="همگام‌سازی گفتگوها"><span><IconButton disabled={syncing || !dialogsEnabled} onClick={onSync} aria-label="همگام‌سازی گفتگوها">{syncing ? <CircularProgress size={20} /> : <SyncRounded />}</IconButton></span></Tooltip>
      <Tooltip title="افزودن دستی"><span><IconButton disabled={!dialogsEnabled} onClick={onAdd} aria-label="افزودن دستی گفتگو"><AddCommentRounded /></IconButton></span></Tooltip>
      {!docked && <IconButton onClick={onClose} aria-label="بستن فهرست گفتگوها"><CloseRounded /></IconButton>}
    </Stack>

    <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ px: 1.5, py: 1 }}>
      <Typography variant="subtitle2">{filterLabel}</Typography>
      <Typography variant="caption" color="text.secondary">{totalFiltered.toLocaleString('fa-IR')} گفتگو</Typography>
    </Stack>
    {totalFiltered > items.length && <Alert severity="info" sx={{ mx: 1, mb: 1 }}>برای حفظ سرعت، ۵۰۰ گفت‌وگوی نخست نمایش داده شده است؛ برای موارد دیگر جست‌وجو کنید.</Alert>}

    <List disablePadding sx={{ flex: 1, minHeight: 0, overflowY: 'auto' }}>
      {loading && !items.length && <Stack alignItems="center" spacing={1} sx={{ py: 4 }}><CircularProgress size={28} /><Typography variant="body2" color="text.secondary">در حال دریافت گفتگوها</Typography></Stack>}
      {!loading && !items.length && <Stack alignItems="center" spacing={1} sx={{ p: 3, textAlign: 'center' }}><Typography color="text.secondary">موردی در این بخش نیست.</Typography><IconButton onClick={onAdd} aria-label="افزودن دستی گفتگو"><AddCommentRounded /></IconButton></Stack>}
      {items.map(item => {
        const selected = activePeerKey === item.peer_key
        const secondary = item.peer.username
          ? `@${item.peer.username}`
          : item.top_message_id
            ? `آخرین پیام #${item.top_message_id}`
            : item.source === 'manual' ? 'افزوده‌شده به‌صورت دستی' : 'گفتگو'
        return <ListItemButton
          key={item.peer_key}
          selected={selected}
          onClick={() => onSelect(item)}
          sx={{ minHeight: 68, px: 1.25, gap: 0.5, borderBottom: 1, borderColor: 'divider', '&.Mui-selected': { bgcolor: 'action.selected', borderInlineStart: 4, borderInlineStartColor: 'text.secondary' } }}
        >
          <ListItemAvatar sx={{ minWidth: 54 }}>{renderAvatar(item)}</ListItemAvatar>
          <ListItemText
            primary={titleFor(item)}
            secondary={secondary}
            primaryTypographyProps={{ fontWeight: selected ? 800 : 650, noWrap: true }}
            secondaryTypographyProps={{ noWrap: true }}
          />
          <Stack direction="row" alignItems="center" spacing={0.25}>
            {item.unread_count > 0 && <Badge badgeContent={item.unread_count > 999 ? '999+' : item.unread_count} color="primary" max={999} />}
            <Tooltip title={item.favorite ? 'حذف از منتخب' : 'افزودن به منتخب'}><IconButton size="small" color={item.favorite ? 'warning' : 'default'} onClick={event => { event.stopPropagation(); onFavorite(item) }} aria-label={item.favorite ? 'حذف از منتخب' : 'افزودن به منتخب'}>{item.favorite ? <StarRounded fontSize="small" /> : <StarBorderRounded fontSize="small" />}</IconButton></Tooltip>
            <IconButton size="small" onClick={event => openMenu(event, item)} aria-label="گزینه‌های گفتگو"><MoreVertRounded fontSize="small" /></IconButton>
          </Stack>
        </ListItemButton>
      })}
    </List>

    <Menu anchorEl={menuAnchor} open={Boolean(menuAnchor)} onClose={closeMenu}>
      <Box sx={{ px: 2, pt: 1, pb: 0.5 }}><Typography variant="caption" color="text.secondary">نمایش در فهرست</Typography></Box>
      {(['channel', 'group', 'personal'] as DisplayKind[]).map(kind => <MenuItem
        key={kind}
        selected={menuDialog?.display_kind === kind}
        onClick={() => {
          if (menuDialog) onDisplayKind(menuDialog, kind)
          closeMenu()
        }}
      >{displayKindLabel(kind)}</MenuItem>)}
    </Menu>
  </Paper>
}
