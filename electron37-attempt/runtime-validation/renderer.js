'use strict';
document.querySelector('#result').textContent = 'Renderer JavaScript: ' + (6 * 7);
const context = document.querySelector('#canvas').getContext('2d');
context.fillStyle = '#26a69a';
context.fillRect(0, 0, 240, 160);
context.fillStyle = '#ffc857';
context.fillRect(240, 0, 240, 160);
document.documentElement.dataset.scriptResult = String(6 * 7);
