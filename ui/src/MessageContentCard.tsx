import { useEffect, useMemo, useRef, useState } from 'react'
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
  CircularProgress,
  Collapse,
  IconButton,
  Skeleton,
  Stack,
  Tooltip,
  Typography,
} from '@mui/material'
import EditRounded from '@mui/icons-material/EditRounded'
import AudioFileRounded from '@mui/icons-material/AudioFileRounded'
import DownloadRounded from '@mui/icons-material/DownloadRounded'
import ExpandMoreRounded from '@mui/icons-material/ExpandMoreRounded'
import InfoOutlined from '@mui/icons-material/InfoOutlined'
import ReplayRounded from '@mui/icons-material/ReplayRounded'
import VideoFileRounded from '@mui/icons-material/VideoFileRounded'
import AssignmentRounded from '@mui/icons-material/AssignmentRounded'
import AddTaskRounded from '@mui/icons-material/AddTaskRounded'
import CallSplitRounded from '@mui/icons-material/CallSplitRounded'
import type { ReportingWitnessStatus } from './lib/api'
import type { MessageGroup } from './lib/groupedMedia'
import { playableMediaKind } from './lib/messageMedia'
import { stableMessageKey } from './lib/scrollMath'
import type { DialogItem, IndexPrediction, MessageItem } from './lib/types'
import { loadDialogAvatar, peekDialogAvatar } from './lib/avatarLoader'
import { MACRO_INDICATORS, type MessageIndicatorData } from './lib/indicators'

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
  editIndex?: () => void
  openUsage: () => void
  reportUsageByMessage?: Record<string, ReportingWitnessStatus>
  openReportEvent: (eventId: string) => void
  openRegistration: (
    messageIds: number[],
    sourceMessage?: MessageItem,
    sourceMembers?: MessageItem[],
    initialMacroIndicator?: string,
    initialMicroIndicators?: string[],
  ) => void
  liaisonsMap?: Record<string, { full_name: string; unit_display_name: string }>
  onAuthorClick?: (author: { name: string; username?: string; userId?: string; senderKey?: string; message?: MessageItem }) => void
  indicatorsMap?: Record<string, MessageIndicatorData>
  detachedMessageIds?: Set<number>
  onOpenSplitDialog?: (groupMessages: MessageItem[]) => void
  onOpenMacroSelect?: (messageIds: number[], currentMacro: string) => void
  onOpenMicroEdit?: (messageIds: number[], currentMicros: string[]) => void
}

type MessageContentBlock =
  | { kind: 'images'; items: MessageItem[]; key: string }
  | { kind: 'file'; item: MessageItem; key: string }
  | { kind: 'text'; item: MessageItem; text: string; key: string }

function formatDate(value: string) {
  try { return MESSAGE_DATE_FORMATTER.format(new Date(value)) }
  catch { return value }
}

export function authorLabel(dialog?: DialogItem | null, message?: MessageItem | null) {
  if (!message) return 'نویسنده نامشخص'
  if (message.outgoing || message.sender_resolution === 'self') return 'شما'
  const displayName = message.sender_display_name?.trim()
  if (displayName) return displayName
  const username = message.sender_username?.trim()
  if (username) return `@${username.replace(/^@/, '')}`
  if (dialog?.display_kind === 'personal') {
    return dialog.peer.title?.trim() || (dialog.peer.username ? `@${dialog.peer.username}` : 'مخاطب ایتا')
  }
  return dialog?.peer?.title?.trim() || 'نویسنده نامشخص'
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

const loadedMediaUrls = new Set<string>()

function ImageWithSkeleton({ src, gallery, mediaDisplay, onClick, onDragStart }: any) {
  const isAlreadyLoaded = Boolean(src && loadedMediaUrls.has(src))
  const [loaded, setLoaded] = useState(() => isAlreadyLoaded)
  const imgRef = useRef<HTMLImageElement>(null)

  useEffect(() => {
    if (src && loadedMediaUrls.has(src)) {
      setLoaded(true)
    } else if (imgRef.current?.complete && imgRef.current.naturalWidth > 0) {
      if (src) loadedMediaUrls.add(src)
      setLoaded(true)
    }
  }, [src])

  return <>
    {(!loaded && !isAlreadyLoaded) && <Skeleton variant="rounded" animation="wave" width="100%" height={gallery ? '100%' : 240} sx={{ position: 'absolute', inset: 0, borderRadius: 0, zIndex: 1 }} />}
    <CardMedia
      ref={imgRef}
      component="img"
      src={src}
      alt="پیش‌نمایش رسانه پیام"
      title="برای دریافت و نمایش تصویر اصلی کلیک کنید"
      loading={isAlreadyLoaded ? 'eager' : 'lazy'}
      draggable
      onClick={onClick}
      onDragStart={onDragStart}
      onLoad={() => {
        if (src) loadedMediaUrls.add(src)
        setLoaded(true)
      }}
      onError={() => {
        setLoaded(true)
      }}
      sx={{ display: 'block', width: gallery || mediaDisplay === 'framed' ? '100%' : 'auto', maxWidth: '100%', height: gallery || mediaDisplay === 'framed' ? '100%' : 'auto', maxHeight: gallery || mediaDisplay === 'framed' ? '100%' : 'min(78vh, 1280px)', objectFit: gallery ? 'cover' : 'contain', cursor: 'zoom-in', opacity: (loaded || isAlreadyLoaded) ? 1 : 0, transition: 'opacity 0.15s ease' }}
    />
  </>
}

function galleryColumnSpan(itemCount: number, index: number, compact: boolean): number {
  if (itemCount <= 1) return 6
  if (compact) return itemCount % 2 === 1 && index === itemCount - 1 ? 6 : 3
  if (itemCount === 2) return 3
  if (itemCount === 3) return 2
  if (itemCount === 4) return 3
  if (itemCount === 5) return index < 3 ? 2 : 3
  const remainder = itemCount % 3
  if (remainder === 1 && index === itemCount - 1) return 6
  if (remainder === 2 && index >= itemCount - 2) return 3
  return 2
}

function galleryTileAspectRatio(columnSpan: number): string {
  return columnSpan === 6 ? '16 / 9' : '4 / 3'
}

function PlayableMediaBlock({
  item,
  peerKey,
  media,
  loadMedia,
}: {
  item: MessageItem
  peerKey: string
  media: Record<string, string | null>
  loadMedia: (message: MessageItem) => Promise<void>
}) {
  const kind = playableMediaKind(item.media)
  if (!kind) return <Chip size="small" variant="outlined" label={`📎 ${item.media?.file_name || item.media?.type}`} />
  const key = stableMessageKey(peerKey, item.id)
  const source = media[key]
  const loading = source === null
  const failed = source === ''
  const label = kind === 'audio' ? 'صوت' : 'ویدئو'
  const title = item.media?.file_name || label
  return <Box
    sx={{ border: 1, borderColor: 'divider', borderRadius: 2, overflow: 'hidden', bgcolor: 'background.default' }}
    onClick={event => event.stopPropagation()}
  >
    <Stack direction="row" spacing={1} alignItems="center" sx={{ px: 1.25, py: 1 }}>
      {kind === 'audio' ? <AudioFileRounded color="primary" /> : <VideoFileRounded color="primary" />}
      <Typography variant="body2" fontWeight={750} noWrap sx={{ flex: 1 }} title={title}>{title}</Typography>
      {!source && <Button
        type="button"
        size="small"
        variant={failed ? 'outlined' : 'contained'}
        color={failed ? 'error' : 'primary'}
        disabled={loading}
        startIcon={loading ? <CircularProgress size={16} color="inherit" /> : failed ? <ReplayRounded /> : <DownloadRounded />}
        onClick={event => { event.stopPropagation(); void loadMedia(item) }}
      >
        {loading ? `در حال بارگیری ${label}…` : failed ? `تلاش دوباره برای ${label}` : `بارگیری ${label}`}
      </Button>}
    </Stack>
    {failed && <Typography variant="caption" color="error" sx={{ display: 'block', px: 1.25, pb: 1 }}>بارگیری ناموفق بود؛ دوباره تلاش کنید.</Typography>}
    {source && kind === 'audio' && <Box component="audio" controls preload="metadata" src={source} aria-label={`پخش ${title}`} sx={{ display: 'block', width: '100%', px: 1, pb: 1 }} />}
    {source && kind === 'video' && <Box component="video" controls playsInline preload="metadata" src={source} aria-label={`پخش ${title}`} sx={{ display: 'block', width: '100%', maxHeight: 'min(72vh, 720px)', bgcolor: 'common.black' }} />}
  </Box>
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
  openUsage,
  reportUsageByMessage,
  openReportEvent,
  openRegistration,
  liaisonsMap,
  onAuthorClick,
  indicatorsMap,
  detachedMessageIds,
  onOpenSplitDialog,
  onOpenMacroSelect,
  onOpenMicroEdit,
}: MessageContentCardProps) {
  const [expanded, setExpanded] = useState(false)
  const members = group?.messages || [message]
  const reportUsage = reportUsageByMessage?.[String(message.id)]
    || members.map(item => reportUsageByMessage?.[String(item.id)]).find(Boolean)
    || undefined

  const messageIndicator = indicatorsMap?.[String(message.id)] || indicatorsMap?.[String(members[0].id)]
  const currentMacro = messageIndicator?.macro_indicator || ''
  const currentMicros = messageIndicator?.micro_indicators || []
  const isExplicitlyNoneMacro = currentMacro === 'none'
  const isAssignedMacro = Boolean(currentMacro && currentMacro !== 'none')
  const contentBlocks = buildContentBlocks(members)
  const images = members.filter(item => item.media?.is_image)
  const memberKeys = members.map(item => stableMessageKey(dialog.peer_key, item.id))
  const selected = memberKeys.every(key => selectedKeys.includes(key))
  const anyUsed = members.some(item => item.usage.used)
  const allUsed = members.every(item => item.usage.used)
  const anyStale = members.some(item => item.usage.usage_state === 'stale')
  const collapsible = contentBlocks.some(block => block.kind === 'text' && (block.text.length > 700 || block.text.split('\n').length > 8))
  const rawWriter = authorLabel(dialog, message)
  const senderUserId = message.sender_key?.startsWith('u:') ? message.sender_key.slice(2) : undefined

  const matchedLiaison = useMemo(() => {
    if (!liaisonsMap || message.outgoing) return null
    if (message.sender_key && liaisonsMap[message.sender_key]) return liaisonsMap[message.sender_key]
    if (senderUserId && liaisonsMap[senderUserId]) return liaisonsMap[senderUserId]
    if (message.sender_username) {
      const clean = message.sender_username.toLowerCase().replace(/^@/, '')
      if (liaisonsMap[clean]) return liaisonsMap[clean]
    }
    const rawName = message.sender_display_name?.trim()
    if (rawName && liaisonsMap[rawName]) return liaisonsMap[rawName]
    if (rawWriter && liaisonsMap[rawWriter]) return liaisonsMap[rawWriter]
    return null
  }, [liaisonsMap, message.outgoing, message.sender_key, senderUserId, message.sender_username, message.sender_display_name, rawWriter])

  // Requirement 4: نام + " - " + "حوزه قضایی" + نام حوزه قضایی
  const writer = matchedLiaison && matchedLiaison.unit_display_name
    ? `${matchedLiaison.full_name || rawWriter} - حوزه قضایی ${matchedLiaison.unit_display_name}`
    : rawWriter
  const isLiaison = Boolean(matchedLiaison)

  const senderIsSelf = message.outgoing || message.sender_resolution === 'self'
  const senderIsContact = Boolean(
    !senderIsSelf
    && (
      message.sender_is_eitaa_contact
      || message.sender_resolution === 'eitaa_contact'
      || message.sender_resolution === 'local_contact'
    )
  )
  const imageKeys = images.map(item => stableMessageKey(dialog.peer_key, item.id)).join('|')
  const autoSuggestedMacro = useMemo(() => {
    if (isAssignedMacro || isExplicitlyNoneMacro) return ''
    for (const item of members) {
      for (const pred of item.index_predictions || []) {
        if (pred.label_name.includes('سال') || pred.label_name.includes('ماه') || pred.label_name.includes('مهر')) continue
        for (const m of MACRO_INDICATORS) {
          const cleanName = pred.label_name.replace(/ - کد \d+/, '').trim()
          if (m.includes(cleanName) || cleanName.includes(m)) {
            return m
          }
        }
      }
    }
    const combinedText = members.map(m => m.text || '').join(' ')
    if (combinedText.includes('نماز') || combinedText.includes('بین الصلاتین') || combinedText.includes('نمازخانه')) {
      return 'ترویج و توسعه فرهنگ اقامه نماز'
    }
    if (combinedText.includes('مراسم') || combinedText.includes('شهادت') || combinedText.includes('ولادت') || combinedText.includes('زیارت عاشورا') || combinedText.includes('موکب')) {
      return 'برگزاری مراسم در مناسبت‌های ملی، مذهبی و انقلابی'
    }
    if (combinedText.includes('مسابقه') || combinedText.includes('قرآن') || combinedText.includes('ورزشی')) {
      return 'برگزاری مسابقات استانی فرهنگی، قرآنی و ورزشی'
    }
    if (combinedText.includes('اردو') || combinedText.includes('سفر زیارتی')) {
      return 'برگزاری اردوهای فرهنگی زیارتی برای کارکنان و خانواده'
    }
    if (combinedText.includes('تجلیل') || combinedText.includes('تکریم') || combinedText.includes('بازنشسته')) {
      return 'تکریم و تجلیل از همکاران و خانواده'
    }
    if (combinedText.includes('ارباب رجوع') || combinedText.includes('میز خدمت')) {
      return 'تشویق کارمندان و تکریم ارباب رجوع'
    }
    return ''
  }, [members, isAssignedMacro, isExplicitlyNoneMacro])

  const autoSuggestedMicros = useMemo(() => {
    if (currentMicros.length > 0) return []
    const tags = new Set<string>()
    for (const item of members) {
      const text = item.text || ''
      const matches = text.match(/#([\p{L}\p{N}_]{3,25})/gu) || []
      for (const m of matches) {
        tags.add(m.replace('#', '').replace(/_/g, ' ').trim())
      }
    }
    return Array.from(tags).slice(0, 3)
  }, [members, currentMicros])

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
      title={<Stack direction="row" spacing={0.75} alignItems="center" flexWrap="wrap">
        <Typography
          variant="subtitle2"
          component="h3"
          color={senderIsContact ? 'primary.main' : 'text.primary'}
          fontWeight={senderIsContact ? 900 : senderIsSelf ? 850 : 500}
          onClick={onAuthorClick ? (event) => {
            event.stopPropagation()
            onAuthorClick({
              name: matchedLiaison?.full_name || rawWriter,
              username: message.sender_username || undefined,
              userId: senderUserId,
              senderKey: message.sender_key || undefined,
              message,
            })
          } : undefined}
          sx={{
            cursor: onAuthorClick ? 'pointer' : 'default',
            '&:hover': onAuthorClick ? { textDecoration: 'underline' } : {},
            ...(isLiaison ? { color: 'primary.dark', fontWeight: 900 } : {}),
          }}
          title={onAuthorClick ? "برای مشاهده کارنامه یا تنظیمات رابط کلیک کنید" : undefined}
        >
          {writer}
        </Typography>
        {isLiaison && (
          <Tooltip title="رابط فرهنگی تاییدشده - برای مشاهده کارنامه و پروفایل فعالیت کلیک کنید">
            <Chip
              size="small"
              color="primary"
              variant="filled"
              label="رابط فرهنگی"
              onClick={onAuthorClick ? (event) => {
                event.stopPropagation()
                onAuthorClick({
                  name: matchedLiaison?.full_name || rawWriter,
                  username: message.sender_username || undefined,
                  userId: senderUserId,
                  senderKey: message.sender_key || undefined,
                  message,
                })
              } : undefined}
              sx={{ height: 20, fontSize: '0.65rem', cursor: onAuthorClick ? 'pointer' : 'default' }}
            />
          </Tooltip>
        )}
        {!senderIsSelf && !isLiaison && <Tooltip arrow title={senderIsContact ? 'مخاطب' : 'غیرمخاطب'}>
          <Box component="span" role="img" tabIndex={0} aria-label={senderIsContact ? 'مخاطب' : 'غیرمخاطب'} sx={{ display: 'inline-flex', cursor: 'help' }}>
            <InfoOutlined color={senderIsContact ? 'primary' : 'disabled'} fontSize="small" />
          </Box>
        </Tooltip>}
      </Stack>}
      subheader={<Stack direction="row" spacing={0.75} alignItems="center" flexWrap="wrap">
        {message.sender_username && rawWriter !== `@${message.sender_username.replace(/^@/, '')}` && <Typography variant="caption" color="text.secondary" dir="ltr">@${message.sender_username.replace(/^@/, '')}</Typography>}
      </Stack>}
      sx={{ px: { xs: 1.25, sm: 1.75 }, py: 1.1 }}
    />}

    {contentBlocks.map(block => {
      if (block.kind === 'images') {
        const gallery = block.items.length > 1
        return <Box key={block.key} sx={{ width: '100%', overflow: 'hidden', bgcolor: 'action.hover', display: gallery ? 'grid' : 'flex', justifyContent: 'center', alignItems: 'stretch', gridTemplateColumns: gallery ? 'repeat(6, minmax(0, 1fr))' : undefined, gap: gallery ? 0.5 : 0, aspectRatio: !gallery && mediaDisplay === 'framed' ? '4 / 3' : 'auto' }}>
          {block.items.map((item, index) => {
            const key = stableMessageKey(dialog.peer_key, item.id)
            const selectedMediaUrl = media[key]
            const compactSpan = galleryColumnSpan(block.items.length, index, true)
            const wideSpan = galleryColumnSpan(block.items.length, index, false)
            return <Box key={key} sx={{ position: 'relative', width: '100%', height: !gallery && mediaDisplay === 'framed' ? '100%' : 'auto', minWidth: 0, minHeight: gallery ? 0 : 120, overflow: 'hidden', bgcolor: 'action.hover', gridColumn: gallery ? { xs: `span ${compactSpan}`, sm: `span ${wideSpan}` } : undefined, aspectRatio: gallery ? { xs: galleryTileAspectRatio(compactSpan), sm: galleryTileAspectRatio(wideSpan) } : undefined, display: 'grid', placeItems: 'center', '& img': { transition: theme => theme.transitions.create('transform', { duration: theme.transitions.duration.shorter }) }, '&:hover img': { transform: gallery ? 'scale(1.025)' : 'none' } }}>
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
        return <Box key={block.key} sx={{ px: { xs: 1.25, sm: 1.75 }, pt: 1 }}><PlayableMediaBlock item={block.item} peerKey={dialog.peer_key} media={media} loadMedia={loadMedia} /></Box>
      }
      const blockCollapsible = block.text.length > 700 || block.text.split('\n').length > 8
      return <Box key={block.key} sx={{ px: { xs: 1.25, sm: 1.75 }, pt: 1 }}>
        {blockCollapsible && !expanded && <Typography component="div" variant="body2" sx={{ whiteSpace: 'pre-wrap', lineHeight: 1.9, overflowWrap: 'anywhere' }}>{block.text.slice(0, 420).trimEnd()}…</Typography>}
        <Collapse in={!blockCollapsible || expanded} timeout="auto" unmountOnExit={blockCollapsible}>
          <Typography component="div" variant="body2" sx={{ whiteSpace: 'pre-wrap', lineHeight: 1.9, overflowWrap: 'anywhere' }}>{block.text}</Typography>
        </Collapse>
      </Box>
    })}

    {/* نوار شاخصه‌های کلی و جزئی و دکمه تفکیک پیام */}
    <Box
      sx={{
        px: { xs: 1.25, sm: 1.75 },
        py: 0.75,
        borderTop: '1px solid',
        borderColor: 'divider',
        bgcolor: 'action.hover',
        display: 'flex',
        flexWrap: 'wrap',
        alignItems: 'center',
        gap: 1,
      }}
    >
      {/* ۱. دکمه تفکیک پیام (فقط زمانی که پیام‌ها یکپارچه شده‌اند نشان داده می‌شود) */}
      {members.length > 1 && (
        <Button
          size="small"
          variant="outlined"
          color="warning"
          startIcon={<CallSplitRounded sx={{ fontSize: '1rem' }} />}
          onClick={event => {
            event.stopPropagation()
            onOpenSplitDialog?.(members)
          }}
          sx={{ minHeight: 26, py: 0.25, px: 1, fontSize: '0.72rem', fontWeight: 700 }}
        >
          تفکیک پیام
        </Button>
      )}

      {/* ۲. شاخصه کلی: بولد + دکمه مداد برای اصلاح */}
      <Stack direction="row" spacing={0.5} alignItems="center">
        <Typography
          variant="caption"
          component="span"
          sx={{
            fontWeight: isAssignedMacro ? 700 : 600, // بولد مطابق خواسته کاربر
            color: isAssignedMacro
              ? 'primary.main'
              : isExplicitlyNoneMacro
              ? 'text.secondary'
              : autoSuggestedMacro
              ? 'primary.light'
              : 'text.secondary',
            fontSize: '0.78rem',
            cursor: 'pointer',
            fontStyle: !isAssignedMacro && autoSuggestedMacro ? 'italic' : 'normal',
          }}
          onClick={event => {
            event.stopPropagation()
            onOpenMacroSelect?.(members.map(m => m.id), isExplicitlyNoneMacro ? 'none' : (currentMacro || autoSuggestedMacro))
          }}
          title="شاخصه کلی (سرفصل برنامه‌ای)"
        >
          {isAssignedMacro
            ? `شاخصه کلی: ${currentMacro}`
            : isExplicitlyNoneMacro
            ? 'شاخصه کلی: فاقد شاخصه (آزاد / اطلاعیه)'
            : autoSuggestedMacro
            ? `شاخصه کلی (پیشنهادی): ${autoSuggestedMacro}`
            : 'شاخصه کلی (تعیین‌نشده)'}
        </Typography>
        <Tooltip title="اصلاح شاخصه کلی">
          <IconButton
            size="small"
            aria-label="اصلاح شاخصه کلی"
            onClick={event => {
              event.stopPropagation()
              onOpenMacroSelect?.(members.map(m => m.id), isExplicitlyNoneMacro ? 'none' : (currentMacro || autoSuggestedMacro))
            }}
            sx={{ p: 0.25 }}
          >
            <EditRounded sx={{ fontSize: '0.85rem' }} />
          </IconButton>
        </Tooltip>
      </Stack>

      {/* فاصله ملموس و تفکیک‌کننده بین شاخصه کلی و شاخصه‌های جزئی */}
      <Box sx={{ width: 1, height: 16, bgcolor: 'divider', mx: 0.5 }} />

      {/* ۳. شاخصه‌های جزئی: رنگ دیگر، بولد نباشد، مداد در انتها، امکان چند خطی شدن */}
      <Stack
        direction="row"
        spacing={0.5}
        alignItems="center"
        flexWrap="wrap"
        sx={{ flex: 1, minWidth: 160 }}
      >
        <Typography
          variant="caption"
          sx={{
            fontWeight: 400, // بولد نباشد مطابق خواسته کاربر
            color: 'secondary.main',
            fontSize: '0.75rem',
            ml: 0.5,
          }}
        >
          شاخصه‌های جزئی:
        </Typography>

        {currentMicros.length === 0 ? (
          autoSuggestedMicros.length > 0 ? (
            autoSuggestedMicros.map(micro => (
              <Chip
                key={micro}
                label={`${micro} (پیشنهادی)`}
                size="small"
                variant="outlined"
                color="secondary"
                onClick={event => {
                  event.stopPropagation()
                  onOpenMicroEdit?.(members.map(m => m.id), autoSuggestedMicros)
                }}
                sx={{
                  height: 22,
                  fontSize: '0.68rem',
                  fontWeight: 400,
                  borderStyle: 'dashed',
                  my: 0.25,
                  cursor: 'pointer',
                }}
              />
            ))
          ) : (
            <Typography
              variant="caption"
              sx={{
                fontWeight: 400,
                color: 'text.disabled',
                fontSize: '0.75rem',
                fontStyle: 'italic',
                cursor: 'pointer',
              }}
              onClick={event => {
                event.stopPropagation()
                onOpenMicroEdit?.(members.map(m => m.id), currentMicros)
              }}
            >
              (تعیین‌نشده)
            </Typography>
          )
        ) : (
          currentMicros.map(micro => (
            <Chip
              key={micro}
              label={micro}
              size="small"
              variant="filled"
              color="secondary" // رنگ دیگر
              onClick={event => {
                event.stopPropagation()
                onOpenMicroEdit?.(members.map(m => m.id), currentMicros)
              }}
              sx={{
                height: 22,
                fontSize: '0.68rem',
                fontWeight: 400, // بولد نباشد
                my: 0.25,
                cursor: 'pointer',
              }}
            />
          ))
        )}

        {/* علامت مداد در انتهای شاخصه‌های جزئی */}
        <Tooltip title="اصلاح شاخصه‌های جزئی">
          <IconButton
            size="small"
            aria-label="اصلاح شاخصه‌های جزئی"
            onClick={event => {
              event.stopPropagation()
              onOpenMicroEdit?.(members.map(m => m.id), currentMicros.length > 0 ? currentMicros : autoSuggestedMicros)
            }}
            sx={{ p: 0.25 }}
          >
            <EditRounded sx={{ fontSize: '0.85rem' }} />
          </IconButton>
        </Tooltip>
      </Stack>
    </Box>

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
      {reportUsage?.registered && reportUsage.events.length > 0 && <Chip
        size="small"
        color={reportUsage.events[0].review_status === 'approved' ? 'success' : reportUsage.events[0].review_status === 'conflict' ? 'error' : 'warning'}
        variant="filled"
        icon={<AssignmentRounded />}
        label={`ثبت‌شده · ${reportUsage.events.length > 1 ? `${reportUsage.events.length} پرونده` : reportUsage.events[0].review_status === 'draft' ? 'پیش‌نویس' : reportUsage.events[0].review_status === 'needs_review' ? 'نیازمند بازبینی' : reportUsage.events[0].review_status === 'approved' ? 'تأییدشده' : 'تعارض'}`}
        title="این پیام به پروندهٔ گزارش پیوند دارد"
        onClick={event => { event.stopPropagation(); openReportEvent(reportUsage.events[0].event_id) }}
        sx={{ minHeight: 28 }}
      />}
      {!reportUsage?.registered && <Button size="small" variant="outlined" color="primary" startIcon={<AddTaskRounded />} onClick={event => { event.stopPropagation(); openRegistration(members.map(item => item.id), message, members, isExplicitlyNoneMacro ? '' : (currentMacro || autoSuggestedMacro), currentMicros.length > 0 ? currentMicros : autoSuggestedMicros) }} sx={{ minHeight: 28, py: 0 }}>ثبت در گزارش</Button>}
      {anyUsed && <Button size="small" color={anyStale ? 'warning' : 'error'} variant="outlined" onClick={event => { event.stopPropagation(); openUsage() }} sx={{ minHeight: 28, py: 0 }}>{anyStale ? 'تغییرکرده' : allUsed ? 'وردپرس' : 'بخشی در وردپرس'}</Button>}
      {collapsible && <IconButton
        aria-label={expanded ? 'بستن ادامه پیام' : 'نمایش ادامه پیام'}
        aria-expanded={expanded}
        onClick={event => { event.stopPropagation(); setExpanded(value => !value) }}
        sx={{ transform: expanded ? 'rotate(180deg)' : 'rotate(0deg)', transition: theme => theme.transitions.create('transform', { duration: theme.transitions.duration.shortest }) }}
      ><ExpandMoreRounded /></IconButton>}
      {dialog.display_kind !== 'channel' && (
        <Box
          onClick={onAuthorClick ? (event) => {
            event.stopPropagation()
            onAuthorClick({
              name: matchedLiaison?.full_name || rawWriter,
              username: message.sender_username || undefined,
              userId: senderUserId,
              senderKey: message.sender_key || undefined,
              message,
            })
          } : undefined}
          sx={{ cursor: onAuthorClick ? 'pointer' : 'default', display: 'inline-flex' }}
          title={onAuthorClick ? "مشاهده کارنامه و پروفایل رابط" : undefined}
        >
          <MessageAuthorAvatar siteKey={siteKey} peerKey={authorPeerKey} name={matchedLiaison?.full_name || rawWriter} />
        </Box>
      )}
    </CardActions>
  </Card>
}
