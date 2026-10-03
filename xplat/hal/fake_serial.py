from typing import List, Optional

from .base import Backend, BackendError
from .model import ModelBackend


def parse_hex(text: str, pos: int) -> Optional[tuple]:
    while pos < len(text) and text[pos] == " ":
        pos += 1
    if text[pos:pos + 2] in ("0x", "0X"):
        pos += 2
    start = pos
    while pos < len(text) and text[pos] in "0123456789abcdefABCDEF":
        pos += 1
    if pos == start:
        return None
    return int(text[start:pos], 16) & 0xFFFFFFFF, pos


class FakeSerial:
    def __init__(self, device: Optional[Backend] = None, banner: bool = True, timeout: float = 0.0) -> None:
        self.device = device or ModelBackend()
        self.timeout = timeout
        self.banner = banner
        self.rx = bytearray()
        self.pending = bytearray()
        self.writes: List[bytes] = []
        self.drop_replies = 0
        self.corrupt_replies = 0
        self.truncate_replies = 0
        self.exited = False
        self.closed = False
        if banner:
            self.rx += b"READY\n"

    @property
    def in_waiting(self) -> int:
        return len(self.rx)

    def write(self, data: bytes) -> int:
        if self.closed:
            raise BackendError("write to closed serial port")
        self.writes.append(bytes(data))
        for byte in data:
            if byte in (10, 13):
                line = self.pending.decode(errors="replace")
                self.pending.clear()
                if line:
                    self.respond(self.execute(line))
            else:
                self.pending.append(byte)
        return len(data)

    def respond(self, reply: Optional[str]) -> None:
        if reply is None or self.exited and reply != "BYE":
            return
        if self.drop_replies:
            self.drop_replies -= 1
            return
        if self.corrupt_replies:
            self.corrupt_replies -= 1
            reply = "zz!"
        if self.truncate_replies:
            self.truncate_replies -= 1
            self.rx += reply[:3].encode()
            return
        self.rx += reply.encode() + b"\n"

    def execute(self, line: str) -> Optional[str]:
        op = line[0]
        try:
            if op == "R":
                parsed = parse_hex(line, 1)
                if parsed is None or parsed[0] & 3:
                    return "ERR"
                return "%08x" % self.device.read_reg(parsed[0])
            if op == "W":
                first = parse_hex(line, 1)
                if first is None or first[0] & 3:
                    return "ERR"
                second = parse_hex(line, first[1])
                if second is None:
                    return "ERR"
                self.device.write_reg(first[0], second[0])
                return "OK"
        except BackendError:
            return "ERR"
        if op == "P":
            return "OK"
        if op == "Q":
            self.exited = True
            return "BYE"
        return "ERR"

    def readline(self) -> bytes:
        index = self.rx.find(b"\n")
        end = index + 1 if index >= 0 else len(self.rx)
        data = bytes(self.rx[:end])
        del self.rx[:end]
        return data

    def read(self, size: int = 1) -> bytes:
        data = bytes(self.rx[:size])
        del self.rx[:size]
        return data

    def reset_input_buffer(self) -> None:
        self.rx.clear()

    def power_cycle(self) -> None:
        self.device.reset()
        self.rx.clear()
        self.pending.clear()
        self.exited = False
        if self.banner:
            self.rx += b"READY\n"

    def close(self) -> None:
        self.closed = True
