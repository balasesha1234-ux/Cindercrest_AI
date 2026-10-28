"""Task lifecycle orchestrator coordinating planning, policy gates, execution, and verification."""

import asyncio
import secrets
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from backend.app.agent.events import AuditEventLogger
from backend.app.agent.planner import TaskPlanner
from backend.app.agent.policy import AgentPolicyEngine
from backend.app.agent.schema import (
    AuditEventType,
    PolicyDecision,
    Task,
    TaskOutcome,
    TaskPlan,
    TaskState,
)
from backend.app.agent.tools.registry import ToolRegistry, tool_registry
from backend.app.agent.verifier import OutcomeVerifier
from backend.app.core.exceptions import NotFoundError, ValidationError
from backend.app.store.db import get_db_connection


class TaskOrchestrator:
    """Manages the full lifecycle of agent tasks adhering strictly to safety laws."""

    def __init__(
        self,
        database_url: str | None = None,
        registry: ToolRegistry | None = None,
        planner: TaskPlanner | None = None,
        policy: AgentPolicyEngine | None = None,
        verifier: OutcomeVerifier | None = None,
        event_logger: AuditEventLogger | None = None,
    ) -> None:
        self.database_url = database_url
        self.registry = registry or tool_registry
        self.planner = planner or TaskPlanner()
        self.policy = policy or AgentPolicyEngine(registry=self.registry)
        self.verifier = verifier or OutcomeVerifier()
        self.event_logger = event_logger or AuditEventLogger(database_url=self.database_url)
        self._cancellation_tokens: dict[str, bool] = {}

    def create_task(self, goal: str) -> Task:
        """Create a new task, determine intent, generate and persist a structured plan."""
        cleaned = goal.strip()
        if not cleaned:
            raise ValidationError("Task goal cannot be empty")

        task_id = f"task_{int(time.time())}_{secrets.token_hex(4)}"
        now = datetime.now(UTC)

        # 1. Initial creation
        task = Task(
            task_id=task_id,
            goal=cleaned,
            state=TaskState.CREATED,
            outcome=TaskOutcome.UNKNOWN,
            created_at=now,
            updated_at=now,
        )
        self._save_task(task)
        self.event_logger.log_event(
            task_id,
            AuditEventType.TASK_CREATED,
            {"goal": cleaned, "state": task.state},
        )

        # 2. Planning phase
        task.state = TaskState.PLANNING
        plan = self.planner.create_plan(cleaned)
        task.plan = plan
        task.intent_type = plan.intent

        # If plan requires approval, advance state
        if plan.requires_approval:
            task.state = TaskState.AWAITING_APPROVAL

        task.updated_at = datetime.now(UTC)
        self._save_task(task)
        self.event_logger.log_event(
            task_id,
            AuditEventType.PLAN_GENERATED,
            {
                "intent": plan.intent,
                "step_count": len(plan.steps),
                "requires_approval": plan.requires_approval,
            },
        )

        return task

    async def execute_task(self, task_id: str, timeout_sec: float = 30.0) -> Task:
        """Execute a planned task step-by-step through policy, execution, and verification gates."""
        task = self.get_task(task_id)

        # If already terminal or cancelled, return immediately
        if task.state in (
            TaskState.COMPLETED,
            TaskState.FAILED,
            TaskState.CANCELLED,
            TaskState.OUTCOME_UNKNOWN,
        ):
            return task

        # Check for pre-execution cancellation
        if self._cancellation_tokens.get(task_id, False):
            task.state = TaskState.CANCELLED
            task.outcome = TaskOutcome.CANCELLED
            self._save_task(task)
            return task

        if task.plan is None:
            raise ValidationError(f"Task '{task_id}' has no plan to execute")

        # Conversational tasks have 0 steps and complete directly
        if not task.plan.steps:
            task.state = TaskState.COMPLETED
            task.outcome = TaskOutcome.SUCCESS
            task.updated_at = datetime.now(UTC)
            self._save_task(task)
            self.event_logger.log_event(
                task_id,
                AuditEventType.TASK_COMPLETED,
                {"outcome": task.outcome, "reason": "Conversational prompt completed"},
            )
            return task

        task.state = TaskState.RUNNING
        self._save_task(task)

        try:
            async with asyncio.timeout(timeout_sec):
                for step in task.plan.steps:
                    # Check cancellation before step execution
                    if self._cancellation_tokens.get(task_id, False):
                        step.status = "cancelled"
                        task.state = TaskState.CANCELLED
                        task.outcome = TaskOutcome.CANCELLED
                        self._save_task(task)
                        self.event_logger.log_event(
                            task_id,
                            AuditEventType.TASK_CANCELLED,
                            {"step_index": step.step_index},
                        )
                        return task

                    task.current_step_index = step.step_index
                    step.status = "running"
                    self._save_task(task)
                    self.event_logger.log_event(
                        task_id,
                        AuditEventType.STEP_STARTED,
                        {"step_index": step.step_index, "tool_name": step.tool_name},
                    )

                    # Dynamic parameter resolution for sequential pipeline steps (e.g. search -> read)
                    if step.tool_name == "fs.read_text" and step.parameters.get("path") in (
                        "auto",
                        "",
                        None,
                    ):
                        prev_search = next(
                            (s for s in task.plan.steps if s.tool_name == "fs.search" and s.result),
                            None,
                        )
                        if prev_search and prev_search.result and prev_search.result.get("results"):
                            step.parameters["path"] = prev_search.result["results"][0]["path"]

                    # 1. Policy Gatekeeper: Model proposes, deterministic code decides
                    policy_res = self.policy.evaluate_action(step.tool_name, step.parameters)
                    self.event_logger.log_event(
                        task_id,
                        AuditEventType.POLICY_EVALUATED,
                        {
                            "step_index": step.step_index,
                            "tool_name": step.tool_name,
                            "decision": policy_res.decision,
                            "reason": policy_res.reason,
                        },
                    )

                    if policy_res.decision == PolicyDecision.DENY:
                        step.status = "failed"
                        step.error = f"Policy denied tool execution: {policy_res.reason}"
                        task.state = TaskState.FAILED
                        task.outcome = TaskOutcome.FAILURE
                        task.error_message = step.error
                        task.updated_at = datetime.now(UTC)
                        self._save_task(task)
                        self.event_logger.log_event(
                            task_id,
                            AuditEventType.TASK_FAILED,
                            {"error": step.error},
                        )
                        return task

                    if policy_res.decision == PolicyDecision.REQUIRE_APPROVAL:
                        step.status = "pending"
                        task.state = TaskState.AWAITING_APPROVAL
                        task.updated_at = datetime.now(UTC)
                        self._save_task(task)
                        return task

                    # 2. Tool Execution via Registry
                    try:
                        tool_output = await self.registry.execute(step.tool_name, step.parameters)
                        step.result = tool_output
                        step.status = "completed"
                        self.event_logger.log_event(
                            task_id,
                            AuditEventType.TOOL_EXECUTED,
                            {"step_index": step.step_index, "tool_name": step.tool_name},
                        )
                    except Exception as exc:
                        step.status = "failed"
                        step.error = str(exc)
                        task.state = TaskState.FAILED
                        task.outcome = TaskOutcome.FAILURE
                        task.error_message = f"Execution error in step {step.step_index}: {exc}"
                        task.updated_at = datetime.now(UTC)
                        self._save_task(task)
                        self.event_logger.log_event(
                            task_id,
                            AuditEventType.TASK_FAILED,
                            {"error": str(exc)},
                        )
                        return task

                    # 3. Independent Outcome Verification Gate: 'Attempted is not done'
                    task.state = TaskState.VERIFYING
                    self._save_task(task)

                    ver_res = self.verifier.verify_step(step)
                    self.event_logger.log_event(
                        task_id,
                        AuditEventType.OUTCOME_VERIFIED,
                        {
                            "step_index": step.step_index,
                            "verified": ver_res.verified,
                            "outcome": ver_res.outcome,
                            "reason": ver_res.reason,
                        },
                    )

                    if not ver_res.verified:
                        step.verified = False
                        task.state = (
                            TaskState.OUTCOME_UNKNOWN
                            if ver_res.outcome == TaskOutcome.UNKNOWN
                            else TaskState.FAILED
                        )
                        task.outcome = ver_res.outcome
                        task.error_message = f"Outcome verification failed for step {step.step_index}: {ver_res.reason}"
                        task.updated_at = datetime.now(UTC)
                        self._save_task(task)
                        return task

                    step.verified = True
                    task.state = TaskState.RUNNING
                    self._save_task(task)

                # All steps executed and independently verified
                task.state = TaskState.COMPLETED
                task.outcome = TaskOutcome.SUCCESS

                # Synthesize grounded summary from read document if applicable
                read_step = next(
                    (s for s in task.plan.steps if s.tool_name == "fs.read_text" and s.result),
                    None,
                )
                if read_step and read_step.result and isinstance(read_step.result, dict):
                    doc_path = read_step.result.get("path", "")
                    doc_text = read_step.result.get("content", "")
                    task.result_summary = self._synthesize_grounded_summary(doc_path, doc_text)

                task.updated_at = datetime.now(UTC)
                self._save_task(task)
                self.event_logger.log_event(
                    task_id,
                    AuditEventType.TASK_COMPLETED,
                    {"outcome": task.outcome, "summary": task.result_summary},
                )
                return task

        except TimeoutError:
            task.state = TaskState.OUTCOME_UNKNOWN
            task.outcome = TaskOutcome.UNKNOWN
            task.error_message = f"Task execution exceeded timeout limit of {timeout_sec}s"
            task.updated_at = datetime.now(UTC)
            self._save_task(task)
            self.event_logger.log_event(
                task_id,
                AuditEventType.TASK_FAILED,
                {"error": "Execution timeout", "state": task.state},
            )
            return task

    def cancel_task(self, task_id: str) -> Task:
        """Cancel an in-flight or planned task."""
        self._cancellation_tokens[task_id] = True
        task = self.get_task(task_id)
        task.state = TaskState.CANCELLED
        task.outcome = TaskOutcome.CANCELLED
        task.updated_at = datetime.now(UTC)
        self._save_task(task)
        self.event_logger.log_event(
            task_id,
            AuditEventType.TASK_CANCELLED,
            {"task_id": task_id, "state": task.state},
        )
        return task

    def get_task(self, task_id: str) -> Task:
        """Retrieve task by unique identifier from SQLite."""
        with get_db_connection(self.database_url) as conn:
            row = conn.execute(
                """
                SELECT task_id, goal, intent_type, state, outcome, plan_json, current_step_index, error_message, result_summary, created_at, updated_at
                FROM tasks
                WHERE task_id = ?
            """,
                (task_id,),
            ).fetchone()

            if not row:
                raise NotFoundError(message=f"Task '{task_id}' was not found")

            plan: TaskPlan | None = None
            if row["plan_json"]:
                try:
                    plan = TaskPlan.model_validate_json(row["plan_json"])
                except Exception:
                    plan = None

            return Task(
                task_id=row["task_id"],
                goal=row["goal"],
                intent_type=row["intent_type"],
                state=row["state"],
                outcome=row["outcome"],
                plan=plan,
                current_step_index=row["current_step_index"],
                error_message=row["error_message"],
                result_summary=row["result_summary"] if "result_summary" in row.keys() else None,
                created_at=datetime.fromisoformat(row["created_at"]),
                updated_at=datetime.fromisoformat(row["updated_at"]),
            )

    def list_tasks(self, limit: int = 50) -> list[Task]:
        """List tasks ordered by most recent first."""
        with get_db_connection(self.database_url) as conn:
            rows = conn.execute(
                """
                SELECT task_id, goal, intent_type, state, outcome, plan_json, current_step_index, error_message, result_summary, created_at, updated_at
                FROM tasks
                ORDER BY created_at DESC
                LIMIT ?
            """,
                (limit,),
            ).fetchall()

            tasks: list[Task] = []
            for row in rows:
                plan: TaskPlan | None = None
                if row["plan_json"]:
                    try:
                        plan = TaskPlan.model_validate_json(row["plan_json"])
                    except Exception:
                        plan = None

                tasks.append(
                    Task(
                        task_id=row["task_id"],
                        goal=row["goal"],
                        intent_type=row["intent_type"],
                        state=row["state"],
                        outcome=row["outcome"],
                        plan=plan,
                        current_step_index=row["current_step_index"],
                        error_message=row["error_message"],
                        result_summary=row["result_summary"]
                        if "result_summary" in row.keys()
                        else None,
                        created_at=datetime.fromisoformat(row["created_at"]),
                        updated_at=datetime.fromisoformat(row["updated_at"]),
                    )
                )
            return tasks

    def get_task_events(self, task_id: str) -> list[dict[str, Any]]:
        """Retrieve audit event trail for a task."""
        return self.event_logger.get_events_for_task(task_id)

    def _save_task(self, task: Task) -> None:
        """Persist task to SQLite table."""
        plan_json = task.plan.model_dump_json() if task.plan else "{}"
        created_str = task.created_at.isoformat()
        updated_str = task.updated_at.isoformat()

        with get_db_connection(self.database_url) as conn:
            conn.execute(
                """
                INSERT INTO tasks (
                    task_id, goal, intent_type, state, outcome, plan_json, current_step_index, error_message, result_summary, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(task_id) DO UPDATE SET
                    intent_type = excluded.intent_type,
                    state = excluded.state,
                    outcome = excluded.outcome,
                    plan_json = excluded.plan_json,
                    current_step_index = excluded.current_step_index,
                    error_message = excluded.error_message,
                    result_summary = excluded.result_summary,
                    updated_at = excluded.updated_at
            """,
                (
                    task.task_id,
                    task.goal,
                    task.intent_type.value
                    if hasattr(task.intent_type, "value")
                    else str(task.intent_type),
                    task.state.value if hasattr(task.state, "value") else str(task.state),
                    task.outcome.value if hasattr(task.outcome, "value") else str(task.outcome),
                    plan_json,
                    task.current_step_index,
                    task.error_message,
                    task.result_summary,
                    created_str,
                    updated_str,
                ),
            )
            conn.commit()

    def _synthesize_grounded_summary(self, path: str, content: str) -> str:
        """Synthesize a concise factual summary grounded strictly in document text."""
        if not content:
            return f"Document '{path}' is empty."

        lines = [line.strip() for line in content.splitlines() if line.strip()]
        title = ""
        headings: list[str] = []
        body_snippets: list[str] = []

        for line in lines:
            if line.startswith("# ") and not title:
                title = line.lstrip("# ").strip()
            elif line.startswith("## "):
                headings.append(line.lstrip("# ").strip())
            elif not line.startswith("#") and len(body_snippets) < 3 and len(line) > 20:
                body_snippets.append(line)

        title_display = title or Path(path).name
        summary_parts = [f"Summary of {title_display} ({path}):"]

        if headings:
            top_sections = ", ".join(headings[:4])
            summary_parts.append(f"Key sections covered: {top_sections}.")

        if body_snippets:
            snippet_summary = " ".join(body_snippets[:2])
            if len(snippet_summary) > 280:
                snippet_summary = snippet_summary[:277] + "..."
            summary_parts.append(f"Overview: {snippet_summary}")

        return " ".join(summary_parts)


# Global orchestrator singleton
task_orchestrator = TaskOrchestrator()
