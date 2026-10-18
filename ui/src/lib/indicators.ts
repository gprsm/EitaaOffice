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
    const res = await fetch('/api/v3/reporting/indicators/macro')
    if (!res.ok) return MACRO_INDICATORS
    const data = await res.json()
    return Array.isArray(data.macro_indicators) ? data.macro_indicators : MACRO_INDICATORS
  } catch {
    return MACRO_INDICATORS
  }
}

export async function fetchMicroIndicators(): Promise<MicroIndicatorItem[]> {
  try {
    const res = await fetch('/api/v3/reporting/indicators/micro')
    if (!res.ok) return []
    const data = await res.json()
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
  const res = await fetch('/api/v3/reporting/indicators/micro', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  const data = await res.json()
  if (!res.ok || !data.ok) {
    throw new Error(data?.error?.message || 'خطا در ثبت شاخصه جزئی')
  }
  return data.indicator
}

export async function updateMicroIndicator(
  indicatorId: string,
  payload: { title?: string; category?: string; color?: string },
): Promise<MicroIndicatorItem> {
  const res = await fetch(`/api/v3/reporting/indicators/micro/${encodeURIComponent(indicatorId)}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  const data = await res.json()
  if (!res.ok || !data.ok) {
    throw new Error(data?.error?.message || 'خطا در ویرایش شاخصه جزئی')
  }
  return data.indicator
}

export async function deleteMicroIndicator(indicatorId: string): Promise<boolean> {
  const res = await fetch(`/api/v3/reporting/indicators/micro/${encodeURIComponent(indicatorId)}`, {
    method: 'DELETE',
  })
  const data = await res.json()
  if (!res.ok || !data.ok) {
    throw new Error(data?.error?.message || 'خطا در حذف شاخصه جزئی')
  }
  return Boolean(data.deleted)
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
    const res = await fetch(url)
    if (!res.ok) return {}
    const data = await res.json()
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
  const res = await fetch('/api/v3/reporting/indicators/messages/assign', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  const data = await res.json()
  if (!res.ok || !data.ok) {
    throw new Error(data?.error?.message || 'خطا در انتساب شاخصه‌ها به پیام')
  }
}

export async function fetchMessageSplits(peerKey: string): Promise<number[]> {
  if (!peerKey) return []
  try {
    const res = await fetch(`/api/v3/reporting/splits?peer_key=${encodeURIComponent(peerKey)}`)
    if (!res.ok) return []
    const data = await res.json()
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
  const res = await fetch('/api/v3/reporting/splits', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  const data = await res.json()
  if (!res.ok || !data.ok) {
    throw new Error(data?.error?.message || 'خطا در ثبت تفکیک پیام')
  }
  return Array.isArray(data.detached_message_ids) ? data.detached_message_ids : []
}
