'use strict';

const { app, BrowserWindow, session, screen } = require('electron');
const path = require('node:path');
const fs = require('node:fs');

// UOS Loong64 machines may abort while launching the Chromium GPU process
// when no compatible accelerated driver is available. This diagnostic app is
// intended to test page/network rendering, so make software compositing the
// default even when the caller omits --disable-gpu. Some pages also request
// WebGL/video acceleration after navigation; disable those paths too because
// this Chromium build otherwise retries the broken GPU process and aborts the
// browser process several seconds after a page has rendered.
for (const switchName of [
  'disable-gpu',
  'disable-gpu-compositing',
  'disable-gpu-rasterization',
  'disable-accelerated-2d-canvas',
  'disable-accelerated-video-decode',
  'disable-accelerated-mjpeg-decode',
  'disable-webgl',
  'disable-webgl2',
  // The UOS Loong64 zygote/sandbox path currently crashes renderer
  // processes. This is a local diagnostic app, so use the stable path.
  'no-zygote',
  'no-sandbox',
]) {
  app.commandLine.appendSwitch(switchName);
}
app.commandLine.appendSwitch(
  'disable-features',
  'VaapiVideoDecoder,UseChromeOSDirectVideoDecoder,WebGPU',
);
app.disableHardwareAcceleration();

const pages = [
  { name: '小红书', url: 'https://www.xiaohongshu.com/' },
  { name: '哔哩哔哩', url: 'https://www.bilibili.com/' },
  { name: '百度', url: 'https://www.baidu.com/' },
];
const windows = new Set();
const diagnosticsDir = process.env.ELECTRON_TEST_DIAGNOSTICS_DIR || '/tmp';

function selectedPages() {
  const selector = (process.env.ELECTRON_TEST_PAGE || '').trim().toLowerCase();
  if (!selector) return pages;
  const aliases = {
    xhs: '小红书',
    xiaohongshu: '小红书',
    bilibili: '哔哩哔哩',
    b站: '哔哩哔哩',
    baidu: '百度',
  };
  const wanted = aliases[selector] || selector;
  const result = pages.filter((page) => page.name.toLowerCase() === wanted || page.name === wanted);
  if (result.length === 0) {
    console.error(`Unknown ELECTRON_TEST_PAGE=${selector}; available: xhs, bilibili, baidu`);
    return pages;
  }
  return result;
}

function escapeHtml(value) {
  return String(value).replace(/[&<>\"']/g, (character) => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '\"': '&quot;',
    "'": '&#39;',
  })[character]);
}

function chromeUserAgent() {
  const current = app.userAgentFallback ||
    'Mozilla/5.0 (X11; Linux loongarch64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36';
  return current.replace(/\sElectron\/[^\s]+/g, '');
}

function failurePage(page, errorCode, errorDescription, validatedURL) {
  const url = validatedURL || page.url;
  return `<!doctype html>
<meta charset="utf-8">
<title>${escapeHtml(page.name)}加载失败</title>
<style>
  html, body { margin: 0; min-height: 100%; font: 16px sans-serif; color: #1f2937; background: #f3f4f6; }
  main { box-sizing: border-box; max-width: 760px; margin: 8vh auto; padding: 32px; border-radius: 14px; background: white; box-shadow: 0 8px 30px #0002; }
  h1 { margin-top: 0; font-size: 24px; }
  code { display: block; margin: 12px 0; padding: 12px; border-radius: 8px; color: #991b1b; background: #fef2f2; white-space: pre-wrap; word-break: break-word; }
  button { border: 0; border-radius: 8px; padding: 10px 18px; color: white; background: #2563eb; cursor: pointer; font-size: 15px; }
  p { line-height: 1.6; }
</style>
<main>
  <h1>${escapeHtml(page.name)}没有加载成功</h1>
  <p>Electron 的渲染进程仍然可以显示错误页。请检查网络或代理设置，然后点击重试。</p>
  <code>错误码: ${escapeHtml(errorCode)} ${escapeHtml(errorDescription)}\nURL: ${escapeHtml(url)}</code>
  <button id="retry">重试</button>
</main>
<script>document.querySelector('#retry').onclick = () => { location.href = ${JSON.stringify(page.url)}; };</script>`;
}

async function inspectPage(win, page, index) {
  if (win.isDestroyed()) return;
  try {
    const state = await win.webContents.executeJavaScript(`(() => {
      const body = document.body;
      const visible = body ? Array.from(body.querySelectorAll('*')).filter((element) => {
        const style = getComputedStyle(element);
        const rect = element.getBoundingClientRect();
        return style.display !== 'none' && style.visibility !== 'hidden' &&
          Number(style.opacity) > 0 && rect.width > 1 && rect.height > 1;
      }).length : 0;
      return {
        title: document.title,
        readyState: document.readyState,
        bodyTextLength: body ? body.innerText.trim().length : -1,
        bodyHtmlLength: body ? body.innerHTML.length : -1,
        bodyChildren: body ? body.children.length : -1,
        visibleElements: visible,
        bodyBackground: body ? getComputedStyle(body).backgroundColor : '',
        url: location.href,
      };
    })()`, true);
    console.log(`[${page.name}] DOM ${JSON.stringify(state)}`);

    // A site can change document.title even when its renderer has produced an
    // empty page. Put a visible diagnostic on that page so this cannot look
    // like an Electron white-screen failure.
    if (state.bodyTextLength < 20 && state.visibleElements < 3) {
      const message = `${page.name} 页面已完成导航，但没有检测到可见内容。\n` +
        `这通常是网络/代理或网站风控响应，不是 Electron 进程崩溃。\n` +
        `URL: ${state.url}`;
      await win.webContents.executeJavaScript(`(() => {
        const old = document.getElementById('__electron_page_diagnostic__');
        if (old) old.remove();
        const panel = document.createElement('div');
        panel.id = '__electron_page_diagnostic__';
        panel.style.cssText = 'position:fixed;z-index:2147483647;left:24px;right:24px;top:24px;padding:18px 22px;border:2px solid #f59e0b;border-radius:12px;background:#fffbeb;color:#78350f;box-shadow:0 8px 30px #0004;font:16px/1.6 sans-serif;white-space:pre-wrap';
        panel.textContent = ${JSON.stringify(message)};
        const retry = document.createElement('button');
        retry.textContent = '重新加载';
        retry.style.cssText = 'display:block;margin-top:12px;padding:8px 14px;border:0;border-radius:7px;background:#2563eb;color:white;cursor:pointer;font-size:15px';
        retry.onclick = () => location.reload();
        panel.appendChild(retry);
        (document.body || document.documentElement).appendChild(panel);
      })()`, true);
      console.error(`[${page.name}] page has no visible content; diagnostic overlay inserted`);
    }
  } catch (error) {
    console.error(`[${page.name}] DOM inspect failed`, error);
  }
}

function saveScreenshot(win, page, index) {
  setTimeout(async () => {
    if (win.isDestroyed()) return;
    try {
      const image = await win.webContents.capturePage();
      fs.mkdirSync(diagnosticsDir, { recursive: true });
      const file = path.join(diagnosticsDir, `electron-page-${index}.png`);
      fs.writeFileSync(file, image.toPNG());
      console.log(`[${page.name}] screenshot ${file} (${image.getSize().width}x${image.getSize().height})`);
    } catch (error) {
      console.error(`[${page.name}] screenshot failed`, error);
    }
  }, 2500);
}

function openPage(page, index) {
  const display = screen.getPrimaryDisplay();
  const area = display.workArea;
  const tile = process.env.ELECTRON_TEST_TILE === '1';
  const width = tile ? Math.max(640, Math.floor(area.width / 2) - 20) : 1280;
  const height = tile ? Math.max(480, Math.floor(area.height / 2) - 34) : 860;
  const column = index % 2;
  const row = Math.floor(index / 2);
  const win = new BrowserWindow({
    title: `Electron Loong64 - ${page.name}`,
    width,
    height,
    x: tile ? area.x + column * (width + 12) : area.x + 40 + (index % 3) * 30,
    y: tile ? area.y + row * (height + 34) : area.y + 40 + (index % 3) * 30,
    backgroundColor: '#ffffff',
    show: false,
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });
  windows.add(win);
  let shown = false;
  let failureShown = false;
  const startedAt = Date.now();
  const showWindow = (reason) => {
    if (shown || win.isDestroyed()) return;
    shown = true;
    win.show();
    console.log(`[${page.name}] window shown (${reason}, ${Date.now() - startedAt} ms)`);
  };
  const loadingTimer = setTimeout(() => {
    showWindow('loading-timeout');
    console.error(`[${page.name}] still loading after 12s; inspect did-finish-load/did-fail-load logs`);
  }, 12000);
  win.webContents.setUserAgent(chromeUserAgent());
  win.webContents.setWindowOpenHandler(({ url }) => {
    console.log(`[${page.name}] window.open -> ${url}`);
    return { action: 'allow' };
  });
  win.webContents.on('did-start-loading', () => console.log(`[${page.name}] loading ${page.url}`));
  win.webContents.once('ready-to-show', () => console.log(`[${page.name}] renderer produced first frame`));
  win.webContents.on('did-finish-load', () => {
    clearTimeout(loadingTimer);
    showWindow('did-finish-load');
    console.log(`[${page.name}] loaded ${win.webContents.getURL()}`);
    inspectPage(win, page, index);
  });
  win.webContents.on('console-message', (_event, level, message, line, sourceId) => {
    console.log(`[${page.name}] console level=${level} ${sourceId}:${line} ${message}`);
  });
  win.webContents.on('did-stop-loading', () => saveScreenshot(win, page, index));
  win.webContents.on('did-fail-load', (_event, errorCode, errorDescription, validatedURL, isMainFrame) => {
    console.error(`[${page.name}] load failed ${errorCode} ${errorDescription}: ${validatedURL}`);
    if (!isMainFrame || failureShown || win.isDestroyed()) return;
    failureShown = true;
    clearTimeout(loadingTimer);
    win.webContents.loadURL(`data:text/html;charset=utf-8,${encodeURIComponent(failurePage(page, errorCode, errorDescription, validatedURL))}`)
      .catch((error) => console.error(`[${page.name}] error page failed`, error));
    showWindow('did-fail-load');
  });
  win.webContents.on('render-process-gone', (_event, details) => {
    console.error(`[${page.name}] renderer gone: ${details.reason} (exit ${details.exitCode})`);
  });
  win.on('closed', () => {
    clearTimeout(loadingTimer);
    windows.delete(win);
  });
  win.loadURL(page.url).catch((error) => console.error(`[${page.name}] loadURL error`, error));
}

app.whenReady().then(async () => {
  const proxy = process.env.ELECTRON_TEST_PROXY;
  if (proxy) {
    console.log(`Using Electron proxy: ${proxy}`);
    await session.defaultSession.setProxy({ proxyRules: proxy });
  }
  console.log(`Electron ${process.versions.electron}, Node ${process.versions.node}, arch ${process.arch}`);
  for (const [index, page] of selectedPages().entries()) openPage(page, index);
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});
