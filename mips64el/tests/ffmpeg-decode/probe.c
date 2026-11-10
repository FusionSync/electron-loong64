/* Decode generated elementary streams through the actual Chromium FFmpeg SO. */
#include <dlfcn.h>
#include <errno.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "libavcodec/avcodec.h"
#include "libavutil/frame.h"
#include "libavutil/version.h"

#define APIS(X) \
  X(av_version_info) X(avcodec_version) X(avutil_version) \
  X(avcodec_find_decoder_by_name) X(avcodec_alloc_context3) \
  X(avcodec_open2) X(avcodec_free_context) X(av_parser_init) \
  X(av_parser_parse2) X(av_parser_close) X(avcodec_send_packet) \
  X(avcodec_receive_frame) X(av_frame_alloc) X(av_frame_unref) \
  X(av_frame_free) X(av_packet_alloc) X(av_packet_unref) X(av_packet_free)
#define DECLARE(name) static __typeof__(&name) p_##name;
APIS(DECLARE)

static int frames;
static int64_t samples;
static double energy, video_error;
static int nonzero;
static const char *decoder;

static void fail(const char *message, int result) {
  fprintf(stderr, "%s: %s (%d)\n", decoder, message, result);
  exit(1);
}

static double sample_at(const AVFrame *frame, int index) {
  /* Fixtures are mono, so packed and planar indexing is identical. */
  const void *data = frame->extended_data[0];
  switch (frame->format) {
    case AV_SAMPLE_FMT_FLT: case AV_SAMPLE_FMT_FLTP:
      return ((const float *)data)[index];
    case AV_SAMPLE_FMT_DBL: case AV_SAMPLE_FMT_DBLP:
      return ((const double *)data)[index];
    case AV_SAMPLE_FMT_S16: case AV_SAMPLE_FMT_S16P:
      return ((const int16_t *)data)[index] / 32768.0;
    case AV_SAMPLE_FMT_S32: case AV_SAMPLE_FMT_S32P:
      return ((const int32_t *)data)[index] / 2147483648.0;
    default: fail("unexpected audio sample format", frame->format);
  }
  return 0;
}

static void inspect_frame(const AVFrame *frame) {
  if (!strcmp(decoder, "h264")) {
    if (frame->width != 32 || frame->height != 32 ||
        frame->format != AV_PIX_FMT_YUV420P || frames >= 4)
      fail("unexpected video dimensions, format or frame count", frame->format);
    for (int plane = 0; plane < 3; ++plane) {
      const int size = plane == 0 ? 32 : 16;
      for (int y = 0; y < size; ++y) {
        for (int x = 0; x < size; ++x) {
          const int expected = plane == 0 ? 24 + x * 3 + y * 2 + frames * 8 :
                               plane == 1 ? 72 + frames * 12 : 168 - frames * 9;
          const int value = frame->data[plane][y * frame->linesize[plane] + x];
          const double error = value - expected;
          video_error += error * error;
          if (fabs(error) > 16) fail("decoded video differs from generated pattern", value);
        }
      }
    }
  } else {
    if (frame->sample_rate != 48000 || frame->ch_layout.nb_channels != 1 ||
        frame->nb_samples <= 0 || !frame->extended_data || !frame->extended_data[0])
      fail("unexpected audio rate, layout or samples", frame->nb_samples);
    for (int index = 0; index < frame->nb_samples; ++index) {
      const double value = sample_at(frame, index);
      if (!isfinite(value) || fabs(value) > 1.2)
        fail("non-finite or excessive decoded audio", index);
      energy += value * value;
      nonzero += fabs(value) > 0.01;
    }
    samples += frame->nb_samples;
  }
  ++frames;
}

static int receive_frames(AVCodecContext *context, AVFrame *frame) {
  int result;
  while ((result = p_avcodec_receive_frame(context, frame)) == 0) {
    inspect_frame(frame);
    p_av_frame_unref(frame);
  }
  if (result != AVERROR(EAGAIN) && result != AVERROR_EOF)
    fail("avcodec_receive_frame failed", result);
  return result;
}

static void send(AVCodecContext *context, AVFrame *frame, AVPacket *packet) {
  int result = p_avcodec_send_packet(context, packet);
  if (result == AVERROR(EAGAIN)) {
    receive_frames(context, frame);
    result = p_avcodec_send_packet(context, packet);
  }
  if (result < 0) fail("avcodec_send_packet failed", result);
  const int received = receive_frames(context, frame);
  if (!packet && received != AVERROR_EOF)
    fail("decoder did not reach EOF after drain", received);
}

int main(int argc, char **argv) {
  if (argc != 6) {
    fprintf(stderr, "usage: probe libffmpeg.so decoder fixture expected_samples expected_rms\n");
    return 2;
  }
  decoder = argv[2];
  if (strcmp(decoder, "h264") && strcmp(decoder, "aac") && strcmp(decoder, "mp3"))
    fail("unsupported probe decoder", 0);
  void *library = dlopen(argv[1], RTLD_NOW | RTLD_LOCAL);
  if (!library) { fprintf(stderr, "%s\n", dlerror()); return 2; }
#define RESOLVE(name) do { \
    *(void **)(&p_##name) = dlsym(library, #name); \
    if (!p_##name) fail("missing " #name, 0); \
  } while (0);
  APIS(RESOLVE)
  if (p_avcodec_version() != LIBAVCODEC_VERSION_INT ||
      p_avutil_version() != LIBAVUTIL_VERSION_INT)
    fail("source headers do not match FFmpeg library ABI version", 0);

  FILE *input = fopen(argv[3], "rb");
  if (!input || fseek(input, 0, SEEK_END)) fail("cannot open fixture", errno);
  long length = ftell(input);
  if (length <= 0 || length > 1024 * 1024 || fseek(input, 0, SEEK_SET))
    fail("invalid fixture length", 0);
  uint8_t *buffer = calloc(1, length + AV_INPUT_BUFFER_PADDING_SIZE);
  if (!buffer || fread(buffer, 1, length, input) != (size_t)length)
    fail("cannot read padded fixture", errno);
  fclose(input);
  const AVCodec *codec = p_avcodec_find_decoder_by_name(decoder);
  if (!codec) fail("decoder missing", 0);
  AVCodecContext *context = p_avcodec_alloc_context3(codec);
  AVCodecParserContext *parser = p_av_parser_init(codec->id);
  AVFrame *frame = p_av_frame_alloc();
  AVPacket *packet = p_av_packet_alloc();
  if (!context || !parser || !frame || !packet) fail("allocation failed", 0);
  context->thread_count = 1;
  int result = p_avcodec_open2(context, codec, NULL);
  if (result < 0) fail("avcodec_open2 failed", result);

  int64_t offset = 0;
  int iterations = 0;
  while (offset < length) {
    int remaining = length - offset;
    if (remaining > 137) remaining = 137; /* Deliberately split packet boundaries. */
    result = p_av_parser_parse2(parser, context, &packet->data, &packet->size,
                               buffer + offset, remaining, AV_NOPTS_VALUE,
                               AV_NOPTS_VALUE, offset);
    if (result < 0 || ++iterations > 100000 || (!result && !packet->size))
      fail("parser failed or stalled", result);
    offset += result;
    if (packet->size) send(context, frame, packet);
    p_av_packet_unref(packet);
  }
  result = p_av_parser_parse2(parser, context, &packet->data, &packet->size,
                             NULL, 0, AV_NOPTS_VALUE, AV_NOPTS_VALUE, offset);
  if (result < 0) fail("parser drain failed", result);
  if (packet->size) send(context, frame, packet);
  p_av_packet_unref(packet);
  send(context, frame, NULL);

  if (!strcmp(decoder, "h264")) {
    double mse = video_error / (4 * (32 * 32 + 2 * 16 * 16));
    if (frames != 4 || mse > 16) fail("video frame count or pattern MSE failed", frames);
    printf("h264 PASS frames=%d dimensions=32x32 format=yuv420p pattern_mse=%.6f\n", frames, mse);
  } else {
    const int64_t expected_samples = strtoll(argv[4], NULL, 10);
    const double expected_rms = strtod(argv[5], NULL);
    const double rms = samples ? sqrt(energy / samples) : 0;
    if (frames < 2 || samples != expected_samples || expected_samples < 4096 ||
        expected_samples > 8192 || rms < 0.05 || rms > 0.4 ||
        fabs(rms - expected_rms) > 0.02 || nonzero < 3000)
      fail("audio sample count, energy or host-reference RMS failed", (int)samples);
    printf("%s PASS frames=%d samples=%lld rate=48000 channels=1 rms=%.6f nonzero=%d\n",
           decoder, frames, (long long)samples, rms, nonzero);
  }
  printf("FFmpeg %s source-matching libavcodec=%u libavutil=%u\n",
         p_av_version_info(), p_avcodec_version(), p_avutil_version());
  p_av_packet_free(&packet);
  p_av_frame_free(&frame);
  p_av_parser_close(parser);
  p_avcodec_free_context(&context);
  free(buffer);
  dlclose(library);
  return 0;
}
