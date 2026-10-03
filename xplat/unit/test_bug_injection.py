import os
import subprocess
import sys

import pytest

from xplat.hal.model import BUGS
from xplat.hal.registry import bug_sim_path
from xplat.hal.rtl import DEFAULT_FW, DEFAULT_SIM

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CLI = os.path.join(ROOT, "xplat", "run_regression.py")

EXPECTED_WHERE = {
    "dma_len_off_by_one": ("dma_copy_basic", "guard word after dst"),
    "timer_w1c_ignored": ("reg_access_types", "TIMER.STATUS.MATCH after writing 1"),
}


def cli(*args):
    return subprocess.run([sys.executable, CLI, *args], capture_output=True, text=True, cwd=ROOT)


rtl_built = os.path.exists(DEFAULT_SIM) and os.path.exists(DEFAULT_FW)


def test_every_bug_has_an_expected_signature():
    assert set(EXPECTED_WHERE) == set(BUGS)


@pytest.mark.skipif(not rtl_built, reason="run make sim fw first")
@pytest.mark.parametrize("bug", BUGS)
def test_bug_planted_in_model_is_flagged_against_clean_rtl(bug):
    p = cli("--backends", "model,rtl", "--inject-bug", bug, "--bug-target", "model", "--quiet")
    test, where = EXPECTED_WHERE[bug]
    assert p.returncode == 1
    assert "MISMATCH %s" % test in p.stdout
    assert where in p.stdout
    assert "disagree: model" in p.stdout


@pytest.mark.parametrize("bug", BUGS)
def test_model_bug_also_reaches_the_fake_fpga_wrapping_it(bug):
    p = cli("--backends", "model,fpga", "--inject-bug", bug, "--bug-target", "model", "--quiet")
    assert p.returncode == 1
    assert "MISMATCH" not in p.stdout.split("FAILURES")[0].split("VERDICT")[1].replace("VERDICT", "")
    assert p.stdout.count("FAIL ") >= 2


@pytest.mark.parametrize("bug", BUGS)
def test_bug_in_model_alone_still_fails(bug):
    p = cli("--backend", "model", "--inject-bug", bug, "--bug-target", "model", "--quiet")
    assert p.returncode == 1
    assert "REGRESSION FAILED" in p.stdout


def test_unknown_bug_rejected_by_cli():
    assert cli("--backend", "model", "--inject-bug", "gremlin").returncode == 2


def test_clean_run_unaffected_by_flag_absence():
    assert cli("--backends", "model,fpga", "--quiet").returncode == 0


@pytest.mark.skipif(not rtl_built, reason="run make sim fw first")
def test_html_names_the_injected_bug(tmp_path):
    page = tmp_path / "r.html"
    cli("--backends", "model,rtl", "--inject-bug", "dma_len_off_by_one", "--bug-target", "model", "--html", str(page), "--quiet")
    text = page.read_text()
    assert "injected bug: dma_len_off_by_one in model" in text
    assert "Cross-backend mismatches" in text


@pytest.mark.parametrize("bug", BUGS)
def test_bug_planted_in_rtl_is_flagged_against_model(bug):
    if not os.path.exists(bug_sim_path(bug)):
        pytest.skip("run make xplat-bugdemo to build the bugged simulator")
    p = cli("--backends", "model,rtl", "--inject-bug", bug, "--quiet")
    test, where = EXPECTED_WHERE[bug]
    assert p.returncode == 1
    assert "MISMATCH %s" % test in p.stdout
    assert where in p.stdout
    assert "disagree: rtl" in p.stdout


def test_rtl_carries_the_bug_hooks_but_off_by_default():
    dma = open(os.path.join(ROOT, "rtl", "dma.v")).read()
    timer = open(os.path.join(ROOT, "rtl", "timer.v")).read()
    assert "`ifdef INJECT_DMA_LEN_OFF_BY_ONE" in dma
    assert "`ifndef INJECT_TIMER_W1C_IGNORED" in timer
    makefile = open(os.path.join(ROOT, "Makefile")).read()
    assert "-DINJECT_$(shell" in makefile
    assert "INJECT_" not in makefile.split("$(SIM): $(RTL)")[1].split("\n\n")[0]
