# Package a completed MIPS64EL build

The main Electron build must finish successfully first. The build wrapper records
that success in `.electron-build-success.json`, including hashes of the Electron
binary, GN configuration, build graph, and generated version information. A new
wrapper invocation clears the previous record before modifying the build.

For a manually managed build, run the recorder **only after observing Ninja's
exit code 0**. Use the source/output paths from the container that built it:

```bash
set -euo pipefail
export PATH="/work/src/buildtools/linux64:$PATH"
rm -f /work/out/.electron-build-success.json
ninja -C /work/out electron -j2
python3 /work/recipe/scripts/record-build-success.py \
  /work/src /work/out --ninja-exit-code 0

ninja -C /work/out -j2 \
  electron_dist_zip electron_ffmpeg_zip electron_chromedriver_zip \
  electron_mksnapshot_zip hunspell_dictionaries_zip \
  libcxx_headers_zip libcxxabi_headers_zip libcxx_objects_zip node_headers
```

The auxiliary targets can compile their own missing dependencies. Keep their
generation in the normal build stage. The collector below only reads existing
outputs and writes a new release directory outside the build output:

```bash
python3 mips64el/scripts/package-release.py \
  /absolute/path/to/out/mips64el \
  /absolute/path/to/releases/electron-37.2.2-mips64el \
  --max-glibc 2.28
```

The collector requires a matching success record and `dist.zip`. It checks ZIP
integrity, required runtime resources, the runtime version, and the packaged
Electron binary's hash against the completed build. It audits every runtime ELF
for little-endian MIPS64R2/N64, hard-float, the expected dynamic loader, and the
selected glibc symbol baseline. It rejects Chromium link-only sysroot stubs.

The destination contains available release assets, `runtime-audit.json`,
`release-manifest.json`, and `SHASUMS256.txt`. Missing auxiliary assets are listed
explicitly. Existing release directories are preserved; choose a new destination
for each collection attempt. Hardware execution is a separate validation step.

## Official Electron 37 targets

The names and source paths below come from `electron/BUILD.gn` in Electron 37.2.2.

| GN/Ninja target | Existing output under the build directory |
| --- | --- |
| `electron_dist_zip` | `dist.zip` |
| `electron_ffmpeg_zip` | `ffmpeg.zip` |
| `electron_chromedriver_zip` | `chromedriver.zip` |
| `electron_mksnapshot_zip` | `mksnapshot.zip` |
| `hunspell_dictionaries_zip` | `hunspell_dictionaries.zip` |
| `libcxx_headers_zip` | `libcxx_headers.zip` |
| `libcxxabi_headers_zip` | `libcxxabi_headers.zip` |
| `libcxx_objects_zip` | `libcxx_objects.zip` |
| `node_headers` | `gen/node_headers.tar.gz` |

`electron_symbols` is conditional on the official/symbol build configuration.
After generating real symbols, Electron's `script/zip-symbols.py --build-dir OUT`
creates `symbols.zip` and Linux `debug.zip`. The current `symbol_level=0`,
`is_official_build=false` configuration does not provide those payloads. The
collector skips missing or empty symbol/debug archives.

Cross builds can produce an x86_64 `mksnapshot` generator for MIPS snapshots. The
collector detects that executable architecture and names its archive
`mksnapshot-vVERSION-linux-x64-for-mips64el.zip`; it is recorded separately from
MIPS executables. The collected `ffmpeg.zip` follows this build's codec settings;
the upstream separately built free-codec FFmpeg variant is a distinct build.

This recipe disables optional V8 context prewarming. The runtime must include
the normal `snapshot_blob.bin`; `v8_context_snapshot.bin` and the context
snapshot generator are not expected. The ordinary cross `mksnapshot` remains
available. Upstream `electron/script/verify-mksnapshot.py` unconditionally calls
the context generator and therefore cannot validate this configuration unchanged.

Electron 37's Linux `electron_dist_zip` uses `electron/build/zip.py`, which writes
the build outputs directly into the ZIP without stripping them. Its Electron
binary should therefore match `out/electron` exactly.
