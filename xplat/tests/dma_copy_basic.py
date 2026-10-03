import random

from xplat.framework import config, expect_eq, expect_words, register
from xplat.hal.base import Backend
from xplat.tests.common import GUARD, SCRATCH_BASE, expect_dma_idle_and_clean, random_words

WORDS = 32
SRC = SCRATCH_BASE
DST = SCRATCH_BASE + 0x1000


@register("dma_copy_basic", "copy N words, compare contents, source and guard words untouched")
def dma_copy_basic(b: Backend, log) -> None:
    rng = random.Random(config.seed)
    data = random_words(rng, WORDS)
    b.write_words(SRC, data)
    b.write_reg(DST - 4, GUARD)
    b.write_reg(DST + 4 * WORDS, GUARD)
    b.write_words(DST, [0] * WORDS)

    b.dma_copy(SRC, DST, WORDS)

    expect_words("dst", DST, b.read_words(DST, WORDS), data)
    expect_words("src", SRC, b.read_words(SRC, WORDS), data)
    expect_eq("guard word before dst", b.read_reg(DST - 4), GUARD, DST - 4)
    expect_eq("guard word after dst", b.read_reg(DST + 4 * WORDS), GUARD, DST + 4 * WORDS)
    expect_eq("DMA.SRC after copy", b.read("DMA.SRC"), SRC, b.addr("DMA.SRC"))
    expect_eq("DMA.DST after copy", b.read("DMA.DST"), DST, b.addr("DMA.DST"))
    expect_eq("DMA.LEN after copy", b.read("DMA.LEN"), WORDS, b.addr("DMA.LEN"))
    expect_dma_idle_and_clean(b, "after copy")
    log("copied %d words" % WORDS)
