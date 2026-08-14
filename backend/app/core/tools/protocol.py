from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from app.core.citations import Citations


@dataclass
class ToolResult:
    """Model content plus optional message parts to stream/persist."""

    content: str
    source_parts: list[dict[str, Any]] = field(default_factory=list)


class Tool(Protocol):
    name: str
    description: str
    parameters: dict[str, Any]

    async def run(self, args: dict[str, Any], citations: Citations) -> ToolResult: ...
