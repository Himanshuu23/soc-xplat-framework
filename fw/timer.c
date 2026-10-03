#include "timer.h"

volatile uint32_t timer_irq_count;
volatile uint32_t timer_irq_limit;

void timer_stop(void)
{
    TIMER->ctrl = 0;
    TIMER->status = TIMER_STATUS_MATCH_MASK;
}

void timer_start(uint32_t compare, uint32_t ctrl_flags)
{
    timer_stop();
    TIMER->compare = compare;
    TIMER->count = 0;
    TIMER->ctrl = TIMER_CTRL_ENABLE_MASK | ctrl_flags;
}

void timer_isr(void)
{
    TIMER->status = TIMER_STATUS_MATCH_MASK;
    timer_irq_count++;
    if (timer_irq_limit && timer_irq_count >= timer_irq_limit)
        TIMER->ctrl = 0;
}
