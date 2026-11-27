"""Section 1.6: the automatic test report script used by CI."""

from pathlib import Path

from scripts.test_report import main, read_cases, render

JUNIT = """<?xml version="1.0" encoding="utf-8"?>
<testsuites><testsuite name="pytest" tests="4">
  <testcase classname="tests.a" name="test_ok" time="0.010"/>
  <testcase classname="tests.a" name="test_bad" time="0.020">
    <failure message="assert 1 == 2&#10;second line">trace</failure>
  </testcase>
  <testcase classname="tests.b" name="test_boom" time="0.001">
    <error message="">RuntimeError: x | y</error>
  </testcase>
  <testcase classname="tests.b" name="test_later" time="0">
    <skipped message="needs services"/>
  </testcase>
</testsuite></testsuites>
"""


def _write(tmp_path: Path, content: str = JUNIT) -> Path:
    path = tmp_path / "junit.xml"
    path.write_text(content, encoding="utf-8")
    return path


def test_s1_6_04_reads_every_outcome_and_message(tmp_path: Path) -> None:
    cases = read_cases(_write(tmp_path))
    assert [c.outcome for c in cases] == ["passed", "failed", "error", "skipped"]
    assert cases[1].message == "assert 1 == 2"
    assert cases[2].message == "RuntimeError: x | y"


def test_s1_6_05_totals_failures_and_all_tests_with_pipes_escaped(tmp_path: Path) -> None:
    report = render("Suite", read_cases(_write(tmp_path)))
    assert "**4 tests**: ✅ 1 passed · ❌ 1 failed · 💥 1 errors · ⏭️ 1 skipped" in report
    assert "### Failures" in report
    assert "RuntimeError: x / y" in report
    assert "`tests.a::test_ok`" in report


def test_s1_6_06_no_failures_means_no_failure_section(tmp_path: Path) -> None:
    path = _write(tmp_path, '<testsuite><testcase classname="t" name="ok" time="0"/></testsuite>')
    assert "### Failures" not in render("Suite", read_cases(path))


def test_s1_6_06_missing_results_file_and_bad_usage(tmp_path: Path) -> None:
    assert main(["x", "Suite", str(tmp_path / "missing.xml")]) == 0
    assert main(["x"]) == 2
    assert main(["x", "Suite", str(_write(tmp_path))]) == 0
