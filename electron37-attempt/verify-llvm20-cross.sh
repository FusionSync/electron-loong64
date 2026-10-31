#!/bin/bash
set -euo pipefail
attempt=$(cd -- "$(dirname -- "$0")" && pwd)
project=$(cd -- "$attempt/.." && pwd)
runtime="$attempt/host-runtime"
smoke="$attempt/llvm20-smoke"
exec > >(tee "$attempt/logs/llvm20-cross-validation.log") 2>&1
trap 'status=$?; printf "%s\n" "$status" > "$attempt/logs/llvm20-gnu-validation.exit"' ERR

"$runtime/bin/uos-clang" --version
"$runtime/bin/uos-clang" "$smoke/hello.c" -o "$smoke/hello-c"
"$runtime/bin/uos-clang++" -std=c++20 -pthread "$smoke/hello.cpp" -o "$smoke/hello-cpp"
"$runtime/bin/python3" "$project/scripts/audit-elf.py" "$smoke/hello-c" "$smoke/hello-cpp"

for binary in "$smoke/hello-c" "$smoke/hello-cpp"; do
    "$runtime/bin/ssh" -S "$project/.ssh-control" -o BatchMode=yes -p "${UOS_SSH_PORT:-22}" "${UOS_SSH_USER:-UOS}@${UOS_SSH_HOST:-127.0.0.1}" \
      'set -eu; exe=$(mktemp /tmp/uos-llvm20-XXXXXX); trap '\''rm -f "$exe"'\'' EXIT; cat > "$exe"; chmod 700 "$exe"; "$exe"' \
      < "$binary"
done
echo 'LLVM20 C/C++20 cross-link, ELF ABI audit, and UOS execution all passed.'
trap - ERR
printf '0\n' > "$attempt/logs/llvm20-gnu-validation.exit"
for mode in builtins profile; do
    if [[ "$mode" == builtins ]] && ! "$runtime/bin/python3" "$attempt/inspect-llvm20-runtimes.py"; then
        printf '1\n' > "$attempt/logs/llvm20-builtins-validation.exit"
        exit 1
    fi
    if bash "$attempt/verify-llvm20-compiler-rt.sh" "$mode"; then
        printf '0\n' > "$attempt/logs/llvm20-$mode-validation.exit"
    else
        status=$?
        printf '%s\n' "$status" > "$attempt/logs/llvm20-$mode-validation.exit"
        echo "Compiler runtime $mode validation failed; see its separate log."
        if [[ "$mode" == builtins ]]; then exit "$status"; fi
    fi
done
for mode in gnu-medium lld lld-medium direct crel; do
    if bash "$attempt/verify-llvm20-lld.sh" "$mode"; then
        printf '0\n' > "$attempt/logs/llvm20-$mode-validation.exit"
        echo "Additional $mode validation passed."
    else
        status=$?
        printf '%s\n' "$status" > "$attempt/logs/llvm20-$mode-validation.exit"
        echo "Additional $mode validation failed; see logs/llvm20-$mode-validation.log."
    fi
done
