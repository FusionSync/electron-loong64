# SwiftShader LLVM 10 MIPS64EL JIT triple

Verified on 2026-11-10 with LLVM 20.1.8, against SwiftShader revision
`a8133cbb3c8969e3c1e6b3cea2c02ec8312ef9ca`.

The Linux LLVM 10 configuration checked `__mips__` before `__mips64`.
Clang's N64 MIPS64EL target defines both macros, so the original headers
selected the 32-bit `mipsel-linux-gnu` triple even though pointers are 64 bits.
This is valid C/C++ and can compile successfully. It affects the target that
SwiftShader's Reactor JIT creates at runtime: `src/Reactor/LLVMJIT.cpp` constructs
its `JITTargetMachineBuilder` from `LLVM_DEFAULT_TARGET_TRIPLE`.

The source helper now checks `__mips64` first in all three active Linux LLVM 10
triple definitions:

- `configs/linux/include/llvm/Config/llvm-config.h`: default and host triple.
- `configs/linux/include/llvm/Config/config.h`: default triple.

These are under `third_party/swiftshader/third_party/llvm-10.0` in the Chromium
source tree. The existing LLVM 10 MIPS backend and native target registration
remain in use. The current Reactor GN target selects LLVM 10; the inactive
LLVM 16 configuration and Windows headers were not changed.

The actual container compiler preprocessed both headers for each target below.
The before results used the original files from the pinned SwiftShader Git
revision; the after results included the patched files. Both default and host
triples agreed in each case, including when `config.h` includes `llvm-config.h`.

| Compiler target and flags | Pointer bytes | Before | After |
| --- | ---: | --- | --- |
| `mips64el-linux-gnuabi64 -march=mips64r2 -mabi=64` | 8 | `mipsel-linux-gnu` | `mips64el-linux-gnuabi64` |
| `mipsel-linux-gnu -march=mips32r2 -mabi=32` | 4 | `mipsel-linux-gnu` | `mipsel-linux-gnu` |
| `x86_64-linux-gnu` | 8 | `x86_64-unknown-linux-gnu` | `x86_64-unknown-linux-gnu` |
| `aarch64-linux-gnu` | 8 | `aarch64-linux-gnu` | `aarch64-linux-gnu` |

To inspect the selected macros from a configured compiler environment, set
`SWIFTSHADER` to the source checkout's `third_party/swiftshader` directory:

```bash
clang --target=mips64el-linux-gnuabi64 -march=mips64r2 -mabi=64 \
  -I "$SWIFTSHADER/third_party/llvm-10.0/configs/linux/include" \
  -include llvm/Config/llvm-config.h -dM -E -x c /dev/null
```

Expected definitions include `__mips__ 1`, `__mips64 1`, `_MIPS_SIM _ABI64`,
`__SIZEOF_POINTER__ 8`, and both LLVM triples set to
`"mips64el-linux-gnuabi64"`. Repeating with `-include llvm/Config/config.h`
must produce the same triple values.

Applying the complete source helper twice produced `3 changed, 26 already
applied`, then `0 changed, 29 already applied`. The three substitutions form
one SwiftShader adaptation and are individually checked for upstream context
and idempotence. No GN or Ninja process was invoked by this verification.
This establishes correct triple selection; a completed Electron build and
GPU or software Vulkan runtime test are separate checks.
