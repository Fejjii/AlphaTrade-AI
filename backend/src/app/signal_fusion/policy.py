"""Versioned FusionPolicy contract.

References one UserStrategyVersion / CompiledSetupDefinition pair. Declares
required, optional, and disqualifying evidence roles, thresholds, and
freshness/finality policy versions. Does not evaluate account risk.
"""

from __future__ import annotations

from uuid import UUID

from pydantic import Field, model_validator

from app.market_contracts.models import CanonicalDecimal, CanonicalModel
from app.schemas.common import Timeframe
from app.signal_fusion.enums import EvidenceRole, TenantAssertionRole
from app.signal_fusion.types import (
    SCHEMA_VERSION_1_0,
    ExecutableSetupRef,
    PolicyVersion,
    RoleTimeframeBinding,
    RuleWeight,
    Sha256Hex,
    hashed_model,
)

FUSION_POLICY_SCHEMA = "FusionPolicy/v1"
DEFAULT_FUSION_POLICY_VERSION = "first-slice-fusion/v1"
DEFAULT_CORRECTION_SELECTION_POLICY = "selected-final-revision/v1"


def first_slice_role_timeframes() -> tuple[RoleTimeframeBinding, ...]:
    """First-slice trigger (M15) vs context (H4) role-timeframe bindings."""
    return (
        RoleTimeframeBinding(role=EvidenceRole.TRIGGER_OHLCV, timeframe=Timeframe.M15),
        RoleTimeframeBinding(role=EvidenceRole.CONTEXT_OHLCV, timeframe=Timeframe.H4),
        RoleTimeframeBinding(role=EvidenceRole.CVD_WINDOW, timeframe=Timeframe.M15),
    )


class FusionThresholds(CanonicalModel):
    confirmation_score: CanonicalDecimal
    weights: tuple[RuleWeight, ...] = ()


class FusionPolicy(CanonicalModel):
    """Immutable fusion policy. Setup truth only; no account or risk fields."""

    schema_version: str = FUSION_POLICY_SCHEMA
    policy_version: PolicyVersion
    organization_id: UUID
    strategy_version_id: UUID
    executable_setup: ExecutableSetupRef
    required_roles: tuple[EvidenceRole, ...]
    optional_roles: tuple[EvidenceRole, ...] = ()
    disqualifying_roles: tuple[EvidenceRole, ...] = ()
    role_timeframes: tuple[RoleTimeframeBinding, ...] = Field(
        default_factory=first_slice_role_timeframes
    )
    required_assertion_roles: tuple[TenantAssertionRole, ...] = ()
    identity_assertion_roles: tuple[TenantAssertionRole, ...] = ()
    thresholds: FusionThresholds
    freshness_policy_version: PolicyVersion
    finality_policy_version: PolicyVersion
    correction_selection_policy: PolicyVersion = DEFAULT_CORRECTION_SELECTION_POLICY
    content_hash: Sha256Hex

    @model_validator(mode="after")
    def _roles_disjoint(self) -> FusionPolicy:
        required = set(self.required_roles)
        optional = set(self.optional_roles)
        disqualifying = set(self.disqualifying_roles)
        if required & optional:
            raise ValueError("Required and optional evidence roles must be disjoint.")
        if required & disqualifying:
            raise ValueError("Required and disqualifying evidence roles must be disjoint.")
        if not self.required_roles:
            raise ValueError("FusionPolicy must declare at least one required evidence role.")
        bound_roles = [binding.role for binding in self.role_timeframes]
        if len(bound_roles) != len(set(bound_roles)):
            raise ValueError("role_timeframes must bind each evidence role at most once.")
        if TenantAssertionRole.PRESENTATION in self.required_assertion_roles:
            raise ValueError("PRESENTATION assertions cannot be required for identity.")
        if TenantAssertionRole.PRESENTATION in self.identity_assertion_roles:
            raise ValueError("PRESENTATION assertions cannot be identity-forming.")
        if len(self.required_assertion_roles) != len(set(self.required_assertion_roles)):
            raise ValueError("required_assertion_roles must be unique.")
        if len(self.identity_assertion_roles) != len(set(self.identity_assertion_roles)):
            raise ValueError("identity_assertion_roles must be unique.")
        identity_set = set(self.identity_assertion_roles)
        if identity_set and not set(self.required_assertion_roles) <= identity_set:
            raise ValueError(
                "Required assertion roles must be a subset of identity assertion roles."
            )
        return self


def build_fusion_policy(
    *,
    policy_version: str,
    organization_id: UUID,
    strategy_version_id: UUID,
    executable_setup: ExecutableSetupRef,
    required_roles: tuple[EvidenceRole, ...],
    thresholds: FusionThresholds,
    freshness_policy_version: str,
    finality_policy_version: str,
    optional_roles: tuple[EvidenceRole, ...] = (),
    disqualifying_roles: tuple[EvidenceRole, ...] = (),
    correction_selection_policy: str = DEFAULT_CORRECTION_SELECTION_POLICY,
    role_timeframes: tuple[RoleTimeframeBinding, ...] | None = None,
    required_assertion_roles: tuple[TenantAssertionRole, ...] = (),
    identity_assertion_roles: tuple[TenantAssertionRole, ...] = (),
) -> FusionPolicy:
    draft = FusionPolicy(
        schema_version=FUSION_POLICY_SCHEMA,
        policy_version=policy_version,
        organization_id=organization_id,
        strategy_version_id=strategy_version_id,
        executable_setup=executable_setup,
        required_roles=required_roles,
        optional_roles=optional_roles,
        disqualifying_roles=disqualifying_roles,
        role_timeframes=(
            first_slice_role_timeframes() if role_timeframes is None else role_timeframes
        ),
        required_assertion_roles=required_assertion_roles,
        identity_assertion_roles=identity_assertion_roles,
        thresholds=thresholds,
        freshness_policy_version=freshness_policy_version,
        finality_policy_version=finality_policy_version,
        correction_selection_policy=correction_selection_policy,
        content_hash="0" * 64,
    )
    return hashed_model(draft)


__all__ = [
    "DEFAULT_CORRECTION_SELECTION_POLICY",
    "DEFAULT_FUSION_POLICY_VERSION",
    "FUSION_POLICY_SCHEMA",
    "SCHEMA_VERSION_1_0",
    "FusionPolicy",
    "FusionThresholds",
    "build_fusion_policy",
    "first_slice_role_timeframes",
]
