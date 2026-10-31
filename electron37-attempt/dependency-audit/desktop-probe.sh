#!/usr/bin/env bash
set -euxo pipefail
cd /work/electron37-attempt/dependency-audit
export UOS_SYSROOT=/work/electron37-attempt/sysroot-complete
packages=(gtk+-3.0 nss gbm libdrm alsa x11 xkbcommon dbus-1)
cflags_text=$(uos-pkg-config --cflags "${packages[@]}")
libs_text=$(uos-pkg-config --libs "${packages[@]}")
read -r -a cflags <<< "$cflags_text"
read -r -a libs <<< "$libs_text"
uos-cc -O0 "${cflags[@]}" desktop-probe.c "${libs[@]}" -lcups -o desktop-probe-loongarch64
loongarch64-linux-gnu-readelf -hW desktop-probe-loongarch64
loongarch64-linux-gnu-readelf -dW desktop-probe-loongarch64
loongarch64-linux-gnu-readelf -VW desktop-probe-loongarch64
