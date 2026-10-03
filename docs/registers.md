# Register reference

_generated from spec/registers.yaml by tools/gen_regs.py, do not edit_

| Region | Base | Size |
|---|---|---|
| RAM | 0x00000000 | 64 KB |
| UART | 0x10000000 | 4 KB |
| TIMER | 0x10001000 | 4 KB |
| DMA | 0x10002000 | 4 KB |
| SYS | 0x10003000 | 4 KB |

Access types: RW read/write, RO read only, WO write only (reads 0), W1C write 1 to clear, SPECIAL side effects on read or write.

## UART (0x10000000)

8N1 serial port, one byte RX buffer, no FIFO

| Offset | Register | Reset | Description |
|---|---|---|---|
| 0x0 | DATA | 0x00000000 | write sends the low byte, read returns the last received byte and clears RX_VALID |
| 0x4 | STATUS | 0x00000000 | link status |
| 0x8 | BAUD | 0x00000010 | clock cycles per bit |

### UART.DATA

| Bits | Field | Access | Description |
|---|---|---|---|
| 7:0 | BYTE | SPECIAL | transmit or receive byte |

### UART.STATUS

| Bits | Field | Access | Description |
|---|---|---|---|
| 0 | TX_BUSY | RO | a byte is being shifted out |
| 1 | RX_VALID | RO | a received byte is waiting in DATA |

### UART.BAUD

| Bits | Field | Access | Description |
|---|---|---|---|
| 15:0 | DIVISOR | RW | clock cycles per bit |

## TIMER (0x10001000)

32-bit free-running counter with compare match

| Offset | Register | Reset | Description |
|---|---|---|---|
| 0x0 | COUNT | 0x00000000 | counter, increments every clock while enabled |
| 0x4 | COMPARE | 0xffffffff | match value |
| 0x8 | CTRL | 0x00000000 | control |
| 0xc | STATUS | 0x00000000 | status |

### TIMER.COUNT

| Bits | Field | Access | Description |
|---|---|---|---|
| 31:0 | VALUE | RW | current count |

### TIMER.COMPARE

| Bits | Field | Access | Description |
|---|---|---|---|
| 31:0 | VALUE | RW | value that sets MATCH when COUNT reaches it |

### TIMER.CTRL

| Bits | Field | Access | Description |
|---|---|---|---|
| 0 | ENABLE | RW | counter runs |
| 1 | IRQ_EN | RW | MATCH drives the irq line |
| 2 | RELOAD | RW | COUNT returns to 0 after a match |

### TIMER.STATUS

| Bits | Field | Access | Description |
|---|---|---|---|
| 0 | MATCH | W1C | COUNT reached COMPARE, cleared by writing 1 |

## DMA (0x10002000)

word copy engine, RAM to RAM

| Offset | Register | Reset | Description |
|---|---|---|---|
| 0x0 | SRC | 0x00000000 | source byte address, writes ignored while BUSY |
| 0x4 | DST | 0x00000000 | destination byte address, writes ignored while BUSY |
| 0x8 | LEN | 0x00000000 | transfer length in words, writes ignored while BUSY |
| 0xc | CTRL | 0x00000000 | control |
| 0x10 | STATUS | 0x00000000 | status |

### DMA.SRC

| Bits | Field | Access | Description |
|---|---|---|---|
| 31:0 | ADDR | RW | source address |

### DMA.DST

| Bits | Field | Access | Description |
|---|---|---|---|
| 31:0 | ADDR | RW | destination address |

### DMA.LEN

| Bits | Field | Access | Description |
|---|---|---|---|
| 31:0 | WORDS | RW | number of 32-bit words |

### DMA.CTRL

| Bits | Field | Access | Description |
|---|---|---|---|
| 0 | START | WO | begin the transfer |
| 1 | IRQ_EN | RW | DONE drives the irq line |

### DMA.STATUS

| Bits | Field | Access | Description |
|---|---|---|---|
| 0 | BUSY | RO | a transfer is running |
| 1 | DONE | W1C | transfer finished, sticky until cleared by writing 1 |

## SYS (0x10003000)

simulation control

| Offset | Register | Reset | Description |
|---|---|---|---|
| 0x0 | EXIT | 0x00000000 | any write ends the simulation, the value is the process exit code |

### SYS.EXIT

| Bits | Field | Access | Description |
|---|---|---|---|
| 31:0 | CODE | SPECIAL | exit code |

## Interrupts

The irq line of each source is its status flag AND its enable bit.

| Bit | Name | Status flag | Enable |
|---|---|---|---|
| 0 | timer | TIMER.STATUS.MATCH | TIMER.CTRL.IRQ_EN |
| 1 | dma | DMA.STATUS.DONE | DMA.CTRL.IRQ_EN |
