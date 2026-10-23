from typing import Any, cast

from agent_tools.contracts import BaseBankingTool


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, BaseBankingTool[Any, Any]] = {}

    def register(self, tool: BaseBankingTool[Any, Any]) -> None:
        if tool.name in self._tools:
            raise ValueError(f"duplicate tool name: {tool.name}")
        self._tools[tool.name] = tool

    def get(self, name: str) -> BaseBankingTool[Any, Any] | None:
        return self._tools.get(name)

    def list_allowed(self, allowed_actions: set[str] | None = None) -> list[dict[str, object]]:
        tools = list(self._tools.values())
        if allowed_actions is not None:
            tools = [tool for tool in tools if tool.action in allowed_actions]
        return [tool.metadata() for tool in tools]

    def export_input_schema(self, name: str) -> dict[str, object]:
        tool = self.get(name)
        if tool is None:
            raise KeyError(name)
        return cast(dict[str, object], tool.input_model.model_json_schema())
