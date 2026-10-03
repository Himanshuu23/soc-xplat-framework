import time
from abc import ABC, abstractmethod
from typing import List

from gen import regs

WORD_MASK = 0xFFFFFFFF


class BackendError(Exception):
    pass


class BackendTimeout(BackendError):
    pass


class BackendProtocolError(BackendError):
    pass


class Backend(ABC):
    name = "backend"

    @abstractmethod
    def read_reg(self, addr: int) -> int:
        ...

    @abstractmethod
    def write_reg(self, addr: int, val: int) -> None:
        ...

    @abstractmethod
    def reset(self) -> None:
        ...

    def close(self) -> None:
        pass

    def __enter__(self) -> "Backend":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def addr(self, name: str) -> int:
        return regs.REGISTERS[name].address

    def read(self, name: str) -> int:
        return self.read_reg(self.addr(name))

    def write(self, name: str, val: int) -> None:
        self.write_reg(self.addr(name), val)

    def read_field(self, dotted: str) -> int:
        periph, reg, fld = dotted.split(".")
        field = regs.REGISTERS["%s.%s" % (periph, reg)].field(fld)
        return (self.read("%s.%s" % (periph, reg)) & field.mask) >> field.lsb

    def write_words(self, addr: int, words: List[int]) -> None:
        for i, word in enumerate(words):
            self.write_reg(addr + 4 * i, word)

    def read_words(self, addr: int, count: int) -> List[int]:
        return [self.read_reg(addr + 4 * i) for i in range(count)]

    def dma_copy(self, src: int, dst: int, words: int, irq: bool = False, timeout: float = 10.0) -> None:
        done = regs.REGISTERS["DMA.STATUS"].field("DONE").mask
        start = regs.REGISTERS["DMA.CTRL"].field("START").mask
        irq_en = regs.REGISTERS["DMA.CTRL"].field("IRQ_EN").mask
        self.write("DMA.STATUS", done)
        self.write("DMA.SRC", src)
        self.write("DMA.DST", dst)
        self.write("DMA.LEN", words)
        self.write("DMA.CTRL", start | (irq_en if irq else 0))
        deadline = time.monotonic() + timeout
        while not self.read("DMA.STATUS") & done:
            if time.monotonic() > deadline:
                raise BackendTimeout("DMA did not finish %d words within %.1fs" % (words, timeout))
        self.write("DMA.STATUS", done)

    def irq_asserted(self, name: str) -> bool:
        irq = regs.IRQS[name]
        return bool(self.read_field(irq.status)) and bool(self.read_field(irq.enable))

    def wait_irq(self, name: str, timeout: float = 1.0, polls: int = 50) -> bool:
        deadline = time.monotonic() + timeout
        for _ in range(polls):
            if self.irq_asserted(name):
                return True
            if time.monotonic() > deadline:
                break
        return False
