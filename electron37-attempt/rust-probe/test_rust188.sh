#!/bin/bash
set -u
cd /work/electron37-attempt/rust-probe
for spec in pic-large static-large pic-small static-small; do
  reloc=${spec%-*}
  model=${spec#*-}
  echo "== rust188-$spec =="
  /work/electron37-attempt/tools/rust188/bin/rustc \
    --target loongarch64-unknown-linux-gnu \
    --sysroot=/work/electron37-attempt/tools/rust188 \
    -C linker=/usr/local/bin/uos-cc -C panic=abort \
    -C code-model=$model -C relocation-model=$reloc \
    -C link-arg=-Wl,--no-eh-frame-hdr hello.rs \
    -o builds/hello-rust188-$spec > builds/rust188-$spec.log 2>&1
  rc=$?
  echo "compile_rc=$rc"
  if [ "$rc" = 0 ]; then
    /work/electron37-attempt/tools/llvm20/bin/llvm-objdump -d \
      builds/hello-rust188-$spec \
      --disassemble-symbols=_ZN3std3sys4args4unix3imp15ARGV_INIT_ARRAY12init_wrapper17h7fcc58397c669a9dE \
      | sed -n '5,22p'
    /work/electron37-attempt/host-runtime/bin/ssh -S /work/.ssh-control \
      -o BatchMode=yes -p "${UOS_SSH_PORT:-22}" "${UOS_SSH_USER:-UOS}@${UOS_SSH_HOST:-127.0.0.1}" \
      "cat > /tmp/hello-rust188-$spec" < builds/hello-rust188-$spec
    /work/electron37-attempt/host-runtime/bin/ssh -S /work/.ssh-control \
      -o BatchMode=yes -p "${UOS_SSH_PORT:-22}" "${UOS_SSH_USER:-UOS}@${UOS_SSH_HOST:-127.0.0.1}" \
      "chmod 700 /tmp/hello-rust188-$spec; /tmp/hello-rust188-$spec"
  fi
done
