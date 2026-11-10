#!/usr/bin/env bash
set -euo pipefail

source_root=${1:?usage: $0 /path/to/chromium/src [out-dir]}
source_root=$(cd -- "$source_root" && pwd -P)
recipe_root=$(cd -- "$(dirname -- "$0")/.." && pwd -P)
out_dir=${2:-$source_root/../out/mips64el}
image=${MIPS_IMAGE:-electron37-mips64el:buster-clang20}
jobs=${NINJA_JOBS:-2}

if [[ ! $jobs =~ ^[1-9][0-9]*$ ]]; then
  echo 'NINJA_JOBS must be a positive integer.' >&2
  exit 2
fi
if [[ ! -x $source_root/buildtools/linux64/gn || ! -f $source_root/electron/BUILD.gn ]]; then
  echo 'The source directory must contain an initialized Chromium/Electron checkout.' >&2
  exit 2
fi

mkdir -p -- "$out_dir"
out_dir=$(cd -- "$out_dir" && pwd -P)
if [[ $out_dir == / || $source_root/ == "$out_dir/"* || $recipe_root/ == "$out_dir/"* ]]; then
  echo 'The output directory must not contain the source checkout or recipe.' >&2
  exit 2
fi
docker run --rm --user "$(id -u):$(id -g)" \
  --memory="${BUILD_MEMORY:-24g}" \
  -e ELECTRON_OUT_DIR=/work/out \
  -e npm_config_cache=/tmp/electron-npm-cache \
  -v "$source_root:/work/src" \
  -v "$out_dir:/work/out" \
  -v "$recipe_root:/work/recipe:ro" \
  -w /work/src "$image" bash -c '
    set -euo pipefail
    rm -f /work/out/.electron-build-success.json
    # GN selects host and target pkg-config roots separately. Global target
    # variables would make host queries read MIPS paths.
    unset PKG_CONFIG_SYSROOT_DIR PKG_CONFIG_LIBDIR PKG_CONFIG_PATH
    export PATH="/work/src/buildtools/linux64:$PATH"
    node --version
    /opt/llvm20/bin/clang --version
    python3 /work/recipe/patches/apply-mips64el-source-patches.py /work/src
    python3 /work/recipe/patches/apply-mips64el-ffmpeg-patches.py /work/src
    python3 /work/recipe/scripts/refresh-local-hook-outputs.py /work/src
    /work/src/buildtools/linux64/gn gen /work/out \
      --fail-on-unused-args \
      --args="$(cat /work/recipe/gn-args.gn)"
    ninja -C /work/out electron -j"$1"
    python3 /work/recipe/scripts/record-build-success.py /work/src /work/out \
      --ninja-exit-code 0
  ' build-electron "$jobs"
