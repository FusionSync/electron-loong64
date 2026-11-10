/* N64 ABI wrapper: protect the caller's state, then measure a real swap. */
#if !defined(__mips__) || _MIPS_SIM != _ABI64
#error This probe requires the MIPS N64 ABI
#endif

.text
.set noreorder
.globl probe_saved_fprs
.type probe_saved_fprs, @function
.ent probe_saved_fprs
probe_saved_fprs:
    /* a0=from, a1=to, a2=seeds, a3=observations, a4=swap function */
    daddiu $sp, $sp, -96
    sd $s0, 0($sp)
    sd $ra, 8($sp)
    sdc1 $f24, 16($sp)
    sdc1 $f25, 24($sp)
    sdc1 $f26, 32($sp)
    sdc1 $f27, 40($sp)
    sdc1 $f28, 48($sp)
    sdc1 $f29, 56($sp)
    sdc1 $f30, 64($sp)
    sdc1 $f31, 72($sp)
    move $s0, $a3
    ldc1 $f24, 0($a2)
    ldc1 $f25, 8($a2)
    ldc1 $f26, 16($a2)
    ldc1 $f27, 24($a2)
    ldc1 $f28, 32($a2)
    ldc1 $f29, 40($a2)
    ldc1 $f30, 48($a2)
    ldc1 $f31, 56($a2)
    move $t9, $a4
    jalr $t9
    nop
    sdc1 $f24, 0($s0)
    sdc1 $f25, 8($s0)
    sdc1 $f26, 16($s0)
    sdc1 $f27, 24($s0)
    sdc1 $f28, 32($s0)
    sdc1 $f29, 40($s0)
    sdc1 $f30, 48($s0)
    sdc1 $f31, 56($s0)
    ldc1 $f24, 16($sp)
    ldc1 $f25, 24($sp)
    ldc1 $f26, 32($sp)
    ldc1 $f27, 40($sp)
    ldc1 $f28, 48($sp)
    ldc1 $f29, 56($sp)
    ldc1 $f30, 64($sp)
    ldc1 $f31, 72($sp)
    ld $s0, 0($sp)
    ld $ra, 8($sp)
    daddiu $sp, $sp, 96
    jr $ra
    nop
.end probe_saved_fprs
.size probe_saved_fprs, .-probe_saved_fprs
.section .note.GNU-stack,"",@progbits
