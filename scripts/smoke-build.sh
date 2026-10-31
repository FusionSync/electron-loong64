#!/usr/bin/env bash
set -euo pipefail
root=$(cd -- "$(dirname -- "$0")/.." && pwd)
cd "$root"
scripts/run.sh bash -c 'cmake -S tests -B output/cmake -DCMAKE_TOOLCHAIN_FILE=/opt/uos-cross/uos20-loongarch64.cmake -DCMAKE_BUILD_TYPE=Release && cmake --build output/cmake --clean-first --parallel 2'
python3 scripts/audit-elf.py output/cmake/hello-c output/cmake/hello-cpp > output/elf-audit.json
cat output/elf-audit.json
