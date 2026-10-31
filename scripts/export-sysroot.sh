#!/usr/bin/env bash
set -euo pipefail
root=$(cd -- "$(dirname -- "$0")/.." && pwd)
target=${UOS_TARGET:-${UOS_SSH_USER:-UOS}@${UOS_SSH_HOST:-127.0.0.1}}
port=${UOS_SSH_PORT:-22}
dest=${1:?Usage: export-sysroot.sh NEW_ARCHIVE.tar.gz}
if [[ -e "$dest" ]]; then
    echo "Refusing to overwrite $dest" >&2
    exit 1
fi
ssh -p "$port" "$target" 'set -o pipefail; tar -C / -cf - lib lib64 usr/include usr/lib/loongarch64-linux-gnu usr/lib/gcc usr/lib/pkgconfig usr/share/pkgconfig | gzip -1' > "$dest.part"
gzip -t "$dest.part"
mv -- "$dest.part" "$dest"
echo "Exported $dest; pin its SHA256 before rebuilding the image."
