#include "dma.h"
#include "irq.h"
#include "test.h"
#include "timer.h"
#include "uart.h"

#define WORDS 64
#define GUARD 2
#define POISON 0xffffffffu

static uint32_t src_buf[WORDS];
static uint32_t dst_buf[WORDS + 2 * GUARD];
static uint32_t *const dst = dst_buf + GUARD;
static uint32_t seed = 0x2545f491;

static uint32_t next_random(void)
{
    seed ^= seed << 13;
    seed ^= seed >> 17;
    seed ^= seed << 5;
    return seed;
}

static void prepare(void)
{
    for (int i = 0; i < WORDS; i++)
        src_buf[i] = next_random();
    for (int i = 0; i < WORDS + 2 * GUARD; i++)
        dst_buf[i] = POISON;
}

static int copied(uint32_t words)
{
    for (uint32_t i = 0; i < words; i++) {
        if (dst[i] != src_buf[i])
            return 0;
    }
    return 1;
}

static int guards_intact(void)
{
    for (int i = 0; i < GUARD; i++) {
        if (dst_buf[i] != POISON || dst_buf[WORDS + GUARD + i] != POISON)
            return 0;
    }
    return 1;
}

int main(void)
{
    test_begin("dma_memcpy");

    TIMER->compare = 0xffffffffu;
    TIMER->count = 0;
    TIMER->ctrl = TIMER_CTRL_ENABLE_MASK;

    prepare();
    uint32_t t_start = TIMER->count;
    dma_start(src_buf, dst, WORDS, 0);
    uint32_t busy_seen = DMA->status & DMA_STATUS_BUSY_MASK;
    uint32_t progress = 0;
    while (DMA->status & DMA_STATUS_BUSY_MASK)
        progress++;
    uint32_t cycles = TIMER->count - t_start;
    check("busy right after start", busy_seen != 0);
    check("cpu kept running during dma", progress > 0);
    check("done flag set", (DMA->status & DMA_STATUS_DONE_MASK) != 0);
    check("polled copy matches", copied(WORDS));
    check("guard words untouched", guards_intact());
    check("no irq when irq_en is 0", dma_irq_count == 0);
    uart_puts("  info dma copied ");
    uart_put_dec(WORDS);
    uart_puts(" words in ~");
    uart_put_dec(cycles);
    uart_puts(" cycles while cpu polled\n");
    check("copy needs at least 4 cycles per word", cycles >= 4 * WORDS);

    prepare();
    dma_irq_count = 0;
    irq_enable(IRQ_DMA);
    dma_start(src_buf, dst, WORDS, 1);
    uint32_t guard = 0;
    while (dma_irq_count == 0 && guard++ < 100000) {
    }
    check("dma done interrupt delivered", dma_irq_count == 1);
    check("irq copy matches", copied(WORDS));
    check("isr cleared done flag", (DMA->status & DMA_STATUS_DONE_MASK) == 0);
    for (volatile int i = 0; i < 2000; i++) {
    }
    check("done irq is not re-entered", dma_irq_count == 1);
    irq_disable(IRQ_DMA);

    prepare();
    dma_start(src_buf, dst, 1, 0);
    check("single word completes", dma_wait(100000) == 0);
    check("only one word copied", dst[0] == src_buf[0] && dst[1] == POISON);

    prepare();
    dma_start(src_buf, dst, 0, 0);
    check("zero length finishes at once", (DMA->status & DMA_STATUS_DONE_MASK) != 0);
    check("zero length copies nothing", dst[0] == POISON);

    prepare();
    DMA->status = DMA_STATUS_DONE_MASK;
    DMA->src = (uint32_t)src_buf;
    DMA->dst = (uint32_t)dst;
    DMA->len = WORDS;
    DMA->ctrl = DMA_CTRL_START_MASK;
    DMA->src = 0;
    DMA->len = 1;
    check("config writes ignored while busy", DMA->src == (uint32_t)src_buf && DMA->len == WORDS);
    check("transfer still completes", dma_wait(100000) == 0 && copied(WORDS));

    TIMER->ctrl = 0;
    test_end();
}
