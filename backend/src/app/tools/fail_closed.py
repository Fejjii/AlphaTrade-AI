"""Fail-closed results for mutation/execution tools that are not authoritative."""

from __future__ import annotations

from enum import StrEnum

from app.schemas.tools import ToolOutput


class ToolFailureCode(StrEnum):
    UNAVAILABLE = "UNAVAILABLE"
    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"
    BLOCKED = "BLOCKED"


def fail_closed(
    tool_name: str,
    code: ToolFailureCode,
    reason: str,
) -> ToolOutput:
    """Return an explicit unsuccessful result. Never reports success."""
    return ToolOutput(
        tool_name=tool_name,
        success=False,
        error=f"{code.value}: {reason}",
        result={"status": code.value, "code": code.value, "reason": reason},
    )
