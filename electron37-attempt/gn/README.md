# Electron 37.2.2 cross-build GN configuration

The complete `gn gen --fail-on-unused-args` preflight passed in the existing
container: 33,534 targets from 4,149 files. Source synchronization and official
hooks are complete. Vendor LLVM20 compilation, runtime inspection, and the
Electron link remain pending; GN generation does not execute the compiler.
No source-content changes were made for this configuration. Detailed results
and native SDK package replay commands are in `host-audit/README.md`.

## Use inside `uos-electron37-attempt`

```sh
source /work/electron37-attempt/env.sh
cd /work/electron37-attempt
python3 gn/prepare-facades.py
mkdir -p src/out/UOS37
cp gn/args.gn src/out/UOS37/args.gn
cd src
gn gen out/UOS37 --fail-on-unused-args
ninja -C out/UOS37 -j1 electron
```

Run `prepare-facades.py` again after LLVM extraction. It makes real directories
and individual runtime-library symlinks; additional verified LoongArch runtime
archives can be placed into the facade without modifying vendor files. It
refuses to overwrite a pre-existing file or a differing symlink.

## Toolchain separation

The exact Chromium 138.0.7204.100 files already provide everything needed for
architecture selection; **no custom GN toolchain/config file inside `src` is
required** for this draft:

| Purpose | Existing GN toolchain | Compile SDK |
| --- | --- | --- |
| Electron / Chromium | `//build/toolchain/linux:clang_loong64` | `target_sysroot=/work/electron37-attempt/sysroot-complete` |
| Ordinary build tools, Rust proc macros | `//build/toolchain/linux:clang_x64` | Container's native x86_64 headers/libs |
| Electron's JS-to-C text generator | Explicit `electron_js2c_toolchain=//build/toolchain/linux:clang_x64` | Container's native x86_64 headers/libs |
| V8 snapshots / Torque generators | `//build/toolchain/linux:clang_x64_v8_loong64` | Container's native x86_64 headers/libs |

`build/config/BUILDCONFIG.gn` chooses the first two. V8 commit
`e5b4c78b54e8b033b2701db3df0bf67d3030e4c1` automatically chooses the third;
the pinned source is saved in `evidence/v8-snapshot_toolchain.gni`.
The generator is an x86_64 executable with the LoongArch simulator enabled.
It must run in the container during snapshot creation. Do not force V8's
snapshot toolchain to the LoongArch target toolchain.

`build/config/sysroot.gni` applies an explicit `target_sysroot` only when both
CPU and OS match the target. `use_sysroot=false` prevents automatic Debian host
sysroot selection but does not disable that explicit target sysroot. The global
`sysroot` arg must remain unset. The native container SDK includes glibc 2.27
headers/start files; generated host tools are initially linked against those
native libraries. Its ability to compile all Chromium host tools is still to
be proven by the build. The separate `host-runtime` snapshot is a runtime
closure for downloaded host tools, **not a host compilation sysroot**. If a
host-source compatibility failure requires a newer complete x64 sysroot, its
generated tools also need the matching runtime/loader; changing the sysroot
alone would be insufficient.

`compiler-driver.py` supplies the vendor LLVM through `clang_base_path`. It
reads `--target` / `-target`, including GNU response files, to select target
flags, and preserves the original response files for Clang. An invocation with
no target explicitly uses x86_64. The target gets UOS C headers, GCC startup
objects, GNU ld, libgcc and `/lib64/ld.so.1`; it never gets GCC 8 C++ headers.
Chromium builds its own libc++ for both target and host. The driver refuses
a UOS sysroot on an x86_64 command. It does not strip unknown compiler flags.
`-no-canonical-prefixes` preserves Clang's own executable path when running
through the explicit host loader, allowing `-fintegrated-cc1` to work. The
actual Clang21 SDK probe that exposed this issue is recorded in
`host-audit/README.md`; vendor20 compilation remains a separate check.

`build/toolchain/gcc_toolchain.gni` forwards `{{ldflags}}` through
`build/rust/rustc_wrapper.py` as `-Clink-arg=...`, so LoongArch Rust executable
links also carry `--target=loongarch64-linux-gnu` to this same facade. Rust proc
macros use the x64 toolchain. The installed vendor Rust reports
`rustc 1.88.0 (4ed61557a 2025-06-27)`, LLVM 18.1.7; ThinLTO is disabled to avoid
mixing Rust LLVM18 bitcode with Clang LLVM20. The extra
`rustc_literal_escaper` stdlib entry is required by the actual vendor bundle
and was established by the toolchain agent's extracted-stdlib compilation.

`pkg-config` recognizes the target from the per-process `PKG_CONFIG_LIBDIR`
that Chromium's `pkg-config.py` sets. It adds all three UOS pkgconfig directories
and clears external `PKG_CONFIG_PATH`. Native queries use native pkg-config.
This also handles the V8 simulator toolchain, which is distinct from
`host_toolchain` in GN. `system_libdir` alone would omit UOS `usr/lib/pkgconfig`;
using the container's unconditional `uos-pkg-config` would misroute native
queries. Specifying this custom wrapper also disables Chromium's Debian-only
cached pkg-config results. The wrapper's optional target root override is
`UOS_ELECTRON_SYSROOT`, not the older image's `UOS_SYSROOT`.

## Required support files and remaining checks

The added configuration is exactly this `args.gn`, the compiler/tool facade,
the pkg-config wrapper, and the bindgen facade; the separate community and
UOS20 Crashpad source patches remain necessary and are managed by the parent
attempt scripts. No native `linux/unbundle` toolchain is used.

* **Compiler runtime archives:** after the community patch,
  `build/config/clang/BUILD.gn` expects
  `clang-facade/lib/clang/20/lib/linux/libclang_rt.builtins-x86_64.a` and
  `libclang_rt.builtins-loongarch64.a`. `runtime_library` in
  `build/config/compiler/BUILD.gn` adds builtins unconditionally for Clang.
  Rust coverage-enabled links may also request matching `profile` archives.
  Check actual package contents, ELF machine and LoongArch old-ABI flags;
  the compiler's ability to emit LoongArch objects does not prove those
  archives are included. Do not substitute upstream ABI2 archives or empty
  archives. The non-community original GN uses triple subdirectories instead,
  which is why the final patched tree must be used for this check.
* **Linker:** initial `use_lld=false` selects GNU ld and naturally avoids
  Chromium's `-Wa,--crel,--allow-experimental-crel` block at
  `build/config/compiler/BUILD.gn:635`. The facade also supports explicit
  `-fuse-ld=lld`, using a host-runtime launcher for `ld.lld`. Before changing
  `use_lld`, run both plain LLD and LLD+CREL binaries on the UOS target. GNU
  ld is a compatibility baseline and its final Electron link memory use is
  still an empirical question.
* **Bindgen:** `bindgen-facade/bin/bindgen` launches the Chromium-downloaded
  `src/third_party/rust-toolchain/bin/bindgen` with the isolated host loader;
  `bindgen-facade/lib` points to vendor LLVM20 libraries. The downloaded
  bindgen 0.69.4 has loaded Chromium's supplied libclang21, parsed a UOS header,
  and passed a Rust/C structure-layout comparison on UOS. Repeat that probe
  with the final vendor20 libclang after installation; see `../bindgen-audit`.
  `UOS_BINDGEN_BIN` allows an explicitly installed fallback; no stub is used.
* **libffi:** the complete GN preflight does not load the optional bundled-GLib
  libffi configuration, so `use_system_libffi` is not a valid argument in this
  graph and has been removed. Native libffi development files remain installed
  for the host SDK, and the UOS sysroot retains its matching target library.
* **Compiler flags:** Chromium pins a newer LLVM than the vendor LLVM20.
  Disabling Chrome plugins and warnings-as-errors is deliberate, but any
  unsupported substantive compiler option still requires an evidenced fix.

## Validation status

The scripts pass Python parsing and Bash syntax checks. Command-selection
checks cover host, target, nested response files, and rejecting a target
sysroot on a host invocation. The complete strict GN preflight passed, and
`host-audit/generated-toolchains.json` verifies target Electron, native js2c,
and the x64 V8 LoongArch simulator settings in the actual generated Ninja
files. `host-audit/gn-args-resolved.txt` records accepted argument values.

Native SDK probes with the downloaded **Clang21** passed C compilation,
linking, and execution, plus C++20 syntax checks of Chromium libc++ headers
and four implementation files. Vendor **LLVM20** compiler validation and the
Electron build remain separate work after its download. Older dispatch and
pkg-config evidence remains in `evidence`; no result here implies Electron
has finished building.
