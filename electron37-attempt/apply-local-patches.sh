#!/usr/bin/env bash
# Restore saved local compatibility changes after the repository patch series.
set -euo pipefail
attempt_root=$(cd -- "$(dirname -- "$0")" && pwd)
exec python3 - "$attempt_root" "$@" <<'PY'
import hashlib
import json
from pathlib import Path
import subprocess
import sys

root = Path(sys.argv[1])
arguments = sys.argv[2:]
if arguments not in ([], ['--check']):
    raise SystemExit('Usage: apply-local-patches.sh [--check]')
check_only = arguments == ['--check']
saved = root / 'local-patches'
source = root / 'src'


def git(*args, repository=source):
    return subprocess.check_output(['git', '-C', str(repository), *args], text=True).strip()


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


subprocess.run(['sha256sum', '--check', '--quiet', 'SHA256SUMS'],
               cwd=saved, check=True)
manifest = json.loads((saved / 'manifest.json').read_text())
if git('rev-parse', 'HEAD') != manifest['baseline_head']:
    raise SystemExit('Chromium HEAD differs from the saved local-patch baseline; '
                     'review/rebase these patches before applying them.')

# Validate every source and patch first, before making any source/index changes.
pending = []
for item in manifest['patches']:
    repository = root / item.get('repository', manifest['repository'])
    baseline = item.get('baseline_head', manifest['baseline_head'])
    if git('rev-parse', 'HEAD', repository=repository) != baseline:
        raise SystemExit('Repository HEAD differs from saved baseline: ' + str(repository))
    patch = saved / item['patch']
    if sha256(patch) != item['patch_sha256']:
        raise SystemExit('Patch hash differs: ' + item['patch'])
    current = sha256(repository / item['path'])
    if current == item['applied_sha256']:
        git('apply', '--reverse', '--check', str(patch), repository=repository)
        print('Already applied: ' + item['patch'], flush=True)
    elif current == item['base_sha256']:
        git('apply', '--check', str(patch), repository=repository)
        pending.append(item)
        print('Ready to apply: ' + item['patch'], flush=True)
    else:
        raise SystemExit('Source differs from both saved versions: ' + item['path'])

if check_only:
    print('Check passed; no source or Git index files changed.', flush=True)
    raise SystemExit(0)

for item in pending:
    repository = root / item.get('repository', manifest['repository'])
    git('apply', str(saved / item['patch']), repository=repository)
    if sha256(repository / item['path']) != item['applied_sha256']:
        raise SystemExit('Applied source hash differs: ' + item['path'])
    print('Applied: ' + item['patch'], flush=True)

# The repository patch runner requires a clean tracked-file status on retry.
# Preserve its existing local-change convention, with explicit hash validation
# above so changes hidden by this Git flag remain reviewable and detectable.
for item in manifest['patches']:
    repository = root / item.get('repository', manifest['repository'])
    if not git('ls-files', '-v', '--', item['path'], repository=repository).startswith('h '):
        git('update-index', '--assume-unchanged', '--', item['path'], repository=repository)
print('Local compatibility patches are ready.', flush=True)
PY
