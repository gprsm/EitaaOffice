import { useEffect, useMemo, useState } from 'react'
import {
  Avatar,
  Box,
  Button,
  Card,
  CardActions,
  CardContent,
  CardHeader,
  CardMedia,
  Checkbox,
  Chip,
  Collapse,
  IconButton,
  Skeleton,
  Stack,
  Typography,
} from '@mui/material'
import EditRounded from '@mui/icons-material/EditRounded'
import ExpandMoreRounded from '@mui/icons-material/ExpandMoreRounded'
import { albumCaption } from './lib/groupedMedia'
import type { MediaAlbum } from './lib/groupedMedia'
import { stableMessageKey } from './lib/scrollMath'
import type { DialogItem, IndexPrediction, MessageItem } from './lib/types'
import { loadDialogAvatar, peekDialogAvatar } from './lib/avatarLoader'

const MESSAGE_DATE_FORMATTER = new Intl.DateTimeFormat('fa-IR', {
  hour: '2-digit',
  minute: '2-digit',
})

type MessageContentCardProps = {
  siteKey: string
  timelineGroup?: 'start' | 'middle' | 'end' | 'none'
  dialog: DialogItem
  message: MessageItem
  album?: MediaAlbum
  media: Record<string, string | null>
  mediaDisplay: 'dynamic' | 'framed'
  selectedKeys: string[]
  selectionMode: boolean
  loadMedia: (message: MessageItem) => Promise<void>
  openFullMedia: (message: MessageItem) => Promise<void>
  toggle: () => void
  editIndex: () => void
  openUsage: () => void
}

function formatDate(value: string) {
  try { return MESSAGE_DATE_FORMATTER.format(new Date(value)) }
  catch { return value }
}

function authorLabel(dialog: DialogItem, message: MessageItem) {
  if (message.outgoing || message.sender_resolution === 'self') return 'شما'
  const displayName = message.sender_display_name?.trim()
  if (displayName) return displayName
  const username = message.sender_username?.trim()
  if (username) return `@${username.replace(/^@/, '')}`
  if (dialog.display_kind === 'personal') {
    return dialog.peer.title?.trim() || (dialog.peer.username ? `@${dialog.peer.username}` : 'مخاطب ایتا')
  }
  return 'نویسنده نامشخص'
}

function authorInitials(value: string) {
  const words = value.replace(/^@/, '').trim().split(/\s+/).filter(Boolean)
  if (!words.length) return 'ا'
  return words.slice(0, 2).map(word => word[0]).join('')
}

function MessageAuthorAvatar({ siteKey, peerKey, name }: { siteKey: string; peerKey?: string | null; name: string }) {
  const [src, setSrc] = useState<string | null | undefined>(() => peerKey ? peekDialogAvatar(siteKey, peerKey) : null)
  useEffect(() => {
    if (!peerKey) { setSrc(null); return }
    const cached = peekDialogAvatar(siteKey, peerKey)
    setSrc(cached)
    if (cached === undefined) {
      void loadDialogAvatar(siteKey, peerKey).then(setSrc)
    }
  }, [peerKey, siteKey])

  return <Avatar src={src || undefined} sx={{ width: 28, height: 28, ml: 1, bgcolor: 'primary.main', color: 'primary.contrastText', fontSize: '0.75rem', fontWeight: 800 }}>{authorInitials(name)}</Avatar>
}

function ImageWithSkeleton({ src, album, mediaDisplay, onClick, onDragStart }: any) {
  const [loaded, setLoaded] = useState(false)
  return <>
    {!loaded && <Skeleton variant="rounded" animation="wave" width="100%" height={album ? '100%' : 240} sx={{ position: 'absolute', inset: 0, borderRadius: 0, zIndex: 1 }} />}
    <CardMedia
      component="img"
      src={src}
      alt="پیش‌نمایش رسانه پیام"
      title="برای دریافت و نمایش تصویر اصلی کلیک کنید"
      loading="lazy"
      draggable
      onClick={onClick}
      onDragStart={onDragStart}
      onLoad={() => setLoaded(true)}
      sx={{ display: 'block', width: album || mediaDisplay === 'framed' ? '100%' : 'auto', maxWidth: '100%', height: album || mediaDisplay === 'framed' ? '100%' : 'auto', maxHeight: album || mediaDisplay === 'framed' ? '100%' : 'min(78vh, 1280px)', objectFit: album ? 'cover' : 'contain', cursor: 'zoom-in', opacity: loaded ? 1 : 0, transition: 'opacity 0.3s ease' }}
    />
  </>
}

export function MessageContentCard({
  siteKey,
  dialog,
  message,
  album,
  media,
  mediaDisplay,
  selectedKeys,
  selectionMode,
  loadMedia,
  openFullMedia,
  toggle,
  editIndex,
  openUsage,
  timelineGroup = 'none',
}: MessageContentCardProps) {
  const [expanded, setExpanded] = useState(false)
  const members = album?.messages || [message]
  const images = members.filter(item => item.media?.is_image)
  const files = members.filter(item => item.media && !item.media.is_image)
  const caption = album ? albumCaption(members) : message.text
  const memberKeys = members.map(item => stableMessageKey(dialog.peer_key, item.id))
  const selected = memberKeys.every(key => selectedKeys.includes(key))
  const anyUsed = members.some(item => item.usage.used)
  const allUsed = members.every(item => item.usage.used)
  const anyStale = members.some(item => item.usage.usage_state === 'stale')
  const collapsible = caption.length > 700 || caption.split('\n').length > 8
  const writer = authorLabel(dialog, message)
  const imageKeys = images.map(item => stableMessageKey(dialog.peer_key, item.id)).join('|')
  const indexPredictions = useMemo(() => {
    const indexedByLabel = new Map<number, IndexPrediction>()
    for (const item of members) {
      for (const prediction of item.index_predictions || []) {
        const current = indexedByLabel.get(prediction.label_id)
        if (!current || prediction.score > current.score) indexedByLabel.set(prediction.label_id, prediction)
      }
    }
    return [...indexedByLabel.values()].sort((a, b) => b.score - a.score).slice(0, 5)
  }, [members])

  useEffect(() => {
    for (const item of images) {
      if (media[stableMessageKey(dialog.peer_key, item.id)] === undefined) void loadMedia(item)
    }
  }, [dialog.peer_key, imageKeys, loadMedia, media]) // eslint-disable-line react-hooks/exhaustive-deps

  const handleCardClick = () => {
    if (selectionMode) toggle()
    else if (anyUsed) openUsage()
  }
  const firstId = members[0].id
  const lastId = members[members.length - 1].id
  const stateColor = anyStale ? 'warning.main' : allUsed ? 'error.main' : anyUsed ? 'warning.light' : 'divider'

  return <Card
    component="article"
    variant="outlined"
    onClick={handleCardClick}
    onContextMenu={event => { event.preventDefault(); toggle() }}
    sx={{
      position: 'relative',
      width: { xs: '100%', sm: 'min(620px, 88%)' },
      ml: message.outgoing ? 0 : 'auto',
      mr: message.outgoing ? 'auto' : 0,
      overflow: 'hidden',
      borderRadius: message.outgoing
        ? timelineGroup === 'start' ? '16px 16px 16px 5px' : timelineGroup === 'middle' ? '5px 16px 16px 5px' : timelineGroup === 'end' ? '5px 16px 16px 16px' : '16px 16px 16px 5px'
        : timelineGroup === 'start' ? '16px 16px 5px 16px' : timelineGroup === 'middle' ? '16px 5px 5px 16px' : timelineGroup === 'end' ? '16px 5px 16px 16px' : '16px 16px 5px 16px',
      bgcolor: theme => selected
        ? theme.palette.action.selected
        : anyStale
          ? theme.palette.warning.light
          : message.outgoing
            ? (theme.palette.mode === 'dark' ? theme.palette.action.selected : theme.palette.success.light)
            : theme.palette.background.paper,
      borderColor: stateColor,
      borderWidth: allUsed || anyStale ? 2 : 1,
      outline: selected ? '3px solid' : 0,
      outlineColor: 'primary.light',
      boxShadow: 1,
      cursor: selectionMode || anyUsed ? 'pointer' : 'default',
      transition: theme => theme.transitions.create(['box-shadow', 'background-color']),
      '&:hover': { boxShadow: 3 },
      '& .MuiCardHeader-action': { alignSelf: 'center', m: 0 },
    }}
  >
    {(timelineGroup === 'none' || timelineGroup === 'start') && dialog.display_kind !== 'channel' && <CardHeader
      action={message.sender_is_eitaa_contact && <Chip size="small" color="primary" variant="outlined" label="مخاطب" />}
      title={<Typography variant="subtitle2" component="h3" fontWeight={850}>{writer}</Typography>}
      subheader={<Stack direction="row" spacing={0.75} alignItems="center" flexWrap="wrap">
        {message.sender_username && writer !== `@${message.sender_username.replace(/^@/, '')}` && <Typography variant="caption" color="text.secondary" dir="ltr">@${message.sender_username.replace(/^@/, '')}</Typography>}
      </Stack>}
      sx={{ px: { xs: 1.25, sm: 1.75 }, py: 1.1 }}
    />}

    {album && <Box sx={{ px: 1.25, pb: 0.75 }}><Chip size="small" color={album.kind === 'inferred' ? 'warning' : 'info'} variant="outlined" label={album.kind === 'inferred' ? `گالری پیشنهادی · ${members.length.toLocaleString('fa-IR')} تصویر` : `گالری · ${members.length.toLocaleString('fa-IR')} رسانه`} /></Box>}

    {images.length > 0 && <Box sx={{ width: '100%', overflow: 'hidden', bgcolor: 'action.hover', display: album ? 'grid' : 'flex', justifyContent: 'center', alignItems: 'flex-start', gridTemplateColumns: album ? (images.length > 4 ? 'repeat(3, minmax(0, 1fr))' : images.length === 1 ? '1fr' : 'repeat(2, minmax(0, 1fr))') : undefined, gridTemplateRows: album ? (images.length === 1 ? '1fr' : images.length > 4 ? `repeat(${Math.ceil(images.length / 3)}, minmax(0, 1fr))` : 'repeat(2, minmax(0, 1fr))') : undefined, gap: album ? 0.25 : 0, aspectRatio: album || mediaDisplay === 'framed' ? '4 / 3' : 'auto' }}>
      {images.map((item, index) => {
        const key = stableMessageKey(dialog.peer_key, item.id)
        const selectedMediaUrl = media[key]
        const spanFirstOfThree = Boolean(album && images.length === 3 && index === 0)
        return <Box key={key} sx={{ position: 'relative', minWidth: 0, minHeight: album ? 0 : 120, overflow: 'hidden', bgcolor: 'action.hover', gridRow: spanFirstOfThree ? '1 / -1' : images.length === 2 ? '1 / -1' : undefined, gridColumn: album && images.length === 1 ? '1 / -1' : undefined, display: 'grid', placeItems: 'center' }}>
          {selectedMediaUrl
            ? <ImageWithSkeleton
                src={selectedMediaUrl}
                album={album}
                mediaDisplay={mediaDisplay}
                onClick={(event: any) => { event.stopPropagation(); void openFullMedia(item) }}
                onDragStart={(event: any) => { event.dataTransfer.setData('application/x-eitaa-source', key); event.dataTransfer.effectAllowed = 'copy' }}
              />
            : selectedMediaUrl === null
              ? <Skeleton variant="rounded" animation="wave" width="100%" height={album ? '100%' : 240} sx={{ borderRadius: 0 }} />
              : <Typography variant="caption" color="text.secondary" sx={{ p: 3 }}>پیش‌نمایش تصویر</Typography>}
        </Box>
      })}
    </Box>}

    <CardContent sx={{ px: { xs: 1.25, sm: 1.75 }, py: 1, '&:last-child': { pb: 1 } }}>
      {files.length > 0 && <Stack direction="row" flexWrap="wrap" gap={0.5} sx={{ mb: caption ? 1 : 0 }}>{files.map(item => <Chip size="small" variant="outlined" key={stableMessageKey(dialog.peer_key, item.id)} label={`📎 ${item.media?.file_name || item.media?.type}`} />)}</Stack>}
      {caption && !collapsible && <Typography component="div" variant="body2" sx={{ whiteSpace: 'pre-wrap', lineHeight: 1.9, overflowWrap: 'anywhere' }}>{caption}</Typography>}
      {caption && collapsible && !expanded && <Typography component="div" variant="body2" sx={{ whiteSpace: 'pre-wrap', lineHeight: 1.9, overflowWrap: 'anywhere' }}>{caption.slice(0, 420).trimEnd()}…</Typography>}
      <Collapse in={expanded} timeout="auto" unmountOnExit>
        {collapsible && <Typography component="div" variant="body2" sx={{ whiteSpace: 'pre-wrap', lineHeight: 1.9, overflowWrap: 'anywhere' }}>{caption}</Typography>}
      </Collapse>
      {indexPredictions.length > 0 && <Stack direction="row" flexWrap="wrap" gap={0.5} mt={1} aria-label="پیشنهادهای ایندکس محلی" alignItems="center">
        {indexPredictions.map(prediction => <Chip size="small" color={prediction.manual ? 'success' : 'secondary'} variant="outlined" key={prediction.label_id} title={`${Math.round(prediction.score * 100)}٪${prediction.evidence.length ? ` — نشانه‌ها: ${prediction.evidence.join('، ')}` : ''}`} label={`${prediction.label_name} · ${prediction.manual ? 'دستی' : `${Math.round(prediction.score * 100)}٪`}`} />)}
        <IconButton aria-label="اصلاح ایندکس پیام" size="small" sx={{ ml: 0.5 }} onClick={event => { event.stopPropagation(); editIndex() }}><EditRounded fontSize="small" /></IconButton>
      </Stack>}
    </CardContent>

    <CardActions disableSpacing sx={{ minHeight: 44, px: 1, pt: 0, gap: 0.25 }}>
      <Checkbox
        inputProps={{ 'aria-label': album ? 'انتخاب گالری' : 'انتخاب پیام' }}
        checked={selected}
        onClick={event => { event.stopPropagation(); toggle() }}
        size="small"
      />
      {dialog.display_kind === 'personal' && <Typography variant="caption" color="text.secondary" sx={{ direction: 'ltr' }}>{album ? `#${firstId}–#${lastId}` : `#${message.id}`}</Typography>}
      <Box sx={{ flex: 1 }} />
      {anyUsed && <Button size="small" color={anyStale ? 'warning' : 'error'} variant="outlined" onClick={event => { event.stopPropagation(); openUsage() }} sx={{ minHeight: 28, py: 0 }}>{anyStale ? 'تغییرکرده' : allUsed ? 'وردپرس' : 'بخشی در وردپرس'}</Button>}
      {collapsible && <IconButton
        aria-label={expanded ? 'بستن ادامه پیام' : 'نمایش ادامه پیام'}
        aria-expanded={expanded}
        onClick={event => { event.stopPropagation(); setExpanded(value => !value) }}
        sx={{ transform: expanded ? 'rotate(180deg)' : 'rotate(0deg)', transition: theme => theme.transitions.create('transform', { duration: theme.transitions.duration.shortest }) }}
      ><ExpandMoreRounded /></IconButton>}
      {dialog.display_kind !== 'channel' && (timelineGroup === 'none' || timelineGroup === 'end') && <MessageAuthorAvatar siteKey={siteKey} peerKey={message.sender_key} name={writer} />}
    </CardActions>
  </Card>
}
