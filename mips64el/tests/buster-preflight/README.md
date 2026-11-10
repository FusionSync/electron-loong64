# Buster / Loongson 3A4000 preflight

These tests build FFmpeg and Rust std from the prepared Electron 37.2.2 source, using the complete Buster target root. They then run small target programs under QEMU's Loongson-3A4000 CPU model.

The work directory must contain `src/` (synchronized and patched Chromium/Electron source) and `sysroot-buster/` (created by `sysroots/buster/build.sh`). Build the LLVM 20 cross image first. From the `mips64el/` recipe directory:

```sh
QEMU_MIPS64EL=/path/to/qemu-mips64el-static \
MIPS_IMAGE=electron37-mips64el:buster-clang20 \
NINJA_JOBS=4 \
  ./tests/buster-preflight/run.sh /absolute/path/to/mips-work
```

QEMU 8.2.2 was used for the recorded run. QEMU must support `-cpu Loongson-3A4000`; a real MIPS machine is not required for this preflight.

The script uses an independent `out/buster-preflight-clang20/` output, explicitly selects `/work/sysroot-buster` and Debian multiarch pkg-config paths, and unsets global target pkg-config variables for host-tool queries. It compiles with Clang 20, GNU target ld, Chromium's libc++ configuration and the vendored Rust compiler. The Rust linker uses Buster's libgcc_s explicitly because rustc requests `-nodefaultlibs`.

Tests cover:

- C: pthread creation/join, temporary-file I/O, and dynamic loading of GTK3, GLib, NSS, ALSA, DRM, X11 and udev.
- Rust: heap allocation, Vec/String, threads, AtomicU64, UTF-8 and temporary-file I/O, linked to the freshly built target std.
- FFmpeg: shared-library loading and H264/AAC/MP3 decoder initialization.

Logs and executables go to `WORK_DIR/reports/buster-preflight/`. The FFmpeg library and Rust std remain in the independent output directory. Full Electron linking, media playback, GUI/GPU/browser behavior and real 3A4000 hardware validation are outside this small test's scope.
