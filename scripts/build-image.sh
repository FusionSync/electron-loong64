#!/usr/bin/env bash
set -euo pipefail
root=$(cd -- "$(dirname -- "$0")/.." && pwd)
cd "$root"
if [[ ${FETCH_INPUTS:-0} == 1 ]]; then
    "$root/scripts/fetch-inputs.sh"
fi
if [[ ${FETCH_BASE_IMAGE:-0} == 1 ]]; then
    "$root/scripts/fetch-native-base.sh"
fi
(cd inputs && sha256sum -c ../metadata/SHA256SUMS)
base=${BASE_IMAGE:-electron37-native-builder:ubuntu18.04}
for input in inputs/uos20-sysroot-20261027.tar.gz inputs/loongson-gcc8.3-rc1.6.tar.xz inputs/libstdc++-8-dev_8.3.0.13-deepin1_loongarch64.deb; do
    if [[ ! -f "$input" ]]; then
        echo "Missing $input; obtain it from an authorized UOS/Loongson source before building." >&2
        exit 2
    fi
done
if ! docker image inspect "$base" >/dev/null 2>&1; then
    echo "Base image $base is not available locally; build/load the pinned base image or set BASE_IMAGE." >&2
    exit 2
fi
docker build --network=none --pull=false --build-arg "BASE_IMAGE=$base" \
    -t electron-loong64:gcc8-oldabi .
