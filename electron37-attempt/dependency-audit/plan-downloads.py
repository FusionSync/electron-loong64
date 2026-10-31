import json
from pathlib import Path
import re
import runpy

root = Path(__file__).resolve().parent
common = runpy.run_path(str(root / 'select-packages.py'))
closure = json.loads((root / 'dev-closure.json').read_text())
by_name = {}
for record in common['parse_records'](closure['records']):
    by_name.setdefault(record['Package'], []).append(record)
installed, sources = common['installed'], common['sources']
plan, skipped, blocked = [], [], []
for name in closure['queried']:
    if name in installed or name in ['dpkg-dev', 'libc-dev', 'libz-dev']:
        skipped.append(name)
        continue
    choices = by_name.get(name, [])
    if not choices:
        blocked.append({'name': name, 'reason': 'No package records'})
        continue
    chosen, reason = None, None
    for record in choices:
        m = re.match(r'([^ ]+)(?: \(([^)]+)\))?', record.get('Source', name))
        source, source_version = m.group(1), m.group(2) or record['Version']
        if source_version in sources.get(source, set()):
            chosen, reason = record.copy(), 'APT index version matches installed source version'
            break
    if chosen is None:
        candidate = choices[0]
        source = candidate.get('Source', name).split(' ')[0]
        versions = sorted(sources.get(source, set()))
        if len(versions) == 1:
            chosen = candidate.copy()
            chosen['Version'] = versions[0]
            old_binary_version = versions[0].split(':', 1)[-1]
            filename = candidate['Filename']
            chosen['Filename'] = str(Path(filename).parent / (
                name + '_' + old_binary_version + '_' + candidate['Architecture'] + '.deb'))
            chosen.pop('SHA256', None)
            chosen.pop('Size', None)
            reason = 'Exact installed source version, retained official HTTPS pool artifact; not in current APT index'
        elif not versions and (candidate['Architecture'] == 'all' or name == 'libpthread-stubs0-dev'):
            chosen, reason = candidate.copy(), 'Header/protocol support package without a separately installed runtime source'
        else:
            blocked.append({'name': name, 'reason': 'Ambiguous or missing installed runtime source',
                            'source_versions': versions})
            continue
    plan.append({'name': name, 'version': chosen['Version'], 'architecture': chosen['Architecture'],
                 'url': 'https://professional-packages.chinauos.com/desktop-professional/' + chosen['Filename'],
                 'filename': Path(chosen['Filename']).name, 'sha256': chosen.get('SHA256'),
                 'selection_reason': reason})
(root / 'download-plan.json').write_text(json.dumps(
    {'packages': plan, 'skipped': skipped, 'blocked': blocked}, ensure_ascii=False, indent=2) + '\n')
print('DOWNLOADS', len(plan), 'SKIP', len(skipped), 'BLOCKED', blocked)
