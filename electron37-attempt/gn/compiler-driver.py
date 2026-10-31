#!/usr/bin/env python3
"""Run vendor host tools while isolating x86_64 and UOS target compiler flags."""

import json
import os
from pathlib import Path
import shlex
import sys


ATTEMPT = Path(__file__).resolve().parent.parent
LLVM = ATTEMPT / "tools/llvm20"
RUNTIME = ATTEMPT / "host-runtime"
FACADE = ATTEMPT / "gn/clang-facade"


def expanded_arguments(arguments, stack=()):
    """Inspect GNU response files; leave the original argv untouched for Clang."""
    for argument in arguments:
        if argument.startswith("@") and len(argument) > 1:
            response = Path(argument[1:]).resolve()
            if response in stack or len(stack) >= 20:
                raise ValueError("recursive or excessively nested response file")
            with response.open() as handle:
                tokens = shlex.split(handle.read(), comments=False, posix=True)
            yield from expanded_arguments(tokens, stack + (response,))
        else:
            yield argument


def option_value(arguments, names):
    """Follow the driver's last-option-wins convention."""
    result = None
    for index, argument in enumerate(arguments):
        for name in names:
            if argument == name:
                if index + 1 == len(arguments):
                    raise ValueError("missing value after " + name)
                result = arguments[index + 1]
            elif argument.startswith(name + "="):
                result = argument[len(name) + 1:]
    return result


def rewrite_loongarch_arguments(arguments):
    """Pass Chromium's medium code model through Clang's target frontend.

    The Loongson LLVM 20 driver intentionally exposes only the small model in
    its driver option table, while its LoongArch cc1 backend accepts the
    medium model.  Chromium's LoongArch configuration emits the portable
    ``-mcmodel=medium`` spelling, so translate it only for target compilations
    and leave host tool invocations untouched.
    """
    rewritten = []
    index = 0
    while index < len(arguments):
        argument = arguments[index]
        if argument == "-mabi=lp64d":
            # This LLVM20 vendor build spells the hard-float old ABI as
            # target-abi lp64 with the fp64 feature enabled by the triple.
            rewritten.append("-mabi=lp64")
        elif argument == "-mcmodel=medium":
            rewritten += ["-Xclang", "-mcmodel=medium"]
        elif argument == "-mabi" and index + 1 < len(arguments) and arguments[index + 1] == "lp64d":
            rewritten += ["-mabi", "lp64"]
            index += 1
        elif argument == "-mcmodel" and index + 1 < len(arguments) and arguments[index + 1] == "medium":
            rewritten += ["-Xclang", "-mcmodel=medium"]
            index += 1
        else:
            rewritten.append(argument)
        index += 1
    return rewritten


def main():
    tool = Path(sys.argv[0]).name
    arguments = sys.argv[1:]
    environment = os.environ.copy()
    extra_library_path = environment.get("UOS_HOST_LIBRARY_PATH", "")
    environment["UOS_HOST_LIBRARY_PATH"] = str(LLVM / "lib") + (
        ":" + extra_library_path if extra_library_path else "")
    command = [str(RUNTIME / "bin/host-run")]
    architecture = "host-tool"

    if tool in ("clang", "clang++"):
        inspected = list(expanded_arguments(arguments))
        triple = option_value(inspected, ("--target", "-target"))
        target_sysroot = option_value(inspected, ("--sysroot", "-isysroot"))
        linker = option_value(inspected, ("-fuse-ld",))
        linker_path = option_value(inspected, ("--ld-path",))
        linking = not any(argument in inspected for argument in (
            "-c", "-S", "-E", "-fsyntax-only", "--version", "-dumpmachine",
            "-print-resource-dir", "-print-search-dirs"))
        target = triple is not None and triple.startswith("loongarch64-")
        if triple and not target and not triple.startswith("x86_64-"):
            raise ValueError("this facade supports only x86_64/loongarch64: " + triple)
        architecture = "loongarch64" if target else "x86_64"
        if target:
            arguments = rewrite_loongarch_arguments(arguments)
        # /proc/self/exe names the explicit host-runtime loader. Preserve the
        # Clang argv[0] path so spawned frontend jobs find Clang, not the loader.
        command += [str(LLVM / "bin/clang"), "-no-canonical-prefixes", "-fintegrated-cc1",
                    "-resource-dir", str(FACADE / "lib/clang/20")]
        if tool == "clang++":
            command.append("--driver-mode=g++")
        if not triple:
            command.append("--target=x86_64-unknown-linux-gnu")
        if target:
            sysroot = target_sysroot or environment.get(
                "UOS_ELECTRON_SYSROOT", str(ATTEMPT / "sysroot-complete"))
            if not target_sysroot:
                command.append("--sysroot=" + sysroot)
            command += [
                "--gcc-toolchain=/opt/loongson",
                "-B/opt/uos-target-runtime/",
                "-B" + sysroot + "/usr/lib/loongarch64-linux-gnu/",
                "-isystem", sysroot + "/usr/include/loongarch64-linux-gnu",
            ]
            if linking:
                command += [
                    "-rtlib=libgcc", "-L/opt/uos-target-runtime",
                    "-L" + sysroot + "/usr/lib/loongarch64-linux-gnu",
                    "-Wl,--dynamic-linker=/lib64/ld.so.1",
                    "-Wl,-rpath-link," + sysroot + "/usr/lib/loongarch64-linux-gnu",
                ]
            # The UOS vendor GNU ld is 2.31 and cannot relax the LoongArch
            # SOP relocations emitted by the Rust 1.88 target stdlib once
            # Electron's text layout becomes large.  Keep it as the
            # compatibility default, but allow a link-only LLD retry without
            # changing GN compile flags (and therefore without rebuilding all
            # 53k objects).  LLD 20 has already passed the UOS ABI probes.
            lld_path = environment.get("UOS_LLD_PATH", str(FACADE / "bin/ld.lld"))
            default_linker = (lld_path
                              if environment.get("UOS_FORCE_LLD") == "1"
                              else "/opt/loongson/bin/loongarch64-linux-gnu-ld")
        else:
            # Runtime snapshot libraries must never become the host compile SDK.
            if target_sysroot and ("uos-sysroot" in target_sysroot or
                                   "sysroot-complete" in target_sysroot):
                raise ValueError("refusing UOS sysroot for an x86_64 compilation")
            default_linker = "/usr/bin/ld"
        if linking and not linker_path:
            if linker == "lld":
                command.append("--ld-path=" + str(FACADE / "bin/ld.lld"))
            elif linker in (None, "bfd"):
                command.append("--ld-path=" + default_linker)
        command += arguments
    else:
        supported = {"llvm-ar", "llvm-nm", "llvm-readelf", "llvm-objcopy",
                     "llvm-objdump", "llvm-strip", "llvm-symbolizer", "ld.lld"}
        if tool not in supported:
            raise ValueError("unsupported facade tool: " + tool)
        command += [str(LLVM / "bin" / tool)] + arguments

    if environment.get("UOS_GN_WRAPPER_PRINT_COMMAND") == "1":
        print(json.dumps({"architecture": architecture, "argv": command}, indent=2))
        return 0
    os.execve(command[0], command, environment)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError) as error:
        sys.exit("compiler facade: " + str(error))
