"""Turn pytest JUnit XML into a Markdown test report.

Used by CI to publish the automatic test report on every run's summary page:
    python scripts/test_report.py "Unit & integration" reports/junit.xml >> "$GITHUB_STEP_SUMMARY"

Lists totals, every failure with its message, and every test with its result, so the
milestone logs can link to proof instead of hand-typed results.
"""

import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

ICONS = {"passed": "✅", "failed": "❌", "error": "💥", "skipped": "⏭️"}


@dataclass(frozen=True)
class Case:
    name: str
    outcome: str
    seconds: float
    message: str


def _first_line(text: str) -> str:
    stripped = text.strip()
    return stripped.splitlines()[0][:200] if stripped else ""


def read_cases(path: Path) -> list[Case]:
    root = ET.parse(path).getroot()  # noqa: S314 - trusted file produced by pytest in CI
    cases: list[Case] = []
    for element in root.iter("testcase"):
        outcome, message = "passed", ""
        for tag in ("failure", "error", "skipped"):
            child = element.find(tag)
            if child is not None:
                outcome = "failed" if tag == "failure" else tag
                message = _first_line(child.get("message") or child.text or "")
                break
        name = f"{element.get('classname', '')}::{element.get('name', '')}"
        cases.append(Case(name, outcome, float(element.get("time", "0")), message))
    return cases


def render(title: str, cases: list[Case]) -> str:
    counts = {key: sum(c.outcome == key for c in cases) for key in ICONS}
    lines = [
        f"## {title}: test report",
        "",
        f"**{len(cases)} tests**: ✅ {counts['passed']} passed · ❌ {counts['failed']} failed · "
        f"💥 {counts['error']} errors · ⏭️ {counts['skipped']} skipped",
        "",
    ]
    problems = [c for c in cases if c.outcome in ("failed", "error")]
    if problems:
        lines += ["### Failures", "", "| Test | Message |", "| --- | --- |"]
        lines += [f"| `{c.name}` | {c.message.replace('|', '/')} |" for c in problems]
        lines.append("")
    lines += [
        "<details><summary>All tests</summary>",
        "",
        "| Result | Test | Time (s) |",
        "| --- | --- | --- |",
    ]
    lines += [f"| {ICONS[c.outcome]} | `{c.name}` | {c.seconds:.3f} |" for c in cases]
    lines += ["", "</details>", ""]
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        sys.stderr.write("usage: test_report.py <title> <junit.xml>\n")
        return 2
    path = Path(argv[2])
    if not path.exists():
        sys.stdout.write(f"## {argv[1]}: no test results found ({path})\n")
        return 0
    sys.stdout.write(render(argv[1], read_cases(path)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
