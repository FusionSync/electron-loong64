#!/usr/bin/env python3
"""Collect existing Electron release assets from a completed build, without Ninja.

The output tree is read only. A matching record-build-success.py marker and an
existing official electron_dist_zip are mandatory. Optional assets are reported
when absent; debug and symbols are never required for symbol_level=0 builds.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import struct
import subprocess
import sys
import tarfile
import tempfile
import zipfile


def digest(path):
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def check_success(root):
    marker = root / ".electron-build-success.json"
    if not marker.is_file():
        raise ValueError("No complete Electron build record. Run packaging only after Ninja electron exits 0 and record-build-success.py records it.")
    record = json.loads(marker.read_text())
    if (record.get("schema"), record.get("status"), record.get("target"),
        record.get("target_cpu"), record.get("ninja_exit_code")) != (1, "complete", "electron", "mips64el", 0):
        raise ValueError("Invalid Electron build success record")
    expected = {"electron", "args.gn", "build.ninja", "gen/electron/electron_version.args"}
    if {entry["path"] for entry in record["files"]} != expected:
        raise ValueError("Incomplete build success record")
    for entry in record["files"]:
        path = root / entry["path"]
        if (not path.is_file() or path.is_symlink() or path.stat().st_size != entry["size"]
                or digest(path) != entry["sha256"]):
            raise ValueError("Build changed since successful Ninja: " + entry["path"])
    if not re.fullmatch(r"\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?", record["version"]):
        raise ValueError("Invalid recorded Electron version")
    return record


def safe_name(name):
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or "\\" in name:
        raise ValueError("Unsafe archive member: " + name)
    return str(path)


def check_zip(path):
    with zipfile.ZipFile(path) as archive:
        names, machines = set(), set()
        for entry in archive.infolist():
            name = safe_name(entry.filename)
            if name in names:
                raise ValueError("Duplicate archive member: " + name)
            names.add(name)
            if not entry.is_dir():
                with archive.open(entry) as stream:
                    header = stream.read(64)
                if header.startswith(b"\x7fELF"):
                    if len(header) < 64 or header[4:6] != b"\x02\x01":
                        raise ValueError("Non-ELF64/little-endian binary in " + str(path))
                    machines.add(struct.unpack_from("<H", header, 18)[0])
        bad = archive.testzip()
        if bad is not None or not names:
            raise ValueError("Empty or corrupt zip: " + str(path))
    return names, machines


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("out", type=Path)
    parser.add_argument("destination", type=Path, help="new directory outside the build output")
    parser.add_argument("--max-glibc", default="2.28")
    args = parser.parse_args()
    root = args.out.resolve()
    destination = args.destination.resolve()
    stage = None
    try:
        if destination == root or root in destination.parents or destination in root.parents:
            raise ValueError("Release destination must be separate from the build output")
        if destination.exists():
            raise ValueError("Release destination already exists; choose a new directory")
        success = check_success(root)
        version = success["version"]
        dist = root / "dist.zip"
        if not dist.is_file() or dist.is_symlink():
            raise ValueError("dist.zip is missing. Generate the official electron_dist_zip target after the main build succeeds.")
        names, machines = check_zip(dist)
        required = {"electron", "version", "LICENSE", "LICENSES.chromium.html", "icudtl.dat",
                    "resources.pak", "chrome_100_percent.pak", "resources/default_app.asar", "chrome-sandbox"}
        if not required.issubset(names) or not any(name.startswith("locales/") and name.endswith(".pak") for name in names):
            raise ValueError("dist.zip lacks required runtime files: " + ", ".join(sorted(required - names)))
        if machines != {8}:
            raise ValueError(f"Runtime zip contains unexpected ELF machines: {sorted(machines)}")
        with zipfile.ZipFile(dist) as archive:
            if archive.read("version").decode().strip().removeprefix("v") != version:
                raise ValueError("Runtime zip version differs from the completed build")
            with archive.open("electron") as stream:
                binary_digest = hashlib.file_digest(stream, "sha256").hexdigest() if hasattr(hashlib, "file_digest") else None
                if binary_digest is None:
                    value = hashlib.sha256()
                    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                        value.update(chunk)
                    binary_digest = value.hexdigest()
            if binary_digest != digest(root / "electron"):
                raise ValueError("Runtime zip electron differs from the completed build")
        destination.parent.mkdir(parents=True, exist_ok=True)
        stage = Path(tempfile.mkdtemp(prefix=destination.name + ".partial-", dir=destination.parent))
        runtime = stage / ".runtime-audit"
        runtime.mkdir()
        with zipfile.ZipFile(dist) as archive:
            archive.extractall(runtime)
        audit_script = Path(__file__).resolve().with_name("audit-dist.py")
        subprocess.run([sys.executable, str(audit_script), str(runtime), "--max-glibc", args.max_glibc,
                        "--require-electron", "--output", str(stage / "runtime-audit.json")], check=True)
        shutil.rmtree(runtime)
        assets = [
            ("dist.zip", f"electron-v{version}-linux-mips64el.zip", "electron_dist_zip"),
            ("ffmpeg.zip", f"ffmpeg-v{version}-linux-mips64el.zip", "electron_ffmpeg_zip"),
            ("chromedriver.zip", f"chromedriver-v{version}-linux-mips64el.zip", "electron_chromedriver_zip"),
            ("mksnapshot.zip", f"mksnapshot-v{version}-linux-mips64el.zip", "electron_mksnapshot_zip"),
            ("hunspell_dictionaries.zip", "hunspell-dictionaries.zip", "hunspell_dictionaries_zip"),
            ("libcxx_headers.zip", "libcxx-headers.zip", "libcxx_headers_zip"),
            ("libcxxabi_headers.zip", "libcxxabi-headers.zip", "libcxxabi_headers_zip"),
            ("libcxx_objects.zip", f"libcxx-objects-v{version}-linux-mips64el.zip", "libcxx_objects_zip"),
            ("gen/node_headers.tar.gz", f"node-v{version}-headers.tar.gz", "node_headers"),
            ("symbols.zip", f"electron-v{version}-linux-mips64el-symbols.zip", "electron_symbols + electron/script/zip-symbols.py"),
            ("debug.zip", f"electron-v{version}-linux-mips64el-debug.zip", "electron_symbols + electron/script/zip-symbols.py"),
        ]
        collected, unavailable = [], []
        for source, name, target in assets:
            path = root / source
            if not path.is_file() or path.is_symlink() or not path.stat().st_size:
                unavailable.append({"source": source, "target": target, "reason": "not generated"})
                continue
            machines = set()
            if path.suffix == ".zip":
                member_names, machines = check_zip(path)
                if source == "symbols.zip" and not any(x.endswith(".sym") for x in member_names):
                    unavailable.append({"source": source, "target": target, "reason": "no symbol payload"})
                    continue
                if source == "debug.zip" and not machines:
                    unavailable.append({"source": source, "target": target, "reason": "no ELF debug payload"})
                    continue
                if source == "mksnapshot.zip" and machines == {62}:
                    # Cross-build snapshot generators can be x64 executables.
                    name = f"mksnapshot-v{version}-linux-x64-for-mips64el.zip"
                elif machines - {8}:
                    raise ValueError(f"Unexpected ELF machines in {source}: {sorted(machines)}")
            else:
                with tarfile.open(path, "r:gz") as archive:
                    members = archive.getmembers()
                    for member in members:
                        safe_name(member.name)
                    if not any(member.name.endswith("/node.h") for member in members):
                        raise ValueError("Node headers archive has no node.h")
            output = stage / name
            shutil.copy2(path, output)
            output_digest = digest(output)
            if output_digest != digest(path):
                raise ValueError("Asset changed while being collected: " + source)
            collected.append({"name": name, "source": source, "target": target,
                              "size": output.stat().st_size, "sha256": output_digest,
                              "elf_machines": sorted(machines)})
        check_success(root)
        manifest = {"schema": 1, "version": version, "target_cpu": "mips64el",
                    "max_glibc": args.max_glibc, "created_at_utc": datetime.now(timezone.utc).isoformat(),
                    "build_success": success, "assets": collected, "unavailable": unavailable,
                    "target_executed": False, "real_hardware_verified": False,
                    "notes": ["Collected existing official target outputs; no compilation or upload performed.",
                              "Debug and symbols are optional and depend on the build's symbol settings.",
                              "An x64 mksnapshot cross generator is named linux-x64-for-mips64el explicitly.",
                              "ffmpeg.zip follows this build's codec configuration; no separate free-codec build is implied."]}
        (stage / "release-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        lines = [f"{digest(path)}  {path.name}\n" for path in sorted(stage.iterdir()) if path.is_file()]
        (stage / "SHASUMS256.txt").write_text("".join(lines))
        stage.rename(destination)
        stage = None
        print(f"Collected {len(collected)} assets: {destination}")
        for item in unavailable:
            print(f"Unavailable: {item['source']} ({item['reason']}); target: {item['target']}")
    except (OSError, ValueError, KeyError, zipfile.BadZipFile, tarfile.TarError,
            subprocess.CalledProcessError) as error:
        parser.exit(1, f"ERROR: {error}\n")
    finally:
        if stage is not None:
            shutil.rmtree(stage)


if __name__ == "__main__":
    main()
