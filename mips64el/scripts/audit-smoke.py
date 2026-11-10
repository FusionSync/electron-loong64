#!/usr/bin/env python3
"""Assert MIPS64R2 little-endian N64 hard-float ELF properties after linking."""

import argparse
import json
import os
from pathlib import Path
import re
import struct
import subprocess


def readelf(path, option):
    return subprocess.check_output(["readelf", option, str(path)], text=True,
                                   env={**os.environ, "LC_ALL": "C"})


def resolve_sysroot_file(path, sysroot):
    for _ in range(16):
        if not path.is_symlink():
            return path
        target = Path(os.readlink(path))
        path = sysroot / str(target).lstrip("/") if target.is_absolute() else path.parent / target
    raise SystemExit(f"too many symlinks resolving target libc: {path}")


def maximum(versions):
    return max(versions, key=lambda value: tuple(map(int, value.split(".")))) if versions else None


def inspect(path):
    with path.open("rb") as stream:
        header = stream.read(64)
    if len(header) < 64 or header[:6] != b"\x7fELF\x02\x01":
        raise SystemExit(f"Expected ELF64 little-endian output: {path}")
    machine = struct.unpack_from("<H", header, 18)[0]
    flags = struct.unpack_from("<I", header, 48)[0]
    if machine != 8:
        raise SystemExit(f"Expected MIPS ELF machine 8, got {machine}: {path}")
    if flags & 0xF0000000 != 0x80000000:
        raise SystemExit(f"Expected MIPS64R2 ISA flags, got {flags:#x}: {path}")
    if flags & 0x20 or flags & 0xF000:
        raise SystemExit(f"Unexpected non-N64 ABI flags in ELF64 output: {path}")
    sections = {
        "header": readelf(path, "-hW"),
        "attributes": readelf(path, "-AW"),
        "program_headers": readelf(path, "-lW"),
        "versions": readelf(path, "-VW"),
        "dynamic": readelf(path, "-dW"),
    }
    for name, output in sections.items():
        path.with_name(path.name + "." + name + ".txt").write_text(output)
    attributes = sections["attributes"]
    for expected in (r"ISA:\s+MIPS64r2", r"GPR size:\s+64", r"CPR1 size:\s+64",
                     r"FP ABI:\s+Hard float \(double precision\)"):
        if not re.search(expected, attributes):
            raise SystemExit(f"Missing expected MIPS ABI attribute {expected}: {path}")
    match = re.search(r"Requesting program interpreter:\s*([^\]]+)\]", sections["program_headers"])
    interpreter = match.group(1).strip() if match else None
    if interpreter != "/lib64/ld.so.1":
        raise SystemExit(f"Unexpected dynamic loader {interpreter!r}: {path}")
    glibc_versions = sorted(set(re.findall(r"\bGLIBC_([0-9]+(?:\.[0-9]+)+)\b", sections["versions"])),
                            key=lambda value: tuple(map(int, value.split("."))))
    needed = re.findall(r"Shared library: \[([^\]]+)\]", sections["dynamic"])
    return {
        "file": str(path), "elf_class": 64, "endianness": "little", "machine": machine,
        "flags": f"{flags:#x}", "isa": "MIPS64R2", "abi": "N64", "float_abi": "hard-double",
        "interpreter": interpreter, "needed": needed, "required_glibc_versions": glibc_versions,
        "maximum_required_glibc": maximum(glibc_versions),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sysroot", type=Path, required=True)
    parser.add_argument("--triple", default="mips64el-linux-gnuabi64")
    parser.add_argument("--compiler", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("programs", type=Path, nargs="+")
    args = parser.parse_args()
    libc = args.sysroot / "lib" / args.triple / "libc.so.6"
    libc = resolve_sysroot_file(libc, args.sysroot)
    if not libc.is_file():
        raise SystemExit(f"Missing target libc: {libc}")
    version = re.fullmatch(r"libc-([0-9.]+)\.so", libc.name)
    if version is None:
        version = re.search(rb"release version ([0-9.]+)", libc.read_bytes())
        libc_version = version.group(1).decode("ascii") if version else "unknown"
    else:
        libc_version = version.group(1)
    features = args.sysroot / "usr/include/features.h"
    macros = features.read_text() if features.is_file() else ""
    major = re.search(r"^\s*#\s*define\s+__GLIBC__\s+(\d+)", macros, re.M)
    minor = re.search(r"^\s*#\s*define\s+__GLIBC_MINOR__\s+(\d+)", macros, re.M)
    header_version = major.group(1) + "." + minor.group(1) if major and minor else None
    result = {
        "status": "passed", "target_executed": False,
        "full_electron_verified": False, "electron_libcxx_verified": False,
        "compiler_version": subprocess.check_output([args.compiler, "--version"], text=True).strip(),
        "cxx_probe_standard_library": "GCC 10 support libstdc++; Electron uses separate in-tree libc++",
        "sysroot": {"path": str(args.sysroot), "libc_file": str(libc),
                    "libc_version": libc_version, "glibc_header_macros": header_version,
                    "glibc_2_28_compatibility_validated": False},
        "programs": [inspect(program) for program in args.programs],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    print(f"Sysroot contains glibc {libc_version}; smoke symbol versions do not establish a glibc 2.28 release baseline.")


if __name__ == "__main__":
    main()
