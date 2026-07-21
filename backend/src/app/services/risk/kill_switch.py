"""Process-local kill switch until AT-014 persists server-side state.

Keyed by (organization_id, user_id). Default is inactive. Execution and risk
evaluation read this store; AT-014 will replace it with durable storage + API.
"""

from __future__ import annotations

import uuid

_active: set[tuple[str, str]] = set()


def _key(organization_id: uuid.UUID, user_id: uuid.UUID) -> tuple[str, str]:
    return (str(organization_id), str(user_id))


def is_kill_switch_active(*, organization_id: uuid.UUID, user_id: uuid.UUID) -> bool:
    return _key(organization_id, user_id) in _active


def set_kill_switch_active(
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    active: bool,
) -> None:
    key = _key(organization_id, user_id)
    if active:
        _active.add(key)
    else:
        _active.discard(key)


def clear_all_kill_switches() -> None:
    """Test helper — reset process-local state."""
    _active.clear()
