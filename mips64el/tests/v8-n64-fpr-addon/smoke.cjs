'use strict';

const assert = require('node:assert/strict');
const path = require('node:path');

if (process.arch !== 'mips64el' || !process.versions.electron) {
  throw new Error('Run this probe with the MIPS64EL Electron executable in Node mode');
}
if (!process.argv[2]) {
  throw new Error('Usage: electron smoke.cjs /absolute/path/v8-n64-fpr.node');
}
const addon = require(path.resolve(process.argv[2]));
// (module (func (export "trunc") (param f64) (result i32)
//   local.get 0 i32.trunc_f64_s))
const bytes = Uint8Array.from([
  0, 97, 115, 109, 1, 0, 0, 0,
  1, 6, 1, 96, 1, 124, 1, 127,
  3, 2, 1, 0,
  7, 9, 1, 5, 116, 114, 117, 110, 99, 0, 0,
  10, 7, 1, 5, 0, 32, 0, 170, 11,
]);
const trunc = new WebAssembly.Instance(new WebAssembly.Module(bytes)).exports.trunc;
assert.equal(trunc(1.75), 1); // Compile before seeding the native registers.

const checks = [];
for (const [name, callback] of [
  ['js-entry', () => 42],
  ['wasm-i32-trunc-f64-s', () => {
    for (let i = -32; i <= 32; i++) {
      assert.equal(trunc(i + 0.75), Math.trunc(i + 0.75) | 0);
    }
  }],
]) {
  const mismatchMask = addon.checkCalleeSaved(callback);
  const corruptedRegisters = Array.from({length: 8}, (_, bit) => bit + 24)
    .filter((reg) => (mismatchMask & (1 << (reg - 24))) !== 0)
    .map((reg) => `f${reg}`);
  checks.push({name, mismatchMask, corruptedRegisters, passed: mismatchMask === 0});
}
const passed = checks.every((check) => check.passed);
console.log(JSON.stringify({
  passed, architecture: process.arch, electron: process.versions.electron,
  v8: process.versions.v8, execArgv: process.execArgv, checks,
}));
process.exitCode = passed ? 0 : 1;
