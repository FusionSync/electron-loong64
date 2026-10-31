#!/usr/bin/env python3
"""Restore the matched UOS libnotify development files without replacing runtimes."""
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ATTEMPT = HERE.parent.parent
PACKAGE = HERE / 'libnotify-dev_0.7.7-4+sign_loongarch64.deb'
SHA256 = '3827f8e146fbb3e0a0bd3ebe57481a711ac0a0766a6f86c0b6ef49dceacee055'

if sys.argv[1:] not in ([], ['--check']):
    raise SystemExit('Usage: install-dev-files.py [--check]')
check_only = sys.argv[1:] == ['--check']
if hashlib.sha256(PACKAGE.read_bytes()).hexdigest() != SHA256:
    raise SystemExit('UOS libnotify development package checksum mismatch')
for field, expected in (('Package', 'libnotify-dev'), ('Version', '0.7.7-4+sign'),
                        ('Architecture', 'loongarch64')):
    actual = subprocess.check_output(['dpkg-deb', '--field', str(PACKAGE), field],
                                     universal_newlines=True).strip()
    if actual != expected:
        raise SystemExit('Unexpected package ' + field + ': ' + actual)

with tempfile.TemporaryDirectory(prefix='uos-libnotify-dev-') as temporary:
    extracted = Path(temporary)
    subprocess.check_call(['dpkg-deb', '-x', str(PACKAGE), str(extracted)])
    selected = [entry for entry in (extracted / 'usr/include/libnotify').iterdir()
                if entry.is_file() and entry.suffix == '.h']
    selected.extend(extracted / name for name in (
        'usr/lib/loongarch64-linux-gnu/libnotify.a',
        'usr/lib/loongarch64-linux-gnu/libnotify.so',
        'usr/lib/loongarch64-linux-gnu/pkgconfig/libnotify.pc'))
    if len(selected) != 7:
        raise SystemExit('Unexpected libnotify development payload')
    missing = []
    for root in (ATTEMPT / 'sysroot-overlay', ATTEMPT / 'sysroot-complete'):
        for source in selected:
            destination = root / source.relative_to(extracted)
            parent = destination.parent
            while parent != root.parent:
                if parent.is_symlink():
                    raise SystemExit('Refusing symlink parent: ' + str(parent))
                parent = parent.parent
            if os.path.lexists(str(destination)):
                same = (source.is_symlink() and destination.is_symlink()
                        and os.readlink(source) == os.readlink(destination))
                if not source.is_symlink() and not destination.is_symlink():
                    same = destination.is_file() and source.read_bytes() == destination.read_bytes()
                if not same:
                    raise SystemExit('Conflicting existing file: ' + str(destination))
            else:
                missing.append((source, destination))
    if check_only and missing:
        raise SystemExit('Missing libnotify development files: ' + str(len(missing)))
    if not check_only:
        for source, destination in missing:
            destination.parent.mkdir(parents=True, exist_ok=True)
            if source.is_symlink():
                destination.symlink_to(os.readlink(source))
            else:
                with source.open('rb') as incoming, destination.open('xb') as outgoing:
                    shutil.copyfileobj(incoming, outgoing)
                destination.chmod(0o644)
print('Verified UOS libnotify 0.7.7-4+sign development files; {} added.'.format(
    0 if check_only else len(missing)))
