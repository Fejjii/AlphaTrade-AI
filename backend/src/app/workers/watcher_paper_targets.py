"""Tenant-scoped approved compiled strategies for paper Watcher scans.

BTCUSDT is always first. Additional configured symbols are appended uniquely.
Unknown catalog symbols fail closed later at assembly time.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID, uuid5

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.db.models import UserStrategy
from app.schemas.common import Timeframe
from app.services.canonical_strategy_evaluation import resolve_executable_strategy_policy
from app.services.strategy_versioning import StrategyVersioningService
from app.signal_fusion.errors import StrategyEvaluationPolicyError
from app.signal_fusion.strategy_evaluation_policy import ExecutableStrategyPolicy
from app.watcher.hashing import derive_scan_scope

FIRST_SLICE_SYMBOL = "BTCUSDT"
FIRST_SLICE_TIMEFRAME = Timeframe.M15.value
PAPER_POLICY_NAMESPACE = UUID("a0690000-1111-4000-8000-000000000069")


@dataclass(frozen=True, slots=True)
class PaperScanTarget:
    """One tenant + approved compiled version + symbol scan unit."""

    organization_id: UUID
    user_id: UUID
    strategy_id: UUID
    strategy_version_id: UUID
    compiled_setup_definition_id: UUID
    compiled_content_hash: str
    fusion_policy_version: str
    symbol: str
    timeframe: str = FIRST_SLICE_TIMEFRAME

    @property
    def policy_id(self) -> UUID:
        return paper_policy_id(
            organization_id=self.organization_id,
            strategy_version_id=self.strategy_version_id,
            compiled_content_hash=self.compiled_content_hash,
            symbol=self.symbol,
            timeframe=self.timeframe,
        )

    @property
    def watchlist_item_id(self) -> UUID:
        return uuid5(self.policy_id, "watchlist-item")

    @property
    def scan_scope(self) -> str:
        return derive_scan_scope(policy_id=self.policy_id, timeframe=self.timeframe)


def paper_policy_id(
    *,
    organization_id: UUID,
    strategy_version_id: UUID,
    compiled_content_hash: str,
    symbol: str,
    timeframe: str,
) -> UUID:
    """Deterministic Watcher policy identity for one compiled lineage + symbol."""

    return uuid5(
        PAPER_POLICY_NAMESPACE,
        f"{organization_id}:{strategy_version_id}:{compiled_content_hash}:"
        f"{symbol.strip().upper()}:{timeframe}",
    )


def normalize_paper_symbols(symbols: Sequence[str]) -> tuple[str, ...]:
    """BTCUSDT first, then unique additional configured symbols."""

    ordered: list[str] = []
    seen: set[str] = set()
    for raw in (FIRST_SLICE_SYMBOL, *symbols):
        token = raw.strip().upper()
        if not token or token in seen:
            continue
        seen.add(token)
        ordered.append(token)
    return tuple(ordered)


def list_paper_scan_targets(
    session: Session,
    *,
    symbols: Sequence[str],
    organization_id: UUID | None = None,
    limit: int,
) -> tuple[PaperScanTarget, ...]:
    """Load tenant-scoped APPROVED/ACTIVE compiled strategies per symbol.

    Uses ``resolve_executable_strategy_policy`` so drafts, missing compiles, and
    wrong tenants never become scan targets.
    """

    enabled_symbols = normalize_paper_symbols(symbols)
    stmt = select(UserStrategy).where(UserStrategy.enabled.is_(True))
    if organization_id is not None:
        stmt = stmt.where(UserStrategy.organization_id == organization_id)
    stmt = stmt.order_by(UserStrategy.organization_id, UserStrategy.created_at, UserStrategy.id)
    versioning = StrategyVersioningService(session)
    targets: list[PaperScanTarget] = []
    for strategy in session.scalars(stmt):
        version = versioning.selected_version(strategy)
        if version is None:
            continue
        try:
            executable = resolve_executable_strategy_policy(
                session,
                organization_id=strategy.organization_id,
                strategy_version_id=version.id,
            )
        except (StrategyEvaluationPolicyError, NotFoundError):
            continue
        for symbol in enabled_symbols:
            targets.append(_target_from_executable(strategy, executable, symbol=symbol))
            if len(targets) >= limit:
                return tuple(targets)
    return tuple(targets)


def _target_from_executable(
    strategy: UserStrategy,
    executable: ExecutableStrategyPolicy,
    *,
    symbol: str,
) -> PaperScanTarget:
    return PaperScanTarget(
        organization_id=executable.organization_id,
        user_id=strategy.user_id,
        strategy_id=executable.strategy_id,
        strategy_version_id=executable.strategy_version_id,
        compiled_setup_definition_id=executable.compiled_setup_definition_id,
        compiled_content_hash=executable.compiled_content_hash,
        fusion_policy_version=str(executable.fusion_policy.policy_version),
        symbol=symbol.strip().upper(),
        timeframe=FIRST_SLICE_TIMEFRAME,
    )
