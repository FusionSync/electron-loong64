#!/usr/bin/env python3
"""Persistent ordinary GET/resume; verify before extraction; never bypass denial."""
import hashlib
import fcntl
import json
import os
import re
from pathlib import Path
import shutil
import subprocess
import time

BASE = Path(__file__).resolve().parent
CACHE = BASE / 'llvm20-download-cache'
PARTIAL = CACHE / 'normal-resume.tar.gz'
URL = 'https://ftp.loongnix.cn/toolchain/llvm/llvm20/llvm-toolchain_20.1.8-1_amd64-linux-gnu_debian-10.tar.gz'
SIZE = 706463440
STARTED = time.monotonic()
MAX_SECONDS = int(os.environ.get('LLVM_DOWNLOAD_MAX_SECONDS', '10800'))
DEADLINE = STARTED + MAX_SECONDS
expected = (BASE / 'tools/llvm20.sha256').read_text().split()[0]
lock_file = (BASE / 'logs/llvm20-download.lock').open('a+')
try:
    fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
except BlockingIOError:
    raise SystemExit('Another LLVM downloader already owns the download lock')
(BASE / 'logs/llvm20-download.pid').write_text(str(os.getpid()) + '\n')


def log(message):
    print(time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), message, flush=True)


if not PARTIAL.exists():
    with PARTIAL.open('wb') as destination:
        index = 0
        while (CACHE / f'{index:04d}.chunk').exists():
            with (CACHE / f'{index:04d}.chunk').open('rb') as source:
                shutil.copyfileobj(source, destination)
            index += 1
    log(f'Prepared normal resume from {PARTIAL.stat().st_size} bytes of contiguous cached prefix')

attempt = 0
no_progress = 0
transient_http500 = 0
while time.monotonic() < DEADLINE:
    attempt += 1
    if PARTIAL.stat().st_size == SIZE:
        break
    remaining = int(DEADLINE - time.monotonic())
    if remaining <= 0:
        break
    before = PARTIAL.stat().st_size
    headers = BASE / f'logs/llvm20-normal-attempt-{attempt}.headers'
    command = ['curl', '--resolve', 'ftp.loongnix.cn:443:114.242.206.189', '--location',
               '--fail', '--silent', '--show-error', '--continue-at', '-',
               '--connect-timeout', '20', '--max-time', str(remaining),
               '--speed-time', '60', '--speed-limit', '1024', '--dump-header', str(headers),
               '--output', str(PARTIAL), '--write-out',
               'http=%{http_code} downloaded=%{size_download} speed=%{speed_download}\n', URL]
    log(f'Ordinary resume attempt {attempt} from byte {before}; remaining budget={remaining}s')
    attempt_started = time.monotonic()
    result = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    while result.poll() is None:
        try:
            result.wait(timeout=60)
        except subprocess.TimeoutExpired:
            size = PARTIAL.stat().st_size
            rate = (size - before) / max(1, time.monotonic() - attempt_started)
            log(f'Progress {size}/{SIZE} bytes ({size / SIZE:.1%}); '
                f'attempt average={rate / 1024:.1f} KiB/s; elapsed={time.monotonic() - STARTED:.0f}s')
    stdout, stderr = result.communicate()
    log(json.dumps({'attempt': attempt, 'returncode': result.returncode,
                    'stdout': stdout, 'stderr': stderr,
                    'size': PARTIAL.stat().st_size}))
    header_text = headers.read_text(errors='replace') if headers.exists() else ''
    # Old curl with --fail may retain only the proxy CONNECT response in the
    # header file; the final HTTP code still appears in --write-out.
    denied = (re.search(r'HTTP/\S+\s+(401|403)\b', header_text) or
              re.search(r'\bhttp=(401|403)\b', stdout))
    transient = re.search(r'HTTP/\S+\s+500\b', header_text) or re.search(r'\bhttp=500\b', stdout)
    if denied:
        raise SystemExit(f'Normal resume denied HTTP{denied.group(1)}; no alternate range encoding attempted')
    if transient:
        transient_http500 += 1
        log(f'Transient HTTP500 at byte {before}; ordinary resume retry {transient_http500}/12')
        if transient_http500 >= 12:
            raise SystemExit('Ordinary resume remained HTTP500 after bounded retries; partial cache preserved')
        time.sleep(min(120, max(5, int(DEADLINE - time.monotonic()))))
        continue
    transient_http500 = 0
    if result.returncode == 0 and PARTIAL.stat().st_size == SIZE:
        break
    if PARTIAL.stat().st_size <= before:
        no_progress += 1
        if no_progress >= 4:
            raise SystemExit('Normal resume made no progress after repeated attempts; partial cache preserved')
        time.sleep(min(10, max(0, DEADLINE - time.monotonic())))
    else:
        no_progress = 0

if PARTIAL.stat().st_size != SIZE:
    raise SystemExit(f'Bounded normal resume incomplete: {PARTIAL.stat().st_size}/{SIZE} bytes; no extraction or execution')
digest = hashlib.file_digest(PARTIAL.open('rb'), 'sha256').hexdigest() if hasattr(hashlib, 'file_digest') else None
if digest is None:
    sha = hashlib.sha256()
    with PARTIAL.open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            sha.update(block)
    digest = sha.hexdigest()
if digest != expected:
    raise SystemExit(f'CHECKSUM FAILED expected={expected} actual={digest}; no extraction or execution')
archive = BASE / 'tools/llvm20.tar.gz'
PARTIAL.replace(archive)
log(f'SHA256 VERIFIED {digest}')
destination = BASE / 'tools/llvm20'
destination.mkdir(exist_ok=True)
if any(destination.iterdir()):
    raise SystemExit('Destination nonempty; verified archive retained')
subprocess.run(['tar', '-xzf', str(archive), '-C', str(destination), '--strip-components=1', '--no-same-owner'], check=True)
log(f'COMPLETE: extracted verified archive to {destination}')
subprocess.run([str(BASE / 'host-runtime/bin/python3'), str(BASE / 'validate-llvm20.py')], check=True)
