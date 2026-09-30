import { useEffect, useState, type ReactNode } from 'react'
import {
  AppBar, Box, Drawer, IconButton, List, ListItemButton, ListItemIcon, ListItemText,
  Toolbar, Typography, useMediaQuery, useTheme, Snackbar, Alert, Tooltip,
} from '@mui/material'
import DashboardIcon from '@mui/icons-material/Dashboard'
import TableChartIcon from '@mui/icons-material/TableChart'
import ShieldIcon from '@mui/icons-material/VerifiedUser'
import MapIcon from '@mui/icons-material/Map'
import WordPressIcon from '@mui/icons-material/Article'
import HubIcon from '@mui/icons-material/Hub'
import MenuIcon from '@mui/icons-material/Menu'
import { PeriodProvider, PeriodPicker, usePeriod } from './components/PeriodPicker'
import { ExcelRangeDialog } from './dialogs/ExcelRangeDialog'
import { api } from './api'
import DashboardPage from './pages/DashboardPage'
import WorksheetsPage from './pages/WorksheetsPage'
import MandatesPage from './pages/MandatesPage'
import DistrictsPage from './pages/DistrictsPage'
import WpPostsPage from './pages/WpPostsPage'
import SystemBridgePage from './pages/SystemBridgePage'
import SheetEventsPage from './pages/SheetEventsPage'

type Toast = { text: string; severity: 'success' | 'error' | 'info' } | null

export interface RouteState {
  tab: string
  params: Record<string, string>
}

export interface PageProps {
  notify: (text: string, severity?: Toast extends null ? never : 'success' | 'error' | 'info') => void
  openExcelDialog: () => void
  navigateTo?: (path: string) => void
  params?: Record<string, string>
}

const NAV = [
  { id: 'dashboard', label: 'داشبورد کلان', icon: <DashboardIcon />, el: DashboardPage },
  { id: 'worksheets', label: 'کارتابل کاربرگ‌ها', icon: <TableChartIcon />, el: WorksheetsPage },
  { id: 'mandates', label: 'اسناد بالادستی', icon: <ShieldIcon />, el: MandatesPage },
  { id: 'districts', label: 'شهرستان‌ها', icon: <MapIcon />, el: DistrictsPage },
  { id: 'wp', label: 'بسته‌های خبری وردپرس', icon: <WordPressIcon />, el: WpPostsPage },
  { id: 'bridge', label: 'پل ایتا و وردپرس', icon: <HubIcon />, el: SystemBridgePage },
] as const

// مسیریابی با hash — تب‌ها و صفحات عمیق شیت نشانه‌گذاری و اشتراک‌پذیر می‌شوند (#/sheet/80401)
export const parseHashRoute = (hash: string): RouteState => {
  const clean = hash.replace(/^#\/?/, '')
  const [path, queryString] = clean.split('?')
  const params: Record<string, string> = {}
  if (queryString) {
    new URLSearchParams(queryString).forEach((v, k) => {
      params[k] = v
    })
  }

  const segments = path.split('/').filter(Boolean)
  const root = segments[0] || 'dashboard'

  if (root === 'sheet' && segments[1]) {
    return {
      tab: 'sheet',
      params: { ...params, code: decodeURIComponent(segments[1]) },
    }
  }

  if (root === 'sheet') {
    return {
      tab: 'sheet',
      params,
    }
  }

  return {
    tab: root,
    params,
  }
}

export default function App() {
  const [route, setRoute] = useState<RouteState>(() => parseHashRoute(window.location.hash))
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [excelOpen, setExcelOpen] = useState(false)
  const [toast, setToast] = useState<Toast>(null)
  const muiTheme = useTheme()
  const isMobile = useMediaQuery(muiTheme.breakpoints.down('md'))

  useEffect(() => {
    const onHash = () => {
      setRoute(parseHashRoute(window.location.hash))
    }
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])

  const notify = (text: string, severity: 'success' | 'error' | 'info' = 'success') => setToast({ text, severity })
  const navigateTo = (path: string) => {
    const clean = path.replace(/^#?\/?/, '')
    window.location.hash = `/${clean}`
  }
  const setTab = (id: string) => {
    navigateTo(id)
  }
  const pageProps: PageProps = {
    notify,
    openExcelDialog: () => setExcelOpen(true),
    navigateTo,
    params: route.params,
  }

  let ActivePage: (props: PageProps) => ReactNode
  if (route.tab === 'sheet') {
    ActivePage = SheetEventsPage as (props: PageProps) => ReactNode
  } else {
    const active = NAV.find((n) => n.id === route.tab) ?? NAV[0]
    ActivePage = active.el as (props: PageProps) => ReactNode
  }

  const isNavActive = (id: string) => {
    if (route.tab === 'sheet') {
      return id === 'dashboard'
    }
    return route.tab === id
  }

  const navList = (
    <List sx={{ minWidth: 230 }} onClick={() => isMobile && setDrawerOpen(false)}>
      {NAV.map((n) => (
        <ListItemButton key={n.id} selected={isNavActive(n.id)} onClick={() => setTab(n.id)}>
          <ListItemIcon>{n.icon}</ListItemIcon>
          <ListItemText primary={n.label} />
        </ListItemButton>
      ))}
    </List>
  )

  return (
    <PeriodProvider>
      <Box sx={{ display: 'flex', flexDirection: 'column', minHeight: '100vh' }}>
        <AppBar position="static" color="primary" elevation={0}>
          <Toolbar sx={{ gap: 1, flexWrap: 'wrap' }}>
            {isMobile && (
              <IconButton color="inherit" edge="start" onClick={() => setDrawerOpen(true)} aria-label="منو">
                <MenuIcon />
              </IconButton>
            )}
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.2, flex: 1, minWidth: 240 }}>
              <ShieldIcon />
              <Box>
                <Typography variant="subtitle1" sx={{ fontWeight: 800, lineHeight: 1.2 }}>
                  سامانه جامع مدیریت و پایش گزارش‌های فرهنگی
                </Typography>
                <Typography variant="caption" sx={{ opacity: 0.85 }}>
                  دادگستری کل استان مازندران
                </Typography>
              </Box>
            </Box>
            <Tooltip title="صدور فایل اکسل برای دورهٔ انتخاب‌شده">
              <ExcelQuickButton onClick={() => setExcelOpen(true)} />
            </Tooltip>
          </Toolbar>
        </AppBar>

        {!isMobile && (
          <Box component="nav" sx={{ borderBottom: '1px solid #e2e8f0', background: '#fff' }}>
            <Box sx={{ display: 'flex', gap: 0.5, px: 2, overflowX: 'auto' }}>
              {NAV.map((n) => (
                <NavItem key={n.id} label={n.label} icon={n.icon} active={isNavActive(n.id)} onClick={() => setTab(n.id)} />
              ))}
            </Box>
          </Box>
        )}

        <Drawer open={isMobile && drawerOpen} onClose={() => setDrawerOpen(false)}>
          <Toolbar />
          {navList}
        </Drawer>

        {/* نوار دورهٔ زمانی مشترک — همهٔ صفحات گزارش‌دهی از آن پیروی می‌کنند */}
        <Box sx={{
          px: { xs: 1.5, md: 3 }, py: 1.2, background: '#fff',
          borderBottom: '1px solid #e2e8f0', position: 'sticky', top: 0, zIndex: 20,
        }}>
          <PeriodPicker compact={isMobile} />
        </Box>

        <Box component="main" sx={{ flex: 1, p: { xs: 1.5, md: 3 }, maxWidth: 1480, width: '100%', mx: 'auto' }}>
          <ActivePage {...pageProps} />
        </Box>

        <ExcelRangeDialog open={excelOpen} onClose={() => setExcelOpen(false)} notify={notify} />

        <Snackbar
          open={toast !== null}
          autoHideDuration={4200}
          onClose={() => setToast(null)}
          anchorOrigin={{ vertical: 'bottom', horizontal: 'left' }}
        >
          <Alert severity={toast?.severity ?? 'info'} variant="filled" onClose={() => setToast(null)}>
            {toast?.text}
          </Alert>
        </Snackbar>
      </Box>
    </PeriodProvider>
  )
}

function NavItem({ label, icon, active, onClick }: { label: string; icon: ReactNode; active: boolean; onClick: () => void }) {
  return (
    <ListItemButton
      selected={active}
      onClick={onClick}
      sx={{ borderRadius: 2, my: 0.5, whiteSpace: 'nowrap' }}
    >
      <ListItemIcon sx={{ minWidth: 34 }}>{icon}</ListItemIcon>
      <ListItemText primary={label} primaryTypographyProps={{ fontSize: 13.5, fontWeight: active ? 800 : 500 }} />
    </ListItemButton>
  )
}

function ExcelQuickButton({ onClick }: { onClick: () => void }) {
  const { period } = usePeriod()
  return (
    <IconButton color="inherit" onClick={onClick} aria-label="صدور اکسل دوره">
      <TableChartIcon />
      <Typography variant="caption" sx={{ mr: 0.8, display: { xs: 'none', md: 'inline' } }}>
        اکسل {period.label}
      </Typography>
    </IconButton>
  )
}

// اطمینان از لود شدن ماژول api (جلوگیری از tree-shake اشتباه در حالت dev)
void api
