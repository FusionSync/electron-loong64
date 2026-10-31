# Native builder base image

The cross image in `Dockerfile` is a target sysroot layer. It expects an x86_64
native builder base selected with `BASE_IMAGE`; the local validation build used
the tag `electron37-native-builder:glibc2.27`. That tag is a local name and is
not a public registry reference.

The matching base must provide:

- Ubuntu 18.04 / glibc 2.27 x86_64 user space
- build-essential, Python 3, pkg-config, file, binutils, Git, curl, and xz-utils
- Node.js 16.20.2 with npm 8.19.4
- CMake 3.22.6 and Zig 0.13.0
- a non-root `builder` user with UID/GID 1000 and `/work` as its work directory

The base image contains host tools only. LoongArch64 target headers, libraries,
GCC 8.3, and the target old-ABI sysroot are added by this repository's Dockerfile.
Do not substitute an ARM64 native image: the intended build host is x86_64 and
the target is LoongArch64.

The validated base is available as numbered `electron-loong64-native-glibc227.tar.*`
parts in the public `toolchain-v1` Release. Download and load them with
`./scripts/fetch-native-base.sh`; the script checks every part and the
reconstructed archive against the recorded SHA256 before running `docker load`.
The same image is also published at
`ghcr.io/fusionsync/electron-loong64-native:glibc227` for registries where that
package is accessible. The target sysroot and Debian packages are deliberately
kept out of Git and are downloaded separately.
