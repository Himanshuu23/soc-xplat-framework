from typing import Dict, List, Optional

from gen import regs

from .base import WORD_MASK, Backend, BackendProtocolError

ACCESS_CYCLES = 9000
DMA_CYCLES_PER_WORD = 6
UART_BYTE_CYCLES = 160
BUGS = ("dma_len_off_by_one", "timer_w1c_ignored")


def field_mask(reg: str, name: str) -> int:
    return regs.REGISTERS[reg].field(name).mask


TIMER_ENABLE = field_mask("TIMER.CTRL", "ENABLE")
TIMER_RELOAD = field_mask("TIMER.CTRL", "RELOAD")
TIMER_MATCH = field_mask("TIMER.STATUS", "MATCH")
DMA_START = field_mask("DMA.CTRL", "START")
DMA_BUSY = field_mask("DMA.STATUS", "BUSY")
DMA_DONE = field_mask("DMA.STATUS", "DONE")
UART_TX_BUSY = field_mask("UART.STATUS", "TX_BUSY")
UART_RX_VALID = field_mask("UART.STATUS", "RX_VALID")


class ModelBackend(Backend):
    name = "model"

    def __init__(self, bug: Optional[str] = None, access_cycles: int = ACCESS_CYCLES) -> None:
        if bug is not None and bug not in BUGS:
            raise ValueError("unknown bug %r, choose from %s" % (bug, ", ".join(BUGS)))
        self.bug = bug
        self.access_cycles = access_cycles
        self.ram_size = regs.MEMORY["ram_size"]
        self.ram_fill = regs.MEMORY["ram_fill"]
        self.tx_log: List[int] = []
        self.reset()

    def reset(self) -> None:
        self.time = 0
        self.values: Dict[str, int] = {key: reg.reset for key, reg in regs.REGISTERS.items()}
        self.ram: Dict[int, int] = {}
        self.tx_busy_until = 0
        self.dma_src = 0
        self.dma_dst = 0
        self.dma_remaining = 0
        self.dma_credit = 0
        self.tx_log.clear()

    def check_addr(self, addr: int) -> None:
        if not 0 <= addr <= WORD_MASK or addr & 3:
            raise BackendProtocolError("bad address 0x%x, must be word aligned 32-bit" % addr)

    def read_reg(self, addr: int) -> int:
        self.check_addr(addr)
        self.advance(self.access_cycles)
        if addr < self.ram_size:
            return self.ram.get(addr >> 2, self.ram_fill)
        reg = regs.BY_ADDRESS.get(addr)
        if reg is None:
            return 0
        if reg.key == "UART.DATA":
            self.values["UART.STATUS"] &= ~UART_RX_VALID
        return self.values[reg.key]

    def write_reg(self, addr: int, val: int) -> None:
        self.check_addr(addr)
        val &= WORD_MASK
        self.advance(self.access_cycles)
        if addr < self.ram_size:
            self.ram[addr >> 2] = val
            return
        reg = regs.BY_ADDRESS.get(addr)
        if reg is None:
            return
        if reg.key in ("DMA.SRC", "DMA.DST", "DMA.LEN") and self.values["DMA.STATUS"] & DMA_BUSY:
            return
        if reg.key == "UART.DATA":
            self.uart_send(val & 0xFF)
            return
        if reg.key == "SYS.EXIT":
            self.values[reg.key] = val
            return
        current = self.values[reg.key]
        for f in reg.fields:
            bits = val & f.mask
            if f.access == "RW":
                current = (current & ~f.mask) | bits
            elif f.access == "W1C":
                if self.bug == "timer_w1c_ignored" and reg.key == "TIMER.STATUS":
                    continue
                current &= ~bits
        self.values[reg.key] = current
        if reg.key == "DMA.CTRL" and val & DMA_START:
            self.dma_start()

    def uart_send(self, byte: int) -> None:
        if self.values["UART.STATUS"] & UART_TX_BUSY:
            return
        self.tx_log.append(byte)
        self.values["UART.STATUS"] |= UART_TX_BUSY
        self.tx_busy_until = self.time + UART_BYTE_CYCLES

    def dma_start(self) -> None:
        if self.values["DMA.STATUS"] & DMA_BUSY:
            return
        words = self.values["DMA.LEN"]
        if words == 0:
            self.values["DMA.STATUS"] |= DMA_DONE
            return
        self.dma_src = self.values["DMA.SRC"]
        self.dma_dst = self.values["DMA.DST"]
        self.dma_remaining = words + 1 if self.bug == "dma_len_off_by_one" else words
        self.dma_credit = 0
        self.values["DMA.STATUS"] |= DMA_BUSY

    def advance(self, cycles: int) -> None:
        self.time += cycles
        if self.values["UART.STATUS"] & UART_TX_BUSY and self.time >= self.tx_busy_until:
            self.values["UART.STATUS"] &= ~UART_TX_BUSY
        self.advance_timer(cycles)
        self.advance_dma(cycles)

    def advance_timer(self, cycles: int) -> None:
        ctrl = self.values["TIMER.CTRL"]
        if not ctrl & TIMER_ENABLE:
            return
        count = self.values["TIMER.COUNT"]
        compare = self.values["TIMER.COMPARE"]
        steps_to_match = (compare - count) & WORD_MASK
        if cycles <= steps_to_match:
            count = (count + cycles) & WORD_MASK
        else:
            self.values["TIMER.STATUS"] |= TIMER_MATCH
            after = cycles - steps_to_match - 1
            if ctrl & TIMER_RELOAD:
                count = after % (compare + 1)
            else:
                count = (compare + 1 + after) & WORD_MASK
        self.values["TIMER.COUNT"] = count

    def advance_dma(self, cycles: int) -> None:
        if not self.values["DMA.STATUS"] & DMA_BUSY:
            return
        self.dma_credit += cycles
        words = min(self.dma_remaining, self.dma_credit // DMA_CYCLES_PER_WORD)
        for _ in range(words):
            src_index = (self.dma_src >> 2) & 0x3FFF
            dst_index = (self.dma_dst >> 2) & 0x3FFF
            self.ram[dst_index] = self.ram.get(src_index, self.ram_fill)
            self.dma_src = (self.dma_src + 4) & WORD_MASK
            self.dma_dst = (self.dma_dst + 4) & WORD_MASK
        self.dma_remaining -= words
        self.dma_credit -= words * DMA_CYCLES_PER_WORD
        if self.dma_remaining == 0:
            self.values["DMA.STATUS"] = (self.values["DMA.STATUS"] & ~DMA_BUSY) | DMA_DONE
            self.dma_credit = 0
