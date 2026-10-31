
#define _GNU_SOURCE 1
#include <cerrno>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <csignal>
#include <sys/ptrace.h>
#include <sys/uio.h>
#include <sys/wait.h>
#include <unistd.h>
#include <elf.h>
namespace crashpad {

struct CPUContextLOONG64 {
  uint64_t regs[32];
  uint64_t csr_era;

  union {
    double dregs[32];
    struct {
      float _fp_fregs;
      uint32_t _fp_pad;
    } fregs[32];
  } fpregs;
  uint64_t fcc;
  uint32_t fcsr;
};

}
#include "snapshot/linux/signal_context.h"
#include "util/misc/capture_context.h"

// The production ReadContext and CPU initializers below are extracted verbatim
// from the patched sources. Only ProcessMemory/ProcessReaderLinux are replaced
// with local-memory adapters so the source does not require a full Chromium tree.
struct LogSink { template <typename T> LogSink& operator<<(const T&) { return *this; } };
#define LOG(x) LogSink()
namespace crashpad {
class ProcessMemory {
 public:
  uintptr_t start;
  size_t size;
  bool Read(uintptr_t address, size_t count, void* output) const {
    if (address < start || count > size || address - start > size - count)
      return false;
    memcpy(output, reinterpret_cast<void*>(address), count);
    return true;
  }
};
class ProcessReaderLinux {
 public:
  ProcessMemory memory;
  const ProcessMemory* Memory() const { return &memory; }
};
namespace internal {

void InitializeCPUContextLOONG64_NoFloatingPoint(
    const ThreadContext::t64_t& thread_context,
    CPUContextLOONG64* context) {
  static_assert(sizeof(context->regs) == sizeof(thread_context.regs),
                "gpr context size mismtach");
  memcpy(context->regs, thread_context.regs, sizeof(context->regs));
  context->csr_era = thread_context.csr_era;

  memset(&context->fpregs, 0, sizeof(context->fpregs));
  context->fcc = 0;
  context->fcsr = 0;
}
void InitializeCPUContextLOONG64_OnlyFPU(
    const FloatContext::f64_t& float_context,
    CPUContextLOONG64* context) {
  static_assert(sizeof(context->fpregs) == sizeof(float_context.fpregs),
                "fpu context size mismatch");
  memcpy(&context->fpregs, &float_context.fpregs, sizeof(context->fpregs));
  context->fcc = float_context.fcc;
  context->fcsr = float_context.fcsr;
}
static bool ReadContext(ProcessReaderLinux* reader,
                        LinuxVMAddress context_address,
                        typename ContextTraits64::CPUContext* dest_context) {
  const ProcessMemory* memory = reader->Memory();
  const LinuxVMAddress mcontext_address =
      context_address + offsetof(UContext<ContextTraits64>, mcontext);
  ContextTraits64::MContext mcontext = {};
  // The reserved extension area is not needed by the original UOS ABI.
  if (!memory->Read(mcontext_address,
                    offsetof(ContextTraits64::MContext, reserved),
                    &mcontext)) {
    LOG(ERROR) << "Couldn't read UOS signal context";
    return false;
  }

  ThreadContext::t64_t thread_context = {};
  static_assert(sizeof(thread_context.regs) == sizeof(mcontext.gregs),
                "gpr context size mismatch");
  memcpy(thread_context.regs, mcontext.gregs, sizeof(mcontext.gregs));
  thread_context.csr_era = mcontext.pc;
  InitializeCPUContextLOONG64_NoFloatingPoint(thread_context, dest_context);

  // Bit 0 is USED_FP in the UOS asm/sigcontext.h ABI. Each signal frame holds
  // a 256-bit slot per register; Crashpad's FPU context needs its low 64 bits.
  constexpr uint32_t kUsedFp = 1;
  if (mcontext.flags & kUsedFp) {
    FloatContext::f64_t float_context = {};
    for (size_t reg = 0; reg < 32; ++reg) {
      float_context.fpregs[reg] = mcontext.fpregs[reg][0];
    }
    float_context.fcc = mcontext.fcc;
    float_context.fcsr = mcontext.fcsr;
    InitializeCPUContextLOONG64_OnlyFPU(float_context, dest_context);
  }
  return true;
}

}
}
static const uint64_t fp_marker = UINT64_C(0x405edd2f1a9fbe77);
static const uint64_t gp_marker = UINT64_C(0x1122334455667788);
static volatile sig_atomic_t reader_pass;
static volatile uint64_t reader_fcsr;
static void on_signal(int, siginfo_t*, void* context) {
  crashpad::ProcessReaderLinux reader{{reinterpret_cast<uintptr_t>(context), sizeof(struct ucontext)}};
  crashpad::CPUContextLOONG64 result = {};
  const bool ok = crashpad::internal::ReadContext(&reader, reinterpret_cast<uintptr_t>(context), &result);
  uint64_t f24;
  memcpy(&f24, &result.fpregs.dregs[24], sizeof(f24));
  reader_fcsr = result.fcsr;
  reader_pass = ok && result.csr_era != 0 && result.regs[31] == gp_marker && f24 == fp_marker;
}
int main() {
  struct sigaction action = {};
  action.sa_sigaction = on_signal;
  action.sa_flags = SA_SIGINFO;
  sigemptyset(&action.sa_mask);
  if (sigaction(SIGUSR1, &action, nullptr)) return 2;
  __asm__ volatile("fld.d $f24, %0, 0\n\tmove $r31, %1"
                   : : "r"(&fp_marker), "r"(gp_marker) : "$f24", "$r31");
  if (raise(SIGUSR1)) return 3;
  printf("actual_patched_signal_reader_pass=%d fcsr=%llu\n", reader_pass, (unsigned long long)reader_fcsr);
  ucontext_t captured = {};
  __asm__ volatile("move $r31, %0" : : "r"(gp_marker) : "$r31");
  crashpad::CaptureContext(&captured);
  const bool capture_pass = captured.uc_mcontext.__pc != 0 && captured.uc_mcontext.__gregs[31] == gp_marker;
  printf("actual_patched_capture_assembly_pass=%d pc_offset=%zu gpr_offset=%zu\n", capture_pass, offsetof(ucontext_t, uc_mcontext.__pc), offsetof(ucontext_t, uc_mcontext.__gregs));
  pid_t child = fork();
  if (child < 0) return 4;
  if (child == 0) {
    if (ptrace(PTRACE_TRACEME, 0, nullptr, nullptr)) _exit(5);
    __asm__ volatile("fld.d $f24, %0, 0\n\tmove $r31, %1"
                     : : "r"(&fp_marker), "r"(gp_marker) : "$f24", "$r31");
    raise(SIGSTOP);
    _exit(0);
  }
  int status;
  if (waitpid(child, &status, 0) != child || !WIFSTOPPED(status)) return 6;
  crashpad::ThreadContext::t64_t gprs = {};
  crashpad::FloatContext::f64_t fprs = {};
  struct iovec giov = {&gprs, sizeof(gprs)};
  struct iovec fiov = {&fprs, sizeof(fprs)};
  const int grc = ptrace(PTRACE_GETREGSET, child, reinterpret_cast<void*>(NT_PRSTATUS), &giov);
  const int frc = ptrace(PTRACE_GETREGSET, child, reinterpret_cast<void*>(NT_PRFPREG), &fiov);
  const bool ptrace_pass = grc == 0 && frc == 0 && giov.iov_len == sizeof(gprs) && fiov.iov_len == sizeof(fprs) && gprs.csr_era != 0 && gprs.regs[31] == gp_marker && fprs.fpregs[24] == fp_marker;
  printf("actual_patched_ptrace_types_pass=%d gpr_bytes=%zu fpu_bytes=%zu pc_offset=%zu\n", ptrace_pass, giov.iov_len, fiov.iov_len, offsetof(crashpad::ThreadContext::t64_t, csr_era));
  ptrace(PTRACE_CONT, child, nullptr, nullptr);
  waitpid(child, &status, 0);
  return !(reader_pass && capture_pass && ptrace_pass);
}
