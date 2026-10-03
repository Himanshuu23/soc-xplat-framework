#include "dma.h"

volatile uint32_t dma_irq_count;

void dma_start(const void *src, void *dst, uint32_t words, int irq)
{
    DMA->status = DMA_STATUS_DONE_MASK;
    DMA->src = (uint32_t)src;
    DMA->dst = (uint32_t)dst;
    DMA->len = words;
    DMA->ctrl = DMA_CTRL_START_MASK | (irq ? DMA_CTRL_IRQ_EN_MASK : 0);
}

int dma_wait(uint32_t max_polls)
{
    while (max_polls--) {
        if (DMA->status & DMA_STATUS_DONE_MASK)
            return 0;
    }
    return -1;
}

void dma_isr(void)
{
    if (!(DMA->status & DMA_STATUS_DONE_MASK))
        return;
    DMA->status = DMA_STATUS_DONE_MASK;
    dma_irq_count++;
}
