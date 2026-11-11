'use strict';

const { app, BrowserWindow, Menu, dialog, ipcMain, net, session } = require('electron');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { pathToFileURL } = require('node:url');

const software = process.argv.includes('--software-rendering');
if (software) app.disableHardwareAcceleration();
app.setName('electron-mips64el-manual-desktop');
app.setPath('userData', path.join(app.getPath('appData'), 'electron-mips64el-manual-desktop'));

const logDirectory = path.join(app.getPath('userData'), 'logs');
fs.mkdirSync(logDirectory, { recursive: true });
const logPath = path.join(logDirectory, `desktop-${new Date().toISOString().replace(/[:.]/g, '-')}.jsonl`);
const dashboardURL = pathToFileURL(path.join(__dirname, 'index.html')).href;
const events = [];
const remoteWindows = new Map();
const FILE_LIMIT = 2 * 1024 * 1024;
const RESPONSE_LIMIT = 64 * 1024;
let localWindow;
let remoteSession;
let sequence = 0;
let logBytes = 0;

function visibleURL(value) {
  try {
    const url = new URL(value);
    return url.protocol === 'file:' ? url.href : url.origin + url.pathname;
  } catch { return String(value).slice(0, 300); }
}

function log(type, details = {}) {
  const entry = { sequence: ++sequence, time: new Date().toISOString(), type, ...details };
  events.push(entry);
  if (events.length > 200) events.shift();
  const line = JSON.stringify(entry) + '\n';
  try {
    if (logBytes + Buffer.byteLength(line) > 8 * 1024 * 1024) {
      fs.renameSync(logPath, logPath + '.previous');
      logBytes = 0;
    }
    fs.appendFileSync(logPath, line);
    logBytes += Buffer.byteLength(line);
  } catch (error) { process.stderr.write(`Log write failed: ${error.message}\n`); }
  process.stdout.write(line);
  if (localWindow && !localWindow.isDestroyed() && !localWindow.webContents.isDestroyed()) {
    localWindow.webContents.send('manual:log', entry);
  }
}

function webURL(value) {
  if (typeof value !== 'string' || value.length > 2048) throw new Error('请输入不超过 2048 字符的 HTTP/HTTPS 地址');
  const url = new URL(value);
  if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password) {
    throw new Error('仅支持不带用户名、密码的 HTTP/HTTPS 地址');
  }
  return url.href;
}

function instrument(window, label) {
  const contents = window.webContents;
  const info = { windowId: contents.id, window: label };
  contents.on('did-start-loading', () => log('load-start', info));
  contents.on('dom-ready', () => log('dom-ready', info));
  contents.on('did-finish-load', () => log('load-finished', { ...info, url: visibleURL(contents.getURL()), title: contents.getTitle() }));
  contents.on('did-navigate', (_event, url, httpResponseCode) => log('navigation', { ...info, url: visibleURL(url), httpStatus: httpResponseCode }));
  contents.on('did-fail-load', (_event, code, description, url, mainFrame) => {
    log('load-failed', { ...info, code, description, mainFrame, url: visibleURL(url) });
  });
  contents.on('render-process-gone', (_event, details) => log('render-process-gone', { ...info, ...details }));
  contents.on('unresponsive', () => log('unresponsive', info));
  contents.on('responsive', () => log('responsive', info));
  contents.on('preload-error', (_event, preloadPath, error) => log('preload-error', { ...info, preloadPath, error: error.message }));
  contents.on('console-message', event => {
    if (!['warning', 'error'].includes(event.level)) return;
    log('console', { ...info, level: event.level, message: String(event.message || '').slice(0, 1200),
      line: event.lineNumber, source: visibleURL(event.sourceId || '') });
  });
  window.on('closed', () => log('window-closed', info));
  contents.on('will-attach-webview', event => event.preventDefault());
}

function openRemote(value) {
  const url = webURL(value);
  if (remoteWindows.size >= 6) throw new Error('最多同时打开 6 个网页窗口，请先关闭一个');
  const window = new BrowserWindow({
    width: 1120, height: 800, title: new URL(url).hostname, backgroundColor: '#ffffff',
    webPreferences: { contextIsolation: true, nodeIntegration: false, sandbox: true,
      webSecurity: true, session: remoteSession },
  });
  const id = window.webContents.id;
  remoteWindows.set(id, window);
  instrument(window, new URL(url).hostname);
  window.on('closed', () => remoteWindows.delete(id));
  window.webContents.setWindowOpenHandler(details => {
    try { openRemote(details.url); } catch (error) { log('popup-blocked', { error: error.message }); }
    return { action: 'deny' };
  });
  window.webContents.on('will-navigate', (event, next) => {
    try { webURL(next); } catch {
      event.preventDefault();
      log('navigation-blocked', { windowId: id, url: visibleURL(next) });
    }
  });
  log('window-opened', { windowId: id, url: visibleURL(url), isolated: true, sandbox: true });
  window.loadURL(url).catch(error => log('loadURL-rejected', { windowId: id, error: error.message }));
  return { windowId: id, url: visibleURL(url) };
}

function requireDashboard(event) {
  const frame = event.senderFrame;
  if (!localWindow || localWindow.isDestroyed() || event.sender !== localWindow.webContents
      || !frame || frame.parent !== null || frame.url !== dashboardURL) {
    throw new Error('此操作只允许本地测试面板的主页面调用');
  }
}

function handle(channel, action) {
  ipcMain.handle(channel, async (event, value) => {
    try {
      requireDashboard(event);
      return { ok: true, ...(await action(value)) };
    } catch (error) {
      log('operation-failed', { operation: channel, error: error.message });
      return { ok: false, error: error.message };
    }
  });
}

handle('manual:state', async () => {
  let glibc = null;
  try { glibc = process.report.getReport().header.glibcVersionRuntime || null; } catch {}
  return { versions: process.versions, arch: process.arch, platform: process.platform,
    cpu: os.cpus()[0]?.model || 'unknown', glibc, software, logPath, events,
    gpu: app.getGPUFeatureStatus(), switches: {
      noSandbox: app.commandLine.hasSwitch('no-sandbox'), noZygote: app.commandLine.hasSwitch('no-zygote'),
    } };
});
handle('manual:gpu', async () => ({ gpu: app.getGPUFeatureStatus(), info: JSON.stringify(await app.getGPUInfo('basic')).slice(0, 24000) }));
handle('manual:open-web', async value => openRemote(value));
handle('manual:open-file', async () => {
  const selected = await dialog.showOpenDialog(localWindow, { properties: ['openFile'], title: '选择测试文件（最多 2 MiB）' });
  if (selected.canceled || !selected.filePaths.length) return { canceled: true };
  const filename = selected.filePaths[0];
  const file = await fs.promises.open(filename, fs.constants.O_RDONLY | (fs.constants.O_NONBLOCK || 0));
  try {
    const stat = await file.stat();
    if (!stat.isFile() || stat.size > FILE_LIMIT) throw new Error('请选择不超过 2 MiB 的普通文件');
    const bytes = Buffer.alloc(stat.size);
    let read = 0;
    while (read < bytes.length) {
      const result = await file.read(bytes, read, bytes.length - read, read);
      if (!result.bytesRead) break;
      read += result.bytesRead;
    }
    const content = bytes.subarray(0, read);
    const mime = { '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.gif': 'image/gif', '.webp': 'image/webp' }[path.extname(filename).toLowerCase()];
    log('file-read', { name: path.basename(filename), size: stat.size, bytesRead: read });
    return { name: path.basename(filename), size: stat.size, bytesRead: read,
      preview: content.subarray(0, RESPONSE_LIMIT).toString('utf8'), previewTruncated: read > RESPONSE_LIMIT,
      hex: content.subarray(0, 64).toString('hex'), image: mime ? `data:${mime};base64,${content.toString('base64')}` : null };
  } finally { await file.close(); }
});
handle('manual:network', async value => {
  const url = webURL(value);
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(new Error('网络请求超过 15 秒')), 15000);
  const started = Date.now();
  let reader;
  try {
    const response = await net.fetch(url, { signal: controller.signal });
    reader = response.body?.getReader();
    const chunks = [];
    let size = 0;
    let truncated = false;
    if (reader) {
      while (true) {
        const part = await reader.read();
        if (part.done) break;
        const available = RESPONSE_LIMIT - size;
        chunks.push(Buffer.from(part.value.subarray(0, available)));
        size += Math.min(available, part.value.length);
        if (size >= RESPONSE_LIMIT) { truncated = true; break; }
      }
    }
    const result = { url: visibleURL(response.url), status: response.status, httpOK: response.ok,
      contentType: response.headers.get('content-type'), durationMs: Date.now() - started,
      sampledBytes: size, truncated, preview: Buffer.concat(chunks).subarray(0, 16384).toString('utf8') };
    log('network-response', { ...result, preview: undefined });
    return result;
  } finally {
    if (reader) await reader.cancel().catch(() => {});
    clearTimeout(timer);
  }
});

app.on('child-process-gone', (_event, details) => log('child-process-gone', {
  processType: details.type, reason: details.reason, exitCode: details.exitCode,
  name: details.name, serviceName: details.serviceName,
}));
app.on('window-all-closed', () => app.quit());

app.whenReady().then(async () => {
  remoteSession = session.fromPartition('manual-desktop-web');
  remoteSession.setPermissionCheckHandler(() => false);
  remoteSession.setPermissionRequestHandler((contents, permission, callback) => {
    log('permission-denied', { windowId: contents.id, permission });
    callback(false);
  });
  const filter = { urls: ['http://*/*', 'https://*/*'] };
  remoteSession.webRequest.onResponseStarted(filter, details => {
    if (details.resourceType === 'mainFrame' && remoteWindows.has(details.webContentsId)) {
      log('http-response', { windowId: details.webContentsId, url: visibleURL(details.url), status: details.statusCode, fromCache: details.fromCache });
    }
  });
  remoteSession.webRequest.onErrorOccurred(filter, details => {
    if (details.resourceType === 'mainFrame' && remoteWindows.has(details.webContentsId)) {
      log('http-error', { windowId: details.webContentsId, url: visibleURL(details.url), error: details.error });
    }
  });
  Menu.setApplicationMenu(Menu.buildFromTemplate([
    { label: '测试', submenu: [{ role: 'reload' }, { role: 'forceReload' }, { type: 'separator' }, { role: 'quit' }] },
    { label: '查看', submenu: [{ role: 'toggleDevTools' }, { role: 'resetZoom' }, { role: 'zoomIn' }, { role: 'zoomOut' }, { role: 'togglefullscreen' }] },
  ]));
  localWindow = new BrowserWindow({ width: 1180, height: 900, minWidth: 850, minHeight: 600,
    title: 'Electron 3A4000 手工验证', backgroundColor: '#f4f6fa',
    webPreferences: { preload: path.join(__dirname, 'preload.js'), contextIsolation: true,
      nodeIntegration: false, sandbox: true, webSecurity: true },
  });
  instrument(localWindow, 'local-dashboard');
  localWindow.webContents.setWindowOpenHandler(() => ({ action: 'deny' }));
  localWindow.webContents.on('will-navigate', (event, url) => { if (url !== dashboardURL) event.preventDefault(); });
  localWindow.on('closed', () => { localWindow = null; });
  log('startup', { arch: process.arch, electron: process.versions.electron, software, logPath,
    noSandbox: app.commandLine.hasSwitch('no-sandbox'), noZygote: app.commandLine.hasSwitch('no-zygote') });
  await localWindow.loadFile(path.join(__dirname, 'index.html'));
}).catch(error => {
  log('startup-failed', { error: error.stack || String(error) });
  app.exit(1);
});
