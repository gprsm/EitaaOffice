export function createAsyncTaskQueue(maxConcurrent) {
  if (!Number.isInteger(maxConcurrent) || maxConcurrent < 1) {
    throw new RangeError('maxConcurrent must be a positive integer')
  }

  let active = 0
  const pending = []
  let sequence = 0
  let wakeTimer = null

  const pump = () => {
    if (wakeTimer !== null) {
      clearTimeout(wakeTimer)
      wakeTimer = null
    }
    while (active < maxConcurrent && pending.length > 0) {
      const now = Date.now()
      let selectedIndex = -1
      for (let index = 0; index < pending.length; index += 1) {
        const candidate = pending[index]
        if (candidate.notBefore > now) continue
        if (selectedIndex < 0) {
          selectedIndex = index
          continue
        }
        const selected = pending[selectedIndex]
        if (candidate.priority < selected.priority || (
          candidate.priority === selected.priority && candidate.sequence < selected.sequence
        )) selectedIndex = index
      }
      if (selectedIndex < 0) break
      const [entry] = pending.splice(selectedIndex, 1)
      active += 1
      Promise.resolve()
        .then(entry.task)
        .then(entry.resolve, entry.reject)
        .finally(() => {
          active -= 1
          pump()
        })
    }
    if (active < maxConcurrent && pending.length > 0 && wakeTimer === null) {
      const wait = Math.max(0, Math.min(...pending.map(entry => entry.notBefore)) - Date.now())
      wakeTimer = setTimeout(pump, wait)
    }
  }

  return {
    run(task, options = {}) {
      return new Promise((resolve, reject) => {
        pending.push({
          task,
          resolve,
          reject,
          priority: Number.isFinite(options.priority) ? Number(options.priority) : 0,
          key: options.key == null ? null : String(options.key),
          notBefore: Date.now() + Math.max(0, Number(options.delayMs) || 0),
          sequence: sequence++,
        })
        pump()
      })
    },
    promote(key, priority) {
      const selectedKey = String(key)
      let promoted = false
      for (const entry of pending) {
        if (entry.key !== selectedKey) continue
        entry.priority = Math.min(entry.priority, Number(priority))
        entry.notBefore = Math.min(entry.notBefore, Date.now())
        promoted = true
      }
      if (promoted) pump()
      return promoted
    },
  }
}
