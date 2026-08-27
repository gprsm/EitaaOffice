export type AsyncTaskQueue = {
  run<T>(task: () => T | Promise<T>, options?: {
    priority?: number
    key?: string
    delayMs?: number
  }): Promise<T>
  promote(key: string, priority: number): boolean
}

export function createAsyncTaskQueue(maxConcurrent: number): AsyncTaskQueue
