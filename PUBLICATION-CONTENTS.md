# Public publication layout

This repository contains the LoongArch64 old-ABI cross-build recipe, source pins, compatibility patch manifests, linker workaround source, audit scripts, and Electron test programs.

The large Chromium checkout, generated objects, caches, host runtimes, sysroots, and toolchains are intentionally not committed to Git. They are distributed as versioned Release assets or regenerated from pinned sources. The public repository must not contain credentials, proxy settings, private addresses, or unreviewed binary redistribution.

The final Electron bundle is attached to the matching Release with SHA256SUMS. The Docker image may be attached as an OCI archive where redistribution of the target sysroot is permitted; otherwise users build it from their own sysroot using `scripts/export-sysroot.sh`.
