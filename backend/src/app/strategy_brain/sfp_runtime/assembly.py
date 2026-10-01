"""SFP acquisition uses shared Brain assembly and canonical durable receipts."""

from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.evidence_pipeline.assembler import FirstSliceEvidenceAssembler
from app.evidence_pipeline.types import AssembledCanonicalEvidence
from app.market_contracts.enums import FreshnessState
from app.market_contracts.errors import MarketContractError, StaleEvidenceError
from app.market_contracts.identity import EvidenceMarketIdentity
from app.market_contracts.observation import PublicMarketObservation, observation_from_ohlcv
from app.market_contracts.ohlcv import OhlcvBar
from app.persistence.public_market_observations import remember_observation
from app.schemas.nested_continuation import EvidenceAvailability
from app.signal_fusion.strategy_evaluation_policy import ExecutableStrategyPolicy
from app.strategy_brain.sfp.contracts import SfpSpec
from app.strategy_brain.sfp_runtime.records import record_sfp_availability


def sfp_observations(
    session: Session | None,
    *,
    bars: tuple[OhlcvBar, ...],
    identity: EvidenceMarketIdentity,
    now: datetime,
) -> tuple[PublicMarketObservation, ...]:
    observations = tuple(
        observation_from_ohlcv(
            bar,
            identity=identity,
            observed_at=now,
            receive_time=now,
            freshness_state=FreshnessState.FRESH,
        )
        for bar in bars
    )
    return (
        tuple(
            remember_observation(session, o, bar=b) for b, o in zip(bars, observations, strict=True)
        )
        if session
        else observations
    )


def assemble_sfp(
    assembler: FirstSliceEvidenceAssembler,
    *,
    executable: ExecutableStrategyPolicy,
    organization_id: UUID,
    session: Session | None,
) -> AssembledCanonicalEvidence:
    from app.strategy_brain.assembly import assemble_ohlcv_family

    if not isinstance(executable.authored_spec, SfpSpec):
        raise ValueError("SFP assembly requires a registered SFP version")
    if executable.organization_id != organization_id:
        raise ValueError("SFP assembly tenant does not match immutable policy")
    try:
        return assemble_ohlcv_family(
            assembler,
            executable=executable,
            organization_id=organization_id,
            session=session,
        )
    except (MarketContractError, ValueError) as exc:
        if session is not None:
            availability = (
                EvidenceAvailability.STALE
                if isinstance(exc, StaleEvidenceError)
                else EvidenceAvailability.MISSING
            )
            record_sfp_availability(
                session,
                executable=executable,
                availability=availability,
                reason_codes=("required_sfp_evidence_unavailable",),
                evaluated_at=assembler._default_clock(),
                evidence_hash="unavailable",
            )
        raise
