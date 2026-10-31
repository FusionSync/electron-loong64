import json
import re
import subprocess

roots = ['libgtk-3-dev', 'libnss3-dev', 'libnspr4-dev', 'libgbm-dev',
         'libdrm-dev', 'libasound2-dev', 'libcups2-dev', 'libx11-dev',
         'libxcomposite-dev', 'libxdamage-dev', 'libxext-dev', 'libxfixes-dev',
         'libxrandr-dev', 'libxi-dev', 'libxrender-dev', 'libxkbcommon-dev',
         'libxkbcommon-x11-dev', 'libatk1.0-dev', 'libatk-bridge2.0-dev',
         'libatspi2.0-dev', 'libfontconfig1-dev', 'libfreetype6-dev',
         'libdbus-1-dev', 'libglib2.0-dev', 'libpango1.0-dev', 'libcairo2-dev',
         'libx11-xcb-dev', 'libxshmfence-dev', 'libxcursor-dev', 'libxss-dev',
         'libxtst-dev', 'libudev-dev', 'libpulse-dev', 'libpci-dev',
         'libexpat1-dev', 'libffi-dev', 'zlib1g-dev']
seen, queue, records, errors = set(), set(roots), [], []
while queue:
    batch = sorted(queue - seen)
    queue = set()
    if not batch:
        break
    seen.update(batch)
    result = subprocess.run(['apt-cache', 'show'] + batch,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    text = result.stdout.decode(errors='replace')
    records.append(text)
    errors.append(result.stderr.decode(errors='replace'))
    for line in text.splitlines():
        if line.startswith(('Depends:', 'Pre-Depends:')):
            for name in re.findall(r'(?:^|[,|])\s*([a-z0-9+.-]+)', line.split(':', 1)[1]):
                if name.endswith(('-dev', '-dev-bin')) or name in ['linux-libc-dev']:
                    queue.add(name)
print(json.dumps({'roots': roots, 'queried': sorted(seen),
                  'records': '\n'.join(records), 'stderr': '\n'.join(errors)}, ensure_ascii=False))
