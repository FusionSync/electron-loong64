# GNU linker and MIPS Rust bindings validation

Validated on 2026-11-10 against the Electron 37.2.2 / Chromium 138 build,
Clang 20, GNU target Binutils 2.38, and the Debian Buster glibc 2.28 sysroot.

## Two independent link failures

The original `chrome_crashpad_handler` command placed C++ archives in one
`--start-group` / `--end-group` pair and Rust rlibs in a later pair. Rust's
allocator introduced calls to `rust_allocator_internal::*` after GNU ld had
finished searching the C++ group. The C++ implementations were present in
`liballocator_impls.a` and `liballoc_error_handler_impl.a`; no library was missing.
The same ordering problem affected native host tools.

The MIPS allocator also contained two different undefined symbol spellings for
each C++ function. `R_MIPS_CALL_HI16` / `R_MIPS_CALL_LO16` referenced the normal
Itanium name, while `R_MIPS_JALR` incorrectly referenced that name with a leading
byte `0x01`. The input was bindgen's `#[link_name = "\u{1}_ZN..."]` attribute:
the Rust LLVM MIPS backend handled its no-mangle marker inconsistently.

The source helper now keeps C++, native libraries, and Rust inputs in a single
link group. On MIPS64EL Linux only, it also removes the no-mangle marker from
generated `link_name` attributes. This preserves their external names because
Linux ELF has no global symbol prefix. Other architectures keep their original
binding output.

## Actual command results

All tests reused the failed build's real response files and link arguments.
Outputs and replacement allocator rlibs were generated in a separate temporary
directory. GN, Ninja, the source tree, and the main output directory were not
modified by these probes.

| Probe | Result |
| --- | --- |
| MIPS `chrome_crashpad_handler`, one group only | Failed; only the five `0x01` symbol references remained |
| MIPS handler, one group and corrected bindings | Linked successfully, exit 0 |
| Native `character_data_generator`, one group only | Linked successfully, exit 0 |
| MIPS handler `--help`, QEMU 8.2.2 `Loongson-3A4000` with Buster libraries | Printed Crashpad help, exit 0 |

The successful handler was a 3,864,168-byte PIE ELF: little endian, MIPS64R2,
N64, hard double float, no ISA extensions or ASEs. Its highest required GLIBC
symbol version was **2.28**. Its SHA-256 was
`9c9b475440a8add579664173f7b9178d2414ff86b2c87deb00f2088a3cf1b9fb`.
The corrected allocator rlib had no symbol containing byte `0x01`.

The helper was also applied twice to an isolated fixture of the current source:
the first pass made 3 edits with 33 already applied, and the second made no
edits with all 36 already applied. A real wrapper invocation with a fixture
bindgen executable verified marker removal for `mips64el-linux-gnuabi64` and
`mips64el-unknown-linux-gnuabi64`, while x86-64 and LoongArch outputs retained
the marker.

The QEMU check covers this handler's startup and help path. It does not establish
that the complete Electron build, GUI, GPU, sandbox, or crash collection works on
physical 3A4000 hardware.
