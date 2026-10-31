#!/usr/bin/env bash
# Run on the UOS desktop as its logged-in, non-root user.
set -euo pipefail
if [[ $# -lt 1 || $# -gt 2 ]]; then
  echo "Usage: $0 /absolute/path/to/unpacked/electron [new-results-directory]" >&2
  exit 2
fi
[[ $(id -u) != 0 ]] || { echo 'Run as the UOS desktop user, not root.' >&2; exit 2; }
case $(uname -m) in
  loongarch64|loong64) ;;
  *) echo 'This validation must run on the LoongArch target.' >&2; exit 2 ;;
esac
command -v timeout >/dev/null
electron_binary=$(readlink -f -- "$1")
[[ -f "$electron_binary" && -x "$electron_binary" ]] || { echo 'Electron executable missing.' >&2; exit 2; }
validation_dir=$(cd -- "$(dirname -- "$0")" && pwd)
if [[ $# == 2 ]]; then
  mkdir -- "$2" # Refuse to reuse previous evidence.
  results_dir=$(cd -- "$2" && pwd)
else
  results_dir=$(mktemp -d "$PWD/electron-runtime-results-$(date -u +%Y%m%dT%H%M%SZ).XXXXXX")
fi
export UOS_RUNTIME_RESULTS="$results_dir"
export UOS_EXPECTED_ELECTRON_VERSION="${UOS_EXPECTED_ELECTRON_VERSION:-37.2.2}"
export UOS_EXPECTED_NODE_ARCH="${UOS_EXPECTED_NODE_ARCH:-loong64}"
unset ELECTRON_RUN_AS_NODE NODE_OPTIONS NODE_PATH
printf 'stage\tstatus\texit_code\n' > "$results_dir/summary.tsv"
{
  date -u +%FT%TZ
  uname -srm
  printf 'uid=%s\nelectron=%s\nexpected_electron=%s\nexpected_arch=%s\n' \
    "$(id -u)" "$electron_binary" "$UOS_EXPECTED_ELECTRON_VERSION" "$UOS_EXPECTED_NODE_ARCH"
  printf 'DISPLAY=%s\nXAUTHORITY=%s\nXDG_RUNTIME_DIR=%s\nXDG_SESSION_TYPE=%s\n' \
    "${DISPLAY:-}" "${XAUTHORITY:-}" "${XDG_RUNTIME_DIR:-}" "${XDG_SESSION_TYPE:-}"
  sha256sum -- "$electron_binary"
} > "$results_dir/environment.txt"
overall_exit=0
run_stage() {
  local name=$1 limit=$2 code=0 status=passed
  shift 2
  timeout --kill-after=5s "$limit" "$@" \
    > "$results_dir/$name.stdout.log" 2> "$results_dir/$name.stderr.log" || code=$?
  if [[ $name == version && $code == 0 ]] &&
      ! grep -Fxq -- "v$UOS_EXPECTED_ELECTRON_VERSION" "$results_dir/$name.stdout.log"; then
    printf 'Expected version v%s was not printed.\n' "$UOS_EXPECTED_ELECTRON_VERSION" >> "$results_dir/$name.stderr.log"
    code=1
  fi
  if [[ $name == renderer && $code == 0 && ! -f "$results_dir/renderer-normal-quit.ok" ]]; then
    echo 'Process exited without completing renderer checks and normal quit.' >> "$results_dir/$name.stderr.log"
    code=1
  fi
  if [[ $name == node && $code == 0 && ! -f "$results_dir/node.json" ]]; then
    echo 'Process exited without running the Node validation script.' >> "$results_dir/$name.stderr.log"
    code=1
  fi
  if [[ $code != 0 ]]; then status=failed; overall_exit=1; fi
  printf '%s\n' "$code" > "$results_dir/$name.exit"
  printf '%s\t%s\t%s\n' "$name" "$status" "$code" >> "$results_dir/summary.tsv"
}
run_stage version 30s "$electron_binary" --version
run_stage node 30s env ELECTRON_RUN_AS_NODE=1 "$electron_binary" "$validation_dir/node-smoke.js"
if [[ -n ${DISPLAY:-} ]]; then
  run_stage renderer 90s "$electron_binary" "$validation_dir/main.js"
else
  printf 'renderer\tskipped_no_DISPLAY\t-\n' >> "$results_dir/summary.tsv"
  echo 'Use the existing UOS X11 desktop session; DISPLAY is unset.' > "$results_dir/renderer.stderr.log"
  overall_exit=1
fi
printf '%s\n' "$overall_exit" > "$results_dir/overall.exit"
cat "$results_dir/summary.tsv"
printf 'Evidence: %s\n' "$results_dir"
exit "$overall_exit"
