#include "dma.h"
#include "irq.h"
#include "sys.h"
#include "timer.h"
#include "uart.h"

static void fatal(uint32_t pending)
{
    uart_puts("fatal irq 0x");
    uart_put_hex(pending);
    uart_putc('\n');
    sys_exit(3);
}

void irq_handler(uint32_t pending)
{
    if (pending & IRQ_TIMER)
        timer_isr();
    if (pending & IRQ_DMA)
        dma_isr();
    if (pending & ~(uint32_t)(IRQ_TIMER | IRQ_DMA))
        fatal(pending);
}
