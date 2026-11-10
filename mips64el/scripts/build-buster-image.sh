#!/usr/bin/env bash
set -euo pipefail
recipe_root=$(cd -- "$(dirname -- "$0")/.." && pwd)
base_image=${MIPS_BASE_IMAGE:-electron37-mips64el:public-clang20}
image=${MIPS_IMAGE:-electron37-mips64el:buster-clang20}
archive_name=debian-buster-mips64el-glibc2.28-sysroot.tar.xz
archive="$recipe_root/inputs/$archive_name"

if [[ ! -f "$archive" ]]; then
  sysroot_work=${BUSTER_WORK_DIR:-$recipe_root/inputs/buster-work}
  "$recipe_root/sysroots/buster/build.sh" "$sysroot_work" --resume
  "$recipe_root/sysroots/buster/pack.sh" "$sysroot_work/sysroot-buster" "$archive"
fi
(
  cd "$recipe_root/inputs"
  sha256sum -c "$recipe_root/metadata/buster-sysroot-SHA256SUMS"
)
docker image inspect "$base_image" >/dev/null

# Keep the Docker context small: LLVM and the other base inputs are already
# present in the base image, and are not needed for this target-root layer.
context=$(mktemp -d)
trap 'rm -rf -- "$context"' EXIT
mkdir -p "$context/inputs" "$context/metadata"
if ! ln -- "$archive" "$context/inputs/$archive_name" 2>/dev/null; then
  cp -- "$archive" "$context/inputs/$archive_name"
fi
cp -- "$recipe_root/Dockerfile.buster" "$context/Dockerfile"
cp -- "$recipe_root/metadata/buster-sysroot-SHA256SUMS" "$context/metadata/"
docker build --pull=false --network=none \
  --build-arg "BASE_IMAGE=$base_image" -t "$image" "$context"
