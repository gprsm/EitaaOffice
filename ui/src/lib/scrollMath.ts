import type { MessageItem } from './types'

export const TOP_PAGINATION_TRIGGER_PX = 96
export const TOP_PAGINATION_REARM_PX = 280
export const BOTTOM_FOLLOW_THRESHOLD_PX = 180

export type ScrollAnchor = {
  key: string
  viewportOffset: number
}

export type MessageScrollMemory = {
  anchorKey: string | null
  anchorOffset: number
  scrollTop: number
  nearBottom: boolean
}

export type TopPaginationGate = {
  armed: boolean
  inFlight: boolean
}

export function stableMessageKey(peerKey: string, messageId: number): string {
  return `${peerKey}:${messageId}`
}

export function mergeMessagesById(existing: MessageItem[], incoming: MessageItem[]): MessageItem[] {
  if (!existing.length) return [...incoming].sort((a, b) => a.id - b.id)
  if (!incoming.length) return existing
  const merged = new Map<number, MessageItem>()
  for (const message of existing) merged.set(message.id, message)
  for (const message of incoming) merged.set(message.id, message)
  return [...merged.values()].sort((a, b) => a.id - b.id)
}

export function estimateMessageRowSize(message: MessageItem, hasDaySeparator: boolean, hasUnreadSeparator: boolean): number {
  const explicitLines = Math.max(1, message.text ? message.text.split(/\r?\n/).length : 1)
  const wrappedLines = message.text ? Math.max(1, Math.ceil(Math.max(message.text_length || 0, message.text.length) / 48)) : 0
  const textLines = Math.min(28, Math.max(explicitLines, wrappedLines))
  const textHeight = textLines ? 18 + textLines * 23 : 0
  const mediaHeight = message.media?.is_image ? 372 : message.media ? 46 : 0
  const separatorHeight = (hasDaySeparator ? 38 : 0) + (hasUnreadSeparator ? 38 : 0)
  return Math.max(72, 42 + textHeight + mediaHeight + separatorHeight)
}

export function anchorScrollTop(rowStart: number, viewportOffset: number): number {
  return Math.max(0, rowStart - viewportOffset)
}

export function isNearBottom(scrollHeight: number, scrollTop: number, clientHeight: number, threshold = BOTTOM_FOLLOW_THRESHOLD_PX): boolean {
  return scrollHeight - scrollTop - clientHeight <= threshold
}

export function shouldAutoFollow(wasNearBottom: boolean, appended: MessageItem[]): boolean {
  return wasNearBottom || appended.some(message => message.outgoing)
}

export function appendedMessagesAfterTail(messages: MessageItem[], previousTailId: number | null): MessageItem[] {
  if (!messages.length || previousTailId === null) return []
  const previousIndex = messages.findIndex(message => message.id === previousTailId)
  if (previousIndex < 0 || previousIndex >= messages.length - 1) return []
  return messages.slice(previousIndex + 1)
}

export function updateTopPaginationGate(scrollTop: number, previousScrollTop: number, gate: TopPaginationGate): { gate: TopPaginationGate; shouldRequest: boolean } {
  let armed = gate.armed
  if (scrollTop >= TOP_PAGINATION_REARM_PX) armed = true
  const shouldRequest = armed && !gate.inFlight && scrollTop <= TOP_PAGINATION_TRIGGER_PX && scrollTop < previousScrollTop
  return {
    gate: {
      armed: shouldRequest ? false : armed,
      inFlight: gate.inFlight,
    },
    shouldRequest,
  }
}
