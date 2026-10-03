from gen import regs
from xplat.framework import expect_eq, register
from xplat.hal.base import Backend


@register("reg_reset_values", "every register reads its spec reset value after reset")
def reg_reset_values(b: Backend, log) -> None:
    b.write("TIMER.COMPARE", 5)
    b.write("TIMER.COUNT", 0x77)
    b.write("TIMER.CTRL", 0b111)
    b.write("DMA.SRC", 0x12345678)
    b.write("DMA.DST", 0x9ABCDEF0)
    b.write("DMA.LEN", 0x42)
    b.write("DMA.CTRL", 0b10)

    b.reset()

    checked = 0
    for key, reg in regs.REGISTERS.items():
        if reg.access == "SPECIAL":
            continue
        expect_eq("%s reset value" % key, b.read(key), reg.reset, reg.address)
        checked += 1
    log("checked %d registers" % checked)
