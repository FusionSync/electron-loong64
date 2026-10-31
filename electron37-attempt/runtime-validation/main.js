'use strict';
const { app, BrowserWindow } = require('electron');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const results = process.env.UOS_RUNTIME_RESULTS;
if (!results) throw new Error('Use runtime-validation/run.sh to launch this app.');
const report = {
  status: 'running', startedAt: new Date().toISOString(),
  arch: process.arch, versions: process.versions, checks: {}, childProcessEvents: []
};
let window;
let finishing = false;
function save() {
  fs.writeFileSync(path.join(results, 'renderer.json'), JSON.stringify(report, null, 2) + '\n');
}
function fail(error) {
  if (finishing) return;
  finishing = true;
  report.status = 'failed';
  report.error = error.stack || String(error);
  report.finishedAt = new Date().toISOString();
  save();
  console.error(report.error);
  app.exit(1);
}
process.on('uncaughtException', fail);
process.on('unhandledRejection', fail);
const watchdog = setTimeout(() => fail(new Error('Renderer validation timed out after 75 seconds.')), 75000);
for (const flag of ['no-sandbox', 'disable-sandbox', 'disable-setuid-sandbox', 'disable-gpu-sandbox']) {
  if (app.commandLine.hasSwitch(flag)) throw new Error('Sandbox-disabling switch is forbidden: ' + flag);
}
app.enableSandbox();
const profile = path.join(results, 'profile');
fs.mkdirSync(profile, { recursive: true });
app.setPath('userData', profile);
app.on('child-process-gone', (_event, details) => {
  report.childProcessEvents.push(details);
  save();
});
app.on('window-all-closed', () => {
  if (report.checks.capturePage) app.quit();
  else fail(new Error('Window closed before validation completed.'));
});
app.on('will-quit', () => {
  if (!report.checks.capturePage) return;
  finishing = true;
  clearTimeout(watchdog);
  report.checks.normalQuit = true;
  report.status = 'passed';
  report.finishedAt = new Date().toISOString();
  save();
  fs.writeFileSync(path.join(results, 'renderer-normal-quit.ok'), 'normal app.quit after all renderer checks\n');
});
app.whenReady().then(async () => {
  assert.equal(process.platform, 'linux');
  assert.equal(process.arch, process.env.UOS_EXPECTED_NODE_ARCH);
  assert.equal(process.versions.electron, process.env.UOS_EXPECTED_ELECTRON_VERSION);
  window = new BrowserWindow({
    width: 800, height: 520, show: true, title: 'UOS Electron runtime validation',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'), sandbox: true,
      contextIsolation: true, nodeIntegration: false
    }
  });
  report.checks.browserWindow = true;
  window.webContents.on('render-process-gone', (_event, details) => fail(new Error('Renderer exited: ' + JSON.stringify(details))));
  window.webContents.on('preload-error', (_event, preloadPath, error) => fail(new Error(preloadPath + ': ' + error.stack)));
  await window.loadFile(path.join(__dirname, 'index.html'));
  report.checks.localPageLoaded = true;
  report.renderer = await window.webContents.executeJavaScript(`new Promise(resolve => {
    requestAnimationFrame(() => requestAnimationFrame(() => resolve({
      scriptResult: document.documentElement.dataset.scriptResult,
      text: document.querySelector('#result').textContent,
      sandbox: window.runtimeProbe,
      nodeRequire: typeof require,
      calculation: [1, 2, 3, 4].reduce((sum, n) => sum + n, 0),
      canvasPixel: Array.from(document.querySelector('#canvas').getContext('2d').getImageData(5, 5, 1, 1).data)
    })));
  })`);
  assert.equal(report.renderer.scriptResult, '42');
  assert.equal(report.renderer.text, 'Renderer JavaScript: 42');
  assert.equal(report.renderer.calculation, 10);
  assert.deepEqual(report.renderer.canvasPixel, [38, 166, 154, 255]);
  assert.equal(report.renderer.nodeRequire, 'undefined');
  assert.equal(report.renderer.sandbox.sandboxed, true);
  assert.equal(report.renderer.sandbox.contextIsolated, true);
  assert.equal(report.renderer.sandbox.type, 'renderer');
  report.checks.pageJavascript = true;
  report.checks.executeJavascript = true;
  report.checks.rendererReportsSandboxed = true;
  report.renderer.osProcessId = window.webContents.getOSProcessId();
  try {
    const status = fs.readFileSync('/proc/' + report.renderer.osProcessId + '/status', 'utf8');
    report.renderer.procStatus = status.split('\n').filter(line => /^(Name|NoNewPrivs|Seccomp|Seccomp_filters):/.test(line));
  } catch (error) {
    report.renderer.procStatusError = error.message;
  }
  const screenshot = await window.webContents.capturePage();
  assert.equal(screenshot.isEmpty(), false);
  const bitmap = screenshot.toBitmap();
  const colors = new Set();
  for (let offset = 0; offset + 3 < bitmap.length && colors.size < 8; offset += 4) {
    colors.add(bitmap.subarray(offset, offset + 3).toString('hex'));
  }
  assert.ok(colors.size > 2, 'Captured image is blank or lacks the test page colors.');
  fs.writeFileSync(path.join(results, 'renderer.png'), screenshot.toPNG());
  report.screenshot = { ...screenshot.getSize(), distinctRgbSamples: colors.size, file: 'renderer.png' };
  report.checks.capturePage = true;
  report.gpu = { featureStatus: app.getGPUFeatureStatus(), validation: 'information_only' };
  let gpuTimer;
  try {
    report.gpu.basicInfo = await Promise.race([
      app.getGPUInfo('basic'),
      new Promise((_resolve, reject) => { gpuTimer = setTimeout(() => reject(new Error('GPU information timeout')), 5000); })
    ]);
  } catch (error) {
    report.gpu.informationError = error.message;
  } finally {
    clearTimeout(gpuTimer);
  }
  save();
  window.close();
}).catch(fail);
