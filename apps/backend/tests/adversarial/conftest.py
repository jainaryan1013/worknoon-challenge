"""Adversarial-suite reporting: emit a per-attack pass/fail table as evidence
(docs/components/08 §5). Written to apps/backend/adversarial-report.md.
"""

from __future__ import annotations

import pathlib

_RESULTS: list[tuple[str, str]] = []

_MARK = {
    "passed": "✅ blocked / enforced",
    "failed": "❌ BREACH",
    "skipped": "⚠️ skipped (no key)",
}


def pytest_runtest_logreport(report) -> None:
    if "adversarial" not in report.nodeid:
        return
    name = report.nodeid.split("::", 1)[-1]
    if report.when == "call":
        _RESULTS.append((name, report.outcome))
    elif report.skipped and report.when == "setup":
        _RESULTS.append((name, "skipped"))


def pytest_sessionfinish(session, exitstatus) -> None:
    if not _RESULTS:
        return
    total = len(_RESULTS)
    enforced = sum(1 for _, o in _RESULTS if o == "passed")
    breached = sum(1 for _, o in _RESULTS if o == "failed")
    lines = [
        "# Adversarial Suite Report",
        "",
        f"**{enforced}/{total} attacks blocked/enforced; {breached} breaches.**",
        "",
        "| Scenario | Result |",
        "|----------|--------|",
    ]
    for name, outcome in _RESULTS:
        lines.append(f"| `{name}` | {_MARK.get(outcome, outcome)} |")
    lines.append("")
    out = pathlib.Path(__file__).resolve().parents[2] / "adversarial-report.md"
    out.write_text("\n".join(lines))
