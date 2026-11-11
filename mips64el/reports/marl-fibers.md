# Marl MIPS64EL floating-point context preservation

Verified on 2026-11-10 with the public build environment's LLVM 20.1.8,
the complete Buster / GLIBC 2.28 sysroot, and QEMU 8.2.2 using
`-cpu Loongson-3A4000`.

The actual release GN graph selects `osfiber_mips64.c` and
`osfiber_asm_mips64.S` for Marl. Its `Marl.ninja` contains both object rules
and does not define `MARL_FIBERS_USE_UCONTEXT`. This assembly is used by the
current SwiftShader build.

The upstream N64 context switch used `$f31` when saving to the `$f30` slot,
then loaded that slot into `$f31` before loading `$f31`'s own slot. It never
saved or restored `$f30`. N64 requires preservation of every 64-bit register
from `$f24` through `$f31`; a suspended fiber's floating-point state could
therefore be replaced by another fiber's state even though the source compiled.
The source helper now uses `$f30` in those two instructions.

The standalone [probe](../tests/marl-fibers/run.py) compiles the real Marl
context initializer and assembly. A separate assembly wrapper saves its own
caller's registers, seeds all eight callee-saved FPRs with distinct 64-bit
patterns, switches contexts, records the returned FPRs, and restores its
caller's registers. Two real contexts perform three resumptions: the main
context twice and the child once, with distinct patterns for each. The child
also checks its argument and accesses PIC globals before and after suspension.
The executable is linked as PIE with `-fPIC`, `-fstack-protector`, and
`-fno-omit-frame-pointer`; `-Os` matches the release Marl optimization level.

| Optimization | Original assembly | Patched assembly |
| --- | --- | --- |
| `-O0` | Exit 1: `$f30` wrong at all 3 resumptions | Exit 0: all FPR and PIC checks pass |
| `-O2` | Exit 1: `$f30` wrong at all 3 resumptions | Exit 0: all FPR and PIC checks pass |
| `-Os` | Exit 1: `$f30` wrong at all 3 resumptions | Exit 0: all FPR and PIC checks pass |

For example, the original first main-context resumption expected
`f30=3ff1234500000006` but observed the child's
`401abcdef0000006`. The negative control used an unchanged copy of the original
assembly, not a substitute implementation of the context switch.

The real release `osfiber_mips64.o` was also disassembled to examine a possible
`$t9` / PIC entry issue. Its trampoline does not read `$gp` or the incoming
`$t9`: it moves the target argument to `$t9` and calls it with `jalr`.
The actual trampoline and PIC child entry passed every runtime case above.
No speculative `$t9` change was made. This conclusion is limited to the tested
compiler and flags, including the current release configuration.

Inside the build image, with an available static QEMU binary and complete
runtime sysroot, run:

```bash
mips64el-env python3 /work/recipe/tests/marl-fibers/run.py \
  --source-root /work/src \
  --runtime-root /opt/mips-sysroot-buster \
  --qemu /tools/qemu-mips64el-static
```

`--baseline-assembly /path/to/original.S` optionally verifies that the original
assembly exposes the regression. All generated objects and executables stay in
a temporary directory that is cleaned on exit. The verification did not run
GN or Ninja or write into the main output directory.

The complete source helper reported `2 changed, 31 already applied`, then
`0 changed, 33 already applied` on repetition. These probes verify low-level
fiber state preservation and entry, independently of the full Marl scheduler.
They do not replace an Electron GPU test or testing on a physical 3A4000.
