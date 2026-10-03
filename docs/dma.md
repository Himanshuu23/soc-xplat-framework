# DMA

The source has no comments, this is the explanation.

## Programming model

    DMA->src = src_address;
    DMA->dst = dst_address;
    DMA->len = words;
    DMA->ctrl = DMA_CTRL_START | DMA_CTRL_IRQ_EN;
    wait for STATUS.done, by polling or by the irq
    write 1 to STATUS.done

Register layout is in memory_map.md. fw/dma.c wraps this in dma_start, dma_wait and dma_isr.

## State machine

    IDLE  --start, len>0-->  READ  --ack-->  WRITE  --ack, words left-->  READ
                                               |
                                               +--ack, last word--> IDLE, done=1, busy=0

- IDLE: on a CTRL write with start set, latch SRC and DST into working copies and LEN into a counter. LEN = 0 sets done and stays idle.
- READ: ask the RAM for the word at the source address. When the acknowledge comes back, the data is sitting on the RAM read port and is captured into a holding register.
- WRITE: write the held word to the destination address. On acknowledge, advance both addresses by 4 and decrement the counter.

The transfer runs on the working copies. Writes to SRC, DST and LEN while busy are ignored on purpose, so a half-written descriptor cannot corrupt a running copy.

## One word costs four cycles

Cycle 0 request read (granted), cycle 1 acknowledge, cycle 2 request write (granted), cycle 3 acknowledge. The RAM has a single port with a registered read, so a request is granted in one cycle and its data or completion is seen in the next.

## Sharing the RAM with the CPU

The RAM has one port. Both the CPU (instruction fetches and data) and the DMA want it. soc_top.v arbitrates:

- A master is granted at most once per request: it must wait for its own acknowledge before asking again, which prevents a double access while the old request is still shown.
- If only one master is requesting it wins.
- If both request in the same cycle, a one-bit register remembers who won last and the other one goes first. That alternates grants.

The CPU is never starved by a long copy, and the DMA is never starved by a busy CPU. The cost is that both slow down: the testbench measures 64 words in about 397 cycles with the CPU running a polling loop, compared with 256 if the DMA owned the RAM.

Accesses to peripheral registers by the CPU (including the DMA's own registers) do not use the RAM port, so polling STATUS only competes through instruction fetches.

## Interrupt

The irq output is done AND CTRL.irq_en, a level wired to CPU irq bit 1. It drops when software writes 1 to STATUS.done, which dma_isr does.

## Limits

- Word copies only, source and destination must be word aligned (low two bits are ignored).
- RAM to RAM only, addresses wrap modulo 64 KB, no error flag.
- Overlapping ranges are copied forward word by word, so overlap is only safe when the destination is below the source.
