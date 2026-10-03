OUTPUT_ARCH(riscv)
ENTRY(_start)

MEMORY
{
    rom (rx)  : ORIGIN = 0x00000000, LENGTH = 32K
    ram (rwx) : ORIGIN = 0x00008000, LENGTH = 32K
}

SECTIONS
{
    .text : ALIGN(4)
    {
        KEEP(*(.vectors))
        *(.text*)
    } > rom

    .rodata : ALIGN(4)
    {
        *(.rodata*)
        *(.srodata*)
    } > rom

    .data : ALIGN(4)
    {
        _sdata = .;
        *(.data*)
        *(.sdata*)
        . = ALIGN(4);
        _edata = .;
    } > ram AT > rom

    _sidata = LOADADDR(.data);

    .bss (NOLOAD) : ALIGN(4)
    {
        _sbss = .;
        *(.bss*)
        *(.sbss*)
        *(COMMON)
        . = ALIGN(4);
        _ebss = .;
    } > ram

    _stack_top = ORIGIN(ram) + LENGTH(ram);

    /DISCARD/ : { *(.comment) *(.note*) *(.eh_frame*) }
}
