const { app, BrowserWindow, ipcMain, dialog } = require('electron');
const path = require('path');
const WebSocket = require('ws');
const Store = require('electron-store'); // For persistent storage

const store = new Store();

let mainWindow;
let wsClient;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    minWidth: 800,
    minHeight: 600,
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false,
      preload: path.join(__dirname, 'preload.js')
    },
    icon: path.join(__dirname, 'assets/icon.png')
  });

  // Load the React app (assuming it's built)
  mainWindow.loadFile('index.html');

  // Open DevTools in development
  if (process.env.NODE_ENV === 'development') {
    mainWindow.webContents.openDevTools();
  }

  // Handle window close
  mainWindow.on('closed', () => {
    if (wsClient) {
      wsClient.close();
    }
  });
}

// Initialize WebSocket connection
function initWebSocket(authToken) {
  if (wsClient) {
    wsClient.close();
  }

  const wsUrl = `ws://localhost:8000/api/ws/chat?token=${authToken}`;
  wsClient = new WebSocket(wsUrl);

  wsClient.on('open', () => {
    console.log('Connected to SupremeAI WebSocket');
    mainWindow.webContents.send('ws-connected');
  });

  wsClient.on('message', (data) => {
    try {
      const message = JSON.parse(data.toString());
      mainWindow.webContents.send('ws-message', message);
    } catch (e) {
      console.error('Error parsing WebSocket message:', e);
    }
  });

  wsClient.on('error', (error) => {
    console.error('WebSocket error:', error);
    mainWindow.webContents.send('ws-error', error.message);
  });

  wsClient.on('close', (code, reason) => {
    console.log(`WebSocket closed: ${code} - ${reason}`);
    mainWindow.webContents.send('ws-disconnected');
  });
}

// Handle app ready
app.whenReady().then(() => {
  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

// Handle app quit
app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

// IPC handlers for communication with renderer
ipcMain.handle('get-auth-token', async () => {
  return store.get('authToken', null);
});

ipcMain.handle('set-auth-token', async (event, token) => {
  store.set('authToken', token);
  return true;
});

ipcMain.handle('connect-websocket', async (event, authToken) => {
  initWebSocket(authToken);
  return true;
});

ipcMain.handle('send-message', async (event, message) => {
  if (wsClient && wsClient.readyState === WebSocket.OPEN) {
    wsClient.send(JSON.stringify(message));
    return true;
  }
  return false;
});

ipcMain.handle('disconnect-websocket', async () => {
  if (wsClient) {
    wsClient.close();
  }
  return true;
});

// Additional IPC handlers for desktop-specific features
ipcMain.handle('show-open-dialog', async (event, options) => {
  return await dialog.showOpenDialog(mainWindow, {
    properties: ['openFile', 'multiSelections'],
    filters: [
      { name: 'All Files', extensions: ['*'] }
    ],
    ...options
  });
});

ipcMain.handle('show-save-dialog', async (event, options) => {
  return await dialog.showSaveDialog(mainWindow, {
    filters: [
      { name: 'All Files', extensions: ['*'] }
    ],
    ...options
  });
});

module.exports = { initWebSocket };
