"""Persistence for BloFin demo exchange orders and fills (Slice 61)."""

from __future__ import annotations

from app.db.models import ExchangeFill, ExchangeOrder
from app.repositories.base import SQLAlchemyRepository


class ExchangeOrderRepository(SQLAlchemyRepository[ExchangeOrder]):
    model = ExchangeOrder


class ExchangeFillRepository(SQLAlchemyRepository[ExchangeFill]):
    model = ExchangeFill
