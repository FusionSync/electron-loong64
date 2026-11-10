# FFmpeg: Linux MIPS64R2 / N64

These configs were generated from the pinned Electron 37.2.2 FFmpeg checkout,
using Chromium's `media/ffmpeg/scripts/build_ffmpeg.py` codec selections and
rewrites. They are new Linux configurations, built with Clang 20.1.8, the
MIPS64EL sysroot, and the N64 hard-float ABI. R6, MSA, DSP, and Loongson MMI
are disabled. Chrome branding includes AAC and H.264; Chromium branding keeps
the upstream restricted codec set.

Both configurations' `libavcodec.a`, `libavformat.a`, and `libavutil.a` were
cross-compiled successfully. The extra GN source lists come from those actual
object files, using Chromium's standard object filtering and existing basename
collision wrappers. The existing generated lists for other CPUs are preserved.
Chromium GN generation and `ninja -C <out> libffmpeg.so -j2` also passed,
including the bundled libc++, Opus, and final shared-library link. The resulting
library is ELF64 little-endian MIPS64R2, N64 hard-float, with no ISA extensions
or ASEs. Clang finds the sysroot's GCC 10 CRT and libgcc without extra driver
flags. Runtime playback awaits a real target.

Apply to an independent, synchronized source checkout after official Electron
patches and before running GN:

```bash
python3 patches/apply-mips64el-ffmpeg-patches.py /path/to/chromium/src
```

The helper verifies the FFmpeg `configure` and base GN file hashes, verifies all
bundled config checksums, and copies only changed files. It is idempotent.
`manifest.json` records the source revision, compiler, ABI, and source counts.

To regenerate inside the cross-build container:

```bash
python3 scripts/generate-ffmpeg.py /path/to/chromium/src \
  --sysroot /opt/mips-sysroot --llvm /opt/llvm20 --jobs 2 \
  --export-dir /path/to/recipe/patches/ffmpeg-mips64el
```

This calls the upstream recipe directly with explicit sysroot and compiler
overrides, builds both brandings, copies generated configuration files, and
updates the MIPS-only GN source import. It does not run Chromium GN or Ninja.
Keep the build idle while changing its source inputs. `--reuse-build` is only
for regenerating exports from successful build directories made by this exact
recipe. A Git worktree whose host metadata is unavailable inside the container
can pass `--ffmpeg-revision` with the revision recorded by the host.

The standalone configuration checks use GNU ld: this old sysroot's glibc CRT
objects have executable-stack notes rejected by LLD 20. The final Electron
build controls its linker and stack settings independently. The sysroot's
glibc compatibility limit remains the one documented in the main MIPS README.
