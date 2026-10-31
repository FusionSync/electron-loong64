ARG BASE_IMAGE=electron37-native-builder:glibc2.27
FROM ${BASE_IMAGE}
USER root
COPY inputs/ /tmp/uos-inputs/
COPY metadata/SHA256SUMS /tmp/uos-inputs/SHA256SUMS
RUN cd /tmp/uos-inputs && sha256sum -c SHA256SUMS \
 && mkdir -p /opt/uos-sysroot /opt/loongson /opt/uos-target-runtime \
 && tar -xzf uos20-sysroot-20261027.tar.gz -C /opt/uos-sysroot \
 && tar -xJf loongson-gcc8.3-rc1.6.tar.xz -C /opt/loongson --strip-components=1 \
 && dpkg-deb -x libstdc++-8-dev_8.3.0.13-deepin1_loongarch64.deb /opt/uos-sysroot \
 && rm -rf /tmp/uos-inputs
COPY scripts/relativize-sysroot.py /opt/uos-cross/relativize-sysroot.py
RUN python3 /opt/uos-cross/relativize-sysroot.py /opt/uos-sysroot \
 && for f in /opt/uos-sysroot/usr/lib/gcc/loongarch64-linux-gnu/8/*.o \
             /opt/uos-sysroot/usr/lib/gcc/loongarch64-linux-gnu/8/*.a \
             /opt/uos-sysroot/usr/lib/gcc/loongarch64-linux-gnu/8/libgcc_s.so \
             /opt/uos-sysroot/usr/lib/gcc/loongarch64-linux-gnu/8/libstdc++.so \
             /opt/uos-sysroot/usr/lib/gcc/loongarch64-linux-gnu/8/libatomic.so \
             /opt/uos-sysroot/usr/lib/gcc/loongarch64-linux-gnu/8/libgomp.so; do \
      if test -e "$f"; then cp -L "$f" /opt/uos-target-runtime/; fi; \
    done
COPY scripts/uos-cc /usr/local/bin/uos-cc
COPY scripts/uos-pkg-config /usr/local/bin/uos-pkg-config
COPY toolchains/uos20-loongarch64.cmake /opt/uos-cross/uos20-loongarch64.cmake
COPY metadata/target-system.txt metadata/target-packages.tsv /opt/uos-cross/metadata/
RUN chmod +x /usr/local/bin/uos-cc /usr/local/bin/uos-pkg-config \
 && ln -s uos-cc /usr/local/bin/uos-c++ \
 && ln -s uos-cc /usr/local/bin/uos-gcc \
 && ln -s uos-cc /usr/local/bin/uos-g++ \
 && /opt/loongson/bin/loongarch64-linux-gnu-gcc --version
ENV PATH=/usr/local/bin:/opt/loongson/bin:/opt/node/bin:/opt/cmake/bin:/usr/local/sbin:/usr/sbin:/usr/bin:/sbin:/bin \
    UOS_SYSROOT=/opt/uos-sysroot \
    CC=uos-cc CXX=uos-c++ \
    AR=loongarch64-linux-gnu-ar RANLIB=loongarch64-linux-gnu-ranlib \
    STRIP=loongarch64-linux-gnu-strip \
    PKG_CONFIG=uos-pkg-config
LABEL org.opencontainers.image.title="UOS 20 LoongArch old-ABI cross compiler" \
      org.opencontainers.image.description="x86_64 GCC 8.3 cross compiler with a UOS 20 glibc 2.28 sysroot; Electron itself is not built or validated"
USER builder
WORKDIR /work
CMD ["bash"]
