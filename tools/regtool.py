#!/usr/bin/env python3
import argparse
import os
import socket
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_SIM = os.path.join(ROOT, "build", "sim", "soc_sim")
DEFAULT_FW = os.path.join(ROOT, "build", "fw", "monitor.bin")

UART_BASE = 0x10000000
TIMER_BASE = 0x10001000
DMA_BASE = 0x10002000


class RegBridge:
    def __init__(self, port=None, sim=DEFAULT_SIM, firmware=DEFAULT_FW, timeout=10.0):
        self.proc = None
        self.timeout = timeout
        if port is None:
            port = self._free_port()
            self.proc = subprocess.Popen(
                [sim, "--listen", str(port), firmware],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        self.sock = self._connect(port)
        self.buf = b""
        self._sync()

    @staticmethod
    def _free_port():
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            return s.getsockname()[1]

    def _connect(self, port):
        deadline = time.time() + self.timeout
        while True:
            try:
                sock = socket.create_connection(("127.0.0.1", port), timeout=self.timeout)
                sock.settimeout(self.timeout)
                return sock
            except OSError:
                if time.time() > deadline:
                    raise RuntimeError("cannot connect to simulator on port %d" % port)
                time.sleep(0.05)

    def _readline(self):
        while b"\n" not in self.buf:
            chunk = self.sock.recv(256)
            if not chunk:
                raise RuntimeError("simulator closed the connection")
            self.buf += chunk
        line, self.buf = self.buf.split(b"\n", 1)
        return line.decode().strip()

    def _command(self, text):
        self.sock.sendall(text.encode() + b"\n")
        return self._readline()

    def _sync(self):
        self.sock.sendall(b"P\n")
        while self._readline() != "OK":
            pass

    def read_reg(self, addr):
        reply = self._command("R %x" % addr)
        if reply == "ERR":
            raise ValueError("monitor rejected read of 0x%08x" % addr)
        return int(reply, 16)

    def write_reg(self, addr, value):
        reply = self._command("W %x %x" % (addr, value & 0xFFFFFFFF))
        if reply != "OK":
            raise ValueError("monitor rejected write to 0x%08x" % addr)

    def close(self):
        try:
            self.sock.close()
        finally:
            if self.proc:
                try:
                    self.proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.proc.kill()


def selftest(bridge, log):
    results = []

    def check(name, ok):
        results.append(ok)
        log("  %s %s" % ("ok  " if ok else "FAIL", name))

    scratch = 0x9000
    bridge.write_reg(scratch, 0xCAFEF00D)
    check("ram word write/read", bridge.read_reg(scratch) == 0xCAFEF00D)

    check("uart baud register", bridge.read_reg(UART_BASE + 0x8) == 16)
    check("uart idle, nothing pending", bridge.read_reg(UART_BASE + 0x4) == 0)

    bridge.write_reg(TIMER_BASE + 0x4, 0x1234)
    check("timer compare write/read", bridge.read_reg(TIMER_BASE + 0x4) == 0x1234)
    bridge.write_reg(TIMER_BASE + 0x4, 0xFFFFFFFF)
    bridge.write_reg(TIMER_BASE + 0x0, 0)
    bridge.write_reg(TIMER_BASE + 0x8, 1)
    first = bridge.read_reg(TIMER_BASE + 0x0)
    second = bridge.read_reg(TIMER_BASE + 0x0)
    check("timer counts while enabled", second > first > 0)
    bridge.write_reg(TIMER_BASE + 0x8, 0)
    frozen_a = bridge.read_reg(TIMER_BASE + 0x0)
    frozen_b = bridge.read_reg(TIMER_BASE + 0x0)
    check("timer frozen when disabled", frozen_a == frozen_b)

    words = [0x11111111 * (i + 1) & 0xFFFFFFFF for i in range(8)]
    src, dst = 0xA000, 0xA100
    for i, w in enumerate(words):
        bridge.write_reg(src + 4 * i, w)
        bridge.write_reg(dst + 4 * i, 0)
    bridge.write_reg(DMA_BASE + 0x00, src)
    bridge.write_reg(DMA_BASE + 0x04, dst)
    bridge.write_reg(DMA_BASE + 0x08, len(words))
    bridge.write_reg(DMA_BASE + 0x0C, 1)
    status = 0
    for _ in range(50):
        status = bridge.read_reg(DMA_BASE + 0x10)
        if status & 2:
            break
    check("dma done flag set", status & 2 != 0 and status & 1 == 0)
    copied = [bridge.read_reg(dst + 4 * i) for i in range(len(words))]
    check("dma copy driven from python", copied == words)
    bridge.write_reg(DMA_BASE + 0x10, 2)
    check("dma done is write-1-to-clear", bridge.read_reg(DMA_BASE + 0x10) & 2 == 0)

    check("unmapped address reads zero", bridge.read_reg(0x10004000) == 0)
    return all(results)


def shell(bridge):
    print("commands: r ADDR | w ADDR VALUE | quit")
    for line in sys.stdin:
        parts = line.split()
        if not parts:
            continue
        op = parts[0].lower()
        if op in ("q", "quit", "exit"):
            break
        try:
            if op == "r" and len(parts) == 2:
                print("0x%08x" % bridge.read_reg(int(parts[1], 16)))
            elif op == "w" and len(parts) == 3:
                bridge.write_reg(int(parts[1], 16), int(parts[2], 16))
                print("ok")
            else:
                print("usage: r ADDR | w ADDR VALUE")
        except ValueError as e:
            print("error: %s" % e)


def run_commands(bridge, commands):
    for text in commands:
        parts = text.split()
        op = parts[0].upper()
        if op == "R" and len(parts) == 2:
            addr = int(parts[1], 16)
            print("R 0x%08x = 0x%08x" % (addr, bridge.read_reg(addr)))
        elif op == "W" and len(parts) == 3:
            addr, value = int(parts[1], 16), int(parts[2], 16)
            bridge.write_reg(addr, value)
            print("W 0x%08x <- 0x%08x" % (addr, value))
        else:
            raise SystemExit("bad command: %r (use 'R addr' or 'W addr value')" % text)


def main():
    ap = argparse.ArgumentParser(description="Read and write SoC registers through the UART monitor.")
    ap.add_argument("commands", nargs="*", help="'R addr' or 'W addr value' (hex)")
    ap.add_argument("--port", type=int, help="attach to a simulator already listening on this port")
    ap.add_argument("--sim", default=DEFAULT_SIM)
    ap.add_argument("--firmware", default=DEFAULT_FW)
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--shell", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    log = (lambda s: None) if args.quiet else print
    bridge = RegBridge(port=args.port, sim=args.sim, firmware=args.firmware)
    try:
        if args.selftest:
            ok = selftest(bridge, log)
            log("regtool selftest: %s" % ("PASS" if ok else "FAIL"))
            return 0 if ok else 1
        if args.shell:
            shell(bridge)
        else:
            run_commands(bridge, args.commands)
        return 0
    finally:
        bridge.close()


if __name__ == "__main__":
    sys.exit(main())
