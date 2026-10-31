'use strict';
const { contextBridge } = require('electron');
contextBridge.exposeInMainWorld('runtimeProbe', {
  sandboxed: process.sandboxed,
  contextIsolated: process.contextIsolated,
  type: process.type
});
