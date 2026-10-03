import pytest

from gen import regs
from xplat.hal import BackendProtocolError
from xplat.hal.model import ACCESS_CYCLES, DMA_CYCLES_PER_WORD, ModelBackend

SCRATCH = regs.MEMORY["scratch_base"]
FILL = regs.MEMORY["ram_fill"]


@pytest.fixture
def m() -> ModelBackend:
    return ModelBackend()


def test_reset_values_match_spec(m):
    for key, reg in regs.REGISTERS.items():
        if reg.access != "SPECIAL":
            assert m.read(key) == reg.reset, key


def test_ram_reads_fill_until_written(m):
    assert m.read_reg(SCRATCH) == FILL
    m.write_reg(SCRATCH, 0xCAFEF00D)
    assert m.read_reg(SCRATCH) == 0xCAFEF00D
    m.reset()
    assert m.read_reg(SCRATCH) == FILL


def test_unmapped_reads_zero_and_ignores_writes(m):
    m.write_reg(0x10004000, 0x1234)
    assert m.read_reg(0x10004000) == 0


@pytest.mark.parametrize("addr", [1, 2, 3, 0x10002001, -4, 0x1_0000_0000])
def test_bad_addresses_rejected(m, addr):
    with pytest.raises(BackendProtocolError):
        m.read_reg(addr)
    with pytest.raises(BackendProtocolError):
        m.write_reg(addr, 0)


def test_rw_register_readback(m):
    m.write("DMA.SRC", 0x12345678)
    assert m.read("DMA.SRC") == 0x12345678
    m.write("TIMER.CTRL", 0xFFFFFFFF)
    assert m.read("TIMER.CTRL") == 0b111


def test_ro_field_ignores_writes(m):
    m.write("UART.STATUS", 0xFFFFFFFF)
    assert m.read("UART.STATUS") == 0


def test_wo_field_reads_zero(m):
    m.write("DMA.CTRL", 0b01)
    assert m.read("DMA.CTRL") == 0
    m.write("DMA.CTRL", 0b11)
    assert m.read("DMA.CTRL") == 0b10


def test_dma_zero_length_sets_done_without_busy(m):
    m.write("DMA.CTRL", 1)
    assert m.read("DMA.STATUS") == 0b10


def test_done_is_w1c(m):
    m.write("DMA.CTRL", 1)
    m.write("DMA.STATUS", 0)
    assert m.read_field("DMA.STATUS.DONE") == 1
    m.write("DMA.STATUS", 1)
    assert m.read_field("DMA.STATUS.DONE") == 1
    m.write("DMA.STATUS", 2)
    assert m.read_field("DMA.STATUS.DONE") == 0


def test_dma_copy_words(m):
    data = [0x1000 + i for i in range(16)]
    m.write_words(SCRATCH, data)
    m.dma_copy(SCRATCH, SCRATCH + 0x100, 16)
    assert m.read_words(SCRATCH + 0x100, 16) == data


def test_small_dma_finishes_before_next_access(m):
    m.write_words(SCRATCH, [1, 2, 3, 4])
    m.write("DMA.SRC", SCRATCH)
    m.write("DMA.DST", SCRATCH + 0x40)
    m.write("DMA.LEN", 4)
    m.write("DMA.CTRL", 1)
    assert m.read("DMA.STATUS") == 0b10


def test_big_dma_is_observably_busy(m):
    words = regs.MEMORY["scratch_size"] // 4
    assert words * DMA_CYCLES_PER_WORD > 3 * ACCESS_CYCLES
    m.write("DMA.SRC", SCRATCH)
    m.write("DMA.DST", SCRATCH)
    m.write("DMA.LEN", words)
    m.write("DMA.CTRL", 1)
    assert m.read_field("DMA.STATUS.BUSY") == 1
    while m.read_field("DMA.STATUS.BUSY"):
        pass
    assert m.read_field("DMA.STATUS.DONE") == 1


def test_config_ignored_while_busy_and_start_ignored(m):
    words = regs.MEMORY["scratch_size"] // 4
    m.write("DMA.SRC", SCRATCH)
    m.write("DMA.DST", SCRATCH)
    m.write("DMA.LEN", words)
    m.write("DMA.CTRL", 1)
    m.write("DMA.SRC", 0)
    m.write("DMA.CTRL", 1)
    assert m.read_field("DMA.STATUS.BUSY") == 1
    m.write("DMA.LEN", 1)
    while m.read_field("DMA.STATUS.BUSY"):
        pass
    assert m.read("DMA.SRC") == SCRATCH
    assert m.read("DMA.LEN") == words


def test_overlapping_copy_is_forward_word_by_word(m):
    m.write_words(SCRATCH, [1, 2, 3, 4])
    m.dma_copy(SCRATCH, SCRATCH + 4, 3)
    assert m.read_words(SCRATCH, 4) == [1, 1, 1, 1]


def test_dma_addresses_wrap_modulo_ram(m):
    m.write_reg(0x20, 0xABCD)
    m.dma_copy(0x10020, SCRATCH, 1)
    assert m.read_reg(SCRATCH) == 0xABCD


def test_timer_frozen_while_disabled(m):
    first = m.read("TIMER.COUNT")
    second = m.read("TIMER.COUNT")
    assert first == second == 0


def test_timer_counts_by_elapsed_cycles(m):
    m.write("TIMER.CTRL", 1)
    first = m.read("TIMER.COUNT")
    second = m.read("TIMER.COUNT")
    assert second - first == ACCESS_CYCLES


def test_timer_match_flag_at_compare(m):
    m.write("TIMER.COMPARE", 3 * ACCESS_CYCLES)
    m.write("TIMER.CTRL", 1)
    seen = []
    for _ in range(6):
        seen.append(m.read_field("TIMER.STATUS.MATCH"))
    assert seen == [0, 0, 0, 1, 1, 1]


def test_timer_reload_keeps_count_below_period(m):
    m.write("TIMER.COMPARE", 999)
    m.write("TIMER.CTRL", 0b101)
    for _ in range(5):
        assert m.read("TIMER.COUNT") <= 999
    assert m.read_field("TIMER.STATUS.MATCH") == 1


def test_timer_match_w1c(m):
    m.write("TIMER.COMPARE", 0)
    m.write("TIMER.CTRL", 1)
    assert m.read_field("TIMER.STATUS.MATCH") == 1
    m.write("TIMER.CTRL", 0)
    m.write("TIMER.STATUS", 0)
    assert m.read_field("TIMER.STATUS.MATCH") == 1
    m.write("TIMER.STATUS", 1)
    assert m.read_field("TIMER.STATUS.MATCH") == 0


def test_irq_is_status_and_enable(m):
    m.write("TIMER.COMPARE", 0)
    m.write("TIMER.CTRL", 1)
    assert m.read_field("TIMER.STATUS.MATCH") == 1
    assert not m.irq_asserted("timer")
    m.write("TIMER.CTRL", 0b11)
    assert m.irq_asserted("timer")
    assert m.wait_irq("timer", timeout=0.1)


def test_wait_irq_times_out_without_enable(m):
    m.write("DMA.CTRL", 1)
    assert m.read_field("DMA.STATUS.DONE") == 1
    assert m.wait_irq("dma", timeout=0.05, polls=3) is False


def test_dma_irq_follows_done_and_enable(m):
    m.write("DMA.CTRL", 0b10)
    m.dma_copy(SCRATCH, SCRATCH + 0x40, 4, irq=True)
    m.write("DMA.CTRL", 0b10)
    m.write("DMA.CTRL", 0b11)
    assert m.wait_irq("dma", timeout=0.1)
    m.write("DMA.STATUS", 2)
    assert not m.irq_asserted("dma")


def test_uart_tx_logs_bytes_and_goes_busy_then_idle(m):
    m.write("UART.DATA", ord("A"))
    assert m.tx_log == [65]
    assert m.read_field("UART.STATUS.TX_BUSY") == 0


def test_uart_data_read_clears_rx_valid(m):
    m.values["UART.STATUS"] = 2
    m.values["UART.DATA"] = 0x41
    assert m.read("UART.DATA") == 0x41
    assert m.read_field("UART.STATUS.RX_VALID") == 0


def test_unknown_bug_rejected():
    with pytest.raises(ValueError):
        ModelBackend(bug="nonsense")


def test_bug_dma_off_by_one_overwrites_guard_word():
    bad = ModelBackend(bug="dma_len_off_by_one")
    bad.write_words(SCRATCH, [1, 2, 3, 4, 5])
    bad.write_reg(SCRATCH + 0x100 + 16, 0xFFFFFFFF)
    bad.dma_copy(SCRATCH, SCRATCH + 0x100, 4)
    assert bad.read_reg(SCRATCH + 0x100 + 16) == 5


def test_bug_timer_w1c_ignored():
    bad = ModelBackend(bug="timer_w1c_ignored")
    bad.write("TIMER.COMPARE", 0)
    bad.write("TIMER.CTRL", 1)
    bad.write("TIMER.CTRL", 0)
    bad.write("TIMER.STATUS", 1)
    assert bad.read_field("TIMER.STATUS.MATCH") == 1
