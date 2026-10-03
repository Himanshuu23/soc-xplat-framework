import datetime
import html
import xml.etree.ElementTree as ET
from typing import Dict, List

from .runner import ERROR, FAIL, MISMATCH, OK, PASS, SKIP, TestResult, Verdict, counts


def cell(result: TestResult) -> str:
    if result is None:
        return "-"
    return "%s %.2fs" % (result.status, result.seconds)


def console_table(verdicts: List[Verdict], labels: List[str]) -> str:
    name_w = max([len("TEST")] + [len(v.test) for v in verdicts])
    widths = {l: max(len(l), 11) for l in labels}
    header = "%-*s  " % (name_w, "TEST") + "  ".join("%-*s" % (widths[l], l) for l in labels) + "  VERDICT"
    lines = [header, "-" * len(header)]
    for v in verdicts:
        cells = []
        for l in labels:
            r = v.results.get(l)
            cells.append("%-*s" % (widths[l], cell(r) if r else "-"))
        lines.append("%-*s  " % (name_w, v.test) + "  ".join(cells) + "  " + v.status)
    return "\n".join(lines)


def failure_details(results: List[TestResult]) -> str:
    blocks = []
    for r in results:
        if not r.failed:
            continue
        block = ["[%s] %s %s" % (r.backend, r.test, r.status)]
        block.append("    " + r.message.strip().replace("\n", "\n    "))
        for line in r.log:
            block.append("    log: " + line)
        blocks.append("\n".join(block))
    return "\n\n".join(blocks)


def mismatch_report(verdicts: List[Verdict]) -> str:
    lines = []
    for v in verdicts:
        if v.status != MISMATCH:
            continue
        lines.append("MISMATCH %s" % v.test)
        passing = [r for r in v.results.values() if r.status == PASS]
        failing = [r for r in v.results.values() if r.failed]
        lines.append("    agree:    %s" % ", ".join(r.backend for r in passing))
        for r in failing:
            lines.append("    disagree: %s" % r.backend)
            if r.where:
                lines.append("        where:    %s" % r.where)
                lines.append("        expected: %s" % r.expected)
                lines.append("        actual:   %s" % r.actual)
            else:
                lines.append("        error:    %s" % r.message.strip().splitlines()[-1])
    return "\n".join(lines)


def summary_line(results: List[TestResult], verdicts: List[Verdict]) -> str:
    tally = counts(results, verdicts)
    return "%d results: %d pass, %d fail, %d error, %d skip, %d mismatch" % (
        len(results),
        tally[PASS],
        tally[FAIL],
        tally[ERROR],
        tally[SKIP],
        tally[MISMATCH],
    )


def junit_xml(results: List[TestResult], verdicts: List[Verdict], labels: List[str]) -> str:
    root = ET.Element("testsuites", name="xplat")
    total = {"tests": 0, "failures": 0, "errors": 0, "skipped": 0}

    def add_case(suite: ET.Element, r: TestResult) -> None:
        case = ET.SubElement(suite, "testcase", classname=suite.get("name"), name=r.test, time="%.3f" % r.seconds)
        if r.status == FAIL:
            ET.SubElement(case, "failure", message=r.message.splitlines()[0] if r.message else "failed", type="TestFailure").text = r.message
        elif r.status == ERROR:
            ET.SubElement(case, "error", message=(r.message.strip().splitlines() or ["error"])[-1], type="BackendError").text = r.message
        elif r.status == SKIP:
            ET.SubElement(case, "skipped", message=r.message)
        if r.log:
            ET.SubElement(case, "system-out").text = "\n".join(r.log)

    def finish(suite: ET.Element, rows: List[TestResult]) -> None:
        stats = {
            "tests": len(rows),
            "failures": sum(1 for r in rows if r.status == FAIL),
            "errors": sum(1 for r in rows if r.status == ERROR),
            "skipped": sum(1 for r in rows if r.status == SKIP),
        }
        for k, v in stats.items():
            suite.set(k, str(v))
            total[k] += v
        suite.set("time", "%.3f" % sum(r.seconds for r in rows))

    for label in labels:
        rows = [r for r in results if r.backend == label]
        suite = ET.SubElement(root, "testsuite", name="xplat.%s" % label)
        for r in rows:
            add_case(suite, r)
        finish(suite, rows)

    cross = ET.SubElement(root, "testsuite", name="xplat.cross-backend")
    for v in verdicts:
        case = ET.SubElement(cross, "testcase", classname="xplat.cross-backend", name=v.test, time="0")
        if v.status == MISMATCH:
            ET.SubElement(case, "failure", message="backends disagree", type="Mismatch").text = v.detail
    cross.set("tests", str(len(verdicts)))
    cross.set("failures", str(sum(1 for v in verdicts if v.status == MISMATCH)))
    cross.set("errors", "0")
    cross.set("skipped", "0")
    cross.set("time", "0")
    total["tests"] += len(verdicts)
    total["failures"] += sum(1 for v in verdicts if v.status == MISMATCH)

    for k, v in total.items():
        root.set(k, str(v))
    ET.indent(root)
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding="unicode") + "\n"


CSS = """
body{font-family:system-ui,sans-serif;margin:2rem;color:#1b1b1b}
h1{margin-bottom:.2rem}
.meta{color:#555;margin-bottom:1.5rem}
table{border-collapse:collapse;margin:1rem 0}
th,td{border:1px solid #ccc;padding:.4rem .8rem;text-align:left}
th{background:#f3f3f3}
.PASS,.ok{background:#d8f3dc}
.FAIL,.ERROR,.MISMATCH{background:#ffd6d6;font-weight:600}
.SKIP{background:#eee;color:#666}
pre{background:#f7f7f7;border:1px solid #ddd;padding:.7rem;overflow-x:auto}
details{margin:.5rem 0}
summary{cursor:pointer}
.verdict{font-weight:700}
""".strip()


def html_report(results: List[TestResult], verdicts: List[Verdict], labels: List[str], meta: Dict[str, str]) -> str:
    e = html.escape
    out: List[str] = ["<!doctype html>", '<html lang="en"><head><meta charset="utf-8"><title>xplat regression</title>']
    out.append("<style>%s</style></head><body>" % CSS)
    overall = "PASSED" if all(v.status in (OK, SKIP) for v in verdicts) else "FAILED"
    out.append("<h1>xplat regression: %s</h1>" % overall)
    meta_text = " | ".join("%s: %s" % (k, v) for k, v in meta.items())
    out.append('<div class="meta">%s | generated %s</div>' % (e(meta_text), datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    out.append("<p>%s</p>" % e(summary_line(results, verdicts)))

    out.append("<table><tr><th>test</th>%s<th>verdict</th></tr>" % "".join("<th>%s</th>" % e(l) for l in labels))
    for v in verdicts:
        row = ["<tr><td>%s</td>" % e(v.test)]
        for l in labels:
            r = v.results.get(l)
            if r is None:
                row.append("<td>-</td>")
            else:
                row.append('<td class="%s">%s<br><small>%.2fs</small></td>' % (r.status, r.status, r.seconds))
        row.append('<td class="%s verdict">%s</td></tr>' % (v.status, e(v.status)))
        out.append("".join(row))
    out.append("</table>")

    mism = [v for v in verdicts if v.status == MISMATCH]
    if mism:
        out.append("<h2>Cross-backend mismatches</h2>")
        out.append("<pre>%s</pre>" % e(mismatch_report(verdicts)))

    failed = [r for r in results if r.failed]
    if failed:
        out.append("<h2>Failure logs</h2>")
        for r in failed:
            out.append("<details open><summary>[%s] %s %s</summary><pre>%s</pre></details>" % (e(r.backend), e(r.test), r.status, e(r.message.strip() + "".join("\nlog: " + l for l in r.log))))

    out.append("<h2>Runtime</h2><table><tr><th>backend</th><th>total seconds</th></tr>")
    for l in labels:
        out.append("<tr><td>%s</td><td>%.2f</td></tr>" % (e(l), sum(r.seconds for r in results if r.backend == l)))
    out.append("</table></body></html>")
    return "\n".join(out) + "\n"
