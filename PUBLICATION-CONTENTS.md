# Public publication layout

This repository contains the UOS 20 LoongArch64 old-ABI cross-build recipe, source pins, community/UOS patch manifests, local compatibility patches, linker workaround source, audit scripts, and Electron test programs.

The 58 GiB working directory is intentionally not committed as a Git tree. Chromium checkout, generated objects, caches, host runtimes, sysroots, and toolchains are distributed as versioned Release assets or regenerated from the pinned sources. The public repository must not contain SSH credentials, proxy credentials, private addresses, or unreviewed UOS binary redistribution.

The final Electron bundle is attached to the matching Release with SHA256SUMS. The Docker image is attached as an OCI archive when redistribution of the UOS sysroot is permitted; otherwise users build it from their own UOS sysroot using `scripts/export-sysroot.sh`.
