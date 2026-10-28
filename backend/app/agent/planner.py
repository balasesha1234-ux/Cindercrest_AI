"""Structured task planner generating valid, typed plans for the orchestrator."""

import re

from backend.app.agent.analyzer import TaskAnalyzer
from backend.app.agent.schema import ActionStep, TaskIntent, TaskPlan
from backend.app.agent.validator import PlanValidator
from backend.app.core.exceptions import ValidationError


class TaskPlanner:
    """Produces structured plans from user prompts, backed by analyzer classification and validator verification."""

    def __init__(
        self,
        analyzer: TaskAnalyzer | None = None,
        validator: PlanValidator | None = None,
    ) -> None:
        self.analyzer = analyzer or TaskAnalyzer()
        self.validator = validator or PlanValidator()

    def create_plan(self, goal: str) -> TaskPlan:
        """Analyze intent and generate a validated TaskPlan."""
        cleaned = goal.strip()
        if not cleaned:
            raise ValidationError("Task goal cannot be empty")

        intent_res = self.analyzer.classify_intent(cleaned)
        intent = intent_res.intent

        # 1. Conversational intent: 0 steps, direct verbal or text answer
        if intent == TaskIntent.CONVERSATION:
            plan = TaskPlan(
                goal=cleaned,
                intent=intent,
                steps=[],
                requires_approval=False,
            )
            self.validator.validate_plan(plan)
            return plan

        # 2. Information / Lookup intent
        if intent == TaskIntent.INFORMATION:
            steps = self._plan_information_steps(cleaned)
            plan = TaskPlan(
                goal=cleaned,
                intent=intent,
                steps=steps,
                requires_approval=False,
            )
            self.validator.validate_plan(plan)
            return plan

        # 3. Multi-step Task Execution intent
        steps = self._plan_task_execution_steps(cleaned)
        plan = TaskPlan(
            goal=cleaned,
            intent=intent,
            steps=steps,
            requires_approval=False,
        )
        self.validator.validate_plan(plan)
        return plan

    def _plan_information_steps(self, text: str) -> list[ActionStep]:
        lowered = text.lower()

        # Date / Time
        if any(w in lowered for w in ["time", "date", "day", "clock"]):
            return [
                ActionStep(
                    step_index=1,
                    tool_name="datetime_now",
                    parameters={},
                    expected_outcome="Current ISO UTC timestamp and local date/time",
                )
            ]

        # Document search / read
        if any(
            w in lowered
            for w in [
                "find doc",
                "search doc",
                "find file",
                "search file",
                "read file",
                "read doc",
                "document",
                "documentation",
            ]
        ):
            explicit_path = self._extract_document_path(text)
            if explicit_path:
                return [
                    ActionStep(
                        step_index=1,
                        tool_name="fs.read_text",
                        parameters={"path": explicit_path},
                        expected_outcome=f"Read approved document '{explicit_path}'",
                    )
                ]
            query_term = self._extract_fs_query(text)
            return [
                ActionStep(
                    step_index=1,
                    tool_name="fs.search",
                    parameters={"query": query_term},
                    expected_outcome=f"Search approved documents for '{query_term}'",
                )
            ]

        # Calculation / Arithmetic
        if any(w in lowered for w in ["calculate", "compute", "solve", "+", "-", "*", "/", "^"]):
            expr = self._extract_math_expression(text)
            return [
                ActionStep(
                    step_index=1,
                    tool_name="calculator",
                    parameters={"expression": expr},
                    expected_outcome=f"Evaluated arithmetic result for {expr}",
                )
            ]

        # System Specs / Diagnostics
        if any(w in lowered for w in ["spec", "diagnostic", "platform", "os", "system"]):
            return [
                ActionStep(
                    step_index=1,
                    tool_name="system_diagnostics",
                    parameters={},
                    expected_outcome="Host system hardware architecture and OS version",
                )
            ]

        # Text Analysis
        if any(
            w in lowered for w in ["count word", "analyze text", "word count", "character count"]
        ):
            extracted = self._extract_target_text(text)
            return [
                ActionStep(
                    step_index=1,
                    tool_name="text_analyzer",
                    parameters={"text": extracted},
                    expected_outcome="Text metrics (characters, words, lines)",
                )
            ]

        # Default fallback information step: check time
        return [
            ActionStep(
                step_index=1,
                tool_name="datetime_now",
                parameters={},
                expected_outcome="Current timestamp",
            )
        ]

    def _plan_task_execution_steps(self, text: str) -> list[ActionStep]:
        lowered = text.lower()
        steps: list[ActionStep] = []
        step_idx = 1

        # Check for filesystem search and document reading component
        if any(
            w in lowered
            for w in [
                "document",
                "file",
                "assessment",
                "summariz",
                "read text",
                "find doc",
                "search doc",
            ]
        ):
            explicit_path = self._extract_document_path(text)
            if explicit_path:
                steps.append(
                    ActionStep(
                        step_index=step_idx,
                        tool_name="fs.read_text",
                        parameters={"path": explicit_path},
                        expected_outcome=f"Read approved document '{explicit_path}'",
                    )
                )
                step_idx += 1
            else:
                query_term = self._extract_fs_query(text)
                steps.append(
                    ActionStep(
                        step_index=step_idx,
                        tool_name="fs.search",
                        parameters={"query": query_term},
                        expected_outcome=f"Find relevant documents matching '{query_term}' in approved directories",
                    )
                )
                step_idx += 1
                steps.append(
                    ActionStep(
                        step_index=step_idx,
                        tool_name="fs.read_text",
                        parameters={"path": "auto"},
                        expected_outcome="Read and extract grounded text content from the discovered document",
                    )
                )
                step_idx += 1

        # Check for calculation component
        if any(w in lowered for w in ["calculate", "compute", "math"]) or re.search(
            r"\d+\s*[\+\-\*\/]\s*\d+", text
        ):
            expr = self._extract_math_expression(text)
            steps.append(
                ActionStep(
                    step_index=step_idx,
                    tool_name="calculator",
                    parameters={"expression": expr},
                    expected_outcome=f"Evaluated arithmetic result for {expr}",
                )
            )
            step_idx += 1

        # Check for system diagnostics component
        if not any(w in lowered for w in ["document", "file"]) and any(
            w in lowered for w in ["system", "diagnostic", "spec"]
        ):
            steps.append(
                ActionStep(
                    step_index=step_idx,
                    tool_name="system_diagnostics",
                    parameters={},
                    expected_outcome="System hardware architecture and OS diagnostic attributes",
                )
            )
            step_idx += 1

        # Check for date / time component
        if any(w in lowered for w in ["time", "date", "clock", "timestamp"]):
            steps.append(
                ActionStep(
                    step_index=step_idx,
                    tool_name="datetime_now",
                    parameters={},
                    expected_outcome="Current timestamp in ISO format",
                )
            )
            step_idx += 1

        # Check for text analysis component
        if any(w in lowered for w in ["text", "count", "word", "analyze"]):
            extracted = self._extract_target_text(text)
            steps.append(
                ActionStep(
                    step_index=step_idx,
                    tool_name="text_analyzer",
                    parameters={"text": extracted},
                    expected_outcome="Character and word count metrics",
                )
            )
            step_idx += 1

        # Fallback if no specific tools matched multi-step prompt: run diagnostics then time
        if not steps:
            steps = [
                ActionStep(
                    step_index=1,
                    tool_name="system_diagnostics",
                    parameters={},
                    expected_outcome="System diagnostic profile",
                ),
                ActionStep(
                    step_index=2,
                    tool_name="datetime_now",
                    parameters={},
                    expected_outcome="Current execution timestamp",
                ),
            ]

        return steps

    def _extract_math_expression(self, text: str) -> str:
        # Match common prefixes like "calculate 50 * 2"
        match = re.search(
            r"(?:calculate|compute|solve|what is)\s+([0-9\.\s\+\-\*\/\^\(\)]+)", text, re.IGNORECASE
        )
        if match:
            expr = match.group(1).strip().rstrip(",.")
            if expr:
                return expr

        # Match raw math expressions e.g. "50 * 2"
        match2 = re.search(r"([0-9\.\s\+\-\*\/\^\(\)]{3,})", text)
        if match2:
            expr2 = match2.group(1).strip().rstrip(",.")
            if expr2:
                return expr2

        return "1 + 1"

    def _extract_target_text(self, text: str) -> str:
        # Match quotes: 'hello world' or "hello world"
        match = re.search(r"['\"]([^'\"]+)['\"]", text)
        if match:
            return match.group(1)
        # Fallback to the user text itself
        return text

    def _extract_document_path(self, text: str) -> str | None:
        """Extract explicit document path if present in prompt."""
        match = re.search(
            r"\b((?:docs[\\/])?[a-zA-Z0-9_\-\.]+\.(?:md|txt|json|csv|log|py))\b",
            text,
            re.IGNORECASE,
        )
        if match:
            return match.group(1).replace("\\", "/")
        return None

    def _extract_fs_query(self, text: str) -> str:
        """Extract relevant search keyword or pattern for document lookup."""
        lowered = text.lower()
        if "speech" in lowered or "assessment" in lowered:
            return "speech"
        if "security" in lowered:
            return "security"
        if "decision" in lowered:
            return "decision"
        if "status" in lowered:
            return "status"
        if "test" in lowered:
            return "test"
        if "vision" in lowered:
            return "vision"

        # Regex extract: "find the <topic> document"
        m = re.search(
            r"(?:find|search for|look for|about)\s+(?:the\s+)?([a-zA-Z0-9_\-]{3,25})",
            text,
            re.IGNORECASE,
        )
        if m:
            candidate = m.group(1).strip()
            if candidate not in ("the", "document", "file", "project"):
                return candidate

        return "md"
