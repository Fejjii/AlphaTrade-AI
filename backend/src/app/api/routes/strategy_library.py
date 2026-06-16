"""Strategy library CRUD API (Slice 33)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Query

from app.core.dependencies import SessionDep, StrategyLibraryServiceDep
from app.schemas.strategy_library import (
    PaginatedUserStrategies,
    PaginatedUserStrategyVersions,
    StrategyLibraryCreate,
    UserStrategy,
    UserStrategyCreate,
    UserStrategyUpdate,
    UserStrategyVersion,
    UserStrategyVersionCreate,
)
from app.security.rbac import TraderDep

router = APIRouter(prefix="/strategies", tags=["strategies"])


@router.post("", response_model=UserStrategy, summary="Create user strategy")
async def create_strategy(
    body: StrategyLibraryCreate,
    tenant: TraderDep,
    service: StrategyLibraryServiceDep,
    session: SessionDep,
) -> UserStrategy:
    payload = UserStrategyCreate(
        organization_id=tenant.organization_id,
        user_id=tenant.user_id,
        name=body.name,
        setup_type=body.setup_type,
        card=body.card,
        notes=body.notes,
    )
    result = service.create(payload)
    session.commit()
    return result


@router.get("", response_model=PaginatedUserStrategies, summary="List user strategies")
async def list_strategies(
    tenant: TraderDep,
    service: StrategyLibraryServiceDep,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> PaginatedUserStrategies:
    items, total = service.list_strategies(
        organization_id=tenant.organization_id,
        user_id=tenant.user_id,
        limit=limit,
        offset=offset,
    )
    return PaginatedUserStrategies(items=items, total=total, limit=limit, offset=offset)


@router.get("/{strategy_id}", response_model=UserStrategy, summary="Get user strategy")
async def get_strategy(
    strategy_id: uuid.UUID,
    tenant: TraderDep,
    service: StrategyLibraryServiceDep,
) -> UserStrategy:
    return service.get(strategy_id, organization_id=tenant.organization_id, user_id=tenant.user_id)


@router.patch("/{strategy_id}", response_model=UserStrategy, summary="Update user strategy")
async def update_strategy(
    strategy_id: uuid.UUID,
    body: UserStrategyUpdate,
    tenant: TraderDep,
    service: StrategyLibraryServiceDep,
    session: SessionDep,
) -> UserStrategy:
    result = service.update(
        strategy_id,
        body,
        organization_id=tenant.organization_id,
        user_id=tenant.user_id,
    )
    session.commit()
    return result


@router.post(
    "/{strategy_id}/versions",
    response_model=UserStrategyVersion,
    summary="Create strategy version",
)
async def create_strategy_version(
    strategy_id: uuid.UUID,
    body: UserStrategyVersionCreate,
    tenant: TraderDep,
    service: StrategyLibraryServiceDep,
    session: SessionDep,
) -> UserStrategyVersion:
    result = service.create_version(
        strategy_id,
        body,
        organization_id=tenant.organization_id,
        user_id=tenant.user_id,
    )
    session.commit()
    return result


@router.get(
    "/{strategy_id}/versions",
    response_model=PaginatedUserStrategyVersions,
    summary="List strategy versions",
)
async def list_strategy_versions(
    strategy_id: uuid.UUID,
    tenant: TraderDep,
    service: StrategyLibraryServiceDep,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> PaginatedUserStrategyVersions:
    items, total = service.list_versions(
        strategy_id,
        organization_id=tenant.organization_id,
        user_id=tenant.user_id,
        limit=limit,
        offset=offset,
    )
    return PaginatedUserStrategyVersions(items=items, total=total, limit=limit, offset=offset)
