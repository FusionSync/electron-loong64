#!/usr/bin/env python3
"""Record a successful Electron Ninja invocation; call only after its exit 0."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("out", type=Path)
    parser.add_argument("--ninja-exit-code", type=int, choices=[0], required=True,
                        help="the observed Ninja exit code; only zero is accepted")
    args = parser.parse_args()
    root = args.out.resolve()
    files = []
    for name in ("electron", "args.gn", "build.ninja", "gen/electron/electron_version.args"):
        path = root / name
        if not path.is_file() or path.is_symlink() or not path.stat().st_size:
            parser.error(f"Missing completed build artifact: {path}")
        files.append({"path": name, "size": path.stat().st_size, "sha256": digest(path)})
    with (root / "electron").open("rb") as stream:
        header = stream.read(64)
    if (len(header) < 64 or header[:6] != b"\x7fELF\x02\x01"
            or struct.unpack_from("<H", header, 18)[0] != 8
            or struct.unpack_from("<H", header, 16)[0] not in (2, 3)):
        parser.error("electron must be a little-endian ELF64 MIPS executable")
    # The standalone version file belongs to electron_dist_zip, not electron.
    version = json.loads((root / "gen/electron/electron_version.args").read_text())["full_version"]
    version = version.removeprefix("v")
    if not re.fullmatch(r"\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?", version):
        parser.error("Unrecognized Electron version file")
    revision = subprocess.check_output(
        ["git", "-C", str(args.source), "rev-parse", "HEAD"], text=True).strip()
    electron_revision = subprocess.check_output(
        ["git", "-C", str(args.source / "electron"), "rev-parse", "HEAD"], text=True).strip()
    record = {"schema": 1, "status": "complete", "target": "electron",
              "target_cpu": "mips64el", "version": version,
              "ninja_exit_code": 0, "source_revision": revision,
              "electron_revision": electron_revision,
              "recorded_at_utc": datetime.now(timezone.utc).isoformat(), "files": files}
    target = root / ".electron-build-success.json"
    temporary = target.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(record, indent=2) + "\n")
    temporary.replace(target)
    print(f"Recorded completed Electron build: {target}")


if __name__ == "__main__":
    main()
