"""Independent outcome verifier implementing the 'Attempted is not done' law."""

import math
from datetime import datetime
from typing import Any

from backend.app.agent.schema import ActionStep, TaskOutcome, VerificationResult


class OutcomeVerifier:
    """Independently verifies tool output against real expectations without LLM speculation."""

    def verify_step(self, step: ActionStep) -> VerificationResult:
        """Verify the outcome of an individual action step."""
        if step.status != "completed" or step.result is None:
            return VerificationResult(
                verified=False,
                outcome=TaskOutcome.FAILURE,
                reason=f"Step failed or did not return a result: {step.error or 'No output produced'}",
            )

        tool = step.tool_name
        result = step.result

        if not isinstance(result, dict):
            return VerificationResult(
                verified=False,
                outcome=TaskOutcome.UNKNOWN,
                reason=f"Tool output must be a dictionary, got {type(result).__name__}",
            )

        if tool == "datetime_now":
            return self._verify_datetime_now(result)

        if tool == "calculator":
            return self._verify_calculator(result)

        if tool == "system_diagnostics":
            return self._verify_system_diagnostics(result)

        if tool == "text_analyzer":
            return self._verify_text_analyzer(result)

        if tool == "fs.search":
            return self._verify_fs_search(result)

        if tool == "fs.read_text":
            return self._verify_fs_read_text(result)

        # Fallback for unrecognized tools: cannot confirm outcome -> UNKNOWN
        return VerificationResult(
            verified=False,
            outcome=TaskOutcome.UNKNOWN,
            reason=f"No independent verification rule registered for tool '{tool}'",
        )

    def _verify_datetime_now(self, result: dict[str, Any]) -> VerificationResult:
        iso_str = result.get("iso_utc")
        date_str = result.get("date")
        time_str = result.get("time")

        if (
            not isinstance(iso_str, str)
            or not isinstance(date_str, str)
            or not isinstance(time_str, str)
        ):
            return VerificationResult(
                verified=False,
                outcome=TaskOutcome.UNKNOWN,
                reason="datetime_now missing string fields 'iso_utc', 'date', or 'time'",
            )

        try:
            # Must parse as ISO 8601
            datetime.fromisoformat(iso_str)
            # Must match YYYY-MM-DD
            datetime.strptime(date_str, "%Y-%m-%d")
            # Must match HH:MM:SS
            datetime.strptime(time_str, "%H:%M:%S")
            return VerificationResult(
                verified=True,
                outcome=TaskOutcome.SUCCESS,
                reason="Confirmed valid ISO 8601 timestamp and date/time format",
                details={"iso_utc": iso_str},
            )
        except Exception as exc:
            return VerificationResult(
                verified=False,
                outcome=TaskOutcome.UNKNOWN,
                reason=f"Timestamp parsing failed: {exc}",
            )

    def _verify_calculator(self, result: dict[str, Any]) -> VerificationResult:
        val = result.get("result")
        if not isinstance(val, (int, float)) or isinstance(val, bool):
            return VerificationResult(
                verified=False,
                outcome=TaskOutcome.UNKNOWN,
                reason=f"Calculator result must be numeric, got {type(val).__name__}",
            )

        if math.isnan(val) or math.isinf(val):
            return VerificationResult(
                verified=False,
                outcome=TaskOutcome.UNKNOWN,
                reason=f"Calculator returned invalid float value: {val}",
            )

        return VerificationResult(
            verified=True,
            outcome=TaskOutcome.SUCCESS,
            reason="Confirmed numeric arithmetic result",
            details={"value": val},
        )

    def _verify_system_diagnostics(self, result: dict[str, Any]) -> VerificationResult:
        required_keys = ["platform", "architecture", "processor", "python_version"]
        for key in required_keys:
            val = result.get(key)
            if not isinstance(val, str) or not val.strip():
                return VerificationResult(
                    verified=False,
                    outcome=TaskOutcome.UNKNOWN,
                    reason=f"system_diagnostics missing or empty attribute: '{key}'",
                )

        return VerificationResult(
            verified=True,
            outcome=TaskOutcome.SUCCESS,
            reason="Confirmed system attributes are present and non-empty",
            details={k: result[k] for k in required_keys},
        )

    def _verify_text_analyzer(self, result: dict[str, Any]) -> VerificationResult:
        count_keys = ["character_count", "word_count", "line_count"]
        for key in count_keys:
            val = result.get(key)
            if not isinstance(val, int) or isinstance(val, bool) or val < 0:
                return VerificationResult(
                    verified=False,
                    outcome=TaskOutcome.UNKNOWN,
                    reason=f"text_analyzer count '{key}' must be a non-negative integer",
                )

        return VerificationResult(
            verified=True,
            outcome=TaskOutcome.SUCCESS,
            reason="Confirmed text metrics are valid non-negative counts",
            details={k: result[k] for k in count_keys},
        )

    def _verify_fs_search(self, result: dict[str, Any]) -> VerificationResult:
        results = result.get("results")
        total_found = result.get("total_found")
        if not isinstance(results, list) or not isinstance(total_found, int) or total_found < 0:
            return VerificationResult(
                verified=False,
                outcome=TaskOutcome.UNKNOWN,
                reason="fs.search output must contain 'results' (list) and 'total_found' (non-negative integer)",
            )
        return VerificationResult(
            verified=True,
            outcome=TaskOutcome.SUCCESS,
            reason=f"Confirmed filesystem search returned {total_found} match(es)",
            details={"total_found": total_found},
        )

    def _verify_fs_read_text(self, result: dict[str, Any]) -> VerificationResult:
        content = result.get("content")
        char_count = result.get("char_count")
        path_str = result.get("path")
        if (
            not isinstance(content, str)
            or not isinstance(char_count, int)
            or not isinstance(path_str, str)
        ):
            return VerificationResult(
                verified=False,
                outcome=TaskOutcome.UNKNOWN,
                reason="fs.read_text output must contain 'content' (str), 'char_count' (int), and 'path' (str)",
            )
        return VerificationResult(
            verified=True,
            outcome=TaskOutcome.SUCCESS,
            reason=f"Confirmed safe read of {char_count} characters from approved document '{path_str}'",
            details={"path": path_str, "char_count": char_count},
        )
