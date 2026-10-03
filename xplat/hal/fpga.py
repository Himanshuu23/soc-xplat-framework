import re
import shlex
import subprocess
import time
from typing import Any, Callable, Optional

from gen import regs

from .base import Backend, BackendError, BackendProtocolError, BackendTimeout

REPLY_HEX = re.compile(r"^[0-9a-fA-F]{8}$")
SYNC_TRIES = 5
SYNC_LINES = 4


def open_serial(port: str, baud: int, timeout: float) -> Any:
    try:
        import serial
    except ImportError:
        raise BackendError("pyserial is required for a real FPGA, install it with: pip install pyserial")
    try:
        return serial.Serial(port, baud, timeout=timeout)
    except serial.SerialException as e:
        raise BackendError("cannot open serial port %s: %s" % (port, e))


class FpgaBackend(Backend):
    name = "fpga"

    def __init__(
        self,
        ser: Any,
        timeout: float = 2.0,
        reset_hook: Optional[Callable[[], None]] = None,
        reset_command: Optional[str] = None,
        name: Optional[str] = None,
    ) -> None:
        self.ser = ser
        self.timeout = timeout
        self.reset_hook = reset_hook
        self.reset_command = reset_command
        if name:
            self.name = name
        self.sync()

    def transact(self, line: str) -> str:
        self.ser.write(line.encode() + b"\n")
        raw = self.ser.readline()
        if not raw:
            raise BackendTimeout("no reply to %r within %.1fs, is the monitor firmware running?" % (line, self.timeout))
        if not raw.endswith(b"\n"):
            raise BackendTimeout("incomplete reply %r to %r" % (raw, line))
        return raw.decode(errors="replace").strip()

    def sync(self) -> None:
        for _ in range(SYNC_TRIES):
            self.ser.write(b"P\n")
            for _ in range(SYNC_LINES):
                raw = self.ser.readline()
                if not raw:
                    break
                if raw.strip() == b"OK":
                    return
        raise BackendTimeout("monitor did not answer the ping after %d tries" % SYNC_TRIES)

    def read_reg(self, addr: int) -> int:
        reply = self.transact("R %x" % addr)
        if reply == "ERR":
            raise BackendProtocolError("monitor rejected read of 0x%08x" % addr)
        if not REPLY_HEX.match(reply):
            raise BackendProtocolError("invalid reply %r to read of 0x%08x" % (reply, addr))
        return int(reply, 16)

    def write_reg(self, addr: int, val: int) -> None:
        reply = self.transact("W %x %x" % (addr, val & 0xFFFFFFFF))
        if reply == "ERR":
            raise BackendProtocolError("monitor rejected write to 0x%08x" % addr)
        if reply != "OK":
            raise BackendProtocolError("invalid reply %r to write of 0x%08x" % (reply, addr))

    def reset(self) -> None:
        if self.reset_hook:
            self.reset_hook()
            self.ser.reset_input_buffer()
            self.sync()
        elif self.reset_command:
            subprocess.run(shlex.split(self.reset_command), check=True)
            time.sleep(0.5)
            self.ser.reset_input_buffer()
            self.sync()
        else:
            self.soft_reset()

    def soft_reset(self) -> None:
        deadline = time.monotonic() + self.timeout
        while self.read_field("DMA.STATUS.BUSY"):
            if time.monotonic() > deadline:
                raise BackendTimeout("DMA stayed busy during soft reset")
        ordered = sorted(regs.REGISTERS.values(), key=lambda r: r.name != "CTRL")
        for reg in ordered:
            if reg.access == "SPECIAL":
                continue
            value = 0
            for f in reg.fields:
                if f.access == "RW":
                    value |= reg.reset & f.mask
                elif f.access == "W1C":
                    value |= f.mask
            if any(f.access in ("RW", "W1C") for f in reg.fields):
                self.write_reg(reg.address, value)

    def close(self) -> None:
        self.ser.close()
