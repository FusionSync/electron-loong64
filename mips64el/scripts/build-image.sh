#!/usr/bin/env bash
set -euo pipefail
root=$(cd -- "$(dirname -- "$0")/.." && pwd)
cd "$root"

if [[ ${FETCH_INPUTS:-0} == 1 ]]; then
  python3 "$root/scripts/fetch-inputs.py"
fi

python3 "$root/scripts/fetch-inputs.py" --verify-only
(
  cd inputs
  sha256sum -c SHA256SUMS
)
proxy_args=()
for proxy_name in HTTP_PROXY HTTPS_PROXY NO_PROXY http_proxy https_proxy no_proxy; do
  if [[ -n ${!proxy_name:-} ]]; then
    proxy_args+=(--build-arg "$proxy_name")
  fi
done
docker build --pull=false "${proxy_args[@]}" \
  --build-arg "BASE_IMAGE=${BASE_IMAGE:-electron37-mips64el-host-tools:node22}" \
  -t "${MIPS_IMAGE:-electron37-mips64el:n64}" .
