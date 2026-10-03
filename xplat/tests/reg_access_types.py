from typing import List

from gen import regs
from xplat.framework import expect_eq, expect_true, register
from xplat.hal.base import Backend

WALK_PATTERNS = (0xFFFFFFFF, 0x00000000, 0x55555555, 0xAAAAAAAA)
POLLS = 30


def field_mask(reg: regs.Register, access: str) -> int:
    mask = 0
    for f in reg.fields:
        if f.access == access:
            mask |= f.mask
    return mask


def check_rw(b: Backend, reg: regs.Register) -> None:
    mask = field_mask(reg, "RW")
    if not mask:
        return
    values: List[int] = list(reg.test_values) or [p & mask for p in WALK_PATTERNS]
    for value in values:
        b.write(reg.key, value)
        expect_eq("%s RW readback after writing 0x%x" % (reg.key, value), b.read(reg.key) & mask, value & mask, reg.address)
    b.write(reg.key, reg.reset & mask)


def check_ro(b: Backend, reg: regs.Register) -> None:
    mask = field_mask(reg, "RO")
    if not mask:
        return
    before = b.read(reg.key) & mask
    b.write(reg.key, mask)
    expect_eq("%s RO bits after write of ones" % reg.key, b.read(reg.key) & mask, before, reg.address)


def check_w1c(b: Backend, reg: regs.Register, fld: regs.Field) -> None:
    where = "%s.%s" % (reg.key, fld.name)
    for name, value in fld.trigger:
        b.write(name, value)
    for _ in range(POLLS):
        if b.read(reg.key) & fld.mask:
            break
    expect_true("%s set by its trigger" % where, bool(b.read(reg.key) & fld.mask))
    for name, value in fld.cleanup:
        b.write(name, value)
    b.write(reg.key, 0)
    expect_eq("%s after writing 0" % where, b.read(reg.key) & fld.mask, fld.mask, reg.address)
    b.write(reg.key, fld.mask)
    expect_eq("%s after writing 1" % where, b.read(reg.key) & fld.mask, 0, reg.address)
    b.write(reg.key, fld.mask)
    expect_eq("%s after writing 1 again" % where, b.read(reg.key) & fld.mask, 0, reg.address)


def check_wo(b: Backend, reg: regs.Register) -> None:
    mask = field_mask(reg, "WO")
    if not mask:
        return
    b.write(reg.key, mask)
    expect_eq("%s WO bits read back" % reg.key, b.read(reg.key) & mask, 0, reg.address)


@register("reg_access_types", "RW read back, RO ignore writes, W1C clear only on 1, WO read as zero")
def reg_access_types(b: Backend, log) -> None:
    registers = [r for r in regs.REGISTERS.values() if r.access != "SPECIAL"]
    for reg in registers:
        check_rw(b, reg)
    for reg in registers:
        check_ro(b, reg)
    for reg in registers:
        for fld in reg.fields:
            if fld.access == "W1C":
                check_w1c(b, reg, fld)
                b.reset()
    for reg in registers:
        check_wo(b, reg)
    b.reset()
    log("checked %d registers" % len(registers))
