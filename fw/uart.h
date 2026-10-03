#ifndef UART_H
#define UART_H

#include <stddef.h>
#include <stdint.h>
#include "soc.h"

typedef struct {
    volatile uint32_t data;
    volatile uint32_t status;
    volatile uint32_t baud;
} uart_regs_t;

_Static_assert(offsetof(uart_regs_t, data) == UART_DATA_OFFSET, "uart data offset");
_Static_assert(offsetof(uart_regs_t, status) == UART_STATUS_OFFSET, "uart status offset");
_Static_assert(offsetof(uart_regs_t, baud) == UART_BAUD_OFFSET, "uart baud offset");

#define UART ((uart_regs_t *)UART_BASE)

void uart_init(void);
void uart_putc(char c);
void uart_puts(const char *s);
int uart_getc(void);
void uart_put_hex(uint32_t value);
void uart_put_dec(uint32_t value);

#endif
