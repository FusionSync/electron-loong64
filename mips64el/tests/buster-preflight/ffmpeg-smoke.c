#include <dlfcn.h>
#include <stdio.h>
#include <stdlib.h>
int main(int argc, char **argv) {
  if (argc != 2) return 1;
  void *module = dlopen(argv[1], RTLD_NOW | RTLD_LOCAL);
  if (!module) { fprintf(stderr, "%s\n", dlerror()); return 2; }
  const char *(*version)(void) = dlsym(module, "av_version_info");
  const void *(*find)(const char *) = dlsym(module, "avcodec_find_decoder_by_name");
  void *(*allocate)(const void *) = dlsym(module, "avcodec_alloc_context3");
  int (*open_codec)(void *, const void *, void *) = dlsym(module, "avcodec_open2");
  void (*free_context)(void **) = dlsym(module, "avcodec_free_context");
  if (!version || !find || !allocate || !open_codec || !free_context) return 3;
  const char *names[] = {"h264", "aac", "mp3"};
  for (unsigned i = 0; i < sizeof(names) / sizeof(names[0]); ++i) {
    const void *codec = find(names[i]);
    if (!codec) { fprintf(stderr, "decoder missing: %s\n", names[i]); return 4; }
    void *context = allocate(codec);
    if (!context) return 5;
    if (open_codec(context, codec, NULL) < 0) { fprintf(stderr, "decoder open failed: %s\n", names[i]); return 6; }
    free_context(&context);
  }
  printf("FFmpeg %s: dynamic loading and H264/AAC/MP3 decoder initialization passed\n", version());
  dlclose(module);
  return 0;
}
