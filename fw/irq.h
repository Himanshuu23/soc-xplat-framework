#ifndef IRQ_H
#define IRQ_H

#include <stdint.h>
#include "soc.h"

static inline uint32_t irq_maskirq(uint32_t mask)
{
    uint32_t old;
    __asm__ volatile(".insn r 0x0b, 6, 3, %0, %1, x0" : "=r"(old) : "r"(mask));
    return old;
}

static inline void irq_enable(uint32_t bits)
{
    uint32_t old = irq_maskirq(0xffffffffu);
    irq_maskirq(old & ~bits);
}

static inline void irq_disable(uint32_t bits)
{
    uint32_t old = irq_maskirq(0xffffffffu);
    irq_maskirq(old | bits);
}

void irq_handler(uint32_t pending);

#endif
