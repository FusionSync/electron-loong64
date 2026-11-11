# Crashpad MIPS64EL HTTP User-Agent

Verified on 2026-11-10 with LLVM 20.1.8 and the locked Buster / GLIBC 2.28
sysroot.

`third_party/crashpad/crashpad/util/net/http_transport_libcurl.cc` had no
MIPS64EL branch when selecting its process architecture string, so compilation
reached `#error Port`. The source helper now selects `"mips64"` for
`ARCH_CPU_MIPS64EL`.

This function intentionally uses Linux's kernel architecture spelling, rather
than the package architecture name. Linux's
[MIPS Makefile at v4.19](https://github.com/torvalds/linux/blob/v4.19/arch/mips/Makefile)
sets `UTS_MACHINE := mips64` under `CONFIG_64BIT`. The existing code also
appends `uname()`'s machine string when it differs. The change only supplies
the missing HTTP User-Agent label; curl loading, crash report transport, and
other architecture branches retain their behavior.

The complete failed Clang C++ command was rerun in the same container and
working directory, redirecting only the object and dependency-file outputs to
temporary paths. It exited **0** without diagnostics and produced an ELF
64-bit little-endian MIPS64 revision 2 object. No GN or Ninja invocation was
used for that verification.

Applying the source helper reported `1 changed, 30 already applied`, then
`0 changed, 31 already applied` on repetition. The main build must retry the
failed edge; this compile check does not send a crash report or verify HTTP
transport at runtime.
