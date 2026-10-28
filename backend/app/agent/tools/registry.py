"""Tool registry defining capabilities, parameters, and safety tiers."""

from collections.abc import Awaitable
from typing import Any

from pydantic import BaseModel, Field

from backend.app.agent.schema import ToolSafetyTier
from backend.app.core.exceptions import AppError, NotFoundError


class ToolDefinition(BaseModel):
    """Specification of a registered tool capability."""

    name: str = Field(description="Unique tool identifier")
    description: str = Field(description="Functional description for planning")
    safety_tier: ToolSafetyTier = Field(default=ToolSafetyTier.READ)
    parameters_schema: dict[str, Any] = Field(default_factory=dict)
    # Using Any for handler callable to keep Pydantic serialization clean
    handler: Any = Field(exclude=True)


class ToolRegistry:
    """Authoritative registry of executable capabilities."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, tool: ToolDefinition) -> None:
        """Register a new tool."""
        self._tools[tool.name] = tool

    def has_tool(self, name: str) -> bool:
        """Check if tool is registered."""
        return name in self._tools

    def get(self, name: str) -> ToolDefinition | None:
        """Retrieve tool definition by name."""
        return self._tools.get(name)

    def get_tool(self, name: str) -> ToolDefinition:
        """Retrieve tool definition by name or raise NotFoundError."""
        tool = self._tools.get(name)
        if not tool:
            raise NotFoundError(message=f"Tool '{name}' is not registered in the tool registry")
        return tool

    def list_tools(self) -> list[ToolDefinition]:
        """List all registered tools."""
        return list(self._tools.values())

    async def execute(self, name: str, parameters: dict[str, Any]) -> Any:
        """Invoke a tool directly through its registered handler."""
        tool = self.get(name)
        if not tool:
            raise NotFoundError(message=f"Tool '{name}' is not registered in the tool registry")

        handler = tool.handler
        if not callable(handler):
            raise AppError(message=f"Tool '{name}' handler is not callable")

        try:
            res = handler(parameters)
            if isinstance(res, Awaitable):
                return await res
            return res
        except Exception as exc:
            raise AppError(message=f"Tool '{name}' execution failed: {exc}") from exc


# Global tool registry
tool_registry = ToolRegistry()


def get_tool_registry() -> ToolRegistry:
    """Dependency provider for ToolRegistry."""
    return tool_registry
