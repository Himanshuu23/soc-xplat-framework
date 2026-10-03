#include "soc.h"
#include "custom_ops.h"

    .section .vectors, "ax"
    .global _start
_start:
    j reset_handler

    .balign 16
irq_entry:
    setq_insn(q2, x1)
    setq_insn(q3, x2)
    lui x1, %hi(irq_regs)
    addi x1, x1, %lo(irq_regs)
    getq_insn(x2, q0)
    sw x2, 0(x1)
    getq_insn(x2, q2)
    sw x2, 4(x1)
    getq_insn(x2, q3)
    sw x2, 8(x1)
    .irp r, 3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31
    sw x\r, \r*4(x1)
    .endr
    getq_insn(a0, q1)
    jal ra, irq_handler
    lui x1, %hi(irq_regs)
    addi x1, x1, %lo(irq_regs)
    lw x2, 0(x1)
    setq_insn(q0, x2)
    lw x2, 4(x1)
    setq_insn(q1, x2)
    lw x2, 8(x1)
    setq_insn(q2, x2)
    .irp r, 3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31
    lw x\r, \r*4(x1)
    .endr
    getq_insn(x1, q1)
    getq_insn(x2, q2)
    retirq_insn()

    .section .text
reset_handler:
    la sp, _stack_top

    la t0, _sbss
    la t1, _ebss
1:  bgeu t0, t1, 2f
    sw zero, 0(t0)
    addi t0, t0, 4
    j 1b

2:  la t0, _sdata
    la t1, _edata
    la t2, _sidata
3:  bgeu t0, t1, 4f
    lw t3, 0(t2)
    sw t3, 0(t0)
    addi t0, t0, 4
    addi t2, t2, 4
    j 3b

4:  call main
    li t0, SYS_EXIT_ADDR
    sw a0, 0(t0)
5:  j 5b

    .section .bss
    .balign 4
irq_regs:
    .space 128
