#!/usr/bin/env bash
set -euo pipefail
if [[ $# -lt 2 || $# -gt 3 ]]; then
  echo "Usage: $0 CHROMIUM_SOURCE_ROOT BUSTER_SYSROOT [OUTPUT_DIRECTORY]" >&2
  exit 2
fi
probe_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
source_root=$(realpath -- "$1")
sysroot_dir=$(realpath -- "$2")
output_dir=${3:-/tmp/v8-n64-fpr-addon}
mkdir -p -- "$output_dir"
output_dir=$(realpath -- "$output_dir")
"${CC:-/opt/llvm20/bin/clang}" \
  --target=mips64el-linux-gnuabi64 -march=mips64r2 -mabi=64 -mhard-float \
  --sysroot="$sysroot_dir" \
  -B"$sysroot_dir/usr/lib/gcc/mips64el-linux-gnuabi64/8" \
  -L"$sysroot_dir/usr/lib/mips64el-linux-gnuabi64" \
  -O2 -fPIC -fvisibility=hidden -shared -std=c11 -Wall -Wextra -Werror \
  -DNAPI_VERSION=8 -I"$source_root/third_party/electron_node/src" \
  -Wl,--hash-style=sysv -Wl,-z,noexecstack \
  "$probe_dir/addon.c" "$probe_dir/roundtrip.S" \
  -o "$output_dir/v8-n64-fpr.node"
echo "$output_dir/v8-n64-fpr.node"
