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
- ELF checks confirm MIPS64R2/N64/hard-float without MSA; the Buster probe artifacts require no symbol newer than GLIBC_2.28.

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

After the main build exits successfully, follow [the packaging instructions](PACKAGING.md)
to generate the official runtime and auxiliary archives. The collector checks
the successful build record and audits the runtime before writing checksums.

The earlier Bullseye records under `metadata/clang20-smoke-validation.json` and
`reports/rust-preflight.txt` document bring-up only; the selected release sysroot
is Buster. Electron, Chromium and every redistributed input retain their own
licenses and notices.
