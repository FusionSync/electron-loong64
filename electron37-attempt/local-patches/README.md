# Saved UOS Electron compatibility changes

These ten patches preserve the local Chromium and Electron Node changes used by the ongoing
Electron 37.2.2 cross build. They were exported without changing source files,
their timestamps, the Git index, or the running build.

`manifest.json` records the exact repository baseline HEADs after the existing
Electron/community/UOS repository patch series, the ordered patch list, and
SHA-256 hashes of each patch and each source file before/after application.
`SHA256SUMS` covers the patches and manifest. The first seven, ninth, and tenth patches use the
default Chromium repository `src` at
`7c3d04f8dfa78f36adb52f6f7ef11f885287f495`. The eighth overrides `repository`
and `baseline_head` for `src/third_party/electron_node` at
`d7aff0d5cfc015a05e99bc9c00cf9e9679d26cd1`. Source hashes and Git operations
are checked against each patch's repository.

Restore in this order inside the configured build container:

1. Restore the pinned source/dependency revisions and build tools/sysroots.
2. Run `apply-source-patches.sh`, then `apply-patches-resumable.py` to complete
   the recorded repository patch series.
3. Run `bash ./apply-local-patches.sh --check` to verify all hashes, baselines,
   and forward/reverse applicability without changing source or Git index.
4. Run `bash ./apply-local-patches.sh` to apply missing local patches in manifest
   order. Already applied patches pass `git apply --reverse --check` and are
   left untouched. The script refuses unknown source content or another HEAD.
5. Run hooks, GN, and Ninja through `continue-build.sh`; its next invocation
   restores these local patches between repository patches and hooks.

The changes cover regular GNU archives, vendor LLVM20 bindgen arguments,
Rust GNU link groups/host GSSAPI headers, isolated host Node selection/version
checks, UOS ATK 2.30 compatibility, the old assembler's return instruction,
and target C/C++/Rust long calls. The ATK change guards interfaces added
in ATK 2.32 and roles added in 2.34, with existing-role fallbacks.

The restore script marks these files `assume-unchanged` only in apply mode,
matching the existing build's convention so the repository patch runner can
resume. Git status alone therefore does not describe these local modifications;
use the manifest, explicit patch files, and `--check` when reviewing them.
New edits require exporting/reviewing updated patches and hashes before retry.

The patches depend on mounted `host-runtime/`, `host-gssapi-include/`, toolchain
directories, and `sysroot-complete/`. Preserve those with this workspace when
migrating. The host `gperf` and GSSAPI header additions are now matched to
retained local packages, with an independent offline restore script under
`../gn/host-audit/local-additions/`.
The container's additional host SDK setup is recorded separately in
`../gn/host-audit/setup-host-sdk.sh`.

The seventh patch spells the LoongArch syscall trampoline return as
`jirl $zero, $ra, 0`, accepted by the old-ABI LLVM20 assembler. The `2:`
seccomp IP marker still immediately follows `syscall 0`. The real syscall
object compiled successfully; disassembly confirms return encoding
`20 00 00 4c`, matching the compiler-generated returns in the same object.
Runtime validation on UOS remains pending.

The eighth patch adds `-Xclang -mcmodel=large` only to libuv's private C
configuration when `is_clang && current_cpu == "loong64"`. It does not
propagate to consumers or x86_64 host targets. UOS supplies `pthread_atfork`
as a hidden symbol in `libc_nonshared.a`; its final location in Electron
exceeded the short branch's ±128 MiB range. Vendor LLVM20's medium model
still emitted a short call, while its large model emitted a long call in
the diagnostic probe. The full Electron link and runtime checks must still
validate the resulting build.

`verification.json` preserves the earlier six-patch verification record;
it is not evidence that the later patches passed a complete Electron build.

The first patch now also selects vendor `large` for all LoongArch Clang C/C++
targets. Repeated full-link failures showed that medium emits B26 short calls
throughout Electron/Chromium, not just libuv. The ninth patch selects large for
LoongArch GN Rust crates. Neither changes x86_64 host code models. Prebuilt Rust
standard libraries are outside those GN compile rules and require separate
handling; these patches alone do not establish complete-link success.

The tenth patch disables `PA_MUSTTAIL` only for LoongArch. The vendor LLVM20
large-model backend aborts while lowering PartitionAlloc's indirect dispatch
tail calls; an ordinary call preserves dispatch behavior with a small stack
frame cost. Other architectures retain the original `clang::musttail`
attribute. A temporary overlay compiled the failing source successfully with
the large model; the complete Electron build still provides the final check.
