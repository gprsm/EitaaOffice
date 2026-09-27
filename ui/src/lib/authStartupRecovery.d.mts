export type AuthStartupFailure = {
  code: string
  message: string
  retryable: boolean
}

export function authStartupFailure(error: unknown): AuthStartupFailure
export function authStartupRetryDelay(error: unknown, failedAttempt: number): number | null
export function shouldRefreshAppAuthAfterError(path: string, code: string): boolean
