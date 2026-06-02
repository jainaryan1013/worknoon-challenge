#!/usr/bin/env python3
"""Aggregate JUnit XML from every test suite into one markdown report.

Stdlib only, so it runs inside the backend test image. Reads pytest and vitest
(and optionally Playwright) JUnit files and writes <dir>/test-report.md.

Usage:
    python scripts/aggregate_report.py /reports/backend.xml /reports/frontend.xml
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

# Friendly suite labels keyed by the XML filename stem.
_SUITE_LABELS = {
    "backend": "Backend (pytest)",
    "frontend": "Frontend (vitest)",
    "llm": "Adversarial — live LLM (pytest)",
    "e2e": "End-to-end (Playwright)",
}


@dataclass
class Case:
    suite: str
    group: str
    name: str
    status: str  # passed | failed | skipped
    time: float
    message: str = ""


@dataclass
class Suite:
    label: str
    cases: list[Case] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.cases)

    def count(self, status: str) -> int:
        return sum(1 for c in self.cases if c.status == status)

    @property
    def time(self) -> float:
        return sum(c.time for c in self.cases)


def _group_for(classname: str) -> str:
    """Human group label from a JUnit classname (pytest dotted path or file)."""
    if classname.startswith("tests."):
        parts = classname.split(".")
        return parts[1] if len(parts) > 1 else classname  # unit / integration / adversarial
    return classname  # vitest: a file path


def _parse(path: Path) -> Suite:
    label = _SUITE_LABELS.get(path.stem, path.stem)
    suite = Suite(label=label)
    tree = ET.parse(path)
    for tc in tree.iter("testcase"):
        classname = tc.get("classname") or tc.get("file") or ""
        name = tc.get("name") or ""
        time = float(tc.get("time") or 0.0)
        failure = tc.find("failure")
        error = tc.find("error")
        skipped = tc.find("skipped")
        if failure is not None or error is not None:
            node = failure if failure is not None else error
            status = "failed"
            message = (node.get("message") or (node.text or "")).strip().splitlines()[0:1]
            message = message[0] if message else ""
        elif skipped is not None:
            status = "skipped"
            message = (skipped.get("message") or "").strip()
        else:
            status = "passed"
            message = ""
        suite.cases.append(
            Case(suite=label, group=_group_for(classname), name=name,
                 status=status, time=time, message=message)
        )
    return suite


_ICON = {"passed": "✅", "failed": "❌", "skipped": "⚪"}


def _render(suites: list[Suite]) -> str:
    grand = {"passed": 0, "failed": 0, "skipped": 0, "total": 0, "time": 0.0}
    for s in suites:
        grand["passed"] += s.count("passed")
        grand["failed"] += s.count("failed")
        grand["skipped"] += s.count("skipped")
        grand["total"] += s.total
        grand["time"] += s.time

    status_word = "PASSED" if grand["failed"] == 0 else "FAILED"
    out: list[str] = [
        "# Test Report",
        "",
        f"_Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}_",
        "",
        f"## Overall: **{status_word}** — "
        f"{grand['passed']} passed, {grand['failed']} failed, "
        f"{grand['skipped']} skipped ({grand['total']} total, {grand['time']:.1f}s)",
        "",
        "| Suite | Total | ✅ Passed | ❌ Failed | ⚪ Skipped | Time |",
        "|-------|------:|---------:|---------:|----------:|-----:|",
    ]
    for s in suites:
        out.append(
            f"| {s.label} | {s.total} | {s.count('passed')} | "
            f"{s.count('failed')} | {s.count('skipped')} | {s.time:.1f}s |"
        )
    out.append("")

    # Backend category breakdown (unit / integration / adversarial).
    for s in suites:
        groups = sorted({c.group for c in s.cases})
        if len(groups) > 1:
            out += [f"### {s.label} — by category", "",
                    "| Category | Total | Passed | Failed | Skipped |",
                    "|----------|------:|-------:|-------:|--------:|"]
            for g in groups:
                cs = [c for c in s.cases if c.group == g]
                p = sum(1 for c in cs if c.status == "passed")
                f = sum(1 for c in cs if c.status == "failed")
                k = sum(1 for c in cs if c.status == "skipped")
                out.append(f"| `{g}` | {len(cs)} | {p} | {f} | {k} |")
            out.append("")

    # Failures detail.
    failures = [c for s in suites for c in s.cases if c.status == "failed"]
    if failures:
        out += ["## ❌ Failures", ""]
        for c in failures:
            out.append(f"- **{c.suite} · {c.group} · {c.name}** — {c.message}")
        out.append("")

    # Full appendix (collapsed).
    out += ["## All tests", ""]
    for s in suites:
        out += [f"<details><summary>{s.label} ({s.total})</summary>", ""]
        last_group = None
        for c in sorted(s.cases, key=lambda c: (c.group, c.name)):
            if c.group != last_group:
                out.append(f"\n**{c.group}**\n")
                last_group = c.group
            out.append(f"- {_ICON[c.status]} {c.name} ({c.time:.2f}s)")
        out += ["", "</details>", ""]

    return "\n".join(out)


def main(argv: list[str]) -> int:
    paths = [Path(a) for a in argv[1:] if Path(a).exists()]
    if not paths:
        print("aggregate_report: no JUnit XML files found", file=sys.stderr)
        return 2
    suites = [_parse(p) for p in paths]
    report = _render(suites)
    out_path = paths[0].parent / "test-report.md"
    out_path.write_text(report)
    total_failed = sum(s.count("failed") for s in suites)
    print(f"aggregate_report: wrote {out_path} ({total_failed} failures)")
    return 1 if total_failed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
