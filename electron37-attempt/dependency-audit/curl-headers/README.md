# curl public headers for the UOS Crashpad build

Crashpad's `http_transport_libcurl.cc` needs `<curl/curl.h>`, which was absent
from the UOS development overlay. The runtime snapshot already supplies
`libcurl4` and `libcurl3-gnutls` at `7.64.1.21-deepin1` (LoongArch old ABI).
Crashpad uses dlopen/dlsym; it does not link a new curl runtime into Electron.

The UOS official development-package pool required authentication (HTTP 401),
and target SSH was refusing connections. We therefore retained the unmodified
public headers from the same upstream release, curl 7.64.1. These are upstream
headers, not a claim that the UOS vendor development package was downloaded.
All ten functions loaded by Crashpad exist in the UOS runtime, and all options
used by this source exist in the upstream headers.

Source: https://curl.se/download/curl-7.64.1.tar.xz

SHA256: `9252332a7f871ce37bfa7f78bdd0a0e3924d8187cc27cb57c76c9474a7168fb3`

The adjacent `.asc` signature verified with GnuPG against Daniel Stenberg's
public key from https://daniel.haxx.se/mykey.asc. The verified signer fingerprint
is `27EDEAF22F3ABCEB50DB9A125CC908FDB71E12C2`. Retained artifacts, provenance,
hashes and the verification transcript are in this directory. No curl source
code is built or executed, and no runtime libraries are installed or replaced.

`python3 dependency-audit/curl-headers/install-headers.py` restores the nine
public headers to `sysroot-overlay/usr/include/curl` and
`sysroot-complete/usr/include/curl`. It checks the signed archive's pinned hash,
leaves matching files untouched, and refuses conflicting or symlink destinations.
`--check` validates without writing. `continue-build.sh` runs this restoration
before hooks/GN, including after a composed sysroot rebuild.

Validation completed:

- `abi-probe.c` compiled using the target LLVM20 facade and UOS sysroot:
  LP64 pointer/long widths, curl offset/socket types and linked-list layout.
- Its ELF object is LoongArch with flags `0x3`.
- Actual Ninja target `obj/third_party/crashpad/crashpad/util/net/http_transport_libcurl.o`
  compiled successfully using the added headers.

UOS runtime validation remains pending target SSH availability.
