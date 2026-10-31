#!/usr/bin/env bash
# Resume the incremental cross build using saved inputs and compatibility patches.
set -euo pipefail
cd /work/electron37-attempt
source ./env.sh
mkdir -p logs
attempt_logs=$PWD/logs
exec 8>logs/build-pipeline.lock
flock -n 8 || { echo 'Build continuation is already running.' >&2; exit 1; }
rm -f logs/build-pipeline.exit
stage=starting
finish() {
  local rc=$?
  printf '%s\n' "$rc" > "$attempt_logs/build-pipeline.exit"
  printf '%s stage=%s exit=%s\n' "$(date -u +%FT%TZ)" "$stage" "$rc"
}
trap finish EXIT
trap 'exit 143' TERM
trap 'exit 130' INT
set_stage() {
  stage=$1
  printf '%s\n' "$stage" > "$attempt_logs/build-pipeline.stage"
  printf '%s stage=%s\n' "$(date -u +%FT%TZ)" "$stage"
}
wait_for_result() {
  local result_file=$1
  local deadline=$((SECONDS + 14400))
  while [[ ! -f "$result_file" ]]; do
    if ((SECONDS >= deadline)); then
      printf 'Timed out waiting for %s\n' "$result_file" >&2
      return 75
    fi
    sleep 15
  done
  local result
  result=$(cat "$result_file")
  if [[ "$result" != 0 ]]; then
    printf 'Prerequisite failed: %s reports %s\n' "$result_file" "$result" >&2
    return 1
  fi
}

set_stage waiting-for-source-sync
wait_for_result logs/source-sync.exit
set_stage applying-source-patches
bash ./apply-source-patches.sh
set_stage applying-repository-patches
python3 -u ./apply-patches-resumable.py > logs/patches.log 2>&1
set_stage applying-local-compatibility-patches
bash ./apply-local-patches.sh > logs/local-patches.log 2>&1
set_stage restoring-target-curl-headers
python3 dependency-audit/curl-headers/install-headers.py
set_stage restoring-target-libnotify-development-files
python3 dependency-audit/libnotify/install-dev-files.py
set_stage running-hooks
gclient runhooks > logs/hooks.log 2>&1
set_stage waiting-for-llvm-validation
wait_for_result logs/llvm20-validation.exit
set_stage waiting-for-gnu-medium-validation
# Preserve the earlier small-binary compatibility gate. It does not prove
# that the vendor medium model can span Electron's complete text section.
wait_for_result logs/llvm20-gnu-medium-validation.exit
set_stage waiting-for-large-code-model-validation
# The old-ABI compiler needs large for cross-component calls beyond 128 MiB.
# This gate exercises the new C++/Rust calls on the actual UOS target.
wait_for_result logs/large-code-model-validation.exit
set_stage preparing-toolchains
python3 gn/prepare-facades.py
set_stage validating-vendor-bindgen
if grep -q 'passed_local_remote_deferred' logs/llvm20-validation-status.json; then
  export UOS_SKIP_REMOTE_EXECUTION=1
fi
bash ./verify-bindgen-vendor20.sh
mkdir -p src/out/UOS37
# Keep the generated output tied to the checked-in cross-build arguments. A
# stale GN placeholder can otherwise silently configure Chromium without the
# Electron root dependency and leave the `electron` target absent.
cp gn/args.gn src/out/UOS37/args.gn
set_stage generating-build
cd src
./buildtools/linux64/gn gen out/UOS37 --fail-on-unused-args > ../logs/gn-gen.log 2>&1
set_stage compiling-electron
python3 ../run-ninja.py electron > ../logs/ninja-electron.log 2>&1
set_stage electron-link-completed
set_stage packaging-electron
python3 ../run-ninja.py electron:electron_dist_zip \
  > ../logs/package-electron.log 2>&1
set_stage package-created-awaiting-runtime-validation
