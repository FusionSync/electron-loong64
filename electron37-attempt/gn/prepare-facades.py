#!/usr/bin/env python3
"""Create local tool/resource facades without changing Chromium or vendor tools."""
from pathlib import Path
import os

root = Path(__file__).resolve().parent


def link(relative, destination):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        if os.readlink(path) == destination:
            return
        raise SystemExit("existing symlink differs: " + str(path))
    if path.exists():
        raise SystemExit("refusing to replace: " + str(path))
    path.symlink_to(destination)


for name in ("compiler-driver.py", "pkg-config", "bindgen-launcher"):
    path = root / name
    path.chmod(path.stat().st_mode | 0o111)
for tool in ("clang", "clang++", "llvm-ar", "llvm-nm", "llvm-readelf",
             "llvm-objcopy", "llvm-objdump", "llvm-strip", "llvm-symbolizer", "ld.lld"):
    link("clang-facade/bin/" + tool, "../../compiler-driver.py")
# The directory is real so missing target runtimes can be added here later,
# without modifying the vendor toolchain. Resource/include paths stay pinned.
link("clang-facade/lib/clang/20/include", "../../../../../tools/llvm20/lib/clang/20/include")
link("clang-facade/lib/clang/20/share", "../../../../../tools/llvm20/lib/clang/20/share")
runtime_libraries = root.parent / "tools/llvm20/lib/clang/20/lib"
if runtime_libraries.is_dir():
    for original in sorted(runtime_libraries.rglob("*")):
        relative = "clang-facade/lib/clang/20/lib/" + str(original.relative_to(runtime_libraries))
        if original.is_dir():
            (root / relative).mkdir(parents=True, exist_ok=True)
        else:
            link(relative, os.path.relpath(original, (root / relative).parent))
    # Chromium's host toolchain asks for the conventional Linux Clang name,
    # while the vendor archive keeps x86_64 runtimes under its full target
    # triple directory.  Keep the archive untouched and expose the one alias
    # GN needs for host Rust allocator objects.
    host_builtins = runtime_libraries / "x86_64-unknown-linux-gnu/libclang_rt.builtins.a"
    if host_builtins.exists():
        alias = root / "clang-facade/lib/clang/20/lib/linux/libclang_rt.builtins-x86_64.a"
        link("clang-facade/lib/clang/20/lib/linux/libclang_rt.builtins-x86_64.a",
             os.path.relpath(host_builtins, alias.parent))
link("bindgen-facade/bin/bindgen", "../../bindgen-launcher")
link("bindgen-facade/lib", "../../tools/llvm20/lib")
print("Prepared facades; unavailable downloaded tools remain explicit dangling symlinks.")
