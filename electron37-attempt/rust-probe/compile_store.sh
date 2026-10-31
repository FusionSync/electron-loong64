#!/bin/bash
set -u
cd /work/electron37-attempt/rust-probe
for spec in pic-large pic-small static-large static-small; do
  reloc=${spec%-*}
  model=${spec#*-}
  /work/electron37-attempt/src/third_party/rust-toolchain/bin/rustc \
    --target loongarch64-unknown-linux-gnu --sysroot=/work/electron37-attempt/src/out/UOS37/local_rustc_sysroot --crate-type=lib --emit=obj \
    -C code-model=$model -C relocation-model=$reloc -C opt-level=2 \
    store.rs -o builds/store-$spec.o
  echo "== $spec =="
  /work/electron37-attempt/tools/llvm20/bin/llvm-objdump -dr \
    builds/store-$spec.o | head -50
done
