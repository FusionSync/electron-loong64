# Optional Blink context snapshot in the MIPS64EL build

The MIPS64EL bringup uses the standard GN option
`use_v8_context_snapshot = false`. It retains the normal V8 startup snapshot,
`snapshot_blob.bin`, and its x64 `mksnapshot` cross generator. It skips the
additional snapshot that preinitializes Blink DOM contexts.

This is a build configuration choice. It does not disable V8 snapshots, JIT,
WebAssembly, JavaScript execution, or DOM creation. The tradeoff is the loss of
an optimization for creating renderer contexts. Startup performance has not
been measured on a physical 3A4000.

## Source review

Reviewed the Electron 37.2.2 / Chromium 138.0.7204.100 source tree on
2026-11-10. The relevant upstream paths are:

| Path | Behavior |
| --- | --- |
| `tools/v8_context_snapshot/v8_context_snapshot.gni` | Declares `use_v8_context_snapshot` as a GN argument. The existing comment explains that macOS and Windows cross builds disable it because building Blink twice is slow. |
| `tools/v8_context_snapshot/BUILD.gn` | The context generation action and `v8_context_snapshot_generator` executable are inside `if (use_v8_context_snapshot)`. The generated buildflag follows the option. |
| `v8/BUILD.gn` | `v8_snapshot` still depends on `run_mksnapshot_default`; that action still depends on `mksnapshot($v8_snapshot_toolchain)`. Neither dependency is conditional on the Blink context option. |
| `gin/BUILD.gn` | The regular `snapshot_blob.bin` remains runtime data when V8 external startup data is enabled. |
| `electron/BUILD.gn` | The application adds its context snapshot dependency only when enabled. The mksnapshot package always depends on V8's normal generator and adds the Blink context generator conditionally. |

The runtime selects the ordinary path explicitly; it does not first try a
missing context file:

1. `content/app/content_main_runner_impl.cc`, `GetSnapshotType()`, selects
   `gin::V8SnapshotFileType::kDefault` when the buildflag is false.
2. `gin/v8_initializer.cc`, `GetSnapshotFileName()`, maps `kDefault` to
   `snapshot_blob.bin`.
3. Blink's `GetV8ContextSnapshotMode()` in
   `third_party/blink/renderer/bindings/core/v8/v8_initializer.cc` returns
   `kDontUseSnapshot`.
4. `V8ContextSnapshotImpl::CreateContext()` returns an empty context when
   context snapshots are disabled. `LocalWindowProxy::CreateContext()` then
   builds the ordinary DOM context with `v8::Context::New()` and the normal
   Window template. This path also exists for cases such as XML documents
   when context snapshots are enabled.

The separate Electron `load_browser_process_specific_v8_snapshot` fuse is
disabled by default in `electron/build/fuses/fuses.json5`. This recipe does
not turn it on.

## Regenerated build graph

The build restarted at **2026-11-10 19:55:07 UTC**. Its initial Ninja plan
contained **23,712 remaining actions**. A read-only traversal of the actual
`build.ninja` include/subninja graph completed at 19:59 UTC; it loaded 10,552
Ninja files and found no duplicate output definitions or unresolved dependency
variables.

| Check | Result |
| --- | --- |
| Reachable non-phony actions for `electron` | 47,775, including already-built outputs |
| Reachable host-toolchain Blink actions | **0** |
| Context generator definition in the loaded graph | Absent |
| `v8_context_snapshot.bin` output definition | Absent |
| `clang_x64_v8_mips64el/mksnapshot` reachable from `electron` | Present |
| `snapshot_blob.bin` reachable from `electron` | Present |
| Normal host mksnapshot dependency graph | 3,462 non-phony actions; no Blink actions |
| Scheduled buildflag generation | `USE_V8_CONTEXT_SNAPSHOT=false` |

This traversal follows only the Ninja files referenced by the regenerated
graph. Old object files or old Ninja files left on disk do not count as
dependencies. No GN or Ninja process was started for the inspection.

The inspected `args.gn` SHA-256 was
`eacbd122d1c0b6c05746185736c27c58a3596d0c8e8d5453a723d7cf8cf8b9aa`.
At this inspection the existing generated `buildflags.h` still contained its
previous value `1`: its regeneration was queued in the running build. The
new Ninja action explicitly schedules `false`. This graph inspection does
not claim that every affected object has already rebuilt with the new value.

## Packaging and validation

Electron's `dist_zip` template obtains its files from GN's generated runtime
dependency list. `electron/build/zip.py` packages that list; it does not read
the static comparison manifests under `electron/script/zip_manifests`.
Consequently the context file is removed through the same GN option and is
not an unconditional packaging input.

The actual regenerated lists were also inspected:

- `gen.runtime/electron/electron_dist_zip/electron_dist_zip.runtime_deps`
  includes `snapshot_blob.bin` and excludes the optional context binary and
  context generator.
- `gen.runtime/electron/electron_mksnapshot_zip/electron_mksnapshot_zip.runtime_deps`
  includes the x64-for-MIPS64EL `mksnapshot` and excludes the context generator.

The recipe requires `snapshot_blob.bin` in the runtime distribution. The
existing `electron/script/verify-mksnapshot.py` assumes that the optional
context generator exists and invokes it unconditionally. It must not be used
unchanged to validate a configuration with context snapshots disabled.
Normal `mksnapshot` generation and the recipe's runtime smoke tests are the
appropriate checks for this configuration.

This report establishes the source and generated graph behavior. It does not
claim a completed Electron runtime test or physical 3A4000 validation.
