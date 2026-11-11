#!/usr/bin/env bash
set -euo pipefail
recipe_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
work_dir=${1:?usage: $0 /absolute/path/to/mips-work [--resume]}
shift
mkdir -p "$work_dir"
work_dir=$(cd -- "$work_dir" && pwd)
index="$work_dir/buster-index/Packages.xz"
index_url=https://archive.debian.org/debian/dists/buster/main/binary-mips64el/Packages.xz
index_sha=1fc7e0fe112863f5cec2bde655f89f3923f97aa8c3cf5a80db4abb625d6391a6
mkdir -p "$(dirname -- "$index")"
if [[ ! -f "$index" ]]; then
  curl --fail --location --retry 5 --retry-all-errors "$index_url" -o "$index.part"
  mv -- "$index.part" "$index"
fi
printf '%s  %s\n' "$index_sha" "$index" | sha256sum --check
python3 "$recipe_dir/sysroot.py" fetch --manifest "$recipe_dir/manifest.json" --cache "$work_dir/buster-debs" --jobs "${DOWNLOAD_JOBS:-4}"
python3 "$recipe_dir/sysroot.py" extract --manifest "$recipe_dir/manifest.json" --cache "$work_dir/buster-debs" --root "$work_dir/sysroot-buster" "$@"
