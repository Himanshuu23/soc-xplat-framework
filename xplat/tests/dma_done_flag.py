from xplat.framework import expect_eq, expect_true, register
from xplat.hal.base import Backend
from xplat.tests.common import DMA_BUSY, DMA_DONE, DMA_IRQ_EN, SCRATCH_BASE, start_dma

WORDS = 8
SRC = SCRATCH_BASE
DST = SCRATCH_BASE + 0x80


def finish(b: Backend) -> None:
    for _ in range(200):
        status = b.read("DMA.STATUS")
        expect_true("DMA.STATUS never has BUSY and DONE together", not (status & DMA_BUSY and status & DMA_DONE), "status %#x" % status)
        if status & DMA_DONE:
            return
    expect_true("DMA.STATUS.DONE raised", False, "never set")


def done(b: Backend) -> int:
    return b.read("DMA.STATUS") & DMA_DONE


@register("dma_done_flag", "done sets after a transfer, is sticky, clears only on write 1, drives the irq")
def dma_done_flag(b: Backend, log) -> None:
    b.write_words(SRC, list(range(WORDS)))
    expect_eq("DMA.STATUS at start", b.read("DMA.STATUS"), 0, b.addr("DMA.STATUS"))

    start_dma(b, SRC, DST, WORDS)
    finish(b)
    expect_eq("DMA.STATUS.DONE after transfer", done(b), DMA_DONE)
    expect_eq("DMA.STATUS.BUSY after transfer", b.read("DMA.STATUS") & DMA_BUSY, 0)
    expect_eq("DMA.STATUS.DONE is sticky", done(b), DMA_DONE)

    b.write("DMA.STATUS", 0)
    expect_eq("DMA.STATUS.DONE after writing 0", done(b), DMA_DONE)
    b.write("DMA.STATUS", DMA_BUSY)
    expect_eq("DMA.STATUS.DONE after writing the BUSY bit", done(b), DMA_DONE)

    expect_true("dma irq low while irq_en is 0", not b.wait_irq("dma", timeout=0.2, polls=3))
    b.write("DMA.CTRL", DMA_IRQ_EN)
    expect_true("dma irq high with done and irq_en", b.wait_irq("dma", timeout=1.0))

    b.write("DMA.STATUS", DMA_DONE)
    expect_eq("DMA.STATUS.DONE after writing 1", done(b), 0)
    expect_true("dma irq low after clearing done", not b.wait_irq("dma", timeout=0.2, polls=3))

    start_dma(b, SRC, DST, WORDS, irq=True)
    finish(b)
    expect_eq("DMA.STATUS.DONE after second transfer", done(b), DMA_DONE)
    expect_true("dma irq high after second transfer", b.wait_irq("dma", timeout=1.0))
    log("done flag and irq behave")
