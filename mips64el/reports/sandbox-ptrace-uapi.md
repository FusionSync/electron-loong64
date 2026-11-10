# MIPS sandbox ptrace header

Verified on 2026-11-10 using the locked Buster / GLIBC 2.28 sysroot.

`sandbox/linux/seccomp-bpf-helpers/syscall_parameters_restrictions.cc` failed
because it tried to include `asm/ptrace-abi.h` when `PTRACE_GET_THREAD_AREA`
was missing from glibc's `sys/ptrace.h`. That fallback header belongs to the
x86 Linux UAPI (`arch/x86/include/uapi/asm/ptrace-abi.h`); the MIPS UAPI does
not provide it.

The Buster MIPS target already has the required definition in
`usr/include/mips64el-linux-gnuabi64/asm/ptrace.h`:

```c
#define PTRACE_GET_THREAD_AREA 25
```

The source helper now includes that target header for MIPS under the existing
Linux / missing-definition guard. Other architectures retain the original
include branch. `RestrictPtrace()` still allows the architecture's original
thread-area request alongside its register and attach requests; no sandbox
operation or policy was removed. The sysroot and toolchain were not changed.

The complete failed Clang C++ command was extracted from the current Ninja
log and rerun in the same container and output-directory working directory.
Only the object and dependency-file output paths were redirected to temporary
files. The compile exited **0** without diagnostics. The object is ELF 64-bit
little-endian MIPS64 revision 2. Its dependency file confirms that both
`sys/ptrace.h` and `asm/ptrace.h` came from `mips-sysroot-buster`, with no host
header substitution.

The source helper reported `1 changed, 29 already applied`, then
`0 changed, 30 already applied` on repetition. No GN or Ninja process was
started for the verification. The main build must retry the failed edge on
its next invocation; compiling this source alone does not establish a full
sandbox runtime test.
