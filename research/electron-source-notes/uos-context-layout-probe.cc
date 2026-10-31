#include <cstddef>
#include <cstdint>
#include <signal.h>
#include <sys/ucontext.h>
#include <sys/user.h>
#include <asm/ptrace.h>
// Constants are emitted in assembly, requiring no execution on the build host.
extern "C" {
const unsigned long uos_pc_offset = offsetof(ucontext_t, uc_mcontext.__pc);
const unsigned long uos_gregs_offset = offsetof(ucontext_t, uc_mcontext.__gregs);
const unsigned long uos_glibc_fpregs_offset = offsetof(ucontext_t, uc_mcontext.__fpregs);
const unsigned long uos_kernel_fpregs_in_mcontext = offsetof(struct sigcontext, sc_fpregs);
const unsigned long uos_kernel_fcsr_in_mcontext = offsetof(struct sigcontext, sc_fcsr);
const unsigned long uos_kernel_fcc_in_mcontext = offsetof(struct sigcontext, sc_fcc);
const unsigned long uos_ptrace_pc_offset = offsetof(user_regs_struct, pc);
const unsigned long uos_kernel_ptrace_pc_offset = offsetof(user_pt_regs, csr_era);
const unsigned long uos_ptrace_context_size = sizeof(user_regs_struct);
const unsigned long uos_ptrace_fpu_size = sizeof(user_fp_state);
}
// Checks for the fixed layout actually declared by exported UOS headers.
static_assert(offsetof(ucontext_t, uc_mcontext.__pc) == 64);
static_assert(offsetof(ucontext_t, uc_mcontext.__gregs) == 72);
static_assert(offsetof(user_regs_struct, pc) == 256);
static_assert(offsetof(user_pt_regs, csr_era) == 256);
static_assert(sizeof(user_regs_struct) == sizeof(user_pt_regs));
static_assert(sizeof(user_fp_state) == 272);
