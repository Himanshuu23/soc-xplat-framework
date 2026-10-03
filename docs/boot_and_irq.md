# start.S, step by step

The source has no comments, this is the explanation.

## Why custom instructions

PicoRV32 does not implement the standard machine-mode CSRs (mstatus, mepc, mtvec). Interrupts use four custom instructions in the custom0 opcode space (0x0b):

| Instruction | Does |
|---|---|
| getq rd, qs | rd = q register qs |
| setq qd, rs | q register qd = rs |
| retirq | pc = q0, re-enable interrupts |
| maskirq rd, rs | rd = old mask, mask = rs (a 1 bit masks that irq) |

q0 holds the return address when an interrupt is taken, q1 holds the bitmask of pending interrupts. q2 and q3 are free scratch registers. fw/custom_ops.h encodes these with .word so no special assembler support is needed. maskirq is used from C through inline asm in fw/irq.h.

## Vectors

PicoRV32 is configured with reset at 0x00 and interrupt entry at 0x10 (PROGADDR_RESET, PROGADDR_IRQ in soc_top.v). The .vectors section is placed first by the linker script:

- 0x00: j reset_handler
- 0x10: irq_entry (after .balign 16)

## reset_handler

1. sp = _stack_top, the end of RAM, from link.ld.
2. Zero .bss between _sbss and _ebss, one word at a time.
3. Copy .data from _sidata (its load address in the low half of RAM) to _sdata.._edata (its run address in the high half).
4. call main.
5. main's return value goes to the SYS exit register, then an endless loop.

Every interrupt is masked out of reset, so nothing fires before the stack exists.

## irq_entry

At entry every register still belongs to the interrupted code, and no stack frame may be assumed. The same trick as the PicoRV32 reference firmware is used: park x1 and x2 in q2 and q3, which frees two registers to address a save area.

1. setq q2, x1; setq q3, x2.
2. x1 = &irq_regs (a 128-byte area in .bss).
3. Using x2 as a temporary: store q0 (return pc), the original x1 (from q2), the original x2 (from q3).
4. Store x3 to x31 with an .irp loop.
5. getq a0, q1: the pending mask becomes the first C argument.
6. jal irq_handler.
7. Reload irq_regs address, put saved pc back into q0, saved x1 into q1, saved x2 into q2.
8. Reload x3 to x31.
9. getq x1, q1; getq x2, q2: x1 and x2 are restored last because x1 was the base pointer.
10. retirq.

Nesting is not supported, the core blocks new interrupts until retirq.

## C side

irq_handler(pending) in fw/irq.c checks bit 0 and bit 1 and calls timer_isr or dma_isr. Each ISR reads its status flag, writes 1 to clear it, and increments a counter. Any other bit is fatal and ends the simulation with code 3.

The peripheral irq lines are levels. If an ISR did not clear its flag, the line would stay high and the core would re-enter the handler forever.

## LATCHED_IRQ

The core normally remembers an interrupt even if the input drops. With a level source that stays high through the handler, the remembered bit gets set again during the handler and fires a second time after retirq. soc_top.v sets LATCHED_IRQ to 0xfffffffc, so bits 0 and 1 follow the lines directly.
