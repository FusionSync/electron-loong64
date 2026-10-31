#!/usr/bin/env python3
import json
from pathlib import Path
import struct
import sys

BASE = Path(__file__).resolve().parent
LLVM = BASE / 'tools/llvm20'
required = LLVM / 'lib/clang/20/lib/linux/libclang_rt.builtins-loongarch64.a'
reports = []
paths = set(LLVM.rglob('*.a'))
if required.exists():
    paths.add(required)
for path in sorted(paths):
    relative = str(path.relative_to(LLVM))
    if 'loongarch' not in relative or not ('builtins' in path.name or 'profile' in path.name):
        continue
    data = path.read_bytes()
    if not data.startswith(b'!<arch>\n'):
        reports.append({'archive': str(path), 'error': 'Not a conventional ar archive'})
        continue
    offset = 8
    machines, flags = set(), set()
    members = 0
    other_members = []
    while offset + 60 <= len(data):
        header = data[offset:offset + 60]
        size = int(header[48:58].strip())
        content = data[offset + 60:offset + 60 + size]
        if content.startswith(b'\x7fELF\x02\x01'):
            members += 1
            machines.add(struct.unpack_from('<H', content, 18)[0])
            flags.add(hex(struct.unpack_from('<I', content, 48)[0]))
        elif header[:16].strip() not in (b'/', b'//', b'/SYM64/'):
            other_members.append(header[:16].decode('ascii', errors='replace').strip())
        offset += 60 + size + (size % 2)
    reports.append({'archive': str(path), 'elf_members': members,
                    'machines': sorted(machines), 'flags': sorted(flags),
                    'non_elf_members': other_members,
                    'bytes': len(data)})
print(json.dumps(reports, indent=2))
(BASE / 'logs/llvm20-compiler-rt-inventory.json').write_text(json.dumps(reports, indent=2) + '\n')
active = next((report for report in reports if report['archive'] == str(required)), None)
errors = []
if active is None:
    errors.append(f'Missing active target builtins archive: {required}')
elif ('error' in active or not active.get('elf_members') or
      active.get('machines') != [258] or active.get('non_elf_members') or
      not set(active.get('flags', [])).issubset({'0x0', '0x3'})):
    errors.append('Active builtins must contain LoongArch ELF members using old-ABI or neutral flags')
if errors:
    print('\n'.join(errors), file=sys.stderr)
    raise SystemExit(1)
