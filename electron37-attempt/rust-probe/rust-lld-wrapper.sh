#!/bin/bash
set -u
facade=/work/electron37-attempt/gn/clang-facade/bin/clang++
for arg in "$@"; do
  case "$arg" in
    *.o)
      /usr/bin/python3 - "$arg" <<'PY'
import struct, sys
path = sys.argv[1]
with open(path, 'r+b') as f:
    f.seek(48)
    raw = f.read(4)
    if len(raw) == 4 and struct.unpack('<I', raw)[0] == 0x43:
        f.seek(48)
        f.write(struct.pack('<I', 3))
PY
      ;;
  esac
done
args=(--target=loongarch64-linux-gnu --ld-path=/work/electron37-attempt/gn/clang-facade/bin/ld.lld)
for arg in "$@"; do
  args+=("$arg")
done
exec "$facade" "${args[@]}"
