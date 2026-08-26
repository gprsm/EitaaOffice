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
    api(method: string, path: string, body?: unknown, csrfToken?: string, messengerAccountId?: string, correlationId?: string): Promise<DesktopApiResult>
    reportDiagnostic(payload: ClientDiagnosticPayload, correlationId?: string): Promise<boolean>
    openExternal(url: string): Promise<void>
    selectFile(options?: { title?: string; filters?: Array<{ name: string; extensions: string[] }> }): Promise<string | null>
    selectUploadFile(options?: { title?: string; filters?: Array<{ name: string; extensions: string[] }>; messengerAccountId?: string }): Promise<string | null>
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

type ClientDiagnosticPayload = {
  event: 'renderer_render_error' | 'renderer_unhandled_error' | 'renderer_unhandled_rejection'
  level: 'warning' | 'error'
  error_type: string
  safe_context: {
    component_stack_present: boolean
    document_visible: boolean
    online: boolean
    surface: 'renderer' | 'browser'
  }
}
