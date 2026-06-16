"""User strategy library service (Slice 33)."""

from __future__ import annotations

import uuid
from contextlib import suppress

from sqlalchemy.orm import Session

from app.core.errors import NotFoundError, ValidationAppError
from app.db.models import UserStrategy as UserStrategyModel
from app.db.models import UserStrategyVersion as UserStrategyVersionModel
from app.repositories.strategy_library import UserStrategyRepository, UserStrategyVersionRepository
from app.schemas.common import DocumentSourceType, StrategyValidationStatus
from app.schemas.rag import IngestDocumentRequest
from app.schemas.strategy_library import (
    StrategyCard,
    UserStrategy,
    UserStrategyCreate,
    UserStrategyUpdate,
    UserStrategyVersion,
    UserStrategyVersionCreate,
)
from app.services.rag_service import RagService


def _card_to_text(card: StrategyCard) -> str:
    sections = [
        ("Strategy", card.strategy_name),
        ("Market", card.market_type.value),
        ("Assets", ", ".join(card.asset_universe)),
        ("Timeframes", ", ".join(t.value for t in card.timeframes)),
        ("Entry", "; ".join(card.entry_conditions)),
        ("Confirmation", "; ".join(card.confirmation_conditions)),
        ("Invalidation", "; ".join(card.invalidation)),
        ("Stop loss", "; ".join(card.stop_loss)),
        ("Take profit", "; ".join(card.take_profit_plan)),
        ("Runner", "; ".join(card.runner_plan)),
        ("Position sizing", "; ".join(card.position_sizing)),
        ("Add rules", "; ".join(card.add_rules)),
        ("No trade rules", "; ".join(card.no_trade_rules)),
        ("Success criteria", "; ".join(card.success_criteria)),
    ]
    return "\n".join(f"{label}: {value}" for label, value in sections if value)


class StrategyLibraryService:
    def __init__(self, session: Session, rag_service: RagService | None = None) -> None:
        self._session = session
        self._repo = UserStrategyRepository(session)
        self._versions = UserStrategyVersionRepository(session)
        self._rag = rag_service

    def create(self, payload: UserStrategyCreate) -> UserStrategy:
        card = payload.card.model_copy(
            update={"strategy_name": payload.card.strategy_name or payload.name}
        )
        entity = UserStrategyModel(
            organization_id=payload.organization_id,
            user_id=payload.user_id,
            name=payload.name,
            setup_type=payload.setup_type,
            current_version=1,
            enabled=True,
            notes=payload.notes,
        )
        self._repo.add(entity)
        version = UserStrategyVersionModel(
            strategy_id=entity.id,
            version=1,
            card=card.model_dump(mode="json"),
            validation_status=card.validation_status,
        )
        self._versions.add(version)
        self._sync_rag(entity, version, card)
        return self._to_schema(entity, version)

    def list_strategies(
        self,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[UserStrategy], int]:
        rows, total = self._repo.list_scoped(
            organization_id=organization_id,
            user_id=user_id,
            limit=limit,
            offset=offset,
        )
        return [self._to_schema(row) for row in rows], total

    def get(
        self, strategy_id: uuid.UUID, *, organization_id: uuid.UUID, user_id: uuid.UUID
    ) -> UserStrategy:
        row = self._require(strategy_id, organization_id=organization_id, user_id=user_id)
        version = self._versions.latest(row.id)
        return self._to_schema(row, version)

    def update(
        self,
        strategy_id: uuid.UUID,
        payload: UserStrategyUpdate,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> UserStrategy:
        row = self._require(strategy_id, organization_id=organization_id, user_id=user_id)
        if payload.name is not None:
            row.name = payload.name
        if payload.setup_type is not None:
            row.setup_type = payload.setup_type
        if payload.enabled is not None:
            row.enabled = payload.enabled
        if payload.notes is not None:
            row.notes = payload.notes
        version = self._versions.latest(row.id)
        if payload.card is not None:
            row.current_version += 1
            version = UserStrategyVersionModel(
                strategy_id=row.id,
                version=row.current_version,
                card=payload.card.model_dump(mode="json"),
                validation_status=payload.card.validation_status,
            )
            self._versions.add(version)
            self._sync_rag(row, version, payload.card)
        return self._to_schema(row, version)

    def create_version(
        self,
        strategy_id: uuid.UUID,
        payload: UserStrategyVersionCreate,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> UserStrategyVersion:
        row = self._require(strategy_id, organization_id=organization_id, user_id=user_id)
        row.current_version += 1
        status = payload.validation_status or payload.card.validation_status
        version = UserStrategyVersionModel(
            strategy_id=row.id,
            version=row.current_version,
            card=payload.card.model_dump(mode="json"),
            validation_status=status,
        )
        self._versions.add(version)
        self._sync_rag(row, version, payload.card)
        return self._version_to_schema(version)

    def list_versions(
        self,
        strategy_id: uuid.UUID,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[UserStrategyVersion], int]:
        self._require(strategy_id, organization_id=organization_id, user_id=user_id)
        rows, total = self._versions.list_for_strategy(strategy_id, limit=limit, offset=offset)
        return [self._version_to_schema(row) for row in rows], total

    def get_latest_card(self, strategy_id: uuid.UUID) -> StrategyCard | None:
        version = self._versions.latest(strategy_id)
        if version is None:
            return None
        return StrategyCard.model_validate(version.card)

    def _require(
        self,
        strategy_id: uuid.UUID,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> UserStrategyModel:
        row = self._repo.get_scoped(
            strategy_id,
            organization_id=organization_id,
            user_id=user_id,
        )
        if row is None:
            raise NotFoundError("Strategy not found.")
        return row

    def _to_schema(
        self,
        row: UserStrategyModel,
        version: UserStrategyVersionModel | None = None,
    ) -> UserStrategy:
        version = version or self._versions.latest(row.id)
        card = StrategyCard.model_validate(version.card) if version else None
        return UserStrategy(
            id=row.id,
            organization_id=row.organization_id,
            user_id=row.user_id,
            name=row.name,
            setup_type=row.setup_type,
            current_version=row.current_version,
            enabled=row.enabled,
            notes=row.notes,
            latest_card=card,
            validation_status=version.validation_status if version else None,
            backtest_status=version.backtest_status if version else None,
            paper_validation_status=version.paper_validation_status if version else None,
            paper_eligible=row.paper_eligible,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    @staticmethod
    def _version_to_schema(row: UserStrategyVersionModel) -> UserStrategyVersion:
        return UserStrategyVersion(
            id=row.id,
            strategy_id=row.strategy_id,
            version=row.version,
            card=StrategyCard.model_validate(row.card),
            validation_status=row.validation_status,
            backtest_status=row.backtest_status,
            paper_validation_status=row.paper_validation_status,
            created_at=row.created_at,
        )

    def _sync_rag(
        self,
        strategy: UserStrategyModel,
        version: UserStrategyVersionModel,
        card: StrategyCard,
    ) -> None:
        if self._rag is None:
            return
        if card.validation_status not in {
            StrategyValidationStatus.VALIDATED,
            StrategyValidationStatus.IN_REVIEW,
        }:
            return
        text = _card_to_text(card)
        with suppress(ValidationAppError):
            self._rag.ingest(
                IngestDocumentRequest(
                    organization_id=strategy.organization_id,
                    user_id=strategy.user_id,
                    source_type=DocumentSourceType.STRATEGY_TEMPLATE,
                    title=f"Strategy: {strategy.name} v{version.version}",
                    source_uri=f"strategy://{strategy.id}/v{version.version}",
                    text=text,
                    strategy_tag=strategy.setup_type.value,
                )
            )
