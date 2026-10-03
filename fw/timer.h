#ifndef TIMER_H
#define TIMER_H

#include <stddef.h>
#include <stdint.h>
#include "soc.h"

typedef struct {
    volatile uint32_t count;
    volatile uint32_t compare;
    volatile uint32_t ctrl;
    volatile uint32_t status;
} timer_regs_t;

_Static_assert(offsetof(timer_regs_t, count) == TIMER_COUNT_OFFSET, "timer count offset");
_Static_assert(offsetof(timer_regs_t, compare) == TIMER_COMPARE_OFFSET, "timer compare offset");
_Static_assert(offsetof(timer_regs_t, ctrl) == TIMER_CTRL_OFFSET, "timer ctrl offset");
_Static_assert(offsetof(timer_regs_t, status) == TIMER_STATUS_OFFSET, "timer status offset");

#define TIMER ((timer_regs_t *)TIMER_BASE)

extern volatile uint32_t timer_irq_count;
extern volatile uint32_t timer_irq_limit;

void timer_stop(void);
void timer_start(uint32_t compare, uint32_t ctrl_flags);
void timer_isr(void);

#endif
