#include "test.h"
#include "sys.h"
#include "uart.h"

static const char *test_name;
static int failures;

void test_begin(const char *name)
{
    test_name = name;
    uart_init();
    uart_puts("[");
    uart_puts(name);
    uart_puts("] start\n");
}

void check(const char *what, int condition)
{
    uart_puts(condition ? "  ok   " : "  FAIL ");
    uart_puts(what);
    uart_putc('\n');
    if (!condition)
        failures++;
}

void test_end(void)
{
    uart_puts(failures ? "FAIL " : "PASS ");
    uart_puts(test_name);
    uart_putc('\n');
    sys_exit(failures ? 1 : 0);
}
