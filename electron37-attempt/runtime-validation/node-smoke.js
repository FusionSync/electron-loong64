'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const result = {
  status: 'failed', platform: process.platform, arch: process.arch,
  processType: typeof process.type === 'undefined' ? null : process.type,
  versions: process.versions, execPath: process.execPath
};
try {
  assert.equal(process.platform, 'linux');
  assert.equal(process.arch, process.env.UOS_EXPECTED_NODE_ARCH);
  assert.equal(process.versions.electron, process.env.UOS_EXPECTED_ELECTRON_VERSION);
  assert.equal(typeof process.type, 'undefined', 'Expected standalone Node mode, not an Electron browser process.');
  assert.ok(process.versions.node && process.versions.v8 && process.versions.chrome);
  assert.equal(Buffer.from('UOS LoongArch64').toString(), 'UOS LoongArch64');
  result.status = 'passed';
} catch (error) {
  result.error = error.stack;
  process.exitCode = 1;
}
fs.writeFileSync(path.join(process.env.UOS_RUNTIME_RESULTS, 'node.json'), JSON.stringify(result, null, 2) + '\n');
console.log(JSON.stringify(result, null, 2));
