#!/usr/bin/env bash
set -euo pipefail
unset PKG_CONFIG_SYSROOT_DIR PKG_CONFIG_LIBDIR PKG_CONFIG_PATH
cd /work/src
tests=/work/recipe/tests/buster-preflight
out=out/buster-preflight-clang20
report=/work/reports/buster-preflight
mkdir -p "$out" "$report"
cp "$tests/preflight.gn" "$out/args.gn"
buildtools/linux64/gn gen "$out" > "$report/gn-gen.log" 2>&1
ninja -C "$out" -j"${NINJA_JOBS:-4}" third_party/ffmpeg:ffmpeg build/rust/std:std > "$report/ninja.log" 2>&1
clang --target=mips64el-linux-gnuabi64 --sysroot=/work/sysroot-buster -march=mips64r2 -mabi=64 -mno-msa -O2 "$tests/clang-smoke.c" -lpthread -ldl -o "$report/clang-smoke"
clang --target=mips64el-linux-gnuabi64 --sysroot=/work/sysroot-buster -march=mips64r2 -mabi=64 -mno-msa -O2 "$tests/ffmpeg-smoke.c" -ldl -o "$report/ffmpeg-smoke"
third_party/rust-toolchain/bin/rustc "$tests/rust-smoke.rs" --edition=2021 --target=mips64el-unknown-linux-gnuabi64 --sysroot=/work/out/buster-preflight-clang20/local_rustc_sysroot -C linker="$tests/rust-linker.sh" -C panic=abort -C opt-level=2 -o "$report/rust-smoke"
