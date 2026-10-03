import random

from xplat.framework import config, expect_eq, expect_true, expect_words, register
from xplat.hal.base import Backend
from xplat.tests.common import (
    DMA_BUSY,
    DMA_DONE,
    DMA_START,
    GUARD,
    SCRATCH_BASE,
    SCRATCH_END,
    SCRATCH_WORDS,
    expect_dma_idle_and_clean,
    random_words,
    start_dma,
    wait_dma_done,
)

JUNK = 0x0000A000


def check_zero_length(b: Backend) -> None:
    dst = SCRATCH_BASE + 0x100
    b.write_reg(dst, GUARD)
    b.dma_copy(SCRATCH_BASE, dst, 0)
    expect_eq("dst after zero length copy", b.read_reg(dst), GUARD, dst)
    expect_dma_idle_and_clean(b, "after zero length copy")


def busy_trial(b: Backend, what: str, poke) -> None:
    start_dma(b, SCRATCH_BASE, SCRATCH_BASE, SCRATCH_WORDS)
    poke()
    status = b.read("DMA.STATUS")
    expect_true(
        "DMA.STATUS.BUSY while %s" % what,
        bool(status & DMA_BUSY),
        "status %#x, transfer ended before the check could prove the write happened while busy" % status,
    )
    wait_dma_done(b)
    b.write("DMA.STATUS", DMA_DONE)


def check_busy_behaviour(b: Backend, rng: random.Random) -> None:
    sentinel = random_words(rng, 4)
    b.write_words(SCRATCH_BASE, sentinel)
    b.write_words(SCRATCH_END - 16, sentinel)

    for name, junk, original in (
        ("DMA.SRC", JUNK, SCRATCH_BASE),
        ("DMA.DST", JUNK, SCRATCH_BASE),
        ("DMA.LEN", 1, SCRATCH_WORDS),
    ):
        busy_trial(b, "writing %s" % name, lambda n=name, j=junk: b.write(n, j))
        expect_eq("%s write ignored while busy" % name, b.read(name), original, b.addr(name))

    busy_trial(b, "restarting", lambda: b.write("DMA.CTRL", DMA_START))
    for _ in range(3):
        expect_eq("DMA.STATUS after a start while busy", b.read("DMA.STATUS"), 0, b.addr("DMA.STATUS"))

    expect_words("start of scratch after self copy", SCRATCH_BASE, b.read_words(SCRATCH_BASE, 4), sentinel)
    expect_words("end of scratch after self copy", SCRATCH_END - 16, b.read_words(SCRATCH_END - 16, 4), sentinel)


def check_boundaries(b: Backend, rng: random.Random) -> None:
    last = SCRATCH_END - 4
    cases = (
        ("first word to last word", SCRATCH_BASE, last, 1),
        ("last two words to first two", SCRATCH_END - 8, SCRATCH_BASE, 2),
        ("single word onto itself", SCRATCH_BASE + 0x40, SCRATCH_BASE + 0x40, 1),
        ("block ending at region end", SCRATCH_BASE + 0x200, SCRATCH_END - 64, 16),
    )
    for label, src, dst, words in cases:
        data = random_words(rng, words)
        b.write_words(src, data)
        before = b.read_reg(dst - 4) if dst - 4 >= SCRATCH_BASE else None
        b.write_reg(SCRATCH_END, GUARD)
        b.dma_copy(src, dst, words)
        expect_words("dst (%s)" % label, dst, b.read_words(dst, words), data)
        expect_eq("guard word at region end (%s)" % label, b.read_reg(SCRATCH_END), GUARD, SCRATCH_END)
        if before is not None:
            expect_eq("word before dst (%s)" % label, b.read_reg(dst - 4), before, dst - 4)


@register("dma_copy_edge", "zero length, config writes while busy, start while busy, region boundaries")
def dma_copy_edge(b: Backend, log) -> None:
    rng = random.Random(config.seed + 1)
    check_zero_length(b)
    log("zero length ok")
    check_busy_behaviour(b, rng)
    log("busy behaviour ok")
    check_boundaries(b, rng)
    log("boundaries ok")
