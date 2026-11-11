#!/usr/bin/env python3
"""Generate Linux MIPS64R2/N64 FFmpeg configs using Chromium's own recipe.

Run inside the MIPS cross-build image, with LLVM 20 and its host libraries on
PATH/LD_LIBRARY_PATH. Both Chromium and Chrome configurations are built, and
their actual object files determine the GN source lists. Other architectures'
generated GN data is preserved.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import types


CONFIG_FILES = (
    "config.h", "config_components.h", "config.asm", "libavutil/avconfig.h",
    "libavutil/ffversion.h", "libavcodec/bsf_list.c", "libavcodec/codec_list.c",
    "libavcodec/parser_list.c", "libavformat/demuxer_list.c",
    "libavformat/muxer_list.c", "libavformat/protocol_list.c",
)
IMPORT = '''
# Linux MIPS64R2/N64 configurations generated from this FFmpeg revision.
if (use_linux_config && current_cpu == "mips64el") {
  import("ffmpeg_mips64el_generated.gni")
  ffmpeg_c_sources = []
  ffmpeg_gas_sources = []
  ffmpeg_asm_sources = []
  ffmpeg_c_sources = mips64el_ffmpeg_c_sources
  ffmpeg_gas_sources = mips64el_ffmpeg_gas_sources
  ffmpeg_asm_sources = mips64el_ffmpeg_asm_sources
}
'''


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_root", type=Path)
    parser.add_argument("--sysroot", type=Path,
                        default=Path(os.environ.get("MIPS64EL_SYSROOT", "/opt/mips-sysroot")))
    parser.add_argument("--llvm", type=Path, default=Path("/opt/llvm20"))
    parser.add_argument("--jobs", type=int, default=2)
    parser.add_argument("--reuse-build", action="store_true",
                        help="reuse successful build directories from this exact recipe")
    parser.add_argument("--ffmpeg-revision",
                        help="revision recorded by the host when Git worktree metadata is not mounted")
    parser.add_argument("--export-dir", type=Path,
                        help="also copy the generated source/config files here")
    args = parser.parse_args()
    root = args.source_root.resolve()
    ffmpeg = root / "third_party/ffmpeg"
    scripts = root / "media/ffmpeg/scripts"
    if not (ffmpeg / "configure").is_file():
        parser.error("source_root must contain third_party/ffmpeg/configure")
    if args.jobs < 1:
        parser.error("--jobs must be positive")
    llvm = args.llvm.resolve()
    sysroot = args.sysroot.resolve()
    os.environ["PATH"] = str(llvm / "bin") + os.pathsep + os.environ["PATH"]

    # The roll tooling's constructor demands an upstream LLVM installation and
    # every supported host build. Supply only its path provider; all codec flags,
    # configure rewrites, and object filtering still come from the pinned source.
    class Configuration:
        def ffmpeg_src(self):
            return str(ffmpeg)

        def ffmpeg_home(self):
            return str(ffmpeg)

        def chrome_src(self):
            return str(root)

        def target_config_directory(self, arch, operating_system, branding):
            return str(ffmpeg / f"build.{arch}.{operating_system}" / branding)

    robo = types.ModuleType("robo_lib")
    robo.config = types.SimpleNamespace(RoboConfiguration=Configuration)
    sys.modules["robo_lib"] = robo
    sys.path.insert(0, str(scripts))
    build = load_module("mips64el_build_ffmpeg", scripts / "build_ffmpeg.py")
    generate = load_module("mips64el_generate_ffmpeg_gn", scripts / "generate_gn.py")

    # Override the roll script's default in-tree sysroot. GNU ld is deliberate:
    # the Bullseye MIPS glibc CRT objects have executable-stack notes rejected by
    # LLD 20. This does not alter the final Chromium linker's selection.
    configure_args = [
        f"--sysroot={sysroot}",
        f"--cc={llvm / 'bin/clang'}",
        f"--cxx={llvm / 'bin/clang++'}",
        f"--ld={llvm / 'bin/clang'}",
        f"--ar={llvm / 'bin/llvm-ar'}",
        f"--nm={llvm / 'bin/llvm-nm'}",
        f"--ranlib={llvm / 'bin/llvm-ranlib'}",
        "--extra-cflags=-mabi=64 -mhard-float",
        "--extra-ldflags=-mabi=64 -mhard-float -fuse-ld=bfd",
        "--disable-msa", "--disable-mmi", "--disable-mips64r6",
    ]
    options = types.SimpleNamespace(brandings=None, config_only=False, fast=args.reuse_build)
    build.ConfigureAndBuild("mips64el", "linux", "linux", "x64",
                            args.jobs, configure_args, options)

    source_mapping = generate.GetObjectToSourceMapping(generate.GetSourceFiles(str(ffmpeg)))
    source_lists = {}
    generated_paths = []
    for branding in ("Chromium", "Chrome"):
        build_dir = ffmpeg / "build.mips64el.linux" / branding
        config = (build_dir / "config.h").read_text()
        expected = {
            "ARCH_MIPS": "1", "HAVE_MIPS64R2": "1", "HAVE_MIPS64R6": "0",
            "HAVE_MSA": "0", "HAVE_MMI": "0", "HAVE_BIGENDIAN": "0",
        }
        for name, value in expected.items():
            if f"#define {name} {value}\n" not in config:
                raise SystemExit(f"unexpected {branding} target config: {name} != {value}")
        destination = ffmpeg / "chromium/config" / branding / "linux/mips64el"
        for relative in CONFIG_FILES:
            source = build_dir / relative
            if source.is_file():
                target = destination / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
                generated_paths.append(target.relative_to(ffmpeg))
        objects = generate.GetObjectFiles(str(build_dir))
        sources = generate.GetSourceFileSet(source_mapping, objects)
        # Chromium already carries basename-collision wrappers for common files.
        # Reuse those wrappers instead of introducing duplicate archive names.
        renamed = set()
        for source in sources:
            wrapper = Path(source).parent / ("autorename_" + source.replace("/", "_"))
            renamed.add(str(wrapper) if (ffmpeg / wrapper).is_file() else source)
        if not renamed:
            raise SystemExit(f"no object-derived source list for {branding}")
        source_lists[branding] = sorted(renamed)

    lines = [
        "# Generated by mips64el/scripts/generate-ffmpeg.py from compiled objects.",
        "# Linux little-endian MIPS64R2, N64 hard-float, without MSA/MMI.",
        'import("ffmpeg_options.gni")',
    ]
    for index, branding in enumerate(("Chromium", "Chrome")):
        lines.append(('if' if index == 0 else '} else if') +
                     f' (ffmpeg_branding == "{branding}") {{')
        for variable, extension in (("ffmpeg_c_sources", ".c"),
                                    ("ffmpeg_gas_sources", ".S"),
                                    ("ffmpeg_asm_sources", ".asm")):
            lines.append(f"  mips64el_{variable} = [")
            lines.extend(f'    "{source}",' for source in source_lists[branding]
                         if source.endswith(extension))
            lines.append("  ]")
    lines.extend(["}", ""])
    generated_gni = ffmpeg / "ffmpeg_mips64el_generated.gni"
    generated_gni.write_text("\n".join(lines))
    subprocess.run([str(root / "buildtools/linux64/gn"), "format", str(generated_gni)], check=True)
    generated_paths.append(generated_gni.relative_to(ffmpeg))
    original_gni = ffmpeg / "ffmpeg_generated.gni"
    original_text = original_gni.read_text()
    if 'import("ffmpeg_mips64el_generated.gni")' not in original_text:
        original_gni.write_text(original_text + IMPORT)
    else:
        original_text = original_text.removesuffix(IMPORT)
    manifest = {
        "ffmpeg_revision": args.ffmpeg_revision or subprocess.check_output(
            ["git", "-C", str(ffmpeg), "rev-parse", "HEAD"], text=True).strip(),
        "compiler": subprocess.check_output(
            [str(llvm / "bin/clang"), "--version"], text=True).splitlines()[0],
        "target": "mips64el-linux-gnuabi64",
        "isa": "mips64r2", "abi": "n64", "float": "hard", "msa": False,
        "source_counts": {branding: len(sources) for branding, sources in source_lists.items()},
        "files": [str(path) for path in sorted(generated_paths)],
        "baseline_sha256": {
            "configure": hashlib.sha256((ffmpeg / "configure").read_bytes()).hexdigest(),
            "ffmpeg_generated.gni": hashlib.sha256(original_text.encode()).hexdigest(),
        },
        "file_sha256": {
            str(path): hashlib.sha256((ffmpeg / path).read_bytes()).hexdigest()
            for path in sorted(generated_paths)
        },
    }
    if args.export_dir:
        export = args.export_dir.resolve()
        export.mkdir(parents=True, exist_ok=True)
        for relative in generated_paths:
            target = export / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ffmpeg / relative, target)
        (export / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
