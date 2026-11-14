'use strict';

const $ = (id) => document.getElementById(id);
const setStatus = (id, text, kind = '') => { const e = $(id); e.textContent = text; e.className = `status ${kind}`; };

// Draw a moving canvas and record it. This exercises Canvas -> MediaRecorder -> <video>
// without shipping a binary fixture or requiring network access.
let videoUrl;
async function makeVideo() {
  const canvas = document.createElement('canvas'); canvas.width = 640; canvas.height = 360;
  const ctx = canvas.getContext('2d'); const stream = canvas.captureStream(30);
  if (!window.MediaRecorder || !MediaRecorder.isTypeSupported('video/webm;codecs=vp8')) throw new Error('MediaRecorder WebM/VP8 不可用');
  const chunks = []; const recorder = new MediaRecorder(stream, { mimeType: 'video/webm;codecs=vp8' });
  recorder.ondataavailable = (e) => { if (e.data.size) chunks.push(e.data); };
  const started = performance.now();
  const draw = (now) => { const t = (now - started) / 1000; ctx.fillStyle = '#101827'; ctx.fillRect(0, 0, 640, 360); ctx.fillStyle = `hsl(${(t * 110) % 360} 75% 60%)`; ctx.beginPath(); ctx.arc(320 + Math.cos(t * 3) * 190, 180 + Math.sin(t * 2) * 100, 42, 0, Math.PI * 2); ctx.fill(); ctx.fillStyle = '#fff'; ctx.font = '26px sans-serif'; ctx.fillText(`Electron media ${t.toFixed(1)}s`, 24, 42); if (t < 3) requestAnimationFrame(draw); };
  recorder.start(); requestAnimationFrame(draw);
  await new Promise((resolve) => setTimeout(resolve, 3300)); recorder.stop(); await new Promise((resolve) => { recorder.onstop = resolve; });
  if (videoUrl) URL.revokeObjectURL(videoUrl); videoUrl = URL.createObjectURL(new Blob(chunks, { type: recorder.mimeType }));
  $('video').src = videoUrl; $('video').load(); $('video').onloadedmetadata = () => { $('video-info').textContent = JSON.stringify({ mimeType: recorder.mimeType, bytes: chunks.reduce((n, c) => n + c.size, 0), duration: $('video').duration, videoWidth: $('video').videoWidth, videoHeight: $('video').videoHeight }, null, 2); };
  setStatus('video-status', 'WebM 已生成，点击播放', 'ok');
}
$('make-video').onclick = () => makeVideo().catch((e) => { setStatus('video-status', e.message, 'error'); $('video-info').textContent = String(e.stack || e); });
$('play-video').onclick = () => { const v = $('video'); if (v.paused) v.play().catch((e) => setStatus('video-status', e.message, 'error')); else v.pause(); };

function wavUrl(seconds = 2) {
  const rate = 48000; const samples = rate * seconds; const b = new ArrayBuffer(44 + samples * 2); const d = new DataView(b);
  const text = (o, s) => [...s].forEach((c, i) => d.setUint8(o + i, c.charCodeAt(0))); text(0, 'RIFF'); d.setUint32(4, 36 + samples * 2, true); text(8, 'WAVEfmt '); d.setUint32(16, 16, true); d.setUint16(20, 1, true); d.setUint16(22, 1, true); d.setUint32(24, rate, true); d.setUint32(28, rate * 2, true); d.setUint16(32, 2, true); d.setUint16(34, 16, true); text(36, 'data'); d.setUint32(40, samples * 2, true);
  for (let i = 0; i < samples; i++) d.setInt16(44 + i * 2, Math.sin(2 * Math.PI * 440 * i / rate) * 14000, true); return URL.createObjectURL(new Blob([b], { type: 'audio/wav' }));
}
$('make-audio').onclick = () => { const a = $('audio'); if (a.src) URL.revokeObjectURL(a.src); a.src = wavUrl(); a.onloadedmetadata = () => { $('audio-info').textContent = JSON.stringify({ duration: a.duration, readyState: a.readyState, canPlay: a.canPlayType('audio/wav') }, null, 2); }; a.load(); setStatus('audio-status', 'WAV 已生成，点击播放', 'ok'); };
$('tone').onclick = async () => { const ac = new AudioContext(); const osc = ac.createOscillator(); const gain = ac.createGain(); osc.frequency.value = 660; gain.gain.setValueAtTime(0.12, ac.currentTime); gain.gain.exponentialRampToValueAtTime(0.001, ac.currentTime + 1); osc.connect(gain).connect(ac.destination); osc.start(); osc.stop(ac.currentTime + 1); setStatus('audio-status', `Web Audio ${ac.sampleRate} Hz 播放 1 秒`, 'ok'); setTimeout(() => ac.close(), 1200); };

function initWebgl() { const c = $('webgl'); const gl = c.getContext('webgl'); if (!gl) throw new Error('WebGL context 不可用'); const vs = 'attribute vec2 p; uniform float t; void main(){float a=t; gl_Position=vec4(p.x*cos(a)-p.y*sin(a),p.x*sin(a)+p.y*cos(a),0,1);}'; const fs = 'precision mediump float; uniform float t; void main(){gl_FragColor=vec4(0.2+0.8*abs(sin(t)),0.5,0.9,1.0);}'; const compile = (type, src) => { const s = gl.createShader(type); gl.shaderSource(s, src); gl.compileShader(s); if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(s)); return s; }; const p = gl.createProgram(); gl.attachShader(p, compile(gl.VERTEX_SHADER, vs)); gl.attachShader(p, compile(gl.FRAGMENT_SHADER, fs)); gl.linkProgram(p); if (!gl.getProgramParameter(p, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(p)); const buf = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, buf); gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([0, .75, -.75, -.65, .75, -.65]), gl.STATIC_DRAW); const loc = gl.getAttribLocation(p, 'p'); const tloc = gl.getUniformLocation(p, 't'); const start = performance.now(); const frame = (now) => { gl.viewport(0, 0, c.width, c.height); gl.clearColor(.03, .06, .11, 1); gl.clear(gl.COLOR_BUFFER_BIT); gl.useProgram(p); gl.bindBuffer(gl.ARRAY_BUFFER, buf); gl.enableVertexAttribArray(loc); gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0); gl.uniform1f(tloc, (now - start) / 1000); gl.drawArrays(gl.TRIANGLES, 0, 3); requestAnimationFrame(frame); }; requestAnimationFrame(frame); $('gl-info').textContent = JSON.stringify({ vendor: gl.getParameter(gl.VENDOR), renderer: gl.getParameter(gl.RENDERER), version: gl.getParameter(gl.VERSION), shadingLanguage: gl.getParameter(gl.SHADING_LANGUAGE_VERSION) }, null, 2); setStatus('gl-status', 'WebGL 着色器和动画运行中', 'ok'); }
try { initWebgl(); } catch (e) { setStatus('gl-status', e.message, 'error'); $('gl-info').textContent = String(e.stack || e); }

const c2 = $('canvas2d'); const x = c2.getContext('2d'); let n = 0; const draw2d = (t) => { x.fillStyle = '#101827'; x.fillRect(0, 0, c2.width, c2.height); x.fillStyle = '#ffcb6b'; x.beginPath(); x.arc(260 + Math.cos(t / 600) * 170, 95 + Math.sin(t / 500) * 55, 35, 0, Math.PI * 2); x.fill(); n++; if (n === 1) { const px = x.getImageData(0, 0, c2.width, c2.height).data; let checksum = 0; for (let i = 0; i < px.length; i += 97) checksum = (checksum + px[i]) % 1000000007; $('canvas-info').textContent = JSON.stringify({ width: c2.width, height: c2.height, pixelChecksum: checksum }, null, 2); setStatus('canvas-status', 'Canvas 2D 绘制和像素读取成功', 'ok'); } requestAnimationFrame(draw2d); }; requestAnimationFrame(draw2d);
