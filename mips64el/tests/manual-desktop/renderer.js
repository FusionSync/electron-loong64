'use strict';

const api = window.manualDesktop;
const element = id => document.getElementById(id);
const lines = [];
let lastSequence = 0;

function appendEvent(entry) {
  if (entry.sequence <= lastSequence) return;
  lastSequence = entry.sequence;
  lines.push(JSON.stringify(entry));
  if (lines.length > 160) lines.shift();
  element('events').textContent = lines.join('\n');
  element('events').scrollTop = element('events').scrollHeight;
}

async function invoke(work) {
  const result = await work;
  if (!result.ok) throw new Error(result.error);
  return result;
}

function click(id, work) {
  element(id).addEventListener('click', async () => {
    const button = element(id);
    button.disabled = true;
    element('notice').textContent = '';
    try { await work(); }
    catch (error) { element('notice').textContent = error.message; }
    finally { button.disabled = false; }
  });
}

async function openWeb(url) {
  const result = await invoke(api.openWeb(url));
  element('web-status').textContent = `窗口 ${result.windowId}：${result.url}`;
}

async function initialize() {
  if (!api) throw new Error('本地 preload 未加载；请用 Electron 启动 main.js，并查看终端中的 preload-error');
  const state = await invoke(api.state());
  state.events.forEach(appendEvent);
  const stop = api.onLog(appendEvent);
  window.addEventListener('unload', () => stop(), { once: true });
  element('identity').textContent = `Electron ${state.versions.electron} · ${state.arch} · GLIBC ${state.glibc || '未识别'} · ${state.software ? '软件绘制模式' : '默认绘制模式'}`;
  element('log-path').textContent = `日志文件：${state.logPath}`;
  element('system').textContent = JSON.stringify({ cpu: state.cpu, arch: state.arch,
    versions: state.versions, glibc: state.glibc, gpu: state.gpu, diagnosticSwitches: state.switches }, null, 2);
  if (state.switches.noSandbox || state.switches.noZygote) {
    element('notice').textContent = '本次使用了 sandbox/zygote 诊断选项，请单独记录；不能作为默认隔离配置的通过结果。';
  }
  click('open-file', async () => {
    const result = await invoke(api.openFile());
    if (result.canceled) { element('file-status').textContent = '已取消'; return; }
    element('file-status').textContent = `${result.name} · ${result.size} 字节 · 已读取 ${result.bytesRead} 字节`;
    element('file-preview').textContent = `文件头 hex：${result.hex}\n\n${result.preview}${result.previewTruncated ? '\n…预览已截断' : ''}`;
    element('file-image').hidden = !result.image;
    if (result.image) element('file-image').src = result.image;
    else element('file-image').removeAttribute('src');
  });
  click('network', async () => {
    element('network-status').textContent = '请求中…';
    try {
      const result = await invoke(api.network(element('network-url').value));
      element('network-status').textContent = `HTTP ${result.status} · ${result.durationMs} ms · ${result.sampledBytes} 字节${result.truncated ? '（截断）' : ''}`;
      element('network-preview').textContent = `${result.url}\n${result.contentType || '(无 Content-Type)'}\n\n${result.preview}`;
    } catch (error) {
      element('network-status').textContent = '请求失败';
      throw error;
    }
  });
  click('bilibili', () => openWeb('https://www.bilibili.com/'));
  click('xiaohongshu', () => openWeb('https://www.xiaohongshu.com/explore'));
  click('both', async () => { await openWeb('https://www.bilibili.com/'); await openWeb('https://www.xiaohongshu.com/explore'); });
  click('open-web', () => openWeb(element('web-url').value));
  click('gpu', async () => {
    const result = await invoke(api.gpu());
    element('system').textContent = JSON.stringify(result.gpu, null, 2) + '\n\n' + result.info;
  });
}

const canvas = element('animation');
const context = canvas.getContext('2d');
let paused = false;
let phase = 0;
let previous = performance.now();
let fpsBegan = previous;
let frames = 0;
function animate(now) {
  if (!paused && context) {
    phase += Math.min(now - previous, 100) / 1000;
    context.clearRect(0, 0, canvas.width, canvas.height);
    for (let i = 0; i < 12; i++) {
      const x = canvas.width / 2 + Math.sin(phase * (0.6 + i / 14) + i) * (canvas.width / 2 - 18);
      const y = canvas.height / 2 + Math.cos(phase + i * 0.8) * (canvas.height / 2 - 18);
      context.fillStyle = `hsl(${i * 30 + phase * 20},80%,65%)`;
      context.beginPath();
      context.arc(x, y, 10 + i % 3 * 3, 0, Math.PI * 2);
      context.fill();
    }
    frames++;
  }
  if (now - fpsBegan >= 1000) {
    element('fps').textContent = paused ? 'Canvas 已暂停' : `${Math.round(frames * 1000 / (now - fpsBegan))} FPS`;
    frames = 0;
    fpsBegan = now;
  }
  previous = now;
  requestAnimationFrame(animate);
}
element('toggle-animation').addEventListener('click', () => {
  paused = !paused;
  element('toggle-animation').textContent = paused ? '继续 Canvas' : '暂停 Canvas';
});
if (context) requestAnimationFrame(animate);
else element('fps').textContent = '无法创建 Canvas 2D context';
try {
  const gl = document.createElement('canvas').getContext('webgl');
  if (gl) {
    const debug = gl.getExtension('WEBGL_debug_renderer_info');
    element('webgl').textContent = `WebGL 可创建：${debug ? gl.getParameter(debug.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER)}`;
    gl.getExtension('WEBGL_lose_context')?.loseContext();
  } else element('webgl').textContent = 'WebGL 不可用；请结合 GPU 信息与软件模式比较。';
} catch (error) { element('webgl').textContent = `WebGL 检查失败：${error.message}`; }

initialize().catch(error => { element('notice').textContent = error.message; });
