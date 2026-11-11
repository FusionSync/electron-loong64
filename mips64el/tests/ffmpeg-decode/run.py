#!/usr/bin/env python3
"""Generate offline media and decode the actual target FFmpeg under QEMU.

Requires a host ffmpeg with libx264, native AAC and libmp3lame encoders. Source,
sysroot and the library are read-only inputs. No GN/Ninja is invoked.
"""

import argparse
import array
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys


def host_environment():
    return {name: value for name, value in os.environ.items()
            if not name.startswith("QEMU_")
            and name not in {"LD_LIBRARY_PATH", "LD_PRELOAD", "LD_AUDIT"}}


def run(command, **kwargs):
    # The prepared compiler needs its image-provided host support library path.
    # Target loader paths are supplied exclusively to QEMU below.
    return subprocess.run(command, check=True, timeout=60, **kwargs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--runtime-root", required=True, type=Path)
    parser.add_argument("--libffmpeg", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path,
                        help="Dedicated empty directory for all generated outputs")
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--qemu", default="qemu-mips64el-static")
    parser.add_argument("--llvm-root", type=Path, default=Path("/opt/llvm20"))
    parser.add_argument("--sysroot", type=Path, default=Path("/opt/mips-sysroot-buster"))
    parser.add_argument("--linker", default="/opt/mips-toolchain/usr/bin/mips64el-linux-gnuabi64-ld")
    args = parser.parse_args()
    source = args.source_root.resolve() / "third_party/ffmpeg"
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        parser.error("--output-dir must be empty")
    library = output / "libffmpeg.so"
    shutil.copyfile(args.libffmpeg.resolve(), library)
    library_hash = hashlib.sha256(library.read_bytes()).hexdigest()
    tool_version = subprocess.check_output([args.ffmpeg, "-version"], text=True)
    (output / "host-ffmpeg-version.txt").write_text(tool_version)
    qemu_version = subprocess.check_output([args.qemu, "--version"], text=True, env=host_environment())
    compiler_version = subprocess.check_output([str(args.llvm_root / "bin/clang"), "--version"],
                                               text=True)
    video = output / "video.yuv"
    video.write_bytes(b"".join(
        bytes(24 + x * 3 + y * 2 + frame * 8 for y in range(32) for x in range(32)) +
        bytes([72 + frame * 12]) * 256 + bytes([168 - frame * 9]) * 256
        for frame in range(4)))
    pcm = array.array("h", (round(8192 * math.sin(2 * math.pi * 440 * index / 48000))
                            for index in range(4800)))
    if sys.byteorder != "little":
        pcm.byteswap()
    audio = output / "audio.s16le"
    audio.write_bytes(pcm.tobytes())
    common = [args.ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error", "-y"]
    run([*common, "-f", "rawvideo", "-pix_fmt", "yuv420p", "-s", "32x32", "-r", "25",
         "-i", str(video), "-frames:v", "4", "-an", "-c:v", "libx264", "-profile:v", "high",
         "-qp", "10", "-bf", "2", "-g", "12", "-threads", "1", "-f", "h264",
         str(output / "video.h264")])
    inputs = {"h264": (output / "video.h264", 0, 0.0)}
    for codec, encoder, extension, extra in (
            ("aac", "aac", "aac", ["-f", "adts"]),
            ("mp3", "libmp3lame", "mp3", ["-write_xing", "0", "-id3v2_version", "0",
                                          "-write_id3v1", "0", "-f", "mp3"])):
        fixture = output / ("audio." + extension)
        run([*common, "-f", "s16le", "-ar", "48000", "-ac", "1", "-i", str(audio),
             "-c:a", encoder, "-b:a", "96k", "-threads", "1", *extra, str(fixture)])
        reference = output / (codec + "-reference.f32le")
        run([*common, "-i", str(fixture), "-f", "f32le", "-acodec", "pcm_f32le", str(reference)])
        values = array.array("f")
        values.frombytes(reference.read_bytes())
        if sys.byteorder != "little":
            values.byteswap()
        if not values or not all(math.isfinite(value) for value in values):
            raise SystemExit("Invalid host decoded reference")
        rms = math.sqrt(sum(value * value for value in values) / len(values))
        inputs[codec] = (fixture, len(values), rms)

    binary = output / "probe"
    command = [str(args.llvm_root / "bin/clang"), "--target=mips64el-linux-gnuabi64",
               "-mcpu=mips64r2", "-mabi=64", "-mhard-float", "-mno-msa",
               f"--sysroot={args.sysroot.resolve()}", f"--ld-path={args.linker}",
               "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror", "-fPIC", "-pie",
               "-I" + str(source), "-I" + str(source / "chromium/config/Chrome/linux/mips64el"),
               str(Path(__file__).resolve().parent / "probe.c"), "-ldl", "-lm", "-o", str(binary)]
    (output / "compile-command.json").write_text(json.dumps(command, indent=2) + "\n")
    run(command)
    # Do not leak host LD_LIBRARY_PATH/LD_PRELOAD into QEMU's host process.
    environment = host_environment()
    qemu = [args.qemu, "-cpu", "Loongson-3A4000", "-L", str(args.runtime_root.resolve()),
            "-E", "LD_LIBRARY_PATH=/lib/mips64el-linux-gnuabi64:/usr/lib/mips64el-linux-gnuabi64"]
    results = {}
    for codec, (fixture, count, rms) in inputs.items():
        target_command = [*qemu, str(binary), str(library), codec, str(fixture), str(count), str(rms)]
        result = subprocess.run(target_command, env=environment, text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=60)
        (output / (codec + "-command.json")).write_text(json.dumps(
            {"argv": target_command, "exit_code": result.returncode}, indent=2) + "\n")
        (output / (codec + ".log")).write_text(result.stdout)
        print(result.stdout, end="", flush=True)
        if result.returncode or f"{codec} PASS " not in result.stdout:
            raise SystemExit(f"{codec} actual decode failed: {result.returncode}")
        results[codec] = {"fixture_sha256": hashlib.sha256(fixture.read_bytes()).hexdigest(),
                          "fixture_bytes": fixture.stat().st_size, "host_samples": count,
                          "host_rms": rms, "stdout": result.stdout}
    invalid = output / "invalid.h264"
    invalid.write_bytes(bytes(1024))
    negative_command = [*qemu, str(binary), str(library), "h264", str(invalid), "0", "0"]
    negative = subprocess.run(negative_command, env=environment, text=True,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=60)
    (output / "invalid-h264.log").write_text(negative.stdout)
    (output / "invalid-h264-command.json").write_text(json.dumps(
        {"argv": negative_command, "exit_code": negative.returncode}, indent=2) + "\n")
    if (negative.returncode != 1 or "h264 PASS" in negative.stdout
            or "avcodec_send_packet failed" not in negative.stdout):
        raise SystemExit("Invalid H.264 negative control was not rejected by the decoder")
    print("Invalid H.264 negative control rejected as expected (exit 1).", flush=True)
    report = {"schema": 1, "status": "passed", "scope": "FFmpeg library actual decode under QEMU; no GUI/hardware claim",
              "cpu": "Loongson-3A4000", "libffmpeg_sha256": library_hash,
              "qemu_version": qemu_version.splitlines()[0],
              "compiler_version": compiler_version.splitlines()[0],
              "host_ffmpeg_version": tool_version.splitlines()[0],
              "generated_media_sha256": {name: hashlib.sha256((output / name).read_bytes()).hexdigest()
                  for name in ("video.yuv", "audio.s16le", "video.h264", "audio.aac", "audio.mp3",
                               "aac-reference.f32le", "mp3-reference.f32le", "invalid.h264")},
              "negative_control": {"exit_code": negative.returncode, "stdout": negative.stdout},
              "probe_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(), "results": results}
    (output / "result.json").write_text(json.dumps(report, indent=2) + "\n")
    print("All H.264/AAC/MP3 actual decode probes passed.")


if __name__ == "__main__":
    main()
