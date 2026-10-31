# Docker build inputs

The Dockerfile expects these three local files, each checked against `metadata/SHA256SUMS`:

- `uos20-sysroot-20261027.tar.gz` — exported LoongArch64 old-ABI headers, libraries, and pkg-config metadata.
- `loongson-gcc8.3-rc1.6.tar.xz` — Loongson GCC 8.3 cross toolchain.
- `libstdc++-8-dev_8.3.0.13-deepin1_loongarch64.deb` — matching target C++ headers.

These files are intentionally excluded from Git because they contain large distribution binaries. Download or export them only from sources where redistribution is permitted, then verify the recorded SHA256 values before building.

For the published build inputs, run:

```bash
./scripts/fetch-inputs.sh
```

The default source is the `toolchain-v1` Release in
`FusionSync/electron-loong64`. Set `INPUTS_REPO`, `INPUTS_TAG`, or
`INPUTS_BASE_URL` to use another repository, Release, or mirror. The script
downloads into this directory and validates every file against
`metadata/SHA256SUMS`.
