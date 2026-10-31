#!/bin/bash
set -u
cd /work/electron37-attempt/rust-probe
for spec in pic-large pic-large-norelax static-large static-large-norelax pic-small pic-small-norelax static-small static-small-norelax; do
  base=${spec%-norelax}
  model=${base#*-}
  reloc=${base%-*}
  args="-C code-model=$model -C relocation-model=$reloc"
  case "$spec" in
    *norelax) args="$args -C link-arg=-Wl,--no-relax" ;;
  esac
  echo "== $spec =="
  /work/electron37-attempt/src/third_party/rust-toolchain/bin/rustc \
    --target loongarch64-unknown-linux-gnu \
    --sysroot=/work/electron37-attempt/src/out/UOS37/local_rustc_sysroot \
    -C linker=/usr/local/bin/uos-cc -C panic=abort $args \
    -C link-arg=-Wl,--no-eh-frame-hdr hello.rs \
    -o builds/hello-$spec > builds/$spec.log 2>&1
  rc=$?
  echo "compile_rc=$rc"
  if [ "$rc" = 0 ]; then
    /work/electron37-attempt/tools/llvm20/bin/llvm-objdump -d \
      builds/hello-$spec \
      --disassemble-symbols=_ZN3std3sys4args4unix3imp15ARGV_INIT_ARRAY12init_wrapper17h8930db4211f5897dE \
      | sed -n '5,22p'
    /work/electron37-attempt/host-runtime/bin/ssh -S /work/.ssh-control \
      -o BatchMode=yes -p "${UOS_SSH_PORT:-22}" "${UOS_SSH_USER:-UOS}@${UOS_SSH_HOST:-127.0.0.1}" \
      "cat > /tmp/hello-$spec" < builds/hello-$spec
    /work/electron37-attempt/host-runtime/bin/ssh -S /work/.ssh-control \
      -o BatchMode=yes -p "${UOS_SSH_PORT:-22}" "${UOS_SSH_USER:-UOS}@${UOS_SSH_HOST:-127.0.0.1}" \
      "chmod 700 /tmp/hello-$spec; set +e; /tmp/hello-$spec; echo remote_rc=\$?; exit 0"
  fi
done
