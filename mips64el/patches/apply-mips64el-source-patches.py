#!/usr/bin/env python3
"""Apply the small Electron/Chromium MIPS64EL source adaptations.

Usage:
    apply-mips64el-source-patches.py /path/to/chromium/src

The source root may also be supplied through MIPS64EL_SOURCE_ROOT.  It is
intentionally not inferred from this repository: a public checkout can live
anywhere, and applying a patch to the wrong worktree is difficult to diagnose.
The edits target the independently synchronized Chromium/Electron checkout
after its official Electron patches; they do not import LoongArch patches.
They are idempotent and checked against the surrounding upstream text so that
a source revision mismatch fails early.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "source_root",
        nargs="?",
        help="Chromium source root (the directory containing build/ and electron/)",
    )
    return parser.parse_args()


def source_root_from_args(args: argparse.Namespace) -> Path:
    value = args.source_root or os.environ.get("MIPS64EL_SOURCE_ROOT")
    if not value:
        raise SystemExit(
            "pass the Chromium source root as an argument or set "
            "MIPS64EL_SOURCE_ROOT"
        )
    root = Path(value).expanduser().resolve()
    if not root.is_dir():
        raise SystemExit(f"source root does not exist or is not a directory: {root}")
    required = (root / "build", root / "electron")
    missing = [str(path.relative_to(root)) for path in required if not path.is_dir()]
    if missing:
        raise SystemExit(
            f"{root} does not look like a Chromium/Electron source root "
            f"(missing: {', '.join(missing)})"
        )
    return root


class SourcePatcher:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.changed = 0
        self.already_applied = 0

    def replace(self, relative: str, old: str, new: str) -> None:
        path = self.root / relative
        if not path.is_file():
            raise SystemExit(f"expected source file is missing: {relative}")
        text = path.read_text()
        if new in text:
            self.already_applied += 1
            return
        if old not in text:
            raise SystemExit(f"expected upstream context not found: {relative}")
        path.write_text(text.replace(old, new, 1))
        self.changed += 1

    def finish(self) -> None:
        print(
            f"patched {self.root} ({self.changed} changed, "
            f"{self.already_applied} already applied)"
        )


def main() -> None:
    args = parse_args()
    patcher = SourcePatcher(source_root_from_args(args))

    patcher.replace(
        "build/config/rust.gni",
        '  } else if (current_cpu == "riscv64") {\n',
        '  } else if (current_cpu == "mips64el") {\n'
        '    rust_abi_target = "mips64el-unknown-linux-gnuabi64"\n'
        '    cargo_target_abi = ""\n'
        '  } else if (current_cpu == "riscv64") {\n',
    )
    patcher.replace(
        "build/rust/known-target-triples.txt",
        "loongarch64-unknown-linux-gnu\n",
        "loongarch64-unknown-linux-gnu\n"
        "mips64el-unknown-linux-gnuabi64\n",
    )
    patcher.replace(
        "base/allocator/partition_allocator/partition_alloc.gni",
        '           current_cpu == "arm64e" || current_cpu == "loong64" ||\n'
        '           current_cpu == "riscv64") {',
        '           current_cpu == "arm64e" || current_cpu == "loong64" ||\n'
        '           current_cpu == "mips64el" || current_cpu == "riscv64") {',
    )

    # Loongson MIPS kernels commonly use 16 KiB pages, but 4 KiB kernels must
    # remain valid too. Reuse the existing POSIX runtime page-size cache.
    patcher.replace(
        "base/allocator/partition_allocator/src/partition_alloc/"
        "page_allocator_constants.h",
        '    (PA_BUILDFLAG(IS_LINUX) && PA_BUILDFLAG(PA_ARCH_CPU_PPC64))\n',
        '    (PA_BUILDFLAG(IS_LINUX) && PA_BUILDFLAG(PA_ARCH_CPU_PPC64)) ||       \\\n'
        '    (PA_BUILDFLAG(IS_LINUX) && PA_BUILDFLAG(PA_ARCH_CPU_MIPS64EL))\n',
    )
    patcher.replace(
        "base/allocator/partition_allocator/src/partition_alloc/"
        "partition_page_constants.h",
        '    (PA_BUILDFLAG(PA_ARCH_CPU_ARM64) || '
        'PA_BUILDFLAG(PA_ARCH_CPU_PPC64))\n',
        '    (PA_BUILDFLAG(PA_ARCH_CPU_ARM64) || '
        'PA_BUILDFLAG(PA_ARCH_CPU_PPC64) || \\\n'
        '     PA_BUILDFLAG(PA_ARCH_CPU_MIPS64EL))\n',
    )

    # GNU ld requires a thin archive's symbol index even with a Clang frontend.
    # Keep the upstream index-free archive optimization when linking with LLD.
    patcher.replace(
        "build/config/compiler/BUILD.gn",
        '  if ((is_apple && use_lld) || (is_linux && !is_clang) || '
        'current_os == "aix") {\n',
        '  if ((is_apple && use_lld) || '
        '(is_linux && (!is_clang || !use_lld)) ||\n'
        '      current_os == "aix") {\n',
    )

    # LLVM 20 accepts musttail in the frontend, but its MIPS N64 backend cannot
    # lower all of Chromium's required tail calls and aborts during codegen.
    for relative, attribute in (
        ("base/compiler_specific.h", "__has_cpp_attribute"),
        (
            "base/allocator/partition_allocator/src/partition_alloc/"
            "partition_alloc_base/compiler_specific.h",
            "PA_HAS_CPP_ATTRIBUTE",
        ),
    ):
        patcher.replace(
            relative,
            f"#if {attribute}(clang::musttail)\n",
            f"#if {attribute}(clang::musttail) && !defined(__mips__)\n",
        )

    patcher.replace(
        "third_party/skia/modules/skcms/src/skcms_internals.h",
        "        #if __has_cpp_attribute(clang::musttail) && "
        "!__has_feature(memory_sanitizer) \\\n",
        "        #if __has_cpp_attribute(clang::musttail) && "
        "!defined(__mips__) && !__has_feature(memory_sanitizer) \\\n",
    )
    patcher.replace(
        "third_party/protobuf/src/google/protobuf/port_def.inc",
        '    !(defined(_MSC_VER) && defined(_M_IX86)) && !defined(__i386__)\n',
        '    !(defined(_MSC_VER) && defined(_M_IX86)) && !defined(__i386__) && \\\n'
        '    !defined(__mips__)\n',
    )
    patcher.replace(
        "third_party/skia/src/core/SkRasterPipeline.h",
        "#if __has_cpp_attribute(clang::musttail) && "
        "!defined(__EMSCRIPTEN__) && !defined(SK_CPU_ARM32) && \\\n",
        "#if __has_cpp_attribute(clang::musttail) && !defined(__mips__) && "
        "!defined(__EMSCRIPTEN__) && !defined(SK_CPU_ARM32) && \\\n",
    )

    for relative in (
        "third_party/cpu_features/BUILD.gn",
        "third_party/angle/third_party/cpu_features/BUILD.gn",
        "third_party/pdfium/third_party/cpu_features/BUILD.gn",
        "v8/third_party/cpu_features/BUILD.gn",
    ):
        patcher.replace(
            relative,
            '  } else if (current_cpu == "mips") {',
            '  } else if (current_cpu == "mips" || current_cpu == "mips64el") {',
        )

    # V8's build-config dump action is instantiated in the host toolchain too;
    # that scope may not declare MIPS-only args even when the target is MIPS64EL.
    patcher.replace(
        "v8/BUILD.gn",
        '  if (arch == "mips64" || arch == "mips64el") {\n'
        '    mips_arch_variant_var = mips_arch_variant\n'
        '    mips_use_msa_var = mips_use_msa\n'
        '  }\n',
        '  if (arch == "mips64" || arch == "mips64el") {\n'
        '    # The dump action is also instantiated in the host toolchain.  In that\n'
        '    # scope the MIPS-only args are not declared, even when the target is\n'
        '    # MIPS64EL, so provide the architecture defaults explicitly.\n'
        '    if (defined(mips_arch_variant)) {\n'
        '      mips_arch_variant_var = mips_arch_variant\n'
        '    } else {\n'
        '      mips_arch_variant_var = "r2"\n'
        '    }\n'
        '    if (defined(mips_use_msa)) {\n'
        '      mips_use_msa_var = mips_use_msa\n'
        '    }\n'
        '  }\n',
    )

    # This MIPS64 target uses N64, whose callee-saved FPRs are f24..f31.
    # The upstream list instead matched N32, leaking f31 scratch writes to C
    # callers and omitting caller-saved allocatable f20/f22 at C calls.
    patcher.replace(
        "v8/src/codegen/mips64/register-mips64.h",
        "#define C_CALL_CALLEE_SAVE_FP_REGISTERS f20, f22, f24, f26, f28, f30\n",
        "#define C_CALL_CALLEE_SAVE_FP_REGISTERS f24, f25, f26, f27, f28, f29, f30, f31\n",
    )
    patcher.replace(
        "v8/src/codegen/mips64/reglist-mips64.h",
        "const int kNumCalleeSavedFPU = 6;\n",
        "const int kNumCalleeSavedFPU = kCalleeSavedFPU.Count();\n",
    )
    patcher.replace(
        "v8/src/codegen/mips64/reglist-mips64.h",
        "const DoubleRegList kCallerSavedFPU = {f0,  f2,  f4,  f6,  f8,\n"
        "                                       f10, f12, f14, f16, f18};\n",
        "const DoubleRegList kCallerSavedFPU = {f0,  f2,  f4,  f6,  f8,\n"
        "                                       f10, f12, f14, f16, f18, f20, f22};\n",
    )

    patcher.replace(
        "third_party/swiftshader/third_party/marl/BUILD.gn",
        '    } else if (current_cpu == "mips64") {\n',
        '    } else if (current_cpu == "mips64" || current_cpu == "mips64el") {\n',
    )

    # MIPS64 also defines __mips__. Check the narrower macro first so the
    # software Vulkan JIT uses the N64 triple rather than a 32-bit MIPS ABI.
    llvm_config = (
        "third_party/swiftshader/third_party/llvm-10.0/configs/linux/"
        "include/llvm/Config/"
    )
    for relative, macro in (
        ("llvm-config.h", "LLVM_DEFAULT_TARGET_TRIPLE"),
        ("llvm-config.h", "LLVM_HOST_TRIPLE"),
        ("config.h", "LLVM_DEFAULT_TARGET_TRIPLE"),
    ):
        patcher.replace(
            llvm_config + relative,
            '#elif defined(__mips__)\n'
            f'#define {macro} "mipsel-linux-gnu"\n'
            '#elif defined(__mips64)\n'
            f'#define {macro} "mips64el-linux-gnuabi64"\n',
            '#elif defined(__mips64)\n'
            f'#define {macro} "mips64el-linux-gnuabi64"\n'
            '#elif defined(__mips__)\n'
            f'#define {macro} "mipsel-linux-gnu"\n',
        )

    # N64 preserves every FPR from f24 through f31. The upstream fiber switch
    # accidentally used f31 twice and never saved/restored f30's own value.
    for instruction, context_register in (("s.d", "$a0"), ("l.d", "$v0")):
        patcher.replace(
            "third_party/swiftshader/third_party/marl/src/osfiber_asm_mips64.S",
            f"    {instruction}  $f31, MARL_REG_f30({context_register})\n",
            f"    {instruction}  $f30, MARL_REG_f30({context_register})\n",
        )

    patcher.replace(
        "build/config/clang/BUILD.gn",
        '        } else if (current_cpu == "loong64") {\n'
        '          _dir = "loongarch64-unknown-linux-gnu"\n'
        '        } else {\n',
        '        } else if (current_cpu == "loong64") {\n'
        '          _dir = "loongarch64-unknown-linux-gnu"\n'
        '        } else if (current_cpu == "mips64el") {\n'
        '          _dir = "mips64el-unknown-linux-gnuabi64"\n'
        '        } else {\n',
    )

    # The LLVM 20 distribution has no MIPS64EL compiler-rt archive. Clang can
    # use the GCC runtime supplied by the cross toolchain, so do not add a
    # nonexistent clang_rt.builtins archive to MIPS target links.
    patcher.replace(
        "build/config/clang/BUILD.gn",
        '  } else {\n'
        '    libname = "builtins"\n'
        '  }\n'
        '}\n\n'
        '# Adds a dependency on the Clang runtime library clang_rt.profile.',
        '  } else if (current_cpu != "mips64el") {\n'
        '    libname = "builtins"\n'
        '  }\n'
        '}\n\n'
        '# Adds a dependency on the Clang runtime library clang_rt.profile.',
    )

    # GNU ld must be able to revisit C++ archives after Rust introduces calls
    # to Chromium's C++ allocator. Separate C++ and Rust groups cannot do that.
    # This also affects native host tools linked by the same GNU toolchain.
    patcher.replace(
        "build/toolchain/gcc_toolchain.gni",
        '      link_command = "$ld {{ldflags}}${extra_ldflags} -o '
        '\\"$unstripped_outfile\\" $start_group_flag @\\"$rspfile\\" '
        '$end_group_flag {{solibs}} {{libs}} '
        '$start_group_flag {{rlibs}} $end_group_flag"\n',
        '      link_command = "$ld {{ldflags}}${extra_ldflags} -o '
        '\\"$unstripped_outfile\\" $start_group_flag @\\"$rspfile\\" '
        '{{solibs}} {{libs}} {{rlibs}} $end_group_flag"\n',
    )

    # Rust's MIPS LLVM backend strips bindgen's no-mangle marker from the
    # CALL_HI16/LO16 relocations, but incorrectly keeps it in R_MIPS_JALR.
    # Linux ELF has no global symbol prefix, so removing that marker from
    # generated link_name attributes preserves the intended external name.
    # Keep every other target's binding output unchanged.
    patcher.replace(
        "build/rust/run_bindgen.py",
        'import os\nimport subprocess\n',
        'import os\nimport re\nimport subprocess\n',
    )
    patcher.replace(
        "build/rust/run_bindgen.py",
        '      subprocess.check_call([args.exe, *genargs], env=env)\n',
        r'''      subprocess.check_call([args.exe, *genargs], env=env)
      if any(arg.startswith('--target=mips64el-') and '-linux-' in arg
             for arg in args.clangargs):
        with open(args.output, encoding='utf-8') as output:
          bindings = output.read()
        bindings = re.sub(r'(link_name\s*=\s*")\\u\{1\}', r'\1', bindings)
        with open(args.output, 'w', encoding='utf-8') as output:
          output.write(bindings)
''',
    )

    patcher.replace(
        "build/config/linux/pkg-config.py",
        '  (options, args) = parser.parse_args()\n\n'
        '  # Make a list of regular expressions to strip out.\n',
        '  (options, args) = parser.parse_args()\n\n'
        '  # GN passes a sysroot path rebased from the source tree.  In cross builds\n'
        '  # that path can be relative (for example, ../../../opt/mips-sysroot), while\n'
        '  # pkg-config emits paths using that same relative prefix.  Normalize it\n'
        '  # before invoking pkg-config so the returned include and library paths are\n'
        '  # absolute and GN only rebases them once.\n'
        '  if options.sysroot:\n'
        '    options.sysroot = os.path.abspath(options.sysroot)\n\n'
        '  # Make a list of regular expressions to strip out.\n',
    )

    # Chromium's printing args enable CUPS by default.  When use_sysroot is
    # false (needed so the host toolchain does not demand an amd64 sysroot),
    # select the target sysroot's cups-config for the MIPS target toolchain.
    patcher.replace(
        "printing/BUILD.gn",
        '        if (use_sysroot) {\n'
        '          cups_sysroot = rebase_path(sysroot)\n'
        '        } else {\n'
        '          cups_sysroot = ""\n'
        '        }\n',
        '        if (use_sysroot || (target_sysroot != "" && current_cpu == target_cpu)) {\n'
        '          if (sysroot != "") {\n'
        '            cups_sysroot = rebase_path(sysroot)\n'
        '          } else {\n'
        '            cups_sysroot = rebase_path(target_sysroot)\n'
        '          }\n'
        '        } else {\n'
        '          cups_sysroot = ""\n'
        '        }\n',
    )

    # MIPS uses libaom's existing scalar Linux configuration, as RISC-V does.
    # It has no MSA, LoongArch, x86, or ARM dispatch code.
    patcher.replace(
        "third_party/libaom/BUILD.gn",
        '} else if (current_cpu == "riscv64") {\n',
        '} else if (current_cpu == "riscv64" || current_cpu == "mips64el") {\n',
    )

    runtime_delegate = (
        "electron/shell/browser/extensions/api/runtime/"
        "electron_runtime_api_delegate.cc"
    )
    patcher.replace(
        runtime_delegate,
        '  } else if (arch == "x64") {\n'
        '    info->arch = extensions::api::runtime::PlatformArch::kX86_64;\n',
        '  } else if (arch == "x64") {\n'
        '    info->arch = extensions::api::runtime::PlatformArch::kX86_64;\n'
        '  } else if (arch == "mips64el") {\n'
        '    info->arch = extensions::api::runtime::PlatformArch::kMips64;\n',
    )
    patcher.replace(
        runtime_delegate,
        '  } else if (nacl_arch == "x86-64") {\n'
        '    info->nacl_arch = extensions::api::runtime::PlatformNaclArch::kX86_64;\n',
        '  } else if (nacl_arch == "x86-64") {\n'
        '    info->nacl_arch = extensions::api::runtime::PlatformNaclArch::kX86_64;\n'
        '  } else if (nacl_arch == "mips64") {\n'
        '    info->nacl_arch = extensions::api::runtime::PlatformNaclArch::kMips64;\n',
    )

    # Electron's upstream generator assumes out/Release lives inside src.
    # Keep independent output mounts usable by resolving Node from this script.
    patcher.replace(
        "electron/script/node/generate_original_fs.py",
        'NODE_ROOT_DIR = "../../third_party/electron_node"\n',
        'NODE_ROOT_DIR = os.path.join(\n'
        '    os.path.dirname(os.path.abspath(__file__)),\n'
        '    "..", "..", "..", "third_party", "electron_node")\n',
    )

    # Node invokes `gn args` from the output directory. An output mounted
    # outside src has no .gn ancestor, so identify the source root explicitly.
    patcher.replace(
        "third_party/electron_node/tools/generate_config_gypi.py",
        "      [GN, 'args', '--list', '--short', '-C', out_dir])\n",
        "      [GN, 'args', '--list', '--short', '-C', out_dir,\n"
        "       '--root=' + os.path.abspath(os.path.join(\n"
        "           os.path.dirname(__file__), '..', '..', '..'))])\n",
    )

    # Buster's MIPS glibc omits GET_THREAD_AREA, but the target kernel UAPI
    # provides it in asm/ptrace.h. asm/ptrace-abi.h is an x86 header.
    patcher.replace(
        "sandbox/linux/seccomp-bpf-helpers/syscall_parameters_restrictions.cc",
        '#if BUILDFLAG(IS_LINUX) && !defined(__arm__) && !defined(__aarch64__) && \\\n'
        '    !defined(PTRACE_GET_THREAD_AREA)\n'
        '// Also include asm/ptrace-abi.h since ptrace.h in older libc (for instance\n'
        '// the one in Ubuntu 16.04 LTS) is missing PTRACE_GET_THREAD_AREA.\n'
        "// asm/ptrace-abi.h doesn't exist on arm32 and PTRACE_GET_THREAD_AREA isn't\n"
        "// defined on aarch64, so don't try to include this on those platforms.\n"
        '#include <asm/ptrace-abi.h>\n'
        '#endif\n',
        '#if BUILDFLAG(IS_LINUX) && !defined(__arm__) && !defined(__aarch64__) && \\\n'
        '    !defined(PTRACE_GET_THREAD_AREA)\n'
        '#if defined(__mips__)\n'
        '// MIPS exposes the TLS ptrace requests in its target kernel UAPI.\n'
        '#include <asm/ptrace.h>\n'
        '#else\n'
        '// Also include asm/ptrace-abi.h since ptrace.h in older libc (for instance\n'
        '// the one in Ubuntu 16.04 LTS) is missing PTRACE_GET_THREAD_AREA.\n'
        "// asm/ptrace-abi.h doesn't exist on arm32 and PTRACE_GET_THREAD_AREA isn't\n"
        "// defined on aarch64, so don't try to include this on those platforms.\n"
        '#include <asm/ptrace-abi.h>\n'
        '#endif\n'
        '#endif\n',
    )

    # Match Linux's N64 UTS_MACHINE spelling in Crashpad's HTTP User-Agent.
    patcher.replace(
        "third_party/crashpad/crashpad/util/net/http_transport_libcurl.cc",
        '#elif defined (ARCH_CPU_RISCV64)\n'
        '    static constexpr char arch[] = "riscv64";\n',
        '#elif defined (ARCH_CPU_RISCV64)\n'
        '    static constexpr char arch[] = "riscv64";\n'
        '#elif defined(ARCH_CPU_MIPS64EL)\n'
        '    static constexpr char arch[] = "mips64";\n',
    )

    patcher.finish()


if __name__ == "__main__":
    main()
