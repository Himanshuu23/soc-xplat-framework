#include "irq.h"
#include "test.h"
#include "timer.h"

#define PERIOD 999
#define IRQ_TARGET 5

static void spin(uint32_t n)
{
    for (volatile uint32_t i = 0; i < n; i++) {
    }
}

int main(void)
{
    test_begin("timer_irq");

    timer_stop();
    uint32_t a = TIMER->count;
    spin(10);
    check("count frozen while disabled", TIMER->count == a);

    timer_start(PERIOD, 0);
    uint32_t t0 = TIMER->count;
    spin(10);
    check("count advances when enabled", TIMER->count > t0);
    uint32_t guard = 0;
    while (!(TIMER->status & TIMER_STATUS_MATCH_MASK) && guard++ < 100000) {
    }
    check("match flag sets without irq", (TIMER->status & TIMER_STATUS_MATCH_MASK) != 0);
    check("no irq delivered when ctrl.irq_en is 0", timer_irq_count == 0);
    TIMER->status = TIMER_STATUS_MATCH_MASK;
    check("status is write-1-to-clear", (TIMER->status & TIMER_STATUS_MATCH_MASK) == 0);
    timer_stop();

    timer_irq_count = 0;
    timer_start(PERIOD, TIMER_CTRL_IRQ_EN_MASK);
    guard = 0;
    while (!(TIMER->status & TIMER_STATUS_MATCH_MASK) && guard++ < 100000) {
    }
    spin(200);
    check("masked cpu irq stays pending", timer_irq_count == 0);
    irq_enable(IRQ_TIMER);
    guard = 0;
    while (timer_irq_count == 0 && guard++ < 100000) {
    }
    check("irq fires once unmasked", timer_irq_count == 1);
    spin(3000);
    check("level irq is not re-entered after ack", timer_irq_count == 1);
    timer_stop();
    irq_disable(IRQ_TIMER);

    timer_irq_count = 0;
    timer_irq_limit = IRQ_TARGET;
    irq_enable(IRQ_TIMER);
    timer_start(PERIOD, TIMER_CTRL_IRQ_EN_MASK | TIMER_CTRL_RELOAD_MASK);
    guard = 0;
    while (timer_irq_count < IRQ_TARGET && guard++ < 1000000) {
    }
    check("reached target irq count", timer_irq_count == IRQ_TARGET);
    spin(3000);
    check("no extra irqs after the timer stopped", timer_irq_count == IRQ_TARGET);
    check("timer disabled by isr", (TIMER->ctrl & TIMER_CTRL_ENABLE_MASK) == 0);
    check("match cleared by isr", (TIMER->status & TIMER_STATUS_MATCH_MASK) == 0);

    irq_disable(IRQ_TIMER);
    test_end();
}
