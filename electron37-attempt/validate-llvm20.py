#!/usr/bin/env python3
"""Verify LLVM and publish an atomic exit marker after the required GNU/UOS tests."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import traceback

BASE = Path(__file__).resolve().parent
ARCHIVE = BASE / 'tools/llvm20.tar.gz'
LLVM = BASE / 'tools/llvm20'
RUNTIME = BASE / 'host-runtime'
LOGS = BASE / 'logs'
STATE = {'status': 'running', 'phase': 'checksum', 'started_utc': datetime.datetime.now(datetime.timezone.utc).isoformat()}
environment = dict(os.environ, UOS_HOST_LIBRARY_PATH=str(LLVM / 'lib'))


def atomic_write(path, value):
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(value)
    temporary.replace(path)


def phase(name):
    STATE['phase'] = name
    STATE['updated_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    atomic_write(LOGS / 'llvm20-validation-status.json', json.dumps(STATE, indent=2) + '\n')


def validate():
    (LOGS / 'llvm20-validation.exit').unlink(missing_ok=True)
    for mode in ['gnu', 'builtins', 'profile', 'compiler-rt', 'gnu-medium', 'lld', 'lld-medium', 'direct', 'crel']:
        (LOGS / f'llvm20-{mode}-validation.exit').unlink(missing_ok=True)
    phase('checksum')
    expected = (BASE / 'tools/llvm20.sha256').read_text().split()[0]
    digest = hashlib.sha256()
    with ARCHIVE.open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(block)
    assert digest.hexdigest() == expected, 'Archive checksum mismatch; refusing to execute tools'
    STATE['archive_sha256'] = expected
    atomic_write(LOGS / 'llvm20-download.exit', '0\n')

    with (LOGS / 'llvm20-validation.log').open('w') as log:
        def run(command, data=None):
            log.write('$ ' + ' '.join(map(str, command)) + '\n')
            result = subprocess.run(list(map(str, command)), input=data, capture_output=True,
                                    text=True, env=environment)
            log.write(result.stdout + result.stderr + f'\nexit={result.returncode}\n')
            log.flush()
            return result

        phase('host_loader_and_clang')
        clang = LLVM / 'bin/clang'
        run([RUNTIME / 'lib/ld-linux-x86-64.so.2', '--library-path',
             str(RUNTIME / 'lib') + ':' + str(LLVM / 'lib'), '--list', clang])
        version = run([RUNTIME / 'bin/host-run', clang, '--version'])
        if version.returncode:
            raise RuntimeError('Verified LLVM extracted but clang cannot run; see llvm20-validation.log')
        run([RUNTIME / 'bin/host-run', clang, '--print-targets'])

        phase('loongarch_object')
        output = LOGS / 'llvm20-loongarch64-smoke.o'
        compiled = run([RUNTIME / 'bin/host-run', clang, '-no-canonical-prefixes', '-fintegrated-cc1',
                        '-resource-dir', LLVM / 'lib/clang/20', '--target=loongarch64-unknown-linux-gnu',
                        '-x', 'c', '-c', '-', '-o', output], data='int answer(void) { return 42; }\n')
        if compiled.returncode:
            raise RuntimeError('Clang runs, but LoongArch object compilation failed; see validation log')
        elf = output.read_bytes()
        assert elf[:5] == b'\x7fELF\x02', 'Not an ELF64 object'
        machine = struct.unpack_from('<H', elf, 18)[0]
        flags = struct.unpack_from('<I', elf, 48)[0]
        assert machine == 258, f'Unexpected ELF machine {machine}'
        log.write(json.dumps({'machine': machine, 'e_flags': hex(flags),
                              'object': str(output), 'archive_sha256': expected}) + '\n')

    phase('cross_link_and_uos_execution')
    subprocess.run(['bash', str(BASE / 'verify-llvm20-cross.sh')], check=True)
    STATE['optional_results'] = {}
    STATE['builtins_validation'] = 'passed'
    for mode in ['profile', 'gnu-medium', 'lld', 'lld-medium', 'direct', 'crel']:
        marker = LOGS / f'llvm20-{mode}-validation.exit'
        STATE['optional_results'][mode] = marker.read_text().strip() if marker.exists() else 'not_run'
    STATE['status'] = 'passed'
    phase('complete')
    atomic_write(LOGS / 'llvm20-validation.exit', '0\n')
    print('LLVM20 required GNU/UOS validation passed; independent LLD/CREL results recorded.')


try:
    validate()
except BaseException as error:
    STATE['status'] = 'failed'
    STATE['error'] = repr(error)
    phase(STATE['phase'])
    atomic_write(LOGS / 'llvm20-validation.exit', '1\n')
    if STATE['phase'] == 'checksum':
        atomic_write(LOGS / 'llvm20-download.exit', '1\n')
    traceback.print_exc()
    raise SystemExit(1)
