import os
import subprocess
import sys
import xml.etree.ElementTree as ET

import pytest

from xplat import framework, report, runner
from xplat.hal import BackendError
from xplat.hal.model import ModelBackend
from xplat.tests import all_tests

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CLI = os.path.join(ROOT, "xplat", "run_regression.py")


def specs(**bugs):
    out = [runner.BackendSpec("model", ModelBackend)]
    for label, bug in bugs.items():
        out.append(runner.BackendSpec(label, lambda b=bug: ModelBackend(bug=b)))
    return out


def run(specs_, names=None):
    tests = [t for t in all_tests() if names is None or t.name in names]
    results = runner.run_suite(specs_, tests)
    labels = [s.label for s in specs_]
    return results, runner.analyze(results, labels, [t.name for t in tests]), labels


def test_clean_run_is_ok_and_exits_zero():
    results, verdicts, _ = run(specs(twin=None))
    assert {v.status for v in verdicts} == {runner.OK}
    assert runner.exit_code(verdicts) == 0
    assert all(r.status == runner.PASS for r in results)


def test_mismatch_when_one_backend_has_a_bug():
    results, verdicts, _ = run(specs(buggy="dma_len_off_by_one"))
    by_name = {v.test: v for v in verdicts}
    assert by_name["dma_copy_basic"].status == runner.MISMATCH
    assert by_name["reg_reset_values"].status == runner.OK
    assert runner.exit_code(verdicts) == 1
    assert "passes on model but fails on buggy" in by_name["dma_copy_basic"].detail


def test_fail_when_every_backend_fails():
    _, verdicts, _ = run([runner.BackendSpec("a", lambda: ModelBackend(bug="timer_w1c_ignored")), runner.BackendSpec("b", lambda: ModelBackend(bug="timer_w1c_ignored"))], ["reg_access_types"])
    assert verdicts[0].status == runner.FAIL
    assert runner.exit_code(verdicts) == 1


def test_failure_records_where_expected_actual():
    results, _, _ = run(specs(buggy="timer_w1c_ignored"), ["reg_access_types"])
    bad = [r for r in results if r.backend == "buggy"][0]
    assert bad.status == runner.FAIL
    assert "TIMER.STATUS.MATCH" in bad.where
    assert bad.expected == "0x00000000" and bad.actual == "0x00000001"


def test_unavailable_backend_reports_error_for_each_test():
    def broken():
        raise BackendError("no simulator here")

    results, verdicts, _ = run([runner.BackendSpec("model", ModelBackend), runner.BackendSpec("rtl", broken)], ["timer_basic", "dma_copy_basic"])
    rtl = [r for r in results if r.backend == "rtl"]
    assert [r.status for r in rtl] == [runner.ERROR, runner.ERROR]
    assert "backend unavailable: no simulator here" in rtl[0].message
    assert {v.status for v in verdicts} == {runner.MISMATCH}


def test_unexpected_exception_becomes_error_with_traceback():
    class Exploding(ModelBackend):
        def read_reg(self, addr):
            raise RuntimeError("boom")

    results, _, _ = run([runner.BackendSpec("x", Exploding)], ["timer_basic"])
    assert results[0].status == runner.ERROR
    assert "RuntimeError: boom" in results[0].message


def test_skip_is_not_a_failure():
    case = framework.TestCase("skippy", "", lambda b, log: (_ for _ in ()).throw(framework.Skip("not here")))
    results = runner.run_suite([runner.BackendSpec("model", ModelBackend)], [case])
    verdicts = runner.analyze(results, ["model"], ["skippy"])
    assert results[0].status == runner.SKIP
    assert verdicts[0].status == runner.SKIP
    assert runner.exit_code(verdicts) == 0


def test_skip_on_one_backend_does_not_cause_mismatch():
    def fn(b, log):
        if b.name != "model":
            raise framework.Skip("model only")

    case = framework.TestCase("half", "", fn)
    class Other(ModelBackend):
        name = "other"
    results = runner.run_suite([runner.BackendSpec("model", ModelBackend), runner.BackendSpec("other", Other)], [case])
    verdicts = runner.analyze(results, ["model", "other"], ["half"])
    assert verdicts[0].status == runner.OK


def test_runner_resets_between_tests():
    seen = []
    cases = [
        framework.TestCase("one", "", lambda b, log: (b.write("TIMER.COMPARE", 5), seen.append(b.read("TIMER.COMPARE")))),
        framework.TestCase("two", "", lambda b, log: seen.append(b.read("TIMER.COMPARE"))),
    ]
    runner.run_suite([runner.BackendSpec("model", ModelBackend)], cases)
    assert seen == [5, 0xFFFFFFFF]


def test_console_table_and_mismatch_report():
    results, verdicts, labels = run(specs(buggy="dma_len_off_by_one"))
    table = report.console_table(verdicts, labels)
    assert "MISMATCH" in table and "model" in table and "buggy" in table
    text = report.mismatch_report(verdicts)
    assert "MISMATCH dma_copy_basic" in text
    assert "disagree: buggy" in text
    assert "guard word after dst" in text
    assert "expected: 0xa5a5a5a5" in text


def test_summary_counts():
    results, verdicts, _ = run(specs(buggy="dma_len_off_by_one"))
    line = report.summary_line(results, verdicts)
    assert "pass" in line and "mismatch" in line
    assert runner.counts(results, verdicts)[runner.MISMATCH] >= 2


def test_junit_xml_structure():
    results, verdicts, labels = run(specs(buggy="dma_len_off_by_one"))
    root = ET.fromstring(report.junit_xml(results, verdicts, labels))
    suites = {s.get("name"): s for s in root.findall("testsuite")}
    assert set(suites) == {"xplat.model", "xplat.buggy", "xplat.cross-backend"}
    assert suites["xplat.model"].get("failures") == "0"
    assert int(suites["xplat.buggy"].get("failures")) >= 1
    cross = suites["xplat.cross-backend"]
    failing = [c.get("name") for c in cross.findall("testcase") if c.find("failure") is not None]
    assert "dma_copy_basic" in failing
    assert int(root.get("failures")) == int(suites["xplat.buggy"].get("failures")) + int(cross.get("failures"))
    assert int(root.get("tests")) == 7 * 2 + 7


def test_junit_marks_errors_and_skips():
    results = [
        runner.TestResult("a", "t1", runner.ERROR, 0.1, message="Traceback\nValueError: x"),
        runner.TestResult("a", "t2", runner.SKIP, 0.0, message="why"),
    ]
    verdicts = runner.analyze(results, ["a"], ["t1", "t2"])
    root = ET.fromstring(report.junit_xml(results, verdicts, ["a"]))
    suite = root.find("testsuite")
    assert suite.get("errors") == "1" and suite.get("skipped") == "1"
    assert suite.find("testcase[@name='t1']/error").get("message") == "ValueError: x"


def test_html_report_contents():
    results, verdicts, labels = run(specs(buggy="dma_len_off_by_one"))
    page = report.html_report(results, verdicts, labels, {"seed": "0x1"})
    assert "<h1>xplat regression: FAILED</h1>" in page
    assert 'class="MISMATCH verdict"' in page
    assert "Cross-backend mismatches" in page
    assert "guard word after dst" in page
    for tag in ("table", "tr", "td", "th", "pre", "details"):
        assert page.count("<%s" % tag) == page.count("</%s>" % tag), tag


def test_html_escapes_messages():
    results = [runner.TestResult("a", "t", runner.FAIL, 0.0, message="<script>alert(1)</script>")]
    verdicts = runner.analyze(results, ["a"], ["t"])
    page = report.html_report(results, verdicts, ["a"], {})
    assert "<script>" not in page and "&lt;script&gt;" in page


def cli(*args):
    return subprocess.run([sys.executable, CLI, *args], capture_output=True, text=True, cwd=ROOT)


def test_cli_passes_on_model_and_fake_fpga(tmp_path):
    junit, page = tmp_path / "j.xml", tmp_path / "r.html"
    p = cli("--backends", "model,fpga", "--junit", str(junit), "--html", str(page), "--quiet")
    assert p.returncode == 0, p.stdout + p.stderr
    assert "REGRESSION PASSED" in p.stdout
    assert "fpga" in p.stdout
    ET.parse(junit)
    assert page.read_text().startswith("<!doctype html>")


def test_cli_test_filter_and_list():
    p = cli("--backend", "model", "--tests", "timer_basic", "--quiet")
    assert p.returncode == 0 and "reg_reset_values" not in p.stdout
    listing = cli("--list")
    assert listing.returncode == 0 and listing.stdout.count("\n") == 7


def test_cli_usage_errors_exit_two():
    assert cli("--backend", "warp").returncode == 2
    assert cli("--backend", "model", "--tests", "nope").returncode == 2


def test_cli_exits_nonzero_when_backend_unavailable():
    p = cli("--backends", "model,rtl", "--sim", "/nonexistent/soc_sim", "--quiet")
    assert p.returncode == 1
    assert "backend unavailable" in p.stdout and "MISMATCH" in p.stdout


def test_cli_seed_is_applied():
    p = cli("--backend", "model", "--tests", "random_dma", "--seed", "0x99")
    assert p.returncode == 0
    assert "random_dma" in p.stdout
