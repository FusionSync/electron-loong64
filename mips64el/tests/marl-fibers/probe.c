/* Exercise real Marl N64 contexts, including every callee-saved FPR. */
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

#include "osfiber_asm_mips64.h"

typedef void (*swap_function)(struct marl_fiber_context*,
                             const struct marl_fiber_context*);
extern void marl_fiber_swap(struct marl_fiber_context*,
                            const struct marl_fiber_context*);
extern void marl_fiber_set_target(struct marl_fiber_context*, void*, uint32_t,
                                  void (*)(void*), void*);
extern void probe_saved_fprs(struct marl_fiber_context*,
                             const struct marl_fiber_context*,
                             const uint64_t*, uint64_t*, swap_function);

static struct marl_fiber_context main_context;
static struct marl_fiber_context child_context;
static unsigned char child_stack[64 * 1024] __attribute__((aligned(16)));
static uint64_t main_seed[2][8];
static uint64_t child_seed[8];
static uint64_t main_observed[2][8];
static uint64_t child_observed[8];
static volatile unsigned pic_marker;
static unsigned child_stage;
static const uint64_t argument_cookie = UINT64_C(0x3141592653589793);

static void child_entry(void* argument) {
  /* Access PIC globals and the supplied argument before and after suspension. */
  if (argument != &argument_cookie ||
      *(const uint64_t*)argument != UINT64_C(0x3141592653589793)) {
    _Exit(2);
  }
  pic_marker += 0x123;
  child_stage = 1;
  probe_saved_fprs(&child_context, &main_context, child_seed, child_observed,
                   marl_fiber_swap);
  pic_marker += 0x456;
  child_stage = 2;
  marl_fiber_swap(&child_context, &main_context);
  /* The test never resumes this context after the final yield. */
  _Exit(3);
}

static unsigned check(const char* name, const uint64_t* expected,
                      const uint64_t* observed) {
  unsigned failures = 0;
  for (unsigned index = 0; index != 8; ++index) {
    if (expected[index] != observed[index]) {
      fprintf(stderr,
              "%s f%u mismatch: expected=%016" PRIx64 " observed=%016" PRIx64
              "\n",
              name, index + 24, expected[index], observed[index]);
      ++failures;
    }
  }
  return failures;
}

int main(void) {
  _Static_assert(sizeof(uintptr_t) == 8, "This test requires N64 pointers");
  _Static_assert(sizeof(struct marl_fiber_context) == 176,
                 "Unexpected real Marl context layout");
  for (unsigned index = 0; index != 8; ++index) {
    main_seed[0][index] = UINT64_C(0x3ff1234500000000) + index;
    main_seed[1][index] = UINT64_C(0x4006789a00000000) + index;
    child_seed[index] = UINT64_C(0x401abcdef0000000) + index;
  }
  marl_fiber_set_target(&child_context, child_stack, sizeof(child_stack),
                        child_entry, (void*)&argument_cookie);
  probe_saved_fprs(&main_context, &child_context, main_seed[0], main_observed[0],
                   marl_fiber_swap);
  if (child_stage != 1 || pic_marker != 0x123) {
    fprintf(stderr, "PIC entry or first context switch failed\n");
    return 2;
  }
  probe_saved_fprs(&main_context, &child_context, main_seed[1], main_observed[1],
                   marl_fiber_swap);
  if (child_stage != 2 || pic_marker != 0x579) {
    fprintf(stderr, "PIC resume or second context switch failed\n");
    return 2;
  }
  unsigned failures = check("main round 1", main_seed[0], main_observed[0]);
  failures += check("main round 2", main_seed[1], main_observed[1]);
  failures += check("child resume", child_seed, child_observed);
  if (failures) {
    fprintf(stderr, "%u callee-saved FPR mismatches\n", failures);
    return 1;
  }
  puts("PASS: f24-f31 preserved in three resumptions across two contexts; "
       "PIC entry and resume");
  return 0;
}
