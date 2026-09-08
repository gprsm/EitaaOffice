import type { MessageItem } from './types'

type MessageMedia = NonNullable<MessageItem['media']>

export type PlayableMediaKind = 'audio' | 'video'

export const MAX_INTERACTIVE_MEDIA_BYTES = 512 * 1024 * 1024

const AUDIO_TYPES = new Set(['audio', 'voice', 'voice_message'])
const VIDEO_TYPES = new Set(['video', 'video_note', 'round_video'])
const AUDIO_EXTENSION = /\.(?:aac|amr|flac|m4a|mp3|oga|ogg|opus|wav)$/i
const VIDEO_EXTENSION = /\.(?:3gp|avi|m4v|mkv|mov|mp4|ogv|webm)$/i

export function playableMediaKind(media?: MessageMedia | null): PlayableMediaKind | null {
  if (!media || media.is_image) return null
  const type = String(media.type || '').trim().toLowerCase()
  const mimeType = String(media.mime_type || '').trim().toLowerCase()
  const fileName = String(media.file_name || '').trim()
  if (AUDIO_TYPES.has(type) || mimeType.startsWith('audio/') || AUDIO_EXTENSION.test(fileName)) return 'audio'
  if (VIDEO_TYPES.has(type) || mimeType.startsWith('video/') || VIDEO_EXTENSION.test(fileName)) return 'video'
  return null
}

export function mediaPreviewRequest(media?: MessageMedia | null): { quality: 'thumbnail' | 'full'; max_bytes?: number } {
  return playableMediaKind(media)
    ? { quality: 'full', max_bytes: MAX_INTERACTIVE_MEDIA_BYTES }
    : { quality: 'thumbnail' }
}
