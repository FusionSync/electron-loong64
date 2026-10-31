# Electron 37.2.2 source and LoongArch patch investigation

This directory contains source metadata, adaptation patches and validation evidence. The real checkout is in `../../electron37-attempt/src`. All 19 configured repository patch series have now completed there, with 240 patch commits verified. The full Electron build has not yet completed.

## Pinned sources

* Electron official tag `v37.2.2` points through annotated tag object `8eb7b0b5841f0ed219fa9b2ff4d677a7eb2faae3` to commit `102f740ec2fc8f34601c84b79ea1bf06042e8d00`.
* Its `DEPS` pins Chromium `138.0.7204.100`, Node `v22.17.0`, and Yarn `1.22.22`.
* Official archive: <https://codeload.github.com/electron/electron/tar.gz/102f740ec2fc8f34601c84b79ea1bf06042e8d00>.
* Chromium Git source: <https://chromium.googlesource.com/chromium/src.git>, tag `138.0.7204.100`; GitHub mirror <https://github.com/chromium/chromium/tree/138.0.7204.100>.
* Closest community patch set: <https://github.com/darkyzhou/electron-loong64/tree/ca6a76b1580f45aed1f01640ba565a86e6fc3dc5>. This is branch `37.2.5`, originally based on Chromium `138.0.7204.168` and Node `v22.17.1`. There is no community `37.2.2` branch/release at the time of investigation.

`source-pins.json` records identifiers and local patch SHA-256 hashes. `upstream-v37.2.2-DEPS` is the actual upstream file fetched through the GitHub API.

## Patch application order

The 37.2.5 community workflow uses official `electron/electron`, not the newer `darkyzhou/electron` fork workflow. Both outer patch files apply inside `src/electron`. They install nested patch files and update their `.patches` manifests. Electron's subsequent gclient hook applies nested patches to Chromium and third-party checkouts.

For the actual 37.2.2 checkout:

```sh
cd src/electron
git apply --check /path/to/adapted-37.2.2-chromium.patch
git apply /path/to/adapted-37.2.2-chromium.patch
git apply --check /path/to/37.2.5-patches_electron.patch
```

The original `chromium.patch` first fails on the outer `patches/chromium/.patches` manifest: 37.2.5 has an extra macOS patch that is absent in 37.2.2. Full patch application later exposed differences inside the nested Chromium sandbox patch. `adapted-37.2.2-chromium.patch` fixes that outer manifest context, removes hunks for `RestrictSockSendFlags` and `IsSockSendOneMsg` (which do not exist in 37.2.2), and adapts the existing `IsAllowedGeneralIo` sendmsg/sendto guard while preserving other architectures. See `37.2.2-sandbox-adaptation.md` and its review diff. The resulting complete nested series has now applied successfully to the pinned source.

Do not blindly apply the community `electron.patch` build arguments for cross-compilation: its release/ffmpeg GN arguments set both target and host to the native `unbundle:default` toolchain, `/usr` LLVM, and `use_sysroot=false`. A UOS cross build must supply its separate host and target toolchains and UOS sysroot. Its actual Electron source hunk adds LoongArch to extension platform-info APIs; the patch also registers a Breakpad patch.

The underlying Chromium source already defines `clang_loong64`, `clang_x64_v8_loong64`, Rust target `loongarch64-unknown-linux-gnu`, and configurable external Rust paths. The community build used LLVM 20 and Rust 1.88.0 with `RUSTC_BOOTSTRAP=1`, `rustc_version="rustc 1.88.0 (6b00bc388 2025-06-23)"`, `rust_sysroot_absolute`, `rust_bindgen_root`, and bindgen 0.69.1. Its Chromium patch adds Rust `-Ccode-model=medium` for LoongArch and enables LSX by default.

## Validation completed

On 2026-10-27, the actual checkout completed all 19 patch series in `src/electron/patches/config.json`: Chromium, BoringSSL, DevTools, FFmpeg, V8, Node, NAN, Perfetto, Squirrel, Mantle, ReactiveObjC, WebRTC, reclient configs, SQLite, Skia, SwiftShader, XNNPACK, Breakpad and LSS. These include 146 Chromium patch commits and 240 commits overall. The UOS Crashpad, sandbox signal, LSS and older host ELF-header fixes are included.

`source-patch-verification.json` independently records the resulting base, HEAD and patch-stream SHA-256 for every repository. Read-only validation checked that each repository matches `../../electron37-attempt/logs/patch-state.json`, that its saved upstream ref matches its base, that the base is an ancestor of HEAD, and that the number of new commits equals its manifest length. All tracked files are clean when independently patched submodules are excluded, and no `git am` transaction remains.

`../../electron37-attempt/apply-patches-resumable.py` records each repository before and after applying its series. Completed repositories are skipped only when HEAD and patch content still match; interrupted or changed repositories stop for recovery. Its status check excludes child gitlinks because those repositories receive their own patch commits and checks. The surrounding pipeline holds `logs/build-pipeline.lock`. A crash after `git am` succeeds but before its completion record is saved deliberately stops for manual reconciliation on restart.

The `.gclient` override `custom_hooks = [{'name': 'patch_chromium'}]` suppresses only Electron's original patch hook. Inspected depot_tools code filters hooks by exact name and only adds a replacement when an `action` is present (`gclient.py`, lines 1026–1040); child dependencies do not inherit these custom hooks. The pipeline runs the resumable patch step before `gclient runhooks`, so other dependency hooks remain active.

`chromium138-selected-apply-check.log` is earlier evidence from checks against 14 of the original 73 nested Chromium source files. It is retained as historical evidence; the full repository verification above supersedes that limited patch-applicability result. Successful patch application and focused ABI probes do not establish that Electron compiles or runs in full.

`apply-check-37.2.2` and `chromium138-apply-check` are deliberately sparse validation fixtures. They are not build trees.

Electron's `yarn@1.22.22 install --frozen-lockfile` also completed, including its dependency postinstall steps. The original lockfile is byte-identical to the pinned Electron checkout. The build environment bypasses its proxy only for `registry.yarnpkg.com` (whose TLS handshake failed through that proxy) and enables Node's native proxy handling for GitHub downloads in postinstall scripts. See `../../electron37-attempt/logs/yarn-network-diagnosis.md` for the isolated failures, configuration fix, successful run and checksums. This validates the JavaScript dependency step, not the remaining gclient hooks or native Electron compilation.

## Actual UOS ABI incompatibility reproduced

The community README requires glibc >= 2.38 and targets new-world LoongArch. The actual target runs UOS Desktop 20, glibc 2.28 and Linux 4.19 with old ABI libraries.

Executed inside the real `uos-electron37-attempt` container against the exported UOS sysroot:

```sh
uos-c++ -std=c++17 -fsyntax-only /work/research/electron-source-notes/crashpad-newabi-header-probe.cc
```

The compiler reports three concrete incompatibilities in fields/types referenced by the community Crashpad patch:

* UOS `mcontext_t` has no `__extcontext` member.
* UOS headers do not define `FPU_CTX_MAGIC`.
* UOS headers do not define `struct sctx_info`.

See `crashpad-newabi-header-probe.log`. This is a focused ABI header probe, not an attempted compilation of the full Electron translation unit.

The layout also differs: actual UOS `ucontext_t` puts `uc_mcontext` before `uc_sigmask`, while the community patch puts the signal mask before the machine context and walks variable-size extension records. UOS declares fixed floating-point arrays instead. Changing the compiler alone does not fix these layout differences.

The similarly named `loongson/electron` branch `19-x-y-loongarch64` does not provide a verified old-ABI replacement: its current commit `a16ca1d02de04c28236ea2107bf59bf9d0341e55` from 2022-06-16 also uses `__extcontext`, `sctx_info`, and `FPU_CTX_MAGIC`. Its fetched Crashpad patch is retained for comparison. No safe field-for-field mapping is claimed.

## UOS Crashpad adaptation implemented and checked

`uos20-crashpad-oldabi.patch` is a real five-file patch for **Chromium's source root after the community LoongArch patch**. It is specific to this UOS 20 sysroot and kernel ABI. It replaces the previously identified incompatible context readers, register layout and assembly offsets.

The runtime probe `uos-signal-ptrace-probe` ran on the actual target and established:

| Field | UOS kernel/runtime value | Community patch expectation |
| --- | ---: | ---: |
| Signal PC offset | 64 | 176 |
| Signal GPR array offset | 72 | 184 |
| Signal FPU array offset | 384 | Extension records |
| Ptrace PC offset | 256 | 264 |
| Ptrace GPR bytes | 360 | 360 |
| Ptrace FPU bytes | 272 | 272 |

The actual target's glibc `mcontext_t` declares FPU offset 352, but a known value loaded into FPU register 24 was present at kernel offset 384 and absent at libc offset 352. The patch therefore uses the kernel `sigcontext` layout and validates its offsets against kernel headers. It does not assume that matching struct sizes imply a matching PC offset.

The five changed files are:

* `snapshot/linux/signal_context.h`: kernel signal layout and static offset assertions.
* `snapshot/linux/exception_snapshot_linux.cc`: read fixed FPU slots, use their low 64 bits, and handle the USED_FP bit.
* `util/linux/thread_info.h`: remove the new-ABI orig_a0 slot, use UOS user_fp_state, and assert PC/FPU offsets.
* `util/linux/ptracer.cc`: request the exact FPU context size.
* `util/misc/capture_context_linux.S`: write PC/GPR at the UOS offsets.

`uos20-crashpad-patch-check.log` records a successful exact-source `git apply --check`. Actual patched headers compile against the exported sysroot.

`generate-crashpad-runtime-probe.py` extracts the production patched `ReadContext` function and CPU conversion functions verbatim and compiles them with the actual patched headers and context-capture assembly. A small local-memory adapter replaces the rest of Chromium's process-memory infrastructure for this focused test. On the real UOS target it reports:

```text
actual_patched_signal_reader_pass=1
actual_patched_capture_assembly_pass=1
actual_patched_ptrace_types_pass=1
exit=0
```

Full details are in `crashpad-oldabi-runtime-probe-target.log`. This verifies the affected context decoding and assembly with real target signals and ptrace register sets; it does not claim that the complete Crashpad or Electron build has finished.

The real checkout integrates this as `src/electron/patches/chromium/uos20_crashpad_oldabi.patch`, immediately after `loong64_support.patch` in the Chromium manifest. `../../electron37-attempt/apply-source-patches.sh` reproduces these registrations and excludes the community's native-only GN argument files from this cross build.

The same pipeline also registers `uos20-sandbox-signal-oldabi.patch`, `uos20-lss-oldabi.patch` and `breakpad-old-host-elf-constant.patch`. Real target probes confirmed the UOS 128-signal ABI, 16-byte kernel signal mask, old `clone` TLS/child-TID argument order, and patched LSS signal/clone operations. The actual Breakpad `MemoryMappedFile` implementation ran on the target, and its full `dump_symbols.cc` compiled on the older host after correcting the `EM_LOONGARCH` fallback guard. See `oldabi-followup/README.md` for the before/after results and scope.

## Disabling Crashpad is not an existing Linux build switch

Exact Electron 37.2.2 `BUILD.gn` has Linux Crashpad client dependencies at line 648 and an unconditional Linux handler data dependency at line 1237. Exact Chromium 138 `components/crash/core/app/BUILD.gn` similarly adds `crashpad_linux.cc` and the handler for Linux at lines 86-88, and declares the handler for Linux at line 238. There is no surrounding `enable_crashpad` option in these source paths. A runtime switch would not stop the compilation of those dependencies. Removing crash reporting would require source changes across these paths and callers; the supplied UOS patch instead repairs the verified ABI issue.

## Accessible official depot_tools archive

The official archive <https://storage.googleapis.com/chrome-infra/depot_tools.zip> responded HTTP 200 and contained 31,259,643 bytes at the time of inspection. Its ZIP central directory was read using HTTP ranges and confirmed Linux `gclient`, `fetch`, `vpython3`, `update_depot_tools`, their Python scripts, and a complete `.git` directory. See `official-depot-tools-zip-files.txt`.

The inspected immutable object generation is `1793098256120784`, with MD5 `ab3a5afae29373267fbf0ccd4a8b7650`; an immutable URL can append `?generation=1793098256120784`. The archive can be extracted on Linux, retaining or restoring executable bits as needed. Set `DEPOT_TOOLS_UPDATE=0` initially if automatic Git self-update would hit an unavailable googlesource connection.

`electron/depot_tools` on GitHub was checked and is empty, so it is not a usable mirror. The googlesource Gitiles archive timed out from this environment. The user-provided HTTP proxy later became usable after the parent corrected its selected network node; subsequent exact source files were fetched through that proxy.
