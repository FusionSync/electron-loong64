# Real Electron entry FPR regression probe

This N-API addon seeds all eight native N64 callee-saved FPRs (`f24`–`f31`),
calls a JavaScript function through **real `napi_call_function`**, and checks
their bit patterns after V8 returns. Its assembly wrapper restores its own
caller's original FPR values even when a canary check fails.

The JavaScript callback calls scalar Wasm `i32.trunc_f64_s`, whose MIPS Liftoff
implementation uses scratch `f31`. This exercises the real V8 entry builtin;
the probe does not implement a replacement V8 entry frame or register policy.

Build inside the MIPS build container, using the prepared source and Buster
sysroot:

```sh
bash /work/recipe/tests/v8-n64-fpr-addon/build.sh \
  /work/src /opt/mips-sysroot-buster /tmp/v8-n64-fpr-addon
```

Run with the completed MIPS Electron and matching libraries:

```sh
ELECTRON_RUN_AS_NODE=1 /path/to/electron --liftoff --no-wasm-tier-up \
  /path/to/tests/v8-n64-fpr-addon/smoke.cjs \
  /tmp/v8-n64-fpr-addon/v8-n64-fpr.node
```

The JSON result lists corrupted registers per check; success exits 0. Keep
`--liftoff --no-wasm-tier-up` so the conversion uses the audited baseline
compiler. This checks native-to-JavaScript FPR preservation. It does not prove
the separate `PushCallerSaved` path, GUI, or physical hardware behavior.
