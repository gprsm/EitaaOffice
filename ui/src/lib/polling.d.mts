export type PollingEnvironment = {
  visible?: boolean
  online?: boolean
  mobile?: boolean
  saveData?: boolean
  active?: boolean
}

export function adaptivePollDelay(attempt?: number, environment?: PollingEnvironment): number
export function currentPollingEnvironment(): PollingEnvironment
export function waitForAdaptivePoll(attempt?: number, options?: { active?: boolean }): Promise<void>

declare global {
  interface NetworkInformation { saveData?: boolean }
  interface Navigator { connection?: NetworkInformation }
}
