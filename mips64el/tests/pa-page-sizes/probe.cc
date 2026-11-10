// Check the real PartitionAlloc headers, using generated target build flags.
#include <cstdio>
#include <unistd.h>

#include "partition_alloc/partition_page_constants.h"

#if !PA_BUILDFLAG(PA_ARCH_CPU_MIPS64EL)
#error This probe must be compiled for MIPS64EL.
#endif
#ifndef PARTITION_ALLOCATOR_CONSTANTS_POSIX_NONCONST_PAGE_SIZE
#error Linux MIPS64EL must use runtime page sizes.
#endif

// Supply the cache storage normally defined in partition_address_space.cc;
// the allocator implementation itself is not needed to test these headers.
namespace partition_alloc::internal {
PageCharacteristics page_characteristics;
}

#ifdef PROBE_PAGE_SIZE
extern "C" int __wrap_getpagesize(void) {
  return PROBE_PAGE_SIZE;
}
#endif

int main() {
  using namespace partition_alloc::internal;
#ifdef PROBE_PAGE_SIZE
  const size_t expected = PROBE_PAGE_SIZE;
#else
  const size_t expected = static_cast<size_t>(getpagesize());
#endif
  const size_t actual = PageAllocationGranularity();
  const size_t shift = PageAllocationGranularityShift();
  const size_t partition_shift = PartitionPageShift();
  const size_t partition_size = PartitionPageSize();
  std::printf("page=%zu shift=%zu partition=%zu partition_shift=%zu "
              "slots_limit=%zu\n",
              actual, shift, partition_size, partition_shift,
              kMaxSlotsPerSlotSpan);
  if (actual != expected || SystemPageSize() != expected ||
      (size_t{1} << shift) != expected)
    return 1;
  if (partition_shift != shift + 2 || partition_size != expected * 4)
    return 2;
  if (NumSystemPagesPerPartitionPage() != 4 ||
      kMaxSlotsPerSlotSpan <
          partition_size / partition_alloc::BucketIndexLookup::kMinBucketSize)
    return 3;
  if (PageAllocationGranularity() != actual ||
      PageAllocationGranularityShift() != shift ||
      page_characteristics.size.load(std::memory_order_relaxed) != expected ||
      page_characteristics.shift.load(std::memory_order_relaxed) != shift)
    return 4;
  return 0;
}
