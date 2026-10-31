import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

work = Path('/work/electron37-attempt')
packages = work / 'dependency-packages'
overlay = work / 'sysroot-overlay'
merged = work / 'sysroot-complete'
base = Path('/opt/uos-sysroot')
results = json.loads((packages / 'download-results.json').read_text(encoding='utf-8'))
if any(p['status'] != 'verified' for p in results):
    raise SystemExit('Refusing to extract unverified download set')
with (packages / 'SHA256SUMS').open('w') as sums:
    for package in results:
        file = packages / package['filename']
        digest = hashlib.sha256(file.read_bytes()).hexdigest()
        if digest != package['actual_sha256']:
            raise SystemExit('Transfer hash mismatch: ' + str(file))
        sums.write(digest + '  ' + file.name + '\n')
for package in results:
    subprocess.check_call(['dpkg-deb', '-x', str(packages / package['filename']), str(overlay)])
subprocess.check_call(['python3', '/work/scripts/relativize-sysroot.py', str(overlay)])
if merged.exists():
    raise SystemExit('Refusing to replace existing merged sysroot')
shutil.copytree(str(overlay), str(merged), symlinks=True, copy_function=os.link)
links = 0

def fill(source, destination):
    global links
    for entry in source.iterdir():
        path = destination / entry.name
        if not os.path.lexists(str(path)):
            path.symlink_to(str(entry))
            links += 1
        elif path.is_dir() and not path.is_symlink() and entry.is_dir():
            fill(entry, path)

fill(base, merged)
for relative in ['usr/lib/loongarch64-linux-gnu/libc.so']:
    source, destination = base / relative, merged / relative
    if destination.is_symlink():
        destination.unlink()
        shutil.copy2(str(source), str(destination))
# GNU ld only prefixes absolute paths in scripts physically inside --sysroot.
# Preserve that behavior instead of linking libc.so back to the base snapshot.
print('Extracted {} verified development packages; added {} links to unchanged base sysroot'.format(len(results), links))
