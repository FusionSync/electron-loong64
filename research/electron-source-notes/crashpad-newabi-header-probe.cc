// Reproduces fields required by electron-loong64 37.2.5 Crashpad patch.
#include <cstddef>
#include <sys/ucontext.h>
#include <asm/sigcontext.h>
constexpr auto extcontext_offset = offsetof(ucontext_t, uc_mcontext.__extcontext);
constexpr auto fpu_magic = FPU_CTX_MAGIC;
static_assert(sizeof(struct sctx_info) > 0, "sctx_info must be available");
