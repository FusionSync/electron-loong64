#!/usr/bin/env python3
"""Validate the executable ABI against this UOS 20 target."""
import json
import pathlib
import re
import struct
import subprocess
import sys

reports = []
for filename in sys.argv[1:]:
    path = pathlib.Path(filename)
    header = path.read_bytes()[:64]
    assert header[:6] == b"\x7fELF\x02\x01", "Expected ELF64 little endian"
    machine = struct.unpack_from("<H", header, 18)[0]
    flags = struct.unpack_from("<I", header, 48)[0]
    assert machine == 258, "Expected LoongArch ELF"
    assert flags == 3, "Expected target's old LoongArch LP64 ABI flags (0x3)"
    program = subprocess.check_output(["readelf", "-l", str(path)], universal_newlines=True)
    match = re.search(r"Requesting program interpreter: ([^\]]+)", program)
    interpreter = match.group(1) if match else None
    assert interpreter == "/lib64/ld.so.1", "Unexpected target interpreter"
    versions = subprocess.check_output(["readelf", "--version-info", str(path)], universal_newlines=True)
    required = sorted(set(re.findall(r"Name: (GLIBC_[0-9.]+)", versions)),
                      key=lambda s: tuple(map(int, s[6:].split("."))))
    assert required, "Expected a dynamically linked glibc program"
    assert all(tuple(map(int, s[6:].split("."))) <= (2, 28) for s in required), "glibc requirement too new"
    dynamic = subprocess.check_output(["readelf", "-d", str(path)], universal_newlines=True)
    assert not re.search(r"\((?:RPATH|RUNPATH)\)", dynamic), "Unexpected embedded library search path"
    reports.append({"file": str(path), "machine": machine, "flags": hex(flags),
                    "interpreter": interpreter, "glibc_required": required,
                    "needed": re.findall(r"Shared library: \[([^\]]+)\]", dynamic),
                    "static_audit_passed": True})
print(json.dumps(reports, indent=2))
