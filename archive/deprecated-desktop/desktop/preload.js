const { contextBridge, ipcRenderer } = require('electron');

// Expose protected methods that allow the renderer process to use
// the ipcRenderer without exposing the entire object
contextBridge.exposeInMainWorld('electronAPI', {
  // Auth token management
  getAuthToken: () => ipcRenderer.invoke('get-auth-token'),
  setAuthToken: (token) => ipcRenderer.invoke('set-auth-token', token),

  // WebSocket communication
  connectWebSocket: (authToken) => ipcRenderer.invoke('connect-websocket', authToken),
  sendMessage: (message) => ipcRenderer.invoke('send-message', message),
  disconnectWebSocket: () => ipcRenderer.invoke('disconnect-websocket'),

  // Dialogs
  showOpenDialog: (options) => ipcRenderer.invoke('show-open-dialog', options),
  showSaveDialog: (options) => ipcRenderer.invoke('show-save-dialog', options),

  // WebSocket event listeners
  onWsConnected: (callback) => ipcRenderer.on('ws-connected', callback),
  onWsMessage: (callback) => ipcRenderer.on('ws-message', callback),
  onWsError: (callback) => ipcRenderer.on('ws-error', callback),
  onWsDisconnected: (callback) => ipcRenderer.on('ws-disconnected', callback),

  // Remove listeners
  removeWsConnectedListener: () => ipcRenderer.removeAllListeners('ws-connected'),
  removeWsMessageListener: () => ipcRenderer.removeAllListeners('ws-message'),
  removeWsErrorListener: () => ipcRenderer.removeAllListeners('ws-error'),
  removeWsDisconnectedListener: () => ipcRenderer.removeAllListeners('ws-disconnected'),
});
