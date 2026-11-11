# Clean source bootstrap validation

On 2026-11-10, the public source preparation flow completed in a new,
independent workspace: fresh network sync, the complete official Electron patch
stack, hooks, both public MIPS adaptation helpers, and a separate GN graph.
**This check did not compile or run Electron.**

The [machine-readable record](../metadata/clean-bootstrap-validation.json)
contains the pinned revisions, patch input hashes, file comparisons, host tool
versions and GN results. Raw logs remain local.

| Check | Observed result |
| --- | --- |
| Electron / Chromium / depot_tools | Exact pinned commits |
| Official Electron patches | All 14 repositories; 228 applied commits |
| Hooks | Passed, including frozen Yarn dependencies and required generated inputs |
| Public source helper (original run) | 39 replacements installed in the fresh checkout |
| ATK 2.30 compatibility follow-up | 9 additional replacements applied in an independent clean checkout; the resulting accessibility source matches the main-build file by SHA256 |
| Public FFmpeg helper | 22 files installed from the checked payload |
| Comparison with the ongoing main build | All 57 helper files and all four checked host binaries have identical SHA256 values |
| Independent GN generation | Exit 0; 27,588 targets from 4,150 files; unused arguments rejected |
| Ordinary V8 startup snapshot | Electron depends on the action declaring `snapshot_blob.bin` as output and runtime data |
| Optional context prewarming | Disabled; no context snapshot generator in Electron's dependencies |

The checkout used [the public pins](../metadata/source-pins.json), a recipe copy,
and newly created npm/vpython caches. It did not mount or hardlink an existing
source checkout or mutable dependency cache. The already-built Buster recipe
image supplied the cross compiler and GLIBC 2.28 sysroot; rebuilding that image
was outside this check. An initial network transport failure was resumed in the
script-marked workspace without substituting cached source.

Source preparation and GN each used one CPU and a 3 GiB container memory limit.
GN ran with networking disabled and generated into an empty, separate output
directory. This limit does not describe the resources needed for a full
Electron build. The complete validation directory used about 27.7 GiB.

The GN dependency check found 12,173 transitive Electron targets.
`//tools/v8_context_snapshot:buildflags` remains as a configuration header target;
it does not build the disabled context snapshot generator. Normal V8 startup
snapshot generation remains enabled in the graph. The snapshot file itself was
not built or executed during this validation.

The checked host binaries are GN 2237, Chromium Rust 1.88.0-dev and its matching
`rustc_driver` library, and Chromium's host Node v22.11.0. Their SHA256 values and
the executable tools' version output match the ongoing build's copies. Host
Node is distinct from the pinned target Node source version v22.17.0.

This establishes that the public source preparation and GN steps work without
the initial source cache. The original clean bootstrap's source-helper stage
covered 39 replacements; the 9 ATK replacements were validated afterward in a
separate clean checkout and matched the main-build accessibility source. The
current public helper therefore covers 48 replacements across the same 57 files.
It does not establish a successful complete Electron build, GUI, sandbox, GPU,
media playback, or physical 3A4000 execution. The comparison covers the
documented helper files and host tools, not the entire main build input tree.
Untracked Python `__pycache__` files are generated caches, not recipe inputs.
Official patched commit IDs can vary with git-am committer timestamps; the
pinned bases and patch mbox hashes identify the patch inputs.
