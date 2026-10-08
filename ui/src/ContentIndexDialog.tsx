import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  FormControl,
  FormControlLabel,
  Grid,
  IconButton,
  InputLabel,
  LinearProgress,
  MenuItem,
  Paper,
  Select,
  Stack,
  Switch,
  Tab,
  Tabs,
  TextField,
  Tooltip,
  Typography,
  useMediaQuery,
  useTheme,
} from '@mui/material'
import type { SenderFilterOption } from './lib/types'
import CloseRounded from '@mui/icons-material/CloseRounded'
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined'
import AddRounded from '@mui/icons-material/AddRounded'
import DeleteOutlineRounded from '@mui/icons-material/DeleteOutlineRounded'
import PlayArrowRounded from '@mui/icons-material/PlayArrowRounded'
import StopCircleOutlined from '@mui/icons-material/StopCircleOutlined'
import RestartAltRounded from '@mui/icons-material/RestartAltRounded'
import TuneRounded from '@mui/icons-material/TuneRounded'


export type MaterialIndexDefinition = {
  id: number
  name: string
  aliases: string[]
  kind: 'wordpress-category' | 'wordpress-tag' | 'custom'
  wordpressCategoryId?: number | null
}

type NamedId = { id: number; name: string }

type Props = {
  open: boolean
  close: () => void
  contentIndexActive: boolean
  contentIndexState?: string
  contentIndexProcessed: number
  contentIndexTarget: number
  contentIndexPercent: number
  coldStart: boolean
  resultCount: number
  canStart: boolean
  start: () => void
  cancel: () => void
  definitions: MaterialIndexDefinition[]
  categories: NamedId[]
  customIndexName: string
  setCustomIndexName: (value: string) => void
  customIndexCategoryId: number | null
  customIndexKeywords: string
  setCustomIndexKeywords: (value: string) => void
  setCustomIndexCategoryId: (value: number | null) => void
  addCustomIndex: () => void
  selectedDefinitionId: number | null
  selectDefinition: (id: number) => void
  indexNameDraft: string
  setIndexNameDraft: (value: string) => void
  indexKeywordDraft: string
  setIndexKeywordDraft: (value: string) => void
  saveDefinition: () => void
  deleteDefinition: (id: number) => void
}

const kindLabel = (kind: MaterialIndexDefinition['kind']) => kind === 'wordpress-category'
  ? 'دسته سایت'
  : kind === 'wordpress-tag'
    ? 'برچسب سایت'
    : 'ایندکس محلی'



export function ContentIndexDialog(props: Props) {
  const theme = useTheme()
  const fullScreen = useMediaQuery(theme.breakpoints.down('sm'))
  const selected = props.definitions.find(item => item.id === props.selectedDefinitionId)

  return <Dialog
    open={props.open}
    onClose={props.close}
    fullScreen={fullScreen}
    maxWidth="md"
    aria-labelledby="content-index-title"
  >
    <DialogTitle id="content-index-title" sx={{ pb: 1 }}>
      <Stack direction="row" alignItems="center" justifyContent="space-between" gap={2}>
        <Box minWidth={0}>
          <Typography variant="h6" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>ایندکس‌گذاری محتوا<Tooltip title="ایندکس‌ها بر اساس الگوهای استنتاجی و یادگیری عمیق سبک در دیتابیس محلی ذخیره و تحلیل می‌شوند. سال و ماه شمسی نیز خودکار ثبت می‌شوند."><IconButton size="small"><InfoOutlinedIcon fontSize="small" /></IconButton></Tooltip></Typography>
          <Typography variant="body2" color="text.secondary">پردازش متن کاملاً مستقل، محلی و مبتنی بر یادگیری و استنتاج است.</Typography>
        </Box>
        <IconButton aria-label="بستن" onClick={props.close}><CloseRounded /></IconButton>
      </Stack>
    </DialogTitle>
    <DialogContent dividers sx={{ bgcolor: 'background.default' }}>
      <Stack spacing={2.25}>
        <Paper variant="outlined" sx={{ p: { xs: 1.5, sm: 2 } }}>
          <Stack spacing={1.5}>
            <Stack direction={{ xs: 'column', sm: 'row' }} justifyContent="space-between" alignItems={{ xs: 'stretch', sm: 'center' }} gap={1.5}>
              <Box>
                <Typography fontWeight={900}>پایش محتوای گفت‌وگوی جاری</Typography>
                <Typography variant="body2" color="text.secondary">برای حفظ روانی برنامه، پردازش در وظیفه پس‌زمینه انجام می‌شود و نتیجه‌ها صفحه‌بندی می‌شوند.</Typography>
              </Box>
              {props.contentIndexActive
                ? <Button color="warning" variant="outlined" startIcon={<StopCircleOutlined />} onClick={props.cancel} disabled={props.contentIndexState === 'cancelling'}>{props.contentIndexState === 'cancelling' ? 'در حال لغو…' : 'لغو ایمن'}</Button>
                : <Button variant="contained" startIcon={<PlayArrowRounded />} onClick={props.start} disabled={!props.canStart}>شروع ایندکس</Button>}
            </Stack>
            {props.contentIndexState && <>
              <LinearProgress variant="determinate" value={props.contentIndexPercent} />
              <Stack direction="row" justifyContent="space-between" gap={1}>
                <Typography variant="caption">{props.contentIndexProcessed.toLocaleString('fa-IR')} از {props.contentIndexTarget.toLocaleString('fa-IR')}</Typography>
                <Typography variant="caption">{Math.round(props.contentIndexPercent).toLocaleString('fa-IR')}٪</Typography>
              </Stack>
            </>}
            <Stack direction="row" gap={1} flexWrap="wrap">
              <Chip label={`${props.resultCount.toLocaleString('fa-IR')} پیام دارای نتیجه`} color="primary" variant="outlined" />
              {props.coldStart && <Chip label="شروع سرد؛ نیازمند بازخورد بیشتر" color="warning" variant="outlined" />}
            </Stack>
          </Stack>
        </Paper>

        <Grid container spacing={2}>
          <Grid size={{ xs: 12, md: 5 }}>
            <Paper variant="outlined" sx={{ p: { xs: 1.5, sm: 2 }, height: '100%' }}>
              <Stack spacing={1.5}>
                <Box>
                  <Typography fontWeight={900}>ایندکس محلی جدید</Typography>
                  <Typography variant="body2" color="text.secondary">برای هر عنوان یا سرفصل موضوعی، یک ایندکس مستقل همراه با کلمات کلیدی و نشانه‌های استنتاج بسازید.</Typography>
                </Box>
                <TextField label="نام ایندکس" value={props.customIndexName} onChange={event => props.setCustomIndexName(event.target.value)} placeholder="مثلاً غبارروبی مزار شهدا" />
                <TextField label="واژه‌ها و عبارت‌های راهنمای اختیاری" value={props.customIndexKeywords} onChange={event => props.setCustomIndexKeywords(event.target.value)} multiline minRows={2} placeholder="عطرافشانی، گلزار شهدا، ادای احترام" helperText="هر واژه یا عبارت را با «،» جدا کنید." />
                <FormControl>
                  <InputLabel>اتصال اختیاری به وردپرس</InputLabel>
                  <Select<string> label="اتصال اختیاری به وردپرس" value={props.customIndexCategoryId == null ? '' : String(props.customIndexCategoryId)} onChange={event => props.setCustomIndexCategoryId(event.target.value ? Number(event.target.value) : null)}>
                    <MenuItem value="">بدون نگاشت</MenuItem>
                    {props.categories.map(item => <MenuItem key={item.id} value={String(item.id)}>{item.name}</MenuItem>)}
                  </Select>
                </FormControl>
                <Button variant="outlined" startIcon={<AddRounded />} onClick={props.addCustomIndex} disabled={!props.customIndexName.trim()}>افزودن ایندکس</Button>
                <Divider />
                <Box>
                  <Typography fontWeight={900} gutterBottom>ایندکس‌های موضوعی من</Typography>
                  <Stack spacing={1} sx={{ maxHeight: 260, overflow: 'auto' }}>
                    {props.definitions.filter(item => item.kind === 'custom').length ? props.definitions.filter(item => item.kind === 'custom').map(item => <Paper key={item.id} variant="outlined" sx={{ p: 1.25 }}>
                      <Stack direction={{ xs: 'column', sm: 'row' }} justifyContent="space-between" gap={1}>
                        <Box minWidth={0}><Typography fontWeight={800}>{item.name}</Typography><Typography variant="caption" color="text.secondary" sx={{ overflowWrap: 'anywhere' }}>{item.aliases.length ? item.aliases.join('، ') : 'بدون واژه راهنما'}</Typography></Box>
                        <Stack direction="row" gap={.75}><Button size="small" variant="outlined" onClick={() => props.selectDefinition(item.id)}>ویرایش</Button><Button size="small" color="error" onClick={() => props.deleteDefinition(item.id)}>حذف</Button></Stack>
                      </Stack>
                    </Paper>) : <Alert severity="info">هنوز ایندکس سفارشی ساخته نشده است.</Alert>}
                  </Stack>
                </Box>
              </Stack>
            </Paper>
          </Grid>

          <Grid size={{ xs: 12, md: 7 }}>
            <Paper variant="outlined" sx={{ p: { xs: 1.5, sm: 2 }, height: '100%' }}>
              <Stack spacing={1.5}>
                <Box>
                  <Typography fontWeight={900}>ویرایش نام و واژه‌های راهنما</Typography>
                  <Typography variant="body2" color="text.secondary">واژه‌ها را با «،» جدا کنید. این واژه‌ها راهنمای مدل سبک محلی هستند و نتیجه نهایی همچنان قابل اصلاح است.</Typography>
                </Box>
                <FormControl disabled={!props.definitions.length}>
                  <InputLabel>ایندکس قابل تنظیم</InputLabel>
                  <Select label="ایندکس قابل تنظیم" value={props.selectedDefinitionId ?? ''} onChange={event => props.selectDefinition(Number(event.target.value))}>
                    {props.definitions.map(item => <MenuItem key={item.id} value={item.id}>{kindLabel(item.kind)} — {item.name}</MenuItem>)}
                  </Select>
                </FormControl>
                <TextField label="نام نمایشی محلی" value={props.indexNameDraft} onChange={event => props.setIndexNameDraft(event.target.value)} disabled={!selected} />
                <TextField label="واژه‌ها و عبارت‌های راهنما" value={props.indexKeywordDraft} onChange={event => props.setIndexKeywordDraft(event.target.value)} multiline minRows={2} disabled={!selected} placeholder="عطرافشانی، گلزار شهدا، ادای احترام" />
                <Divider />
                <Stack direction={{ xs: 'column', sm: 'row' }} gap={1} justifyContent="space-between">
                  <Button variant="contained" onClick={props.saveDefinition} disabled={!selected}>ذخیره تنظیمات</Button>
                  {selected?.kind === 'custom' && <Button color="error" variant="outlined" startIcon={<DeleteOutlineRounded />} onClick={() => props.deleteDefinition(selected.id)}>حذف ایندکس سفارشی</Button>}
                </Stack>
              </Stack>
            </Paper>
          </Grid>
        </Grid>
      </Stack>
    </DialogContent>
    <DialogActions sx={{ px: { xs: 1.25, sm: 2.25 }, py: 1.5 }}>
      <Button onClick={props.close}>بستن</Button>
    </DialogActions>
  </Dialog>
}
