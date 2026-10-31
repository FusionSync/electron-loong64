import json
from pathlib import Path
import re

root = Path(__file__).resolve().parent
audit = json.loads((root / 'target-audit.json').read_text())
installed = {}
sources = {}
for line in audit['installed']['stdout'].splitlines():
    name, version, arch, status, source, source_version = line.split('\t')
    if status == 'installed':
        installed[name] = {'version': version, 'arch': arch,
                           'source': source, 'source_version': source_version}
        sources.setdefault(source, set()).add(source_version)

def parse_records(text):
    records = []
    for block in text.split('\n\n'):
        record = {}
        key = None
        for line in block.splitlines():
            if line.startswith(' ') and key:
                record[key] += '\n' + line
            elif ': ' in line:
                key, value = line.split(': ', 1)
                record[key] = value
        if 'Package' in record:
            records.append(record)
    return records

records = parse_records(audit['records']['stdout'])
by_name = {}
for record in records:
    by_name.setdefault(record['Package'], []).append(record)

selected, blocked = [], []
for name in audit['roots']:
    choices = by_name.get(name, [])
    match = None
    for record in choices:
        m = re.match(r'([^ ]+)(?: \(([^)]+)\))?', record.get('Source', name))
        source, source_version = m.group(1), m.group(2) or record['Version']
        if source_version in sources.get(source, set()):
            match = record
            break
    if match:
        selected.append(match)
    else:
        blocked.append({'name': name, 'available': [x['Version'] for x in choices],
                        'installed_source_versions': sorted(sources.get(
                            choices[0].get('Source', name).split(' ')[0], set())) if choices else []})

(root / 'initial-selection.json').write_text(json.dumps(
    {'selected': selected, 'blocked': blocked}, ensure_ascii=False, indent=2) + '\n')
for record in selected:
    print('MATCH', record['Package'], record['Version'])
for record in blocked:
    print('NO_MATCH', record['name'], ','.join(record['installed_source_versions']),
          'available=' + ','.join(record['available']))
