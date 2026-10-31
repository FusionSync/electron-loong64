#!/usr/bin/env bash
set -euo pipefail
root=$(cd -- "$(dirname -- "$0")/.." && pwd)
args=(--rm --network=none --user "$(id -u):$(id -g)" --cpus 2 --memory 2g
      -v "$root:/work" -w /work)
if [[ -t 0 && -t 1 ]]; then args+=(-it); fi
if [[ $# -eq 0 ]]; then set -- bash; fi
exec docker run "${args[@]}" uos20-loongarch64-cross:gcc8-oldabi "$@"
