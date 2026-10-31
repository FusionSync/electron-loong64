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

For public distribution, publish the matching base and final cross image to a
container registry such as GHCR, or build an equivalent base from independently
licensed inputs. The target sysroot and Debian packages are deliberately kept out of
Git and must be obtained from an authorized toolchain source.
