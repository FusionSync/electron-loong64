import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

root = Path('/work/electron37-attempt') if Path('/work/electron37-attempt').exists() else Path.cwd() / 'electron37-attempt'
out = root / 'src/out/UOS37'
only = sys.argv[1:]

def value(text, name):
    m = re.search(r'^\s*' + re.escape(name) + r' = (.*)$', text, re.M)
    return m.group(1) if m else ''

def unescape(v):
    # GN/Ninja emits backslash-escaped dollars/spaces in environment values.
    return v.replace(r'\$', '$').replace(r'\ ', ' ')

def env_items(raw):
    matches = list(re.finditer(r'(?:^| )([A-Za-z_][A-Za-z0-9_]*)=', raw))
    result = []
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(raw)
        key = m.group(1)
        val = raw[m.end():end].strip()
        val = val.replace(r'\$', '$').replace(r'\ ', ' ').replace(r'\<', '<').replace(r'\>', '>')
        result.append(key + '=' + val)
    return result

jobs = []
for f in out.joinpath('obj').rglob('*.ninja'):
    text = f.read_text(errors='ignore')
    if ': rust_rlib ' not in text or '--target=loongarch64-unknown-linux-gnu' not in text:
        continue
    m = re.search(r'^build ([^:\n]+): rust_rlib ([^\n]+)', text, re.M)
    if not m:
        continue
    output = m.group(1).strip()
    if 'testing/rust_gtest_interop' in output or '/tests/' in output or 'third_party/boringssl' in output:
        continue
    if only and not any(x in output or x in str(f) for x in only):
        continue
    all_inputs = m.group(2)
    inp = all_inputs.split('|', 1)[0].strip().split()[0]
    dep_paths = set()
    if '|' in all_inputs:
        dep_paths = {x for x in all_inputs.split('|', 1)[1].split() if x.endswith('.rlib')}
    crate_name = value(text, 'crate_name')
    crate_type = value(text, 'crate_type')
    output_dir = value(text, 'output_dir')
    output_ext = value(text, 'output_extension')
    output_name = value(text, 'target_output_name')
    rustflags = unescape(value(text, 'rustflags'))
    rustenv_raw = value(text, 'rustenv')
    externs = unescape(value(text, 'externs'))
    rustdeps = unescape(value(text, 'rustdeps'))
    ldflags = unescape(value(text, 'ldflags'))
    sources = unescape(value(text, 'sources'))
    if not output_name:
        continue
    output_path = out / output
    depfile = out / output_dir / ('lib' + output_name + output_ext + '.d')
    rsp = out / output_dir / ('lib' + output_name + output_ext + '.rsp')
    args = [
        sys.executable, str(root / 'src/build/rust/rustc_wrapper.py'),
        '--rustc=' + str(root / 'src/third_party/rust-toolchain/bin/rustc'),
        '--depfile=' + str(depfile), '--rsp=' + str(rsp), '--',
        '-Clinker=' + str(root / 'gn/clang-facade/bin/clang++'),
        '--crate-name', crate_name, inp, '--crate-type', crate_type,
    ]
    args += shlex.split(rustflags)
    args += ['--emit=dep-info=' + str(depfile) + ',link', '-o', str(output_path), 'LDFLAGS']
    args += shlex.split(ldflags)
    args += ['RUSTENV']
    args += env_items(rustenv_raw)
    args += ['SOURCES']
    rsp.parent.mkdir(parents=True, exist_ok=True)
    rsp.write_text(rustdeps + ' ' + externs + ' SOURCES ' + sources)
    jobs.append((str(f.relative_to(out)), output, args, rsp, dep_paths))

# Rebuild prerequisites first. Rust embeds dependency metadata, so rebuilding
# std/core/alloc in arbitrary order produces E0460 version mismatches.
by_output = {j[1]: j for j in jobs}
ordered = []
seen = set()
def visit(j):
    if j[1] in seen:
        return
    seen.add(j[1])
    for dep in j[4]:
        if dep in by_output:
            visit(by_output[dep])
    ordered.append(j)
for j in jobs:
    visit(j)
jobs = ordered

print('jobs', len(jobs), flush=True)
for label, output, args, rsp, _ in jobs:
    print('RUN', output, flush=True)
    p = subprocess.run(args, cwd=out, env=os.environ.copy())
    if p.returncode:
        print('FAILED', output, p.returncode, file=sys.stderr, flush=True)
        sys.exit(p.returncode)
    try:
        rsp.unlink()
    except FileNotFoundError:
        pass
