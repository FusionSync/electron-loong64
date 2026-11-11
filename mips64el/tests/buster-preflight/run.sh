#!/usr/bin/env bash
set -euo pipefail
recipe_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
work_dir=${1:?usage: $0 /absolute/path/to/mips-work}
work_dir=$(cd -- "$work_dir" && pwd)
mips_image=${MIPS_IMAGE:-electron37-mips64el:buster-clang20}
qemu_mips=${QEMU_MIPS64EL:-qemu-mips64el}
if ! command -v "$qemu_mips" >/dev/null; then
  echo "Set QEMU_MIPS64EL to a QEMU binary supporting -cpu Loongson-3A4000." >&2
  exit 1
fi
docker run --rm --user "$(id -u):$(id -g)" -v "$work_dir:/work" -v "$recipe_root:/work/recipe:ro" -e NINJA_JOBS="${NINJA_JOBS:-4}" "$mips_image" bash /work/recipe/tests/buster-preflight/run-in-container.sh
report="$work_dir/reports/buster-preflight"
for name in clang rust; do
  "$qemu_mips" -cpu Loongson-3A4000 -L "$work_dir/sysroot-buster" "$report/$name-smoke" > "$report/run-$name.log" 2>&1
  cat "$report/run-$name.log"
done
"$qemu_mips" -cpu Loongson-3A4000 -L "$work_dir/sysroot-buster" "$report/ffmpeg-smoke" "$work_dir/out/buster-preflight-clang20/libffmpeg.so" > "$report/run-ffmpeg.log" 2>&1
cat "$report/run-ffmpeg.log"
