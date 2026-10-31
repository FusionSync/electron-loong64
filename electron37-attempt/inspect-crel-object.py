#!/usr/bin/env python3
"""Confirm the -Wa,--crel probe actually contains CREL relocation sections."""
import json
from pathlib import Path
import struct
import sys

reports = []
for argument in sys.argv[1:]:
    path = Path(argument)
    data = path.read_bytes()
    assert data[:6] == b'\x7fELF\x02\x01', 'Expected ELF64 little endian'
    offset = struct.unpack_from('<Q', data, 40)[0]
    entry_size, count, names_index = struct.unpack_from('<HHH', data, 58)
    names_header = offset + names_index * entry_size
    names_offset, names_size = struct.unpack_from('<QQ', data, names_header + 24)
    names = data[names_offset:names_offset + names_size]
    sections = []
    for index in range(count):
        name_offset, section_type = struct.unpack_from('<II', data, offset + index * entry_size)
        name = names[name_offset:].split(b'\0', 1)[0].decode()
        if name.startswith(('.crel', '.rel', '.rela')):
            sections.append({'name': name, 'type': hex(section_type)})
    assert any(section['name'].startswith('.crel') for section in sections), f'No CREL sections in {path}'
    reports.append({'object': str(path), 'relocation_sections': sections})
print(json.dumps(reports, indent=2))
