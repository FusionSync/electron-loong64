#!/usr/bin/env python3
"""Cross-compile real PartitionAlloc page-size functions and run them in QEMU.

Requires a patched, GN-generated source checkout, Clang 20, and a complete
MIPS64EL runtime sysroot. Chromium's reduced link sysroot cannot run binaries.
All generated executables are confined to a temporary directory.
"""

import argparse
from pathlib import Path
import subprocess
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--runtime-root", required=True, type=Path)
    parser.add_argument("--qemu", default="qemu-mips64el-static")
    parser.add_argument("--cpu", default="Loongson-3A4000")
    parser.add_argument("--llvm-root", type=Path, default=Path("/opt/llvm20"))
    parser.add_argument("--sysroot", type=Path, default=Path("/opt/mips-sysroot"))
    args = parser.parse_args()
    source = args.source_root.resolve()
    output = args.out_dir.resolve()
    pa = "base/allocator/partition_allocator/src"
    if not (output / "gen" / pa / "partition_alloc/buildflags.h").is_file():
        parser.error("--out-dir must contain GN-generated PartitionAlloc buildflags.h")
    flags = [
        str(args.llvm_root / "bin/clang++"),
        "--target=mips64el-linux-gnuabi64", f"--sysroot={args.sysroot.resolve()}",
        "-mcpu=mips64r2", "-mabi=64", "-mhard-float", "-std=c++20", "-O2",
        "-D_LIBCPP_HARDENING_MODE=_LIBCPP_HARDENING_MODE_EXTENSIVE",
        "-D_LIBCPP_DISABLE_VISIBILITY_ANNOTATIONS",
        "-D_LIBCXXABI_DISABLE_VISIBILITY_ANNOTATIONS", "-nostdinc++", "-nostdlib++",
        f"-isystem{source / 'third_party/libc++/src/include'}",
        f"-isystem{source / 'third_party/libc++abi/src/include'}",
        f"-I{source / pa}", f"-I{output / 'gen' / pa}",
        f"-I{source}", f"-I{output / 'gen'}",
        f"-I{source / 'buildtools/third_party/libc++'}",
    ]
    qemu = [
        args.qemu, "-cpu", args.cpu, "-L", str(args.runtime_root.resolve()),
        "-E", "LD_LIBRARY_PATH=/lib/mips64el-linux-gnuabi64:"
        "/usr/lib/mips64el-linux-gnuabi64",
    ]
    probe = Path(__file__).resolve().with_name("probe.cc")
    with tempfile.TemporaryDirectory(prefix="mips-pa-pages-") as directory:
        for page in (4096, 16384, 65536, None):
            binary = Path(directory) / f"probe-{page or 'actual'}"
            extra = [] if page is None else [
                f"-DPROBE_PAGE_SIZE={page}", "-Wl,--wrap=getpagesize",
            ]
            subprocess.run([*flags, *extra, str(probe), "-o", str(binary)], check=True)
            subprocess.run([*qemu, str(binary)], check=True)
    print("All real-header MIPS64EL page-size probes passed.")


if __name__ == "__main__":
    main()
