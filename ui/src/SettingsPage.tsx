import { useCallback, useEffect, useState } from 'react'
import {
  Alert,
  Box,
  Button,
  Checkbox,
  Chip,
  Divider,
  FormControlLabel,
  MenuItem,
  Paper,
  Stack,
  Switch,
  TextField,
  Typography,
} from '@mui/material'
import CloseRounded from '@mui/icons-material/CloseRounded'
import DeleteOutlineRounded from '@mui/icons-material/DeleteOutlineRounded'
import FolderOpenRounded from '@mui/icons-material/FolderOpenRounded'
import RouterRounded from '@mui/icons-material/RouterRounded'
import SaveRounded from '@mui/icons-material/SaveRounded'
import VerifiedRounded from '@mui/icons-material/VerifiedRounded'
import { api } from './lib/api'
import type { Site } from './lib/types'
import { LoginAppearanceSettingsPanel } from './LoginExperience'
import { AppUserManagementPanel } from './AppUserManagementPanel'
import { MessengerAccountManagementPanel } from './MessengerAccountGate'
import { ServiceAccountSettingsPanel } from './ServiceAccountSettingsPanel'

type SiteForm = {
  site_key: string
  base_url: string
  default_status: string
  default_category_id: string | number
  timeout_seconds: number
  verify_tls: boolean
  retry_attempts: number
  allow_insecure_http: boolean
  username: string
  application_password: string
  is_default: boolean
  username_configured?: boolean
  application_password_configured?: boolean
}

type DeploymentSettings = {
  mode: 'desktop_loopback' | 'trusted_lan_http' | 'web_reverse_proxy'
  bind_host: string
  bind_port: number
  restart_required: boolean
  proxy_update_required: boolean
  can_manage: boolean
}

const emptySite = (): SiteForm => ({
  site_key: '',
  base_url: 'http://localhost',
  default_status: 'draft',
  default_category_id: '',
  timeout_seconds: 30,
  verify_tls: false,
  retry_attempts: 2,
  allow_insecure_http: true,
  username: '',
  application_password: '',
  is_default: false,
})

export function SettingsPage({
  sites,
  onChanged,
  onClose,
  showWordPressPanel,
  onShowWordPressPanelChange,
}: {
  sites: Site[]
  onChanged: () => Promise<void> | void
  onClose: () => void
  showWordPressPanel: boolean
  onShowWordPressPanelChange: (value: boolean) => void
}) {
  const [items, setItems] = useState<Site[]>(sites)
  const [form, setForm] = useState<SiteForm>(emptySite)
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [network, setNetwork] = useState<DeploymentSettings | null>(null)
  const [portDraft, setPortDraft] = useState('')
  const [portConfirmed, setPortConfirmed] = useState(false)

  const load = useCallback(async () => {
    const response = await api<{ sites: Site[] }>('GET', '/api/v1/settings/sites')
    setItems(response.sites)
  }, [])

  const loadNetwork = useCallback(async () => {
    const response = await api<DeploymentSettings>('GET', '/api/v2/settings/deployment')
    setNetwork(response)
    setPortDraft(String(response.bind_port))
  }, [])

  useEffect(() => {
    void Promise.all([load(), loadNetwork()]).catch(reason => {
      setError(reason instanceof Error ? reason.message : 'خواندن تنظیمات ناموفق بود.')
    })
  }, [load, loadNetwork])

  const savePort = async () => {
    setBusy('port'); setError(''); setMessage('')
    try {
      const response = await api<DeploymentSettings>('POST', '/api/v2/settings/deployment/port', {
        port: Number(portDraft),
        confirm: portConfirmed,
      })
      setNetwork(response)
      setPortDraft(String(response.bind_port))
      setPortConfirmed(false)
      setMessage(response.proxy_update_required
        ? 'پورت داخلی ذخیره شد. برنامه را دوباره اجرا و پورت مقصد Laragon یا Reverse Proxy را نیز با همین مقدار هماهنگ کنید.'
        : 'پورت داخلی ذخیره شد. برای اعمال آن، برنامه را ببندید و دوباره اجرا کنید.')
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'ذخیره پورت ناموفق بود.')
    } finally { setBusy('') }
  }

  const edit = (site: Site) => setForm({
    site_key: site.site_key,
    base_url: site.base_url,
    default_status: site.default_status,
    default_category_id: site.default_category_id ?? '',
    timeout_seconds: site.timeout_seconds ?? 30,
    verify_tls: Boolean(site.verify_tls),
    retry_attempts: site.retry_attempts ?? 2,
    allow_insecure_http: Boolean(site.allow_insecure_http),
    username: '',
    application_password: '',
    is_default: site.is_default,
    username_configured: site.username_configured,
    application_password_configured: site.application_password_configured,
  })

  const sitePayload = () => {
    const payload: Record<string, unknown> = {
      ...form,
      default_category_id: form.default_category_id === '' ? null : Number(form.default_category_id),
      timeout_seconds: Number(form.timeout_seconds),
      retry_attempts: Number(form.retry_attempts),
    }
    if (!form.username) delete payload.username
    if (!form.application_password) delete payload.application_password
    delete payload.username_configured
    delete payload.application_password_configured
    return payload
  }

  const persistForm = async (announce = true) => {
    const response = await api<{ sites: Site[] }>('POST', '/api/v1/settings/sites/upsert', sitePayload())
    setItems(response.sites)
    const saved = response.sites.find(item => item.site_key === form.site_key)
    if (saved) edit(saved)
    await onChanged()
    if (announce) setMessage('تنظیمات سایت ذخیره شد و نسخهٔ پشتیبان تنظیمات باقی ماند.')
  }

  const save = async () => {
    setBusy('save'); setError(''); setMessage('')
    try { await persistForm(true) }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'ذخیره تنظیمات ناموفق بود.') }
    finally { setBusy('') }
  }

  const test = async () => {
    setBusy('test'); setError(''); setMessage('')
    try {
      await persistForm(false)
      await api('POST', '/api/v1/settings/sites/test', { site_key: form.site_key })
      setMessage('تنظیمات ذخیره شد و اتصال و احراز هویت وردپرس تأیید شد.')
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'ذخیره یا آزمون اتصال ناموفق بود.')
    } finally { setBusy('') }
  }

  const makeDefault = async (site: Site) => {
    setBusy(`default-${site.site_key}`); setError(''); setMessage('')
    try {
      const response = await api<{ sites: Site[] }>('POST', '/api/v1/settings/sites/default', { site_key: site.site_key })
      setItems(response.sites)
      await onChanged()
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'تغییر سایت پیش‌فرض ناموفق بود.')
    } finally { setBusy('') }
  }

  const remove = async (site: Site) => {
    if (!confirm(`سایت «${site.site_key}» حذف شود؟ نسخه پشتیبان تنظیمات باقی می‌ماند.`)) return
    setBusy(`delete-${site.site_key}`); setError(''); setMessage('')
    try {
      const response = await api<{ sites: Site[] }>('POST', '/api/v1/settings/sites/delete', { site_key: site.site_key, confirm: true })
      setItems(response.sites)
      setForm(emptySite())
      await onChanged()
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'حذف سایت ناموفق بود.')
    } finally { setBusy('') }
  }

  const updateBaseUrl = (base_url: string) => {
    const localHttp = /^http:\/\//i.test(base_url)
    const https = /^https:\/\//i.test(base_url)
    setForm(current => ({
      ...current,
      base_url,
      allow_insecure_http: localHttp ? true : current.allow_insecure_http,
      verify_tls: localHttp ? false : https ? true : current.verify_tls,
    }))
  }

  return <Box sx={{ minHeight: '100%', bgcolor: 'background.default', p: { xs: 1.5, sm: 2.5, lg: 3 } }}>
    <Stack spacing={2.5} sx={{ width: '100%', maxWidth: 1280, mx: 'auto' }}>
      <Stack direction="row" alignItems="center" justifyContent="space-between" gap={2}>
        <Box>
          <Typography variant="h4" component="h1">تنظیمات</Typography>
          <Typography variant="body2" color="text.secondary">
            کاربران، حساب‌های پیام‌رسان، ظاهر ورود و سایت‌های وردپرس در بخش‌های مستقل مدیریت می‌شوند.
          </Typography>
        </Box>
        <Button startIcon={<CloseRounded />} disabled={Boolean(busy)} onClick={onClose}>بازگشت</Button>
      </Stack>

      {error && <Alert severity="error">{error}</Alert>}
      {message && <Alert severity="success">{message}</Alert>}

      <Paper variant="outlined" sx={{ p: { xs: 2, md: 2.5 } }}>
        <Stack spacing={2}>
          <Box>
            <Typography variant="h6">ظاهر صفحه ورود</Typography>
            <Typography variant="body2" color="text.secondary">تصویر انتخاب‌شده فقط در Runtime محلی برنامه نگهداری می‌شود.</Typography>
          </Box>
          <LoginAppearanceSettingsPanel />
        </Stack>
      </Paper>

      <AppUserManagementPanel />
      <MessengerAccountManagementPanel />
      <Paper variant="outlined" sx={{ p: { xs: 2, md: 2.5 } }}>
        <ServiceAccountSettingsPanel />
      </Paper>

      <Paper variant="outlined" sx={{ p: { xs: 2, md: 2.5 } }}>
        <Stack spacing={1}>
          <Typography variant="h6">نمایش پنل وردپرس</Typography>
          <FormControlLabel
            control={<Switch checked={showWordPressPanel} onChange={event => onShowWordPressPanelChange(event.target.checked)} />}
            label="پنل ساخت و انتشار نوشتهٔ وردپرس نمایش داده شود"
          />
          <Typography variant="body2" color="text.secondary">
            این گزینه به‌صورت پیش‌فرض خاموش است. تا وقتی روشن نباشد و دسترسی یک سایت کامل نشده باشد، دسته‌ها و برچسب‌های وردپرس بررسی نمی‌شوند و فقط عملیات گفتگو نمایش داده می‌شود.
          </Typography>
          {showWordPressPanel && !items.some(site => site.credentials_configured) && <Alert severity="info">
            پنل درخواست شده است، اما ابتدا باید نشانی، نام کاربری و رمز برنامهٔ یک سایت وردپرس را کامل و آزمون کنید.
          </Alert>}
        </Stack>
      </Paper>


      <Paper variant="outlined" sx={{ p: { xs: 2, md: 2.5 } }}>
        <Stack spacing={2}>
          <Stack direction={{ xs: 'column', sm: 'row' }} alignItems={{ sm: 'center' }} justifyContent="space-between" gap={1}>
            <Box>
              <Typography variant="h6">شبکه و وب</Typography>
              <Typography variant="body2" color="text.secondary">
                این بخش تنها محل تنظیم پورت داخلی برنامه است؛ نشانی‌های مجاز داخلی نیز خودکار هماهنگ می‌شوند.
              </Typography>
            </Box>
            {network && <Chip
              icon={<RouterRounded />}
              label={network.mode === 'web_reverse_proxy' ? 'وب با Reverse Proxy' : network.mode === 'trusted_lan_http' ? 'شبکه خصوصی' : 'فقط همین رایانه'}
              color={network.mode === 'web_reverse_proxy' ? 'primary' : 'default'}
            />}
          </Stack>
          <Divider />
          {network?.proxy_update_required && <Alert severity="info">
            این مقدار پورت داخلی Backend است. پورت عمومی ۸۰/۴۴۳ تغییر نمی‌کند؛ پس از ذخیره، مقصد Laragon یا Reverse Proxy باید به همین پورت داخلی اشاره کند.
          </Alert>}
          {network?.restart_required && <Alert severity="warning">
            تغییر ذخیره شده است و پس از اجرای مجدد برنامه اعمال می‌شود.
          </Alert>}
          {network && !network.can_manage && <Alert severity="info">
            مشاهده برای شما مجاز است، اما فقط مدیر سامانه می‌تواند پورت را تغییر دهد.
          </Alert>}
          <Stack component="form" spacing={1.5} onSubmit={event => { event.preventDefault(); void savePort() }}>
            <TextField
              label="پورت داخلی برنامه"
              type="number"
              value={portDraft}
              onChange={event => setPortDraft(event.target.value.replace(/[^0-9]/g, ''))}
              disabled={!network?.can_manage || busy === 'port'}
              inputProps={{ min: 1, max: 65535, dir: 'ltr', inputMode: 'numeric' }}
              helperText={network ? `نشانی اتصال داخلی: ${network.bind_host}:${network.bind_port}` : 'در حال خواندن پورت فعلی…'}
            />
            <FormControlLabel
              control={<Checkbox checked={portConfirmed} onChange={event => setPortConfirmed(event.target.checked)} disabled={!network?.can_manage || busy === 'port'} />}
              label="می‌دانم پس از ذخیره برنامه باید دوباره اجرا شود"
            />
            <Button
              type="submit"
              variant="contained"
              startIcon={<SaveRounded />}
              disabled={!network?.can_manage || !portConfirmed || !portDraft || busy === 'port'}
              sx={{ alignSelf: { sm: 'flex-start' } }}
            >
              {busy === 'port' ? 'در حال ذخیره…' : 'ذخیره پورت'}
            </Button>
          </Stack>
        </Stack>
      </Paper>

      <Paper variant="outlined" sx={{ p: { xs: 2, md: 2.5 } }}>
        <Stack spacing={2}>
          <Box>
            <Typography variant="h6">سایت‌ها و دسترسی وردپرس</Typography>
            <Typography variant="body2" color="text.secondary">
              رمز برنامه در فایل محلی امن ذخیره می‌شود و هیچ‌گاه دوباره در رابط نمایش داده نمی‌شود.
            </Typography>
          </Box>
          <Divider />
          <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', lg: 'minmax(280px, .75fr) minmax(0, 1.25fr)' }, gap: 2 }}>
            <Stack spacing={1.25}>
              <Button variant="outlined" onClick={() => setForm(emptySite())}>افزودن سایت جدید</Button>
              {items.map(site => <Paper
                key={site.site_key}
                variant="outlined"
                sx={{ p: 1.5, borderColor: form.site_key === site.site_key ? 'primary.main' : undefined }}
              >
                <Stack spacing={1}>
                  <Button
                    variant="text"
                    color="inherit"
                    onClick={() => edit(site)}
                    sx={{ justifyContent: 'flex-start', textAlign: 'start', px: 0.5 }}
                  >
                    <Box sx={{ flex: 1 }}>
                      <Typography fontWeight={800} dir="ltr">{site.site_key}</Typography>
                      <Typography variant="body2" color="text.secondary" dir="ltr" noWrap>{site.base_url}</Typography>
                    </Box>
                  </Button>
                  <Stack direction="row" gap={1} flexWrap="wrap">
                    {site.is_default && <Chip size="small" color="primary" label="پیش‌فرض" />}
                    <Chip size="small" color={site.credentials_configured ? 'success' : 'default'} label={site.credentials_configured ? 'دسترسی آماده' : 'دسترسی ناقص'} />
                  </Stack>
                  <Stack direction="row" gap={1}>
                    <Button size="small" disabled={site.is_default || Boolean(busy)} onClick={() => void makeDefault(site)}>پیش‌فرض</Button>
                    <Button size="small" color="error" startIcon={<DeleteOutlineRounded />} disabled={Boolean(busy)} onClick={() => void remove(site)}>حذف</Button>
                  </Stack>
                </Stack>
              </Paper>)}
              {!items.length && <Alert severity="info">هنوز سایتی تعریف نشده است.</Alert>}
            </Stack>

            <Stack spacing={1.5} component="form" onSubmit={event => { event.preventDefault(); void save() }}>
              <Typography variant="subtitle1" fontWeight={800}>{form.site_key ? 'ویرایش اتصال' : 'اتصال جدید'}</Typography>
              <TextField
                label="کلید سایت"
                value={form.site_key}
                onChange={event => setForm(current => ({ ...current, site_key: event.target.value.toLowerCase().replace(/[^a-z0-9-]/g, '-') }))}
                placeholder="medical-site"
                inputProps={{ dir: 'ltr', spellCheck: false }}
              />
              <TextField
                label="نشانی سایت"
                value={form.base_url}
                onChange={event => updateBaseUrl(event.target.value)}
                placeholder="http://localhost یا https://example.com"
                inputProps={{ dir: 'ltr', spellCheck: false }}
                helperText="برای شبکهٔ خصوصی از localhost یا IP خصوصی استفاده کنید."
              />
              <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr' }, gap: 1.5 }}>
                <TextField select label="وضعیت پیش‌فرض" value={form.default_status} onChange={event => setForm(current => ({ ...current, default_status: event.target.value }))}>
                  <MenuItem value="draft">پیش‌نویس</MenuItem>
                  <MenuItem value="pending">در انتظار بررسی</MenuItem>
                  <MenuItem value="private">خصوصی</MenuItem>
                  <MenuItem value="publish">انتشار</MenuItem>
                </TextField>
                <TextField label="شناسه دسته پیش‌فرض" type="number" value={form.default_category_id} onChange={event => setForm(current => ({ ...current, default_category_id: event.target.value }))} inputProps={{ min: 1 }} />
              </Box>
              <TextField
                label="نام کاربری وردپرس"
                value={form.username}
                onChange={event => setForm(current => ({ ...current, username: event.target.value }))}
                autoComplete="username"
                inputProps={{ dir: 'ltr', spellCheck: false }}
                placeholder={form.username_configured ? 'ذخیره شده؛ برای تغییر مقدار جدید وارد کنید' : 'eitaa-user'}
              />
              <TextField
                label="رمز برنامه وردپرس"
                type="password"
                value={form.application_password}
                onChange={event => setForm(current => ({ ...current, application_password: event.target.value }))}
                autoComplete="new-password"
                inputProps={{ dir: 'ltr' }}
                placeholder={form.application_password_configured ? 'ذخیره شده؛ برای تغییر مقدار جدید وارد کنید' : 'xxxx xxxx xxxx xxxx'}
              />
              <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr' }, gap: 1.5 }}>
                <TextField label="زمان انتظار (ثانیه)" type="number" value={form.timeout_seconds} onChange={event => setForm(current => ({ ...current, timeout_seconds: Number(event.target.value) }))} inputProps={{ min: 1 }} />
                <TextField label="تلاش مجدد" type="number" value={form.retry_attempts} onChange={event => setForm(current => ({ ...current, retry_attempts: Number(event.target.value) }))} inputProps={{ min: 0, max: 5 }} />
              </Box>
              <FormControlLabel control={<Checkbox checked={form.allow_insecure_http} onChange={event => setForm(current => ({ ...current, allow_insecure_http: event.target.checked }))} />} label="اجازه HTTP فقط برای شبکهٔ خصوصی و محیط توسعه" />
              <FormControlLabel control={<Checkbox disabled={/^http:\/\//i.test(form.base_url)} checked={form.verify_tls} onChange={event => setForm(current => ({ ...current, verify_tls: event.target.checked }))} />} label="بررسی گواهی TLS در اتصال HTTPS" />
              <FormControlLabel control={<Checkbox checked={form.is_default} onChange={event => setForm(current => ({ ...current, is_default: event.target.checked }))} />} label="انتخاب به‌عنوان سایت پیش‌فرض" />
              <Stack direction={{ xs: 'column', sm: 'row' }} gap={1}>
                <Button type="button" variant="outlined" startIcon={<VerifiedRounded />} disabled={Boolean(busy) || !form.site_key} onClick={() => void test()}>{busy === 'test' ? 'در حال آزمون…' : 'ذخیره و آزمون اتصال'}</Button>
                <Button type="submit" variant="contained" startIcon={<SaveRounded />} disabled={Boolean(busy) || !form.site_key || !form.base_url}>{busy === 'save' ? 'در حال ذخیره…' : 'ذخیره تنظیمات'}</Button>
              </Stack>
            </Stack>
          </Box>
        </Stack>
      </Paper>

      <Stack direction={{ xs: 'column', sm: 'row' }} justifyContent="space-between" gap={1}>
        <Button startIcon={<FolderOpenRounded />} onClick={() => void window.eitaaDesktop.openLogs()}>بازکردن گزارش‌ها</Button>
        <Button variant="contained" disabled={Boolean(busy)} onClick={onClose}>بازگشت به گفتگوها</Button>
      </Stack>
    </Stack>
  </Box>
}
