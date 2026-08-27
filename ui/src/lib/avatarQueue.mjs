export function createAsyncTaskQueue(maxConcurrent) {
  if (!Number.isInteger(maxConcurrent) || maxConcurrent < 1) {
    throw new RangeError('maxConcurrent must be a positive integer')
  }

  let active = 0
  const pending = []

  const pump = () => {
    while (active < maxConcurrent && pending.length > 0) {
      const entry = pending.shift()
      active += 1
      Promise.resolve()
        .then(entry.task)
        .then(entry.resolve, entry.reject)
        .finally(() => {
          active -= 1
          pump()
        })
    }
  }

  return {
    run(task) {
      return new Promise((resolve, reject) => {
        pending.push({ task, resolve, reject })
        pump()
      })
    },
  }
}
