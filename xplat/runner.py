import time
import traceback
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from .framework import Skip, TestCase, TestFailure
from .hal.base import Backend, BackendError

PASS = "PASS"
FAIL = "FAIL"
ERROR = "ERROR"
SKIP = "SKIP"

OK = "ok"
MISMATCH = "MISMATCH"


@dataclass
class TestResult:
    __test__ = False

    backend: str
    test: str
    status: str
    seconds: float
    message: str = ""
    where: str = ""
    expected: str = ""
    actual: str = ""
    log: List[str] = field(default_factory=list)

    @property
    def failed(self) -> bool:
        return self.status in (FAIL, ERROR)


@dataclass
class BackendSpec:
    label: str
    factory: Callable[[], Backend]


@dataclass
class Verdict:
    test: str
    status: str
    detail: str
    results: Dict[str, TestResult]


ResultHook = Callable[[TestResult], None]


def run_one(backend: Backend, label: str, case: TestCase) -> TestResult:
    logs: List[str] = []
    start = time.monotonic()
    result = TestResult(label, case.name, PASS, 0.0, log=logs)
    try:
        backend.reset()
        case.fn(backend, logs.append)
    except TestFailure as e:
        result.status = FAIL
        result.message = str(e)
        result.where, result.expected, result.actual = e.where, e.expected, e.actual
    except Skip as e:
        result.status = SKIP
        result.message = str(e)
    except BackendError as e:
        result.status = ERROR
        result.message = "%s: %s" % (type(e).__name__, e)
    except Exception:
        result.status = ERROR
        result.message = traceback.format_exc()
    result.seconds = time.monotonic() - start
    return result


def run_backend(spec: BackendSpec, tests: List[TestCase], on_result: Optional[ResultHook] = None) -> List[TestResult]:
    results: List[TestResult] = []
    try:
        backend = spec.factory()
    except Exception as e:
        for case in tests:
            result = TestResult(spec.label, case.name, ERROR, 0.0, message="backend unavailable: %s" % e)
            results.append(result)
            if on_result:
                on_result(result)
        return results
    try:
        for case in tests:
            result = run_one(backend, spec.label, case)
            results.append(result)
            if on_result:
                on_result(result)
    finally:
        try:
            backend.close()
        except Exception:
            pass
    return results


def run_suite(specs: List[BackendSpec], tests: List[TestCase], on_result: Optional[ResultHook] = None) -> List[TestResult]:
    results: List[TestResult] = []
    for spec in specs:
        results.extend(run_backend(spec, tests, on_result))
    return results


def short(text: str) -> str:
    lines = [line for line in text.strip().splitlines() if line.strip()]
    return lines[-1].strip() if lines else ""


def analyze(results: List[TestResult], labels: List[str], test_names: List[str]) -> List[Verdict]:
    verdicts: List[Verdict] = []
    for name in test_names:
        per_backend = {r.backend: r for r in results if r.test == name}
        ran = [per_backend[l] for l in labels if l in per_backend and per_backend[l].status != SKIP]
        passing = [r for r in ran if r.status == PASS]
        failing = [r for r in ran if r.failed]
        if not ran:
            verdicts.append(Verdict(name, SKIP, "skipped on every backend", per_backend))
        elif passing and failing:
            lines = ["passes on %s but fails on %s" % (", ".join(r.backend for r in passing), ", ".join(r.backend for r in failing))]
            for r in failing:
                lines.append("%s: %s" % (r.backend, short(r.message)))
            verdicts.append(Verdict(name, MISMATCH, "; ".join(lines), per_backend))
        elif failing:
            detail = "; ".join("%s: %s" % (r.backend, short(r.message)) for r in failing)
            verdicts.append(Verdict(name, FAIL, detail, per_backend))
        else:
            verdicts.append(Verdict(name, OK, "", per_backend))
    return verdicts


def exit_code(verdicts: List[Verdict]) -> int:
    return 0 if all(v.status in (OK, SKIP) for v in verdicts) else 1


def counts(results: List[TestResult], verdicts: List[Verdict]) -> Dict[str, int]:
    tally = {PASS: 0, FAIL: 0, ERROR: 0, SKIP: 0}
    for r in results:
        tally[r.status] += 1
    tally[MISMATCH] = sum(1 for v in verdicts if v.status == MISMATCH)
    return tally
