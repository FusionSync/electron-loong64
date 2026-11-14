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

function checkMediaCapabilities() {
  const video = document.createElement('video');
  const audio = document.createElement('audio');
  const formats = [
    ['H.264/MP4', video.canPlayType('video/mp4; codecs="avc1.42E01E"')],
    ['VP8/WebM', video.canPlayType('video/webm; codecs="vp8, vorbis"')],
    ['VP9/WebM', video.canPlayType('video/webm; codecs="vp09.00.10.08"')],
    ['AAC/M4A', audio.canPlayType('audio/mp4; codecs="mp4a.40.2"')],
    ['MP3', audio.canPlayType('audio/mpeg')],
    ['Opus/Ogg', audio.canPlayType('audio/ogg; codecs="opus"')],
    ['WAV', audio.canPlayType('audio/wav')],
  ];
  const names = formats.map(([name, result]) => `${name}: ${result || '不支持'}`);
  element('media-capabilities').textContent = `格式声明（maybe=可能支持，需实际文件验证）：${names.join(' · ')}`;
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
  checkMediaCapabilities();
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
  click('canvas-snapshot', async () => {
    if (!canvas) throw new Error('Canvas 2D 不可用');
    const png = canvas.toDataURL('image/png');
    const bytes = Math.round((png.length * 3) / 4);
    element('canvas-status').textContent = `PNG 导出成功 · 约 ${bytes} 字节 · ${png.slice(0, 28)}…`;
    element('canvas-status').className = 'result pass';
  });
  click('audio-start', playTestTone);
  click('audio-stop', stopTestTone);
  click('audio-open', async () => {
    const result = await invoke(api.openMedia('audio'));
    if (result.canceled) { element('audio-status').textContent = '已取消'; return; }
    const audio = element('audio-file');
    audio.src = result.url;
    audio.load();
    element('audio-status').textContent = `${result.name} · ${result.size} 字节 · 已载入，点击播放器播放`;
    element('audio-status').className = 'result';
  });
  click('video-start', startCanvasVideo);
  click('video-stop', stopCanvasVideo);
  click('video-open', async () => {
    const result = await invoke(api.openMedia('video'));
    if (result.canceled) { element('video-status').textContent = '已取消'; return; }
    const video = element('test-video');
    stopCanvasVideo();
    video.src = result.url;
    video.muted = false;
    video.load();
    element('video-status').textContent = `${result.name} · ${result.size} 字节 · 已载入，点击播放按钮`;
    element('video-status').className = 'result';
  });
  element('audio-file').addEventListener('loadedmetadata', () => {
    const audio = element('audio-file');
    element('audio-status').textContent = `媒体元数据已读取 · ${audio.duration === Infinity ? '时长未知' : `${audio.duration.toFixed(2)} 秒`}`;
    element('audio-status').className = 'result pass';
  });
  element('audio-file').addEventListener('error', () => {
    element('audio-status').textContent = `音频解码失败：${element('audio-file').error?.message || '浏览器不支持此格式'}`;
    element('audio-status').className = 'result warn';
  });
  element('test-video').addEventListener('loadedmetadata', () => {
    const video = element('test-video');
    element('video-status').textContent = `视频元数据已读取 · ${video.videoWidth}×${video.videoHeight} · ${video.duration === Infinity ? '时长未知' : `${video.duration.toFixed(2)} 秒`}`;
    element('video-status').className = 'result pass';
  });
  element('test-video').addEventListener('error', () => {
    element('video-status').textContent = `视频解码失败：${element('test-video').error?.message || '浏览器不支持此格式'}`;
    element('video-status').className = 'result warn';
  });
  element('webgl-run').addEventListener('click', runWebGL);
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

let audioContext;
let oscillator;
let audioGain;
async function playTestTone() {
  stopTestTone();
  const AudioContext = window.AudioContext || window.webkitAudioContext;
  if (!AudioContext) throw new Error('Web Audio API 不可用');
  audioContext = audioContext || new AudioContext();
  if (audioContext.state === 'suspended') await audioContext.resume();
  oscillator = audioContext.createOscillator();
  audioGain = audioContext.createGain();
  oscillator.type = 'sine'; oscillator.frequency.value = 440;
  audioGain.gain.setValueAtTime(0.0001, audioContext.currentTime);
  audioGain.gain.exponentialRampToValueAtTime(0.12, audioContext.currentTime + 0.03);
  audioGain.gain.exponentialRampToValueAtTime(0.0001, audioContext.currentTime + 0.95);
  oscillator.connect(audioGain).connect(audioContext.destination);
  oscillator.start(); oscillator.stop(audioContext.currentTime + 1);
  oscillator.addEventListener('ended', () => { oscillator = null; });
  element('audio-status').textContent = `Web Audio 播放中 · 440 Hz · AudioContext ${audioContext.state}`;
  element('audio-status').className = 'result pass';
}
function stopTestTone() {
  if (oscillator) { try { oscillator.stop(); } catch {} oscillator.disconnect(); oscillator = null; }
  if (audioGain) { audioGain.disconnect(); audioGain = null; }
  if (element('audio-status')) element('audio-status').textContent = audioContext ? `已停止 · AudioContext ${audioContext.state}` : '尚未测试';
}

let canvasVideoStream;
let canvasVideoTimer;
function startCanvasVideo() {
  stopCanvasVideo();
  const video = element('test-video');
  if (!canvas.captureStream || typeof video.srcObject === 'undefined') throw new Error('Canvas captureStream 不可用');
  const source = document.createElement('canvas'); source.width = 640; source.height = 360;
  const ctx = source.getContext('2d');
  canvasVideoStream = source.captureStream(30); video.removeAttribute('src'); video.srcObject = canvasVideoStream; video.muted = true;
  let t = 0;
  canvasVideoTimer = setInterval(() => {
    t += 1 / 30;
    const g = ctx.createLinearGradient(0, 0, source.width, source.height);
    g.addColorStop(0, `hsl(${(t * 55) % 360}, 85%, 45%)`); g.addColorStop(1, '#16245f');
    ctx.fillStyle = g; ctx.fillRect(0, 0, source.width, source.height);
    ctx.fillStyle = '#fff'; ctx.font = 'bold 30px sans-serif'; ctx.fillText(`Canvas → Video  ${t.toFixed(1)} s`, 28, 60);
    ctx.beginPath(); ctx.arc(320 + Math.sin(t * 3) * 230, 210 + Math.cos(t * 2) * 90, 44, 0, Math.PI * 2); ctx.fillStyle = '#f8d568'; ctx.fill();
  }, 1000 / 30);
  video.play().then(() => { element('video-status').textContent = 'Canvas 视频播放中 · captureStream · 30 FPS'; element('video-status').className = 'result pass'; })
    .catch(error => { element('video-status').textContent = `视频播放失败：${error.message}`; element('video-status').className = 'result warn'; });
}
function stopCanvasVideo() {
  if (canvasVideoTimer) { clearInterval(canvasVideoTimer); canvasVideoTimer = null; }
  if (canvasVideoStream) { canvasVideoStream.getTracks().forEach(track => track.stop()); canvasVideoStream = null; }
  const video = element('test-video');
  if (video && video.srcObject) { video.pause(); video.srcObject = null; }
}

let webglAnimation;
function runWebGL() {
  const target = element('webgl-canvas');
  const gl = target.getContext('webgl', { antialias: true, alpha: false });
  if (!gl) { element('webgl-status').textContent = 'WebGL context 创建失败'; element('webgl-status').className = 'result warn'; return; }
  if (webglAnimation) cancelAnimationFrame(webglAnimation);
  const vertexSource = 'attribute vec2 position; attribute vec3 color; uniform float angle; varying vec3 vColor; void main(){ float c=cos(angle),s=sin(angle); gl_Position=vec4(c*position.x-s*position.y,s*position.x+c*position.y,0.0,1.0); vColor=color; }';
  const fragmentSource = 'precision mediump float; varying vec3 vColor; void main(){ gl_FragColor=vec4(vColor,1.0); }';
  const compile = (type, source) => { const shader = gl.createShader(type); gl.shaderSource(shader, source); gl.compileShader(shader); if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(shader) || 'shader compile failed'); return shader; };
  try {
    const program = gl.createProgram(); gl.attachShader(program, compile(gl.VERTEX_SHADER, vertexSource)); gl.attachShader(program, compile(gl.FRAGMENT_SHADER, fragmentSource)); gl.linkProgram(program);
    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(program) || 'program link failed');
    const data = new Float32Array([-0.7, -0.6, 1, 0.25, 0.2, 0.7, -0.6, 0.2, 1, 0.25, 0, 0.7, 0.2, 0.25, 1]);
    const buffer = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, buffer); gl.bufferData(gl.ARRAY_BUFFER, data, gl.STATIC_DRAW); gl.useProgram(program);
    const pos = gl.getAttribLocation(program, 'position'), color = gl.getAttribLocation(program, 'color'); gl.enableVertexAttribArray(pos); gl.vertexAttribPointer(pos, 2, gl.FLOAT, false, 20, 0); gl.enableVertexAttribArray(color); gl.vertexAttribPointer(color, 3, gl.FLOAT, false, 20, 8);
    const angle = gl.getUniformLocation(program, 'angle'); const started = performance.now(); let frames = 0;
    const draw = now => { gl.viewport(0, 0, target.width, target.height); gl.clearColor(0.03, 0.06, 0.15, 1); gl.clear(gl.COLOR_BUFFER_BIT); gl.uniform1f(angle, (now - started) / 1400); gl.drawArrays(gl.TRIANGLES, 0, 3); frames++; if (now - started < 3000) webglAnimation = requestAnimationFrame(draw); else element('webgl-status').textContent = `WebGL 渲染成功 · ${gl.getParameter(gl.VERSION)} · ${frames} 帧 · ${gl.getParameter(gl.RENDERER)}`; };
    webglAnimation = requestAnimationFrame(draw);
    element('webgl-status').textContent = `WebGL 着色器已编译 · ${gl.getParameter(gl.VERSION)}`; element('webgl-status').className = 'result pass';
  } catch (error) { element('webgl-status').textContent = `WebGL 失败：${error.message}`; element('webgl-status').className = 'result warn'; }
}
try {
  const gl = document.createElement('canvas').getContext('webgl');
  if (gl) {
    const debug = gl.getExtension('WEBGL_debug_renderer_info');
    element('webgl').textContent = `WebGL 可创建：${debug ? gl.getParameter(debug.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER)}`;
    gl.getExtension('WEBGL_lose_context')?.loseContext();
  } else element('webgl').textContent = 'WebGL 不可用；请结合 GPU 信息与软件模式比较。';
} catch (error) { element('webgl').textContent = `WebGL 检查失败：${error.message}`; }

runWebGL();

initialize().catch(error => { element('notice').textContent = error.message; });
