#include "uart.h"
#include "test.h"

int main(void)
{
    test_begin("uart_hello");

    uart_puts("Hello from PicoRV32!\n");
    uart_puts("hex: 0x");
    uart_put_hex(0xdeadbeef);
    uart_puts(" dec: ");
    uart_put_dec(1234567);
    uart_putc('\n');

    check("baud register reads back", UART->baud == UART_BAUD_DIV);
    check("tx busy right after write", (UART->status & UART_STATUS_TX_BUSY_MASK) != 0);
    while (UART->status & UART_STATUS_TX_BUSY_MASK) {
    }
    check("tx idle after drain", (UART->status & UART_STATUS_TX_BUSY_MASK) == 0);
    check("rx empty with no input", (UART->status & UART_STATUS_RX_VALID_MASK) == 0);

    test_end();
}
