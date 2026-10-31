#include <stdio.h>
#include <gtk/gtk.h>
#include <nss.h>
#include <gbm.h>
#include <xf86drm.h>
#include <alsa/asoundlib.h>
#include <cups/cups.h>
#include <X11/Xlib.h>
#include <xkbcommon/xkbcommon.h>
#include <dbus/dbus.h>

int main(void) {
    const char *mismatch = glib_check_version(GLIB_MAJOR_VERSION,
                                             GLIB_MINOR_VERSION,
                                             GLIB_MICRO_VERSION);
    if (mismatch) {
        fprintf(stderr, "GLib runtime mismatch: %s\n", mismatch);
        return 1;
    }
    printf("GTK %u.%u.%u GLib %u.%u.%u NSS %s ALSA %s\n",
           gtk_get_major_version(), gtk_get_minor_version(), gtk_get_micro_version(),
           glib_major_version, glib_minor_version, glib_micro_version,
           NSS_GetVersion(), snd_asoundlib_version());
    printf("Resolved GBM/DRM/CUPS/X11/XKB/DBus functions: %p %p %p %p %p %p\n",
           (void *)gbm_create_device, (void *)drmGetVersion,
           (void *)cupsGetDefault, (void *)XOpenDisplay,
           (void *)xkb_context_new, (void *)dbus_get_version);
    puts("UOS desktop development headers and target runtime libraries passed");
    return 0;
}
