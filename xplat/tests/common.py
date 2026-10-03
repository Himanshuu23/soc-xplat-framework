import random
from typing import List

from gen import regs
from xplat.framework import expect_eq
from xplat.hal.base import Backend, BackendTimeout

SCRATCH_BASE = regs.MEMORY["scratch_base"]
SCRATCH_SIZE = regs.MEMORY["scratch_size"]
SCRATCH_END = SCRATCH_BASE + SCRATCH_SIZE
SCRATCH_WORDS = SCRATCH_SIZE // 4
GUARD = 0xA5A5A5A5

TIMER_ENABLE = regs.REGISTERS["TIMER.CTRL"].field("ENABLE").mask
TIMER_IRQ_EN = regs.REGISTERS["TIMER.CTRL"].field("IRQ_EN").mask
TIMER_RELOAD = regs.REGISTERS["TIMER.CTRL"].field("RELOAD").mask
TIMER_MATCH = regs.REGISTERS["TIMER.STATUS"].field("MATCH").mask
DMA_START = regs.REGISTERS["DMA.CTRL"].field("START").mask
DMA_IRQ_EN = regs.REGISTERS["DMA.CTRL"].field("IRQ_EN").mask
DMA_BUSY = regs.REGISTERS["DMA.STATUS"].field("BUSY").mask
DMA_DONE = regs.REGISTERS["DMA.STATUS"].field("DONE").mask


def random_words(rng: random.Random, count: int) -> List[int]:
    return [rng.getrandbits(32) for _ in range(count)]


def start_dma(b: Backend, src: int, dst: int, words: int, irq: bool = False) -> None:
    b.write("DMA.STATUS", DMA_DONE)
    b.write("DMA.SRC", src)
    b.write("DMA.DST", dst)
    b.write("DMA.LEN", words)
    b.write("DMA.CTRL", DMA_START | (DMA_IRQ_EN if irq else 0))


def wait_dma_done(b: Backend, polls: int = 200) -> int:
    for count in range(polls):
        if b.read("DMA.STATUS") & DMA_DONE:
            return count
    raise BackendTimeout("DMA.STATUS.DONE never set within %d polls" % polls)


def expect_dma_idle_and_clean(b: Backend, where: str) -> None:
    expect_eq("%s DMA.STATUS" % where, b.read("DMA.STATUS"), 0, b.addr("DMA.STATUS"))
