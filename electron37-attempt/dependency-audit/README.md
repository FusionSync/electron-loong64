# UOS desktop development sysroot

Completed 2026-10-27 for the UOS 20 LoongArch machine at `the configured UOS target`.
This is an old-ABI target (glibc 2.28, ELF flags `0x3`, loader `/lib64/ld.so.1`).

## Result and usage

`/work/electron37-attempt/sysroot-complete` is the usable target sysroot inside
the `uos-electron37-attempt` container. Set:

```sh
export UOS_SYSROOT=/work/electron37-attempt/sysroot-complete
uos-pkg-config --cflags --libs gtk+-3.0 nss gbm libdrm alsa x11 xkbcommon dbus-1
bash /work/electron37-attempt/dependency-audit/desktop-probe.sh
```

Chromium GN `target_sysroot` should use this same path. Host x86_64 tools must
retain their own host headers, libraries, and pkg-config paths.

The overlay contains 99 development or protocol packages, 33,872,302 bytes of
DEB downloads (32.3 MiB). It supplies GTK, GLib, NSS/NSPR, ALSA, CUPS, Mesa GBM,
DRM, X11 extensions, XKB, DBus, fontconfig, freetype, Cairo, Pango, ATK, and
related headers and development symlinks. CUPS has headers and `-lcups` but this
UOS version does not provide a `cups.pc` file.

## Package selection and provenance

All DEBs came from the target's existing UOS official repository:
`https://professional-packages.chinauos.com/desktop-professional/`.
The target's normal APT authentication was used in place; credentials were not
copied. No packages were installed or upgraded on the target, and no RPM or
other distribution's packages were added to the target sysroot.

Development packages were selected against the corresponding **installed
runtime/source version**. The repository's newest candidate is often newer
than the installed desktop; selecting it blindly would introduce incompatible
headers or library requirements. Pure protocol/XML development packages do
not carry a runtime-library ABI requirement.

Of the 99 artifacts, 62 had SHA256 values in the target's cached APT package
metadata and were checked against those values. The other 37 exact installed
versions were retained at the official HTTPS package-pool URLs but absent from
the current package index. For those, package name, version, and architecture
were verified with `dpkg-deb`, HTTPS origin was recorded, and a local SHA256
was recorded for transfer/reuse integrity. These 37 local hashes are **not**
independent checks against authenticated repository index hashes.

`../dependency-packages/download-results.json` records each artifact's URL,
selection reason, control identity, expected hash where available, actual
hash, and result. `../dependency-packages/SHA256SUMS` verifies the retained
local archives. `target-audit.json` and `dev-closure.json` retain the installed
versions and dependency metadata used for selection. The download scripts
only use `apt-get download` or `apt-helper download-file`.

## Layout and rebuild

The original `/opt/uos-sysroot` is unchanged. `../sysroot-overlay` is the raw
unpacked development overlay. `../sysroot-complete` uses hardlinks to the
overlay plus 5,116 links to the base runtime snapshot, avoiding another full
copy. This composed view depends on `/opt/uos-sysroot` inside the container;
it is not a standalone portable sysroot archive.

`extract-and-merge.py` checks every downloaded hash before extraction and
refuses to replace an existing composed sysroot. A rebuild must explicitly
remove only the generated `sysroot-complete` directory first. The merge handles
the base system's `/lib -> usr/lib` layout even when development DEBs create
a real `/lib` directory. It copies the base `libc.so` linker script into the
composed root: GNU ld only rebases absolute paths in a script physically
located inside `--sysroot`.

## Validation

`desktop-probe.sh` cross-compiles a C program in the x86_64 container using
these headers and the target runtime libraries. The resulting binary was
sent through SSH to a temporary executable on the UOS machine, run there,
and removed. Both compilation/linking and target execution returned zero.

The test calls version functions and resolves symbols from GTK, GLib, NSS,
ALSA, GBM, DRM, CUPS, X11, XKB, and DBus without opening a display or devices.
Target output included:

```text
GTK 3.24.5 GLib 2.58.3 NSS 3.42.1 ALSA 1.1.8
UOS desktop development headers and target runtime libraries passed
```

Evidence is in `desktop-probe-build.log`, `desktop-probe-target.log`, and
`pkg-config-after.log`. This proves the tested headers, linker paths, ABI, and
runtime library selection work together. It does not prove that all Chromium
138 APIs compile against these older library versions or that Electron itself
has finished building.

On 2026-10-29, Crashpad required curl development headers absent from the
original 99-package overlay. Nine signed-upstream curl 7.64.1 public headers
were added, matching the installed runtime's upstream release. Existing UOS
runtime libraries were retained. See `curl-headers/README.md` for origin,
signature verification, ABI checks, limitations and offline restoration.

Electron's notification loader subsequently required `libnotify/notify.h`.
The exact UOS `libnotify-dev=0.7.7-4+sign`, matching installed `libnotify4`,
was downloaded through the restored target SSH connection and checked against
its APT SHA256. Its development files supplement the original overlay without
replacing runtime libraries. See `libnotify/README.md` for the retained package,
metadata, independent restore script and successful failed-target recompile.
