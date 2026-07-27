import type { MessageItem } from './types'

export const INFERRED_ALBUM_MAX_GAP_SECONDS = 120

export type MediaAlbum = {
  key: string
  groupedId: number | null
  kind: 'server' | 'inferred'
  messages: MessageItem[]
  leader: MessageItem
  last: MessageItem
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
