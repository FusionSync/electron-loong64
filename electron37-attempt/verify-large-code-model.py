#!/usr/bin/env python3
"""Validate vendor old-ABI C++/Rust long calls on UOS; run in the build container."""

import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import tempfile
import time
import traceback


ROOT = Path(__file__).resolve().parent
LOGS = ROOT / "logs"
GATE = LOGS / "large-code-model-validation.json"
EXIT = LOGS / "large-code-model-validation.exit"
GNU = Path("/opt/loongson/bin")
CLANG = ROOT / "gn/clang-facade/bin/clang"
CXX = ROOT / "gn/clang-facade/bin/clang++"
RUSTC = ROOT / "tools/rust188/bin/rustc"
GAP = 160 * 1024 * 1024

STARTUP = r'''extern int call_far(void);
__attribute__((noreturn)) void _start(void) {
  register long status __asm__("$r4") = call_far();
  register long number __asm__("$r11") = 93;
  __asm__ volatile ("syscall 0" : : "r"(status), "r"(number) : "memory");
  __builtin_unreachable();
}
'''
LINK_SCRIPT = '''OUTPUT_FORMAT(elf64-loongarch)
ENTRY(_start)
PHDRS { near PT_LOAD FLAGS(5); far PT_LOAD FLAGS(5); stack PT_GNU_STACK FLAGS(6); }
SECTIONS {
 . = 0x120010000;
 .text : { startup.o(.text*) caller.o(.text*) } :near
 .rodata : { *(.rodata*) } :near
 . = 0x12a010000;
 .far : { callee.o(.text*) } :far
 /DISCARD/ : { *(.comment) *(.note*) *(.eh_frame*) }
}
'''


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main():
    LOGS.mkdir(exist_ok=True)
    # The pipeline treats this file as a completion marker. Remove an older
    # result while validation is running so a stale failure/success cannot be
    # mistaken for the current run; finally below writes the definitive code.
    try:
        EXIT.unlink()
    except FileNotFoundError:
        pass
    evidence = Path(tempfile.mkdtemp(prefix="large-code-model-", dir=ROOT))
    report = {
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "status": "running", "evidence_directory": str(evidence),
        "script_sha256": sha256(Path(__file__)), "code_model": "large",
        "scope": "Freestanding C++ and no_std Rust external calls across 160 MiB; not complete Electron or Rust std validation",
        "commands": [], "results": [],
    }
    GATE.write_text(json.dumps(report, indent=2) + "\n")
    env = os.environ.copy()
    env["PATH"] = str(ROOT / "host-runtime/bin") + ":" + env["PATH"]

    def run(argv, cwd=evidence, payload=None, timeout=120):
        argv = [str(arg) for arg in argv]
        started = time.monotonic()
        record = {"argv": argv, "cwd": str(cwd)}
        report["commands"].append(record)
        if payload is not None:
            record["stdin_sha256"] = hashlib.sha256(payload).hexdigest()
        try:
            result = subprocess.run(argv, cwd=str(cwd), env=env, input=payload,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    timeout=timeout)
            record.update(exit=result.returncode,
                          stdout=result.stdout.decode(errors="replace"),
                          stderr=result.stderr.decode(errors="replace"))
        except Exception as error:
            record.update(exit=None, error=str(error))
            raise
        finally:
            record["elapsed_seconds"] = round(time.monotonic() - started, 3)
            name = "command-{:02d}.json".format(len(report["commands"]))
            (evidence / name).write_text(json.dumps(record, indent=2) + "\n")
        result.check_returncode()
        return record["stdout"]

    success = False
    try:
        run([CXX, "--version"])
        run([RUSTC, "-vV"])
        run([GNU / "loongarch64-linux-gnu-ld", "--version"])
        tools = [ROOT / "gn/compiler-driver.py", ROOT / "tools/llvm20/bin/clang",
                 RUSTC, GNU / "loongarch64-linux-gnu-ld"]
        report["tool_sha256"] = {str(path): sha256(path) for path in tools}
        common = ["--target=loongarch64-linux-gnu", "-mabi=lp64d", "-Xclang",
                  "-mcmodel=large", "-O2", "-fPIC", "-ffunction-sections",
                  "-ffreestanding", "-fno-stack-protector", "-fno-unwind-tables",
                  "-fno-asynchronous-unwind-tables"]
        for language in ("cpp", "rust"):
            work = evidence / language
            work.mkdir()
            (work / "startup.c").write_text(STARTUP)
            (work / "far-segments.ld").write_text(LINK_SCRIPT)
            run([CLANG, *common, "-c", "startup.c", "-o", "startup.o"], work)
            if language == "cpp":
                (work / "caller.cc").write_text(
                    'int far_cpp_value(int);\nextern "C" __attribute__((noinline)) '
                    'int call_far() { return far_cpp_value(5) + 7; }\n')
                (work / "callee.cc").write_text(
                    '__attribute__((noinline)) int far_cpp_value(int x) { return x * 7; }\n')
                for name in ("caller", "callee"):
                    run([CXX, *common, "-fno-exceptions", "-fno-rtti", "-c",
                         name + ".cc", "-o", name + ".o"], work)
                far_name = "far_cpp_value(int)"
            else:
                (work / "caller.rs").write_text(
                    '#![no_std]\nunsafe extern "C" { fn far_value(x: i32) -> i32; }\n'
                    '#[no_mangle]\n#[inline(never)]\npub extern "C" fn call_far() -> i32 '
                    '{ (unsafe { far_value(5) }) + 7 }\n')
                (work / "callee.c").write_text(
                    '__attribute__((noinline)) int far_value(int x) { return x * 7; }\n')
                run([RUSTC, "--crate-name", "uos_far_call", "--crate-type=rlib",
                     "--target=loongarch64-unknown-linux-gnu", "--emit=obj",
                     "-Copt-level=2", "-Cpanic=abort", "-Crelocation-model=pic",
                     "-Ccode-model=large", "-Ccodegen-units=1", "-Cforce-unwind-tables=no",
                     "caller.rs", "-o", "caller.o"], work)
                run([CLANG, *common, "-c", "callee.c", "-o", "callee.o"], work)
                far_name = "far_value"
            run([GNU / "loongarch64-linux-gnu-ld", "-T", "far-segments.ld",
                 "-o", "probe", "startup.o", "caller.o", "callee.o"], work)
            for filename, tool_args in (
                    ("elf.txt", ["readelf", "-h", "-l", "-Ws"]),
                    ("disassembly.txt", ["objdump", "-d"]),
                    ("caller-relocations.txt", ["objdump", "-dr"])):
                target = "caller.o" if filename == "caller-relocations.txt" else "probe"
                output = run([GNU / ("loongarch64-linux-gnu-" + tool_args[0]),
                              *tool_args[1:], target], work)
                (work / filename).write_text(output)
            symbols = {}
            for line in run([GNU / "loongarch64-linux-gnu-nm", "-n", "-C", "probe"], work).splitlines():
                fields = line.split(None, 2)
                if len(fields) == 3:
                    symbols[fields[2]] = int(fields[0], 16)
            distance = symbols[far_name] - symbols["call_far"]
            raw = (work / "probe").read_bytes()
            if raw[:6] != b"\x7fELF\x02\x01" or struct.unpack_from("<H", raw, 18)[0] != 258:
                raise RuntimeError("Probe is not ELF64 little-endian LoongArch")
            if struct.unpack_from("<I", raw, 48)[0] != 3:
                raise RuntimeError("Probe does not use the UOS old ABI")
            phoff = struct.unpack_from("<Q", raw, 32)[0]
            phsize, phnum = struct.unpack_from("<HH", raw, 54)
            headers = [struct.unpack_from("<IIQQQQQQ", raw, phoff + i * phsize) for i in range(phnum)]
            loads = [header for header in headers if header[0] == 1]
            if len(loads) != 2 or loads[1][3] - loads[0][3] != GAP:
                raise RuntimeError("Probe does not have the required 160 MiB segment separation")
            if distance <= 128 * 1024 * 1024 or len(raw) >= 1024 * 1024:
                raise RuntimeError("Probe call distance or compact file size is incorrect")
            relocations = (work / "caller-relocations.txt").read_text()
            if "pcaddu18i" not in relocations or "jirl" not in relocations:
                raise RuntimeError("Caller has no expected large-model long call")
            expected_hash = hashlib.sha256(raw).hexdigest()
            remote = '''set -eu
probe_dir=$(mktemp -d /tmp/uos-large-call.XXXXXX)
trap 'rm -f "$probe_dir/probe"; rmdir "$probe_dir"' EXIT
cat > "$probe_dir/probe"
chmod 700 "$probe_dir/probe"
test "$(uname -m)" = loongarch64
actual_hash=$(sha256sum "$probe_dir/probe")
actual_hash=${actual_hash%% *}
test "$actual_hash" = EXPECTED_HASH
printf 'sha256=%s\n' "$actual_hash"
set +e
"$probe_dir/probe"
result=$?
set -e
printf 'call_result=%s\n' "$result"
test "$result" -eq 42
'''.replace("EXPECTED_HASH", expected_hash)
            ssh = [ROOT / "host-runtime/bin/ssh", "-S", ROOT.parent / ".ssh-control",
                   "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", "-p", os.environ.get("UOS_SSH_PORT", "22"),
                   f"{os.environ.get('UOS_SSH_USER', 'UOS')}@{os.environ.get('UOS_SSH_HOST', '127.0.0.1')}", remote]
            output = run(ssh, work, raw, timeout=45)
            (work / "target-execution.txt").write_text(output)
            if "sha256=" + expected_hash not in output or "call_result=42\n" not in output:
                raise RuntimeError("Target output does not confirm the expected hash and result")
            result = {"language": language, "status": "passed", "elf_flags": "0x3",
                      "binary_sha256": expected_hash, "binary_size": len(raw),
                      "caller_address": hex(symbols["call_far"]),
                      "callee_address": hex(symbols[far_name]),
                      "call_distance_bytes": distance, "segment_gap_bytes": GAP,
                      "remote_hash_match": True, "call_result": 42, "ssh_exit": 0}
            report["results"].append(result)
            print(language + ": large-model far call returned 42 on UOS", flush=True)
        success = True
        report["status"] = "passed_local_and_uos"
    except Exception:
        report["status"] = "failed"
        report["error"] = traceback.format_exc()
        print(report["error"], flush=True)
    finally:
        report["file_sha256"] = {
            str(path.relative_to(evidence)): sha256(path)
            for path in sorted(evidence.rglob("*")) if path.is_file()
        }
        manifest = evidence / "manifest.json"
        manifest.write_text(json.dumps(report, indent=2) + "\n")
        hashes = dict(report["file_sha256"])
        hashes["manifest.json"] = sha256(manifest)
        (evidence / "SHA256SUMS").write_text("".join(
            value + "  " + name + "\n" for name, value in sorted(hashes.items())))
        gate = {key: value for key, value in report.items() if key not in ("commands", "file_sha256")}
        gate["evidence_manifest_sha256"] = hashes["manifest.json"]
        GATE.write_text(json.dumps(gate, indent=2) + "\n")
        EXIT.write_text("0\n" if success else "1\n")
        print("Evidence: " + str(evidence), flush=True)
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
