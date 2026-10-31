#include <curl/curl.h>
#include <stddef.h>

_Static_assert(LIBCURL_VERSION_NUM == 0x074001, "curl header version");
_Static_assert(sizeof(void*) == 8, "LoongArch LP64 pointers");
_Static_assert(sizeof(long) == 8, "LoongArch LP64 long");
_Static_assert(sizeof(curl_off_t) == 8, "curl offset ABI");
_Static_assert(sizeof(curl_socklen_t) == 4, "curl socket length ABI");
_Static_assert(sizeof(struct curl_slist) == 16, "curl list ABI");
_Static_assert(offsetof(struct curl_slist, next) == 8, "curl list pointer offset");
