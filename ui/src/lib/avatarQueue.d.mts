export type AsyncTaskQueue = {
  run<T>(task: () => T | Promise<T>): Promise<T>
}

export function createAsyncTaskQueue(maxConcurrent: number): AsyncTaskQueue
