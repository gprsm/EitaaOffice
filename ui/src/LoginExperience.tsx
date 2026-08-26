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

  return <Stack spacing={2}>
    <Box
      aria-label="پیش‌نمایش پس‌زمینه صفحه ورود"
      sx={{
        position: 'relative',
        minHeight: { xs: 170, sm: 210 },
        overflow: 'hidden',
        border: 1,
        borderColor: 'divider',
        borderRadius: 2.25,
        background: 'linear-gradient(145deg, #16253a, #09111e)',
      }}
    >
      {(loading || busy === 'select') && <Skeleton variant="rectangular" animation="wave" width="100%" height="100%" sx={{ position: 'absolute', inset: 0 }} />}
      {!loading && busy !== 'select' && appearance.backgroundDataUrl && <Box component="img" src={appearance.backgroundDataUrl} alt="پیش‌نمایش تصویر انتخاب‌شده" sx={{ position: 'absolute', inset: 0, width: '100%', height: '100%', display: 'block', objectFit: 'cover', objectPosition: appearance.position }} />}
      {!loading && busy !== 'select' && !appearance.backgroundDataUrl && <Stack alignItems="center" justifyContent="center" spacing={1} sx={{ position: 'absolute', inset: 0, p: 3, color: 'rgba(235, 245, 255, .7)', textAlign: 'center' }}>
        <ImageOutlined />
        <Typography variant="body2">در حال حاضر از پس‌زمینهٔ گرادیانی امن استفاده می‌شود.</Typography>
      </Stack>}
      <Box sx={{ position: 'absolute', inset: 0, backgroundColor: `rgba(3, 8, 18, ${overlay})` }} />
      <Box sx={{ position: 'absolute', top: '19%', insetInlineEnd: '12%', width: 'min(37%, 150px)', height: '62%', border: '1px solid rgba(255, 255, 255, .28)', borderRadius: 1.5, bgcolor: 'rgba(20, 28, 39, .72)', boxShadow: '0 12px 35px rgba(0, 0, 0, .35)', backdropFilter: 'blur(8px)' }} />
    </Box>

    <Box>
      <Typography variant="subtitle2" gutterBottom>تصویر پس‌زمینه</Typography>
      <Typography variant="caption" color="text.secondary">
        PNG، JPEG، WebP یا AVIF تا ۱۵ مگابایت؛ تصویر در پوشه Runtime برنامه کپی می‌شود و فایل اصلی جابه‌جا نخواهد شد.
      </Typography>
      {appearance.backgroundFileName && <Typography variant="caption" dir="auto" sx={{ display: 'block', mt: 1, overflow: 'hidden', color: 'primary.main', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{appearance.backgroundFileName}</Typography>}
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

  return <Box dir="rtl" sx={{ position: 'relative', isolation: 'isolate', minHeight: '100dvh', overflow: 'auto', color: '#f7f9fc', bgcolor: '#070b12' }}>
    <Box aria-hidden sx={{ position: 'fixed', zIndex: -2, inset: 0, overflow: 'hidden', pointerEvents: 'none', background: 'radial-gradient(circle at 16% 22%, rgba(43, 139, 211, .38), transparent 35%), linear-gradient(145deg, #111c2b, #07101b 55%, #08151a)' }}>
      {(loading || (appearance.backgroundDataUrl && !imageReady)) && <Skeleton variant="rectangular" animation="wave" width="100%" height="100%" sx={{ position: 'absolute', inset: 0, transform: 'none', bgcolor: 'rgba(43, 56, 74, .88)' }} />}
      {appearance.backgroundDataUrl && <Box
        component="img"
        src={appearance.backgroundDataUrl}
        alt=""
        onLoad={() => setImageReady(true)}
        onError={() => setImageReady(true)}
        sx={{ position: 'absolute', inset: 0, width: '100%', height: '100%', display: 'block', objectFit: 'cover', objectPosition: appearance.position, opacity: imageReady ? 1 : 0, transition: 'opacity 280ms ease', '@media (prefers-reduced-motion: reduce)': { transition: 'none' } }}
      />}
    </Box>
    <Box aria-hidden sx={{ position: 'fixed', zIndex: -1, inset: 0, pointerEvents: 'none', background: `linear-gradient(90deg, rgba(3, 8, 18, .22), rgba(3, 8, 18, .06) 42%, rgba(3, 8, 18, .3)), rgba(3, 8, 18, ${appearance.overlay})` }} />

    <IconButton
      aria-label="تنظیم ظاهر صفحه ورود"
      title="تنظیم ظاهر صفحه ورود"
      onClick={() => setSettingsOpen(true)}
      sx={{ position: 'fixed', zIndex: 4, top: 'max(12px, env(safe-area-inset-top))', insetInlineStart: 'max(12px, env(safe-area-inset-left))', color: '#f7f9fc', bgcolor: 'rgba(10, 17, 27, .62)', border: '1px solid rgba(255, 255, 255, .18)', backdropFilter: 'blur(14px)', '&:hover': { bgcolor: 'rgba(26, 38, 54, .84)' } }}
    >
      <SettingsRounded />
    </IconButton>

    <Box sx={{ width: '100%', minHeight: '100dvh', mx: 'auto', px: { xs: 'max(12px, env(safe-area-inset-right))', sm: 'max(28px, env(safe-area-inset-right))' }, pt: 'max(68px, env(safe-area-inset-top))', pb: 'max(18px, env(safe-area-inset-bottom))', display: 'grid', placeItems: 'center' }}>
      <Paper
        elevation={24}
        sx={{
          width: '100%',
          maxWidth: 440,
          justifySelf: 'center',
          p: { xs: 2, sm: 'clamp(22px, 4vw, 38px)' },
          overflow: 'hidden',
          border: 1,
          borderRadius: { xs: 2.5, sm: 3.25 },
          boxShadow: '0 28px 90px rgba(0, 0, 0, .44)',
          backdropFilter: 'blur(24px) saturate(125%)',
          bgcolor: theme.palette.mode === 'dark' ? 'rgba(16, 23, 34, .9)' : 'rgba(255, 255, 255, .92)',
          borderColor: theme.palette.mode === 'dark' ? 'rgba(255,255,255,.13)' : 'rgba(255,255,255,.72)',
          '& .MuiButton-root': { minHeight: 46 },
          '& .MuiAlert-root': { textAlign: 'start' },
        }}
      >
        {children}
      </Paper>
    </Box>

    <Dialog open={settingsOpen} onClose={() => setSettingsOpen(false)} fullWidth maxWidth="sm" fullScreen={fullScreen} dir="rtl">
      <DialogTitle>ظاهر صفحه ورود</DialogTitle>
      <IconButton aria-label="بستن" onClick={() => setSettingsOpen(false)} sx={{ position: 'absolute', top: 10, insetInlineEnd: 10 }}><CloseRounded /></IconButton>
      <DialogContent dividers><LoginAppearanceSettingsPanel /></DialogContent>
      <DialogActions><Button onClick={() => setSettingsOpen(false)}>بستن</Button></DialogActions>
    </Dialog>
  </Box>
}
