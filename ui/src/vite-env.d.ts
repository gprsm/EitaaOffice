/// <reference types="vite/client" />

type DesktopApiResult = { status: number; payload: any }
type LoginAppearanceValue = {
  backgroundDataUrl: string | null
  backgroundFile: string | null
  backgroundFileName: string | null
  position: 'center' | 'top' | 'bottom'
  overlay: number
}

interface Window {
  eitaaDesktop: {
    api(method: string, path: string, body?: unknown): Promise<DesktopApiResult>
    openExternal(url: string): Promise<void>
    selectFile(options?: { title?: string; filters?: Array<{ name: string; extensions: string[] }> }): Promise<string | null>
    selectUploadFile(options?: { title?: string; filters?: Array<{ name: string; extensions: string[] }> }): Promise<string | null>
    loginAppearance: {
      get(): Promise<LoginAppearanceValue>
      selectBackground(): Promise<LoginAppearanceValue>
      save(value: Pick<LoginAppearanceValue, 'position' | 'overlay'>): Promise<LoginAppearanceValue>
      clearBackground(): Promise<LoginAppearanceValue>
    }
    openLogs(): Promise<void>
    platform: string
    windowControls: {
      minimize(): Promise<void>
      toggleMaximize(): Promise<boolean>
      close(): Promise<void>
      isMaximized(): Promise<boolean>
      onMaximized(callback: (value: boolean) => void): () => void
    }
  }
}
