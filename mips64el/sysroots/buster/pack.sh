#!/usr/bin/env bash
set -euo pipefail
recipe_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
sysroot_root=${1:?usage: $0 /path/to/sysroot-buster /path/to/sysroot.tar.xz}
archive=${2:?usage: $0 /path/to/sysroot-buster /path/to/sysroot.tar.xz}
sysroot_root=$(cd -- "$sysroot_root" && pwd)
python3 - "$recipe_dir/manifest.json" "$sysroot_root/.sysroot-recipe.json" <<'CHECK'
import hashlib,json,pathlib,sys
manifest,state=map(pathlib.Path,sys.argv[1:])
expected=hashlib.sha256(manifest.read_bytes()).hexdigest()
value=json.loads(state.read_text())
if not value.get('complete') or value.get('manifest_sha256')!=expected:
    raise SystemExit('Sysroot must be a complete extraction of this pinned manifest.')
CHECK
mkdir -p "$(dirname -- "$archive")"
trap 'rm -f -- "$archive.part"' EXIT
LC_ALL=C tar --sort=name --mtime=@0 --owner=0 --group=0 --numeric-owner -C "$sysroot_root" -cf - . | xz -T2 -3 > "$archive.part"
xz -t "$archive.part"
mv -- "$archive.part" "$archive"
trap - EXIT
sha256sum "$archive"
