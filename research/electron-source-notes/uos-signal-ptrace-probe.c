#define _GNU_SOURCE
#include <errno.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stddef.h>
#include <sys/ptrace.h>
#include <sys/uio.h>
#include <sys/user.h>
#include <sys/wait.h>
#include <unistd.h>
#include <elf.h>
#include <asm/ptrace.h>
#include <asm/ucontext.h>

static const uint64_t fp_marker = UINT64_C(0x405edd2f1a9fbe77);
static const uint64_t gp_marker = UINT64_C(0x1122334455667788);
static volatile sig_atomic_t signal_seen;
static volatile uint64_t observed[6];
static void on_signal(int signum, siginfo_t *info, void *opaque) {
  (void)signum; (void)info;
  struct ucontext *kernel_context = (struct ucontext *)opaque;
  ucontext_t *libc_context = (ucontext_t *)opaque;
  observed[0] = kernel_context->uc_mcontext.sc_pc;
  observed[1] = kernel_context->uc_mcontext.sc_regs[31];
  observed[2] = kernel_context->uc_mcontext.sc_fpregs[24].val64[0];
  observed[3] = libc_context->uc_mcontext.__fpregs[24].__val64[0];
  observed[4] = kernel_context->uc_mcontext.sc_regs[3];
  observed[5] = kernel_context->uc_mcontext.sc_flags;
  signal_seen = 1;
}
static void load_markers(void) {
  __asm__ volatile("fld.d $f24, %0, 0\n\tmove $r31, %1"
                   : : "r"(&fp_marker), "r"(gp_marker) : "$f24", "$r31");
}
int main(void) {
  struct sigaction action;
  memset(&action, 0, sizeof(action));
  action.sa_sigaction = on_signal;
  action.sa_flags = SA_SIGINFO;
  sigemptyset(&action.sa_mask);
  if (sigaction(SIGUSR1, &action, NULL)) { perror("sigaction"); return 2; }
  // Keep markers live across raise; both registers are callee-saved.
  __asm__ volatile("fld.d $f24, %0, 0\n\tmove $r31, %1"
                   : : "r"(&fp_marker), "r"(gp_marker) : "$f24", "$r31");
  if (raise(SIGUSR1)) { perror("raise"); return 3; }
  printf("signal_seen=%d signal_pc_nonzero=%d signal_sp_nonzero=%d\n", signal_seen, observed[0] != 0, observed[4] != 0);
  printf("signal_gpr31_match=%d signal_kernel_f24_match=%d signal_glibc_f24_match=%d signal_flags=%llu\n", observed[1] == gp_marker, observed[2] == fp_marker, observed[3] == fp_marker, (unsigned long long)observed[5]);
  printf("kernel_pc_offset=%zu kernel_gprs_offset=%zu kernel_fpu_offset=%zu libc_fpu_offset=%zu kernel_sigmask_offset=%zu libc_sigmask_offset=%zu\n", offsetof(struct ucontext, uc_mcontext.sc_pc), offsetof(struct ucontext, uc_mcontext.sc_regs), offsetof(struct ucontext, uc_mcontext.sc_fpregs), offsetof(ucontext_t, uc_mcontext.__fpregs), offsetof(struct ucontext, uc_sigmask), offsetof(ucontext_t, uc_sigmask));
  pid_t child = fork();
  if (child < 0) { perror("fork"); return 4; }
  if (child == 0) {
    if (ptrace(PTRACE_TRACEME, 0, NULL, NULL)) _exit(5);
    __asm__ volatile("fld.d $f24, %0, 0\n\tmove $r31, %1"
                     : : "r"(&fp_marker), "r"(gp_marker) : "$f24", "$r31");
    raise(SIGSTOP);
    _exit(0);
  }
  int status;
  if (waitpid(child, &status, 0) != child || !WIFSTOPPED(status)) { perror("waitpid"); return 6; }
  struct user_pt_regs gprs;
  struct user_fp_state fprs;
  memset(&gprs, 0, sizeof(gprs)); memset(&fprs, 0, sizeof(fprs));
  struct iovec giov = { &gprs, sizeof(gprs) };
  struct iovec fiov = { &fprs, sizeof(fprs) };
  int grc = ptrace(PTRACE_GETREGSET, child, (void *)(uintptr_t)NT_PRSTATUS, &giov);
  int gerr = errno;
  int frc = ptrace(PTRACE_GETREGSET, child, (void *)(uintptr_t)NT_PRFPREG, &fiov);
  int ferr = errno;
  printf("ptrace_gpr_result=%d errno=%d bytes=%zu pc_nonzero=%d gpr31_match=%d pc_offset=%zu\n", grc, grc ? gerr : 0, giov.iov_len, gprs.csr_era != 0, gprs.regs[31] == gp_marker, offsetof(struct user_pt_regs, csr_era));
  printf("ptrace_fpu_result=%d errno=%d bytes=%zu f24_match=%d\n", frc, frc ? ferr : 0, fiov.iov_len, fprs.fpr[24] == fp_marker);
  ptrace(PTRACE_CONT, child, NULL, NULL);
  waitpid(child, &status, 0);
  return !(signal_seen && observed[1] == gp_marker && observed[2] == fp_marker && grc == 0 && frc == 0 && gprs.regs[31] == gp_marker && fprs.fpr[24] == fp_marker);
}
