const { contextBridge, ipcRenderer } = require('electron')
contextBridge.exposeInMainWorld('eitaaDesktop', {
  api: (method, path, body) => ipcRenderer.invoke('api:request', { method, path, body }),
  openExternal: url => ipcRenderer.invoke('shell:open-external', url),
  selectFile: options => ipcRenderer.invoke('dialog:select-file', options),
  selectUploadFile: options => ipcRenderer.invoke('dialog:select-upload-file', options),
  loginAppearance: {
    get: () => ipcRenderer.invoke('login-appearance:get'),
    selectBackground: () => ipcRenderer.invoke('login-appearance:select-background'),
    save: value => ipcRenderer.invoke('login-appearance:save', value),
    clearBackground: () => ipcRenderer.invoke('login-appearance:clear-background'),
  },
  openLogs: () => ipcRenderer.invoke('shell:open-logs'),
  platform: process.platform,
  windowControls: {
    minimize: () => ipcRenderer.invoke('window:minimize'),
    toggleMaximize: () => ipcRenderer.invoke('window:toggle-maximize'),
    close: () => ipcRenderer.invoke('window:close'),
    isMaximized: () => ipcRenderer.invoke('window:is-maximized'),
    onMaximized: callback => { const listener = (_event, value) => callback(Boolean(value)); ipcRenderer.on('window:maximized', listener); return () => ipcRenderer.removeListener('window:maximized', listener) },
  },
})
