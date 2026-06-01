"""Generic tool input/output envelopes and tool specification schema.

Tools are the only capabilities exposed to the agent. Each declares typed I/O,
a risk level, and whether it requires approval (master prompt §13).
"""

from __future__ import annotations

from typing import Any

from pydantic import Field

from app.schemas.common import ORMModel, StrictModel, ToolRiskLevel


class ToolInput(StrictModel):
    """Envelope for arguments passed to a tool.

    Concrete tools validate ``arguments`` against their own typed schema; this
    envelope carries correlation context without leaking it into tool logic.
    """

    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class ToolOutput(ORMModel):
    """Envelope for tool results, including success/error status."""

    tool_name: str
    success: bool
    result: dict[str, Any] | None = None
    error: str | None = None
    used_fallback: bool = False
    latency_ms: float | None = Field(default=None, ge=0)


class ToolSpec(ORMModel):
    """Static description of a registered tool."""

    name: str
    description: str
    risk_level: ToolRiskLevel
    requires_approval: bool
    provider_dependencies: list[str] = Field(default_factory=list)
    has_fallback: bool = False
    enabled: bool = True
