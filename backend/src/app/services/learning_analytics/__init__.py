"""Learning analytics service package (Slice 84 — read-only, record derived).

Aggregates existing manual paper validation sessions, observations, and outcomes
into read-only learning summaries. Contains no order, proposal, approval,
execution, exchange, engine, scanner, worker, or Telegram code paths.
"""

from __future__ import annotations

from app.services.learning_analytics.service import LearningAnalyticsService

__all__ = ["LearningAnalyticsService"]
