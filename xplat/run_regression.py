#!/usr/bin/env python3
import argparse
import os
import subprocess
import sys
from typing import List

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from xplat import framework, report, runner  # noqa: E402
from xplat.hal import BACKENDS, BUGS, BackendOptions, create_backend  # noqa: E402
from xplat.hal.registry import FAKE_PORT, bug_sim_path  # noqa: E402
from xplat.hal.rtl import DEFAULT_FW, DEFAULT_SIM  # noqa: E402
from xplat.tests import ORDER, all_tests  # noqa: E402


def backend_label(name: str, opts: BackendOptions) -> str:
    if name == "fpga" and opts.serial_port == FAKE_PORT:
        return "fpga"
    return name


def write(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w") as f:
        f.write(text)


def build_bug_sim(bug: str) -> bool:
    sim = bug_sim_path(bug)
    if os.path.exists(sim):
        return True
    print("building simulator with bug %s ..." % bug, flush=True)
    done = subprocess.run(["make", "-C", ROOT, os.path.relpath(sim, ROOT)], capture_output=True, text=True)
    if done.returncode != 0:
        print(done.stdout + done.stderr, file=sys.stderr)
    return done.returncode == 0


def parse_args(argv: List[str]) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Run every xplat test on each backend and compare the results.")
    ap.add_argument("--backends", default="model,rtl", help="comma list from: %s (default model,rtl)" % ", ".join(BACKENDS))
    ap.add_argument("--backend", help="shorthand for a single backend")
    ap.add_argument("--tests", help="comma list of test names, default all")
    ap.add_argument("--list", action="store_true", help="list tests and exit")
    ap.add_argument("--seed", type=lambda s: int(s, 0), default=framework.DEFAULT_SEED)
    ap.add_argument("--serial", default=FAKE_PORT, help="serial port for the fpga backend, or 'fake' (default)")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--reset-command", help="shell command that resets the FPGA between tests")
    ap.add_argument("--sim", default=DEFAULT_SIM)
    ap.add_argument("--firmware", default=DEFAULT_FW)
    ap.add_argument("--inject-bug", choices=BUGS, help="plant a deliberate bug to prove the regression catches it")
    ap.add_argument("--bug-target", choices=("rtl", "model"), default="rtl", help="where --inject-bug plants the bug (default rtl)")
    ap.add_argument("--junit", help="write JUnit XML here")
    ap.add_argument("--html", help="write an HTML report here")
    ap.add_argument("--quiet", action="store_true", help="only print the table and verdict")
    return ap.parse_args(argv)


def main(argv: List[str]) -> int:
    args = parse_args(argv)

    if args.list:
        for case in all_tests():
            print("%-18s %s" % (case.name, case.description))
        return 0

    names = [args.backend] if args.backend else [n.strip() for n in args.backends.split(",") if n.strip()]
    for n in names:
        if n not in BACKENDS:
            print("unknown backend %r, choose from %s" % (n, ", ".join(BACKENDS)), file=sys.stderr)
            return 2

    tests = all_tests()
    if args.tests:
        wanted = [t.strip() for t in args.tests.split(",") if t.strip()]
        unknown = [t for t in wanted if t not in ORDER]
        if unknown:
            print("unknown test(s): %s" % ", ".join(unknown), file=sys.stderr)
            return 2
        tests = [t for t in tests if t.name in wanted]

    if args.inject_bug and args.bug_target == "rtl" and "rtl" in names and not build_bug_sim(args.inject_bug):
        print("could not build the bugged simulator", file=sys.stderr)
        return 2

    framework.config.seed = args.seed
    opts = BackendOptions(
        bug=args.inject_bug,
        bug_target=args.bug_target,
        sim=args.sim,
        firmware=args.firmware,
        serial_port=args.serial,
        baud=args.baud,
        reset_command=args.reset_command,
    )
    specs = [runner.BackendSpec(backend_label(n, opts), (lambda n=n: create_backend(n, opts))) for n in names]
    labels = [s.label for s in specs]

    def progress(r: runner.TestResult) -> None:
        if not args.quiet:
            print("[%-9s] %-18s %-5s %.2fs" % (r.backend, r.test, r.status, r.seconds), flush=True)

    if args.inject_bug:
        print("injected bug: %s planted in the %s" % (args.inject_bug, args.bug_target))
    results = runner.run_suite(specs, tests, progress)
    verdicts = runner.analyze(results, labels, [t.name for t in tests])

    print()
    print(report.console_table(verdicts, labels))
    print()
    print(report.summary_line(results, verdicts))

    details = report.failure_details(results)
    if details:
        print("\nFAILURES\n" + details)
    mismatches = report.mismatch_report(verdicts)
    if mismatches:
        print("\nMISMATCHES\n" + mismatches)

    meta = {"seed": hex(args.seed), "backends": ",".join(labels), "tests": str(len(tests))}
    if args.inject_bug:
        meta["injected bug"] = "%s in %s" % (args.inject_bug, args.bug_target)
    if args.junit:
        write(args.junit, report.junit_xml(results, verdicts, labels))
        print("\njunit: %s" % args.junit)
    if args.html:
        write(args.html, report.html_report(results, verdicts, labels, meta))
        print("html:  %s" % args.html)

    code = runner.exit_code(verdicts)
    print("\nREGRESSION %s" % ("PASSED" if code == 0 else "FAILED"))
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
