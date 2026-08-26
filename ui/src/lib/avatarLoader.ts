import { api, getClientStoragePrefix } from './api'

type AvatarCacheEntry = { value: string | null; expiresAt: number }

const avatarCache = new Map<string, AvatarCacheEntry>()
const avatarRequests = new Map<string, Promise<string | null>>()
const POSITIVE_TTL_MS = 60 * 60 * 1000
const NEGATIVE_TTL_MS = 2 * 60 * 1000

const MAX_CONCURRENT_REQUESTS = 3
let activeRequestCount = 0
const requestQueue: (() => void)[] = []

function pumpQueue() {
  if (activeRequestCount >= MAX_CONCURRENT_REQUESTS || requestQueue.length === 0) return
  activeRequestCount++
  const task = requestQueue.shift()
  if (task) task()
}

const keyFor = (siteKey: string, peerKey: string) => `${getClientStoragePrefix()}:${siteKey}:${peerKey}`

export function peekDialogAvatar(siteKey: string, peerKey: string): string | null | undefined {
  const entry = avatarCache.get(keyFor(siteKey, peerKey))
  if (!entry) return undefined
  if (entry.expiresAt <= Date.now()) {
    avatarCache.delete(keyFor(siteKey, peerKey))
    return undefined
  }
  return entry.value
}

export function loadDialogAvatar(siteKey: string, peerKey: string): Promise<string | null> {
  const key = keyFor(siteKey, peerKey)
  const cached = peekDialogAvatar(siteKey, peerKey)
  if (cached !== undefined) return Promise.resolve(cached)
  const running = avatarRequests.get(key)
  if (running) return running
  
  const request = new Promise<string | null>((resolve, reject) => {
    requestQueue.push(() => {
      api<{ data_url?: string; avatar_present?: boolean }>('POST', '/api/v1/dialogs/avatar', {
        site_key: siteKey,
        peer_key: peerKey,
        cached_only: false,
      }).then(response => {
        const value = response.avatar_present && response.data_url ? response.data_url : null
        avatarCache.set(key, { value, expiresAt: Date.now() + (value ? POSITIVE_TTL_MS : NEGATIVE_TTL_MS) })
        resolve(value)
      }).catch(reject).finally(() => {
        activeRequestCount--
        pumpQueue()
      })
    })
    pumpQueue()
  }).finally(() => avatarRequests.delete(key))
  
  avatarRequests.set(key, request)
  return request
}

export function clearDialogAvatarCache(siteKey?: string, peerKey?: string) {
  if (siteKey && peerKey) {
    avatarCache.delete(keyFor(siteKey, peerKey))
    return
  }
  if (siteKey) {
    for (const key of avatarCache.keys()) if (key.startsWith(`${siteKey}:`)) avatarCache.delete(key)
    return
  }
  avatarCache.clear()
}
