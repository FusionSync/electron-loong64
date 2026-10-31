#!/usr/bin/env python3
"""Run the memory-bounded build and stop before exhausting the shared volume."""
import os
from pathlib import Path
import signal
import subprocess
import sys

attempt = Path(__file__).resolve().parent
source = attempt / 'src'
jobs = os.environ.get('UOS_NINJA_JOBS', '4')
if not jobs.isdigit() or int(jobs) < 1:
    raise SystemExit('UOS_NINJA_JOBS must be a positive integer')
command = [str(source / 'third_party/ninja/ninja'), '-C', 'out/UOS37', '-j' + jobs]
command.extend(sys.argv[1:] or ['electron'])
minimum_free = 2 * 1024**3
process = subprocess.Popen(command, cwd=source, start_new_session=True)
try:
    while True:
        try:
            sys.exit(process.wait(timeout=15))
        except subprocess.TimeoutExpired:
            filesystem = os.statvfs(source)
            available = filesystem.f_bavail * filesystem.f_frsize
            if available < minimum_free:
                print('Stopping Ninja: shared host volume has less than 2 GiB free; '
                      'all completed build files are retained.', flush=True)
                os.killpg(process.pid, signal.SIGINT)
                process.wait()
                sys.exit(75)
except KeyboardInterrupt:
    os.killpg(process.pid, signal.SIGINT)
    process.wait()
    sys.exit(130)
