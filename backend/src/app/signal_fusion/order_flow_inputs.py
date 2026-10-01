"""Shared required-print gating for every canonical strategy family."""

from collections.abc import Sequence
from datetime import datetime

from app.market_contracts.errors import WrongSourceError
from app.market_contracts.observation import observation_from_order_flow
from app.market_contracts.order_flow import OrderFlowObservation, require_order_flow
from app.signal_fusion.adapters import AssessmentCommand
from app.signal_fusion.enums import EvidenceRole

ORDER_FLOW_ROLES = frozenset({EvidenceRole.CVD_5M, EvidenceRole.ORDER_FLOW_5M})


def require_bound_order_flow(
    item: OrderFlowObservation | None,
    *,
    command: AssessmentCommand,
    required_roles: Sequence[EvidenceRole],
    evaluated_at: datetime,
    trigger_end: datetime | None,
) -> None:
    roles = tuple(role for role in required_roles if role in ORDER_FLOW_ROLES)
    if not roles:
        return
    require_order_flow(item, identity=command.evidence_identity, evaluated_at=evaluated_at)
    assert item is not None
    if trigger_end is None or item.window_end != trigger_end:
        raise WrongSourceError("Required 5m order flow is not bound to the trigger close.")
    for role in roles:
        selected = [
            observation
            for observation, selected_role in zip(
                command.public_observations, command.selected_roles, strict=True
            )
            if selected_role is role
        ]
        if selected != [observation_from_order_flow(item, cvd=role is EvidenceRole.CVD_5M)]:
            raise WrongSourceError("Required 5m payload is not bound to the command.")
