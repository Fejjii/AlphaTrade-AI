"""Tool definition contract for the agent tool registry."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.schemas.common import ToolRiskLevel
from app.schemas.tools import ToolOutput


@dataclass(frozen=True)
class ToolDefinition:
    """Static metadata plus the callable implementation."""

    name: str
    description: str
    risk_level: ToolRiskLevel
    requires_approval: bool
    provider_dependencies: tuple[str, ...]
    has_fallback: bool
    enabled: bool
    execute: Callable[[dict[str, Any]], ToolOutput]
