#!/usr/bin/env node
'use strict';

// Offline Node/ELECTRON_RUN_AS_NODE probe. GUI and real hardware are separate.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { performance } = require('node:perf_hooks');
const { Worker, isMainThread, parentPort, workerData } = require('node:worker_threads');

if (!isMainThread) {
  const count = new Int32Array(workerData.shared, 0, 1);
  const wide = new BigInt64Array(workerData.shared, 8, 1);
  for (let i = 0; i < 4096; ++i) {
    Atomics.add(count, 0, 1);
    Atomics.add(wide, 0, 1n);
  }
  parentPort.postMessage({ message: 'worker 中文', sqrt: Math.sqrt(81) });
  parentPort.close();
} else {
  main().catch(error => {
    process.stdout.write(JSON.stringify({ schema: 1, status: 'failed',
      error: String(error && error.stack || error) }) + '\n', () => process.exit(1));
  });
}

async function main() {
  const started = performance.now();
  const controller = new AbortController();
  const workers = new Set();
  const servers = new Set();
  const sockets = new Set();
  const requests = new Set();
  const results = [];
  let directory;
  let overallTimer;
  let failure;
  const report = {
    schema: 1,
    scope: 'offline Node or ELECTRON_RUN_AS_NODE runtime smoke',
    context: process.env.SMOKE_CONTEXT || 'unspecified',
    runtime: { node: process.versions.node, v8: process.versions.v8,
      electron: process.versions.electron || null, arch: process.arch,
      platform: process.platform, exec_argv: process.execArgv },
    target_executed: process.arch === 'mips64el',
    gui_verified: false,
    physical_hardware_verified: false,
    results,
  };

  function timeoutValue(name, fallback) {
    const value = Number(process.env[name] || fallback);
    assert(Number.isSafeInteger(value) && value >= 1000 && value <= 900000,
      `${name} must be an integer from 1000 to 900000 milliseconds`);
    return value;
  }

  async function runCase(name, work, milliseconds) {
    const began = performance.now();
    const signal = controller.signal;
    let timer;
    let onAbort;
    try {
      signal.throwIfAborted();
      const interrupted = new Promise((resolve, reject) => {
        onAbort = () => reject(signal.reason);
        signal.addEventListener('abort', onAbort, { once: true });
        timer = setTimeout(() => controller.abort(new Error(`${name} timed out`)), milliseconds);
      });
      const details = await Promise.race([Promise.resolve().then(work), interrupted]);
      results.push({ name, status: 'passed', duration_ms: Math.round(performance.now() - began), details });
    } catch (error) {
      results.push({ name, status: 'failed', duration_ms: Math.round(performance.now() - began),
        error: String(error && error.stack || error) });
      throw error;
    } finally {
      clearTimeout(timer);
      if (onAbort) signal.removeEventListener('abort', onAbort);
    }
  }

  async function cleanup() {
    for (const request of requests) request.destroy();
    for (const socket of sockets) socket.destroy();
    const pending = [];
    for (const server of servers) {
      server.closeAllConnections();
      pending.push(new Promise(resolve => server.close(resolve)));
    }
    for (const worker of workers) pending.push(worker.terminate());
    let timer;
    try {
      await Promise.race([
        Promise.all(pending),
        new Promise((resolve, reject) => {
          timer = setTimeout(() => reject(new Error('resource cleanup timed out')), 10000);
        }),
      ]);
    } finally {
      clearTimeout(timer);
      if (directory) fs.rmSync(directory, { recursive: true, force: true });
    }
  }

  try {
    const caseTimeout = timeoutValue('SMOKE_TIMEOUT_MS', 60000);
    const totalTimeout = timeoutValue('SMOKE_TOTAL_TIMEOUT_MS', 240000);
    report.timeouts = { per_case_ms: caseTimeout, total_ms: totalTimeout };
    overallTimer = setTimeout(() => controller.abort(new Error('overall smoke timeout')), totalTimeout);

    await runCase('runtime_identity', () => {
      if (process.env.SMOKE_EXPECT_ARCH) assert.equal(process.arch, process.env.SMOKE_EXPECT_ARCH);
      if (process.env.SMOKE_REQUIRE_ELECTRON === '1') assert(process.versions.electron,
        'Expected Electron with ELECTRON_RUN_AS_NODE=1');
      return { expected_arch: process.env.SMOKE_EXPECT_ARCH || null,
        electron_required: process.env.SMOKE_REQUIRE_ELECTRON === '1' };
    }, caseTimeout);

    await runCase('jit_hot_loop_and_type_deoptimization', () => {
      let prepare, optimize, status, finalize;
      try {
        prepare = new Function('fn', '%PrepareFunctionForOptimization(fn);');
        optimize = new Function('fn', '%OptimizeFunctionOnNextCall(fn);');
        status = new Function('fn', 'return %GetOptimizationStatus(fn);');
        finalize = new Function('%FinalizeOptimization();');
      } catch (error) {
        throw new Error('JIT verification requires --allow-natives-syntax on the runtime command line', { cause: error });
      }
      function sum(values) {
        let answer = 0;
        for (let i = 0; i < values.length; ++i) answer += values[i] * 3 + 1;
        return answer;
      }
      const values = Int32Array.from({ length: 4096 }, (_, i) => i);
      const expected = 3 * 4095 * 4096 / 2 + 4096;
      prepare(sum);
      for (let i = 0; i < 64; ++i) assert.equal(sum(values), expected);
      optimize(sum);
      assert.equal(sum(values), expected);
      // Warm-up may already have queued concurrent compilation. Install it
      // before checking the status instead of depending on host timing.
      finalize();
      assert.equal(sum(values), expected);
      // V8 12/13 runtime.h: OptimizationStatus::kOptimized = 1 << 4.
      const optimizedLoop = status(sum);
      assert(optimizedLoop & 16, `hot loop did not reach optimized code: ${optimizedLoop}`);

      function add(a, b) { return a + b; }
      prepare(add);
      for (let i = 0; i < 1024; ++i) assert.equal(add(i, 1), i + 1);
      optimize(add);
      assert.equal(add(20, 22), 42);
      finalize();
      assert.equal(add(20, 22), 42);
      const before = status(add);
      assert(before & 16, `addition did not reach optimized code: ${before}`);
      assert.equal(add('type-change-', 7), 'type-change-7');
      const after = status(add);
      assert.equal(after & 16, 0, `expected deoptimization after number-to-string change: ${after}`);
      assert.equal(add(0.5, 0.25), 0.75);
      return { optimized_loop_status: optimizedLoop, optimized_add_status: before,
        post_type_change_status: after, optimization_confirmed: true, deoptimization_confirmed: true };
    }, caseTimeout);

    await runCase('floating_point_typed_arrays_and_regexp', () => {
      const values = new Float64Array([Math.sqrt(81), Math.sin(Math.PI / 2), -0, NaN]);
      assert.equal(values[0], 9);
      assert(Math.abs(values[1] - 1) < 1e-12);
      assert(Object.is(values[2], -0));
      assert(Number.isNaN(values[3]));
      const bytes = new ArrayBuffer(8);
      const view = new DataView(bytes);
      view.setUint32(0, 0x12345678, true);
      assert.deepEqual(Array.from(new Uint8Array(bytes, 0, 4)), [0x78, 0x56, 0x34, 0x12]);
      const expression = /^(中文)-(\d+)$/u;
      for (let i = 0; i < 128; ++i) assert.equal(expression.exec(`中文-${i}`)[2], String(i));
      assert.equal(Buffer.from('中文 UTF-8', 'utf8').toString('utf8'), '中文 UTF-8');
      return { negative_zero: true, nan: true, explicit_little_endian_io: true, regexp: true };
    }, caseTimeout);

    await runCase('bigint', () => {
      const left = (1n << 127n) + 123456789n;
      const right = 987654321n;
      assert.equal(left * right / right, left);
      assert.equal(left % right, 264491552n);
      const values = new BigInt64Array([-1n, (1n << 63n) - 1n]);
      assert.equal(values[0], -1n);
      assert.equal(values[1], 9223372036854775807n);
      return { multiply_divide: true, remainder: true, bigint64_array: true };
    }, caseTimeout);

    await runCase('scalar_webassembly', async () => {
      const bytes = new Uint8Array([
        0, 97, 115, 109, 1, 0, 0, 0, 1, 7, 1, 96, 2, 127, 127, 1, 127,
        3, 2, 1, 0, 7, 7, 1, 3, 97, 100, 100, 0, 0,
        10, 9, 1, 7, 0, 32, 0, 32, 1, 106, 11,
      ]);
      assert(WebAssembly.validate(bytes));
      const { instance } = await WebAssembly.instantiate(bytes);
      for (let i = 0; i < 4096; ++i) assert.equal(instance.exports.add(i, 2), i + 2);
      assert.equal(instance.exports.add(2147483647, 1), -2147483648);
      return { module: 'i32.add', calls: 4097, simd_tested: false };
    }, caseTimeout);

    await runCase('intl', () => {
      assert.equal(Intl.DateTimeFormat.supportedLocalesOf(['zh-CN', 'en-US']).length, 2);
      const formatter = new Intl.DateTimeFormat('zh-CN', {
        timeZone: 'UTC', year: 'numeric', month: '2-digit', day: '2-digit',
      });
      const parts = Object.fromEntries(formatter.formatToParts(new Date('2026-11-10T12:00:00Z'))
        .filter(part => part.type !== 'literal').map(part => [part.type, part.value]));
      assert.deepEqual(parts, { year: '2026', month: '11', day: '10' });
      assert(new Intl.Collator('zh-CN').compare('a', 'b') < 0);
      return { locales: ['zh-CN', 'en-US'], timezone: 'UTC', date_parts: parts };
    }, caseTimeout);

    await runCase('crypto_and_tls_initialization', () => {
      const crypto = require('node:crypto');
      const tls = require('node:tls');
      assert.equal(crypto.createHash('sha256').update('abc').digest('hex'),
        'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad');
      assert.equal(crypto.pbkdf2Sync('password', 'salt', 1, 32, 'sha256').toString('hex'),
        '120fb6cffcf8b32c43e7225256c4f837a86548c92ccc35480805987cb70be17b');
      assert.equal(crypto.randomBytes(32).length, 32);
      assert(tls.createSecureContext({ minVersion: 'TLSv1.2' }).context);
      assert(tls.getCiphers().length > 0);
      return { sha256: true, pbkdf2: true, entropy: true, tls_context: true,
        tls_handshake_tested: false };
    }, caseTimeout);

    await runCase('filesystem', async () => {
      directory = fs.mkdtempSync(path.join(os.tmpdir(), 'electron-mips-runtime-'));
      const original = path.join(directory, 'original.txt');
      const renamed = path.join(directory, 'renamed.txt');
      await fs.promises.writeFile(original, 'Electron 中文 file I/O\n', { flag: 'wx' });
      await fs.promises.rename(original, renamed);
      assert.equal(await fs.promises.readFile(renamed, 'utf8'), 'Electron 中文 file I/O\n');
      assert((await fs.promises.stat(renamed)).isFile());
      return { write: true, rename: true, read: true, stat: true };
    }, caseTimeout);

    await runCase('worker_threads_and_shared_atomics', async () => {
      const shared = new SharedArrayBuffer(16);
      const worker = new Worker(__filename, { workerData: { shared }, execArgv: [] });
      workers.add(worker);
      const [message] = await Promise.all([
        new Promise((resolve, reject) => { worker.once('message', resolve); worker.once('error', reject); }),
        new Promise((resolve, reject) => {
          worker.once('exit', code => code === 0 ? resolve() : reject(new Error(`worker exit ${code}`)));
          worker.once('error', reject);
        }),
      ]);
      workers.delete(worker);
      assert.deepEqual(message, { message: 'worker 中文', sqrt: 9 });
      assert.equal(Atomics.load(new Int32Array(shared, 0, 1), 0), 4096);
      assert.equal(Atomics.load(new BigInt64Array(shared, 8, 1), 0), 4096n);
      return { worker_exit: 0, shared_int32: 4096, shared_bigint64: '4096' };
    }, caseTimeout);

    await runCase('localhost_http', async () => {
      const http = require('node:http');
      const server = http.createServer((request, response) => {
        const body = [];
        request.on('data', chunk => body.push(chunk));
        request.on('error', error => response.destroy(error));
        request.on('end', () => {
          response.writeHead(200, { 'content-type': 'application/json; charset=utf-8' });
          response.end(JSON.stringify({ method: request.method, path: request.url,
            body: Buffer.concat(body).toString('utf8') }));
        });
      });
      servers.add(server);
      server.on('connection', socket => {
        sockets.add(socket);
        socket.on('close', () => sockets.delete(socket));
      });
      await new Promise((resolve, reject) => {
        server.once('error', reject);
        server.listen(0, '127.0.0.1', resolve);
      });
      const payload = 'offline 中文 HTTP';
      const reply = await new Promise((resolve, reject) => {
        const request = http.request({ host: '127.0.0.1', port: server.address().port,
          path: '/offline', method: 'POST', agent: false, signal: controller.signal,
          headers: { 'content-type': 'text/plain; charset=utf-8',
            'content-length': Buffer.byteLength(payload) } }, response => {
          const body = [];
          response.on('data', chunk => body.push(chunk));
          response.on('error', reject);
          response.on('end', () => {
            try {
              assert.equal(response.statusCode, 200);
              resolve(JSON.parse(Buffer.concat(body).toString('utf8')));
            } catch (error) { reject(error); }
          });
        });
        requests.add(request);
        request.on('close', () => requests.delete(request));
        request.on('error', reject);
        request.end(payload);
      });
      assert.deepEqual(reply, { method: 'POST', path: '/offline', body: payload });
      return { address: '127.0.0.1', request: 'POST', external_network_used: false };
    }, caseTimeout);
  } catch (error) {
    failure = error;
  } finally {
    clearTimeout(overallTimer);
    try { await cleanup(); } catch (error) { failure ||= error; }
  }
  report.status = failure ? 'failed' : 'passed';
  report.duration_ms = Math.round(performance.now() - started);
  report.temporary_files_removed = !directory || !fs.existsSync(directory);
  if (failure) report.error = String(failure && failure.stack || failure);
  process.stdout.write(JSON.stringify(report) + '\n', () => process.exit(failure ? 1 : 0));
}
