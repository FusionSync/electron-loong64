#!/usr/bin/env python3
"""Audit every ELF in a MIPS64EL runtime directory before packaging it."""

import argparse
import json
import os
from pathlib import Path
import re
import struct
import subprocess


def version(value):
    return tuple(map(int, value.split(".")))


def readelf(path, option):
    return subprocess.check_output(
        ["readelf", option, str(path)], text=True,
        env={**os.environ, "LC_ALL": "C"}, stderr=subprocess.STDOUT,
    )


def inspect(path, relative, maximum):
    with path.open("rb") as stream:
        header = stream.read(64)
    errors = []
    result = {"file": str(relative)}
    if len(header) < 64 or header[:6] != b"\x7fELF\x02\x01":
        return {**result, "errors": ["expected ELF64 little-endian"]}
    machine = struct.unpack_from("<H", header, 18)[0]
    flags = struct.unpack_from("<I", header, 48)[0]
    result.update(machine=machine, flags=f"{flags:#x}")
    if machine != 8:
        return {**result, "errors": [f"expected MIPS machine 8, got {machine}"]}
    if flags & 0xF0000000 != 0x80000000:
        errors.append("expected MIPS64R2 ISA")
    if flags & 0x20 or flags & 0xF000:
        errors.append("expected N64 ABI")
    attributes = readelf(path, "-AW")
    for expected in (r"ISA:\s+MIPS64r2", r"GPR size:\s+64", r"CPR1 size:\s+64",
                     r"FP ABI:\s+Hard float \(double precision\)"):
        if not re.search(expected, attributes):
            errors.append(f"missing ABI attribute: {expected}")
    if not re.search(r"ISA Extension:\s+None", attributes):
        errors.append("unexpected ISA extension")
    if not re.search(r"ASEs:\s+None", attributes):
        errors.append("unexpected architecture-specific extension")
    versions = sorted(set(re.findall(r"\bGLIBC_([0-9]+(?:\.[0-9]+)+)\b",
                                     readelf(path, "-VW"))), key=version)
    result["maximum_glibc"] = versions[-1] if versions else None
    if versions and version(versions[-1]) > maximum:
        errors.append(f"GLIBC_{versions[-1]} exceeds selected baseline")
    program_headers = readelf(path, "-lW")
    match = re.search(r"Requesting program interpreter:\s*([^\]]+)\]", program_headers)
    interpreter = match.group(1).strip() if match else None
    result["interpreter"] = interpreter
    if interpreter is not None and interpreter != "/lib64/ld.so.1":
        errors.append(f"unexpected interpreter: {interpreter}")
    dynamic = readelf(path, "-dW")
    result["needed"] = re.findall(r"Shared library: \[([^\]]+)\]", dynamic)
    # Chromium's link-only sysroot stubs must never become shipped runtimes.
    symbols = readelf(path, "--dyn-syms")
    absolute_functions = [line.strip() for line in symbols.splitlines()
                          if re.search(r"\bFUNC\s+\S+\s+\S+\s+ABS\s+", line)]
    if absolute_functions:
        errors.append("absolute dynamic function symbols: " + "; ".join(absolute_functions))
    result["errors"] = errors
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--max-glibc", default="2.28")
    parser.add_argument("--require-electron", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.directory.resolve()
    if not root.is_dir():
        parser.error("directory must be an unpacked runtime directory")
    records = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink() or not path.is_file():
            continue
        with path.open("rb") as stream:
            magic = stream.read(4)
        if magic != b"\x7fELF":
            continue
        try:
            records.append(inspect(path, path.relative_to(root), version(args.max_glibc)))
        except (OSError, subprocess.CalledProcessError) as error:
            records.append({"file": str(path.relative_to(root)), "errors": [str(error)]})
    errors = []
    if not records:
        errors.append("no ELF files found")
    if args.require_electron and not any(record["file"] == "electron" for record in records):
        errors.append("electron executable missing")
    passed = not errors and all(not record["errors"] for record in records)
    result = {"status": "passed" if passed else "failed", "max_glibc": args.max_glibc,
              "target_executed": False, "real_hardware_verified": False,
              "errors": errors, "elf_files": records}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    main()
