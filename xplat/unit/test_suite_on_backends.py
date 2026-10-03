import os
import random
import re

import pytest

from xplat import framework
from xplat.hal import create_backend
from xplat.hal.model import BUGS, ModelBackend
from xplat.hal.fake_serial import FakeSerial
from xplat.hal.fpga import FpgaBackend
from xplat.tests import ORDER, all_tests
from xplat.tests.random_dma import pick_transfer

TESTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "tests")


def run_all(backend) -> dict:
    results = {}
    for case in all_tests():
        backend.reset()
        try:
            case.fn(backend, lambda s: None)
            results[case.name] = None
        except framework.TestFailure as e:
            results[case.name] = e
    return results


def test_seven_tests_registered_in_order():
    assert [t.name for t in all_tests()] == list(ORDER)
    assert len(ORDER) == 7


@pytest.mark.parametrize("name", ["model", "fpga"])
def test_all_pass_on_clean_backend(name):
    backend = create_backend(name)
    results = run_all(backend)
    assert {k: v for k, v in results.items() if v} == {}


def test_all_pass_on_fake_serial_over_clean_model():
    fake = FakeSerial()
    backend = FpgaBackend(fake, reset_hook=fake.power_cycle)
    assert all(v is None for v in run_all(backend).values())


def test_dma_length_bug_is_caught_with_location():
    results = run_all(ModelBackend(bug="dma_len_off_by_one"))
    failure = results["dma_copy_basic"]
    assert failure is not None
    assert "guard word after dst" in failure.where
    assert results["random_dma"] is not None
    assert "iteration" in results["random_dma"].where


def test_timer_w1c_bug_is_caught_with_location():
    results = run_all(ModelBackend(bug="timer_w1c_ignored"))
    failure = results["reg_access_types"]
    assert failure is not None
    assert "TIMER.STATUS.MATCH" in failure.where


@pytest.mark.parametrize("bug", BUGS)
def test_every_bug_fails_at_least_one_test(bug):
    results = run_all(ModelBackend(bug=bug))
    assert any(v is not None for v in results.values())


def test_random_dma_is_reproducible_for_a_seed():
    def picks(seed):
        rng = random.Random(seed)
        return [pick_transfer(rng) for _ in range(12)]

    assert picks(7) == picks(7)
    assert picks(7) != picks(8)


def test_random_dma_covers_overlap_and_disjoint_cases():
    rng = random.Random(framework.DEFAULT_SEED)
    cases = [pick_transfer(rng) for _ in range(200)]
    overlapping = [c for c in cases if abs(c[0] - c[1]) < 4 * c[2]]
    assert 0 < len(overlapping) < len(cases)


def test_random_dma_stays_inside_scratch():
    from xplat.tests.common import SCRATCH_BASE, SCRATCH_END

    rng = random.Random(1)
    for _ in range(500):
        src, dst, words = pick_transfer(rng)
        assert SCRATCH_BASE < min(src, dst)
        assert max(src, dst) + 4 * words < SCRATCH_END


def test_changing_the_seed_changes_the_run():
    framework.config.seed = 99
    try:
        backend = create_backend("model")
        backend.reset()
        logs = []
        framework.REGISTRY["random_dma"].fn(backend, logs.append)
        assert logs[0] == "seed 0x00000063"
    finally:
        framework.config.seed = framework.DEFAULT_SEED


def test_tests_contain_no_backend_specific_code():
    banned = re.compile(r"\b(rtl|fpga|ModelBackend|RtlBackend|FpgaBackend|isinstance|soc_sim|socket|serial)\b", re.I)
    offenders = []
    for fname in sorted(os.listdir(TESTS_DIR)):
        if fname.endswith(".py"):
            for lineno, line in enumerate(open(os.path.join(TESTS_DIR, fname)), 1):
                if banned.search(line):
                    offenders.append("%s:%d: %s" % (fname, lineno, line.strip()))
    assert offenders == []


def test_tests_only_use_the_backend_api():
    allowed = {"hal.base", "framework", "tests.common"}
    for fname in sorted(os.listdir(TESTS_DIR)):
        if fname.endswith(".py") and fname != "__init__.py":
            for line in open(os.path.join(TESTS_DIR, fname)):
                m = re.match(r"from xplat\.(\S+) import", line)
                if m:
                    assert m.group(1) in allowed, (fname, line)
