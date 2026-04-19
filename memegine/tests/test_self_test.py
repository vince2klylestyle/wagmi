from __future__ import annotations

from memegine import self_test


def test_self_test_passes_end_to_end():
    """The big integration test: walk a synthetic operator through the
    whole pipeline. If this fails, something in the integration (not just
    a unit) is broken."""
    report = self_test.run()
    assert report.ok, report.as_text()


def test_self_test_reports_every_step():
    report = self_test.run()
    expected_steps = {
        "grade idea", "queue topic", "start session",
        "format suggest", "build pipeline", "deep lint",
        "fragments expand", "caption lint",
        "ref add winner + auto-codex",
        "engagement paste",
        "post build + X prepare",
        "stats/next/last dashboards",
        "validate config",
        "end session",
    }
    actual = {s.name for s in report.steps}
    assert expected_steps <= actual


def test_report_ok_computed_correctly():
    r = self_test.SelfTestReport()
    r.steps.append(self_test.StepResult("a", True))
    r.steps.append(self_test.StepResult("b", True))
    assert r.ok

    r.steps.append(self_test.StepResult("c", False, "fail"))
    assert not r.ok
