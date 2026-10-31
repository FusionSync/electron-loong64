#!/bin/bash
set -u
cd /work/electron37-attempt/rust-probe
/work/electron37-attempt/src/third_party/rust-toolchain/bin/rustc \
  --target loongarch64-unknown-linux-gnu \
  --sysroot=/work/electron37-attempt/src/out/UOS37/local_rustc_sysroot \
  -C linker=/usr/local/bin/uos-cc -C panic=abort \
  -C code-model=large -C relocation-model=pic \
  -C link-arg=-Wl,--no-eh-frame-hdr -C link-arg=-Wl,--emit-relocs \
  hello.rs -o builds/hello-pic-relocs
echo relocations-in-final
readelf -rW builds/hello-pic-relocs | grep -E 'ARGV|ARGC|R_LARCH_PCALA' | head -60
echo sections
readelf -SW builds/hello-pic-relocs | grep -E 'text|bss|init_array'
echo symbols
readelf -sW builds/hello-pic-relocs | grep -E 'ARGV|ARGC|init_wrapper' | head -30
