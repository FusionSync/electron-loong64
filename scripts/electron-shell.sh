#!/usr/bin/env bash
set -euo pipefail
project_root=$(cd -- "$(dirname -- "$0")/.." && pwd)
container_name=${UOS_ELECTRON_CONTAINER:-uos-electron37-attempt}
if ! docker container inspect "$container_name" >/dev/null 2>&1; then
    docker run -d --name "$container_name" \
      --user "$(id -u):$(id -g)" --cpus "${UOS_BUILD_CPUS:-8}" \
      --memory "${UOS_BUILD_MEMORY:-24g}" --memory-swap "${UOS_BUILD_MEMORY_SWAP:-24g}" \
      --pids-limit 512 -v "$project_root:/work" -w /work/electron37-attempt \
      uos20-loongarch64-cross:gcc8-oldabi sleep infinity >/dev/null
fi
if [[ $(docker inspect --format '{{.State.Running}}' "$container_name") != true ]]; then
    docker start "$container_name" >/dev/null
fi
args=()
if [[ -t 0 && -t 1 ]]; then args+=(-it); fi
if [[ $# -eq 0 ]]; then
    exec docker exec "${args[@]}" "$container_name" bash --rcfile /work/electron37-attempt/env.sh
fi
exec docker exec "${args[@]}" "$container_name" bash -c \
    'source /work/electron37-attempt/env.sh; exec "$@"' bash "$@"
