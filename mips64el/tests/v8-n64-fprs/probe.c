/* Source-derived V8 register envelopes; the runner supplies the assembly. */
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>

extern void probe_callee(const uint64_t*, uint64_t*);
extern void probe_caller(const uint64_t*, uint64_t*, void (*)(void));

/* f20 and f22 are caller-saved in N64. Let the real C compiler enforce that
 * convention; an N32 compiler would have to preserve these clobbers. */
__attribute__((noinline)) static void native_callback(void) {
  __asm__ volatile("dmtc1 $zero, $f20\n\tdmtc1 $zero, $f22"
                   :
                   :
                   : "$f20", "$f22");
}

static unsigned check(const char* name, const uint64_t* expected,
                      const uint64_t* observed, unsigned count,
                      unsigned first_register, unsigned step) {
  unsigned failures = 0;
  for (unsigned index = 0; index != count; ++index) {
    if (expected[index] != observed[index]) {
      fprintf(stderr,
              "%s f%u mismatch: expected=%016" PRIx64 " observed=%016" PRIx64
              "\n",
              name, first_register + index * step, expected[index],
              observed[index]);
      ++failures;
    }
  }
  return failures;
}

int main(void) {
  _Static_assert(sizeof(uintptr_t) == 8, "This test requires N64 pointers");
#if _MIPS_SIM != _ABI64 || !defined(__mips_hard_float)
#error This test requires the N64 hard-float ABI
#endif
  uint64_t callee_seed[8], callee_observed[8];
  uint64_t caller_seed[12], caller_observed[12];
  for (unsigned index = 0; index != 8; ++index) {
    callee_seed[index] = UINT64_C(0x3ff1234500000000) + index;
  }
  for (unsigned index = 0; index != 12; ++index) {
    caller_seed[index] = UINT64_C(0x4006789a00000000) + index;
  }
  probe_callee(callee_seed, callee_observed);
  probe_caller(caller_seed, caller_observed, native_callback);
  unsigned failures = check("C-to-V8 entry", callee_seed, callee_observed,
                             8, 24, 1);
  failures += check("V8-to-C caller save", caller_seed, caller_observed,
                    12, 0, 2);
  if (failures) {
    fprintf(stderr, "%u N64 FPR mismatches\n", failures);
    return 1;
  }
  puts("PASS: N64 f24-f31 entry preservation and allocatable caller FPRs");
  return 0;
}
