#include <stdint.h>
#include "sys.h"
#include "uart.h"

#define LINE_MAX 48

static int read_line(char *buf)
{
    int n = 0;
    for (;;) {
        char c = (char)uart_getc();
        if (c == '\n' || c == '\r') {
            buf[n] = 0;
            return n;
        }
        if (n < LINE_MAX - 1)
            buf[n++] = c;
    }
}

static const char *skip_spaces(const char *p)
{
    while (*p == ' ')
        p++;
    return p;
}

static const char *parse_hex(const char *p, uint32_t *value)
{
    p = skip_spaces(p);
    if (p[0] == '0' && (p[1] == 'x' || p[1] == 'X'))
        p += 2;
    const char *start = p;
    uint32_t v = 0;
    for (;; p++) {
        char c = *p;
        if (c >= '0' && c <= '9')
            v = (v << 4) | (uint32_t)(c - '0');
        else if (c >= 'a' && c <= 'f')
            v = (v << 4) | (uint32_t)(c - 'a' + 10);
        else if (c >= 'A' && c <= 'F')
            v = (v << 4) | (uint32_t)(c - 'A' + 10);
        else
            break;
    }
    if (p == start)
        return 0;
    *value = v;
    return p;
}

static void reply_hex(uint32_t value)
{
    uart_put_hex(value);
    uart_putc('\n');
}

static void command(const char *line)
{
    uint32_t addr, value;
    const char *p = skip_spaces(line + 1);

    if (line[0] == 'R') {
        p = parse_hex(p, &addr);
        if (!p || (addr & 3))
            goto error;
        reply_hex(*(volatile uint32_t *)addr);
    } else if (line[0] == 'W') {
        p = parse_hex(p, &addr);
        if (!p || (addr & 3))
            goto error;
        p = parse_hex(p, &value);
        if (!p)
            goto error;
        *(volatile uint32_t *)addr = value;
        uart_puts("OK\n");
    } else if (line[0] == 'P') {
        uart_puts("OK\n");
    } else if (line[0] == 'Q') {
        uart_puts("BYE\n");
        sys_exit(0);
    } else {
        goto error;
    }
    return;

error:
    uart_puts("ERR\n");
}

int main(void)
{
    char line[LINE_MAX];

    uart_init();
    uart_puts("READY\n");
    for (;;) {
        if (read_line(line))
            command(line);
    }
}
