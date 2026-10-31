#!/bin/bash
set -euo pipefail
attempt=$(cd -- "$(dirname -- "$0")" && pwd)
project=$(cd -- "$attempt/.." && pwd)
runtime="$attempt/host-runtime"
smoke="$attempt/llvm20-smoke"
mode=${1:-lld}
extra=()
linker=(--ld-path="$runtime/bin/uos-ld.lld")
case "$mode" in
    lld) ;;
    direct) ;;
    crel) extra=(-Wa,--crel) ;;
    gnu-medium) extra=(-mabi=lp64d -mcmodel=medium); linker=() ;;
    lld-medium) extra=(-mabi=lp64d -mcmodel=medium) ;;
    *) echo "Unknown validation mode: $mode" >&2; exit 2 ;;
esac
exec > >(tee "$attempt/logs/llvm20-$mode-validation.log") 2>&1

if [[ "$mode" == gnu-medium ]]; then
    /opt/loongson/bin/loongarch64-linux-gnu-ld --version
else
    "$runtime/bin/uos-ld.lld" --version
fi
binaries=("$smoke/hello-c-$mode")
if [[ "$mode" == direct ]]; then
    sysroot=${UOS_SYSROOT:-/opt/uos-sysroot}
    startup="$sysroot/usr/lib/loongarch64-linux-gnu"
    "$runtime/bin/uos-clang" -c "$smoke/hello.c" -o "$smoke/hello-direct.o"
    "$runtime/bin/uos-ld.lld" --sysroot="$sysroot" -m elf64loongarch \
        --dynamic-linker=/lib64/ld.so.1 -o "$smoke/hello-c-$mode" \
        "$startup/crt1.o" "$startup/crti.o" /opt/uos-target-runtime/crtbegin.o \
        "$smoke/hello-direct.o" -L/opt/uos-target-runtime -L"$startup" \
        -L"$sysroot/lib/loongarch64-linux-gnu" --rpath-link="$startup" \
        --start-group -lgcc -lgcc_s -lc --end-group \
        /opt/uos-target-runtime/crtend.o "$startup/crtn.o"
elif [[ "$mode" == crel ]]; then
    "$runtime/bin/uos-clang" -c "$smoke/hello.c" "${extra[@]}" -o "$smoke/hello-c-crel.o"
    "$runtime/bin/uos-clang++" -c -std=c++20 -pthread "$smoke/hello.cpp" \
        "${extra[@]}" -o "$smoke/hello-cpp-crel.o"
    "$runtime/bin/python3" "$attempt/inspect-crel-object.py" \
        "$smoke/hello-c-crel.o" "$smoke/hello-cpp-crel.o"
    "$runtime/bin/uos-clang" "$smoke/hello-c-crel.o" \
        --ld-path="$runtime/bin/uos-ld.lld" -o "$smoke/hello-c-$mode"
    "$runtime/bin/uos-clang++" -pthread "$smoke/hello-cpp-crel.o" \
        --ld-path="$runtime/bin/uos-ld.lld" -o "$smoke/hello-cpp-$mode"
    binaries+=("$smoke/hello-cpp-$mode")
else
    "$runtime/bin/uos-clang" "$smoke/hello.c" "${linker[@]}" \
        "${extra[@]}" -o "$smoke/hello-c-$mode"
    "$runtime/bin/uos-clang++" -std=c++20 -pthread "$smoke/hello.cpp" \
        "${linker[@]}" "${extra[@]}" -o "$smoke/hello-cpp-$mode"
    binaries+=("$smoke/hello-cpp-$mode")
fi
"$runtime/bin/python3" "$project/scripts/audit-elf.py" "${binaries[@]}"
for binary in "${binaries[@]}"; do
    "$runtime/bin/ssh" -S "$project/.ssh-control" -o BatchMode=yes -p "${UOS_SSH_PORT:-22}" "${UOS_SSH_USER:-UOS}@${UOS_SSH_HOST:-127.0.0.1}" \
      'set -eu; exe=$(mktemp /tmp/uos-llvm20-XXXXXX); trap '\''rm -f "$exe"'\'' EXIT; cat > "$exe"; chmod 700 "$exe"; "$exe"' \
      < "$binary"
done
echo "LLVM20 $mode cross-link, ELF ABI audit, and UOS execution all passed."
