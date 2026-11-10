# MIPS link-range preflight

**2026-11-10: no current evidence requires a global `-mxgot` or
`-mlong-calls` change. The final main Electron link has not completed.**
This is an inspection of existing objects, generated commands and relevant
toolchain implementations, not a successful full-Electron link result.

The generated target commands use MIPS64R2/N64, C/C++ `-fPIC`, Rust
`-Crelocation-model=pic`, and PIE linking. ThinLTO is disabled and the inspected
Rust commands use `-Clto=no`. A non-executing Clang `-###` inspection confirms
selection of `/opt/mips-toolchain/usr/bin/mips64el-linux-gnuabi64-ld`, GNU
binutils 2.38, with the `elf64ltsmip` emulation. No global `-mxgot` or
`-mlong-calls` is present.

## Existing-output evidence

These counts are snapshots of a build still in progress. They do not include
objects that have not yet been generated or certify every eventual link input.

| Inspection | Result |
| --- | --- |
| ELF flags and relocations in 14,335 target `.o` files | All PIC/CPIC; no `R_MIPS_PC16` or `R_MIPS_26`; 2,138,379 `R_MIPS_CALL16` and 2,219,423 `R_MIPS_JALR` relocations |
| GOT-reference estimate across 14,802 target `.o` files | Maximum 3662 estimated slots, about 29 KiB, in Node's `sqlite3.o` |
| 83 existing Rust `.rlib` files, containing 477 MIPS ELF members | All PIC/CPIC; no `R_MIPS_PC16` or `R_MIPS_26`; largest distinct GOT-reference set 3212; extended `GOT_HI16/LO16` and `CALL_HI16/LO16` sequences are present |

The object estimate counts distinct symbol/addend references, conservatively
counts distinct `GOT_PAGE` references, allows two slots for GD/LDM TLS entries,
and adds two reserved slots. The maximum consists of 137 non-page references,
3523 page references and two reserved slots. This is an estimate from input
relocations, not a measurement of the final linker's allocated GOT.

## Range handling and its limits

- **GOT16:** GNU 2.38 explicitly implements
  [multi-GOT partitioning](https://github.com/RTEMS/sourceware-mirror-binutils-gdb/blob/binutils-2_38-branch/bfd/elfxx-mips.c#L4903),
  [automatically invoked when the aggregate GOT exceeds the window](https://github.com/RTEMS/sourceware-mirror-binutils-gdb/blob/binutils-2_38-branch/bfd/elfxx-mips.c#L9704)
  on this non-VxWorks target. The
  [size bound](https://github.com/RTEMS/sourceware-mirror-binutils-gdb/blob/binutils-2_38-branch/bfd/elfxx-mips.c#L919)
  is `0x7ff0 + 0x7fff`, about 64 KiB, or roughly 8189 eight-byte slots before
  reserved entries are deducted. A large aggregate Electron GOT therefore
  does not by itself require `-mxgot`. A single input object's requirements
  can still exceed a small-GOT window; no such input was found in this audit.
  [GCC's documented multi-GOT qualification](https://gcc.gnu.org/onlinedocs/gcc/MIPS-Options.html#index-mxgot)
  describes this distinction.
- **Direct calls:** ordinary inspected PIC calls load a complete address from
  the GOT and use `jalr`; they do not require caller and callee to share a
  256 MiB `jal` region. GNU treats `R_MIPS_JALR` as an optimization hint and
  [only substitutes a short `bal` when its displacement fits](https://github.com/RTEMS/sourceware-mirror-binutils-gdb/blob/binutils-2_38-branch/bfd/elfxx-mips.c#L6665).
  An eventual hand-written direct `R_MIPS_26` or `R_MIPS_PC16` reference would
  still need its own range analysis; the audit found neither.
- **LA25:** GNU's
  [LA25 interfaces initialize `$t9` for non-PIC calls into PIC functions](https://github.com/RTEMS/sourceware-mirror-binutils-gdb/blob/binutils-2_38-branch/bfd/elfxx-mips.c#L263).
  The [eligibility check explicitly skips EF_PIC callers](https://github.com/RTEMS/sourceware-mirror-binutils-gdb/blob/binutils-2_38-branch/bfd/elfxx-mips.c#L5299).
  These interfaces are not a general guarantee that arbitrary far branches
  or direct jumps will be repaired.
- **Function-local short branches:** upstream LLVM 20.1.8 has an enabled
  [MIPS branch-expansion pass](https://github.com/llvm/llvm-project/blob/llvmorg-20.1.8/llvm/lib/Target/Mips/MipsBranchExpansion.cpp#L112)
  for [standard MIPS encodings](https://github.com/llvm/llvm-project/blob/llvmorg-20.1.8/llvm/lib/Target/Mips/MipsSubtarget.h#L346).
  Its [N64 PIC expansion](https://github.com/llvm/llvm-project/blob/llvmorg-20.1.8/llvm/lib/Target/Mips/MipsBranchExpansion.cpp#L546)
  uses a local PC acquisition, a wider offset and `jr64`; it assumes a
  within-function offset of less than ±2 GiB. No flag disabling this pass
  was found in the inspected commands. This source reference is **upstream
  LLVM 20.1.8, not the LoongNix modified source tree**. The installed C/C++
  compiler identifies as LoongNix Clang 20.1.8; source inspection does not
  establish that every downstream implementation detail is identical.
  The Rust archive findings above are observations of its actual objects,
  not a claim that the vendored Rust compiler uses this LLVM version.

The current configuration should continue unchanged on this evidence.
Successful final Electron linking and subsequent runtime validation remain
required. No GN/Ninja invocation, rebuild or build-input modification was
performed for this inspection.
