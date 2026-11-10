/* N64 PIC wrapper: test the real V8 entry without changing our caller's FPRs. */
.abicalls
.section .mdebug.abi64,"",@progbits
.text
.set nomips16
.set nomicromips
.set noreorder
.p2align 3
.globl probe_n64_fpr_roundtrip
.hidden probe_n64_fpr_roundtrip
.hidden probe_invoke_js
.type probe_n64_fpr_roundtrip,@function
.ent probe_n64_fpr_roundtrip
probe_n64_fpr_roundtrip:
  .frame $sp,80,$ra
  .mask 0x90000000,-8
  .fmask 0xff000000,-24
  daddiu $sp,$sp,-80
  sd $ra,72($sp)
  sd $gp,64($sp)
  sdc1 $f24,0($sp)
  sdc1 $f25,8($sp)
  sdc1 $f26,16($sp)
  sdc1 $f27,24($sp)
  sdc1 $f28,32($sp)
  sdc1 $f29,40($sp)
  sdc1 $f30,48($sp)
  sdc1 $f31,56($sp)

  lui $12,%hi(%neg(%gp_rel(probe_n64_fpr_roundtrip)))
  daddu $12,$12,$25
  daddiu $gp,$12,%lo(%neg(%gp_rel(probe_n64_fpr_roundtrip)))

.macro SEED reg
  dli $12,0x3ff1234567890000+\reg
  dmtc1 $12,$f\reg
.endm
  SEED 24
  SEED 25
  SEED 26
  SEED 27
  SEED 28
  SEED 29
  SEED 30
  SEED 31

  /* a0 still contains ProbeContext*. The bridge uses napi_call_function. */
  ld $25,%call16(probe_invoke_js)($gp)
  jalr $25
  nop

  or $2,$zero,$zero
.macro CHECK reg,bit
  dli $12,0x3ff1234567890000+\reg
  dmfc1 $13,$f\reg
  xor $13,$13,$12
  sltu $13,$zero,$13
  dsll $13,$13,\bit
  or $2,$2,$13
.endm
  CHECK 24,0
  CHECK 25,1
  CHECK 26,2
  CHECK 27,3
  CHECK 28,4
  CHECK 29,5
  CHECK 30,6
  CHECK 31,7

  ldc1 $f24,0($sp)
  ldc1 $f25,8($sp)
  ldc1 $f26,16($sp)
  ldc1 $f27,24($sp)
  ldc1 $f28,32($sp)
  ldc1 $f29,40($sp)
  ldc1 $f30,48($sp)
  ldc1 $f31,56($sp)
  ld $gp,64($sp)
  ld $ra,72($sp)
  jr $ra
  daddiu $sp,$sp,80
.end probe_n64_fpr_roundtrip
.size probe_n64_fpr_roundtrip,.-probe_n64_fpr_roundtrip
.section .note.GNU-stack,"",@progbits
