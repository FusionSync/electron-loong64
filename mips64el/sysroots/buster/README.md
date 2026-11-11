# Debian Buster MIPS64EL sysroot · glibc 2.28

The MIPS64EL build uses a complete, independent Buster target root. All target headers, libraries and CRT objects come from the same official Debian archive. It supports the **MIPS64R2 / little-endian / N64 / hard-float** baseline used for Loongson 3A4000.

Standard MIPS64R2 instructions are a conservative baseline for 3A4000; optional
LoongISA extensions are not required. A Debian sysroot does not itself cause
illegal instructions by omitting those extensions. The relevant compatibility
checks are the emitted ISA, endianness, N64 floating-point ABI, loader and
library versions. This root has passed the QEMU checks below; compatibility
with a particular desktop distribution still needs testing on that system.

| Item | Locked input |
| --- | --- |
| libc | glibc 2.28-10+deb10u1 |
| Target GCC support files | GCC 8.3 CRT, libgcc and libstdc++ development files |
| Desktop libraries | GTK3, GLib, NSS, ALSA, DRM, X11, udev and their dependencies |
| Package closure | 558 packages, 204.3 MiB downloaded |
| Extracted root | About 945 MiB, including copyright notices |
| Packaged root | About 202 MiB, xz archive |

## Use the packaged root

`inputs/debian-buster-mips64el-glibc2.28-sysroot.tar.xz` is an image input, kept outside Git. Its SHA-256 is:

```text
ed4c9dddc58afd35be6b3f8faef5359603f64ab9cca1893c4408a470e2c0af94
```

From the `mips64el/` directory, run `sha256sum -c sysroots/buster/SHA256SUMS` to verify both the archive and package lock.

The separate `Dockerfile.buster` extracts it to `/opt/mips-sysroot-buster`. The compiler runs on x86_64; this root supplies the **target** ABI files. Clang can discover the Buster GCC8 CRT/runtime in the root automatically. GN uses `system_libdir = "lib/mips64el-linux-gnuabi64"` because this root keeps Debian's standard multiarch paths.

## Rebuild from public packages

From the `mips64el/` recipe directory on an x86_64 Linux host:

```sh
./sysroots/buster/build.sh /absolute/path/to/mips-work
./sysroots/buster/pack.sh \
  /absolute/path/to/mips-work/sysroot-buster \
  ./inputs/debian-buster-mips64el-glibc2.28-sysroot.tar.xz
```

Requires Python 3, curl, dpkg, dpkg-deb, tar and xz. `build.sh` stores the package index and cache in the work directory, verifies every SHA-256, and extracts the pinned package set. It runs neither target programs nor package installation scripts. Absolute symlinks become equivalent relative links inside the root. Use `build.sh WORK_DIR --resume` to repeat extraction for the identical manifest; a different recipe cannot reuse a nonempty destination.

Generated JSON state has explicit mode 0644, independent of host umask. A full second extraction under umask 0022 matched all 31361 file/directory/link entries of the original umask 0002 root after stamp normalization, and both normalized archives had the identical SHA-256 above. See [the reproducibility record](provenance/reproducibility.json).

`pack.sh` checks the completed manifest stamp, normalizes tar entry order/timestamps/ownership, compresses with `xz -T2 -3`, tests the archive, and prints its SHA-256. Compression tools and versions can affect archive bytes; the recipe's file content and package digests remain locked.

Downloads accept standard proxy environment variables. `DOWNLOAD_JOBS=4` controls fetch concurrency. The older Bullseye input lock remains separate; it is not mixed into this root.

## Verify provenance and dependency choices

[`manifest.json`](manifest.json) locks each package name, version, URL, size and SHA-256, and records all chosen Depends/Pre-Depends edges. The official archived Packages index SHA-256 is `1fc7e0fe112863f5cec2bde655f89f3923f97aa8c3cf5a80db4abb625d6391a6`. It matches the [signed Debian Release metadata](provenance/Release); all three Release signatures were verified with Chromium's Debian archive keyring. The signing identities are recorded in [signature-check.txt](provenance/signature-check.txt).

To regenerate the lock after deliberately changing [`seeds.txt`](seeds.txt):

```sh
python3 sysroots/buster/sysroot.py resolve \
  --index /absolute/path/to/mips-work/buster-index/Packages.xz \
  --index-url https://archive.debian.org/debian/dists/buster/main/binary-mips64el/Packages.xz \
  --index-sha256 1fc7e0fe112863f5cec2bde655f89f3923f97aa8c3cf5a80db4abb625d6391a6 \
  --seeds sysroots/buster/seeds.txt \
  --manifest sysroots/buster/manifest.json
```

The resolver checks dependency versions, alternatives, architecture restrictions and virtual Provides. It excludes Recommends/Suggests and is a deterministic sysroot resolver rather than a general apt installation solver. The selected package set has no explicit package Conflicts/Breaks. GTK4, Qt6 and PipeWire 0.3 are absent from Buster; this configuration uses GTK3/X11.

## Tests completed

The [preflight report](../../reports/buster-preflight.txt) records successful GN generation, a complete FFmpeg shared-library build, a complete Rust target standard-library build, and three executable tests under **QEMU 8 with its Loongson-3A4000 CPU model**. The Rust test and FFmpeg require no symbol newer than GLIBC_2.28. An audit of 857 shared ELF files in this root found no newer GLIBC requirement.

Run the [reproduction tests](../../tests/buster-preflight/README.md) after preparing an Electron 37.2.2 source checkout. Full Electron linking and real 3A4000 desktop validation remain separate release requirements.
