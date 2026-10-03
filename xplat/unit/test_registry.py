import pytest

from xplat.hal import BACKENDS, BackendError, BackendOptions, create_backend
from xplat.hal.registry import bug_sim_path


def test_backend_names():
    assert BACKENDS == ("model", "rtl", "fpga")


def test_create_model():
    assert create_backend("model").name == "model"


def test_create_fake_fpga():
    backend = create_backend("fpga", BackendOptions(serial_port="fake"))
    assert backend.name == "fpga-fake"
    assert backend.read("UART.BAUD") == 0x10


def test_unknown_backend():
    with pytest.raises(BackendError, match="unknown backend"):
        create_backend("quantum")


def test_unknown_bug():
    with pytest.raises(BackendError, match="unknown bug"):
        create_backend("model", BackendOptions(bug="gremlin"))


def test_model_bug_target_plants_bug_in_model():
    backend = create_backend("model", BackendOptions(bug="dma_len_off_by_one", bug_target="model"))
    assert backend.bug == "dma_len_off_by_one"


def test_rtl_bug_target_leaves_model_clean():
    backend = create_backend("model", BackendOptions(bug="dma_len_off_by_one", bug_target="rtl"))
    assert backend.bug is None


def test_rtl_bug_target_points_at_bug_build(tmp_path, monkeypatch):
    missing = str(tmp_path / "sim_bug_dma_len_off_by_one" / "soc_sim")
    monkeypatch.setattr("xplat.hal.registry.bug_sim_path", lambda bug: missing)
    with pytest.raises(BackendError, match="sim_bug_dma_len_off_by_one"):
        create_backend("rtl", BackendOptions(bug="dma_len_off_by_one", bug_target="rtl"))


def test_bug_sim_path_layout():
    assert bug_sim_path("x").endswith("build/sim_bug_x/soc_sim")


def test_real_serial_port_missing_gives_clear_error():
    with pytest.raises(BackendError, match="cannot open serial port"):
        create_backend("fpga", BackendOptions(serial_port="/dev/does-not-exist"))
