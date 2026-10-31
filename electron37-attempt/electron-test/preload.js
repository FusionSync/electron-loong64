'use strict';

const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronTest', Object.freeze({
  getSystemInfo: () => ipcRenderer.invoke('system:info'),
  openFile: () => ipcRenderer.invoke('file:open'),
  request: (url) => ipcRenderer.invoke('network:request', url),
  openBilibili: () => ipcRenderer.invoke('shell:open-bilibili'),
}));
