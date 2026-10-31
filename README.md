# Electron 37.2.2 LoongArch64 on UOS 20

This repository contains the reproducible recipe and patch records for building Electron 37.2.2 for the UOS 20 LoongArch64 old ABI from an x86_64 Docker host. The final gldfixed bundle has been statically audited and tested on a real UOS Loong64 desktop. A clean third-party rebuild has not yet been independently completed, so the release records both the working artifact and the remaining reproducibility conditions.

The layout and LoongArch release comparison were cross-checked against the community project [darkyzhou/electron-loong64](https://github.com/darkyzhou/electron-loong64). This repository keeps the UOS old-ABI adaptations and the gldfixed relink record separately.

The project uses the official Electron commit `102f740ec2fc8f34601c84b79ea1bf06042e8d00`, Chromium `5f45b4744e3d5ba82c2ca6d942f1e7a516110752`, Node `3567fa7d70fee8831ab2891e6940ca63be568b08`, and the LoongArch community/UOS patch series recorded under `research/electron-source-notes/`. The community source branch is 37.2.5; its patches were adapted to the 37.2.2 dependency revisions.

## What is in Git

The Git tree contains the Dockerfile, cross-toolchain scripts, source pins, patch manifests, the 11 local compatibility patches, the binutils relocation fix source, audit scripts, and Electron test programs. The Chromium checkout, generated objects, downloaded toolchains, sysroot binaries, caches, and build logs are excluded because the working directory is tens of gigabytes. They are referenced by SHA256 and supplied as Release assets or regenerated from their pinned sources.

Do not commit SSH credentials, proxy credentials, private network addresses, UOS user data, or unreviewed UOS binary packages. The UOS sysroot contains distribution binaries; redistribute it only where the applicable UOS/Deepin package licenses permit.

## Cross image

The image is an x86_64 build environment targeting UOS LoongArch64 old ABI (ELF flags `0x3`, glibc 2.28). It is suitable for C/C++ and CMake cross compilation. The Dockerfile layers the UOS target sysroot onto the pinned native builder base. Supply that base image locally with `BASE_IMAGE` (or load it from the matching release/registry image) and provide the three files under `inputs/`; the repository does not embed multi-gigabyte proprietary/redistributable base layers.

```bash
./scripts/build-image.sh
./scripts/smoke-build.sh
```

Use `UOS_BUILD_CPUS`, `UOS_BUILD_MEMORY`, `UOS_BUILD_MEMORY_SWAP`, `UOS_BUILD_PROXY`, `UOS_SSH_HOST`, `UOS_SSH_PORT`, and `UOS_SSH_USER` to configure local resources, networking, and optional UOS runtime validation.

## Electron build

The full build needs at least 24 GiB RAM, a large work volume, LLVM 20, Rust 1.88, the host runtime, the complete UOS development sysroot, and the pinned depot tools. Start from a clean clone, populate the Release inputs, then run the documented source sync, patch, GN, Ninja, linker, packaging, and audit steps. The gldfixed artifact was produced with the patched GNU binutils linker because the old UOS linker rejected a LoongArch type-44 relocation mask; the exact relink command is retained under `electron37-attempt/tools/`.

The final Electron bundle and SHA256 manifest are attached to the corresponding GitHub Release. It includes Chromium, libffmpeg, mksnapshot, chromedriver, Node headers, libcxx assets, and the test programs.

## Upstream notices

Electron is MIT licensed; Chromium and its dependencies carry their respective BSD, MIT, LGPL, GPL, and other notices. See `LICENSES/UPSTREAM-NOTICES.md` and the notices shipped inside the Electron bundle.
