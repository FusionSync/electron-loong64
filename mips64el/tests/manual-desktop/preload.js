'use strict';

const { contextBridge, ipcRenderer } = require('electron');

// Installed only on the fixed local dashboard, never on a remote web page.
contextBridge.exposeInMainWorld('manualDesktop', {
  state: () => ipcRenderer.invoke('manual:state'),
  gpu: () => ipcRenderer.invoke('manual:gpu'),
  openFile: () => ipcRenderer.invoke('manual:open-file'),
  network: url => ipcRenderer.invoke('manual:network', url),
  openWeb: url => ipcRenderer.invoke('manual:open-web', url),
  onLog: callback => {
    if (typeof callback !== 'function') throw new TypeError('callback must be a function');
    const listener = (_event, entry) => callback(entry);
    ipcRenderer.on('manual:log', listener);
    return () => ipcRenderer.removeListener('manual:log', listener);
  },
});
