#!/usr/bin/env python3
"""Execute source-derived V8 MIPS64 FPR save/restore envelopes under QEMU.

The emitter compiles and runs V8's actual MultiPushFPU/MultiPopFPU C++ method
bodies with a tiny instruction-output adapter. Register sets come from the
actual V8 headers. The callee test executes the actual Liftoff f64-to-i32
conversion instruction fragment, and the caller test calls a Clang-compiled
N64 C function. This is a focused ABI probe, not a full V8 or Electron run.
All generated files stay in a temporary directory; GN/Ninja are not invoked.
"""

import argparse
from pathlib import Path
import re
import subprocess
import tempfile


def method(source, name):
    """Copy a real method body, including its original save/restore loops."""
    start = source.index(f"void MacroAssembler::{name}(DoubleRegList regs)")
    opening = source.index("{", start)
    depth = 1
    end = opening + 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[start:end]


def emitter_source(root):
    headers = root / "v8/src/codegen/mips64"
    registers = (headers / "register-mips64.h").read_text()
    reglist = (headers / "reglist-mips64.h").read_text()
    assembler = (headers / "macro-assembler-mips64.cc").read_text()
    callee = re.search(r"^#define C_CALL_CALLEE_SAVE_FP_REGISTERS (.+)$",
                       registers, re.MULTILINE).group(1)
    caller = re.search(r"const DoubleRegList kCallerSavedFPU = \{([^}]+)\}",
                       reglist).group(1)
    # Compile the real methods with only their instruction sinks substituted.
    # This runs the actual list counting, iteration order, and stack offsets.
    return r'''
#include <cstdint>
#include <cstdio>
#include <initializer_list>
#include <string>
enum Register { sp };
enum FPR { ''' + ", ".join(f"f{i}={i}" for i in range(32)) + r''' };
constexpr int kNumRegisters = 32;
constexpr int kDoubleSize = 8;
struct DoubleRegList {
  uint32_t value = 0;
  DoubleRegList(std::initializer_list<int> regs) {
    for (int reg : regs) value |= uint32_t{1} << reg;
  }
  int Count() const { return __builtin_popcount(value); }
  uint32_t bits() const { return value; }
};
struct FPURegister {
  int code;
  static FPURegister from_code(int code) { return {code}; }
};
struct Operand { int value; explicit Operand(int value) : value(value) {} };
struct MemOperand {
  int offset;
  MemOperand(Register, int offset) : offset(offset) {}
};
class MacroAssembler {
 public:
  void MultiPushFPU(DoubleRegList regs);
  void MultiPopFPU(DoubleRegList regs);
  void Dsubu(Register, Register, Operand value) {
    std::printf("    daddiu $sp, $sp, -%d\n", value.value);
  }
  void daddiu(Register, Register, int value) {
    std::printf("    daddiu $sp, $sp, %d\n", value);
  }
  void Sdc1(FPURegister reg, MemOperand address) {
    std::printf("    sdc1 $f%d, %d($sp)\n", reg.code, address.offset);
  }
  void Ldc1(FPURegister reg, MemOperand address) {
    std::printf("    ldc1 $f%d, %d($sp)\n", reg.code, address.offset);
  }
};
''' + method(assembler, "MultiPushFPU") + "\n" + method(
        assembler, "MultiPopFPU") + r'''
int main(int argc, char** argv) {
  if (argc != 3) return 2;
  const DoubleRegList callee = {''' + callee + r'''};
  const DoubleRegList caller = {''' + caller + r'''};
  DoubleRegList selected = std::string(argv[1]) == "callee" ? callee : caller;
  MacroAssembler assembler;
  if (std::string(argv[2]) == "push") assembler.MultiPushFPU(selected);
  else assembler.MultiPopFPU(selected);
}
'''


def liftoff_fragment(root):
    registers = (root / "v8/src/codegen/mips64/register-mips64.h").read_text()
    aliases = dict(re.findall(
        r"constexpr DoubleRegister (kScratchDoubleReg2?) = (f\d+);", registers))
    source = (root / "v8/src/wasm/baseline/mips64/"
              "liftoff-assembler-mips64-inl.h").read_text()
    conversion = source.split("case kExprI32SConvertF64: {", 1)[1].split(
        "case kExprI32UConvertF64:", 1)[0]
    # Keep the actual three instructions that write/read the secondary scratch
    # register, with the real register aliases. Rounding and the trap branch
    # are outside the fragment; the probe supplies an exactly integral input.
    statements = re.findall(
        r"(?:trunc_w_d|mfc1|cvt_d_w)\([^;]+;", conversion)
    expected = [
        "trunc_w_d(kScratchDoubleReg2, rounded);",
        "mfc1(dst.gp(), kScratchDoubleReg2);",
        "cvt_d_w(kScratchDoubleReg2, kScratchDoubleReg2);",
    ]
    if [re.sub(r"\s+", " ", text) for text in statements] != expected:
        raise SystemExit("Unexpected real Liftoff conversion fragment")
    for text in statements:
        text = text.removesuffix(";")
        text = text.replace("dst.gp()", "$t0")
        text = text.replace("kScratchDoubleReg2", "$" + aliases["kScratchDoubleReg2"])
        text = text.replace("rounded", "$" + aliases["kScratchDoubleReg"])
        name, arguments = text.split("(", 1)
        yield "    " + name.replace("_", ".") + " " + arguments[:-1]


def wrapper(name, body):
    # Protect the probe's own caller independently of the V8 policy under test.
    # s0 holds the observations pointer across a real native call.
    lines = [f".globl {name}", f".type {name}, @function", f"{name}:",
             "    daddiu $sp, $sp, -96", "    sd $s0, 0($sp)",
             "    sd $ra, 8($sp)"]
    lines += [f"    sdc1 $f{i}, {16 + (i - 24) * 8}($sp)"
              for i in range(24, 32)]
    lines += ["    move $s0, $a1", *body]
    lines += [f"    ldc1 $f{i}, {16 + (i - 24) * 8}($sp)"
              for i in range(24, 32)]
    lines += ["    ld $s0, 0($sp)", "    ld $ra, 8($sp)",
              "    daddiu $sp, $sp, 96", "    jr $ra", "    nop",
              f".size {name}, .-{name}"]
    return "\n".join(lines)


def assembly_source(root, emitter):
    def emit(which, action):
        return subprocess.check_output([str(emitter), which, action],
                                       text=True).splitlines()

    callee = [f"    ldc1 $f{i}, {(i - 24) * 8}($a0)" for i in range(24, 32)]
    callee += emit("callee", "push")
    callee += ["    dli $t0, 0x4010000000000000", "    dmtc1 $t0, $f30"]
    callee += list(liftoff_fragment(root))
    callee += emit("callee", "pop")
    callee += [f"    sdc1 $f{i}, {(i - 24) * 8}($s0)" for i in range(24, 32)]

    caller = [f"    ldc1 $f{i}, {i * 4}($a0)" for i in range(0, 24, 2)]
    caller += emit("caller", "push")
    caller += ["    move $t9, $a2", "    jalr $t9", "    nop"]
    caller += emit("caller", "pop")
    caller += [f"    sdc1 $f{i}, {i * 4}($s0)" for i in range(0, 24, 2)]
    return (".text\n.set noreorder\n" + wrapper("probe_callee", callee) +
            "\n" + wrapper("probe_caller", caller) +
            '\n.section .note.GNU-stack,"",@progbits\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--baseline-source-root", type=Path,
                        help="Optional original source tree: require f31/f20/f22 failure")
    parser.add_argument("--runtime-root", required=True, type=Path)
    parser.add_argument("--qemu", default="qemu-mips64el-static")
    parser.add_argument("--cpu", default="Loongson-3A4000")
    parser.add_argument("--host-cxx", default="c++")
    parser.add_argument("--llvm-root", type=Path, default=Path("/opt/llvm20"))
    parser.add_argument("--sysroot", type=Path,
                        default=Path("/opt/mips-sysroot-buster"))
    parser.add_argument("--linker", default=(
        "/opt/mips-toolchain/usr/bin/mips64el-linux-gnuabi64-ld"))
    args = parser.parse_args()
    qemu = [args.qemu, "-cpu", args.cpu, "-L", str(args.runtime_root.resolve()),
            "-E", "LD_LIBRARY_PATH=/lib/mips64el-linux-gnuabi64:"
            "/usr/lib/mips64el-linux-gnuabi64"]
    flags = [str(args.llvm_root / "bin/clang"),
             "--target=mips64el-linux-gnuabi64", "-mcpu=mips64r2", "-mabi=64",
             "-mhard-float", f"--sysroot={args.sysroot.resolve()}",
             f"-fuse-ld={args.linker}", "-std=c11", "-fPIC", "-pie",
             "-fstack-protector", "-fno-omit-frame-pointer",
             str(Path(__file__).resolve().parent / "probe.c")]
    sources = [("patched", args.source_root.resolve())]
    if args.baseline_source_root:
        sources.insert(0, ("baseline", args.baseline_source_root.resolve()))
    with tempfile.TemporaryDirectory(prefix="mips-v8-n64-fprs-") as directory:
        temporary = Path(directory)
        for label, root in sources:
            cpp = temporary / (label + "-emitter.cc")
            cpp.write_text(emitter_source(root))
            emitter = temporary / (label + "-emitter")
            subprocess.run([args.host_cxx, "-std=c++17", str(cpp), "-o", str(emitter)],
                           check=True)
            assembly = temporary / (label + ".S")
            assembly.write_text(assembly_source(root, emitter))
            for optimization in ("-O0", "-O2", "-Os"):
                binary = temporary / (label + optimization)
                subprocess.run([*flags, optimization, str(assembly), "-o", str(binary)],
                               check=True)
                result = subprocess.run([*qemu, str(binary)], text=True,
                                        stdout=subprocess.PIPE,
                                        stderr=subprocess.STDOUT, timeout=30)
                print(f"{optimization} {label}: exit {result.returncode}", flush=True)
                print(result.stdout, end="", flush=True)
                if label == "baseline":
                    if result.returncode != 1 or any(
                            f"f{reg} mismatch" not in result.stdout for reg in (20, 22, 31)):
                        raise SystemExit("Original V8 policy did not expose the N64 regression")
                elif result.returncode:
                    raise SystemExit(result.returncode)
    print("All source-derived V8 N64 FPR probes passed.")


if __name__ == "__main__":
    main()
