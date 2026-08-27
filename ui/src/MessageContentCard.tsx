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
import type { MessageGroup } from './lib/groupedMedia'
import { stableMessageKey } from './lib/scrollMath'
import type { DialogItem, IndexPrediction, MessageItem } from './lib/types'
import { loadDialogAvatar, peekDialogAvatar } from './lib/avatarLoader'

const MESSAGE_DATE_FORMATTER = new Intl.DateTimeFormat('fa-IR', {
  hour: '2-digit',
  minute: '2-digit',
})

type MessageContentCardProps = {
  siteKey: string
  dialog: DialogItem
  message: MessageItem
  group?: MessageGroup
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

type MessageContentBlock =
  | { kind: 'images'; items: MessageItem[]; key: string }
  | { kind: 'file'; item: MessageItem; key: string }
  | { kind: 'text'; item: MessageItem; text: string; key: string }

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
    let active = true
    if (!peerKey) { setSrc(null); return () => { active = false } }
    const cached = peekDialogAvatar(siteKey, peerKey)
    setSrc(cached)
    if (cached === undefined) {
      void loadDialogAvatar(siteKey, peerKey)
        .then(value => { if (active) setSrc(value) })
        .catch(() => { if (active) setSrc(null) })
    }
    return () => { active = false }
  }, [peerKey, siteKey])

  return <Avatar src={src || undefined} slotProps={{ img: { onError: () => setSrc(null) } }} sx={{ width: 28, height: 28, ml: 1, bgcolor: 'primary.main', color: 'primary.contrastText', fontSize: '0.75rem', fontWeight: 800 }}>{authorInitials(name)}</Avatar>
}

function buildContentBlocks(members: MessageItem[]): MessageContentBlock[] {
  const blocks: MessageContentBlock[] = []
  let index = 0
  while (index < members.length) {
    const item = members[index]
    if (item.media?.is_image) {
      const images: MessageItem[] = []
      while (index < members.length && members[index].media?.is_image) {
        images.push(members[index])
        index += 1
      }
      blocks.push({ kind: 'images', items: images, key: `images:${images[0].id}:${images[images.length - 1].id}` })
      for (const image of images) {
        const text = image.text.trim()
        if (text) blocks.push({ kind: 'text', item: image, text, key: `caption:${image.id}` })
      }
      continue
    }
    if (item.media) blocks.push({ kind: 'file', item, key: `file:${item.id}` })
    const text = item.text.trim()
    if (text) blocks.push({ kind: 'text', item, text, key: `text:${item.id}` })
    index += 1
  }
  return blocks
}

function ImageWithSkeleton({ src, gallery, mediaDisplay, onClick, onDragStart }: any) {
  const [loaded, setLoaded] = useState(false)
  return <>
    {!loaded && <Skeleton variant="rounded" animation="wave" width="100%" height={gallery ? '100%' : 240} sx={{ position: 'absolute', inset: 0, borderRadius: 0, zIndex: 1 }} />}
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
      sx={{ display: 'block', width: gallery || mediaDisplay === 'framed' ? '100%' : 'auto', maxWidth: '100%', height: gallery || mediaDisplay === 'framed' ? '100%' : 'auto', maxHeight: gallery || mediaDisplay === 'framed' ? '100%' : 'min(78vh, 1280px)', objectFit: gallery ? 'cover' : 'contain', cursor: 'zoom-in', opacity: loaded ? 1 : 0, transition: 'opacity 0.3s ease' }}
    />
  </>
}

export function MessageContentCard({
  siteKey,
  dialog,
  message,
  group,
  media,
  mediaDisplay,
  selectedKeys,
  selectionMode,
  loadMedia,
  openFullMedia,
  toggle,
  editIndex,
  openUsage,
}: MessageContentCardProps) {
  const [expanded, setExpanded] = useState(false)
  const members = group?.messages || [message]
  const contentBlocks = buildContentBlocks(members)
  const images = members.filter(item => item.media?.is_image)
  const memberKeys = members.map(item => stableMessageKey(dialog.peer_key, item.id))
  const selected = memberKeys.every(key => selectedKeys.includes(key))
  const anyUsed = members.some(item => item.usage.used)
  const allUsed = members.every(item => item.usage.used)
  const anyStale = members.some(item => item.usage.usage_state === 'stale')
  const collapsible = contentBlocks.some(block => block.kind === 'text' && (block.text.length > 700 || block.text.split('\n').length > 8))
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
  const firstTime = formatDate(members[0].date)
  const lastTime = formatDate(members[members.length - 1].date)
  const authorPeerKey = message.outgoing
    ? null
    : message.sender_key || (dialog.display_kind === 'personal' ? dialog.peer_key : null)
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
      borderRadius: message.outgoing ? '16px 16px 16px 5px' : '16px 16px 5px 16px',
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
    {dialog.display_kind !== 'channel' && <CardHeader
      action={message.sender_is_eitaa_contact && <Chip size="small" color="primary" variant="outlined" label="مخاطب" />}
      title={<Typography variant="subtitle2" component="h3" fontWeight={850}>{writer}</Typography>}
      subheader={<Stack direction="row" spacing={0.75} alignItems="center" flexWrap="wrap">
        {message.sender_username && writer !== `@${message.sender_username.replace(/^@/, '')}` && <Typography variant="caption" color="text.secondary" dir="ltr">@${message.sender_username.replace(/^@/, '')}</Typography>}
      </Stack>}
      sx={{ px: { xs: 1.25, sm: 1.75 }, py: 1.1 }}
    />}

    {members.length > 1 && <Box sx={{ px: 1.25, pb: 0.75 }}><Chip size="small" color={group?.kind === 'inferred' ? 'warning' : 'info'} variant="outlined" label={group?.kind === 'inferred' ? `گالری پیشنهادی · ${members.length.toLocaleString('fa-IR')} تصویر` : `${members.length.toLocaleString('fa-IR')} پیام پیوسته`} /></Box>}

    {contentBlocks.map(block => {
      if (block.kind === 'images') {
        const gallery = block.items.length > 1
        return <Box key={block.key} sx={{ width: '100%', overflow: 'hidden', bgcolor: 'action.hover', display: gallery ? 'grid' : 'flex', justifyContent: 'center', alignItems: 'flex-start', gridTemplateColumns: gallery ? (block.items.length > 4 ? 'repeat(3, minmax(0, 1fr))' : 'repeat(2, minmax(0, 1fr))') : undefined, gridTemplateRows: gallery ? (block.items.length > 4 ? `repeat(${Math.ceil(block.items.length / 3)}, minmax(0, 1fr))` : 'repeat(2, minmax(0, 1fr))') : undefined, gap: gallery ? 0.25 : 0, aspectRatio: gallery || mediaDisplay === 'framed' ? '4 / 3' : 'auto' }}>
          {block.items.map((item, index) => {
            const key = stableMessageKey(dialog.peer_key, item.id)
            const selectedMediaUrl = media[key]
            const spanFirstOfThree = gallery && block.items.length === 3 && index === 0
            return <Box key={key} sx={{ position: 'relative', minWidth: 0, minHeight: gallery ? 0 : 120, overflow: 'hidden', bgcolor: 'action.hover', gridRow: spanFirstOfThree ? '1 / -1' : block.items.length === 2 ? '1 / -1' : undefined, display: 'grid', placeItems: 'center' }}>
              {selectedMediaUrl
                ? <ImageWithSkeleton
                    src={selectedMediaUrl}
                    gallery={gallery}
                    mediaDisplay={mediaDisplay}
                    onClick={(event: any) => { event.stopPropagation(); void openFullMedia(item) }}
                    onDragStart={(event: any) => { event.dataTransfer.setData('application/x-eitaa-source', key); event.dataTransfer.effectAllowed = 'copy' }}
                  />
                : selectedMediaUrl === null
                  ? <Skeleton variant="rounded" animation="wave" width="100%" height={gallery ? '100%' : 240} sx={{ borderRadius: 0 }} />
                  : <Typography variant="caption" color="text.secondary" sx={{ p: 3 }}>پیش‌نمایش تصویر</Typography>}
            </Box>
          })}
        </Box>
      }
      if (block.kind === 'file') {
        return <Box key={block.key} sx={{ px: { xs: 1.25, sm: 1.75 }, pt: 1 }}><Chip size="small" variant="outlined" label={`📎 ${block.item.media?.file_name || block.item.media?.type}`} /></Box>
      }
      const blockCollapsible = block.text.length > 700 || block.text.split('\n').length > 8
      return <Box key={block.key} sx={{ px: { xs: 1.25, sm: 1.75 }, pt: 1 }}>
        {blockCollapsible && !expanded && <Typography component="div" variant="body2" sx={{ whiteSpace: 'pre-wrap', lineHeight: 1.9, overflowWrap: 'anywhere' }}>{block.text.slice(0, 420).trimEnd()}…</Typography>}
        <Collapse in={!blockCollapsible || expanded} timeout="auto" unmountOnExit={blockCollapsible}>
          <Typography component="div" variant="body2" sx={{ whiteSpace: 'pre-wrap', lineHeight: 1.9, overflowWrap: 'anywhere' }}>{block.text}</Typography>
        </Collapse>
      </Box>
    })}

    {indexPredictions.length > 0 && <CardContent sx={{ px: { xs: 1.25, sm: 1.75 }, py: 1, '&:last-child': { pb: 1 } }}>
      <Stack direction="row" flexWrap="wrap" gap={0.5} aria-label="پیشنهادهای ایندکس محلی" alignItems="center">
        {indexPredictions.map(prediction => <Chip size="small" color={prediction.manual ? 'success' : 'secondary'} variant="outlined" key={prediction.label_id} title={`${Math.round(prediction.score * 100)}٪${prediction.evidence.length ? ` — نشانه‌ها: ${prediction.evidence.join('، ')}` : ''}`} label={`${prediction.label_name} · ${prediction.manual ? 'دستی' : `${Math.round(prediction.score * 100)}٪`}`} />)}
        <IconButton aria-label="اصلاح ایندکس پیام" size="small" sx={{ ml: 0.5 }} onClick={event => { event.stopPropagation(); editIndex() }}><EditRounded fontSize="small" /></IconButton>
      </Stack>
    </CardContent>}

    <CardActions disableSpacing sx={{ minHeight: 44, px: 1, pt: 0, gap: 0.25 }}>
      <Checkbox
        inputProps={{ 'aria-label': members.length > 1 ? 'انتخاب گروه پیام' : 'انتخاب پیام' }}
        checked={selected}
        onClick={event => { event.stopPropagation(); toggle() }}
        size="small"
      />
      {dialog.display_kind === 'personal' && <Typography variant="caption" color="text.secondary" sx={{ direction: 'ltr' }}>{members.length > 1 ? `#${firstId}–#${lastId}` : `#${message.id}`}</Typography>}
      <Typography variant="caption" color="text.secondary" sx={{ ml: 0.75 }}>{firstTime === lastTime ? firstTime : `${firstTime}–${lastTime}`}</Typography>
      <Box sx={{ flex: 1 }} />
      {anyUsed && <Button size="small" color={anyStale ? 'warning' : 'error'} variant="outlined" onClick={event => { event.stopPropagation(); openUsage() }} sx={{ minHeight: 28, py: 0 }}>{anyStale ? 'تغییرکرده' : allUsed ? 'وردپرس' : 'بخشی در وردپرس'}</Button>}
      {collapsible && <IconButton
        aria-label={expanded ? 'بستن ادامه پیام' : 'نمایش ادامه پیام'}
        aria-expanded={expanded}
        onClick={event => { event.stopPropagation(); setExpanded(value => !value) }}
        sx={{ transform: expanded ? 'rotate(180deg)' : 'rotate(0deg)', transition: theme => theme.transitions.create('transform', { duration: theme.transitions.duration.shortest }) }}
      ><ExpandMoreRounded /></IconButton>}
      {dialog.display_kind !== 'channel' && <MessageAuthorAvatar siteKey={siteKey} peerKey={authorPeerKey} name={writer} />}
    </CardActions>
  </Card>
}
