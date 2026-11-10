# TFLite CPU execution without the optional XNNPACK delegate

Examined on 2026-11-10 against the independently synchronized Electron 37.2.2
and Chromium source checkout, using the Buster / GLIBC 2.28 cross environment.

The MIPS build first failed in XNNPACK's `hardware-config.h` with `use of empty
enum`: every member of `enum xnn_arch_flags` is conditional on a supported
architecture, and this version of XNNPACK's `common.h` does not identify MIPS.
Adding a dummy enum member would only hide the first failure.

There are real scalar kernels in the XNNPACK source. For example,
`src/src/configs/gemm-config.c` has a scalar fallback for FP32 GEMM, and
`src/src/configs/xx-fill-config.c` has a scalar fill fallback. However, this
Chromium integration does not supply a complete generic scalar backend:

- The generated `third_party/xnnpack/BUILD.gn` selects configuration and
  microkernel dependency sets for x86/x64 and ARM64 only. Its fallback sets
  both `xnnpack_deps` and `xnnpack_standalone_deps` to empty lists. On MIPS,
  even `src/src/configs/hardware-config.c` is absent from the selected graph.
- XNNPACK's GN configuration defines `XNN_ENABLE_CPUINFO=1`.
  `xnn_init_hardware_config()` requires successful `cpuinfo_initialize()` on
  this target. The bundled cpuinfo initializer has no MIPS implementation;
  its unsupported-architecture path returns the uninitialized state.
- The architecture identifiers and complete dependency graph therefore need
  an additional backend port and runtime validation before XNNPACK can be
  claimed to work on a 3A4000. The presence of individual scalar kernels does
  not establish that support.

The public GN arguments now use the upstream switch:

```gn
build_tflite_with_xnnpack = false
```

`third_party/tflite/features.gni` declares this switch; its broad default
otherwise enables XNNPACK on MIPS. Disabling it defines
`TFLITE_WITHOUT_XNNPACK` and removes the XNNPACK delegate sources and
dependencies. No SIMD features or hardware support are invented, and no
XNNPACK source files are modified.

The standard TFLite CPU kernels remain selected, including addition,
convolution, depthwise convolution, and fully connected operations.
`tflite_kernels` lists them independently of this flag, and the main TFLite
target retains its dependency on these kernels. The existing
`build_tflite_with_ruy = true` default remains in effect. WebNN's builtin
resolver and interpreter execution also remain present; its XNNPACK-specific
includes, delegate creation, padding, and GN dependency are guarded by this
same build flag. The other GN consumers in `content/app` and
`third_party/mediapipe` also guard their XNNPACK integration with the switch.
TFLite's default builtin resolver can still call
`MaybeCreateXNNPACKDelegate`, because `tflite_with_xnnpack_optional.cc` supplies
the existing null implementation when the delegate is not compiled in.

The functional change is loss of the optional XNNPACK inference acceleration
on this target. This does not disable the TFLite CPU interpreter or all WebNN
support. Performance and operator coverage still require testing with real
models; complete Electron and physical 3A4000 validation are separate checks.
Other delegate settings, including the separate OpenCL switch, are not changed
by this argument.

Validation included an independent review of the TFLite and WebNN fallback
paths. After regenerating the main Buster build, `gn desc` for
`//electron:electron deps --all` returned 17,788 labels with no XNNPACK
dependency. Both target and snapshot-host TFLite kernels and interpreter
dependencies remained present. The generated arguments recorded the disabled
delegate. Rerunning the original failed XNNPACK compiler command is not a
validation of this switch, because the intended result is removal of that
optional target from the build graph. Real model execution remains untested.
