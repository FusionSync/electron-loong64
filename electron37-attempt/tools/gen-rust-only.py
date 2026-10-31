from pathlib import Path
import re

root = Path('/work/electron37-attempt') if Path('/work/electron37-attempt').exists() else Path.cwd() / 'electron37-attempt'
out = root / 'src/out/UOS37'
files = []
for f in out.joinpath('obj').rglob('*.ninja'):
    t = f.read_text(errors='ignore')
    if ': rust_rlib ' in t and '--target=loongarch64-unknown-linux-gnu' in t:
        files.append((f, t))

lines = [
    'pool rust_pool',
    '  depth = 12',
    'rule rust_rlib',
    '  command = "python3" "../../build/rust/rustc_wrapper.py" --rustc=../../third_party/rust-toolchain/bin/rustc --depfile=${output_dir}/lib${target_output_name}${output_extension}.d --rsp=${output_dir}/lib${target_output_name}${output_extension}.rsp -- -Clinker="/work/electron37-attempt/gn/clang-facade/bin/clang++" --crate-name ${crate_name} ${in} --crate-type ${crate_type} ${rustflags} --emit=dep-info=${output_dir}/lib${target_output_name}${output_extension}.d,link -o ${output_dir}/lib${target_output_name}${output_extension} LDFLAGS RUSTENV ${rustenv}',
    '  description = RUST ${out}',
    '  rspfile = ${output_dir}/lib${target_output_name}${output_extension}.rsp',
    '  rspfile_content = ${rustdeps} ${externs} SOURCES ${sources}',
    '  depfile = ${output_dir}/lib${target_output_name}${output_extension}.d',
    '  deps = gcc',
    'build force: phony',
]
wanted = {
    'crate_name', 'crate_type', 'output_extension', 'output_dir', 'rustflags',
    'rustenv', 'target_output_name', 'source_file_part', 'source_name_part',
    'externs', 'rustdeps', 'ldflags', 'sources',
}
for f, t in files:
    m = re.search(r'^build ([^:\n]+): rust_rlib ([^\n]+)', t, re.M)
    if not m:
        continue
    outp = m.group(1).strip()
    inp = m.group(2).split('|', 1)[0].strip().split()[0]
    lines.append('# ' + str(f.relative_to(out)))
    for line in t.splitlines():
        mm = re.match(r'^(\w+) = (.*)$', line)
        if mm and mm.group(1) in wanted:
            lines.append(line)
    lines.append(f'build {outp}: rust_rlib {inp} | force')

path = out / 'rust-only.ninja'
path.write_text('\n'.join(lines) + '\n')
print(f'files={len(files)} bytes={path.stat().st_size}')
