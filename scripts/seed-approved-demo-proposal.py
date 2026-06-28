#!/usr/bin/env python3
"""Seed one approved BTCUSDT demo proposal via existing service layer (Slice 66b).

Uses ProposalService + ApprovalService exactly like test_workflows::_seed_approved_proposal.
Must run with staging DATABASE_URL (Render Shell, Render one-off job, or local export).

Usage:
  cd backend && uv run python ../scripts/seed-approved-demo-proposal.py \\
    --organization-id <uuid> --user-id <uuid> --price 44455.1

Prints JSON: {"proposal_id": "...", "approval_id": "..."}
Never prints secrets.
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from decimal import Decimal
from pathlib import Path


def _bootstrap_import_path() -> None:
    candidates = [
        Path("/app/src"),
        Path(__file__).resolve().parent.parent / "backend" / "src",
    ]
    for candidate in candidates:
        if candidate.is_dir():
            sys.path.insert(0, str(candidate))
            return
    raise SystemExit("Could not locate app package (expected /app/src or backend/src).")


_bootstrap_import_path()

from app.core.config import get_settings  # noqa: E402
from app.db.session import get_session_factory  # noqa: E402
from app.schemas.approval import ApprovalDecisionRequest  # noqa: E402
from app.schemas.common import (  # noqa: E402
    ApprovalAction,
    RiskAction,
    RiskSeverity,
    StrategyId,
)
from app.schemas.proposal import ExitCriteria, TakeProfitLevel, TradeProposalCreate  # noqa: E402
from app.schemas.risk import RiskCheckResult  # noqa: E402
from app.services.approval_service import ApprovalService  # noqa: E402
from app.services.audit_service import AuditService  # noqa: E402
from app.services.proposal_service import ProposalService  # noqa: E402


def _assert_safe_settings() -> None:
    settings = get_settings()
    if settings.real_trading_enabled:
        raise SystemExit("Refused: real_trading_enabled is true.")
    if settings.environment == "production":
        raise SystemExit("Refused: production environment.")
    # Demo posture (paper_exchange_demo) is verified by the orchestrator HTTP preflight
    # before this script runs. This script only persists proposal + approval rows.


def seed_approved_proposal(
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    price: Decimal,
    size: Decimal,
    symbol: str,
) -> tuple[uuid.UUID, uuid.UUID]:
    """Create proposal with risk_result=ALLOW, approval, and approve it."""
    _assert_safe_settings()
    factory = get_session_factory()
    with factory() as session:
        audit = AuditService(session)
        proposals = ProposalService(session, audit)
        approvals = ApprovalService(session, audit)

        stop_loss = (price * Decimal("0.95")).quantize(Decimal("0.1"))
        take_profit = (price * Decimal("1.05")).quantize(Decimal("0.1"))

        proposal = proposals.create(
            TradeProposalCreate(
                organization_id=organization_id,
                user_id=user_id,
                strategy_id=StrategyId.HTF_TREND_PULLBACK,
                symbol=symbol,
                timeframe="4h",
                direction="long",
                entry_price=price,
                position_size=size,
                leverage=Decimal("1"),
                exit=ExitCriteria(
                    invalidation="Slice 66b controlled demo limit test — thesis invalid below stop.",
                    stop_loss=stop_loss,
                    take_profits=[TakeProfitLevel(price=take_profit, size_fraction=1.0)],
                ),
                confidence=0.7,
                risk_level=RiskSeverity.LOW,
                rationale="Slice 66b controlled far-from-market BloFin demo limit order seed.",
                approval_required=True,
                risk_result=RiskCheckResult(
                    action=RiskAction.ALLOW,
                    severity=RiskSeverity.LOW,
                    explanation="Slice 66b controlled demo limit order — risk ALLOW.",
                    approval_required=True,
                ),
            )
        )
        if proposal.id is None:
            raise SystemExit("Proposal creation did not return an id.")

        approval = approvals.create_for_proposal(
            proposal_id=proposal.id,
            organization_id=organization_id,
            user_id=user_id,
            risk_level=proposal.risk_level,
            confidence=float(proposal.confidence),
            approval_reason="Slice 66b controlled demo limit order seed.",
        )
        if approval.id is None:
            raise SystemExit("Approval creation did not return an id.")

        approvals.decide(
            approval.id,
            ApprovalDecisionRequest(
                action=ApprovalAction.APPROVE,
                reason="Slice 66b controlled demo limit order — human approved for test.",
            ),
        )
        session.commit()
        return proposal.id, approval.id


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed one approved demo proposal (service layer).")
    parser.add_argument("--organization-id", required=True, type=uuid.UUID)
    parser.add_argument("--user-id", required=True, type=uuid.UUID)
    parser.add_argument("--price", required=True, type=Decimal, help="Limit entry price (tick-aligned).")
    parser.add_argument("--size", default=Decimal("0.1"), type=Decimal, help="Contract size (min 0.1).")
    parser.add_argument("--symbol", default="BTCUSDT", help="Platform symbol.")
    args = parser.parse_args()

    proposal_id, approval_id = seed_approved_proposal(
        organization_id=args.organization_id,
        user_id=args.user_id,
        price=args.price,
        size=args.size,
        symbol=args.symbol.upper(),
    )
    print(json.dumps({"proposal_id": str(proposal_id), "approval_id": str(approval_id)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
