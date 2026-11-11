#!/usr/bin/env bash
# Compatibility entry point. The primary probe now uses LLVM/Clang 20.
set -euo pipefail
root=$(cd -- "$(dirname -- "$0")/.." && pwd)
exec "$root/scripts/smoke-test.sh" "$@"
