import { useState } from 'react'
import { Box, Button, Card, CircularProgress, Collapse, IconButton, Stack, Typography } from '@mui/material'
import DownloadRounded from '@mui/icons-material/DownloadRounded'
import ExpandMoreRounded from '@mui/icons-material/ExpandMoreRounded'

const MESSAGE_TIME_FORMATTER = new Intl.DateTimeFormat('fa-IR', {
  hour: '2-digit',
  minute: '2-digit',
})

export function BaleMessageCard({
  text,
  sentAtUnixMs,
  outgoing,
  hasMedia,
  canDownloadMedia,
  downloading,
  onDownload,
}: {
  text?: string
  sentAtUnixMs: number
  outgoing: boolean
  hasMedia: boolean
  canDownloadMedia: boolean
  downloading: boolean
  onDownload: () => void
}) {
  const [expanded, setExpanded] = useState(false)
  const value = (text || '').trim()
  let time = ''
  try { time = MESSAGE_TIME_FORMATTER.format(new Date(sentAtUnixMs)) } catch { time = '' }
  const collapsible = value.length > 700 || value.split('\n').length > 8
  const attachmentOnly = !value && hasMedia
  return <Card
    component="article"
    variant="outlined"
    sx={{
      position: 'relative',
      width: { xs: '100%', sm: 'min(620px, 88%)' },
      ml: outgoing ? 0 : 'auto',
      mr: outgoing ? 'auto' : 0,
      overflow: 'hidden',
      borderRadius: outgoing ? '16px 16px 16px 5px' : '16px 16px 5px 16px',
      bgcolor: theme => outgoing
        ? (theme.palette.mode === 'dark' ? theme.palette.action.selected : theme.palette.success.light)
        : theme.palette.background.paper,
      boxShadow: 1,
      transition: theme => theme.transitions.create(['box-shadow', 'background-color']),
      '&:hover': { boxShadow: 3 },
    }}
  >
    <Box sx={{ px: { xs: 1.25, sm: 1.75 }, pt: attachmentOnly ? 1.25 : 1 }}>
      {value && <>
        {collapsible && !expanded && <Typography component="div" variant="body2" sx={{ whiteSpace: 'pre-wrap', lineHeight: 1.9, overflowWrap: 'anywhere' }}>{value.slice(0, 420).trimEnd()}…</Typography>}
        <Collapse in={!collapsible || expanded} timeout="auto" unmountOnExit={collapsible}>
          <Typography component="div" variant="body2" sx={{ whiteSpace: 'pre-wrap', lineHeight: 1.9, overflowWrap: 'anywhere' }}>{value}</Typography>
        </Collapse>
      </>}
      {hasMedia && <Stack direction="row" alignItems="center" sx={{ pt: value ? 0.5 : 0, pb: 0.5 }}>
        <Button
          size="small"
          variant="outlined"
          startIcon={downloading ? <CircularProgress size={16} color="inherit" /> : <DownloadRounded />}
          disabled={downloading || !canDownloadMedia}
          onClick={onDownload}
        >{downloading ? 'در حال دریافت پیوست…' : 'دریافت پیوست'}</Button>
      </Stack>}
    </Box>
    <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ minHeight: 36, px: { xs: 1.25, sm: 1.75 }, py: 0.5 }}>
      <Typography variant="caption" color="text.secondary">{time}</Typography>
      {collapsible && <IconButton
        aria-label={expanded ? 'بستن ادامه پیام' : 'نمایش ادامه پیام'}
        aria-expanded={expanded}
        onClick={() => setExpanded(value => !value)}
        sx={{ transform: expanded ? 'rotate(180deg)' : 'rotate(0deg)', transition: theme => theme.transitions.create('transform', { duration: theme.transitions.duration.shortest }) }}
      ><ExpandMoreRounded /></IconButton>}
    </Stack>
  </Card>
}
