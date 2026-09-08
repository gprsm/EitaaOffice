import type { MessageItem } from './types'

export const INFERRED_ALBUM_MAX_GAP_SECONDS = 120
export const MESSAGE_GROUP_MAX_GAP_SECONDS = 5 * 60

export type MediaAlbum = {
  key: string
  groupedId: number | null
  kind: 'server' | 'inferred'
  messages: MessageItem[]
  leader: MessageItem
  last: MessageItem
}

export type MessageGroup = {
  key: string
  kind: 'server' | 'inferred' | 'timeline'
  messages: MessageItem[]
  leader: MessageItem
  last: MessageItem
}

export type MessageGroupOptions = {
  fallbackIncomingSenderKey?: string | null
}

function createAlbum(key: string, groupedId: number | null, kind: MediaAlbum['kind'], messages: MessageItem[]): MediaAlbum {
  const members = [...messages].sort((a, b) => a.id - b.id)
  return { key, groupedId, kind, messages: members, leader: members[0], last: members[members.length - 1] }
}

function isInferredCandidate(message: MessageItem): boolean {
  return (
    (message.grouped_id === null || message.grouped_id === undefined)
    && Boolean(message.media?.is_image)
    && Boolean(message.sender_key)
  )
}

function sameReplyContext(left: MessageItem, right: MessageItem): boolean {
  return (left.reply_to_message_id ?? null) === (right.reply_to_message_id ?? null)
}

function closeInTime(left: MessageItem, right: MessageItem): boolean {
  const leftTime = Date.parse(left.date)
  const rightTime = Date.parse(right.date)
  if (!Number.isFinite(leftTime) || !Number.isFinite(rightTime)) return false
  return rightTime >= leftTime && (rightTime - leftTime) / 1000 <= INFERRED_ALBUM_MAX_GAP_SECONDS
}

export function buildAlbumLookup(messages: MessageItem[]): Map<number, MediaAlbum> {
  const ordered = [...messages].sort((a, b) => a.id - b.id)
  const grouped = new Map<number, MessageItem[]>()
  for (const message of ordered) {
    if (message.grouped_id === null || message.grouped_id === undefined) continue
    const members = grouped.get(message.grouped_id) || []
    members.push(message)
    grouped.set(message.grouped_id, members)
  }

  const lookup = new Map<number, MediaAlbum>()
  for (const [groupedId, members] of grouped) {
    const album = createAlbum(`server:${groupedId}`, groupedId, 'server', members)
    for (const member of album.messages) lookup.set(member.id, album)
  }

  let index = 0
  while (index < ordered.length) {
    const first = ordered[index]
    if (lookup.has(first.id) || !isInferredCandidate(first)) {
      index += 1
      continue
    }
    const run = [first]
    let cursor = index + 1
    while (cursor < ordered.length) {
      const previous = run[run.length - 1]
      const candidate = ordered[cursor]
      if (
        lookup.has(candidate.id)
        || !isInferredCandidate(candidate)
        || candidate.sender_key !== first.sender_key
        || candidate.id !== previous.id + 1
        || !sameReplyContext(previous, candidate)
        || !closeInTime(previous, candidate)
      ) break
      run.push(candidate)
      cursor += 1
    }
    if (run.length >= 2) {
      const album = createAlbum(
        `inferred:${first.sender_key}:${run[0].id}:${run[run.length - 1].id}`,
        null,
        'inferred',
        run,
      )
      for (const member of album.messages) lookup.set(member.id, album)
    }
    index = Math.max(index + 1, cursor)
  }
  return lookup
}

export function albumCaption(messages: MessageItem[]): string {
  const seen = new Set<string>()
  const captions: string[] = []
  for (const message of messages) {
    const caption = message.text.trim()
    if (!caption || seen.has(caption)) continue
    seen.add(caption)
    captions.push(caption)
  }
  return captions.join('\n\n')
}

function senderIdentity(message: MessageItem, fallbackIncomingSenderKey?: string | null): string | null {
  if (message.outgoing || message.sender_resolution === 'self') return 'sender:self'
  if (message.sender_key) return `sender:key:${message.sender_key}`
  const username = message.sender_username?.trim().replace(/^@/, '').toLowerCase()
  if (username) return `sender:username:${username}`
  return fallbackIncomingSenderKey ? `sender:fallback:${fallbackIncomingSenderKey}` : null
}

function localDayKey(value: string): string | null {
  const date = new Date(value)
  if (!Number.isFinite(date.getTime())) return null
  return `${date.getFullYear()}-${date.getMonth() + 1}-${date.getDate()}`
}

function canJoinMessageUnits(
  left: MessageItem,
  right: MessageItem,
  fallbackIncomingSenderKey?: string | null,
): boolean {
  const leftSender = senderIdentity(left, fallbackIncomingSenderKey)
  const rightSender = senderIdentity(right, fallbackIncomingSenderKey)
  if (!leftSender || leftSender !== rightSender) return false
  const leftTime = Date.parse(left.date)
  const rightTime = Date.parse(right.date)
  if (!Number.isFinite(leftTime) || !Number.isFinite(rightTime)) return false
  const gapSeconds = (rightTime - leftTime) / 1000
  if (gapSeconds < 0 || gapSeconds > MESSAGE_GROUP_MAX_GAP_SECONDS) return false
  const leftDay = localDayKey(left.date)
  return Boolean(leftDay && leftDay === localDayKey(right.date))
}

function createMessageGroup(
  units: { messages: MessageItem[]; album?: MediaAlbum }[],
): MessageGroup {
  const messages = units.flatMap(unit => unit.messages)
  const onlyAlbum = units.length === 1 ? units[0].album : undefined
  const kind = onlyAlbum?.kind || 'timeline'
  return {
    key: onlyAlbum?.key || `timeline:${messages[0].id}:${messages[messages.length - 1].id}`,
    kind,
    messages,
    leader: messages[0],
    last: messages[messages.length - 1],
  }
}

/**
 * Maps every member of a visual message block to one immutable group. Existing
 * provider albums are treated as atomic units, then adjacent units from the same
 * sender are merged when their gap is at most five minutes and the display day
 * does not change. Build this lookup from the unfiltered message window so a UI
 * filter cannot accidentally merge messages that were not adjacent originally.
 */
export function buildMessageGroupLookup(
  messages: MessageItem[],
  options: MessageGroupOptions = {},
): Map<number, MessageGroup> {
  const ordered = [...messages].sort((a, b) => a.id - b.id)
  const albums = buildAlbumLookup(ordered)
  const units: { messages: MessageItem[]; album?: MediaAlbum }[] = []
  for (const message of ordered) {
    const album = albums.get(message.id)
    if (album) {
      if (album.leader.id === message.id) units.push({ messages: album.messages, album })
      continue
    }
    units.push({ messages: [message] })
  }

  const lookup = new Map<number, MessageGroup>()
  let cursor = 0
  while (cursor < units.length) {
    const run = [units[cursor]]
    let next = cursor + 1
    while (next < units.length) {
      const previousUnit = run[run.length - 1]
      const candidateUnit = units[next]
      if (!canJoinMessageUnits(
        previousUnit.messages[previousUnit.messages.length - 1],
        candidateUnit.messages[0],
        options.fallbackIncomingSenderKey,
      )) break
      run.push(candidateUnit)
      next += 1
    }
    const memberCount = run.reduce((total, unit) => total + unit.messages.length, 0)
    if (memberCount >= 2 || run[0].album) {
      const group = createMessageGroup(run)
      for (const member of group.messages) lookup.set(member.id, group)
    }
    cursor = next
  }
  return lookup
}

export function messageGroupText(messages: MessageItem[]): string {
  return messages.map(message => message.text.trim()).filter(Boolean).join('\n\n')
}
