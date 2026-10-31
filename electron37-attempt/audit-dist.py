#!/usr/bin/env python3
"""Read-only ABI and content audit for the UOS 20 Electron distribution."""
import argparse
import datetime
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import zipfile

BASE = Path(__file__).resolve().parent
EXECUTABLES = {"electron", "chrome_crashpad_handler", "chrome-sandbox", "chrome_sandbox"}
REQUIRED_ELFS = {
    "electron", "chrome_crashpad_handler", "chrome-sandbox", "libffmpeg.so",
    "libEGL.so", "libGLESv2.so", "libvulkan.so.1", "libvk_swiftshader.so",
}
REQUIRED_FILES = REQUIRED_ELFS | {
    "version", "LICENSE", "LICENSES.chromium.html", "resources.pak",
    "chrome_100_percent.pak", "chrome_200_percent.pak", "icudtl.dat",
    "snapshot_blob.bin", "v8_context_snapshot.bin", "resources/default_app.asar",
    "locales/en-US.pak", "locales/zh-CN.pak",
}


def readelf(path, option):
    result = subprocess.run(
        ["readelf", option, str(path)], capture_output=True, text=True,
        env=dict(os.environ, LC_ALL="C"),
    )
    if result.returncode:
        raise ValueError("readelf failed: " + result.stderr.strip())
    return result.stdout


def origin_path(value):
    """Allow paths contained in the directory of the distributed ELF."""
    for entry in value.split(":"):
        if not re.fullmatch(r"\$(?:ORIGIN|\{ORIGIN\})(?:/[A-Za-z0-9_.+-]+)*", entry):
            return False
        if ".." in entry.split("/"):
            return False
    return True


def audit_elf(path, label):
    report = {"file": label, "errors": []}
    errors = report["errors"]
    try:
        with path.open("rb") as source:
            header = source.read(64)
        if len(header) < 64 or header[:6] != b"\x7fELF\x02\x01":
            raise ValueError("Expected ELF64 little endian")
        elf_type = struct.unpack_from("<H", header, 16)[0]
        machine = struct.unpack_from("<H", header, 18)[0]
        flags = struct.unpack_from("<I", header, 48)[0]
        report.update(elf_type=elf_type, machine=machine, flags=hex(flags))
        if elf_type not in (2, 3):
            errors.append("Expected an executable or shared library, not an object")
        if machine != 258:
            errors.append("Expected LoongArch ELF machine 258")
        if flags != 3:
            errors.append("Expected old LoongArch LP64 ABI flags 0x3")
        program = readelf(path, "-lW")
        match = re.search(r"Requesting program interpreter: ([^\]]+)", program)
        interpreter = match.group(1) if match else None
        report["interpreter"] = interpreter
        if PurePosixPath(label).name in EXECUTABLES or elf_type == 2 or interpreter:
            if interpreter != "/lib64/ld.so.1":
                errors.append("Expected executable interpreter /lib64/ld.so.1")
        versions = readelf(path, "--version-info")
        # Version definitions describe exports; only Version needs are imports.
        needs = versions.split("Version needs section", 1)[-1] if "Version needs section" in versions else ""
        imported_glibc = set(re.findall(r"Name: (GLIBC_[A-Za-z0-9_.]+)", needs))
        unsupported = sorted(value for value in imported_glibc if not re.fullmatch(r"GLIBC_[0-9.]+", value))
        for version in unsupported:
            errors.append("Unsupported glibc ABI requirement: " + version)
        required = sorted(
            imported_glibc - set(unsupported),
            key=lambda value: tuple(map(int, value[6:].split("."))),
        )
        report["glibc_required"] = required
        report["glibc_other_requirements"] = unsupported
        if not required:
            errors.append("Expected a dynamically linked glibc executable/library")
        for version in required:
            numbers = tuple(map(int, version[6:].split(".")))
            if numbers + (0,) * (3 - len(numbers)) > (2, 28, 0):
                errors.append("glibc requirement exceeds 2.28: " + version)
        dynamic = readelf(path, "-dW")
        report["needed"] = re.findall(r"Shared library: \[([^\]]+)\]", dynamic)
        paths = re.findall(r"\((RPATH|RUNPATH)\).*?\[([^\]]*)\]", dynamic)
        report["library_paths"] = [{"kind": kind, "value": value} for kind, value in paths]
        for kind, value in paths:
            if not origin_path(value):
                errors.append(kind + " is outside the distribution directory: " + value)
        for needed in report["needed"]:
            if "/" in needed:
                errors.append("DT_NEEDED contains a path: " + needed)
    except (OSError, ValueError, struct.error) as error:
        errors.append(str(error))
    report["static_audit_passed"] = not errors
    return report


def audit_zip(path, report):
    with zipfile.ZipFile(path) as archive:
        members = {}
        for entry in archive.infolist():
            name = PurePosixPath(entry.filename)
            if name.is_absolute() or ".." in name.parts or "\\" in entry.filename:
                raise ValueError("Unsafe ZIP member: " + entry.filename)
            if entry.is_dir():
                continue
            normalized = str(name)
            if normalized in members:
                raise ValueError("Duplicate ZIP member: " + normalized)
            members[normalized] = entry
        report["member_count"] = len(members)
        missing = sorted(REQUIRED_FILES - members.keys())
        if missing:
            report["errors"].append("Missing required ZIP files: " + ", ".join(missing))
        for name in sorted(REQUIRED_FILES & members.keys()):
            if not members[name].file_size:
                report["errors"].append("Empty required ZIP file: " + name)
        bad_member = archive.testzip()
        report["zip_crc_passed"] = bad_member is None
        if bad_member:
            report["errors"].append("ZIP CRC failed: " + bad_member)
        if "version" in members:
            if members["version"].file_size > 4096:
                report["errors"].append("Unexpectedly large version file")
            else:
                report["electron_version"] = archive.read(members["version"]).decode("utf-8").strip()
        seen_elfs = set()
        with tempfile.TemporaryDirectory(prefix="uos-electron-dist-audit-") as directory:
            temporary = Path(directory) / "current-elf"
            for name, entry in sorted(members.items()):
                with archive.open(entry) as source:
                    header = source.read(64)
                    if header[:4] != b"\x7fELF":
                        continue
                    seen_elfs.add(name)
                    with temporary.open("wb") as output:
                        output.write(header)
                        shutil.copyfileobj(source, output, length=1024 * 1024)
                report["elfs"].append(audit_elf(temporary, name))
                temporary.unlink()
        non_elfs = sorted((REQUIRED_ELFS & members.keys()) - seen_elfs)
        if non_elfs:
            report["errors"].append("Required executable/library is not ELF: " + ", ".join(non_elfs))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--zip", type=Path, help="Distribution ZIP (default: src/out/UOS37/dist.zip)")
    modes.add_argument("--elf", type=Path, nargs="+", help="Audit existing ELF files only; does not certify a distribution")
    parser.add_argument("--report", type=Path, help="JSON evidence path (default: dist-audit/<mode>-audit.json)")
    args = parser.parse_args()
    mode = "elf" if args.elf else "dist"
    report = {
        "mode": mode,
        "created_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "errors": [], "elfs": [], "runtime_validation": "not_performed",
    }
    try:
        if args.elf:
            report["elfs"] = [audit_elf(path, str(path)) for path in args.elf]
        else:
            path = args.zip or BASE / "src/out/UOS37/dist.zip"
            report["zip"] = str(path)
            audit_zip(path, report)
    except (OSError, ValueError, zipfile.BadZipFile, RuntimeError) as error:
        report["errors"].append(str(error))
    report["passed"] = not report["errors"] and bool(report["elfs"]) and all(
        item["static_audit_passed"] for item in report["elfs"]
    )
    destination = args.report or BASE / "dist-audit" / (mode + "-audit.json")
    destination.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(report, indent=2) + "\n"
    temporary = destination.with_name(destination.name + ".tmp")
    temporary.write_text(rendered)
    temporary.replace(destination)
    print(rendered, end="")
    print("Audit evidence: " + str(destination), file=sys.stderr)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
