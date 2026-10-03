# generated from spec/registers.yaml by tools/gen_regs.py, do not edit
from dataclasses import dataclass
from typing import Dict, Tuple


@dataclass(frozen=True)
class Field:
    name: str
    msb: int
    lsb: int
    access: str
    description: str
    trigger: Tuple[Tuple[str, int], ...] = ()
    cleanup: Tuple[Tuple[str, int], ...] = ()

    @property
    def mask(self) -> int:
        return ((1 << (self.msb - self.lsb + 1)) - 1) << self.lsb


@dataclass(frozen=True)
class Register:
    periph: str
    name: str
    offset: int
    address: int
    reset: int
    access: str
    description: str
    test_values: Tuple[int, ...]
    fields: Tuple[Field, ...]

    @property
    def key(self) -> str:
        return "%s.%s" % (self.periph, self.name)

    def field(self, name: str) -> Field:
        for f in self.fields:
            if f.name == name:
                return f
        raise KeyError("%s.%s" % (self.key, name))


@dataclass(frozen=True)
class Irq:
    name: str
    bit: int
    status: str
    enable: str


MEMORY: Dict[str, int] = {
    'ram_base': 0x00000000,
    'ram_size': 0x00010000,
    'ram_fill': 0xdeadbeef,
    'scratch_base': 0x00009000,
    'scratch_size': 0x00006000,
}

BASES: Dict[str, int] = {
    'UART': 0x10000000,
    'TIMER': 0x10001000,
    'DMA': 0x10002000,
    'SYS': 0x10003000,
}

REGISTERS: Dict[str, Register] = {}

REGISTERS['UART.DATA'] = Register(
    periph='UART',
    name='DATA',
    offset=0x0,
    address=0x10000000,
    reset=0x00000000,
    access='SPECIAL',
    description='write sends the low byte, read returns the last received byte and clears RX_VALID',
    test_values=(),
    fields=(
        Field('BYTE', 7, 0, 'SPECIAL', 'transmit or receive byte', (), ()),
    ),
)

REGISTERS['UART.STATUS'] = Register(
    periph='UART',
    name='STATUS',
    offset=0x4,
    address=0x10000004,
    reset=0x00000000,
    access='',
    description='link status',
    test_values=(),
    fields=(
        Field('TX_BUSY', 0, 0, 'RO', 'a byte is being shifted out', (), ()),
        Field('RX_VALID', 1, 1, 'RO', 'a received byte is waiting in DATA', (), ()),
    ),
)

REGISTERS['UART.BAUD'] = Register(
    periph='UART',
    name='BAUD',
    offset=0x8,
    address=0x10000008,
    reset=0x00000010,
    access='',
    description='clock cycles per bit',
    test_values=(0x00000010, ),
    fields=(
        Field('DIVISOR', 15, 0, 'RW', 'clock cycles per bit', (), ()),
    ),
)

REGISTERS['TIMER.COUNT'] = Register(
    periph='TIMER',
    name='COUNT',
    offset=0x0,
    address=0x10001000,
    reset=0x00000000,
    access='',
    description='counter, increments every clock while enabled',
    test_values=(),
    fields=(
        Field('VALUE', 31, 0, 'RW', 'current count', (), ()),
    ),
)

REGISTERS['TIMER.COMPARE'] = Register(
    periph='TIMER',
    name='COMPARE',
    offset=0x4,
    address=0x10001004,
    reset=0xffffffff,
    access='',
    description='match value',
    test_values=(),
    fields=(
        Field('VALUE', 31, 0, 'RW', 'value that sets MATCH when COUNT reaches it', (), ()),
    ),
)

REGISTERS['TIMER.CTRL'] = Register(
    periph='TIMER',
    name='CTRL',
    offset=0x8,
    address=0x10001008,
    reset=0x00000000,
    access='',
    description='control',
    test_values=(),
    fields=(
        Field('ENABLE', 0, 0, 'RW', 'counter runs', (), ()),
        Field('IRQ_EN', 1, 1, 'RW', 'MATCH drives the irq line', (), ()),
        Field('RELOAD', 2, 2, 'RW', 'COUNT returns to 0 after a match', (), ()),
    ),
)

REGISTERS['TIMER.STATUS'] = Register(
    periph='TIMER',
    name='STATUS',
    offset=0xc,
    address=0x1000100c,
    reset=0x00000000,
    access='',
    description='status',
    test_values=(),
    fields=(
        Field('MATCH', 0, 0, 'W1C', 'COUNT reached COMPARE, cleared by writing 1', (('TIMER.COMPARE', 0), ('TIMER.COUNT', 0), ('TIMER.CTRL', 1), ), (('TIMER.CTRL', 0), )),
    ),
)

REGISTERS['DMA.SRC'] = Register(
    periph='DMA',
    name='SRC',
    offset=0x0,
    address=0x10002000,
    reset=0x00000000,
    access='',
    description='source byte address, writes ignored while BUSY',
    test_values=(),
    fields=(
        Field('ADDR', 31, 0, 'RW', 'source address', (), ()),
    ),
)

REGISTERS['DMA.DST'] = Register(
    periph='DMA',
    name='DST',
    offset=0x4,
    address=0x10002004,
    reset=0x00000000,
    access='',
    description='destination byte address, writes ignored while BUSY',
    test_values=(),
    fields=(
        Field('ADDR', 31, 0, 'RW', 'destination address', (), ()),
    ),
)

REGISTERS['DMA.LEN'] = Register(
    periph='DMA',
    name='LEN',
    offset=0x8,
    address=0x10002008,
    reset=0x00000000,
    access='',
    description='transfer length in words, writes ignored while BUSY',
    test_values=(),
    fields=(
        Field('WORDS', 31, 0, 'RW', 'number of 32-bit words', (), ()),
    ),
)

REGISTERS['DMA.CTRL'] = Register(
    periph='DMA',
    name='CTRL',
    offset=0xc,
    address=0x1000200c,
    reset=0x00000000,
    access='',
    description='control',
    test_values=(),
    fields=(
        Field('START', 0, 0, 'WO', 'begin the transfer', (), ()),
        Field('IRQ_EN', 1, 1, 'RW', 'DONE drives the irq line', (), ()),
    ),
)

REGISTERS['DMA.STATUS'] = Register(
    periph='DMA',
    name='STATUS',
    offset=0x10,
    address=0x10002010,
    reset=0x00000000,
    access='',
    description='status',
    test_values=(),
    fields=(
        Field('BUSY', 0, 0, 'RO', 'a transfer is running', (), ()),
        Field('DONE', 1, 1, 'W1C', 'transfer finished, sticky until cleared by writing 1', (('DMA.LEN', 0), ('DMA.CTRL', 1), ), ()),
    ),
)

REGISTERS['SYS.EXIT'] = Register(
    periph='SYS',
    name='EXIT',
    offset=0x0,
    address=0x10003000,
    reset=0x00000000,
    access='SPECIAL',
    description='any write ends the simulation, the value is the process exit code',
    test_values=(),
    fields=(
        Field('CODE', 31, 0, 'SPECIAL', 'exit code', (), ()),
    ),
)

IRQS: Dict[str, Irq] = {
    'timer': Irq('timer', 0, 'TIMER.STATUS.MATCH', 'TIMER.CTRL.IRQ_EN'),
    'dma': Irq('dma', 1, 'DMA.STATUS.DONE', 'DMA.CTRL.IRQ_EN'),
}

BY_ADDRESS: Dict[int, Register] = {r.address: r for r in REGISTERS.values()}
