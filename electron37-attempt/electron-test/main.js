'use strict';

const {
  app,
  BrowserWindow,
  dialog,
  ipcMain,
  net,
  shell,
} = require('electron');
const fs = require('node:fs/promises');
const path = require('node:path');

let mainWindow;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1180,
    height: 820,
    minWidth: 900,
    minHeight: 650,
    show: false,
    backgroundColor: '#101827',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
  });

  mainWindow.loadFile(path.join(__dirname, 'test.html'));
  mainWindow.once('ready-to-show', () => mainWindow.show());
}

function assertWebUrl(value) {
  const url = new URL(String(value));
  if (!['http:', 'https:'].includes(url.protocol)) {
    throw new Error('Only http:// and https:// URLs are allowed');
  }
  if (url.username || url.password || url.toString().length > 2048) {
    throw new Error('The URL must not contain credentials and must be at most 2048 characters');
  }
  return url;
}

function requestWithElectronNet(value) {
  const url = assertWebUrl(value);
  return new Promise((resolve, reject) => {
    const started = Date.now();
    const request = net.request({
      method: 'GET',
      url: url.toString(),
    });
    const timeout = setTimeout(() => {
      request.abort();
      reject(new Error('Electron net request timed out after 15 seconds'));
    }, 15000);
    const clearTimeoutIfDone = () => clearTimeout(timeout);
    request.setHeader('User-Agent', 'Electron37-Loong64-Functional-Test/1.0');
    request.on('response', (response) => {
      const chunks = [];
      let total = 0;
      response.on('data', (chunk) => {
        total += chunk.length;
        if (Buffer.concat(chunks).length < 8192) chunks.push(chunk);
      });
      response.on('end', () => {
        clearTimeoutIfDone();
        const body = Buffer.concat(chunks).toString('utf8').slice(0, 4000);
        resolve({
          url: url.toString(),
          statusCode: response.statusCode,
          statusMessage: response.statusMessage,
          headers: response.headers,
          bytesReceived: total,
          elapsedMs: Date.now() - started,
          body,
        });
      });
      response.on('error', (error) => {
        clearTimeoutIfDone();
        reject(error);
      });
    });
    request.on('error', (error) => {
      clearTimeoutIfDone();
      reject(error);
    });
    request.end();
  });
}

ipcMain.handle('system:info', () => ({
  arch: process.arch,
  platform: process.platform,
  versions: process.versions,
  electronPath: process.execPath,
  home: app.getPath('home'),
  display: process.env.DISPLAY || '(unset)',
}));

ipcMain.handle('file:open', async () => {
  const result = await dialog.showOpenDialog(mainWindow, {
    title: '选择一个文件进行读取测试',
    defaultPath: app.getPath('home'),
    properties: ['openFile'],
  });
  if (result.canceled || result.filePaths.length === 0) {
    return { canceled: true };
  }
  const filePath = result.filePaths[0];
  const stat = await fs.stat(filePath);
  const content = await fs.readFile(filePath);
  return {
    canceled: false,
    path: filePath,
    size: stat.size,
    mode: stat.mode.toString(8),
    preview: content.toString('utf8', 0, Math.min(content.length, 4096)),
  };
});

ipcMain.handle('network:request', async (_event, value) => {
  try {
    return { ok: true, ...(await requestWithElectronNet(value)) };
  } catch (error) {
    return {
      ok: false,
      error: error && error.stack ? error.stack : String(error),
    };
  }
});

ipcMain.handle('shell:open-bilibili', async () => {
  const url = 'https://www.bilibili.com/';
  await shell.openExternal(url);
  return { ok: true, url };
});

app.whenReady().then(() => {
  createWindow();
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});
