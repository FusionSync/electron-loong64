# Actual FFmpeg decode on the 3A4000 QEMU model

This focused test decodes real, locally generated H.264, AAC and MP3 elementary
streams with a copy of the supplied target `libffmpeg.so`. It never invokes GN
or Ninja and does not change the source tree, sysroot or build output. It is
library/QEMU validation; it does not test Electron video playback, Chromium's
media pipeline, GUI, GPU, sound output, sandbox or physical hardware.

Requirements: the prepared cross image, complete Buster runtime root, matching
Chromium FFmpeg source headers, QEMU supporting `Loongson-3A4000`, and a host
FFmpeg executable containing `libx264`, native AAC and `libmp3lame` encoders.
Use an installed host FFmpeg or supply a static x86_64 executable. The test
downloads no media or dependencies and runs offline once these inputs exist.

From a shell containing the cross compiler and target linker:

```bash
python3 tests/ffmpeg-decode/run.py \
  --source-root /work/src \
  --runtime-root /work/sysroot-buster \
  --libffmpeg /work/out/mips64el-buster/libffmpeg.so \
  --output-dir /tmp/ffmpeg-decode-result \
  --qemu /path/to/qemu-mips64el-static \
  --ffmpeg /path/to/host-ffmpeg
```

The output directory must be empty. The LLVM, sysroot and GNU linker paths
default to those in the public cross image; `--help` lists overrides. For an
isolated container, mount the work tree and recipe read-only, mount a separate
empty results directory writable, bind the two host executables read-only, and
use `--network none --cpus 1 --memory 2g --user 1000:1000`. Nothing requires the
main build container to stop.

The generator writes four known 32×32 YUV420P frames and a 0.1-second, 48 kHz
mono 440 Hz sine wave. H.264 uses QP 10 and permits B-frame reordering. AAC
uses ADTS; MP3 disables gapless metadata so elementary-stream decode has explicit
priming/padding samples. Host FFmpeg decodes the audio fixtures to float PCM
to establish sample counts and reference energy. Input padding and deliberately
split 137-byte chunks exercise the target `av_parser_*` and send/receive APIs;
the parser and decoder are both drained at EOF.

Assertions cover all four video frames, exact dimensions/pixel format, every
visible Y/U/V value against the generated pattern with a lossy tolerance,
48 kHz mono audio, exact host-reference sample count, finite bounded values,
nonzero signal and reference RMS within 0.02. The target library must expose
the real APIs and match the source header ABI version. There is no bit-exact
audio requirement across decoder versions.

A negative control sends 1024 zero bytes as H.264 and requires a real decoder
error and exit 1, with no PASS output. Its command, fixture and error log are
retained alongside the successful cases.

`result.json` records the tested library/probe/fixture hashes, tool versions,
sample counts and stdout. Commands, fixture bytes and host reference PCM stay
in the results directory. Encoder versions can change fixture bytes; the
signal and assertions remain defined by the generator. No media or static
FFmpeg binary is committed to the recipe.
