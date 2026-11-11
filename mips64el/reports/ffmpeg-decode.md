# Actual H.264/AAC/MP3 decode under QEMU

**Passed on 2026-11-10.** The current main build's target `libffmpeg.so`
successfully decoded locally generated elementary streams under QEMU's
`Loongson-3A4000` CPU model and the complete Buster GLIBC 2.28 root. This extends
the earlier decoder-initialization check to real parser, decoder, frame and
sample execution. It does not establish completion of the Electron build.

This check covers the FFmpeg shared library under QEMU. It does not cover
Electron/Chromium media playback, GUI, GPU, audio-device output, sandbox,
hardware acceleration or physical-machine compatibility.

The [public test](../tests/ffmpeg-decode/README.md) copies the supplied library
to a dedicated results directory, compiles a small C probe against the actual
source headers, resolves real `av_parser_*` and send/receive exports, and checks
the header/library ABI versions. Source, sysroot and main output were mounted
read-only. The independent container had networking disabled, one CPU and a
2 GiB memory limit; GN and Ninja were not invoked.

| Input | Actual decoded result | Assertions |
| --- | --- | --- |
| H.264, 847 bytes | 4 frames, 32×32 YUV420P; pattern MSE 5.725911 | Exact frame count and dimensions; every visible Y/U/V value within 16 of the generated pattern; aggregate MSE ≤ 16 |
| AAC ADTS, 1702 bytes | 6 frames, 6144 samples, 48 kHz mono; RMS 0.155823 | Exact host-reference sample count; finite bounded signal, 4676 samples above absolute amplitude 0.01; reference RMS difference ≤ 0.02 |
| MP3, 1728 bytes | 6 frames, 6912 samples, 48 kHz mono; RMS 0.139954 | Exact host-reference sample count; finite bounded signal, 4664 samples above absolute amplitude 0.01; reference RMS difference ≤ 0.02 |

The raw input is four known YUV frames and a 0.1-second, 440 Hz sine wave.
All media were generated locally; no external media fixture was downloaded.
AAC priming and MP3 padding account for decoded sample counts exceeding the
4800 input samples. MP3 Xing/ID3 metadata is disabled to keep elementary-stream
and host-reference sample counting consistent. The target parser receives
137-byte chunks, then both parser and decoder are drained at EOF.

Tools and identity:

- Target library: FFmpeg `7.1.git`; libavcodec version integer `4063590`,
  libavutil `3932772`; both equal the actual source-header versions.
- Compiler: LoongNix Clang 20.1.8, MIPS64R2/N64 hard-float, no MSA.
  Probe ELF reports no ISA extensions or ASEs.
- Runtime: QEMU 8.2.2, Debian build `1:8.2.2+ds-0ubuntu1.18`, CPU
  `Loongson-3A4000`; the complete Buster root supplies GLIBC 2.28.
- Host fixture generator/reference decoder: FFmpeg `7.0.2-static` from
  `https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz`.
  Downloaded archive SHA256:
  `abda8d77ce8309141f83ab8edf0596834087c52467f6badf376a6a2a4c87cf67`.
  The generator executable is not included in this repository.
- Target `libffmpeg.so` SHA256:
  `fcc85f2b95476eee96dc053e32ece59b51494cf438bacd5d2b25f9b8ae3ecae8`.
  This matched the main build library after the run. Its highest required
  GLIBC symbol version is 2.28.
- Target probe SHA256:
  `498fd74854903c32193aa6b19eec977200e8619d9dd28decc28b08a25c2175d1`.

All generated-media SHA256 values from the recorded run:

```text
f59c3c461f832b3a1a1a8198ab3e3ad8752c41e8a214e1da8f898bfc1d770a72  video.yuv
78ca5f08413b02078dc30320fa12d87e7fd1ae47416f797e261bb26b73447749  audio.s16le
e7473359ef84d4f97ee386a93ed96d8d39f250063865da319b839675144aa93c  video.h264
70b4bf07fe6ccd0bf9cd23d3e2f01f199b33feb5c101a616155c4c3926970871  audio.aac
6c2d3888492aacea806d45a4c633a9bd0942b4527724b0511b3df830e8eca7ab  audio.mp3
347d6ee34c0bdda2397dfbdc2705751e4722f5aef47697ebc2d2f8d557d924b6  aac-reference.f32le
15833dbe5bbb82213bb88d3d9126dc8c83eee3502c3699466aed55a5c7cdd319  mp3-reference.f32le
```

A negative control supplied 1024 zero bytes as H.264 input to the same probe
and library. The real decoder reported `No start code is found` and
`Error splitting the input into NAL units`; the probe exited 1 at
`avcodec_send_packet failed (-1094995529)` and emitted no PASS result.
Negative fixture SHA256:
`5f70bf18a086007016e948b04aed3b82103a36bea41755b6cddfaf10ace3c6ef`.

The results directory records JSON, exact commands, fixture bytes, reference
PCM and stdout. The public runner records the generator version and fixture
hashes so future runs can distinguish encoder changes from target failures.
It uses tolerances for lossy decoded content, with no cross-version bit-exact
audio requirement.
