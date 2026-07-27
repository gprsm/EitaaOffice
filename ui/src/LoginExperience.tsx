import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react'
import {
  Alert,
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  IconButton,
  Paper,
  Skeleton,
  Slider,
  Stack,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
  useMediaQuery,
  useTheme,
} from '@mui/material'
import CloseRounded from '@mui/icons-material/CloseRounded'
import DeleteOutlineRounded from '@mui/icons-material/DeleteOutlineRounded'
import ImageOutlined from '@mui/icons-material/ImageOutlined'
import SettingsRounded from '@mui/icons-material/SettingsRounded'
import ShieldOutlined from '@mui/icons-material/ShieldOutlined'

const DEFAULT_APPEARANCE: LoginAppearanceValue = {
  backgroundDataUrl: null,
  backgroundFile: null,
  backgroundFileName: null,
  position: 'center',
  overlay: 0.58,
}

type LoginAppearanceContextValue = {
  appearance: LoginAppearanceValue
  loading: boolean
  selectBackground: () => Promise<void>
  save: (value: Pick<LoginAppearanceValue, 'position' | 'overlay'>) => Promise<void>
  clearBackground: () => Promise<void>
}

const LoginAppearanceContext = createContext<LoginAppearanceContextValue>({
  appearance: DEFAULT_APPEARANCE,
  loading: true,
  selectBackground: async () => undefined,
  save: async () => undefined,
  clearBackground: async () => undefined,
})

function normalizeAppearance(value?: Partial<LoginAppearanceValue> | null): LoginAppearanceValue {
  const position = value?.position === 'top' || value?.position === 'bottom' ? value.position : 'center'
  const selectedOverlay = Number(value?.overlay)
  return {
    backgroundDataUrl: value?.backgroundDataUrl || null,
    backgroundFile: value?.backgroundFile || null,
    backgroundFileName: value?.backgroundFileName || null,
    position,
    overlay: Number.isFinite(selectedOverlay) ? Math.min(0.82, Math.max(0.2, selectedOverlay)) : 0.58,
  }
}

export function LoginAppearanceProvider({ children }: { children: ReactNode }) {
  const [appearance, setAppearance] = useState<LoginAppearanceValue>(DEFAULT_APPEARANCE)
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    setLoading(true)
    try { setAppearance(normalizeAppearance(await window.eitaaDesktop.loginAppearance.get())) }
    catch { setAppearance(DEFAULT_APPEARANCE) }
    finally { setLoading(false) }
  }, [])

  useEffect(() => { void load() }, [load])

  const selectBackground = useCallback(async () => {
    setLoading(true)
    try { setAppearance(normalizeAppearance(await window.eitaaDesktop.loginAppearance.selectBackground())) }
    finally { setLoading(false) }
  }, [])

  const save = useCallback(async (value: Pick<LoginAppearanceValue, 'position' | 'overlay'>) => {
    setLoading(true)
    try { setAppearance(normalizeAppearance(await window.eitaaDesktop.loginAppearance.save(value))) }
    finally { setLoading(false) }
  }, [])

  const clearBackground = useCallback(async () => {
    setLoading(true)
    try { setAppearance(normalizeAppearance(await window.eitaaDesktop.loginAppearance.clearBackground())) }
    finally { setLoading(false) }
  }, [])

  const context = useMemo(
    () => ({ appearance, loading, selectBackground, save, clearBackground }),
    [appearance, clearBackground, loading, save, selectBackground],
  )
  return <LoginAppearanceContext.Provider value={context}>{children}</LoginAppearanceContext.Provider>
}

export function useLoginAppearance() {
  return useContext(LoginAppearanceContext)
}

export function LoginAppearanceSettingsPanel() {
  const { appearance, loading, selectBackground, save, clearBackground } = useLoginAppearance()
  const [position, setPosition] = useState<LoginAppearanceValue['position']>(appearance.position)
  const [overlay, setOverlay] = useState(appearance.overlay)
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    setPosition(appearance.position)
    setOverlay(appearance.overlay)
  }, [appearance.overlay, appearance.position])

  const run = async (name: string, action: () => Promise<void>) => {
    setBusy(name)
    setError('')
    try { await action() }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'تغییر ظاهر صفحه ورود ناموفق بود.') }
    finally { setBusy('') }
  }

  return <Stack className="login-appearance-settings" spacing={2}>
    <Box className="login-appearance-preview" aria-label="پیش‌نمایش پس‌زمینه صفحه ورود">
      {(loading || busy === 'select') && <Skeleton variant="rectangular" animation="wave" width="100%" height="100%" />}
      {!loading && busy !== 'select' && appearance.backgroundDataUrl && <Box component="img" src={appearance.backgroundDataUrl} alt="پیش‌نمایش تصویر انتخاب‌شده" sx={{ objectPosition: appearance.position }} />}
      {!loading && busy !== 'select' && !appearance.backgroundDataUrl && <Stack alignItems="center" justifyContent="center" spacing={1} className="login-appearance-empty">
        <ImageOutlined />
        <Typography variant="body2">در حال حاضر از پس‌زمینهٔ گرادیانی امن استفاده می‌شود.</Typography>
      </Stack>}
      <Box className="login-appearance-preview-shade" sx={{ backgroundColor: `rgba(3, 8, 18, ${overlay})` }} />
      <Box className="login-appearance-preview-card" />
    </Box>

    <Box>
      <Typography variant="subtitle2" gutterBottom>تصویر پس‌زمینه</Typography>
      <Typography variant="caption" color="text.secondary">
        PNG، JPEG، WebP یا AVIF تا ۱۵ مگابایت؛ تصویر در پوشه Runtime برنامه کپی می‌شود و فایل اصلی جابه‌جا نخواهد شد.
      </Typography>
      {appearance.backgroundFileName && <Typography variant="caption" className="login-appearance-file" dir="auto">{appearance.backgroundFileName}</Typography>}
    </Box>

    <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1}>
      <Button
        variant="contained"
        startIcon={<ImageOutlined />}
        disabled={Boolean(busy)}
        onClick={() => void run('select', selectBackground)}
      >
        {busy === 'select' ? 'در حال بارگذاری…' : appearance.backgroundDataUrl ? 'تغییر تصویر' : 'انتخاب تصویر'}
      </Button>
      <Button
        variant="outlined"
        color="error"
        startIcon={<DeleteOutlineRounded />}
        disabled={Boolean(busy) || !appearance.backgroundDataUrl}
        onClick={() => void run('clear', clearBackground)}
      >
        حذف تصویر
      </Button>
    </Stack>

    <Box>
      <Typography variant="subtitle2" gutterBottom>محل تمرکز تصویر</Typography>
      <ToggleButtonGroup
        exclusive
        fullWidth
        size="small"
        value={position}
        onChange={(_event, value: LoginAppearanceValue['position'] | null) => { if (value) setPosition(value) }}
        aria-label="محل تمرکز تصویر"
      >
        <ToggleButton value="top">بالا</ToggleButton>
        <ToggleButton value="center">مرکز</ToggleButton>
        <ToggleButton value="bottom">پایین</ToggleButton>
      </ToggleButtonGroup>
    </Box>

    <Box>
      <Typography variant="subtitle2">تیرگی لایهٔ خوانایی: {Math.round(overlay * 100).toLocaleString('fa-IR')}٪</Typography>
      <Slider
        min={0.2}
        max={0.82}
        step={0.02}
        value={overlay}
        onChange={(_event, value) => setOverlay(value as number)}
        aria-label="تیرگی لایه خوانایی"
      />
    </Box>

    {error && <Alert severity="error">{error}</Alert>}
    <Button
      variant="outlined"
      disabled={Boolean(busy) || loading}
      onClick={() => void run('save', () => save({ position, overlay }))}
    >
      {busy === 'save' ? 'در حال ذخیره…' : 'ذخیره تنظیمات ظاهر'}
    </Button>
  </Stack>
}

export function LoginSurface({ children }: { children: ReactNode }) {
  const { appearance, loading } = useLoginAppearance()
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [imageReady, setImageReady] = useState(false)
  const theme = useTheme()
  const fullScreen = useMediaQuery(theme.breakpoints.down('sm'))

  useEffect(() => { setImageReady(false) }, [appearance.backgroundDataUrl])

  return <Box
    className="login-screen"
    dir="rtl"
    sx={{ '--login-overlay': appearance.overlay } as React.CSSProperties}
  >
    <Box className="login-background-layer" aria-hidden>
      {(loading || (appearance.backgroundDataUrl && !imageReady)) && <Skeleton className="login-background-skeleton" variant="rectangular" animation="wave" width="100%" height="100%" />}
      {appearance.backgroundDataUrl && <Box
        component="img"
        src={appearance.backgroundDataUrl}
        alt=""
        onLoad={() => setImageReady(true)}
        onError={() => setImageReady(true)}
        sx={{ objectPosition: appearance.position, opacity: imageReady ? 1 : 0 }}
      />}
    </Box>
    <Box className="login-background-overlay" aria-hidden />

    <IconButton
      className="login-settings-button"
      aria-label="تنظیم ظاهر صفحه ورود"
      title="تنظیم ظاهر صفحه ورود"
      onClick={() => setSettingsOpen(true)}
    >
      <SettingsRounded />
    </IconButton>

    <Box className="login-layout">
      <Stack className="login-intro" spacing={2.25}>
        <Box className="login-brand-lockup">
          <Box className="login-brand-mark">EB</Box>
          <Box>
            <Typography component="p" className="login-eyebrow">EITAA BRIDGE</Typography>
            <Typography component="h1" variant="h3">مرکز یکپارچهٔ محتوای ایتا</Typography>
          </Box>
        </Box>
        <Typography className="login-intro-copy">
          ورود امن، مدیریت گفتگوها و آماده‌سازی محتوا برای انتشار؛ با حفظ داده‌ها و نشست در همین رایانه.
        </Typography>
        <Paper className="login-isolation-note" elevation={0}>
          <ShieldOutlined />
          <Box>
            <Typography variant="subtitle2">آماده برای معماری چندحسابی ایزوله</Typography>
            <Typography variant="caption">هر حساب باید Session، Scheduler و فضای دادهٔ مستقل خود را داشته باشد؛ این صفحه بر همان مرز طراحی شده است.</Typography>
          </Box>
        </Paper>
      </Stack>

      <Paper
        className="login-panel"
        elevation={24}
        sx={{
          bgcolor: theme.palette.mode === 'dark' ? 'rgba(16, 23, 34, .9)' : 'rgba(255, 255, 255, .92)',
          borderColor: theme.palette.mode === 'dark' ? 'rgba(255,255,255,.13)' : 'rgba(255,255,255,.72)',
        }}
      >
        {children}
      </Paper>
    </Box>

    <Dialog open={settingsOpen} onClose={() => setSettingsOpen(false)} fullWidth maxWidth="sm" fullScreen={fullScreen} dir="rtl">
      <DialogTitle>ظاهر صفحه ورود</DialogTitle>
      <IconButton className="login-appearance-close" aria-label="بستن" onClick={() => setSettingsOpen(false)}><CloseRounded /></IconButton>
      <DialogContent dividers><LoginAppearanceSettingsPanel /></DialogContent>
      <DialogActions><Button onClick={() => setSettingsOpen(false)}>بستن</Button></DialogActions>
    </Dialog>
  </Box>
}
