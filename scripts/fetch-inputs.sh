#!/usr/bin/env bash
set -euo pipefail

# Download the large binary inputs which are intentionally kept out of Git.
# The release assets are public; curl also honors HTTP(S)_PROXY for restricted
# build networks. Override INPUTS_REPO, INPUTS_TAG, or INPUTS_BASE_URL when
# using a mirror.
root=$(cd -- "$(dirname -- "$0")/.." && pwd)
input_dir=${INPUTS_DIR:-$root/inputs}
repo=${INPUTS_REPO:-FusionSync/electron-loong64}
tag=${INPUTS_TAG:-toolchain-v1}
base_url=${INPUTS_BASE_URL:-https://github.com/$repo/releases/download/$tag}

mkdir -p "$input_dir"

download() {
    local name=$1
    local output=$input_dir/$name
    local part=$output.part
    local url_name=${name//+/%2B}
    local url=$base_url/$url_name

    if [[ -f "$output" ]]; then
        local expected actual
        expected=$(awk -v name="$name" '$2 == name {print $1}' "$root/metadata/SHA256SUMS")
        actual=$(sha256sum "$output" | awk '{print $1}')
        if [[ -n "$expected" && "$actual" == "$expected" ]]; then
            echo "Already verified: $name"
            return
        fi
    fi

    echo "Downloading $name"
    curl --fail --location --retry 4 --retry-delay 2 --continue-at - --output "$part" "$url"
    mv -- "$part" "$output"
}

download uos20-sysroot-20261027.tar.gz
download loongson-gcc8.3-rc1.6.tar.xz
download libstdc++-8-dev_8.3.0.13-deepin1_loongarch64.deb

(cd "$input_dir" && sha256sum -c "$root/metadata/SHA256SUMS")
echo "Verified build inputs in $input_dir"
