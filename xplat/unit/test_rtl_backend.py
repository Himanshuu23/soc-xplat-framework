import os
import socket

import pytest

from gen import regs
from xplat.hal import BackendError, BackendProtocolError, BackendTimeout
from xplat.hal.rtl import DEFAULT_FW, DEFAULT_SIM, RtlBackend

SCRATCH = regs.MEMORY["scratch_base"]


class FakeBridge:
    def __init__(self, read=None, write=None) -> None:
        self.read = read or (lambda addr: 0)
        self.write = write or (lambda addr, val: None)
        self.closed = False

    def read_reg(self, addr: int) -> int:
        return self.read(addr)

    def write_reg(self, addr: int, val: int) -> None:
        self.write(addr, val)

    def close(self) -> None:
        self.closed = True


def make(bridge: FakeBridge) -> RtlBackend:
    return RtlBackend(bridge_factory=lambda: bridge)


def raiser(exc: Exception):
    def fn(*args):
        raise exc

    return fn


def test_socket_timeout_becomes_backend_timeout():
    backend = make(FakeBridge(read=raiser(socket.timeout())))
    with pytest.raises(BackendTimeout, match="read 0x00009000"):
        backend.read_reg(SCRATCH)


def test_invalid_reply_becomes_protocol_error():
    backend = make(FakeBridge(read=raiser(ValueError("invalid literal for int()"))))
    with pytest.raises(BackendProtocolError, match="invalid"):
        backend.read_reg(SCRATCH)


def test_rejected_write_becomes_protocol_error():
    backend = make(FakeBridge(write=raiser(ValueError("monitor rejected write"))))
    with pytest.raises(BackendProtocolError, match="rejected"):
        backend.write_reg(SCRATCH, 1)


def test_closed_connection_becomes_backend_error():
    backend = make(FakeBridge(read=raiser(RuntimeError("simulator closed the connection"))))
    with pytest.raises(BackendError, match="connection failed"):
        backend.read_reg(SCRATCH)


def test_os_error_becomes_backend_error():
    backend = make(FakeBridge(write=raiser(ConnectionResetError("reset"))))
    with pytest.raises(BackendError, match="socket error"):
        backend.write_reg(SCRATCH, 1)


def test_reset_closes_old_bridge_and_opens_new_one():
    bridges = []

    def factory():
        bridges.append(FakeBridge())
        return bridges[-1]

    backend = RtlBackend(bridge_factory=factory)
    backend.reset()
    assert len(bridges) == 2
    assert bridges[0].closed and not bridges[1].closed


def test_close_is_idempotent():
    backend = make(FakeBridge())
    backend.close()
    backend.close()


def test_missing_simulator_gives_actionable_error(tmp_path):
    with pytest.raises(BackendError, match="make sim"):
        RtlBackend(sim=str(tmp_path / "nope"), firmware=DEFAULT_FW)


def test_missing_firmware_gives_actionable_error(tmp_path):
    sim = tmp_path / "sim"
    sim.write_text("")
    with pytest.raises(BackendError, match="make fw"):
        RtlBackend(sim=str(sim), firmware=str(tmp_path / "nope.bin"))


built = os.path.exists(DEFAULT_SIM) and os.path.exists(DEFAULT_FW)


@pytest.mark.skipif(not built, reason="run make sim fw first")
def test_real_simulation_roundtrip_and_reset():
    with RtlBackend() as backend:
        backend.write_reg(SCRATCH, 0xCAFEF00D)
        assert backend.read_reg(SCRATCH) == 0xCAFEF00D
        assert backend.read("UART.BAUD") == 0x10
        backend.reset()
        assert backend.read_reg(SCRATCH) == regs.MEMORY["ram_fill"]


def timer_deltas() -> list:
    with RtlBackend() as backend:
        backend.write("TIMER.CTRL", 1)
        counts = [backend.read("TIMER.COUNT") for _ in range(5)]
    return [b - a for a, b in zip(counts, counts[1:])]


@pytest.mark.skipif(not built, reason="run make sim fw first")
def test_real_simulation_time_is_deterministic():
    first = timer_deltas()
    second = timer_deltas()
    assert first == second
    assert len(set(first)) == 1


@pytest.mark.skipif(not built, reason="run make sim fw first")
def test_real_dma_busy_window_is_observable():
    words = regs.MEMORY["scratch_size"] // 4
    with RtlBackend() as backend:
        backend.write("DMA.SRC", SCRATCH)
        backend.write("DMA.DST", SCRATCH)
        backend.write("DMA.LEN", words)
        backend.write("DMA.CTRL", 1)
        backend.write("DMA.SRC", 0)
        assert backend.read_field("DMA.STATUS.BUSY") == 1
        assert backend.read("DMA.SRC") == SCRATCH
