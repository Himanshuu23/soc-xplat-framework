#ifndef DMA_H
#define DMA_H

#include <stddef.h>
#include <stdint.h>
#include "soc.h"

typedef struct {
    volatile uint32_t src;
    volatile uint32_t dst;
    volatile uint32_t len;
    volatile uint32_t ctrl;
    volatile uint32_t status;
} dma_regs_t;

_Static_assert(offsetof(dma_regs_t, src) == DMA_SRC_OFFSET, "dma src offset");
_Static_assert(offsetof(dma_regs_t, dst) == DMA_DST_OFFSET, "dma dst offset");
_Static_assert(offsetof(dma_regs_t, len) == DMA_LEN_OFFSET, "dma len offset");
_Static_assert(offsetof(dma_regs_t, ctrl) == DMA_CTRL_OFFSET, "dma ctrl offset");
_Static_assert(offsetof(dma_regs_t, status) == DMA_STATUS_OFFSET, "dma status offset");

#define DMA ((dma_regs_t *)DMA_BASE)

extern volatile uint32_t dma_irq_count;

void dma_start(const void *src, void *dst, uint32_t words, int irq);
int dma_wait(uint32_t max_polls);
void dma_isr(void);

#endif
