'use strict';

const output = document.querySelector('#output');
const status = document.querySelector('#status');
const canvas = document.querySelector('#canvas');
const ctx = canvas.getContext('2d');
const ball = { x: 60, y: 60, vx: 2.7, vy: 1.9, radius: 18 };
let frames = 0;
let lastFpsTime = performance.now();

function write(value, replace = false) {
  const text = typeof value === 'string' ? value : JSON.stringify(value, null, 2);
  output.textContent = replace ? text : `${output.textContent}\n${text}`.trim();
}

function setStatus(text, kind = 'info') {
  status.textContent = text;
  status.dataset.kind = kind;
}

function drawFrame(now) {
  const width = canvas.width;
  const height = canvas.height;
  ctx.fillStyle = '#101827';
  ctx.fillRect(0, 0, width, height);
  ctx.strokeStyle = '#263852';
  ctx.lineWidth = 2;
  ctx.strokeRect(1, 1, width - 2, height - 2);
  ball.x += ball.vx;
  ball.y += ball.vy;
  if (ball.x < ball.radius || ball.x > width - ball.radius) ball.vx *= -1;
  if (ball.y < ball.radius || ball.y > height - ball.radius) ball.vy *= -1;
  const gradient = ctx.createRadialGradient(ball.x - 5, ball.y - 6, 2, ball.x, ball.y, ball.radius);
  gradient.addColorStop(0, '#fff7ad');
  gradient.addColorStop(0.3, '#ffcb6b');
  gradient.addColorStop(1, '#e85d75');
  ctx.fillStyle = gradient;
  ctx.beginPath();
  ctx.arc(ball.x, ball.y, ball.radius, 0, Math.PI * 2);
  ctx.fill();
  frames += 1;
  if (now - lastFpsTime > 1000) {
    document.querySelector('#fps').textContent = `${frames} FPS`;
    frames = 0;
    lastFpsTime = now;
  }
  requestAnimationFrame(drawFrame);
}
requestAnimationFrame(drawFrame);

document.querySelector('#animate').addEventListener('click', () => {
  const box = document.querySelector('#animated-box');
  box.classList.toggle('running');
  setStatus(box.classList.contains('running') ? 'CSS animation: running' : 'CSS animation: paused', 'ok');
});

document.querySelector('#open-file').addEventListener('click', async () => {
  setStatus('等待文件选择…');
  try {
    const result = await window.electronTest.openFile();
    if (result.canceled) {
      setStatus('已取消文件选择');
      return;
    }
    write({ file: result.path, size: result.size, mode: result.mode, preview: result.preview }, true);
    setStatus('文件打开和读取成功', 'ok');
  } catch (error) {
    setStatus('文件测试失败', 'error');
    write(String(error), true);
  }
});

document.querySelector('#network').addEventListener('click', async () => {
  const url = document.querySelector('#url').value.trim();
  setStatus(`请求中：${url}`);
  try {
    const result = await window.electronTest.request(url);
    write(result, true);
    setStatus(result.ok ? `网络请求完成：HTTP ${result.statusCode}` : '网络请求失败', result.ok ? 'ok' : 'error');
  } catch (error) {
    setStatus('网络测试失败', 'error');
    write(String(error), true);
  }
});

document.querySelector('#open-bilibili').addEventListener('click', async () => {
  try {
    const result = await window.electronTest.openBilibili();
    setStatus(`已请求系统浏览器打开 ${result.url}`, 'ok');
    write(result);
  } catch (error) {
    setStatus('打开 B 站失败', 'error');
    write(String(error), true);
  }
});

window.electronTest.getSystemInfo().then((info) => {
  document.querySelector('#system').textContent = `${info.platform} / ${info.arch} / Electron ${info.versions.electron} / Node ${info.versions.node} / DISPLAY ${info.display}`;
  write(info, true);
}).catch((error) => write(String(error), true));
