#!/usr/bin/env bash
# Compile with the same LLVM major used for Electron; never execute target ELF.
set -euo pipefail
root=$(cd -- "$(dirname -- "$0")/.." && pwd)
out=${OUT_DIR:-$root/output/clang20-smoke}
mkdir -p "$out"

sysroot=${MIPS64EL_SYSROOT:-/opt/mips-sysroot}
triple=${MIPS64EL_TRIPLE:-mips64el-linux-gnuabi64}
clang=${MIPS64EL_CLANG:-/opt/llvm20/bin/clang}
clangxx=${MIPS64EL_CLANGXX:-/opt/llvm20/bin/clang++}
gcc_install=${MIPS64EL_GCC_INSTALL:-/opt/mips-toolchain/usr/lib/gcc-cross/$triple/10}
linker=${MIPS64EL_GNU_LD:-/opt/mips-toolchain/usr/bin/$triple-ld}

export LC_ALL=C
export PATH="/opt/llvm20/bin:/opt/node/bin:/opt/mips-toolchain/usr/bin:$PATH"
export LD_LIBRARY_PATH="/opt/llvm-deps:/opt/llvm20/lib:/opt/mips-toolchain/usr/lib/x86_64-linux-gnu:/opt/mips-toolchain/usr/lib:/opt/mips-toolchain/lib:${LD_LIBRARY_PATH:-}"

"$clang" --version | tee "$out/clang-version.txt"
if ! head -1 "$out/clang-version.txt" | grep -Eq 'clang version 20\.'; then
  echo 'The primary smoke test requires LLVM/Clang 20.' >&2
  exit 2
fi
[[ -d "$gcc_install" && -x "$linker" ]] || {
  echo "Missing GCC runtime/CRT directory or GNU linker: $gcc_install / $linker" >&2
  exit 2
}
common=(--target="$triple" --sysroot="$sysroot" --gcc-install-dir="$gcc_install"
        -march=mips64r2 -mabi=64 -mhard-float -fuse-ld="$linker")

cat >"$out/hello-clang20.c" <<'SOURCE'
#include <stdio.h>
int main(void) { puts("electron-mips64el-clang20-c-smoke"); return 0; }
SOURCE
cat >"$out/concepts-clang20.cc" <<'SOURCE'
#include <concepts>
#include <cstdio>
#include <string>

template <std::integral T>
constexpr T plus_one(T value) { return value + 1; }

template <class T>
concept Scalable = requires(T value) {
  { value * 2 } -> std::same_as<T>;
};

static_assert(Scalable<int>);
static_assert(!std::integral<double>);
static_assert(plus_one(41) == 42);

int main() {
  std::string message = "electron-mips64el-clang20-cxx20-concepts:";
  message += std::to_string(plus_one(41));
  std::puts(message.c_str());
  return plus_one(41) == 42 ? 0 : 1;
}
SOURCE

commands="$out/build-commands.txt"
: >"$commands"
for source_file in hello-clang20.c concepts-clang20.cc; do
  if [[ $source_file == *.cc ]]; then
    command=("$clangxx" "${common[@]}" -std=c++20 -stdlib=libstdc++
             "$out/$source_file" -o "$out/concepts-clang20-mips64el")
  else
    command=("$clang" "${common[@]}" -std=c11
             "$out/$source_file" -o "$out/hello-clang20-mips64el")
  fi
  printf '%q ' "${command[@]}" >>"$commands"
  printf '\n' >>"$commands"
  "${command[@]}"
done

python3 "$root/scripts/audit-smoke.py" \
  --sysroot "$sysroot" --triple "$triple" --compiler "$clang" \
  --output "$out/elf-audit.json" \
  "$out/hello-clang20-mips64el" "$out/concepts-clang20-mips64el"
printf '\nClang 20 C/C++20 cross-compilation and ELF audit passed: %s\n' "$out"
printf 'Target programs were not executed. Full Electron/libc++ and device runtime remain unverified.\n'
