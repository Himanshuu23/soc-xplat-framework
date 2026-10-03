// generated from spec/registers.yaml by tools/gen_regs.py, do not edit
package soc_regs_pkg;

    localparam logic [31:0] RAM_BASE = 32'h00000000;
    localparam logic [31:0] RAM_SIZE = 32'h00010000;

    localparam logic [31:0] UART_BASE = 32'h10000000;
    localparam logic [31:0] UART_DATA_OFFSET = 32'h00000000;
    localparam logic [31:0] UART_DATA_RESET = 32'h00000000;
    localparam int UART_DATA_BYTE_LSB = 0;
    localparam int UART_DATA_BYTE_MSB = 7;
    localparam logic [31:0] UART_DATA_BYTE_MASK = 32'h000000ff;
    localparam logic [31:0] UART_STATUS_OFFSET = 32'h00000004;
    localparam logic [31:0] UART_STATUS_RESET = 32'h00000000;
    localparam int UART_STATUS_TX_BUSY_LSB = 0;
    localparam int UART_STATUS_TX_BUSY_MSB = 0;
    localparam logic [31:0] UART_STATUS_TX_BUSY_MASK = 32'h00000001;
    localparam int UART_STATUS_RX_VALID_LSB = 1;
    localparam int UART_STATUS_RX_VALID_MSB = 1;
    localparam logic [31:0] UART_STATUS_RX_VALID_MASK = 32'h00000002;
    localparam logic [31:0] UART_BAUD_OFFSET = 32'h00000008;
    localparam logic [31:0] UART_BAUD_RESET = 32'h00000010;
    localparam int UART_BAUD_DIVISOR_LSB = 0;
    localparam int UART_BAUD_DIVISOR_MSB = 15;
    localparam logic [31:0] UART_BAUD_DIVISOR_MASK = 32'h0000ffff;

    localparam logic [31:0] TIMER_BASE = 32'h10001000;
    localparam logic [31:0] TIMER_COUNT_OFFSET = 32'h00000000;
    localparam logic [31:0] TIMER_COUNT_RESET = 32'h00000000;
    localparam int TIMER_COUNT_VALUE_LSB = 0;
    localparam int TIMER_COUNT_VALUE_MSB = 31;
    localparam logic [31:0] TIMER_COUNT_VALUE_MASK = 32'hffffffff;
    localparam logic [31:0] TIMER_COMPARE_OFFSET = 32'h00000004;
    localparam logic [31:0] TIMER_COMPARE_RESET = 32'hffffffff;
    localparam int TIMER_COMPARE_VALUE_LSB = 0;
    localparam int TIMER_COMPARE_VALUE_MSB = 31;
    localparam logic [31:0] TIMER_COMPARE_VALUE_MASK = 32'hffffffff;
    localparam logic [31:0] TIMER_CTRL_OFFSET = 32'h00000008;
    localparam logic [31:0] TIMER_CTRL_RESET = 32'h00000000;
    localparam int TIMER_CTRL_ENABLE_LSB = 0;
    localparam int TIMER_CTRL_ENABLE_MSB = 0;
    localparam logic [31:0] TIMER_CTRL_ENABLE_MASK = 32'h00000001;
    localparam int TIMER_CTRL_IRQ_EN_LSB = 1;
    localparam int TIMER_CTRL_IRQ_EN_MSB = 1;
    localparam logic [31:0] TIMER_CTRL_IRQ_EN_MASK = 32'h00000002;
    localparam int TIMER_CTRL_RELOAD_LSB = 2;
    localparam int TIMER_CTRL_RELOAD_MSB = 2;
    localparam logic [31:0] TIMER_CTRL_RELOAD_MASK = 32'h00000004;
    localparam logic [31:0] TIMER_STATUS_OFFSET = 32'h0000000c;
    localparam logic [31:0] TIMER_STATUS_RESET = 32'h00000000;
    localparam int TIMER_STATUS_MATCH_LSB = 0;
    localparam int TIMER_STATUS_MATCH_MSB = 0;
    localparam logic [31:0] TIMER_STATUS_MATCH_MASK = 32'h00000001;

    localparam logic [31:0] DMA_BASE = 32'h10002000;
    localparam logic [31:0] DMA_SRC_OFFSET = 32'h00000000;
    localparam logic [31:0] DMA_SRC_RESET = 32'h00000000;
    localparam int DMA_SRC_ADDR_LSB = 0;
    localparam int DMA_SRC_ADDR_MSB = 31;
    localparam logic [31:0] DMA_SRC_ADDR_MASK = 32'hffffffff;
    localparam logic [31:0] DMA_DST_OFFSET = 32'h00000004;
    localparam logic [31:0] DMA_DST_RESET = 32'h00000000;
    localparam int DMA_DST_ADDR_LSB = 0;
    localparam int DMA_DST_ADDR_MSB = 31;
    localparam logic [31:0] DMA_DST_ADDR_MASK = 32'hffffffff;
    localparam logic [31:0] DMA_LEN_OFFSET = 32'h00000008;
    localparam logic [31:0] DMA_LEN_RESET = 32'h00000000;
    localparam int DMA_LEN_WORDS_LSB = 0;
    localparam int DMA_LEN_WORDS_MSB = 31;
    localparam logic [31:0] DMA_LEN_WORDS_MASK = 32'hffffffff;
    localparam logic [31:0] DMA_CTRL_OFFSET = 32'h0000000c;
    localparam logic [31:0] DMA_CTRL_RESET = 32'h00000000;
    localparam int DMA_CTRL_START_LSB = 0;
    localparam int DMA_CTRL_START_MSB = 0;
    localparam logic [31:0] DMA_CTRL_START_MASK = 32'h00000001;
    localparam int DMA_CTRL_IRQ_EN_LSB = 1;
    localparam int DMA_CTRL_IRQ_EN_MSB = 1;
    localparam logic [31:0] DMA_CTRL_IRQ_EN_MASK = 32'h00000002;
    localparam logic [31:0] DMA_STATUS_OFFSET = 32'h00000010;
    localparam logic [31:0] DMA_STATUS_RESET = 32'h00000000;
    localparam int DMA_STATUS_BUSY_LSB = 0;
    localparam int DMA_STATUS_BUSY_MSB = 0;
    localparam logic [31:0] DMA_STATUS_BUSY_MASK = 32'h00000001;
    localparam int DMA_STATUS_DONE_LSB = 1;
    localparam int DMA_STATUS_DONE_MSB = 1;
    localparam logic [31:0] DMA_STATUS_DONE_MASK = 32'h00000002;

    localparam logic [31:0] SYS_BASE = 32'h10003000;
    localparam logic [31:0] SYS_EXIT_OFFSET = 32'h00000000;
    localparam logic [31:0] SYS_EXIT_RESET = 32'h00000000;
    localparam int SYS_EXIT_CODE_LSB = 0;
    localparam int SYS_EXIT_CODE_MSB = 31;
    localparam logic [31:0] SYS_EXIT_CODE_MASK = 32'hffffffff;

    localparam int IRQ_TIMER_BIT = 0;
    localparam int IRQ_DMA_BIT = 1;

endpackage
