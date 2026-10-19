import { api } from './api'

export const MACRO_INDICATORS: string[] = [
  'برگزاری مراسم در مناسبت‌های ملی، مذهبی و انقلابی',
  'ترویج و توسعه فرهنگ اقامه نماز',
  'تکریم و تجلیل از همکاران و خانواده',
  'برگزاری مسابقات استانی فرهنگی، قرآنی و ورزشی',
  'برگزاری اردوهای فرهنگی زیارتی برای کارکنان و خانواده',
  'تشویق کارمندان و تکریم ارباب رجوع',
  'اجرای منشور اخلاقی و رفتار حرفه‌ای',
  'دوره‌های آموزشی، توانمندسازی و تولیدات فرهنگی',
  'غیر برنامه‌ای',
]

export type ProgramCatalogItem = {
  program_code: string
  title: string
  canonical_macro: string
  kind: string
  workbook_sheet: string
  valid_from_year: number
  valid_to_year: number | null
  is_active: number | boolean
  display_order: number
  description: string
  created_at?: string
  updated_at?: string
}

export type MicroIndicatorItem = {
  indicator_id: string
  title: string
  category: string
  color: string
  usage_count: number
  created_at: string
  updated_at: string
}

export type MessageIndicatorData = {
  macro_indicator: string
  micro_indicators: string[]
  updated_at?: string
  updated_by?: string
}

export async function fetchMacroIndicators(): Promise<string[]> {
  try {
    const data = await api<{ ok: boolean; macro_indicators: string[] }>(
      'GET',
      '/api/v3/reporting/indicators/macro',
    )
    return Array.isArray(data.macro_indicators) ? data.macro_indicators : MACRO_INDICATORS
  } catch {
    return MACRO_INDICATORS
  }
}

export async function fetchProgramCatalog(params?: {
  year?: number
  include_inactive?: boolean
}): Promise<ProgramCatalogItem[]> {
  try {
    const qs = new URLSearchParams()
    if (params?.year) qs.set('year', String(params.year))
    if (params?.include_inactive) qs.set('include_inactive', '1')
    const queryStr = qs.toString() ? `?${qs.toString()}` : ''
    const data = await api<{ ok: boolean; programs: ProgramCatalogItem[] }>(
      'GET',
      `/api/v3/reporting/catalog/programs${queryStr}`,
    )
    return Array.isArray(data.programs) ? data.programs : []
  } catch {
    return []
  }
}

export async function saveProgramCatalogItem(
  payload: Partial<ProgramCatalogItem>,
): Promise<ProgramCatalogItem> {
  const data = await api<{ ok: boolean; program: ProgramCatalogItem }>(
    'POST',
    '/api/v3/reporting/catalog/programs',
    payload,
  )
  return data.program
}

export async function toggleProgramActive(
  program_code: string,
  is_active: boolean,
): Promise<ProgramCatalogItem> {
  const data = await api<{ ok: boolean; program: ProgramCatalogItem }>(
    'POST',
    '/api/v3/reporting/catalog/programs/toggle-active',
    { program_code, is_active },
  )
  return data.program
}

export async function fetchMicroIndicators(): Promise<MicroIndicatorItem[]> {
  try {
    const data = await api<{ ok: boolean; micro_indicators: MicroIndicatorItem[] }>(
      'GET',
      '/api/v3/reporting/indicators/micro',
    )
    return Array.isArray(data.micro_indicators) ? data.micro_indicators : []
  } catch {
    return []
  }
}

export async function saveMicroIndicator(payload: {
  title: string
  category?: string
  color?: string
}): Promise<MicroIndicatorItem> {
  const data = await api<{ ok: boolean; indicator: MicroIndicatorItem }>(
    'POST',
    '/api/v3/reporting/indicators/micro',
    payload,
  )
  return data.indicator
}

export async function updateMicroIndicator(
  indicatorId: string,
  payload: { title?: string; category?: string; color?: string },
): Promise<MicroIndicatorItem> {
  const data = await api<{ ok: boolean; indicator: MicroIndicatorItem }>(
    'PUT',
    `/api/v3/reporting/indicators/micro/${encodeURIComponent(indicatorId)}`,
    payload,
  )
  return data.indicator
}

export async function deleteMicroIndicator(indicatorId: string): Promise<boolean> {
  try {
    const data = await api<{ ok: boolean; deleted: boolean }>(
      'DELETE',
      `/api/v3/reporting/indicators/micro/${encodeURIComponent(indicatorId)}`,
    )
    return Boolean(data.deleted)
  } catch {
    const data = await api<{ ok: boolean; deleted: boolean }>(
      'POST',
      `/api/v3/reporting/indicators/micro/${encodeURIComponent(indicatorId)}/delete`,
      {},
    )
    return Boolean(data.deleted)
  }
}

export async function fetchMessageIndicators(
  peerKey: string,
  messageIds?: number[],
): Promise<Record<string, MessageIndicatorData>> {
  if (!peerKey) return {}
  try {
    let url = `/api/v3/reporting/indicators/messages?peer_key=${encodeURIComponent(peerKey)}`
    if (messageIds && messageIds.length > 0) {
      url += `&message_ids=${encodeURIComponent(messageIds.join(','))}`
    }
    const data = await api<{ ok: boolean; indicators: Record<string, MessageIndicatorData> }>(
      'GET',
      url,
    )
    return data.indicators || {}
  } catch {
    return {}
  }
}

export async function assignMessageIndicators(payload: {
  peer_key: string
  message_ids: number[]
  macro_indicator: string
  micro_indicators: string[]
}): Promise<void> {
  await api<{ ok: boolean }>(
    'POST',
    '/api/v3/reporting/indicators/messages/assign',
    payload,
  )
}

export async function fetchMessageSplits(peerKey: string): Promise<number[]> {
  if (!peerKey) return []
  try {
    const data = await api<{ ok: boolean; detached_message_ids: number[] }>(
      'GET',
      `/api/v3/reporting/splits?peer_key=${encodeURIComponent(peerKey)}`,
    )
    return Array.isArray(data.detached_message_ids) ? data.detached_message_ids : []
  } catch {
    return []
  }
}

export async function saveMessageSplits(payload: {
  peer_key: string
  detached_ids?: number[]
  unified_ids?: number[]
}): Promise<number[]> {
  const data = await api<{ ok: boolean; detached_message_ids: number[] }>(
    'POST',
    '/api/v3/reporting/splits',
    payload,
  )
  return Array.isArray(data.detached_message_ids) ? data.detached_message_ids : []
}
