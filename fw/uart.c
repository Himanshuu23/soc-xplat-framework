#include "uart.h"

void uart_init(void)
{
    UART->baud = UART_BAUD_DIV;
}

void uart_putc(char c)
{
    while (UART->status & UART_STATUS_TX_BUSY_MASK) {
    }
    UART->data = (uint8_t)c;
}

void uart_puts(const char *s)
{
    while (*s)
        uart_putc(*s++);
}

int uart_getc(void)
{
    while (!(UART->status & UART_STATUS_RX_VALID_MASK)) {
    }
    return UART->data & 0xff;
}

void uart_put_hex(uint32_t value)
{
    for (int shift = 28; shift >= 0; shift -= 4)
        uart_putc("0123456789abcdef"[(value >> shift) & 0xf]);
}

void uart_put_dec(uint32_t value)
{
    char digits[10];
    int n = 0;
    do {
        digits[n++] = (char)('0' + value % 10);
        value /= 10;
    } while (value);
    while (n--)
        uart_putc(digits[n]);
}
