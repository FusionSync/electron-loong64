#include <dlfcn.h>
#include <errno.h>
#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/utsname.h>
#include <time.h>

static void *worker(void *opaque) {
  unsigned long *value = opaque;
  *value = 500500;
  return NULL;
}
int main(void) {
  pthread_t thread;
  unsigned long value = 0;
  if (pthread_create(&thread, NULL, worker, &value) || pthread_join(thread, NULL)) return 1;
  if (value != 500500) return 2;
  const char *libs[] = {"libglib-2.0.so.0", "libgtk-3.so.0", "libnss3.so", "libasound.so.2", "libdrm.so.2", "libX11.so.6", "libudev.so.1"};
  for (size_t i = 0; i < sizeof(libs) / sizeof(libs[0]); ++i) {
    void *module = dlopen(libs[i], RTLD_NOW | RTLD_LOCAL);
    if (!module) { fprintf(stderr, "dlopen %s: %s\n", libs[i], dlerror()); return 3; }
    dlclose(module);
  }
  FILE *stream = tmpfile();
  if (!stream) return 4;
  const char *text = "Electron MIPS64EL Buster: 中文";
  fputs(text, stream); rewind(stream);
  char buffer[256] = {0};
  fread(buffer, 1, sizeof(buffer) - 1, stream); fclose(stream);
  if (strcmp(buffer, text)) return 5;
  printf("%s; pthreads, file I/O, dlopen GTK3/GLib/NSS/ALSA/DRM/X11/udev passed\n", text);
  return 0;
}
