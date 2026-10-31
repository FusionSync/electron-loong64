#!/usr/bin/env bash
set -euo pipefail
cd /work/electron37-attempt/src/electron
notes=/work/research/electron-source-notes
apply_once() {
  local patch=$1
  shift
  # Later patches extend these two manifests; validate registrations below.
  if git apply --reverse --check --exclude=patches/config.json \
      --exclude=patches/chromium/.patches --exclude=patches/breakpad/.patches \
      "$@" "$patch" >/dev/null 2>&1; then
    printf 'Already applied: %s\n' "$patch"
  else
    git apply --check "$@" "$patch"
    git apply "$@" "$patch"
  fi
}
apply_once "$notes/adapted-37.2.2-chromium.patch"
# The community release arguments select a native toolchain and no sysroot.
# Keep those out of this cross build; use separate GN arguments instead.
apply_once "$notes/37.2.5-patches_electron.patch" '--exclude=build/args/*'
cp "$notes/uos20-crashpad-oldabi.patch" patches/chromium/uos20_crashpad_oldabi.patch
cp "$notes/uos20-sandbox-signal-oldabi.patch" patches/chromium/uos20_sandbox_signal_oldabi.patch
cp "$notes/breakpad-old-host-elf-constant.patch" patches/breakpad/old_host_elf_constant.patch
mkdir -p patches/lss
cp "$notes/uos20-lss-oldabi.patch" patches/lss/uos20_oldabi.patch
python3 - <<'PY'
from pathlib import Path
import json
manifest = Path('patches/chromium/.patches')
lines = manifest.read_text().splitlines()
assert 'loong64_support.patch' in lines, 'Missing community Chromium registration'
registered = {entry['patch_dir'] for entry in json.loads(Path('patches/config.json').read_text())}
for name in ('skia', 'swiftshader', 'xnnpack', 'breakpad'):
    assert 'src/electron/patches/' + name in registered, 'Missing patch registration: ' + name
patch = 'uos20_crashpad_oldabi.patch'
if patch not in lines:
    lines.insert(lines.index('loong64_support.patch') + 1, patch)
patch = 'uos20_sandbox_signal_oldabi.patch'
if patch not in lines:
    lines.insert(lines.index('uos20_crashpad_oldabi.patch') + 1, patch)
manifest.write_text('\n'.join(lines) + '\n')
manifest = Path('patches/breakpad/.patches')
lines = manifest.read_text().splitlines()
if 'old_host_elf_constant.patch' not in lines:
    lines.append('old_host_elf_constant.patch')
manifest.write_text('\n'.join(lines) + '\n')
Path('patches/lss/.patches').write_text('uos20_oldabi.patch\n')
config = Path('patches/config.json')
entries = json.loads(config.read_text())
if not any(entry['repo'] == 'src/third_party/lss' for entry in entries):
    entries.append({'patch_dir': 'src/electron/patches/lss', 'repo': 'src/third_party/lss'})
    config.write_text(json.dumps(entries, indent=2) + '\n')
PY
git diff --check
