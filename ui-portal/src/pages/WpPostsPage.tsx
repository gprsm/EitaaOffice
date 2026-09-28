import { useEffect, useState } from 'react'
import {
  Alert, Box, Button, Card, CardContent, Chip, LinearProgress, Table, TableBody,
  TableCell, TableContainer, TableHead, TablePagination, TableRow, Typography, Paper,
} from '@mui/material'
import OpenInNewIcon from '@mui/icons-material/OpenInNew'
import PublicIcon from '@mui/icons-material/Public'
import { api, type WpPost } from '../api'
import { faNum } from '../periods'

/** کارتابل بسته‌های خبری وردپرس (F-097) */
export default function WpPostsPage({ notify }: { notify: (text: string, severity?: 'success' | 'error' | 'info') => void }) {
  const [rows, setRows] = useState<WpPost[]>([])
  const [page, setPage] = useState(0)
  const [pageSize, setPageSize] = useState(20)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    let alive = true
    setLoading(true)
    api.wpPosts(pageSize, page * pageSize)
      .then((res) => alive && setRows(res.rows))
      .catch((err) => alive && setError(err instanceof Error ? err.message : 'خطا در دریافت نوشته‌ها'))
      .finally(() => alive && setLoading(false))
    return () => { alive = false }
  }, [page, pageSize])

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
              <TableCell align="center">عملیات</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {rows.map((p) => (
              <TableRow key={p.ID} hover>
                <TableCell><code>#{faNum(p.ID)}</code></TableCell>
                <TableCell sx={{ maxWidth: 360 }}>
                  <strong>{p.post_title}</strong>
                  <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
                    {faNum(p.post_date.slice(0, 10))}
                  </Typography>
                </TableCell>
                <TableCell sx={{ maxWidth: 200 }}>
                  {(p.tags || []).slice(0, 4).map((t) => (
                    <Chip key={t} size="small" label={t} sx={{ mr: 0.5, mb: 0.5 }} />
                  ))}
                </TableCell>
                <TableCell>
                  <Chip size="small" color={p.post_status === 'publish' ? 'success' : 'warning'}
                    label={p.post_status === 'publish' ? 'منتشر شده' : 'در انتظار بررسی'} />
                </TableCell>
                <TableCell align="center" sx={{ whiteSpace: 'nowrap' }}>
                  {p.post_status !== 'publish' && (
                    <Button size="small" variant="contained" startIcon={<PublicIcon />}
                      onClick={() => publish(p)}>
                      انتشار
                    </Button>
                  )}
                  <Button size="small" startIcon={<OpenInNewIcon />}
                    href={`http://localhost/wp-admin/post.php?post=${p.ID}&action=edit`} target="_blank">
                    وردپرس
                  </Button>
                </TableCell>
              </TableRow>
            ))}
            {rows.length === 0 && !loading && (
              <TableRow><TableCell colSpan={5} align="center" sx={{ py: 4, color: 'text.secondary' }}>
                نوشته‌ای یافت نشد.
              </TableCell></TableRow>
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
    </Box>
  )
}

