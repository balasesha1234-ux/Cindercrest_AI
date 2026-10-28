"""Unit tests for the OutcomeVerifier enforcing the 'Attempted is not done' law."""

from backend.app.agent.schema import ActionStep, TaskOutcome
from backend.app.agent.verifier import OutcomeVerifier


def test_verify_datetime_now_success() -> None:
    verifier = OutcomeVerifier()
    step = ActionStep(
        step_index=1,
        tool_name="datetime_now",
        parameters={},
        expected_outcome="Timestamp",
        status="completed",
        result={
            "iso_utc": "2026-10-28T12:00:00+00:00",
            "date": "2026-10-28",
            "time": "12:00:00",
            "day_of_week": "Wednesday",
        },
    )
    res = verifier.verify_step(step)
    assert res.verified is True
    assert res.outcome == TaskOutcome.SUCCESS


def test_verify_datetime_now_invalid_format_returns_unknown() -> None:
    verifier = OutcomeVerifier()
    step = ActionStep(
        step_index=1,
        tool_name="datetime_now",
        parameters={},
        expected_outcome="Timestamp",
        status="completed",
        result={"iso_utc": "not-a-valid-date", "date": "bad", "time": "bad"},
    )
    res = verifier.verify_step(step)
    assert res.verified is False
    assert res.outcome == TaskOutcome.UNKNOWN


def test_verify_calculator_success() -> None:
    verifier = OutcomeVerifier()
    step = ActionStep(
        step_index=1,
        tool_name="calculator",
        parameters={"expression": "10 * 5"},
        expected_outcome="50",
        status="completed",
        result={"result": 50, "expression": "10 * 5"},
    )
    res = verifier.verify_step(step)
    assert res.verified is True
    assert res.outcome == TaskOutcome.SUCCESS


def test_verify_calculator_invalid_result_returns_unknown() -> None:
    verifier = OutcomeVerifier()
    step = ActionStep(
        step_index=1,
        tool_name="calculator",
        parameters={"expression": "10 * 5"},
        expected_outcome="50",
        status="completed",
        result={"result": "not_a_number"},
    )
    res = verifier.verify_step(step)
    assert res.verified is False
    assert res.outcome == TaskOutcome.UNKNOWN


def test_verify_uncompleted_step_returns_failure() -> None:
    verifier = OutcomeVerifier()
    step = ActionStep(
        step_index=1,
        tool_name="calculator",
        parameters={"expression": "1 + 1"},
        expected_outcome="2",
        status="failed",
        error="Division by zero",
    )
    res = verifier.verify_step(step)
    assert res.verified is False
    assert res.outcome == TaskOutcome.FAILURE


def test_verify_system_diagnostics_success() -> None:
    verifier = OutcomeVerifier()
    step = ActionStep(
        step_index=1,
        tool_name="system_diagnostics",
        parameters={},
        expected_outcome="Specs",
        status="completed",
        result={
            "platform": "Windows",
            "architecture": "AMD64",
            "processor": "Intel",
            "python_version": "3.14.6",
        },
    )
    res = verifier.verify_step(step)
    assert res.verified is True
    assert res.outcome == TaskOutcome.SUCCESS


def test_verify_text_analyzer_success() -> None:
    verifier = OutcomeVerifier()
    step = ActionStep(
        step_index=1,
        tool_name="text_analyzer",
        parameters={"text": "hello world"},
        expected_outcome="Metrics",
        status="completed",
        result={
            "character_count": 11,
            "character_count_no_spaces": 10,
            "word_count": 2,
            "line_count": 1,
        },
    )
    res = verifier.verify_step(step)
    assert res.verified is True
    assert res.outcome == TaskOutcome.SUCCESS
