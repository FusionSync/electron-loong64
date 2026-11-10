# Offline Electron / Node runtime smoke

This checks the JavaScript runtime, including actual optimization and a type
change that deoptimizes the function. It also checks floating point, typed
arrays, RegExp, BigInt, scalar WebAssembly, ICU/Intl, crypto/TLS initialization,
file I/O, worker threads with shared 32/64-bit atomics, and localhost HTTP.
It downloads nothing and contacts only `127.0.0.1` on an automatically selected
port. TLS initialization is checked; a TLS handshake is not.

`smoke.cjs` prints one JSON report to stdout and exits nonzero on failure. Pass
`--allow-natives-syntax` directly to the runtime: the JIT case uses V8's testing
intrinsics to confirm optimized code and deoptimization, rather than assuming
that a hot loop was optimized. V8's `kOptimized` status bit is checked against
the pinned V8 13 sources and Node 22's V8 12 sources.

## Host check

From the `mips64el/` recipe directory:

```sh
SMOKE_CONTEXT=host-node22 \
  node --allow-natives-syntax tests/runtime-smoke/smoke.cjs \
  > /tmp/runtime-smoke-host.json
```

The checked-in `host-node22-validation.json` is a test of the script on an
x86_64 host. Its `target_executed` is `false`; it provides no MIPS execution
evidence.

## Target execution after Electron has finished building

**The MIPS Electron command below has not yet been executed.** A completed
target Electron executable and its associated libraries/startup data are
required. Do not point this at the x86_64 host `mksnapshot` executable.

Run on an x86_64 Linux host with QEMU supporting `Loongson-3A4000`. Set the three
paths to your own build and independent Buster root; the QEMU executable is an
external dependency, not a verified built-in tool of the compiler image:

```sh
qemu=/absolute/path/to/qemu-mips64el-static
electron_dir=/absolute/path/to/mips-work/out/mips64el-buster
sysroot=/absolute/path/to/mips-work/sysroot-buster
smoke=$(realpath tests/runtime-smoke/smoke.cjs)

ELECTRON_RUN_AS_NODE=1 \
SMOKE_CONTEXT=qemu-Loongson-3A4000 \
SMOKE_EXPECT_ARCH=mips64el \
SMOKE_REQUIRE_ELECTRON=1 \
SMOKE_TIMEOUT_MS=90000 \
SMOKE_TOTAL_TIMEOUT_MS=240000 \
  timeout 330s "$qemu" -cpu Loongson-3A4000 -L "$sysroot" \
    -E "LD_LIBRARY_PATH=$electron_dir:$sysroot/lib/mips64el-linux-gnuabi64:$sysroot/usr/lib/mips64el-linux-gnuabi64:$sysroot/lib64:$sysroot/usr/lib" \
    "$electron_dir/electron" --allow-natives-syntax "$smoke" \
    > runtime-smoke-mips64el.json
```

QEMU's `-E` applies the library path to the target process. It keeps MIPS
libraries out of the host QEMU process's own library search. `-L` selects the
Buster loader/root, and the output directory supplies Electron's own shared
libraries. A complete result has `status: "passed"`, `target_executed: true`,
an Electron version, and both JIT confirmation fields set to `true`.

The default per-case timeout is 60 seconds and total timeout is 240 seconds.
`SMOKE_TIMEOUT_MS` and `SMOKE_TOTAL_TIMEOUT_MS` accept 1000–900000 milliseconds.
The script closes servers/connections, terminates outstanding workers, removes
its temporary directory, and limits cleanup to ten seconds. The outer `timeout`
also bounds synchronous engine hangs; if it kills the process, there may be no
JSON report and its temporary directory may remain.

This is an offline process test. It does not verify GUI, GPU, browser renderer
processes, sandbox behavior, media playback, public websites, a TLS handshake,
or real 3A4000 hardware. Scalar WebAssembly is tested; WebAssembly SIMD is not
part of the MIPS64R2 baseline. See
[the V8 configuration review](../../reports/v8-3a4000-config.md) for the limits
of static ELF auditing and generated machine code.
