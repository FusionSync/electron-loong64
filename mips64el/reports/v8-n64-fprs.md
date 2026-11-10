# V8 MIPS64 N64 floating-point register preservation

Verified on 2026-11-10 with the public build environment's LLVM 20.1.8,
the complete Buster / GLIBC 2.28 runtime, and QEMU 8.2.2 using
`-cpu Loongson-3A4000`. The focused verification did not invoke GN or Ninja
or write into the main build output directory.

## Defect and reachable execution path

The selected target is `mips64el-linux-gnuabi64`, hard-float, MIPS64R2, with
64-bit pointers and FPRs. V8's MIPS64 argument slots are eight bytes, and its
native C argument home area is zero. This recipe does not support the N32 ABI.
The x86-64 snapshot generator uses the same MIPS64 target register definitions;
an ABI condition based on the build host's `_MIPS_SIM` would be incorrect there.

`v8/src/codegen/mips64/register-mips64.h` originally defined
`C_CALL_CALLEE_SAVE_FP_REGISTERS` as `f20,f22,f24,f26,f28,f30`. That is the
N32 set. N64 instead requires **all eight registers `f24` through `f31`**.
The vendored LLVM MIPS backend independently declares these distinct N32 and
N64 sets in `MipsCallingConv.td` (`CSR_N32` and `CSR_N64`).

The mismatch is reachable with the current WebAssembly-enabled configuration:

- `Builtins::Generate_JSEntryVariant()` in
  `v8/src/builtins/mips64/builtins-mips64.cc` saves and restores
  `kCalleeSavedFPU`, which is derived from that macro.
- `kScratchDoubleReg2` is `f31`. Liftoff's ordinary `i32.trunc_f64_s` and
  `i32.trunc_f32_s` implementations write this register in
  `v8/src/wasm/baseline/mips64/liftoff-assembler-mips64-inl.h`.
- A native caller entering JavaScript that runs such Wasm code can therefore
  receive a changed `f31`, violating N64, even though every file compiles.

The related `kCallerSavedFPU` list stopped at even register `f18`. V8's
allocatable FPR set also contains `f20` and `f22`, and these two registers are
caller-saved in N64. `MacroAssembler::PushCallerSaved()` and
`PopCallerSaved()` use this list directly when FP preservation is requested.
The focused test calls a real Clang-compiled N64 C function which clobbers
`f20/f22`. Its emitted assembly has `.fmask 0` and no FPR save/restore, as
the N64 ABI permits.

## Minimal adaptation and frame review

The source helper changes three items in two MIPS64-only headers:

1. Use `f24,f25,f26,f27,f28,f29,f30,f31` for the C callee-saved set.
2. Derive `kNumCalleeSavedFPU` from `kCalleeSavedFPU.Count()`.
3. Add `f20,f22` to the caller-saved list. This retains V8's existing policy
   of listing allocatable even FPRs; odd native FP argument registers are not
   additional allocatable live registers.

`GetSimplifiedCDescriptor()` also obtains its callee-saved FPRs from this macro.
The MIPS code generator uses the incoming descriptor to allocate/save/restore
those registers. The source audit does not claim that the outgoing register
allocator independently trusted this mask to preserve live `f20/f22` values;
the explicit caller-save path and the native entry path provide direct evidence.

`MultiPushFPU()` counts the selected mask, allocates `Count()*8` bytes, then
stores registers in descending order while reducing the slot offset.
`MultiPopFPU()` loads in ascending order and releases the corresponding size.
Both iterate all 32 mask bits and support odd 64-bit FPRs. Increasing six
callee-saved registers to eight adds 16 bytes and preserves stack alignment.
Caller-save sizes and code-generator frame slots are also derived from counts.

Applying the complete source helper to a disposable copy of the previously
adapted source files reported `3 changed, 36 already applied`; repetition
reported `0 changed, 39 already applied`. The main source tree was not changed
by that fixture test.

The `EntryFrameConstants` offsets remain correct. The saved GPR/FPR area is
created before the six entry-frame slots; `fp` is then established from those
slots. `kNextExitFrameFPOffset=-3*pointer_size`, and the two fast-call offsets,
are relative to this later `fp`, so the extra saved registers are on its positive
side and do not change the three offsets. An independent read-only review
confirmed the register sets, push/pop order, size calculations and offsets.

`Simulator::CallInternal()` seeds and verifies only callee-saved GPRs. It does
not check the FPRs, so successful host snapshot execution would not detect this
ABI violation. The simulator was not expanded as part of this focused fix.

## Executed negative and positive controls

The public [runner](../tests/v8-n64-fprs/run.py) reads the actual V8 headers.
It extracts and **compiles the real `MultiPushFPU()` and `MultiPopFPU()` C++
method bodies** into a small host instruction emitter. Only the instruction
sinks are replaced with GNU assembly text output; the real mask iteration,
register order, stack allocation, and offsets execute unchanged. It also reads
the real scratch-register aliases and extracts the three actual Liftoff
`trunc_w_d`, `mfc1`, and `cvt_d_w` statements from the signed f64-to-i32 path.
The input is exactly integral, so the surrounding rounding and trap machinery
is unnecessary for this register-preservation check.

The target probe independently protects its own native caller, seeds FPRs with
distinct bit patterns, runs those source-derived envelopes, and checks both
the native entry preservation and a real compiled C callback. The negative
control reads unchanged source headers, not a substitute register list.

| Optimization | Original source policy | N64 source policy |
| --- | --- | --- |
| `-O0` | Exit 1: `f31`, `f20`, `f22` mismatches | Exit 0: all checks pass |
| `-O2` | Exit 1: `f31`, `f20`, `f22` mismatches | Exit 0: all checks pass |
| `-Os` | Exit 1: `f31`, `f20`, `f22` mismatches | Exit 0: all checks pass |

For example, the original entry policy expected
`f31=3ff1234500000007` but observed `4010000000000000` (4.0), the value written
by the Liftoff fragment. The C callback replaced the seeded `f20/f22` with zero;
the original caller-save envelope failed to restore them.

Inside the build image, with the source helper applied and QEMU available:

```bash
mips64el-env python3 /work/recipe/tests/v8-n64-fprs/run.py \
  --source-root /work/src \
  --runtime-root /opt/mips-sysroot-buster \
  --qemu /tools/qemu-mips64el-static
```

`--baseline-source-root /path/to/original/source` optionally checks the negative
control. That source tree only needs the two register headers, the macro
assembler source and the Liftoff header at their original relative paths.
All generated host emitters, assembly, objects and executables are temporary.

This probe executes real source-derived V8 preservation mechanics and the
relevant instructions under the target ABI. It does not build a complete V8
engine, execute a full JSEntry frame, or verify an Electron runtime. A final
native-addon → JavaScript → Wasm → native-call check remains an additional
runtime gate once the Electron binary exists; physical 3A4000 testing is
also separate.
