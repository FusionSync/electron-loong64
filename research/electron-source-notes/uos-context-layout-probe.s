	.file	"uos-context-layout-probe.cc"
	.text
	.section	.rodata
	.align	3
	.type	_ZL13uos_pc_offset, @object
	.size	_ZL13uos_pc_offset, 8
_ZL13uos_pc_offset:
	.dword	64
	.align	3
	.type	_ZL16uos_gregs_offset, @object
	.size	_ZL16uos_gregs_offset, 8
_ZL16uos_gregs_offset:
	.dword	72
	.align	3
	.type	_ZL23uos_glibc_fpregs_offset, @object
	.size	_ZL23uos_glibc_fpregs_offset, 8
_ZL23uos_glibc_fpregs_offset:
	.dword	352
	.align	3
	.type	_ZL29uos_kernel_fpregs_in_mcontext, @object
	.size	_ZL29uos_kernel_fpregs_in_mcontext, 8
_ZL29uos_kernel_fpregs_in_mcontext:
	.dword	320
	.align	3
	.type	_ZL27uos_kernel_fcsr_in_mcontext, @object
	.size	_ZL27uos_kernel_fcsr_in_mcontext, 8
_ZL27uos_kernel_fcsr_in_mcontext:
	.dword	268
	.align	3
	.type	_ZL26uos_kernel_fcc_in_mcontext, @object
	.size	_ZL26uos_kernel_fcc_in_mcontext, 8
_ZL26uos_kernel_fcc_in_mcontext:
	.dword	280
	.align	3
	.type	_ZL20uos_ptrace_pc_offset, @object
	.size	_ZL20uos_ptrace_pc_offset, 8
_ZL20uos_ptrace_pc_offset:
	.dword	256
	.align	3
	.type	_ZL27uos_kernel_ptrace_pc_offset, @object
	.size	_ZL27uos_kernel_ptrace_pc_offset, 8
_ZL27uos_kernel_ptrace_pc_offset:
	.dword	256
	.align	3
	.type	_ZL23uos_ptrace_context_size, @object
	.size	_ZL23uos_ptrace_context_size, 8
_ZL23uos_ptrace_context_size:
	.dword	360
	.align	3
	.type	_ZL19uos_ptrace_fpu_size, @object
	.size	_ZL19uos_ptrace_fpu_size, 8
_ZL19uos_ptrace_fpu_size:
	.dword	272
	.ident	"GCC: (LoongArch GNU toolchain rc1.6 (20241115)) 8.3.0"
	.section	.note.GNU-stack,"",@progbits
