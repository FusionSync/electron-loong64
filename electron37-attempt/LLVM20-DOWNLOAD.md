# LLVM 20 toolchain input

The build uses the Loongson LLVM 20.1.8 x86_64 host toolchain:

```text
Source: http://ftp.loongnix.cn/toolchain/llvm/llvm20/llvm-toolchain_20.1.8-1_amd64-linux-gnu_debian-10.tar.gz
SHA256: b552f93326948c7292cceaf11db7eb442327448d9f45b4b25eafdbfa9b60c25e
Size: 706463440 bytes
```

Download the archive outside Git, verify the digest, and extract it as
`electron37-attempt/tools/llvm20`. The supplied archive is a host x86_64
toolchain; the target headers and libraries come from the UOS LoongArch64
sysroot described in `inputs/README.md`. `tools/llvm20.sha256` is the small
checksum file used by the validation scripts.

The recorded probes cover host Clang, LoongArch object generation, GNU C/C++
links, compiler-rt, the GNU medium and large code models, bindgen/Rust ABI, and
GN generation. The final Electron bundle was linked with the patched GNU ld
path because the UOS linker rejected a LoongArch type-44 relocation mask. The
exact relink command is retained in `tools/electron-link-command-gldfixed.sh`.

The complete Electron artifact has been statically audited and executed on a
real UOS Loong64 desktop. A clean third-party rebuild still requires the
matching base image, UOS sysroot inputs, and pinned dependency downloads; those
large binaries are intentionally distributed separately from Git.
