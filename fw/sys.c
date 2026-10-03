#include "sys.h"
#include "uart.h"

void sys_exit(int code)
{
    while (UART->status & UART_STATUS_TX_BUSY_MASK) {
    }
    SYS->exit_code = (uint32_t)code;
    for (;;) {
    }
}
