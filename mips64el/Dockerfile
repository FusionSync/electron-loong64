ARG BASE_IMAGE=electron37-mips64el-host-tools:node22
FROM ${BASE_IMAGE} AS native-tools

FROM ubuntu:22.04
ARG DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      ca-certificates curl git file g++ gcc make ninja-build pkg-config gperf bison \
      libcups2-dev libglib2.0-dev libgtk-3-dev libnss3-dev libatk1.0-dev \
      libatk-bridge2.0-dev libdrm-dev libx11-dev libx11-xcb-dev \
      libxcb1-dev libxcomposite-dev libxcursor-dev libxdamage-dev \
      libxext-dev libxfixes-dev libxi-dev libxrandr-dev libxrender-dev \
      libxshmfence-dev libxkbcommon-dev libxkbcommon-x11-dev libgbm-dev \
      libpango1.0-dev libasound2-dev libdbus-1-dev libpulse-dev \
      libwayland-dev libfontconfig1-dev libfreetype6-dev libjpeg-dev \
      libpng-dev libwebp-dev libedit2 libxml2 libtinfo6 zlib1g \
      libudev-dev libnotify-dev libcap-dev libxtst-dev libxss-dev libxt-dev \
      libkrb5-dev libpam0g-dev libpci-dev uuid-dev libatspi2.0-dev \
      libbrlapi-dev libevdev-dev libnspr4-dev libsctp-dev libspeechd-dev \
      libsqlite3-dev libssl-dev libsystemd-dev libelf-dev libcurl4-gnutls-dev \
      libbz2-dev libva-dev libglu1-mesa-dev mesa-common-dev flex patch perl \
      python3 python3-distutils xz-utils zstd unzip zip rsync clang lld \
 && rm -rf /var/lib/apt/lists/*

COPY --from=native-tools /opt/node /opt/node
COPY --from=native-tools /opt/cmake /opt/cmake
COPY --from=native-tools /opt/zig /opt/zig

# Keep target ABI inputs separate from the x86_64 LLVM runtime dependency.
COPY inputs/toolchain-debs/ /tmp/mips-inputs/toolchain-debs/
COPY inputs/debian_bullseye_mips64el_sysroot.tar.xz /tmp/mips-inputs/
COPY inputs/llvm-toolchain_20.1.8-1_amd64-linux-gnu_debian-10.tar.gz /tmp/mips-inputs/
COPY inputs/llvm-host-deps/libffi6_3.2.1-8_amd64.deb /tmp/mips-inputs/llvm-host-deps/
COPY inputs/SHA256SUMS /tmp/mips-inputs/SHA256SUMS

RUN cd /tmp/mips-inputs \
 && sha256sum -c SHA256SUMS \
 && mkdir -p /opt/mips-toolchain /opt/mips-sysroot /opt/llvm20 /opt/llvm-deps \
 && for f in toolchain-debs/*.deb; do dpkg-deb -x "$f" /opt/mips-toolchain; done \
 && ln -sf mips64el-linux-gnuabi64-g++-10 /opt/mips-toolchain/usr/bin/mips64el-linux-gnuabi64-g++ \
 && tar -xJf debian_bullseye_mips64el_sysroot.tar.xz -C /opt/mips-sysroot \
 && tar -xzf llvm-toolchain_20.1.8-1_amd64-linux-gnu_debian-10.tar.gz --strip-components=1 -C /opt/llvm20 \
 && dpkg-deb -x llvm-host-deps/libffi6_3.2.1-8_amd64.deb /tmp/llvm-deps-package \
 && cp -a /tmp/llvm-deps-package/usr/lib/x86_64-linux-gnu/libffi.so.6* /opt/llvm-deps/ \
 && mkdir -p /opt/llvm-deps/share/doc \
 && cp -a /tmp/llvm-deps-package/usr/share/doc/libffi6 /opt/llvm-deps/share/doc/ \
 && rm -rf /tmp/mips-inputs /tmp/llvm-deps-package

COPY scripts/mips64el-pkg-config /usr/local/bin/mips64el-pkg-config
COPY scripts/mips64el-env /usr/local/bin/mips64el-env
RUN chmod +x /usr/local/bin/mips64el-pkg-config /usr/local/bin/mips64el-env

ENV PATH=/opt/llvm20/bin:/opt/node/bin:/opt/mips-toolchain/usr/bin:/opt/cmake/bin:/opt/zig:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
    LD_LIBRARY_PATH=/opt/llvm-deps:/opt/llvm20/lib:/opt/mips-toolchain/usr/lib/x86_64-linux-gnu:/opt/mips-toolchain/usr/lib:/opt/mips-toolchain/lib \
    MIPS64EL_SYSROOT=/opt/mips-sysroot \
    MIPS64EL_TRIPLE=mips64el-linux-gnuabi64 \
    MIPS64EL_MARCH=mips64r2 \
    MIPS64EL_MABI=64 \
    MIPS64EL_CLANG=/opt/llvm20/bin/clang \
    MIPS64EL_CLANGXX=/opt/llvm20/bin/clang++ \
    PKG_CONFIG=mips64el-pkg-config \
    PKG_CONFIG_SYSROOT_DIR=/opt/mips-sysroot \
    PKG_CONFIG_LIBDIR=/opt/mips-sysroot/usr/lib/mips64el-linux-gnuabi64/pkgconfig:/opt/mips-sysroot/usr/share/pkgconfig

RUN /opt/node/bin/node --version \
 && /opt/llvm20/bin/clang --version \
 && /opt/mips-toolchain/usr/bin/mips64el-linux-gnuabi64-gcc --version

LABEL org.opencontainers.image.title="Electron MIPS64EL N64 cross compiler" \
      org.opencontainers.image.description="LLVM 20 compiler and Node 22 host tools with MIPS64R2 N64 target sysroot, GCC runtime, and GNU binutils"

WORKDIR /work
CMD ["bash"]
