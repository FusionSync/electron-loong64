import json
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

def run(args):
    result = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return {'status': result.returncode, 'stdout': result.stdout.decode(errors='replace'),
            'stderr': result.stderr.decode(errors='replace')}

installed = run(['dpkg-query', '-W', '-f=${Package}\t${Version}\t${Architecture}\t${db:Status-Status}\t${source:Package}\t${source:Version}\n'])
policy = run(['apt-cache', 'policy'] + roots)
records = run(['apt-cache', 'show'] + roots)
print(json.dumps({'roots': roots, 'installed': installed, 'policy': policy,
                  'records': records}, ensure_ascii=False))
