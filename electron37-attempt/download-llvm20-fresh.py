#!/usr/bin/env python3
"""Download the official LLVM archive with one ordinary full GET.

This is intentionally separate from the failed resume cache: no Range header,
alternate encoding, or mirror is used. A complete file is accepted only after
the official SHA256 check.
"""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

root = Path(__file__).resolve().parent
out = root / "llvm20-download-cache/full-fresh.tar.gz"
status_path = root / "logs/llvm20-fresh-status.json"
log_path = root / "logs/llvm20-fresh-download.log"
lock_path = root / "logs/llvm20-fresh.lock"
url = "https://ftp.loongnix.cn/toolchain/llvm/llvm20/llvm-toolchain_20.1.8-1_amd64-linux-gnu_debian-10.tar.gz"
size = 706463440
expected = (root / "tools/llvm20.sha256").read_text().split()[0]

lock = lock_path.open("a+")
try:
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
except BlockingIOError:
    raise SystemExit("fresh downloader already running")

out.parent.mkdir(parents=True, exist_ok=True)
if out.exists():
    out.unlink()

def write_status(status, phase, **extra):
    payload = {
        "status": status,
        "phase": phase,
        "bytes": out.stat().st_size if out.exists() else 0,
        "total_bytes": size,
        "updated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    payload.update(extra)
    temporary = status_path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n")
    temporary.replace(status_path)

def log(message):
    with log_path.open("a") as stream:
        stream.write(time.strftime("%Y-%m-%dT%H:%M:%SZ ", time.gmtime()) + message + "\n")

write_status("running", "ordinary_full_get", owner_pid=os.getpid())
log("Starting official full GET; no Range or alternate mirror")
command = [
    "curl", "--location", "--fail", "--silent", "--show-error",
    "--connect-timeout", "20", "--max-time", "14400",
    "--speed-time", "60", "--speed-limit", "1024",
    "--output", str(out), "--write-out",
    "http=%{http_code} downloaded=%{size_download} speed=%{speed_download}\\n", url,
]
process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
while process.poll() is None:
    time.sleep(30)
    current = out.stat().st_size if out.exists() else 0
    write_status("running", "ordinary_full_get", owner_pid=os.getpid())
    log(f"Progress {current}/{size} bytes ({current / size:.1%})")
stdout, stderr = process.communicate()
log(json.dumps({"returncode": process.returncode, "stdout": stdout, "stderr": stderr,
                "bytes": out.stat().st_size if out.exists() else 0}))
if process.returncode != 0 or not out.exists() or out.stat().st_size != size:
    write_status("failed", "ordinary_full_get", returncode=process.returncode,
                 stdout=stdout, stderr=stderr)
    raise SystemExit("official full GET did not produce a complete archive")
digest = hashlib.file_digest(out.open("rb"), "sha256") if hasattr(hashlib, "file_digest") else None
if digest is None:
    sha = hashlib.sha256()
    with out.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            sha.update(block)
    digest = sha
actual = digest.hexdigest()
if actual != expected:
    write_status("failed", "checksum", actual=actual, expected=expected)
    raise SystemExit("official full GET checksum mismatch")
archive = root / "tools/llvm20.tar.gz"
out.replace(archive)
write_status("complete", "checksum_verified", actual=actual)
log(f"SHA256 VERIFIED {actual}; installed archive at {archive}")
