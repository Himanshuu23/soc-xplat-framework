import pytest

from xplat.hal import BackendError
from xplat.hal.fake_serial import FakeSerial, parse_hex
from xplat.hal.model import ModelBackend


@pytest.fixture
def ser() -> FakeSerial:
    s = FakeSerial()
    s.readline()
    return s


def talk(ser: FakeSerial, text: str) -> bytes:
    ser.write(text.encode() + b"\n")
    return ser.readline()


def test_banner_on_open():
    assert FakeSerial().readline() == b"READY\n"


def test_no_banner_when_disabled():
    assert FakeSerial(banner=False).readline() == b""


def test_ping(ser):
    assert talk(ser, "P") == b"OK\n"


def test_write_then_read_ram(ser):
    assert talk(ser, "W 9000 deadbeef") == b"OK\n"
    assert talk(ser, "R 9000") == b"deadbeef\n"


def test_read_reply_is_eight_hex_digits(ser):
    assert talk(ser, "R 10000008") == b"00000010\n"


def test_accepts_0x_prefix_and_upper_case(ser):
    talk(ser, "W 0x9000 0xABCD")
    assert talk(ser, "R 0X9000") == b"0000abcd\n"


def test_unaligned_address_is_err(ser):
    assert talk(ser, "R 9001") == b"ERR\n"
    assert talk(ser, "W 9002 1") == b"ERR\n"


def test_malformed_commands_are_err(ser):
    assert talk(ser, "R") == b"ERR\n"
    assert talk(ser, "R zz") == b"ERR\n"
    assert talk(ser, "W 9000") == b"ERR\n"
    assert talk(ser, "X 1") == b"ERR\n"


def test_empty_lines_get_no_reply(ser):
    ser.write(b"\n\r\n")
    assert ser.readline() == b""


def test_carriage_return_terminates_a_line(ser):
    ser.write(b"P\r")
    assert ser.readline() == b"OK\n"


def test_command_split_across_writes(ser):
    ser.write(b"W 90")
    ser.write(b"00 5\nR 9000\n")
    assert ser.readline() == b"OK\n"
    assert ser.readline() == b"00000005\n"


def test_quit_replies_bye_then_goes_silent(ser):
    assert talk(ser, "Q") == b"BYE\n"
    assert talk(ser, "P") == b""


def test_drop_replies(ser):
    ser.drop_replies = 1
    assert talk(ser, "P") == b""
    assert talk(ser, "P") == b"OK\n"


def test_corrupt_replies(ser):
    ser.corrupt_replies = 1
    assert talk(ser, "R 10000008") == b"zz!\n"
    assert talk(ser, "R 10000008") == b"00000010\n"


def test_truncated_reply_has_no_newline(ser):
    ser.truncate_replies = 1
    assert talk(ser, "R 10000008") == b"000"


def test_readline_returns_empty_when_idle(ser):
    assert ser.readline() == b""


def test_read_and_in_waiting(ser):
    ser.write(b"P\n")
    assert ser.in_waiting == 3
    assert ser.read(2) == b"OK"
    assert ser.read(5) == b"\n"


def test_reset_input_buffer(ser):
    ser.write(b"P\n")
    ser.reset_input_buffer()
    assert ser.readline() == b""


def test_closed_port_rejects_writes(ser):
    ser.close()
    with pytest.raises(BackendError):
        ser.write(b"P\n")


def test_power_cycle_resets_device_and_replays_banner(ser):
    talk(ser, "W 9000 1")
    ser.power_cycle()
    assert ser.readline() == b"READY\n"
    assert talk(ser, "R 9000") == b"deadbeef\n"


def test_reads_go_to_the_device():
    device = ModelBackend()
    device.write_reg(0x9000, 77)
    s = FakeSerial(device, banner=False)
    s.write(b"R 9000\n")
    assert s.readline() == b"0000004d\n"


def test_writes_are_recorded():
    s = FakeSerial(banner=False)
    s.write(b"P\n")
    assert s.writes == [b"P\n"]


@pytest.mark.parametrize(
    "text,expected",
    [("R 10", (0x10, 4)), ("R  0x2a", (0x2A, 7)), ("R ffffffffff", (0xFFFFFFFF, 12)), ("R g", None), ("R ", None)],
)
def test_parse_hex(text, expected):
    assert parse_hex(text, 1) == expected
