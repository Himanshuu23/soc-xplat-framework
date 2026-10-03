import copy
import importlib.util
import os
import re
import shutil
import subprocess

import pytest
import yaml

import gen_regs

ROOT = gen_regs.ROOT


@pytest.fixture(scope="module")
def spec() -> gen_regs.Spec:
    return gen_regs.load_spec()


def write_spec(tmp_path, mutate) -> str:
    with open(gen_regs.SPEC) as f:
        raw = yaml.safe_load(f)
    mutate(raw)
    path = tmp_path / "registers.yaml"
    path.write_text(yaml.safe_dump(raw))
    return str(path)


def test_spec_loads_all_peripherals(spec):
    assert [p.name for p in spec.peripherals] == ["UART", "TIMER", "DMA", "SYS"]
    assert [i.name for i in spec.irqs] == ["timer", "dma"]


def test_bases_and_offsets_match_memory_map(spec):
    bases = {p.name: p.base for p in spec.peripherals}
    assert bases == {"UART": 0x10000000, "TIMER": 0x10001000, "DMA": 0x10002000, "SYS": 0x10003000}
    offsets = {r.key: r.offset for r in spec.registers()}
    assert offsets["DMA.STATUS"] == 0x10
    assert offsets["TIMER.STATUS"] == 0xC
    assert offsets["UART.BAUD"] == 0x8


def test_reset_values_match_rtl(spec):
    resets = {r.key: r.reset for r in spec.registers()}
    uart = open(os.path.join(ROOT, "rtl", "uart.v")).read()
    assert int(re.search(r"DEFAULT_BAUD\s*=\s*(\d+)", uart).group(1)) == resets["UART.BAUD"]
    timer = open(os.path.join(ROOT, "rtl", "timer.v")).read()
    assert "compare <= 32'hffffffff" in timer
    assert resets["TIMER.COMPARE"] == 0xFFFFFFFF
    assert resets["TIMER.COUNT"] == 0


def test_baud_matches_firmware_and_testbench(spec):
    tb = open(os.path.join(ROOT, "sim", "tb.cpp")).read()
    baud = int(re.search(r"kBaudDiv\s*=\s*(\d+)", tb).group(1))
    resets = {r.key: r.reset for r in spec.registers()}
    assert baud == resets["UART.BAUD"]


def test_field_masks(spec):
    by_key = {r.key: r for r in spec.registers()}
    ctrl = {f.name: f.mask for f in by_key["TIMER.CTRL"].fields}
    assert ctrl == {"ENABLE": 1, "IRQ_EN": 2, "RELOAD": 4}
    assert by_key["UART.BAUD"].fields[0].mask == 0xFFFF
    assert by_key["TIMER.COUNT"].fields[0].mask == 0xFFFFFFFF


def test_irq_fields_resolve(spec):
    for irq in spec.irqs:
        reg, fld = spec.find_field(irq.status)
        assert fld.access == "W1C"
        spec.find_field(irq.enable)


def test_c_header_contents(spec):
    text = gen_regs.gen_c_header(spec)
    assert "#define DMA_BASE 0x10002000" in text
    assert "#define DMA_STATUS_DONE_MASK 0x00000002" in text
    assert "#define TIMER_COMPARE_RESET 0xffffffff" in text
    assert "#define IRQ_DMA (1 << IRQ_DMA_BIT)" in text
    assert text.count("#ifndef") == 1


def test_generated_python_matches_spec(spec):
    module_spec = importlib.util.spec_from_file_location("regs_under_test", os.path.join(ROOT, "gen", "regs.py"))
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    assert set(module.REGISTERS) == {r.key for r in spec.registers()}
    done = module.REGISTERS["DMA.STATUS"].field("DONE")
    assert (done.access, done.mask) == ("W1C", 2)
    assert done.trigger == (("DMA.LEN", 0), ("DMA.CTRL", 1))
    assert module.REGISTERS["DMA.STATUS"].address == 0x10002010
    assert module.IRQS["dma"].bit == 1


def test_markdown_lists_every_register(spec):
    text = gen_regs.gen_markdown(spec)
    for r in spec.registers():
        assert "### %s" % r.key in text


def test_committed_files_are_current():
    assert subprocess.run(["python3", os.path.join(ROOT, "tools", "gen_regs.py"), "--check"]).returncode == 0


def test_check_detects_stale_file(tmp_path):
    for rel in gen_regs.outputs(gen_regs.load_spec()):
        dst = tmp_path / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(os.path.join(ROOT, rel), dst)
    script = os.path.join(ROOT, "tools", "gen_regs.py")
    assert subprocess.run(["python3", script, "--check", "--root", str(tmp_path)]).returncode == 0
    with open(tmp_path / "gen" / "regs.h", "a") as f:
        f.write("#define SNEAKY 1\n")
    assert subprocess.run(["python3", script, "--check", "--root", str(tmp_path)]).returncode == 1


def test_regeneration_is_deterministic(spec):
    assert gen_regs.outputs(spec) == gen_regs.outputs(gen_regs.load_spec())


def test_rejects_overlapping_fields(tmp_path):
    def mutate(raw):
        raw["peripherals"]["TIMER"]["registers"][2]["fields"][1]["bits"] = "0"

    with pytest.raises(gen_regs.SpecError, match="overlaps"):
        gen_regs.load_spec(write_spec(tmp_path, mutate))


def test_rejects_unknown_access(tmp_path):
    def mutate(raw):
        raw["peripherals"]["UART"]["registers"][1]["fields"][0]["access"] = "RX"

    with pytest.raises(gen_regs.SpecError, match="bad access"):
        gen_regs.load_spec(write_spec(tmp_path, mutate))


def test_rejects_duplicate_offset(tmp_path):
    def mutate(raw):
        raw["peripherals"]["DMA"]["registers"][1]["offset"] = 0

    with pytest.raises(gen_regs.SpecError, match="duplicate offset"):
        gen_regs.load_spec(write_spec(tmp_path, mutate))


def test_rejects_bad_bit_range(tmp_path):
    def mutate(raw):
        raw["peripherals"]["UART"]["registers"][2]["fields"][0]["bits"] = "3:9"

    with pytest.raises(gen_regs.SpecError, match="bad bit range"):
        gen_regs.load_spec(write_spec(tmp_path, mutate))


def test_rejects_reset_outside_fields(tmp_path):
    def mutate(raw):
        raw["peripherals"]["TIMER"]["registers"][2]["reset"] = 0x80

    with pytest.raises(gen_regs.SpecError, match="outside any field"):
        gen_regs.load_spec(write_spec(tmp_path, mutate))


def test_rejects_unknown_irq_field(tmp_path):
    def mutate(raw):
        raw["irqs"][0]["status"] = "TIMER.STATUS.NOPE"

    with pytest.raises(gen_regs.SpecError):
        gen_regs.load_spec(write_spec(tmp_path, mutate))


@pytest.mark.skipif(shutil.which("verilator") is None, reason="verilator not installed")
def test_sv_package_lints(tmp_path):
    top = tmp_path / "top.sv"
    top.write_text("module top; import soc_regs_pkg::*; logic [31:0] x = DMA_BASE; endmodule\n")
    result = subprocess.run(
        ["verilator", "--lint-only", "-Wno-UNUSEDPARAM", "-Wno-UNUSEDSIGNAL", "--top-module", "top", os.path.join(ROOT, "gen", "regs_pkg.sv"), str(top)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
