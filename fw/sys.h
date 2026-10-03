#ifndef SYS_H
#define SYS_H

#include <stddef.h>
#include <stdint.h>
#include "soc.h"

typedef struct {
    volatile uint32_t exit_code;
} sys_regs_t;

_Static_assert(offsetof(sys_regs_t, exit_code) == SYS_EXIT_OFFSET, "sys exit offset");

#define SYS ((sys_regs_t *)SYS_BASE)

void sys_exit(int code) __attribute__((noreturn));

#endif
