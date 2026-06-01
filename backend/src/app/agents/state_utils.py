"""Helpers to convert :class:`~app.schemas.agent.AgentState` for LangGraph."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from app.schemas.agent import AgentState


def state_to_dict(state: AgentState) -> dict[str, Any]:
    """Serialize state for LangGraph (JSON-compatible values)."""
    return state.model_dump(mode="json")


def parse_state(data: dict[str, Any]) -> AgentState:
    """Parse graph state dict back into a typed :class:`AgentState`."""
    return AgentState.model_validate(data)


def patch_state(current: dict[str, Any], update: dict[str, Any]) -> dict[str, Any]:
    """Shallow-merge an update and re-validate through :class:`AgentState`."""
    merged = {**current, **update}
    return state_to_dict(AgentState.model_validate(merged))


def dump_partial(model: BaseModel) -> dict[str, Any]:
    """Dump a nested Pydantic model for merging into graph state."""
    return model.model_dump(mode="json")
