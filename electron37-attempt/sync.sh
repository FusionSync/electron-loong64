#!/usr/bin/env bash
set -euo pipefail
cd /work/electron37-attempt
source ./env.sh
mkdir -p logs
exec 9>logs/source-sync.lock
flock -n 9 || { echo 'Source synchronization is already running.' >&2; exit 1; }
printf '%s Starting Electron dependency synchronization\n' "$(date -u +%FT%TZ)"
electron_commit=102f740ec2fc8f34601c84b79ea1bf06042e8d00
if [[ $(git -C src/electron rev-parse HEAD) == "$electron_commit" ]] && \
   git -C src/electron symbolic-ref -q HEAD >/dev/null; then
  # gclient must not try rebasing the local, uncommitted architecture patches.
  git -C src/electron checkout --detach "$electron_commit"
fi
if [[ -d src/.git ]] && ! git -C src rev-parse --verify HEAD >/dev/null 2>&1; then
  # Recover an interrupted first gclient fetch without deleting any checkout.
  git -C src -c protocol.version=2 -c http.lowSpeedTime=90 \
    -c http.lowSpeedLimit=1024 fetch --depth=1 --no-tags origin \
    5f45b4744e3d5ba82c2ca6d942f1e7a516110752 || \
    git -C src -c protocol.version=2 fetch --depth=1 --no-tags \
      https://github.com/chromium/chromium.git \
      5f45b4744e3d5ba82c2ca6d942f1e7a516110752
  git -C src checkout --detach FETCH_HEAD
fi
# The unmanaged Electron solution is pinned in .gclient. A --revision override
# would make gclient manage it again and reject the local architecture patches.
gclient sync --no-history --shallow --nohooks --jobs=2 "$@"
printf '%s Dependency synchronization completed; hooks/build not yet run\n' "$(date -u +%FT%TZ)"

