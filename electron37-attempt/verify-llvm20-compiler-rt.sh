#!/bin/bash
set -euo pipefail
attempt=$(cd -- "$(dirname -- "$0")" && pwd)
project=$(cd -- "$attempt/.." && pwd)
runtime="$attempt/host-runtime"
smoke="$attempt/llvm20-smoke"
mode=${1:-builtins}
exec > >(tee "$attempt/logs/llvm20-$mode-validation.log") 2>&1

flags=()
case "$mode" in
    builtins) ;;
    profile) flags=(-fprofile-instr-generate -Wl,--trace-symbol=__llvm_profile_write_file) ;;
    *) echo "Unknown compiler runtime validation mode: $mode" >&2; exit 2 ;;
esac
"$runtime/bin/uos-clang" -rtlib=compiler-rt "${flags[@]}" "$smoke/compiler-rt.c" \
    -Wl,--trace-symbol=__udivti3 -o "$smoke/compiler-rt-$mode" \
    2>&1 | tee "$attempt/logs/llvm20-$mode-link.log"
"$runtime/bin/python3" "$attempt/check-llvm20-symbol-provider.py" \
    "$attempt/logs/llvm20-$mode-link.log" libclang_rt.builtins-loongarch64.a __udivti3
if [[ "$mode" == profile ]]; then
    "$runtime/bin/python3" "$attempt/check-llvm20-symbol-provider.py" \
        "$attempt/logs/llvm20-$mode-link.log" libclang_rt.profile-loongarch64.a __llvm_profile_write_file
fi
"$runtime/bin/python3" "$project/scripts/audit-elf.py" "$smoke/compiler-rt-$mode"

if [[ "$mode" == builtins ]]; then
"$runtime/bin/ssh" -S "$project/.ssh-control" -o BatchMode=yes -p "${UOS_SSH_PORT:-22}" "${UOS_SSH_USER:-UOS}@${UOS_SSH_HOST:-127.0.0.1}" \
    'set -eu; dir=$(mktemp -d /tmp/uos-llvm20-compiler-rt-XXXXXX); trap '\''rm -rf "$dir"'\'' EXIT; cat > "$dir/program"; chmod 700 "$dir/program"; "$dir/program"' \
    < "$smoke/compiler-rt-builtins"
else
"$runtime/bin/ssh" -S "$project/.ssh-control" -o BatchMode=yes -p "${UOS_SSH_PORT:-22}" "${UOS_SSH_USER:-UOS}@${UOS_SSH_HOST:-127.0.0.1}" \
    'set -eu; dir=$(mktemp -d /tmp/uos-llvm20-profile-XXXXXX); trap '\''rm -rf "$dir"'\'' EXIT; cat > "$dir/program"; chmod 700 "$dir/program"; LLVM_PROFILE_FILE="$dir/program.profraw" "$dir/program"; test -s "$dir/program.profraw"; printf "LLVM profile output bytes="; wc -c < "$dir/program.profraw"' \
    < "$smoke/compiler-rt-profile"
fi
echo "LLVM20 compiler-rt $mode linked from vendor archive, passed ABI audit, and ran on UOS."
