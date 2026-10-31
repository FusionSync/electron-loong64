# Docker build inputs

The Dockerfile expects these three local files, each checked against `metadata/SHA256SUMS`:

- `uos20-sysroot-20261027.tar.gz` — exported UOS 20 LoongArch64 headers, libraries, and pkg-config metadata.
- `loongson-gcc8.3-rc1.6.tar.xz` — Loongson GCC 8.3 cross toolchain.
- `libstdc++-8-dev_8.3.0.13-deepin1_loongarch64.deb` — matching UOS C++ headers.

These files are intentionally excluded from Git because they contain large distribution binaries. Download or export them only from sources where redistribution is permitted, then verify the recorded SHA256 values before building.
