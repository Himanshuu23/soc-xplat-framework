#!/usr/bin/env python3
import argparse
import os
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPEC = os.path.join(ROOT, "spec", "registers.yaml")

ACCESS_TYPES = ("RW", "RO", "WO", "W1C", "SPECIAL")
BANNER = "generated from spec/registers.yaml by tools/gen_regs.py, do not edit"


@dataclass
class FieldSpec:
    name: str
    msb: int
    lsb: int
    access: str
    description: str
    trigger: List[Tuple[str, int]] = field(default_factory=list)
    cleanup: List[Tuple[str, int]] = field(default_factory=list)

    @property
    def mask(self) -> int:
        return ((1 << (self.msb - self.lsb + 1)) - 1) << self.lsb


@dataclass
class RegSpec:
    periph: str
    name: str
    offset: int
    reset: int
    access: str
    description: str
    test_values: List[int]
    fields: List[FieldSpec]

    @property
    def key(self) -> str:
        return "%s.%s" % (self.periph, self.name)


@dataclass
class PeriphSpec:
    name: str
    base: int
    description: str
    registers: List[RegSpec]


@dataclass
class IrqSpec:
    name: str
    bit: int
    status: str
    enable: str


@dataclass
class Spec:
    memory: Dict[str, int]
    peripherals: List[PeriphSpec]
    irqs: List[IrqSpec]

    def registers(self) -> List[RegSpec]:
        return [r for p in self.peripherals for r in p.registers]

    def find_field(self, dotted: str) -> Tuple[RegSpec, FieldSpec]:
        periph, reg, fld = dotted.split(".")
        for r in self.registers():
            if r.key == "%s.%s" % (periph, reg):
                for f in r.fields:
                    if f.name == fld:
                        return r, f
        raise SpecError("unknown field %s" % dotted)


class SpecError(Exception):
    pass


def parse_bits(text: str) -> Tuple[int, int]:
    parts = str(text).split(":")
    msb = int(parts[0])
    lsb = int(parts[-1])
    if msb < lsb or msb > 31 or lsb < 0:
        raise SpecError("bad bit range %r" % text)
    return msb, lsb


def parse_steps(items: Optional[list]) -> List[Tuple[str, int]]:
    return [(str(name), int(value)) for name, value in (items or [])]


def load_spec(path: str = SPEC) -> Spec:
    with open(path) as f:
        raw = yaml.safe_load(f)

    peripherals: List[PeriphSpec] = []
    for pname, p in raw["peripherals"].items():
        regs: List[RegSpec] = []
        for r in p["registers"]:
            fields = [
                FieldSpec(
                    name=f["name"],
                    msb=parse_bits(f["bits"])[0],
                    lsb=parse_bits(f["bits"])[1],
                    access=f["access"],
                    description=f.get("description", ""),
                    trigger=parse_steps(f.get("trigger")),
                    cleanup=parse_steps(f.get("cleanup")),
                )
                for f in r["fields"]
            ]
            regs.append(
                RegSpec(
                    periph=pname,
                    name=r["name"],
                    offset=r["offset"],
                    reset=r["reset"],
                    access=r.get("access", ""),
                    description=r.get("description", ""),
                    test_values=list(r.get("test_values", [])),
                    fields=fields,
                )
            )
        peripherals.append(PeriphSpec(pname, p["base"], p.get("description", ""), regs))

    irqs = [IrqSpec(i["name"], i["bit"], i["status"], i["enable"]) for i in raw["irqs"]]
    spec = Spec(memory=dict(raw["memory"]), peripherals=peripherals, irqs=irqs)
    validate(spec)
    return spec


def validate(spec: Spec) -> None:
    seen_bases = set()
    for p in spec.peripherals:
        if p.base in seen_bases:
            raise SpecError("duplicate base 0x%08x" % p.base)
        seen_bases.add(p.base)
        offsets = set()
        for r in p.registers:
            if r.offset % 4:
                raise SpecError("%s offset not word aligned" % r.key)
            if r.offset in offsets:
                raise SpecError("%s duplicate offset" % r.key)
            offsets.add(r.offset)
            if not 0 <= r.reset <= 0xFFFFFFFF:
                raise SpecError("%s reset out of range" % r.key)
            used = 0
            for f in r.fields:
                if f.access not in ACCESS_TYPES:
                    raise SpecError("%s.%s bad access %s" % (r.key, f.name, f.access))
                if used & f.mask:
                    raise SpecError("%s.%s overlaps another field" % (r.key, f.name))
                used |= f.mask
            if r.reset & ~used:
                raise SpecError("%s reset sets bits outside any field" % r.key)
    for irq in spec.irqs:
        spec.find_field(irq.status)
        spec.find_field(irq.enable)
    keys = {r.key for r in spec.registers()}
    for r in spec.registers():
        for f in r.fields:
            for name, _ in f.trigger + f.cleanup:
                if name not in keys:
                    raise SpecError("%s.%s refers to unknown register %s" % (r.key, f.name, name))


def hexs(value: int) -> str:
    return "0x%08x" % value


def gen_c_header(spec: Spec) -> str:
    out: List[str] = []
    out.append("/* %s */" % BANNER)
    out.append("#ifndef REGS_H")
    out.append("#define REGS_H")
    out.append("")
    out.append("#define RAM_BASE %s" % hexs(spec.memory["ram_base"]))
    out.append("#define RAM_SIZE %s" % hexs(spec.memory["ram_size"]))
    out.append("")
    for p in spec.peripherals:
        out.append("#define %s_BASE %s" % (p.name, hexs(p.base)))
    for p in spec.peripherals:
        out.append("")
        for r in p.registers:
            prefix = "%s_%s" % (p.name, r.name)
            out.append("#define %s_OFFSET 0x%x" % (prefix, r.offset))
            out.append("#define %s_ADDR (%s_BASE + %s_OFFSET)" % (prefix, p.name, prefix))
            out.append("#define %s_RESET %s" % (prefix, hexs(r.reset)))
            for f in r.fields:
                fp = "%s_%s" % (prefix, f.name)
                out.append("#define %s_SHIFT %d" % (fp, f.lsb))
                out.append("#define %s_MASK %s" % (fp, hexs(f.mask)))
    out.append("")
    for irq in spec.irqs:
        out.append("#define IRQ_%s_BIT %d" % (irq.name.upper(), irq.bit))
        out.append("#define IRQ_%s (1 << IRQ_%s_BIT)" % (irq.name.upper(), irq.name.upper()))
    out.append("")
    out.append("#endif")
    return "\n".join(out) + "\n"


def gen_sv_package(spec: Spec) -> str:
    out: List[str] = []
    out.append("// %s" % BANNER)
    out.append("package soc_regs_pkg;")
    out.append("")
    out.append("    localparam logic [31:0] RAM_BASE = 32'h%08x;" % spec.memory["ram_base"])
    out.append("    localparam logic [31:0] RAM_SIZE = 32'h%08x;" % spec.memory["ram_size"])
    for p in spec.peripherals:
        out.append("")
        out.append("    localparam logic [31:0] %s_BASE = 32'h%08x;" % (p.name, p.base))
        for r in p.registers:
            prefix = "%s_%s" % (p.name, r.name)
            out.append("    localparam logic [31:0] %s_OFFSET = 32'h%08x;" % (prefix, r.offset))
            out.append("    localparam logic [31:0] %s_RESET = 32'h%08x;" % (prefix, r.reset))
            for f in r.fields:
                fp = "%s_%s" % (prefix, f.name)
                out.append("    localparam int %s_LSB = %d;" % (fp, f.lsb))
                out.append("    localparam int %s_MSB = %d;" % (fp, f.msb))
                out.append("    localparam logic [31:0] %s_MASK = 32'h%08x;" % (fp, f.mask))
    out.append("")
    for irq in spec.irqs:
        out.append("    localparam int IRQ_%s_BIT = %d;" % (irq.name.upper(), irq.bit))
    out.append("")
    out.append("endpackage")
    return "\n".join(out) + "\n"


def py_steps(steps: List[Tuple[str, int]]) -> str:
    return "(" + "".join("(%r, %d), " % (n, v) for n, v in steps) + ")"


def gen_py_module(spec: Spec) -> str:
    out: List[str] = []
    out.append("# %s" % BANNER)
    out.append("from dataclasses import dataclass")
    out.append("from typing import Dict, Tuple")
    out.append("")
    out.append("")
    out.append("@dataclass(frozen=True)")
    out.append("class Field:")
    out.append("    name: str")
    out.append("    msb: int")
    out.append("    lsb: int")
    out.append("    access: str")
    out.append("    description: str")
    out.append("    trigger: Tuple[Tuple[str, int], ...] = ()")
    out.append("    cleanup: Tuple[Tuple[str, int], ...] = ()")
    out.append("")
    out.append("    @property")
    out.append("    def mask(self) -> int:")
    out.append("        return ((1 << (self.msb - self.lsb + 1)) - 1) << self.lsb")
    out.append("")
    out.append("")
    out.append("@dataclass(frozen=True)")
    out.append("class Register:")
    out.append("    periph: str")
    out.append("    name: str")
    out.append("    offset: int")
    out.append("    address: int")
    out.append("    reset: int")
    out.append("    access: str")
    out.append("    description: str")
    out.append("    test_values: Tuple[int, ...]")
    out.append("    fields: Tuple[Field, ...]")
    out.append("")
    out.append("    @property")
    out.append("    def key(self) -> str:")
    out.append('        return "%s.%s" % (self.periph, self.name)')
    out.append("")
    out.append("    def field(self, name: str) -> Field:")
    out.append("        for f in self.fields:")
    out.append("            if f.name == name:")
    out.append("                return f")
    out.append('        raise KeyError("%s.%s" % (self.key, name))')
    out.append("")
    out.append("")
    out.append("@dataclass(frozen=True)")
    out.append("class Irq:")
    out.append("    name: str")
    out.append("    bit: int")
    out.append("    status: str")
    out.append("    enable: str")
    out.append("")
    out.append("")
    out.append("MEMORY: Dict[str, int] = {")
    for k, v in spec.memory.items():
        out.append("    %r: %s," % (k, hexs(v)))
    out.append("}")
    out.append("")
    out.append("BASES: Dict[str, int] = {")
    for p in spec.peripherals:
        out.append("    %r: %s," % (p.name, hexs(p.base)))
    out.append("}")
    out.append("")
    out.append("REGISTERS: Dict[str, Register] = {}")
    out.append("")
    for p in spec.peripherals:
        for r in p.registers:
            out.append("REGISTERS[%r] = Register(" % r.key)
            out.append("    periph=%r," % r.periph)
            out.append("    name=%r," % r.name)
            out.append("    offset=0x%x," % r.offset)
            out.append("    address=%s," % hexs(p.base + r.offset))
            out.append("    reset=%s," % hexs(r.reset))
            out.append("    access=%r," % r.access)
            out.append("    description=%r," % r.description)
            out.append("    test_values=(%s)," % "".join("%s, " % hexs(v) for v in r.test_values))
            out.append("    fields=(")
            for f in r.fields:
                out.append(
                    "        Field(%r, %d, %d, %r, %r, %s, %s),"
                    % (f.name, f.msb, f.lsb, f.access, f.description, py_steps(f.trigger), py_steps(f.cleanup))
                )
            out.append("    ),")
            out.append(")")
            out.append("")
    out.append("IRQS: Dict[str, Irq] = {")
    for i in spec.irqs:
        out.append("    %r: Irq(%r, %d, %r, %r)," % (i.name, i.name, i.bit, i.status, i.enable))
    out.append("}")
    out.append("")
    out.append("BY_ADDRESS: Dict[int, Register] = {r.address: r for r in REGISTERS.values()}")
    return "\n".join(out) + "\n"


def gen_markdown(spec: Spec) -> str:
    out: List[str] = []
    out.append("# Register reference")
    out.append("")
    out.append("_%s_" % BANNER)
    out.append("")
    out.append("| Region | Base | Size |")
    out.append("|---|---|---|")
    out.append("| RAM | %s | %d KB |" % (hexs(spec.memory["ram_base"]), spec.memory["ram_size"] // 1024))
    for p in spec.peripherals:
        out.append("| %s | %s | 4 KB |" % (p.name, hexs(p.base)))
    out.append("")
    out.append("Access types: RW read/write, RO read only, WO write only (reads 0), W1C write 1 to clear, SPECIAL side effects on read or write.")
    for p in spec.peripherals:
        out.append("")
        out.append("## %s (%s)" % (p.name, hexs(p.base)))
        out.append("")
        out.append(p.description)
        out.append("")
        out.append("| Offset | Register | Reset | Description |")
        out.append("|---|---|---|---|")
        for r in p.registers:
            out.append("| 0x%x | %s | %s | %s |" % (r.offset, r.name, hexs(r.reset), r.description))
        for r in p.registers:
            out.append("")
            out.append("### %s.%s" % (p.name, r.name))
            out.append("")
            out.append("| Bits | Field | Access | Description |")
            out.append("|---|---|---|---|")
            for f in r.fields:
                bits = "%d" % f.msb if f.msb == f.lsb else "%d:%d" % (f.msb, f.lsb)
                out.append("| %s | %s | %s | %s |" % (bits, f.name, f.access, f.description))
    out.append("")
    out.append("## Interrupts")
    out.append("")
    out.append("The irq line of each source is its status flag AND its enable bit.")
    out.append("")
    out.append("| Bit | Name | Status flag | Enable |")
    out.append("|---|---|---|---|")
    for i in spec.irqs:
        out.append("| %d | %s | %s | %s |" % (i.bit, i.name, i.status, i.enable))
    return "\n".join(out) + "\n"


def outputs(spec: Spec) -> Dict[str, str]:
    return {
        os.path.join("gen", "regs.h"): gen_c_header(spec),
        os.path.join("gen", "regs.py"): gen_py_module(spec),
        os.path.join("gen", "regs_pkg.sv"): gen_sv_package(spec),
        os.path.join("docs", "registers.md"): gen_markdown(spec),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate register headers from spec/registers.yaml")
    ap.add_argument("--spec", default=SPEC)
    ap.add_argument("--root", default=ROOT)
    ap.add_argument("--check", action="store_true", help="fail if generated files differ from the spec")
    args = ap.parse_args()

    try:
        files = outputs(load_spec(args.spec))
    except (SpecError, KeyError) as e:
        print("spec error: %s" % e, file=sys.stderr)
        return 2

    stale = []
    for rel, text in files.items():
        path = os.path.join(args.root, rel)
        current = open(path).read() if os.path.exists(path) else None
        if current != text:
            stale.append(rel)
            if not args.check:
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "w") as f:
                    f.write(text)

    if args.check:
        if stale:
            print("stale generated files: %s" % ", ".join(stale), file=sys.stderr)
            print("run: make gen", file=sys.stderr)
            return 1
        print("generated files are up to date")
        return 0

    print("generated: %s" % (", ".join(stale) if stale else "nothing changed"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
