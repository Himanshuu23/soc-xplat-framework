import random
from typing import Dict, List

from xplat.framework import config, expect_words, hexv, register
from xplat.hal.base import Backend
from xplat.tests.common import SCRATCH_BASE, SCRATCH_END

ITERATIONS = 12
MAX_WORDS = 16
OVERLAP_ODDS = 5


def pick_transfer(rng: random.Random) -> tuple:
    words = rng.randint(1, MAX_WORDS)
    span = (SCRATCH_END - SCRATCH_BASE) // 4 - 2
    src_index = rng.randint(1, span - words)
    if rng.randrange(OVERLAP_ODDS) == 0:
        dst_index = max(1, min(span - words, src_index + rng.randint(-words, words)))
    else:
        dst_index = rng.randint(1, span - words)
        while abs(dst_index - src_index) < words:
            dst_index = rng.randint(1, span - words)
    return SCRATCH_BASE + 4 * src_index, SCRATCH_BASE + 4 * dst_index, words


def window(base: int, words: int) -> List[int]:
    return [base - 4 + 4 * i for i in range(words + 2)]


@register("random_dma", "constrained-random src/dst/len copies with a fixed seed, checked against a reference")
def random_dma(b: Backend, log) -> None:
    rng = random.Random(config.seed)
    log("seed %s" % hexv(config.seed))
    for n in range(ITERATIONS):
        src, dst, words = pick_transfer(rng)
        addrs = sorted(set(window(src, words) + window(dst, words)))
        image: Dict[int, int] = {a: rng.getrandbits(32) for a in addrs}
        for a in addrs:
            b.write_reg(a, image[a])

        b.dma_copy(src, dst, words)

        for i in range(words):
            image[dst + 4 * i] = image[src + 4 * i]
        label = "iteration %d (src=%s dst=%s words=%d seed=%s)" % (n, hexv(src), hexv(dst), words, hexv(config.seed))
        actual = [b.read_reg(a) for a in addrs]
        expect_words(label, addrs[0], actual, [image[a] for a in addrs])
    log("%d random transfers matched the reference" % ITERATIONS)
