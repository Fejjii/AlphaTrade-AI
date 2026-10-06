"""Owner-scoped stored setup/assessment context. No new assessment or authority."""

import json
from collections.abc import Callable
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.learning_attribution import LearningAttributionRecordRow
from app.db.models import CompiledSetupDefinition, UserStrategy
from app.db.strategy_brain import BrainSetupEventRow, BrainSetupRow
from app.learning_attribution.contracts import AttributionFacts
from app.schemas.canonical_trade_plan import CanonicalTradePlanRevision
from app.signal_fusion.types import hashed_model


def read_setup_evidence(
    session: Session,
    envelope: CanonicalTradePlanRevision,
    *,
    add: Callable[[UUID, str, str], None],
    missing: list[str],
    assessment_content_hash: str | None = None,
) -> None:
    plan, lineage = envelope.plan, envelope.lineage
    try:
        # Savepoints preserve the enclosing read if an optional evidence store is unreadable.
        with session.connection().begin_nested():
            setup = session.scalar(
                select(CompiledSetupDefinition).where(
                    CompiledSetupDefinition.id == plan.setup_definition_id,
                    CompiledSetupDefinition.organization_id == plan.organization_id,
                    CompiledSetupDefinition.user_id == plan.user_id,
                    CompiledSetupDefinition.strategy_version_id == plan.strategy_version_id,
                )
            )
            if setup is None:
                missing.append("linked compiled setup record absent from authenticated owner scope")
            elif setup.content_hash != lineage.compiled_setup_content_hash:
                missing.append("linked compiled setup content conflicts with the approved plan")
            else:
                add(
                    setup.id,
                    "Compiled setup",
                    _bounded(
                        {
                            "compiler": setup.compiler_version,
                            "compile_status": setup.compile_status.value,
                            "compiled_ast": setup.compiled_ast,
                            "content_hash": setup.content_hash,
                            "meaning": "stored definition; no fresh setup or approval implied",
                        }
                    ),
                )
    except SQLAlchemyError:
        missing.append("compiled setup evidence temporarily unreadable; existence is unknown")

    try:
        with session.connection().begin_nested():
            decision_filters = (
                BrainSetupEventRow.organization_id == plan.organization_id,
                BrainSetupEventRow.kind.in_(("paper_decision", "paper_trade_opened")),
                BrainSetupEventRow.payload["candidate_id"].as_string() == str(lineage.candidate_id),
                BrainSetupEventRow.payload["assessment_id"].as_string()
                == str(lineage.assessment_id),
                BrainSetupEventRow.payload["trade_plan_revision_id"].as_string()
                == str(plan.revision_id),
            )
            rows = session.scalars(
                select(BrainSetupRow)
                .join(UserStrategy)
                .where(
                    BrainSetupRow.organization_id == plan.organization_id,
                    UserStrategy.organization_id == plan.organization_id,
                    UserStrategy.user_id == plan.user_id,
                    BrainSetupRow.strategy_version_id == plan.strategy_version_id,
                    # Resolve immutable decisions, not mutable projection identity/state.
                    select(BrainSetupEventRow.id)
                    .where(BrainSetupEventRow.setup_id == BrainSetupRow.id, *decision_filters)
                    .exists(),
                )
                .limit(2)
            ).all()
            if not rows:
                missing.append(
                    "linked detector setup observation absent from authenticated owner scope; "
                    "immutable setup decision for this plan absent; "
                    "current projection is not historical proof"
                )
            elif len(rows) > 1:
                missing.append("linked detector setup observations are ambiguous")
            else:
                row = rows[0]
                events = session.scalars(
                    select(BrainSetupEventRow)
                    .where(
                        BrainSetupEventRow.setup_id == row.id,
                        *decision_filters,
                    )
                    .order_by(BrainSetupEventRow.occurred_at.desc(), BrainSetupEventRow.id)
                    .limit(2)
                ).all()
                if not events:
                    missing.append(
                        "immutable setup decision for this plan absent; "
                        "current projection is not historical proof"
                    )
                else:
                    event = events[0]
                    keys = (
                        "state",
                        "stage",
                        "completed_continuations",
                        "family",
                        "kind",
                        "direction",
                        "timeframe",
                        "reason_codes",
                        "rule_results",
                        "bar_references",
                        "evidence_reference",
                        "evidence_at",
                        "sweep",
                        "anchor_index",
                        "impulse_index",
                        "pullback_index",
                        "confirmed_index",
                        "event_index",
                        "extension",
                        "quality_components",
                        "invalidation_state",
                        "evidence",
                        "data_quality",
                        "canonical_scan_reference",
                        "paper_stage",
                        "risk_state",
                    )
                    observation = {key: event.payload[key] for key in keys if key in event.payload}
                    references = observation.get("bar_references")
                    if isinstance(references, list) and references:
                        observation["bar_reference_count"] = len(references)
                        observation["bar_references"] = references[:12]
                        observation["bar_references_truncated"] = len(references) > 12
                        observation["candle_detail"] = (
                            "stored candle hashes only; OHLCV values not loaded by this read"
                        )
                        missing.append(
                            "historical candle OHLCV values unavailable in this read; "
                            "linked decision supplies references only"
                        )
                    else:
                        missing.append("historical candle references absent from linked decision")
                    add(
                        event.id,
                        "Setup observation",
                        _bounded(
                            {
                                "setup_record": str(row.id),
                                "occurred_at": event.occurred_at.isoformat(),
                                "observation": observation,
                                "meaning": "historical detector/decision, no execution authority",
                            }
                        ),
                    )
    except SQLAlchemyError:
        missing.append("detector setup evidence temporarily unreadable; existence is unknown")

    try:
        with session.connection().begin_nested():
            row = session.scalar(
                select(LearningAttributionRecordRow).where(
                    LearningAttributionRecordRow.organization_id == plan.organization_id,
                    LearningAttributionRecordRow.user_id == plan.user_id,
                    LearningAttributionRecordRow.account_id == plan.account_id,
                    LearningAttributionRecordRow.candidate_id == lineage.candidate_id,
                    LearningAttributionRecordRow.assessment_id == lineage.assessment_id,
                    LearningAttributionRecordRow.trade_plan_revision_id == plan.revision_id,
                    LearningAttributionRecordRow.strategy_version_id == plan.strategy_version_id,
                    LearningAttributionRecordRow.evidence_window_hash
                    == lineage.evidence_window_hash,
                )
            )
            if row is None:
                missing.append("stored assessment summary absent from authenticated plan lineage")
            else:
                facts = AttributionFacts.model_validate(row.facts_payload)
                if (
                    hashed_model(facts).content_hash != row.facts_hash
                    or facts.content_hash != row.facts_hash
                    or facts.organization_id != plan.organization_id
                    or facts.user_id != plan.user_id
                    or facts.account_id != plan.account_id
                    or facts.candidate_id != lineage.candidate_id
                    or facts.assessment_id != lineage.assessment_id
                    or facts.evidence_window_hash != lineage.evidence_window_hash
                    or facts.trade_plan_revision_id != plan.revision_id
                    or facts.strategy_pattern.strategy_version_id != plan.strategy_version_id
                    or facts.strategy_pattern.setup_definition_id != plan.setup_definition_id
                    or facts.setup_quality.assessment_id != lineage.assessment_id
                    or facts.setup_quality.evidence_window_hash != lineage.evidence_window_hash
                    or (
                        assessment_content_hash is not None
                        and facts.setup_quality.assessment_content_hash != assessment_content_hash
                    )
                ):
                    missing.append("stored assessment summary integrity mismatch")
                else:
                    add(
                        row.id,
                        "Assessment summary",
                        _bounded(
                            {
                                "setup_quality": facts.setup_quality.model_dump(mode="json"),
                                "meaning": "stored summary; no full rule snapshot or authority",
                            }
                        ),
                    )
    except SQLAlchemyError:
        missing.append("assessment summary temporarily unreadable; existence is unknown")
    except ValidationError:
        missing.append("stored assessment summary malformed; its conclusions are not used")


def _bounded(value: dict[str, object]) -> str:
    text = json.dumps(value, sort_keys=True, ensure_ascii=True, default=str)
    if len(text) <= 2600:
        return text
    return text[:2600] + " [bounded source excerpt; remaining stored detail omitted]"
