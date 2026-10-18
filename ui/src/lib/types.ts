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
  active?: boolean
  account_role?: 'owner' | 'admin' | 'member' | 'unknown'
  can_manage_community?: boolean
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
    thumbnail_url?: string | null
    thumbnail_cached?: boolean
  } | null
  outgoing: boolean
  sender_key?: string | null
  sender_display_name?: string | null
  sender_username?: string | null
  sender_is_eitaa_contact?: boolean
  sender_resolution?: 'self' | 'eitaa_contact' | 'local_contact' | 'history_user' | 'community_member' | 'unknown'
  reply_to_message_id?: number | null
  grouped_id?: number | null
  album_size?: number
  index_predictions?: IndexPrediction[]
  usage: MessageUsage
}

export interface SenderFilterOption {
  key: string
  label: string
  username?: string | null
  isEitaaContact: boolean
  resolution: NonNullable<MessageItem['sender_resolution']>
}

export interface IndexPrediction {
  label_id: number
  label_name: string
  score: number
  evidence: string[]
  accepted: boolean
  manual?: boolean
  operator_id?: string
  operator_name?: string
  operator_role?: string
  review_status?: 'pending' | 'staff_reviewed' | 'approved' | 'rejected'
}

export interface ContentIndexResult {
  message_id: number
  text_hash: string
  model_version: string
  predictions: IndexPrediction[]
  indexed_at: string
  operator_id?: string
  operator_name?: string
  operator_role?: string
  review_status?: 'pending' | 'staff_reviewed' | 'approved' | 'rejected'
}

export interface ReportDefectItem {
  defect_code: string
  severity: 'blocker' | 'warning' | 'info'
  title: string
  description: string
  field_name: string
}

export interface StaffPerformanceSummary {
  total_staff: number
  total_actions: number
  total_tasks: number
  resolved_tasks: number
  average_accuracy: number
  total_reports?: number
  approved_reports?: number
  average_composite_score?: number
  total_overdue?: number
  total_revoked?: number
}

export interface StaffPerformanceItem {
  operator_id: string
  operator_name: string
  operator_role: string
  total_actions: number
  accept_count: number
  reject_count: number
  override_count: number
  accuracy_rate: number
  assigned_tasks: number
  resolved_tasks: number
  task_resolution_rate: number
  overdue_tasks?: number
  revoked_tasks?: number
  total_reports?: number
  approved_reports?: number
  first_time_approved?: number
  revision_required_reports?: number
  conflict_reports?: number
  report_approval_rate?: number
  first_time_right_rate?: number
  composite_score?: number
}

export interface StaffTaskChecklistItem {
  id: string
  text: string
  done: boolean
}

export interface StaffTask {
  task_id: string
  title: string
  description?: string
  defect_type: string
  priority: 'low' | 'medium' | 'high' | 'urgent'
  status: 'open' | 'in_progress' | 'resolved' | 'closed'
  assigned_to_user_id?: string
  assigned_to_name?: string
  created_by_user_id?: string
  created_by_name?: string
  due_date?: string | null
  resolution_notes?: string
  created_at: string
  updated_at?: string
  resolved_at?: string | null
  closed_at?: string | null
  peer_type?: string
  peer_id?: number
  message_id?: number
  macro_category?: 'workbook_approved' | 'other_cultural'
  program_codes?: string[]
  custom_topic?: string
  task_kind?: 'defect_resolution' | 'event_registration' | 'field_execution' | 'media_production' | 'inquiry_followup' | 'general'
  unit_scope?: string
  unit_name?: string
  checklist?: StaffTaskChecklistItem[]
  requires_manager_approval?: boolean
  reassigned_from_user_id?: string
  reassigned_from_name?: string
  is_escalated?: boolean
  escalated_at?: string | null
  escalation_notes?: string
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
