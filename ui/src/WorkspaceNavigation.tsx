import { type ReactNode, useMemo, useState } from 'react'
import {
  Badge,
  BottomNavigation,
  BottomNavigationAction,
  Box,
  Button,
  Divider,
  IconButton,
  Menu,
  Paper,
  Stack,
  Tooltip,
  Typography,
} from '@mui/material'
import AddCommentRounded from '@mui/icons-material/AddCommentRounded'
import CampaignOutlined from '@mui/icons-material/CampaignOutlined'
import ChatBubbleOutlineRounded from '@mui/icons-material/ChatBubbleOutlineRounded'
import ContactsRounded from '@mui/icons-material/ContactsRounded'
import GroupsOutlined from '@mui/icons-material/GroupsOutlined'
import LogoutRounded from '@mui/icons-material/LogoutRounded'
import MenuRounded from '@mui/icons-material/MenuRounded'
import PersonOutlineRounded from '@mui/icons-material/PersonOutlineRounded'
import SendRounded from '@mui/icons-material/SendRounded'
import SettingsRounded from '@mui/icons-material/SettingsRounded'
import StarOutlineRounded from '@mui/icons-material/StarOutlineRounded'
import SummarizeRounded from '@mui/icons-material/SummarizeRounded'
import SyncRounded from '@mui/icons-material/SyncRounded'
import { WordPressIcon } from './WordPressIcon'

export type WorkspaceSectionValue = 'all' | 'channel' | 'group' | 'personal' | 'favorite'

export type WorkspaceSection = {
  value: WorkspaceSectionValue
  label: string
  count: number
}

const sectionIcon = (value: WorkspaceSectionValue) => ({
  all: <ChatBubbleOutlineRounded />,
  channel: <CampaignOutlined />,
  group: <GroupsOutlined />,
  personal: <PersonOutlineRounded />,
  favorite: <StarOutlineRounded />,
}[value])

export function WorkspaceNavigation({
  sections,
  activeSection,
  userName,
  userRole,
  accountControl,
  syncing,
  dialogsEnabled,
  wordpressVisible,
  wordpressEnabled,
  onSection,
  onSettings,
  onReporting,
  onAddDialog,
  onSync,
  onContacts,
  onBulk,
  onCommunity,
  onWordpress,
  onMessengerLogout,
  onSoftwareLogout,
  syncLabel = 'همگام‌سازی گفتگوها',
  messengerLogoutLabel = 'خروج از حساب ایتا',
}: {
  sections: WorkspaceSection[]
  activeSection: WorkspaceSectionValue
  userName: string
  userRole: string
  accountControl: ReactNode
  syncing: boolean
  dialogsEnabled: boolean
  wordpressVisible: boolean
  wordpressEnabled: boolean
  onSection: (value: WorkspaceSectionValue) => void
  onSettings: () => void
  onReporting?: () => void
  onAddDialog?: () => void
  onSync?: () => void
  onContacts: () => void
  onBulk?: () => void
  onCommunity?: () => void
  onWordpress?: () => void
  onMessengerLogout: () => void
  onSoftwareLogout?: () => void
  // Workspace-specific actions are optional so other providers can reuse the
  // same navigation without advertising Eitaa-only operations they lack.
  syncLabel?: string
  messengerLogoutLabel?: string
}) {
  const [anchor, setAnchor] = useState<HTMLElement | null>(null)
  const selected = useMemo(
    () => sections.findIndex(item => item.value === activeSection),
    [activeSection, sections],
  )
  const mobileSections = useMemo(() => {
    const order: WorkspaceSectionValue[] = ['all', 'channel', 'favorite', 'group', 'personal']
    return order.map(val => sections.find(s => s.value === val)).filter(Boolean) as WorkspaceSection[]
  }, [sections])
  const mobileSelected = useMemo(
    () => mobileSections.findIndex(item => item.value === activeSection),
    [activeSection, mobileSections],
  )
  const close = () => setAnchor(null)
  const invoke = (action: () => void) => { close(); action() }

  const menuButton = <IconButton
    aria-label="منوی بیشتر"
    aria-controls={anchor ? 'workspace-navigation-menu' : undefined}
    aria-expanded={Boolean(anchor)}
    onClick={event => setAnchor(event.currentTarget)}
    sx={{ width: 48, height: 48 }}
  ><MenuRounded /></IconButton>

  return <>
    <Paper
      component="nav"
      square
      elevation={2}
      aria-label="ناوبری اصلی برنامه"
      sx={{
        zIndex: theme => theme.zIndex.appBar,
        color: 'text.primary',
        bgcolor: 'background.paper',
        borderInlineEnd: { md: 1 },
        borderColor: 'divider',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'stretch',
        minWidth: 0,
        '@media (max-width: 899px)': {
          position: 'fixed',
          insetInline: 0,
          bottom: 0,
          height: 'calc(66px + env(safe-area-inset-bottom))',
          pt: 0.5,
          pb: 'env(safe-area-inset-bottom)',
          borderInlineEnd: 0,
          borderTop: 1,
          borderColor: 'divider',
        },
      }}
    >
      <Box sx={{ display: { xs: 'none', md: 'grid' }, placeItems: 'center', py: 1 }}>{menuButton}</Box>
      <Stack spacing={0.25} sx={{ display: { xs: 'none', md: 'flex' }, px: 0.5 }}>
        {sections.map(item => <Tooltip key={item.value} title={item.label} placement="left">
          <Button
            color={activeSection === item.value ? 'primary' : 'inherit'}
            variant={activeSection === item.value ? 'contained' : 'text'}
            onClick={() => onSection(item.value)}
            aria-current={activeSection === item.value ? 'page' : undefined}
            sx={{ minWidth: 0, minHeight: 58, px: 0.5, flexDirection: 'column', gap: 0.25, fontSize: '0.68rem' }}
          >
            <Badge badgeContent={item.count > 999 ? '999+' : item.count} max={999} color="secondary">{sectionIcon(item.value)}</Badge>
            {item.label}
          </Button>
        </Tooltip>)}
      </Stack>
      <Stack spacing={0.25} sx={{ display: { xs: 'none', md: 'flex' }, mt: 'auto', px: 0.5, pb: 1 }}>
        {onReporting && <Tooltip title="گزارش‌ها ۱۴۰۵" placement="left"><Button color="inherit" onClick={onReporting} sx={{ minWidth: 0, minHeight: 54, flexDirection: 'column', fontSize: '0.68rem' }}><SummarizeRounded />گزارش‌ها</Button></Tooltip>}
        <Tooltip title="مخاطبان" placement="left"><Button color="inherit" onClick={onContacts} sx={{ minWidth: 0, minHeight: 54, flexDirection: 'column', fontSize: '0.68rem' }}><ContactsRounded />مخاطبان</Button></Tooltip>
        {wordpressVisible
          ? <Tooltip title={wordpressEnabled ? 'وردپرس' : 'ابتدا تنظیمات وردپرس را کامل کنید'} placement="left"><span><Button color="inherit" disabled={!wordpressEnabled} onClick={onWordpress} sx={{ minWidth: 0, minHeight: 54, width: '100%', flexDirection: 'column', fontSize: '0.68rem' }}><WordPressIcon />وردپرس</Button></span></Tooltip>
          : onCommunity ? <Tooltip title="عملیات گفتگو" placement="left"><Button color="inherit" onClick={onCommunity} sx={{ minWidth: 0, minHeight: 54, width: '100%', flexDirection: 'column', fontSize: '0.68rem' }}><GroupsOutlined />عملیات گفتگو</Button></Tooltip>
          : null}
      </Stack>

      <BottomNavigation
        showLabels
        value={mobileSelected < 0 ? 0 : mobileSelected}
        onChange={(_event, index) => onSection(mobileSections[index]?.value || 'all')}
        sx={{ display: { xs: 'flex', md: 'none' }, width: '100%', height: 62, bgcolor: 'background.paper', '& .MuiBottomNavigationAction-root': { minWidth: 0, px: 0.25, minHeight: 56, fontSize: '0.68rem' } }}
      >
        {mobileSections.map(item => <BottomNavigationAction
          key={item.value}
          label={item.label}
          icon={<Badge badgeContent={item.count > 99 ? '99+' : item.count} max={99} color="secondary">{sectionIcon(item.value)}</Badge>}
          sx={item.value === 'favorite' ? {
            transform: 'translateY(-8px)',
            minWidth: 56,
            minHeight: 64,
            '& .MuiBadge-root': {
              bgcolor: activeSection === 'favorite' ? 'primary.main' : 'background.default',
              color: activeSection === 'favorite' ? 'primary.contrastText' : 'text.secondary',
              borderRadius: '50%',
              p: 1,
              boxShadow: 2,
              transition: theme => theme.transitions.create(['background-color', 'color', 'transform']),
              ...(activeSection === 'favorite' && {
                transform: 'scale(1.1)',
              })
            }
          } : undefined}
        />)}
      </BottomNavigation>
    </Paper>

    <Box sx={{ display: { xs: 'block', md: 'none' }, position: 'fixed', zIndex: theme => theme.zIndex.appBar + 1, top: 'max(8px, env(safe-area-inset-top))', insetInlineStart: 'max(8px, env(safe-area-inset-left))', bgcolor: 'background.paper', borderRadius: '50%', boxShadow: 2 }}>
      {menuButton}
    </Box>

    <Menu
      id="workspace-navigation-menu"
      anchorEl={anchor}
      open={Boolean(anchor)}
      onClose={close}
      slotProps={{ paper: { sx: { width: { xs: 'min(92vw, 360px)', sm: 360 }, maxHeight: 'min(82dvh, 720px)', p: 1 } } }}
    >
      <Box sx={{ px: 1, py: 1 }}>
        <Typography fontWeight={850}>{userName}</Typography>
        <Typography variant="caption" color="text.secondary">{userRole}</Typography>
      </Box>
      <Box sx={{ px: 1 }}>{accountControl}</Box>
      <Divider sx={{ my: 1 }} />
      <Stack spacing={0.25}>
        <Button fullWidth color="inherit" sx={{ justifyContent: 'flex-start' }} startIcon={<SettingsRounded />} onClick={() => invoke(onSettings)}>تنظیمات</Button>
        {onReporting && <Button fullWidth color="inherit" sx={{ justifyContent: 'flex-start' }} startIcon={<SummarizeRounded />} onClick={() => invoke(onReporting)}>سامانه گزارش‌های فرهنگی ۱۴۰۵</Button>}
        <Button fullWidth color="inherit" sx={{ justifyContent: 'flex-start' }} startIcon={<ContactsRounded />} onClick={() => invoke(onContacts)}>مدیریت مخاطبان</Button>
        {onAddDialog && <Button fullWidth color="inherit" sx={{ justifyContent: 'flex-start' }} startIcon={<AddCommentRounded />} disabled={!dialogsEnabled} onClick={() => invoke(onAddDialog)}>افزودن دستی گفتگو</Button>}
        {onSync && <Button fullWidth color="inherit" sx={{ justifyContent: 'flex-start' }} startIcon={<SyncRounded />} disabled={syncing || !dialogsEnabled} onClick={() => invoke(onSync)}>{syncing ? 'در حال همگام‌سازی…' : syncLabel}</Button>}
        {onBulk && <Button fullWidth color="inherit" sx={{ justifyContent: 'flex-start' }} startIcon={<SendRounded />} onClick={() => invoke(onBulk)}>ارسال و اقدام گروهی</Button>}
        {wordpressVisible && onWordpress && <Button fullWidth color="inherit" sx={{ justifyContent: 'flex-start' }} startIcon={<WordPressIcon />} disabled={!wordpressEnabled} onClick={() => invoke(onWordpress)}>ایجاد وردپرس</Button>}
      </Stack>
      <Divider sx={{ my: 1 }} />
      <Stack spacing={0.25}>
        <Button fullWidth color="error" sx={{ justifyContent: 'flex-start' }} startIcon={<LogoutRounded />} onClick={() => invoke(onMessengerLogout)}>{messengerLogoutLabel}</Button>
        {onSoftwareLogout && <Button fullWidth color="error" sx={{ justifyContent: 'flex-start' }} startIcon={<LogoutRounded />} onClick={() => invoke(onSoftwareLogout)}>خروج از نرم‌افزار</Button>}
      </Stack>
    </Menu>
  </>
}
