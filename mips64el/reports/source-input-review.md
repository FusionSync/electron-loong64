# Source input review

Checked on 2026-11-10 against Electron commit
`102f740ec2fc8f34601c84b79ea1bf06042e8d00` and the ongoing MIPS64EL build.
This checks the cached bring-up tree's source modifications. A clean network
bootstrap is being tested independently; neither this review nor that bootstrap
alone establishes a successful complete Electron build.

## Official Electron patches

The ordered `git patch-id --stable` values from the applied commits match all
**210 nonempty official patches in 10 checked repositories**: Chromium,
BoringSSL, DevTools, FFmpeg, V8, Node, NAN, Perfetto, WebRTC and SQLite. Patch IDs
normalize whitespace and hunk line numbers; they do not establish byte identity
of the entire source checkout.

The audit found three omissions in the initial cache: Perfetto's Windows
`ssize_t` adjustment, SQLite's Windows export renaming, and WebRTC's Linux
PipeWire/X11 capture handling. The build was interrupted normally, these exact
official patches were applied, and the incremental build resumed at 20:24 UTC.
No replacement or locally rewritten patch was used for these three changes.

The cached tree has no usable source checkout for Squirrel.Mac, Mantle,
ReactiveObjC or the remote execution configs. Those four patch series were not
validated here. The selected target is Linux with remote execution disabled;
the public bootstrap fetches the pinned dependencies and applies the full
official patch configuration. Its results are a separate check.

## Public architecture adaptations

For each file touched by `apply-mips64el-source-patches.py`, the audit read the
owning repository's official-patch `HEAD`, replayed the public replacements in
memory, and compared the result byte for byte with the active source file.
The FFmpeg helper was also run in a new temporary directory populated with its
unmodified baseline files, and all installed files were compared.

All **39 source replacements and 56 checked files across nine repositories**
matched. Every tracked working-tree change in those repositories was covered
by the two public helpers. The check does not validate every untracked hook
output or dependency revision and does not substitute for a clean bootstrap.
