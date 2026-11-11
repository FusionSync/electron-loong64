#!/usr/bin/env python3
"""Fetch checksum-pinned MIPS target inputs or optional x86_64 host tools."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
from urllib.parse import quote


def checksum(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host-tools", action="store_true",
                        help="fetch the optional standalone host-tools archives instead")
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument("--inputs-dir", type=Path, default=root / "inputs")
    args = parser.parse_args()
    manifest = root / "metadata" / ("host-tools.json" if args.host_tools else "inputs.json")
    entries = json.loads(manifest.read_text())["files"]
    mirror = os.environ.get("MIPS_INPUTS_BASE_URL", "").rstrip("/")
    for entry in entries:
        relative = Path(entry["path"])
        if relative.is_absolute() or ".." in relative.parts:
            raise SystemExit(f"unsafe manifest path: {relative}")
        output = args.inputs_dir / relative
        expected = entry["sha256"]
        if output.is_file() and checksum(output) == expected:
            print(f"Verified: {relative}", flush=True)
            continue
        if args.verify_only:
            raise SystemExit(f"Missing or invalid input: {output}")
        output.parent.mkdir(parents=True, exist_ok=True)
        partial = output.with_name(output.name + ".part")
        url = mirror + "/" + quote(entry["path"], safe="/") if mirror else entry["url"]
        print(f"Downloading: {relative}", flush=True)
        subprocess.run([
            "curl", "--fail", "--location", "--retry", "4", "--retry-delay", "2",
            "--continue-at", "-", "--output", str(partial), url,
        ], check=True)
        actual = checksum(partial)
        if actual != expected:
            raise SystemExit(
                f"SHA256 mismatch: {partial}\nexpected {expected}\nactual   {actual}\n"
                "The partial file has been kept for inspection; remove it before retrying."
            )
        partial.replace(output)
        print(f"Verified: {relative}", flush=True)


if __name__ == "__main__":
    main()
