#!/usr/bin/env python3
"""Run real Marl N64 fiber swaps under a Loongson-3A4000 QEMU CPU.

All outputs stay in a temporary directory. The source root must already have
the recipe's source patches; no GN or Ninja invocation is performed.
"""

import argparse
from pathlib import Path
import subprocess
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--runtime-root", required=True, type=Path)
    parser.add_argument("--qemu", default="qemu-mips64el-static")
    parser.add_argument("--cpu", default="Loongson-3A4000")
    parser.add_argument("--llvm-root", type=Path, default=Path("/opt/llvm20"))
    parser.add_argument("--sysroot", type=Path,
                        default=Path("/opt/mips-sysroot-buster"))
    parser.add_argument("--linker", default=(
        "/opt/mips-toolchain/usr/bin/mips64el-linux-gnuabi64-ld"))
    parser.add_argument("--baseline-assembly", type=Path,
                        help="Optional original assembly: require FPR failure")
    args = parser.parse_args()
    marl = args.source_root.resolve() / "third_party/swiftshader/third_party/marl"
    tests = Path(__file__).resolve().parent
    assembly = marl / "src/osfiber_asm_mips64.S"
    if not assembly.is_file():
        parser.error("--source-root does not contain the real Marl MIPS64 source")
    flags = [
        str(args.llvm_root / "bin/clang"),
        "--target=mips64el-linux-gnuabi64", "-mcpu=mips64r2", "-mabi=64",
        "-mhard-float", f"--sysroot={args.sysroot.resolve()}",
        f"-fuse-ld={args.linker}", "-std=c11", "-fPIC", "-pie",
        "-fstack-protector", "-fno-omit-frame-pointer",
        f"-I{marl / 'src'}", f"-I{marl / 'include'}",
        str(tests / "probe.c"), str(tests / "registers.S"),
        str(marl / "src/osfiber_mips64.c"),
    ]
    qemu = [
        args.qemu, "-cpu", args.cpu, "-L", str(args.runtime_root.resolve()),
        "-E", "LD_LIBRARY_PATH=/lib/mips64el-linux-gnuabi64:"
        "/usr/lib/mips64el-linux-gnuabi64",
    ]
    with tempfile.TemporaryDirectory(prefix="mips-marl-fibers-") as directory:
        for optimization in ("-O0", "-O2", "-Os"):
            sources = [("patched", assembly)]
            if args.baseline_assembly:
                sources.insert(0, ("baseline", args.baseline_assembly.resolve()))
            for label, selected in sources:
                binary = Path(directory) / (optimization[1:] + "-" + label)
                subprocess.run([*flags, optimization, str(selected), "-o", str(binary)],
                               check=True)
                result = subprocess.run([*qemu, str(binary)], text=True,
                                        stdout=subprocess.PIPE,
                                        stderr=subprocess.STDOUT, timeout=30)
                print(f"{optimization} {label}: exit {result.returncode}", flush=True)
                print(result.stdout, end="", flush=True)
                if label == "baseline":
                    if result.returncode != 1 or "f30 mismatch" not in result.stdout:
                        raise SystemExit("Original assembly did not expose the FPR regression")
                elif result.returncode:
                    raise SystemExit(result.returncode)
    print("All real Marl MIPS64EL fiber probes passed.")


if __name__ == "__main__":
    main()
