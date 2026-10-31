# Electron Loong64

This repository contains the reproducible recipe, source pins, compatibility patches, audit tools, and test programs for building Electron 37.2.2 for LoongArch64 Linux with the old ABI from an x86_64 Docker host. The layout and release format were cross-checked against the community project [darkyzhou/electron-loong64](https://github.com/darkyzhou/electron-loong64).

The published binary targets LoongArch64 ELF flags `0x3` and uses glibc 2.28 as its minimum runtime baseline. A distribution with glibc 2.28 or newer can run the binary when its desktop dependencies (GTK, X11, NSS, ALSA, DBus, GPU/graphics libraries, and sandbox support) are compatible. Newer glibc alone does not change the LoongArch ABI requirement. The current release was tested on a physical UOS 1070 Loong64 desktop.

The source pins are the official Electron commit `102f740ec2fc8f34601c84b79ea1bf06042e8d00`, Chromium `5f45b4744e3d5ba82c2ca6d942f1e7a516110752`, and Node `3567fa7d70fee8831ab2891e6940ca63be568b08`. The community 37.2.5 patch series is recorded under `research/electron-source-notes/` and adapted to the Electron 37.2.2 dependency revisions used by this build.

## Repository contents

The Git tree contains the Dockerfile, cross-toolchain scripts, source pins, patch manifests, local compatibility patches, the linker relocation fix, audit scripts, and Electron test programs. The Chromium checkout, generated objects, downloaded toolchains, sysroots, caches, and build logs are excluded because they occupy tens of gigabytes. They are referenced by SHA256 and supplied as release assets or regenerated from pinned sources.

Do not commit credentials, private network addresses, local user data, or unreviewed binary packages. The target sysroot contains distribution binaries; redistribute it only where the applicable package licenses permit.

## Cross-build image

The image is an x86_64 build environment targeting LoongArch64 old ABI. It is suitable for C/C++ and CMake cross compilation. The Dockerfile layers the target sysroot onto the pinned native builder base. Supply that base image locally with `BASE_IMAGE` (see `metadata/base-image-requirements.md`) and provide the three files under `inputs/`; the repository does not embed multi-gigabyte base layers or sysroot archives.

```bash
./scripts/build-image.sh
./scripts/smoke-build.sh
```

The full Electron build needs at least 24 GiB RAM, a large work volume, LLVM 20, Rust 1.88, the host runtime, the complete development sysroot, and the pinned depot tools. Start from a clean clone, populate the release inputs, then run the documented source sync, patch, GN, Ninja, linker, packaging, and audit steps. The final link used the recorded GNU binutils fix for the LoongArch type-44 relocation mask; the exact relink command is retained under `electron37-attempt/tools/`.

The final Electron bundle and SHA256 manifest are attached to the corresponding GitHub Release. It includes Chromium, libffmpeg, mksnapshot, chromedriver, Node headers, libcxx assets, and the test programs.

## Upstream notices

Electron is MIT licensed; Chromium and its dependencies carry their respective BSD, MIT, LGPL, GPL, and other notices. See `LICENSES/UPSTREAM-NOTICES.md` and the notices shipped inside the Electron bundle.

## Publish a verified release

After installing and authenticating the GitHub CLI, set the destination explicitly and run:

```bash
export GH_REPO=OWNER/electron-loong64
./scripts/publish-release.sh
```

The script uploads the unified bundle, its checksum, and the individual assets under `release-assets-fixed/`. It never uploads the sysroot or native builder base layers. Set `RELEASE_TAG` or `ASSET_DIR` when publishing a different verified build.
