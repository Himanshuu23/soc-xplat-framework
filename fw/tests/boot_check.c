#include <stdint.h>
#include "soc.h"
#include "test.h"

extern uint32_t _sdata, _edata, _sbss, _ebss, _stack_top;

#define RAM_POISON 0xdeadbeefu

int data_word = 0x1234abcd;
uint8_t data_bytes[8] = {1, 2, 3, 4, 5, 6, 7, 8};
const char rodata_text[] = "rodata";
static int bss_word;
static uint32_t bss_words[256];

static int bss_array_clean(void)
{
    for (int i = 0; i < 256; i++) {
        if (bss_words[i] != 0 || bss_words[i] == RAM_POISON)
            return 0;
    }
    return 1;
}

int main(void)
{
    test_begin("boot_check");

    check(".data word initialised", data_word == 0x1234abcd);
    int bytes_ok = 1;
    for (int i = 0; i < 8; i++) {
        if (data_bytes[i] != i + 1)
            bytes_ok = 0;
    }
    check(".data array initialised", bytes_ok);
    check(".rodata readable", rodata_text[0] == 'r' && rodata_text[5] == 'a');

    check(".bss scalar is zero", bss_word == 0);
    check(".bss array is zero and unpoisoned", bss_array_clean());

    check(".data lives in RAM", (uint32_t)&_sdata >= 0x8000 && (uint32_t)&_edata <= RAM_SIZE);
    check(".bss lives in RAM", (uint32_t)&_sbss >= (uint32_t)&_edata && (uint32_t)&_ebss <= RAM_SIZE);
    check("stack top is end of RAM", (uint32_t)&_stack_top == RAM_SIZE);

    int local;
    check("stack pointer inside RAM", (uint32_t)&local < RAM_SIZE && (uint32_t)&local >= (uint32_t)&_ebss);

    data_word = 7;
    bss_word = 9;
    check("data and bss are writable", data_word == 7 && bss_word == 9);

    test_end();
}
