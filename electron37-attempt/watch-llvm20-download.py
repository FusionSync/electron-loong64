#!/usr/bin/env python3
"""Observe the already-running downloader and publish durable stage/exit markers."""
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import time

BASE = Path(__file__).resolve().parent
LOGS = BASE / 'logs'
lock_file = (LOGS / 'llvm20-watch.lock').open('a+')
try:
    fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
except BlockingIOError:
    raise SystemExit('Another LLVM download watcher is already active')
OWNER = int((LOGS / 'llvm20-download.pid').read_text().strip())
PARTIAL = BASE / 'llvm20-download-cache/normal-resume.tar.gz'
ARCHIVE = BASE / 'tools/llvm20.tar.gz'
SIZE = 706463440
(LOGS / 'llvm20-watch.pid').write_text(str(os.getpid()) + '\n')


def write(path, text):
    temporary = path.with_name(path.name + '.watch.tmp')
    temporary.write_text(text)
    temporary.replace(path)


def exists_process():
    try:
        os.kill(OWNER, 0)
        return True
    except ProcessLookupError:
        return False


while True:
    active = exists_process()
    validation = LOGS / 'llvm20-validation.exit'
    try:
        archive_size = ARCHIVE.stat().st_size
    except FileNotFoundError:
        archive_size = 0
    try:
        partial_size = PARTIAL.stat().st_size
    except FileNotFoundError:
        partial_size = 0
    downloaded = archive_size == SIZE
    size = archive_size if downloaded else partial_size
    state = {'owner_pid': OWNER, 'owner_running': active, 'bytes': size, 'total_bytes': SIZE,
             'updated_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
             'status': 'running' if active else 'stopped',
             'phase': 'extract_or_validate' if downloaded else 'transfer'}
    if validation.exists():
        code = int(validation.read_text().strip())
        state.update(status='passed' if code == 0 else 'failed', phase='validation_finished', validation_exit=code)
        write(LOGS / 'llvm20-download-status.json', json.dumps(state, indent=2) + '\n')
        break
    if not active:
        archive_valid = False
        if downloaded:
            sha = hashlib.sha256()
            with ARCHIVE.open('rb') as source:
                for block in iter(lambda: source.read(1024 * 1024), b''):
                    sha.update(block)
            archive_valid = sha.hexdigest() == (BASE / 'tools/llvm20.sha256').read_text().split()[0]
        write(LOGS / 'llvm20-download.exit', '0\n' if archive_valid else '1\n')
        state.update(status='failed', phase='extract_or_validate_stopped' if archive_valid else 'download_stopped')
        write(LOGS / 'llvm20-validation-status.json', json.dumps(state, indent=2) + '\n')
        write(LOGS / 'llvm20-validation.exit', '1\n')
        write(LOGS / 'llvm20-download-status.json', json.dumps(state, indent=2) + '\n')
        break
    write(LOGS / 'llvm20-download-status.json', json.dumps(state, indent=2) + '\n')
    time.sleep(30)
