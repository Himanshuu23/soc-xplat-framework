# Memory map

| Base | Size | Device |
|---|---|---|
| 0x0000_0000 | 64 KB | RAM |
| 0x1000_0000 | 4 KB | UART |
| 0x1000_1000 | 4 KB | TIMER |
| 0x1000_2000 | 4 KB | DMA |
| 0x1000_3000 | 4 KB | SYS |

Anything else is unmapped: reads return 0, writes are dropped, and the bus still acknowledges so the CPU never hangs.

All registers are 32 bits and word aligned. Peripherals are selected by address bits [31:12].

Firmware linker layout inside the RAM: 0x0000-0x7FFF holds .text, .rodata and the load image of .data; 0x8000-0xFFFF holds .data, .bss and the stack, which starts at 0x10000 and grows down.

## UART (0x1000_0000)

| Offset | Name | Access | Description |
|---|---|---|---|
| 0x0 | DATA | R/W | write: send the low byte, ignored while tx_busy. read: last received byte, clears rx_valid |
| 0x4 | STATUS | R | bit 0 tx_busy, bit 1 rx_valid |
| 0x8 | BAUD | R/W | clock cycles per bit, reset value 16 |

8N1 framing. RX holds one byte and has no FIFO, so software must read DATA before the next byte finishes arriving. The testbench decodes TX assuming a divisor of 16, which matches UART_BAUD_DIV in fw/soc.h.

## TIMER (0x1000_1000)

| Offset | Name | Access | Description |
|---|---|---|---|
| 0x0 | COUNT | R/W | 32-bit counter, increments every clock while enabled |
| 0x4 | COMPARE | R/W | reset value 0xffff_ffff |
| 0x8 | CTRL | R/W | bit 0 enable, bit 1 irq_en, bit 2 reload |
| 0xC | STATUS | R/W1C | bit 0 match |

When COUNT equals COMPARE the match flag is set. With reload set, COUNT returns to 0, so the period is COMPARE + 1 cycles; otherwise it keeps counting. The irq output is match AND irq_en, a level that stays high until software writes 1 to STATUS.match.

## DMA (0x1000_2000)

| Offset | Name | Access | Description |
|---|---|---|---|
| 0x00 | SRC | R/W | source byte address, word aligned |
| 0x04 | DST | R/W | destination byte address, word aligned |
| 0x08 | LEN | R/W | number of 32-bit words |
| 0x0C | CTRL | R/W | bit 0 start (self-clearing, reads 0), bit 1 irq_en |
| 0x10 | STATUS | R/W1C | bit 0 busy, bit 1 done |

SRC, DST and LEN writes are ignored while busy. A start while busy is ignored. LEN = 0 sets done immediately without touching memory. The irq output is done AND irq_en, a level cleared by writing 1 to STATUS.done. The DMA only masters the RAM; addresses are taken modulo 64 KB.

## SYS (0x1000_3000)

| Offset | Name | Access | Description |
|---|---|---|---|
| 0x0 | EXIT | W | any write ends the simulation, the written value is the process exit code |

## Interrupts

| irq bit | Source |
|---|---|
| 0 | timer |
| 1 | dma |

PicoRV32's internal timer is disabled (ENABLE_IRQ_TIMER = 0), so bit 0 is free. Bit 1 is also the core's ebreak/illegal-instruction interrupt, see the README limitations.
