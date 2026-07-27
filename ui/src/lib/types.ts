export type PeerType = 'channel' | 'chat' | 'user'
export type DisplayKind = 'channel' | 'group' | 'personal'

export interface Site {
  site_key: string
  base_url: string
  is_default: boolean
  default_status: string
  default_category_id?: number | null
  timeout_seconds?: number
  verify_tls?: boolean
  retry_attempts?: number
  allow_insecure_http?: boolean
  username_env?: string
  application_password_env?: string
  username_configured?: boolean
  application_password_configured?: boolean
  credentials_configured: boolean
}

export interface DialogItem {
  peer_key: string
  peer: {
    id: number
    type: PeerType
    title?: string | null
    username?: string | null
    access_hash_present: boolean
  }
  peer_file: string
  technical_kind?: 'private' | 'basic_group' | 'supergroup' | 'channel' | 'unknown'
  display_kind: DisplayKind
  display_kind_locked: boolean
  favorite: boolean
  source: 'remote' | 'manual' | string
  top_message_id: number
  top_message_date?: number | null
  unread_count: number
  unread_mentions_count: number
  read_inbox_max_id?: number
  pinned: boolean
  unread_mark: boolean
  folder_id?: number | null
  broadcast?: boolean
  megagroup?: boolean
  participants_count?: number | null
  photo_cached_path?: string | null
  created_at?: string
  updated_at?: string
}

export interface UsageComposition {
  composition_key: string
  post_id: number
  post_url?: string | null
  status: string
  title: string
  updated_at: string
}

export interface MessageUsage {
  used: boolean
  usage_state: 'unused' | 'used' | 'stale'
  stale: boolean
  publication_status?: string | null
  external_post_id?: string | number | null
  external_url?: string | null
  compositions: UsageComposition[]
}

export interface MessageItem {
  id: number
  date: string
  text: string
  text_length: number
  media?: {
    type: string
    mime_type?: string | null
    file_name?: string | null
    size?: number | null
    is_image: boolean
  } | null
  outgoing: boolean
  sender_key?: string | null
  reply_to_message_id?: number | null
  grouped_id?: number | null
  album_size?: number
  index_predictions?: IndexPrediction[]
  usage: MessageUsage
}

export interface IndexPrediction {
  label_id: number
  label_name: string
  score: number
  evidence: string[]
  accepted: boolean
  manual?: boolean
}

export interface ContentIndexResult {
  message_id: number
  text_hash: string
  model_version: string
  predictions: IndexPrediction[]
  indexed_at: string
}

export interface ContentIndexJob {
  job_id: string
  state: 'queued' | 'running' | 'cancelling' | 'cancelled' | 'completed' | 'failed'
  local_only: boolean
  progress: {
    available_messages?: number
    target_messages?: number
    processed_messages?: number
    text_messages?: number
    indexed_messages?: number
    prediction_count?: number
    training_documents?: number
    cold_start?: boolean
    truncated?: boolean
    model_version?: string
  }
  result?: Record<string, unknown>
  error?: { message?: string }
}

export interface Term {
  id: number
  name: string
  slug: string
  count?: number
  parent_id?: number | null
}

export interface CompositionRecord {
  composition_key: string
  site_key: string
  post_id: number
  post_url?: string | null
  post_slug: string
  status: string
  title: string
  excerpt: string
  category_ids: number[]
  tag_ids: number[]
  source_keys: string[]
  featured_source_key?: string | null
  created_at?: string
  updated_at: string
}
