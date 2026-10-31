import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import subprocess

plan = json.loads(Path('download-plan.json').read_text())

def fetch(package):
    result = dict(package)
    file = Path(package['filename'])
    expected = '\t'.join([package['name'], package['version'], package['architecture']])
    # apt-get download may preserve the epoch in its local filename as %3a.
    if not file.exists():
        for alternate in Path('.').glob(package['name'] + '_*.deb'):
            identity = subprocess.check_output(['dpkg-deb', '--show',
                '--showformat=${Package}\t${Version}\t${Architecture}\n', str(alternate)],
                universal_newlines=True).strip()
            if identity == expected:
                alternate.rename(file)
                break
    if not file.exists():
        if package['sha256']:
            command = ['apt-get', 'download', package['name'] + '=' + package['version']]
        else:
            command = ['/usr/lib/apt/apt-helper', 'download-file', package['url'], str(file)]
        proc = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        result['download_log'] = proc.stdout.decode(errors='replace')
        if proc.returncode:
            result.update(status='download_failed', exit_code=proc.returncode)
            return result
    if not file.exists():
        result.update(status='expected_filename_missing')
        return result
    digest = hashlib.sha256(file.read_bytes()).hexdigest()
    result['actual_sha256'] = digest
    result['bytes'] = file.stat().st_size
    if package['sha256'] and digest != package['sha256']:
        result['status'] = 'sha256_mismatch'
        return result
    control = subprocess.check_output(['dpkg-deb', '--show',
        '--showformat=${Package}\t${Version}\t${Architecture}\n', str(file)], universal_newlines=True).strip()
    result['control_identity'] = control
    if control != expected:
        result['status'] = 'control_identity_mismatch'
        return result
    result['status'] = 'verified'
    return result

with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
    results = list(pool.map(fetch, plan['packages']))
Path('download-results.json').write_text(json.dumps(results, ensure_ascii=False, indent=2) + '\n')
for result in results:
    print(result['status'], result['name'], result['version'], result.get('bytes', 0))
