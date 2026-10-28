"""Safe, deterministic builtin tools adhering to the Real Implementation Law."""

import ast
import math
import operator
import platform
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from backend.app.agent.schema import ToolSafetyTier
from backend.app.agent.tools.registry import ToolDefinition, tool_registry
from backend.app.core.exceptions import ValidationError

# Supported arithmetic operators for safe calculator
SAFE_OPERATORS: dict[type[ast.AST], Callable[..., Any]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}

# Whitelisted safe math functions
SAFE_MATH_FUNCS: dict[str, Callable[..., Any] | float] = {
    "sqrt": math.sqrt,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "log": math.log,
    "abs": abs,
    "round": round,
    "pi": math.pi,
    "e": math.e,
}


def _safe_eval_node(node: ast.AST) -> Any:
    """Recursively evaluate an AST node safely without calling eval()."""
    if isinstance(node, ast.Expression):
        return _safe_eval_node(node.body)

    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float, complex)):
            return node.value
        raise ValidationError(f"Invalid constant type: {type(node.value).__name__}")

    if isinstance(node, ast.BinOp):
        bin_op_type = type(node.op)
        if bin_op_type not in SAFE_OPERATORS:
            raise ValidationError(f"Unsupported binary operator: {bin_op_type.__name__}")
        left = _safe_eval_node(node.left)
        right = _safe_eval_node(node.right)
        bin_fn = SAFE_OPERATORS[bin_op_type]
        return bin_fn(left, right)

    if isinstance(node, ast.UnaryOp):
        unary_op_type = type(node.op)
        if unary_op_type not in SAFE_OPERATORS:
            raise ValidationError(f"Unsupported unary operator: {unary_op_type.__name__}")
        operand = _safe_eval_node(node.operand)
        unary_fn = SAFE_OPERATORS[unary_op_type]
        return unary_fn(operand)

    if isinstance(node, ast.Name):
        if node.id in SAFE_MATH_FUNCS:
            val = SAFE_MATH_FUNCS[node.id]
            if not callable(val):
                return val
        raise ValidationError(f"Unauthorized variable or identifier: {node.id}")

    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name):
            raise ValidationError("Direct function calls only")
        func_name = node.func.id
        if func_name not in SAFE_MATH_FUNCS:
            raise ValidationError(f"Unauthorized function call: {func_name}")
        fn_target = SAFE_MATH_FUNCS[func_name]
        if not callable(fn_target):
            raise ValidationError(f"Identifier is not callable: {func_name}")
        args = [_safe_eval_node(arg) for arg in node.args]
        return fn_target(*args)

    raise ValidationError(f"Disallowed AST node: {type(node).__name__}")


# Tool Handlers
async def datetime_now_handler(parameters: dict[str, Any]) -> dict[str, Any]:
    """Return the current local and UTC timestamp."""
    now = datetime.now(UTC)
    return {
        "iso_utc": now.isoformat(),
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M:%S"),
        "day_of_week": now.strftime("%A"),
        "timezone": "UTC",
    }


async def calculator_handler(parameters: dict[str, Any]) -> dict[str, Any]:
    """Evaluate an arithmetic expression using safe AST evaluation."""
    expr = parameters.get("expression")
    if not expr or not isinstance(expr, str) or not expr.strip():
        raise ValidationError("Missing or empty 'expression' parameter")

    clean_expr = expr.strip()
    try:
        parsed = ast.parse(clean_expr, mode="eval")
        result = _safe_eval_node(parsed)
        return {
            "expression": clean_expr,
            "result": result,
            "type": type(result).__name__,
        }
    except ZeroDivisionError:
        raise ValidationError("Division by zero in mathematical expression")
    except (SyntaxError, ValueError) as exc:
        raise ValidationError(f"Malformed arithmetic expression: {exc}")


async def system_diagnostics_handler(parameters: dict[str, Any]) -> dict[str, Any]:
    """Return safe host system diagnostics (OS, CPU, memory)."""
    return {
        "platform": platform.platform(),
        "processor": platform.processor(),
        "python_version": platform.python_version(),
        "architecture": platform.architecture()[0],
        "machine": platform.machine(),
    }


async def text_analyzer_handler(parameters: dict[str, Any]) -> dict[str, Any]:
    """Perform deterministic text analytics on input text."""
    text = parameters.get("text", "")
    if not isinstance(text, str):
        raise ValidationError("Parameter 'text' must be a string")

    words = text.split()
    return {
        "character_count": len(text),
        "word_count": len(words),
        "line_count": len(text.splitlines()) if text else 0,
        "uppercase": text.upper() if len(text) < 200 else text[:200].upper(),
    }


# Register Builtins
tool_registry.register(
    ToolDefinition(
        name="datetime_now",
        description="Get current system date, time, and day of week.",
        safety_tier=ToolSafetyTier.READ,
        parameters_schema={"type": "object", "properties": {}},
        handler=datetime_now_handler,
    )
)

tool_registry.register(
    ToolDefinition(
        name="calculator",
        description="Perform safe arithmetic and mathematical calculations.",
        safety_tier=ToolSafetyTier.READ,
        parameters_schema={
            "type": "object",
            "required": ["expression"],
            "properties": {
                "expression": {"type": "string", "description": "e.g. '(12 * 8) + sqrt(144)'"}
            },
        },
        handler=calculator_handler,
    )
)

tool_registry.register(
    ToolDefinition(
        name="system_diagnostics",
        description="Inspect host operating system and hardware telemetry.",
        safety_tier=ToolSafetyTier.READ,
        parameters_schema={"type": "object", "properties": {}},
        handler=system_diagnostics_handler,
    )
)

tool_registry.register(
    ToolDefinition(
        name="text_analyzer",
        description="Compute character count, word count, and text statistics.",
        safety_tier=ToolSafetyTier.READ,
        parameters_schema={
            "type": "object",
            "required": ["text"],
            "properties": {"text": {"type": "string", "description": "Text to analyze"}},
        },
        handler=text_analyzer_handler,
    )
)
