import { useEffect, useState } from 'react'
import {
  Alert, Box, Button, Chip, CircularProgress, Dialog, DialogActions,
  DialogContent, DialogTitle, FormControl, IconButton, InputLabel,
  LinearProgress, MenuItem, Paper, Select, Stack, Table, TableBody,
  TableCell, TableContainer, TableHead, TablePagination, TableRow,
  TextField, Tooltip, Typography,
} from '@mui/material'
import EditIcon from '@mui/icons-material/Edit'
import PublicIcon from '@mui/icons-material/Public'
import CloseIcon from '@mui/icons-material/Close'
import SyncAltIcon from '@mui/icons-material/SyncAlt'
import OpenInNewIcon from '@mui/icons-material/OpenInNew'
import { api, type WpPost } from '../api'
import { faDate, faNum } from '../periods'

/** کارتابل بسته‌های خبری وردپرس با قابلیت ویرایش بومی و همگام‌سازی دوطرفه (F-097) */
export default function WpPostsPage({ notify }: { notify: (text: string, severity?: 'success' | 'error' | 'info') => void }) {
  const [rows, setRows] = useState<WpPost[]>([])
  const [page, setPage] = useState(0)
  const [pageSize, setPageSize] = useState(20)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  // وضعیت دیالوگ ویرایش بومی
  const [editPost, setEditPost] = useState<WpPost | null>(null)
  const [editTitle, setEditTitle] = useState('')
  const [editContent, setEditContent] = useState('')
  const [editStatus, setEditStatus] = useState<'pending' | 'publish'>('pending')
  const [saving, setSaving] = useState(false)

  const loadPosts = (p = page, ps = pageSize) => {
    setLoading(true)
    api.wpPosts(ps, p * ps)
      .then((res) => setRows(res.rows))
      .catch((err) => setError(err instanceof Error ? err.message : 'خطا در دریافت نوشته‌ها'))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    loadPosts(page, pageSize)
  }, [page, pageSize])

  const handleOpenEdit = (post: WpPost) => {
    setEditPost(post)
    setEditTitle(post.post_title)
    setEditContent(post.post_content)
    setEditStatus(post.post_status === 'publish' ? 'publish' : 'pending')
  }

  const handleCloseEdit = () => {
    if (saving) return
    setEditPost(null)
  }

  const handleSaveEdit = async () => {
    if (!editPost) return
    if (!editTitle.trim()) {
      notify('عنوان بسته خبری نمی‌تواند خالی باشد.', 'error')
      return
    }
    if (!editContent.trim()) {
      notify('متن محتوای بسته خبری نمی‌تواند خالی باشد.', 'error')
      return
    }

    setSaving(true)
    try {
      await api.updateWpContent(editPost.ID, editContent, editTitle, editStatus)
      notify(`بسته خبری #${faNum(editPost.ID)} با موفقیت در وردپرس ذخیره و رویدادهای متناظر همگام شدند.`, 'success')
      setRows((prev) =>
        prev.map((p) =>
          p.ID === editPost.ID
            ? { ...p, post_title: editTitle, post_content: editContent, post_status: editStatus }
            : p
        )
      )
      setEditPost(null)
    } catch (err) {
      notify(err instanceof Error ? err.message : 'خطا در ذخیره‌سازی بسته خبری', 'error')
    } finally {
      setSaving(false)
    }
  }

  const publish = async (post: WpPost) => {
    if (!window.confirm('این نوشته در سایت عمومی وردپرس منتشر شود؟')) return
    try {
      await api.updateWpStatus(post.ID, 'publish')
      notify(`نوشته #${faNum(post.ID)} منتشر شد`, 'success')
      setRows((r) => r.map((p) => (p.ID === post.ID ? { ...p, post_status: 'publish' } : p)))
    } catch (err) {
      notify(err instanceof Error ? err.message : 'خطا در انتشار', 'error')
    }
  }

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      {error && <Alert severity="error">{error}</Alert>}
      {loading && <LinearProgress />}

      <TableContainer component={Paper}>
        <Table size="small" sx={{ minWidth: 760 }}>
          <TableHead>
            <TableRow>
              <TableCell>شناسه</TableCell>
              <TableCell>عنوان بسته خبری</TableCell>
              <TableCell>حوزه‌ها (برچسب‌ها)</TableCell>
              <TableCell>وضعیت</TableCell>
              <TableCell align="center">عملیات سیستمی</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {rows.map((p) => (
              <TableRow key={p.ID} hover>
                <TableCell><code>#{faNum(p.ID)}</code></TableCell>
                <TableCell sx={{ maxWidth: 360 }}>
                  <a
                    href={`http://localhost/?p=${p.ID}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    style={{ textDecoration: 'none', color: '#0f172a', fontWeight: 'bold', display: 'inline-block' }}
                    onMouseEnter={(e) => (e.currentTarget.style.color = '#1976d2')}
                    onMouseLeave={(e) => (e.currentTarget.style.color = '#0f172a')}
                    title="مشاهده صفحه خبر در وردپرس"
                  >
                    {p.post_title}
                  </a>
                  <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.5 }}>
                    ثبت: {faDate(p.post_date)}
                  </Typography>
                </TableCell>
                <TableCell sx={{ maxWidth: 200 }}>
                  {(p.tags || []).slice(0, 4).map((t) => (
                    <Chip key={t} size="small" label={t} sx={{ mr: 0.5, mb: 0.5 }} />
                  ))}
                </TableCell>
                <TableCell>
                  <Chip
                    size="small"
                    color={p.post_status === 'publish' ? 'success' : 'warning'}
                    label={p.post_status === 'publish' ? 'منتشر شده' : 'در انتظار بررسی'}
                  />
                </TableCell>
                <TableCell align="center" sx={{ whiteSpace: 'nowrap' }}>
                  <Stack direction="row" spacing={1} justifyContent="center">
                    <Button
                      size="small"
                      variant="outlined"
                      color="primary"
                      startIcon={<EditIcon />}
                      onClick={() => handleOpenEdit(p)}
                    >
                      ویرایش محتوا
                    </Button>

                    {p.post_status !== 'publish' && (
                      <Button
                        size="small"
                        variant="contained"
                        color="success"
                        startIcon={<PublicIcon />}
                        onClick={() => publish(p)}
                      >
                        انتشار
                      </Button>
                    )}

                    <Tooltip title="مشاهده صفحه خبر در وردپرس">
                      <IconButton
                        size="small"
                        color="primary"
                        href={`http://localhost/?p=${p.ID}`}
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        <OpenInNewIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                  </Stack>
                </TableCell>
              </TableRow>
            ))}
            {rows.length === 0 && !loading && (
              <TableRow>
                <TableCell colSpan={5} align="center" sx={{ py: 4, color: 'text.secondary' }}>
                  نوشته‌ای یافت نشد.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </TableContainer>

      <TablePagination
        component="div"
        count={page * pageSize + rows.length + (rows.length === pageSize ? pageSize : 0)}
        page={page}
        onPageChange={(_, p) => setPage(p)}
        rowsPerPage={pageSize}
        onRowsPerPageChange={(e) => { setPageSize(Number(e.target.value)); setPage(0) }}
        rowsPerPageOptions={[20, 40]}
        labelRowsPerPage="سطر در صفحه:"
        labelDisplayedRows={({ from, to }) => `${faNum(from)}–${faNum(to)}`}
      />

      {/* مودال ویرایش محتوای نوشته وردپرس از درگاه واحد سامانه */}
      <Dialog
        open={Boolean(editPost)}
        onClose={handleCloseEdit}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle sx={{ m: 0, p: 2, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <Stack direction="row" alignItems="center" spacing={1}>
            <SyncAltIcon color="primary" />
            <Typography variant="h6" component="span" fontWeight="bold">
              ویرایش بسته خبری #{editPost ? faNum(editPost.ID) : ''} (همگام‌سازی دوطرفه)
            </Typography>
          </Stack>
          <IconButton onClick={handleCloseEdit} disabled={saving} size="small">
            <CloseIcon />
          </IconButton>
        </DialogTitle>

        <DialogContent dividers sx={{ display: 'flex', flexDirection: 'column', gap: 2.5, pt: 2 }}>
          <Alert severity="info" variant="outlined" sx={{ fontSize: '0.85rem' }}>
            تغییرات این فرم از طریق <strong>اتصال سیستمی</strong> مستقیماً در دیتابیس وردپرس اعمال می‌شود و
            رویدادهای متناظر در <strong>سامانه گزارش‌گیری</strong> نیز همگام‌سازی خواهند شد. نیازی به ورود به پیشخوان وردپرس نیست.
          </Alert>

          <TextField
            label="عنوان بسته خبری"
            fullWidth
            required
            value={editTitle}
            onChange={(e) => setEditTitle(e.target.value)}
            disabled={saving}
          />

          <FormControl fullWidth size="small">
            <InputLabel id="post-status-select-label">وضعیت انتشار</InputLabel>
            <Select
              labelId="post-status-select-label"
              value={editStatus}
              label="وضعیت انتشار"
              onChange={(e) => setEditStatus(e.target.value as 'pending' | 'publish')}
              disabled={saving}
            >
              <MenuItem value="pending">در انتظار بررسی / پیش‌نویس (Pending)</MenuItem>
              <MenuItem value="publish">منتشر شده در سایت عمومی (Published)</MenuItem>
            </Select>
          </FormControl>

          <TextField
            label="متن کامل و جدول محتوای خبر"
            fullWidth
            required
            multiline
            rows={12}
            value={editContent}
            onChange={(e) => setEditContent(e.target.value)}
            disabled={saving}
            placeholder="متن کامل خبر، اطلاعات حوزه‌ها و رویدادهای مربوطه..."
            inputProps={{
              style: { fontFamily: 'inherit', fontSize: '0.9rem', lineHeight: '1.7' },
              dir: 'rtl',
            }}
          />
        </DialogContent>

        <DialogActions sx={{ px: 3, py: 2 }}>
          <Button onClick={handleCloseEdit} disabled={saving} color="inherit">
            انصراف
          </Button>
          <Button
            variant="contained"
            color="primary"
            onClick={handleSaveEdit}
            disabled={saving}
            startIcon={saving ? <CircularProgress size={18} color="inherit" /> : <SyncAltIcon />}
          >
            {saving ? 'در حال همگام‌سازی...' : 'ذخیره و همگام‌سازی با وردپرس'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  )
}
