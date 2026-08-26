(() => {
  'use strict'

  const STORAGE_USAGE = 'eitaa-bridge.ui.confirmed-wordpress-usage.v1'
  const STORAGE_POSITIONS = 'eitaa-bridge.ui.reading-positions.v1'
  const STORAGE_ACTIVE_PEER = 'eitaa-bridge.ui.peer-key'
  const MAX_USAGE = 2000
  const MAX_POSITIONS = 120
  const SAVE_DELAY_MS = 2500
  const STORAGE_SCOPE_EVENT = 'eitaa-bridge:client-storage-scope-changed'
  let storagePrefix = String(document.documentElement.dataset.clientStorageScope || '')
  const scopedKey = key => storagePrefix ? `${key}.${storagePrefix}` : key

  const readJson = (key, fallback) => {
    try {
      const raw = localStorage.getItem(scopedKey(key))
      return raw ? JSON.parse(raw) : fallback
    } catch {
      return fallback
    }
  }
  const writeJson = (key, value) => {
    try { localStorage.setItem(scopedKey(key), JSON.stringify(value)) } catch { /* best effort */ }
  }
  const sourceMessageId = key => {
    const parts = String(key || '').split(':')
    const value = Number(parts.at(-1))
    return Number.isFinite(value) ? value : null
  }
  const trimByTime = (records, maximum) => Object.fromEntries(
    Object.entries(records)
      .sort((left, right) => Number(right[1]?.updated_at || right[1]?.savedAt || 0) - Number(left[1]?.updated_at || left[1]?.savedAt || 0))
      .slice(0, maximum),
  )

  let usageRecords = readJson(STORAGE_USAGE, {})
  let readingPositions = readJson(STORAGE_POSITIONS, {})
  const dialogsByPeer = new Map()
  const peerByFile = new Map()
  let saveTimer = 0
  let activePeer = ''
  let activeScroll = null
  let activeScrollCleanup = null
  let restoreGeneration = 0
  let userInterruptedRestore = false
  let suppressCheckpointUntil = 0

  const persistUsage = () => {
    usageRecords = trimByTime(usageRecords, MAX_USAGE)
    writeJson(STORAGE_USAGE, usageRecords)
  }
  const persistPositions = () => {
    readingPositions = trimByTime(readingPositions, MAX_POSITIONS)
    writeJson(STORAGE_POSITIONS, readingPositions)
  }
  const schedulePositionSave = () => {
    if (saveTimer) return
    saveTimer = window.setTimeout(() => {
      saveTimer = 0
      const run = () => persistPositions()
      if ('requestIdleCallback' in window) window.requestIdleCallback(run, { timeout: 1200 })
      else window.setTimeout(run, 0)
    }, SAVE_DELAY_MS)
  }

  const normalizeUsage = (existing, record) => {
    const composition = {
      composition_key: record.composition_key,
      post_id: record.post_id,
      post_url: record.post_url || null,
      status: record.status || 'draft',
      title: record.title || '',
      updated_at: new Date(Number(record.updated_at || Date.now())).toISOString(),
    }
    const compositions = [
      composition,
      ...((existing?.compositions || []).filter(item => item.composition_key !== composition.composition_key)),
    ]
    return {
      ...(existing || {}),
      used: true,
      usage_state: 'used',
      stale: false,
      publication_status: 'published',
      external_post_id: String(record.post_id),
      external_url: record.post_url || null,
      compositions,
    }
  }

  const rememberConfirmedSources = payload => {
    const keys = Array.isArray(payload?.confirmed_source_keys)
      ? payload.confirmed_source_keys.map(String)
      : Array.isArray(payload?.record?.source_keys) ? payload.record.source_keys.map(String) : []
    const postId = Number(payload?.post?.id || payload?.record?.post_id || 0)
    if (!keys.length || postId <= 0) return
    const record = {
      composition_key: String(payload?.record?.composition_key || ''),
      post_id: postId,
      post_url: payload?.post?.link || payload?.record?.post_url || null,
      status: String(payload?.post?.status || payload?.record?.status || 'draft'),
      title: String(payload?.record?.title || ''),
      updated_at: Date.now(),
    }
    for (const key of keys) usageRecords[key] = record
    persistUsage()
    window.dispatchEvent(new CustomEvent('eitaa-bridge:usage-confirmed', { detail: { keys, record } }))
  }

  const applyUsageToMessages = (payload, requestPeerFile) => {
    if (!Array.isArray(payload?.messages)) return payload
    const peer = payload.peer || peerByFile.get(requestPeerFile || '')
    const peerKey = peer?.peer_key || (peer?.type && peer?.id != null ? `${peer.type}:${peer.id}` : null)
    if (!peerKey) return payload
    payload.messages = payload.messages.map(message => {
      const key = `${peerKey}:${message.id}`
      const record = usageRecords[key]
      return record ? { ...message, usage: normalizeUsage(message.usage, record) } : message
    })
    return payload
  }

  const updateDialogMaps = payload => {
    if (!Array.isArray(payload?.dialogs)) return
    for (const dialog of payload.dialogs) {
      if (!dialog?.peer_key) continue
      dialogsByPeer.set(dialog.peer_key, dialog)
      if (dialog.peer_file) peerByFile.set(dialog.peer_file, dialog)
    }
  }

  const originalFetch = window.fetch.bind(window)
  window.fetch = async (input, init) => {
    let nextInput = input
    let nextInit = init
    let path = ''
    try {
      const rawUrl = typeof input === 'string' ? input : input.url
      path = new URL(rawUrl, window.location.href).pathname
      if (path === '/api/v1/messages/list' && typeof init?.body === 'string') {
        const body = JSON.parse(init.body)
        const dialog = peerByFile.get(body.peer_file)
        const checkpoint = dialog && Number(dialog.unread_count || 0) <= 0 ? readingPositions[dialog.peer_key] : null
        if (!body.before_id && !body.date_from && checkpoint?.lastVisibleId) {
          body.before_id = Number(checkpoint.lastVisibleId) + 1
          body.limit = Math.max(Number(body.limit || 0), 120)
          nextInit = { ...init, body: JSON.stringify(body) }
        }
      }
    } catch { /* preserve original request */ }

    const response = await originalFetch(nextInput, nextInit)
    if (!response.ok || response.status === 204) return response
    if (![
      '/api/v1/dialogs/list',
      '/api/v1/messages/list',
      '/api/v1/compositions/publish',
      '/api/v1/compositions/update',
    ].includes(path)) return response

    try {
      const payload = await response.clone().json()
      let requestPeerFile = ''
      if (typeof nextInit?.body === 'string') {
        try { requestPeerFile = JSON.parse(nextInit.body).peer_file || '' } catch { /* ignore */ }
      }
      if (path === '/api/v1/dialogs/list') updateDialogMaps(payload)
      if (path === '/api/v1/messages/list') applyUsageToMessages(payload, requestPeerFile)
      if (path === '/api/v1/compositions/publish' || path === '/api/v1/compositions/update') rememberConfirmedSources(payload)
      const headers = new Headers(response.headers)
      headers.set('content-type', 'application/json; charset=utf-8')
      return new Response(JSON.stringify(payload), {
        status: response.status,
        statusText: response.statusText,
        headers,
      })
    } catch {
      return response
    }
  }

  const rowForKey = key => document.querySelector(`.virtual-row[data-message-key="${CSS.escape(String(key))}"]`)
  const scrollContainer = () => document.querySelector('.message-scroll')
  const currentPeer = () => {
    try { return JSON.parse(localStorage.getItem(scopedKey(STORAGE_ACTIVE_PEER)) || '""') || '' } catch { return '' }
  }

  window.addEventListener(STORAGE_SCOPE_EVENT, event => {
    storagePrefix = String(event?.detail?.storagePrefix || '')
    usageRecords = readJson(STORAGE_USAGE, {})
    readingPositions = readJson(STORAGE_POSITIONS, {})
    dialogsByPeer.clear()
    peerByFile.clear()
    activePeer = ''
    restoreGeneration += 1
  })

  const styleConfirmedRows = () => {
    for (const row of document.querySelectorAll('.virtual-row[data-message-key]')) {
      const key = row.dataset.messageKey
      const record = usageRecords[key]
      if (!record) continue
      const card = row.querySelector('.message-card')
      if (!card || card.classList.contains('used')) continue
      card.classList.add('used', 'ui33-confirmed-fallback')
      card.setAttribute('title', `این پیام در نوشته WordPress #${record.post_id} استفاده شده است.`)
      card.querySelector('.select-hover')?.remove()
      if (!card.querySelector('.usage-badge')) {
        const footer = card.querySelector('.message-footer')
        if (footer) {
          const badge = document.createElement('span')
          badge.className = 'usage-badge badge ui33-usage-badge'
          badge.textContent = 'وردپرس'
          footer.appendChild(badge)
        }
      }
    }
  }

  document.addEventListener('click', event => {
    const row = event.target instanceof Element ? event.target.closest('.virtual-row[data-message-key]') : null
    const card = row?.querySelector('.message-card.ui33-confirmed-fallback')
    if (!row || !card || !usageRecords[row.dataset.messageKey]) return
    event.preventDefault()
    event.stopImmediatePropagation()
  }, true)
  document.addEventListener('contextmenu', event => {
    const row = event.target instanceof Element ? event.target.closest('.virtual-row[data-message-key]') : null
    if (!row || !usageRecords[row.dataset.messageKey]) return
    event.preventDefault()
    event.stopImmediatePropagation()
  }, true)

  const visibleRows = scroll => {
    const viewport = scroll.getBoundingClientRect()
    return [...scroll.querySelectorAll('.virtual-row[data-message-key]')]
      .map(row => ({ row, rect: row.getBoundingClientRect() }))
      .filter(item => item.rect.bottom > viewport.top + 1 && item.rect.top < viewport.bottom - 1)
      .sort((a, b) => a.rect.top - b.rect.top)
  }

  const saveCheckpoint = () => {
    if (!activePeer || !activeScroll || Date.now() < suppressCheckpointUntil) return
    const visible = visibleRows(activeScroll)
    if (!visible.length) return
    const first = visible[0]
    const last = visible.at(-1)
    const firstKey = first.row.dataset.messageKey
    const lastKey = last.row.dataset.messageKey
    const viewport = activeScroll.getBoundingClientRect()
    readingPositions[activePeer] = {
      anchorKey: firstKey,
      anchorOffset: first.rect.top - viewport.top,
      scrollTop: activeScroll.scrollTop,
      nearBottom: activeScroll.scrollHeight - activeScroll.scrollTop - activeScroll.clientHeight <= 180,
      firstVisibleId: sourceMessageId(firstKey),
      lastVisibleId: sourceMessageId(lastKey),
      savedAt: Date.now(),
    }
    schedulePositionSave()
  }

  const bindScroll = scroll => {
    if (activeScroll === scroll) return
    activeScrollCleanup?.()
    activeScroll = scroll
    if (!scroll) return
    const onScroll = () => saveCheckpoint()
    const interrupt = () => { userInterruptedRestore = true }
    scroll.addEventListener('scroll', onScroll, { passive: true })
    scroll.addEventListener('wheel', interrupt, { passive: true })
    scroll.addEventListener('touchstart', interrupt, { passive: true })
    scroll.addEventListener('pointerdown', interrupt, { passive: true })
    activeScrollCleanup = () => {
      scroll.removeEventListener('scroll', onScroll)
      scroll.removeEventListener('wheel', interrupt)
      scroll.removeEventListener('touchstart', interrupt)
      scroll.removeEventListener('pointerdown', interrupt)
    }
  }

  const scrollRowToOffset = (scroll, row, offset) => {
    const viewport = scroll.getBoundingClientRect()
    const current = row.getBoundingClientRect().top - viewport.top
    suppressCheckpointUntil = Date.now() + 700
    scroll.scrollTop += current - offset
  }

  const installReadingMarker = (peerKey, checkpoint) => {
    document.querySelector('.ui33-reading-marker')?.remove()
    const dialog = dialogsByPeer.get(peerKey)
    if (!checkpoint || Number(dialog?.unread_count || 0) <= 0) return
    const overlays = document.querySelector('.message-scroll-overlays')
    if (!overlays) return
    const button = document.createElement('button')
    button.type = 'button'
    button.className = 'ui33-reading-marker'
    button.textContent = 'ادامه از آخرین موقعیت'
    button.addEventListener('click', event => {
      event.preventDefault()
      event.stopPropagation()
      const scroll = scrollContainer()
      const row = rowForKey(checkpoint.anchorKey)
      if (scroll && row) scrollRowToOffset(scroll, row, Number(checkpoint.anchorOffset || 0))
    })
    overlays.appendChild(button)
  }

  const restoreActivePeer = peerKey => {
    const generation = ++restoreGeneration
    userInterruptedRestore = false
    const checkpoint = readingPositions[peerKey]
    const dialog = dialogsByPeer.get(peerKey)
    installReadingMarker(peerKey, checkpoint)
    let attempts = 0
    const attempt = () => {
      if (generation !== restoreGeneration || userInterruptedRestore || currentPeer() !== peerKey) return
      attempts += 1
      const scroll = scrollContainer()
      bindScroll(scroll)
      if (!scroll) {
        if (attempts < 40) window.setTimeout(attempt, 150)
        return
      }
      const unread = scroll.querySelector('.unread-separator')
      if (Number(dialog?.unread_count || 0) > 0 && unread) {
        const row = unread.closest('.virtual-row')
        if (row) {
          scrollRowToOffset(scroll, row, 18)
          installReadingMarker(peerKey, checkpoint)
          return
        }
      }
      if (Number(dialog?.unread_count || 0) <= 0 && checkpoint?.anchorKey) {
        const row = rowForKey(checkpoint.anchorKey)
        if (row) {
          scrollRowToOffset(scroll, row, Number(checkpoint.anchorOffset || 0))
          return
        }
      }
      if (attempts < 40) window.setTimeout(attempt, 150)
    }
    window.setTimeout(attempt, 0)
  }

  const observer = new MutationObserver(() => {
    styleConfirmedRows()
    bindScroll(scrollContainer())
    const peer = currentPeer()
    if (peer && peer !== activePeer) {
      activePeer = peer
      restoreActivePeer(peer)
    }
  })
  observer.observe(document.documentElement, { childList: true, subtree: true })

  window.addEventListener('eitaa-bridge:usage-confirmed', () => {
    window.requestAnimationFrame(styleConfirmedRows)
  })
  window.addEventListener('beforeunload', () => {
    saveCheckpoint()
    persistPositions()
    persistUsage()
  })

  const style = document.createElement('style')
  style.textContent = `
    .ui33-reading-marker {
      pointer-events: auto; position: absolute; top: 78px; right: 16px; z-index: 10;
      border: 1px solid rgba(20,91,68,.45); background: rgba(238,250,245,.97);
      color: #145b44; border-radius: 999px; padding: 7px 12px; font: inherit;
      font-size: 12px; cursor: pointer; box-shadow: 0 4px 14px rgba(20,62,49,.14);
    }
    .ui33-reading-marker:hover { background: #dff5ec; }
    .message-card.ui33-confirmed-fallback { border-color: #b4232f !important; box-shadow: inset 0 0 0 1px #b4232f !important; }
    .ui33-usage-badge { background: #b4232f; color: #fff; }
    @media (max-width: 700px) { .ui33-reading-marker { top: 72px; right: 8px; max-width: calc(100% - 16px); } }
  `
  document.head.appendChild(style)

  window.setInterval(() => {
    const peer = currentPeer()
    if (peer && peer !== activePeer) {
      activePeer = peer
      restoreActivePeer(peer)
    }
    styleConfirmedRows()
  }, 500)
})()
