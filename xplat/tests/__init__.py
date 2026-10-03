from typing import List

from xplat.framework import REGISTRY, TestCase

from . import (  # noqa: F401
    dma_copy_basic,
    dma_copy_edge,
    dma_done_flag,
    random_dma,
    reg_access_types,
    reg_reset_values,
    timer_basic,
)

ORDER = (
    "reg_reset_values",
    "reg_access_types",
    "timer_basic",
    "dma_copy_basic",
    "dma_copy_edge",
    "dma_done_flag",
    "random_dma",
)


def all_tests() -> List[TestCase]:
    return [REGISTRY[name] for name in ORDER]
