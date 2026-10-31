#!/usr/bin/env python3
"""Restore public curl headers from the verified upstream 7.64.1 archive."""
import hashlib
from pathlib import Path
import sys
import tarfile

HERE = Path(__file__).resolve().parent
ATTEMPT = HERE.parent.parent
ARCHIVE = HERE / 'curl-7.64.1.tar.xz'
SHA256 = '9252332a7f871ce37bfa7f78bdd0a0e3924d8187cc27cb57c76c9474a7168fb3'

if sys.argv[1:] not in ([], ['--check']):
    raise SystemExit('Usage: install-headers.py [--check]')
check_only = sys.argv[1:] == ['--check']
if hashlib.sha256(ARCHIVE.read_bytes()).hexdigest() != SHA256:
    raise SystemExit('curl archive checksum mismatch')

headers = {}
with tarfile.open(ARCHIVE) as archive:
    for member in archive.getmembers():
        path = Path(member.name)
        if (path.parent.as_posix() == 'curl-7.64.1/include/curl'
                and path.suffix == '.h' and member.isfile()):
            headers[path.name] = archive.extractfile(member).read()
if 'curl.h' not in headers or b'#define LIBCURL_VERSION "7.64.1"' not in headers.get('curlver.h', b''):
    raise SystemExit('Unexpected curl public headers')

# Validate all destinations before writing. Never overwrite existing headers
# from an unrelated package, and never install or replace any runtime library.
missing = []
for root in (ATTEMPT / 'sysroot-overlay', ATTEMPT / 'sysroot-complete'):
    directory = root / 'usr/include/curl'
    if directory.is_symlink():
        raise SystemExit('Refusing symlink destination: ' + str(directory))
    for name, data in headers.items():
        target = directory / name
        if target.is_symlink():
            raise SystemExit('Refusing symlink header: ' + str(target))
        if target.exists():
            if target.read_bytes() != data:
                raise SystemExit('Different existing curl header: ' + str(target))
        else:
            missing.append((target, data))
if check_only:
    if missing:
        raise SystemExit('Missing curl headers: ' + str(len(missing)))
else:
    for target, data in missing:
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('xb') as output:
            output.write(data)
        target.chmod(0o644)
print('Verified curl 7.64.1 public headers; {} files added.'.format(
    0 if check_only else len(missing)))
