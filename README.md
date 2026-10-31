# Electron Loong64

Reproducible Electron 37.2.2 build for LoongArch64 Linux using the old ABI.

- **Verified build:** [v37.2.2-loong64](https://github.com/FusionSync/electron-loong64/releases/tag/v37.2.2-loong64)
- **Build inputs:** [toolchain-v1](https://github.com/FusionSync/electron-loong64/releases/tag/toolchain-v1)
- **Tested on:** UOS 1070 Loong64 physical desktop

| Item | Value |
| --- | --- |
| Target | LoongArch64 Linux, ELF flags `0x3` |
| Runtime baseline | glibc 2.28, plus compatible desktop libraries |
| Build host | x86_64 Linux with Docker |
| Tested on | UOS 1070 Loong64 physical desktop |
| Community patch base | Electron 37.2.5, adapted to the 37.2.2 source tree |

This repository contains the build recipe, patches, toolchain metadata, audit
scripts, and test programs. It does not contain the full Chromium checkout,
generated objects, or the large binary inputs.

## Download the verified build

The ready-to-run files are attached to the
[v37.2.2-loong64 Release](https://github.com/FusionSync/electron-loong64/releases/tag/v37.2.2-loong64).

The main file is `electron-v37.2.2-linux-loong64.zip`. It contains the
Electron/Chromium runtime, `libffmpeg.so`, V8 data, language files, sandbox
helpers, and graphics libraries. The same release also provides the unified
bundle, `chromedriver`, `mksnapshot`, FFmpeg, libc++, Node headers, and SHA256
manifests.

On a LoongArch64 machine, verify the downloaded assets before unpacking them:

```bash
sha256sum -c SHASUMS256.txt
unzip electron-v37.2.2-linux-loong64.zip -d electron-runtime
```

The runtime needs the old LoongArch ABI and glibc 2.28 or newer. A newer glibc
alone is not sufficient: GTK, X11, NSS, ALSA, DBus, graphics, and sandbox
libraries must also be available for the target desktop. The release was
verified on a physical UOS 1070 Loong64 desktop. The bundle contains the
manual web-page and local API test programs; their instructions are in
`electron37-attempt/electron37.2.2-linux-loong64-bundle/README.md`.

## Rebuild the cross compiler

This is the short validation path. It downloads the pinned inputs, loads the
x86_64 native builder image, builds the target cross image, and compiles small
C and C++ programs.

```bash
git clone https://github.com/FusionSync/electron-loong64.git
cd electron-loong64

FETCH_INPUTS=1 FETCH_BASE_IMAGE=1 ./scripts/build-image.sh
./scripts/smoke-build.sh
```

The final command writes `output/elf-audit.json`. A successful audit reports
LoongArch machine `258`, ELF flags `0x3`, interpreter `/lib64/ld.so.1`, and a
glibc symbol requirement no newer than the target baseline.

If GitHub downloads require a proxy, use the standard environment variables:

```bash
HTTPS_PROXY=http://proxy-host:port \
HTTP_PROXY=http://proxy-host:port \
FETCH_INPUTS=1 FETCH_BASE_IMAGE=1 ./scripts/build-image.sh
```

The two download steps may also be run separately:

```bash
./scripts/fetch-inputs.sh       # sysroot, GCC, and libstdc++
./scripts/fetch-native-base.sh  # x86_64 host-tools image
./scripts/build-image.sh
```

## How the image works

```text
x86_64 Docker host
        │ runs native build tools
        ▼
Ubuntu 18.04 host-tools image
        + GCC 8.3 LoongArch cross compiler
        + old-ABI target sysroot (glibc 2.28)
        ▼
LoongArch64 ELF output (flags 0x3)
```

The native image supplies x86_64 tools such as Python, Node, CMake, Ninja, and
the Electron build utilities. The cross layer supplies the LoongArch compiler,
linker, headers, startup objects, libraries, and pkg-config metadata. The
compiler runs on x86_64; the resulting Electron binary runs on LoongArch64.

The target sysroot is deliberately kept separate from the native image. This
prevents host libraries from being used accidentally during target linking and
makes the ABI boundary visible in the Dockerfile.

## Build Electron from source

The complete Electron build is much larger than the smoke test. Allocate at
least 24 GiB RAM and a large work volume. The source build also needs the
pinned LLVM 20, Rust 1.88, depot tools, host runtime, and the complete target
development sysroot.

The maintained pipeline is under [`electron37-attempt/`](electron37-attempt/):

- `sync.sh` synchronizes the pinned Electron and Chromium sources.
- `apply-source-patches.sh` and `apply-local-patches.sh` apply the architecture
  and old-ABI compatibility patches.
- `gn/README.md` documents the host/target GN toolchain split.
- `continue-build.sh` resumes the validated GN, Ninja, packaging, and audit
  stages.

The source pins and patch records are kept under
[`research/electron-source-notes/`](research/electron-source-notes/). The
current build uses official Electron 37.2.2 sources and adapts the community
Loong64 37.2.5 patch series to those dependency revisions.

## Inputs and redistribution

The large inputs are published separately in the
[toolchain-v1 Release](https://github.com/FusionSync/electron-loong64/releases/tag/toolchain-v1):

- old-ABI target sysroot;
- Loongson GCC 8.3 cross toolchain;
- matching target `libstdc++` development package;
- numbered parts of the x86_64 native builder image.

`fetch-inputs.sh` checks the three target files against
[`metadata/SHA256SUMS`](metadata/SHA256SUMS). `fetch-native-base.sh` checks
each image part and the reconstructed Docker archive before running
`docker load`. The binary inputs are excluded from Git because they are large
distribution packages and may have separate redistribution terms. Check the
applicable licenses before mirroring or republishing them.

## Repository layout

| Path | Purpose |
| --- | --- |
| `Dockerfile` | Adds the target sysroot and cross compiler to the native image |
| `scripts/` | Download, image build, smoke test, runtime, and audit commands |
| `toolchains/` | CMake target-toolchain definition |
| `electron37-attempt/` | Full Electron source-build pipeline and validation records |
| `research/electron-source-notes/` | Source pins and upstream/community patch records |
| `metadata/` | Checksums, target package inventory, and image requirements |
| `release-notes/` | Release-specific artifact notes |

## License and notices

Electron is MIT licensed. Chromium and its dependencies include their own BSD,
MIT, LGPL, GPL, and other notices. See
[`LICENSES/UPSTREAM-NOTICES.md`](LICENSES/UPSTREAM-NOTICES.md) and the notices
inside the released Electron bundle.

## Maintainer release workflow

After authenticating GitHub CLI, a verified build can be published with:

```bash
export GH_REPO=OWNER/electron-loong64
./scripts/publish-release.sh
```

The publisher uploads the bundle, checksum, and individual release assets. It
does not upload the sysroot or native builder layers.
