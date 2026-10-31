# UOS 20 distribution audit

Run inside `uos-electron37-attempt`, after sourcing `env.sh`:

```sh
cd /work/electron37-attempt
source ./env.sh
python3 audit-dist.py
```

The default checks `src/out/UOS37/dist.zip`, verifies ZIP CRCs and required distribution files, and audits every ELF in the archive. It requires LoongArch ELF64 little endian, machine 258, old ABI flags `0x3`, and imported glibc versions no newer than 2.28. Executables require `/lib64/ld.so.1`. Shared libraries need no interpreter. RPATH/RUNPATH may contain only `$ORIGIN` or `${ORIGIN}` and subdirectories without `..`; absolute paths, empty search components and path-bearing `DT_NEEDED` entries fail. The JSON report lists all required shared libraries.

Evidence is written to `dist-audit/dist-audit.json` (override with `--report PATH`). Missing ZIPs, missing/empty required files, non-ELF required binaries and ABI failures return status 1. Successful static validation does not replace UOS runtime checks for window creation, GPU, sandbox and native modules.

While compilation is running, audit only completed files without opening the ZIP:

```sh
python3 audit-dist.py --elf \
  src/out/UOS37/libEGL.so src/out/UOS37/libGLESv2.so \
  src/out/UOS37/libffmpeg.so src/out/UOS37/libvk_swiftshader.so \
  src/out/UOS37/libvulkan.so.1
```

This writes `dist-audit/elf-audit.json` with `mode: "elf"`; it does not certify that the complete Electron distribution exists. `--zip PATH` audits another distribution archive. ELF content is never executed, and the build output is never modified.
