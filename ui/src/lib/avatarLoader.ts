import { api, getClientStoragePrefix } from './api'
import { createAsyncTaskQueue } from './avatarQueue.mjs'

type AvatarCacheEntry = { value: string | null; expiresAt: number }

const avatarCache = new Map<string, AvatarCacheEntry>()
const avatarRequests = new Map<string, Promise<string | null>>()
const POSITIVE_TTL_MS = 60 * 60 * 1000
const NEGATIVE_TTL_MS = 2 * 60 * 1000
const FAILURE_TTL_MS = 15 * 1000

// Cached-only requests never open the provider bridge, so they can progress in
// parallel. Remote avatar work remains serialized because the Eitaa session is
// shared and must not execute overlapping provider operations.
const avatarCacheQueue = createAsyncTaskQueue(6)
const avatarRemoteQueue = createAsyncTaskQueue(1)

const scopedKeyFor = (storageScope: string, siteKey: string, peerKey: string) => `${storageScope}:${siteKey}:${peerKey}`
const keyFor = (siteKey: string, peerKey: string) => scopedKeyFor(getClientStoragePrefix(), siteKey, peerKey)

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
  const requestStorageScope = getClientStoragePrefix()
  const key = scopedKeyFor(requestStorageScope, siteKey, peerKey)
  const cached = peekDialogAvatar(siteKey, peerKey)
  if (cached !== undefined) return Promise.resolve(cached)
  const running = avatarRequests.get(key)
  if (running) return running
  
  const request = (async () => {
    try {
      const cachedResponse = await avatarCacheQueue.run(async () => {
        if (requestStorageScope !== getClientStoragePrefix()) return null
        return api<{ data_url?: string; avatar_present?: boolean }>('POST', '/api/v1/dialogs/avatar', {
          site_key: siteKey,
          peer_key: peerKey,
          cached_only: true,
        })
      })
      if (requestStorageScope !== getClientStoragePrefix()) return null
      if (cachedResponse?.avatar_present && cachedResponse.data_url) {
        avatarCache.set(key, { value: cachedResponse.data_url, expiresAt: Date.now() + POSITIVE_TTL_MS })
        return cachedResponse.data_url
      }

      const response = await avatarRemoteQueue.run(async () => {
        if (requestStorageScope !== getClientStoragePrefix()) return null
        return api<{ data_url?: string; avatar_present?: boolean }>('POST', '/api/v1/dialogs/avatar', {
        site_key: siteKey,
        peer_key: peerKey,
        cached_only: false,
      })
      })
      if (requestStorageScope !== getClientStoragePrefix()) return null
      const value = response?.avatar_present && response.data_url ? response.data_url : null
      avatarCache.set(key, { value, expiresAt: Date.now() + (value ? POSITIVE_TTL_MS : NEGATIVE_TTL_MS) })
      return value
    } catch {
      // Avatar failures are presentation-only. Cache them briefly and resolve
      // independently so no rejected task can disrupt the rest of the UI.
      if (requestStorageScope === getClientStoragePrefix()) {
        avatarCache.set(key, { value: null, expiresAt: Date.now() + FAILURE_TTL_MS })
      }
      return null
    }
  })().finally(() => avatarRequests.delete(key))
  
  avatarRequests.set(key, request)
  return request
}

export function clearDialogAvatarCache(siteKey?: string, peerKey?: string) {
  if (siteKey && peerKey) {
    avatarCache.delete(keyFor(siteKey, peerKey))
    return
  }
  if (siteKey) {
    const prefix = `${getClientStoragePrefix()}:${siteKey}:`
    for (const key of avatarCache.keys()) if (key.startsWith(prefix)) avatarCache.delete(key)
    return
  }
  avatarCache.clear()
}
