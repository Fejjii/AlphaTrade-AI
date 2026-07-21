"""Tool registry API (for agent workspace and debugging)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import Field

from app.core.dependencies import ToolRegistryDep
from app.schemas.common import StrictModel
from app.schemas.tools import ToolOutput, ToolSpec
from app.security.rbac import ReaderDep, TraderDep

router = APIRouter(prefix="/tools", tags=["tools"])


class ToolExecuteRequest(StrictModel):
    tool_name: str = Field(min_length=1, max_length=80)
    arguments: dict[str, Any] = Field(default_factory=dict)


@router.get("", response_model=list[ToolSpec], summary="List registered tools")
async def list_tools(registry: ToolRegistryDep, _tenant: ReaderDep) -> list[ToolSpec]:
    return registry.list_specs()


@router.post("/execute", response_model=ToolOutput, summary="Execute a tool (debug/agent)")
async def execute_tool(
    body: ToolExecuteRequest,
    registry: ToolRegistryDep,
    tenant: TraderDep,
) -> ToolOutput:
    # Bind tenant from JWT; never trust client-supplied organization_id/user_id.
    arguments = {
        **body.arguments,
        "organization_id": str(tenant.organization_id),
        "user_id": str(tenant.user_id),
    }
    return registry.execute(body.tool_name, arguments)
