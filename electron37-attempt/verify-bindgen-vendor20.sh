#!/usr/bin/env bash
set -euo pipefail
cd /work/electron37-attempt
source ./env.sh
exec > >(tee logs/bindgen-vendor20-validation.log) 2>&1
trap 'rc=$?; printf "%s\n" "$rc" > logs/bindgen-vendor20-validation.exit' EXIT
bash bindgen-audit/probe.sh "$PWD/tools/llvm20/lib" vendor20
python3 ../scripts/audit-elf.py bindgen-audit/probe-layout-vendor20-loongarch64
if [[ "${UOS_SKIP_REMOTE_EXECUTION:-0}" == 1 ]]; then
  echo 'Local vendor libclang20, Chromium bindgen and Rust188 layout passed; UOS execution deferred.'
else
  ssh -S /work/.ssh-control -o BatchMode=yes -p "${UOS_SSH_PORT:-22}" "${UOS_SSH_USER:-UOS}@${UOS_SSH_HOST:-127.0.0.1}" \
    'set -eu; exe=$(mktemp /tmp/uos-bindgen20-XXXXXX); trap '\''rm -f "$exe"'\'' EXIT; cat > "$exe"; chmod 700 "$exe"; "$exe"' \
    < bindgen-audit/probe-layout-vendor20-loongarch64
  echo 'Vendor libclang20, Chromium bindgen, Rust188 and UOS C/Rust layout passed.'
fi
