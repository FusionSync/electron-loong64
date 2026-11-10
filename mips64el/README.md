# Electron 37.2.2 for Loongson 3A4000

**Experimental MIPS64EL cross build.** The container, target sysroot, Rust
standard library and FFmpeg have passed the checks below. The complete Electron
build is still in progress; a hardware-tested MIPS Electron release is not yet
available.

| Component | Choice |
| --- | --- |
| Build host | x86_64 Linux with Docker |
| Target CPU / ABI | 3A4000: MIPS64R2, little-endian, N64, hard-float |
| Electron | 37.2.2, with pinned Chromium and official Electron patches |
| C/C++ compiler | LoongNix LLVM/Clang 20.1.8; Chromium's in-tree libc++ |
| Target sysroot | Debian Buster, **glibc 2.28**, assembled from 558 locked official packages |
| Target startup/runtime | Buster GCC 8.3 CRT/libgcc; GNU binutils support layer |
| System page sizes | Runtime selection; 4, 16 and 64 KiB probes passed |

3A4000 is a MIPS CPU. This directory has its own images, source checkout,
outputs and sysroot; it does not modify the LoongArch64 build.

## What has passed

- GN generated all 33,703 targets with the Buster sysroot.
- Rust standard library: 64/64 actions; FFmpeg: 460/460 actions, including the shared-library link.
- QEMU's `Loongson-3A4000` CPU model ran C desktop-library, Rust and FFmpeg probes against glibc 2.28.
- The probes cover threads, atomic operations, UTF-8, file I/O, GTK/GLib/NSS/ALSA/X11 linking, and H.264/AAC/MP3 decoder initialization.
- [Actual FFmpeg decoding](reports/ffmpeg-decode.md) also passed: four H.264 frames and AAC/MP3 audio matched the generated pattern, sample counts and signal checks; a damaged H.264 stream was correctly rejected.
- ELF checks confirm MIPS64R2/N64/hard-float without MSA; the Buster probe artifacts require no symbol newer than GLIBC_2.28.
- [Marl fiber probes](reports/marl-fibers.md) preserve all eight N64 callee-saved floating-point registers and verify PIC entry/resume under QEMU at `-O0`, `-O2` and `-Os`, after correcting the upstream `$f30` save/restore.
- [V8 N64 register probes](reports/v8-n64-fprs.md) reproduce and fix incorrect floating-point preservation in native entry and caller-save paths at the same three optimization levels. These focused tests precede full Electron runtime validation.

See [Buster validation](reports/buster-preflight.txt) and
[final public image validation](metadata/public-buster-image-validation.json),
plus [page-size validation](reports/pa-page-sizes.md). These checks do not establish
that the complete Electron application works on a physical desktop.

[The V8 configuration review](reports/v8-3a4000-config.md) also checks the
MIPS64R2 JIT and host snapshot settings. The
[offline runtime smoke](tests/runtime-smoke/README.md) is ready to exercise
optimized JavaScript, deoptimization, scalar Wasm, threads, files and local HTTP
after the complete executable exists. Its recorded host Node result is a
check of the test script, not evidence of MIPS Electron execution.

## Use the prepared environment

The [mips64el-env-v1 prerelease](https://github.com/FusionSync/electron-loong64/releases/tag/mips64el-env-v1)
provides the tested Docker image and the separate glibc 2.28 sysroot. Download
all seven assets and follow the attached `README.txt` to verify them, merge the
three image parts and run `docker load`. These are build inputs, not an
Electron runtime release.

Get the maintained recipe from its independent branch:

```bash
git clone --branch mips64el-3a4000 --single-branch \
  https://github.com/FusionSync/electron-loong64.git
cd electron-loong64/mips64el
```

The imported image is `electron37-mips64el:buster-clang20`. Continue with
the source checkout and compilation steps below. To reconstruct the image
instead, use the following container build steps.

## Build the container

From this directory:

```bash
python3 scripts/fetch-inputs.py
python3 scripts/fetch-inputs.py --host-tools
./scripts/build-host-tools.sh
MIPS_IMAGE=electron37-mips64el:public-clang20 ./scripts/build-image.sh
./scripts/build-buster-image.sh
```

The final image is `electron37-mips64el:buster-clang20`. The intermediate
`public-clang20` image contains the host tools and the original Bullseye
bring-up sysroot; `Dockerfile.buster` removes that target root completely and
extracts the separate Buster root at `/opt/mips-sysroot-buster`.

The Buster script constructs the archive if it is not cached. Package URLs,
versions and SHA256 values are locked in
[`sysroots/buster/`](sysroots/buster/README.md). The sysroot includes its upstream
copyright files. Large archives and package caches stay outside Git.

Downloads honor standard `HTTP_PROXY`/`HTTPS_PROXY` environment variables;
the image wrappers forward them to Docker builds. `MIPS_IMAGE` selects a final
tag and `MIPS_BASE_IMAGE` selects the Buster layer's base image. The Ubuntu base
tag and host apt repositories remain moving inputs, so image byte identity is
not guaranteed.

## Create an independent source checkout

Choose an empty work directory; the bootstrap refuses to overwrite an existing
unmarked workspace:

```bash
mkdir -p /absolute/path/to/mips-work
docker run --rm -it \
  --user "$(id -u):$(id -g)" \
  -e HOME=/tmp -e npm_config_cache=/tmp/electron-npm-cache \
  -v /absolute/path/to/mips-work:/work/sources \
  -v "$PWD:/work/recipe:ro" \
  electron37-mips64el:buster-clang20 \
  python3 /work/recipe/scripts/bootstrap-source.py /work/sources
```

[`metadata/source-pins.json`](metadata/source-pins.json) fixes Electron,
Chromium and depot_tools. The bootstrap syncs the pinned dependencies, records
resolved revisions, applies official Electron patches, then runs hooks. Resume
an interrupted checkout with `--stage sync`, `--stage patches` or
`--stage hooks`; do not resync a tree after patching has begun.

**A complete clean network bootstrap through a finished Electron build has
not yet been verified.** The current bring-up initially reused cached source
dependencies. The public bootstrap does not depend on that local cache or a
LoongArch checkout.

## Compile Electron

```bash
NINJA_JOBS=8 BUILD_MEMORY=24g ./scripts/build-electron.sh \
  /absolute/path/to/mips-work/src \
  /absolute/path/to/mips-work/out/mips64el
```

The wrapper applies the architecture and FFmpeg patches, generates Ninja files
using [`gn-args.gn`](gn-args.gn), and builds Electron. Host tools remain x86_64;
target libraries use the explicit MIPS sysroot. LLVM compiles C++20 and bundled
Rust builds its target standard library from source. GNU ld reads indexed thin
archives. Patches also handle MIPS tail-call limitations, scalar libaom, and
runtime page-size selection.

The optional [XNNPACK inference accelerator](reports/xnnpack-backend.md) is
disabled because this Chromium version has no MIPS backend in its GN graph.
The standard TFLite CPU kernels and interpreter remain enabled.

Optional V8 context prewarming is also disabled with
`use_v8_context_snapshot=false`. This avoids compiling a second Blink for the
host. The normal V8 startup snapshot, JIT and DOM initialization remain enabled;
context creation has less prewarming. See [the configuration review](reports/v8-context-snapshot-option.md).

Use a large work volume. `BUILD_MEMORY` defaults to 24 GiB and `NINJA_JOBS` to
2; choose parallelism appropriate for the host. The settings and patches remain
experimental until the complete application has built and been tested.

## Validate and audit

With a synced source checkout, a separately built `sysroot-buster` in the work
directory, and QEMU supporting `Loongson-3A4000`:

```bash
./tests/buster-preflight/run.sh /absolute/path/to/mips-work
```

See the [probe instructions](tests/buster-preflight/README.md) for preparation.
Before packaging a completed runtime, audit every ELF in its unpacked directory:

```bash
python3 scripts/audit-dist.py /path/to/runtime \
  --max-glibc 2.28 --require-electron --output /path/to/elf-audit.json
```

The audit checks architecture, ABI, ISA extensions, dynamic symbols and glibc
versions. It rejects accidental x86_64 artifacts. A glibc version alone does not
prove OS compatibility: the target must also provide compatible GTK, X11, NSS,
ALSA, graphics, sandbox and other desktop libraries. Physical 3A4000 testing
remains necessary.

The [manual desktop app](tests/manual-desktop/README.md) is ready for that later
hardware check: animations, file selection, network requests, separate Bilibili
and Xiaohongshu windows, and diagnostics for blank pages. Only its JavaScript
syntax has been checked so far.

After the main build exits successfully, follow [the packaging instructions](PACKAGING.md)
to generate the official runtime and auxiliary archives. The collector checks
the successful build record and audits the runtime before writing checksums.

The earlier Bullseye records under `metadata/clang20-smoke-validation.json` and
`reports/rust-preflight.txt` document bring-up only; the selected release sysroot
is Buster. Electron, Chromium and every redistributed input retain their own
licenses and notices.
