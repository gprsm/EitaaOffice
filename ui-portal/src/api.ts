/**
 * کلاینت API پرتال — همهٔ درخواست‌ها با مهلت زمانی و مدیریت خطای فارسی (F-097)
 */

export interface ApiEnvelope<T> {
  success: boolean
  message: string
  data: T
}

export interface ProgramSheet {
  code: string
  program_key: string
  name: string
  title: string
  description: string
  policy_framework: string
  monitoring_criteria: string[]
  questions: { key: string; label: string; qtype: string; auto_from: string; human_gate: boolean }[]
  form_version: string
  badge: string
  icon: string
  count: number
  attendees: number
}

export interface VisitTopic {
  ref: string
  program_key: string
  name: string
  title: string
  row_label: string
  intro: string
  badge: string
  icon: string
  count: number
  attendees: number
}

export interface Kpis {
  total_events: number
  total_facts: number
  total_attendees: number
  total_trips: number
  total_contests: number
  total_ceremonies: number
  total_prayers: number
  total_honors: number
  total_ashura: number
  active_districts: number
}

export interface EventFact {
  value: number
  value_kind: string
}

export interface PortalEvent {
  event_id: string
  program_code?: string
  program_kinds_json: string
  occurred_on: string
  unit_name: string
  occasion: string
  occasion_class: string | null
  official_present: number | null
  had_reception: number | null
  is_ashura_pilgrimage: number
  notes: string
  attendees_count: number | null
  attendees_value_kind: string | null
  attendees_note: string | null
  media_count: number
  facts: Record<string, EventFact>
}

export interface Mandate {
  mandate_id: string
  program_code: string
  kind: string
  title: string
  number: string
  issued_on: string
  document_ref: string
  notes: string
}

export interface DistrictRow {
  unit_name: string
  total_events: number
  total_attendees: number
  program_variety: number
}

export interface WpPost {
  ID: number
  post_title: string
  post_status: string
  post_date: string
  post_content: string
  categories: string[]
  tags: string[]
}

export interface EntryField {
  n: string
  l: string
  t: 'number' | 'select' | 'text' | 'textarea' | 'occasion_class'
  h?: string
  req?: boolean
  o?: { v: string; m?: string }[]
  cn?: string
  cl?: string
}

export interface EntrySection {
  title: string
  icon: string
  hint: string
  fields: EntryField[]
}

export interface EntryFormSpec {
  name: string
  row_label: string
  intro: string
  sections: EntrySection[]
}

export interface EventFilters {
  program_code?: string
  unit_name?: string
  search?: string
  date_from?: string
  date_to?: string
  value_kind?: string
  min_attendees?: string
  has_media?: string
  occasion_class?: string
  sort?: string
}

async function request<T>(params: Record<string, string>, method: 'GET' | 'POST' = 'GET', body?: FormData, timeoutMs = 25000): Promise<T> {
  const qs = new URLSearchParams(params).toString()
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutMs)
  try {
    const resp = await fetch(`api/index.php${qs ? `?${qs}` : ''}`, {
      method,
      body: method === 'POST' ? (body ?? new FormData()) : undefined,
      signal: controller.signal,
    })
    const json = (await resp.json()) as ApiEnvelope<T>
    if (!json.success) throw new Error(json.message || 'خطای سرویس پرتال')
    return json.data
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') {
      throw new Error('پاسخ سرویس با تأخیر مواجه شد و لغو گردید.')
    }
    throw err
  } finally {
    clearTimeout(timer)
  }
}

export const api = {
  kpis: (range: Range) =>
    request<Kpis>({ action: 'get_kpis', ...rangeIso(range) }),
  sheets: (range: Range) =>
    request<ProgramSheet[]>({ action: 'get_sheets', ...rangeIso(range) }),
  visitTopics: (range: Range) =>
    request<VisitTopic[]>({ action: 'get_visit_topics', ...rangeIso(range) }),
  events: (filters: EventFilters, limit: number, offset: number) => {
    const p: Record<string, string> = { action: 'get_events', limit: String(limit), offset: String(offset) }
    for (const [k, v] of Object.entries(filters)) if (v) p[k] = v
    return request<{ rows: PortalEvent[]; total: number; limit: number; offset: number }>(p)
  },
  eventDetail: (eventId: string) =>
    request<PortalEvent & { media_items: unknown[] }>({ action: 'get_event_detail', event_id: eventId }),
  sheetMeta: (programCode: string) =>
    request<{ program_code: string; title: string; monitoring_criteria: string[]; questions: EntryField[]; mandates: Mandate[] }>(
      { action: 'get_sheet_meta', program_code: programCode },
    ),
  districts: (range: Range, search: string, limit: number, offset: number) => {
    const p: Record<string, string> = { action: 'get_districts', ...rangeIso(range), limit: String(limit), offset: String(offset) }
    if (search) p.search = search
    return request<{ rows: DistrictRow[]; total: number }>(p)
  },
  mandates: (programCode: string, search: string, limit: number, offset: number) => {
    const p: Record<string, string> = { action: 'get_mandates', limit: String(limit), offset: String(offset) }
    if (programCode) p.program_code = programCode
    if (search) p.search = search
    return request<{ rows: Mandate[]; total: number }>(p)
  },
  createMandate: (payload: Record<string, string>) => {
    const fd = new FormData()
    fd.append('action', 'create_mandate')
    for (const [k, v] of Object.entries(payload)) fd.append(k, v)
    return request<{ mandate_id: string }>({}, 'POST', fd, 20000)
  },
  deleteMandate: (mandateId: string) => {
    const fd = new FormData()
    fd.append('action', 'delete_mandate')
    fd.append('mandate_id', mandateId)
    return request<null>({}, 'POST', fd, 20000)
  },
  entryFormSpec: (ref: string) =>
    request<EntryFormSpec>({ action: 'get_entry_form', program: ref, format: 'json' }),
  createEvent: (payload: Record<string, string>, evidence?: File | null) => {
    const fd = new FormData()
    fd.append('action', 'create_event')
    for (const [k, v] of Object.entries(payload)) fd.append(k, v)
    if (evidence) fd.append('evidence_file', evidence)
    return request<{ event_id: string }>({}, 'POST', fd, 30000)
  },
  updateEvent: (eventId: string, payload: Record<string, string>) => {
    const fd = new FormData()
    fd.append('action', 'update_event')
    fd.append('event_id', eventId)
    for (const [k, v] of Object.entries(payload)) fd.append(k, v)
    return request<null>({}, 'POST', fd, 20000)
  },
  triggerExcel: (fromJalali: string, toJalali: string) => {
    const fd = new FormData()
    fd.append('action', 'trigger_excel_export')
    if (fromJalali) fd.append('date_from_jalali', fromJalali)
    if (toJalali) fd.append('date_to_jalali', toJalali)
    return request<{ download_url: string; excel_file: string }>({}, 'POST', fd, 45000)
  },
  wpPosts: (limit: number, offset: number) =>
    request<{ rows: WpPost[] }>({ action: 'get_wp_posts', limit: String(limit), offset: String(offset) }),
  health: () =>
    request<{ health: { python_ready: boolean; sqlite_ready: boolean; excel_ready: boolean; excel_modified: string | null } }>(
      { action: 'get_system_health' },
    ),
  updateWpStatus: (postId: number, status: string) => {
    const fd = new FormData()
    fd.append('action', 'update_wp_post_status')
    fd.append('post_id', String(postId))
    fd.append('status', status)
    return request<null>({}, 'POST', fd, 20000)
  },
}

/** بازهٔ دوره → پارامترهای ISO برای سرور */
export interface Range {
  fromIso: string
  toIso: string
  label: string
}

export function rangeIso(range: Range): Record<string, string> {
  return { date_from: range.fromIso, date_to: range.toIso }
}

export const MANDATE_KINDS: Record<string, string> = {
  circular: 'بخشنامه',
  correspondence: 'مکاتبه',
  law: 'قانون',
  policy: 'سیاست‌نامه',
  transformation_doc: 'سند تحول',
  directive: 'دستورالعمل',
  agreement: 'توافق‌نامه',
  guideline: 'شیوه‌نامه',
  resolution: 'مصوبه',
}

export const PROGRAM_REFS: Record<string, string> = {
  '80401': 'trip',
  '80402': 'contest',
  '80403': 'ceremony',
  '80501': 'prayer',
  '80406': 'honor',
  '80601': 'customer_care',
  '80202': 'charter',
  '80403-A': 'ashura',
  training_courses: 'training_course',
  content_production: 'content_production',
  counseling: 'counseling',
  education_services: 'education_services',
  external_collaboration: 'external_collaboration',
}
