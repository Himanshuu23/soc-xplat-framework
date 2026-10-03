import pytest

from gen import regs
from xplat.hal import BackendProtocolError, BackendTimeout
from xplat.hal.fake_serial import FakeSerial
from xplat.hal.fpga import FpgaBackend
from xplat.hal.model import ModelBackend

SCRATCH = regs.MEMORY["scratch_base"]


@pytest.fixture
def fake() -> FakeSerial:
    return FakeSerial()


@pytest.fixture
def fpga(fake) -> FpgaBackend:
    return FpgaBackend(fake, reset_hook=fake.power_cycle, name="fpga-fake")


def test_sync_swallows_banner(fake):
    FpgaBackend(fake)
    assert fake.in_waiting == 0


def test_register_roundtrip(fpga):
    fpga.write_reg(SCRATCH, 0xCAFEF00D)
    assert fpga.read_reg(SCRATCH) == 0xCAFEF00D
    assert fpga.read("UART.BAUD") == 0x10


def test_wire_format(fake, fpga):
    fake.writes.clear()
    fpga.write_reg(0x10002008, 5)
    fpga.read_reg(0x10002008)
    assert fake.writes == [b"W 10002008 5\n", b"R 10002008\n"]


def test_values_are_masked_to_32_bits(fake, fpga):
    fake.writes.clear()
    fpga.write_reg(SCRATCH, 0x1_FFFF_FFFF)
    assert fake.writes == [b"W 9000 ffffffff\n"]


def test_dma_copy_over_serial(fpga):
    data = list(range(100, 108))
    fpga.write_words(SCRATCH, data)
    fpga.dma_copy(SCRATCH, SCRATCH + 0x80, 8)
    assert fpga.read_words(SCRATCH + 0x80, 8) == data


def test_timeout_when_reply_dropped(fake, fpga):
    fake.drop_replies = 1
    with pytest.raises(BackendTimeout, match="no reply"):
        fpga.read_reg(SCRATCH)


def test_timeout_names_the_command(fake, fpga):
    fake.drop_replies = 1
    with pytest.raises(BackendTimeout, match="R 9000"):
        fpga.read_reg(SCRATCH)


def test_invalid_read_reply_is_protocol_error(fake, fpga):
    fake.corrupt_replies = 1
    with pytest.raises(BackendProtocolError, match="invalid reply 'zz!'"):
        fpga.read_reg(SCRATCH)


def test_invalid_write_reply_is_protocol_error(fake, fpga):
    fake.corrupt_replies = 1
    with pytest.raises(BackendProtocolError, match="invalid reply"):
        fpga.write_reg(SCRATCH, 1)


def test_truncated_reply_is_reported(fake, fpga):
    fake.truncate_replies = 1
    with pytest.raises(BackendTimeout, match="incomplete"):
        fpga.read_reg(SCRATCH)


def test_err_reply_is_protocol_error(fpga):
    with pytest.raises(BackendProtocolError, match="rejected read"):
        fpga.read_reg(SCRATCH + 1)
    with pytest.raises(BackendProtocolError, match="rejected write"):
        fpga.write_reg(SCRATCH + 2, 1)


def test_sync_times_out_when_monitor_silent():
    silent = FakeSerial(banner=False)
    silent.drop_replies = 100
    with pytest.raises(BackendTimeout, match="ping"):
        FpgaBackend(silent)


def test_reset_hook_power_cycles_device(fake, fpga):
    fpga.write_reg(SCRATCH, 5)
    fpga.write("TIMER.COMPARE", 123)
    fpga.reset()
    assert fpga.read("TIMER.COMPARE") == 0xFFFFFFFF
    assert fpga.read_reg(SCRATCH) == regs.MEMORY["ram_fill"]


def test_soft_reset_restores_register_defaults(fake):
    backend = FpgaBackend(fake)
    backend.write("TIMER.COMPARE", 5)
    backend.write("TIMER.CTRL", 0b111)
    backend.write("DMA.SRC", 0x1234)
    backend.write("DMA.CTRL", 0b11)
    backend.reset()
    for key, reg in regs.REGISTERS.items():
        if reg.access != "SPECIAL":
            assert backend.read(key) == reg.reset, key


def test_soft_reset_waits_for_dma(fake):
    backend = FpgaBackend(fake)
    backend.write("DMA.SRC", SCRATCH)
    backend.write("DMA.DST", SCRATCH + 0x4000)
    backend.write("DMA.LEN", 2560)
    backend.write("DMA.CTRL", 1)
    backend.reset()
    assert backend.read("DMA.STATUS") == 0
    assert backend.read("DMA.LEN") == 0


def test_reset_command_runs_and_resyncs(fake):
    backend = FpgaBackend(fake, reset_command="true")
    backend.reset()
    assert backend.read("UART.BAUD") == 0x10


def test_close_closes_port(fake, fpga):
    fpga.close()
    assert fake.closed


def test_fake_over_buggy_model_reproduces_bug():
    fake = FakeSerial(ModelBackend(bug="dma_len_off_by_one"))
    backend = FpgaBackend(fake)
    backend.write_words(SCRATCH, [1, 2, 3])
    backend.write_reg(SCRATCH + 0x100 + 8, 0xFFFFFFFF)
    backend.dma_copy(SCRATCH, SCRATCH + 0x100, 2)
    assert backend.read_reg(SCRATCH + 0x100 + 8) == 3
