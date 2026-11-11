#!/usr/bin/env python3
"""Install the generated Linux MIPS64R2 FFmpeg config/source lists.

Run after the official Electron patches and before GN generation. This helper
only edits the selected source tree's third_party/ffmpeg subtree. It verifies
both the source baseline and bundled generated data before writing anything.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


IMPORT = '''
# Linux MIPS64R2/N64 configurations generated from this FFmpeg revision.
if (use_linux_config && current_cpu == "mips64el") {
  import("ffmpeg_mips64el_generated.gni")
  ffmpeg_c_sources = []
  ffmpeg_gas_sources = []
  ffmpeg_asm_sources = []
  ffmpeg_c_sources = mips64el_ffmpeg_c_sources
  ffmpeg_gas_sources = mips64el_ffmpeg_gas_sources
  ffmpeg_asm_sources = mips64el_ffmpeg_asm_sources
}
'''


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_root", type=Path)
    args = parser.parse_args()
    ffmpeg = args.source_root.expanduser().resolve() / "third_party/ffmpeg"
    payload = Path(__file__).resolve().parent / "ffmpeg-mips64el"
    manifest = json.loads((payload / "manifest.json").read_text())
    original_gni = ffmpeg / "ffmpeg_generated.gni"
    original_text = original_gni.read_text()
    if 'import("ffmpeg_mips64el_generated.gni")' in original_text:
        if not original_text.endswith(IMPORT):
            raise SystemExit("unexpected MIPS64EL import context in ffmpeg_generated.gni")
        original_text = original_text.removesuffix(IMPORT)
    baseline = {
        "configure": (ffmpeg / "configure").read_bytes(),
        "ffmpeg_generated.gni": original_text.encode(),
    }
    for name, data in baseline.items():
        if sha256(data) != manifest["baseline_sha256"][name]:
            raise SystemExit(f"FFmpeg source baseline mismatch: {name}")
    contents = {}
    for relative in manifest["files"]:
        path = Path(relative)
        if path.is_absolute() or ".." in path.parts:
            raise SystemExit(f"invalid bundled path: {relative}")
        data = (payload / path).read_bytes()
        if sha256(data) != manifest["file_sha256"][relative]:
            raise SystemExit(f"FFmpeg generated-data checksum mismatch: {relative}")
        contents[path] = data
    changed = 0
    for relative, data in contents.items():
        target = ffmpeg / relative
        if not target.is_file() or target.read_bytes() != data:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            changed += 1
    new_text = original_text + IMPORT
    if original_gni.read_text() != new_text:
        original_gni.write_text(new_text)
        changed += 1
    print(f"FFmpeg MIPS64R2 configs installed ({changed} changed, "
          f"{len(contents) + 1 - changed} already applied)")


if __name__ == "__main__":
    main()
