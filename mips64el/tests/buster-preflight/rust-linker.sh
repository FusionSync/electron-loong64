#!/bin/bash
set -euo pipefail
exec /opt/llvm20/bin/clang --target=mips64el-linux-gnuabi64 --sysroot=/work/sysroot-buster -march=mips64r2 -mabi=64 "$@" /work/sysroot-buster/lib/mips64el-linux-gnuabi64/libgcc_s.so.1
