"""Tenant-scoped experiment API. Domain state changes never start runtime execution."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.core.dependencies import SessionDep, SettingsDep
from app.experiments.service import ExperimentService
from app.schemas.experiments import (
    ExperimentApproval,
    ExperimentCreate,
    ExperimentDetail,
    ExperimentPage,
    ExperimentPromotion,
    ExperimentSample,
    ExperimentSampleCreate,
    ExperimentTransition,
    ExperimentVersion,
    ExperimentVersionCreate,
)
from app.security.rbac import OwnerDep, ReaderDep, TraderDep

router = APIRouter(prefix="/experiments", tags=["experiments"])


def get_experiment_service(session: SessionDep, settings: SettingsDep) -> ExperimentService:
    # Deliberately no source resolver/worker/exchange client installed by HTTP.
    return ExperimentService(session, settings)


ServiceDep = Annotated[ExperimentService, Depends(get_experiment_service)]


@router.post("", response_model=ExperimentVersion, status_code=201)
def create(
    body: ExperimentCreate, tenant: TraderDep, service: ServiceDep, session: SessionDep
) -> ExperimentVersion:
    result = service.create(tenant, body)
    session.commit()
    return result


@router.get("", response_model=ExperimentPage)
def listing(
    tenant: ReaderDep,
    service: ServiceDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ExperimentPage:
    return service.list(tenant, limit=limit, offset=offset)


@router.get("/{experiment_id}", response_model=ExperimentDetail)
def detail(experiment_id: UUID, tenant: ReaderDep, service: ServiceDep) -> ExperimentDetail:
    return service.detail(tenant, experiment_id)


@router.post("/{experiment_id}/versions", response_model=ExperimentVersion, status_code=201)
def fork(
    experiment_id: UUID,
    body: ExperimentVersionCreate,
    tenant: TraderDep,
    service: ServiceDep,
    session: SessionDep,
) -> ExperimentVersion:
    result = service.fork(tenant, experiment_id, body)
    session.commit()
    return result


@router.post("/{experiment_id}/versions/{version_id}/transition", response_model=ExperimentVersion)
def transition(
    experiment_id: UUID,
    version_id: UUID,
    body: ExperimentTransition,
    tenant: TraderDep,
    service: ServiceDep,
    session: SessionDep,
) -> ExperimentVersion:
    result = service.transition(tenant, experiment_id, version_id, body)
    session.commit()
    return result


@router.post("/{experiment_id}/versions/{version_id}/approve", response_model=ExperimentVersion)
def approve(
    experiment_id: UUID,
    version_id: UUID,
    body: ExperimentApproval,
    tenant: OwnerDep,
    service: ServiceDep,
    session: SessionDep,
) -> ExperimentVersion:
    result = service.approve(tenant, experiment_id, version_id, body)
    session.commit()
    return result


@router.post(
    "/{experiment_id}/versions/{version_id}/promote",
    response_model=ExperimentVersion,
    status_code=201,
)
def promote(
    experiment_id: UUID,
    version_id: UUID,
    body: ExperimentPromotion,
    tenant: TraderDep,
    service: ServiceDep,
    session: SessionDep,
) -> ExperimentVersion:
    result = service.promote(tenant, experiment_id, version_id, body)
    session.commit()
    return result


@router.post(
    "/{experiment_id}/versions/{version_id}/samples",
    response_model=ExperimentSample,
    status_code=201,
)
def sample(
    experiment_id: UUID,
    version_id: UUID,
    body: ExperimentSampleCreate,
    tenant: TraderDep,
    service: ServiceDep,
    session: SessionDep,
) -> ExperimentSample:
    result = service.record_sample(tenant, experiment_id, version_id, body)
    session.commit()
    return result
