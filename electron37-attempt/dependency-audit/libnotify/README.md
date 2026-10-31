# Matched UOS libnotify development files

Electron's generated notification loader failed because `libnotify/notify.h`
was absent. The target already has `libnotify4=0.7.7-4+sign`; its exact matching
`libnotify-dev` was downloaded with the target's existing UOS official APT
authentication. Nothing was installed or upgraded on UOS.

The retained DEB is 49,790 bytes. Its SHA256 matches the target APT metadata
retained in `apt-metadata.txt`; package identity and origin are recorded in
`provenance.json`. `install-dev-files.py` verifies that identity and hash,
then restores four headers, the static archive, development linker symlink
and pkg-config file into both sysroot views. Existing conflicting files and
symlink parents are rejected. Runtime libraries are not changed. `--check`
checks the installed payload without writing; the continuation pipeline
restores missing files automatically.

The actual failed Ninja object compiled successfully after this addition;
see `compile-validation.log`. Final Electron linking and runtime validation
remain separate build stages. The original 99-package overlay and its
manifest remain unchanged; this additional package is tracked here.
