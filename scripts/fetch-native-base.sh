#!/usr/bin/env bash
set -euo pipefail

# Fetch the x86_64 host-tools image used as the first layer of Dockerfile.
# The archive is public and contains no target sysroot or private build data.
root=$(cd -- "$(dirname -- "$0")/.." && pwd)
cache_dir=${BASE_IMAGE_DIR:-$root/.cache/native-base}
name=${BASE_IMAGE_ARCHIVE:-electron-loong64-native-glibc227.tar}
tag=${BASE_IMAGE_TAG:-electron37-native-builder:ubuntu18.04}
base_url=${BASE_IMAGE_URL:-https://github.com/FusionSync/electron-loong64/releases/download/toolchain-v1}
output=$cache_dir/$name
part=$output.part

mkdir -p "$cache_dir"
expected=$(awk -v name="$name" '$2 == name {print $1}' "$root/metadata/native-base-SHA256SUMS")
if [[ -z "$expected" ]]; then
    echo "No checksum recorded for $name" >&2
    exit 2
fi

if [[ ! -f "$output" || "$(sha256sum "$output" | awk '{print $1}')" != "$expected" ]]; then
    echo "Downloading $name"
    curl --fail --location --retry 4 --retry-delay 2 --continue-at - --output "$part" "$base_url/$name"
    mv -- "$part" "$output"
fi

(cd "$cache_dir" && sha256sum -c "$root/metadata/native-base-SHA256SUMS")
docker load --input "$output"
if ! docker image inspect "$tag" >/dev/null 2>&1; then
    echo "Loaded archive does not provide expected image tag $tag" >&2
    exit 2
fi
echo "Verified native base image: $tag"
