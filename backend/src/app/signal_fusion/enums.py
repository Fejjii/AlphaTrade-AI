"""Phase 6 fusion, assessment, candidate, and evidence-role enumerations.

Reuses Phase 5 venue/market/finality/freshness/source identities and Phase 3
TradeDirection / Timeframe. Does not create a parallel identity system.
"""

from __future__ import annotations

from enum import StrEnum


class SetupIdentityKind(StrEnum):
    """Executable vs compatibility-only setup identity."""

    COMPILED_SETUP_DEFINITION = "compiled_setup_definition"
    GLOBAL_SETUP_TEMPLATE = "global_setup_template"


class SetupAssessmentState(StrEnum):
    """Canonical setup-truth lifecycle. Independent of account/risk state."""

    NO_SETUP = "no_setup"
    WATCH = "watch"
    PARTIAL_MATCH = "partial_match"
    CONFIRMED_SETUP = "confirmed_setup"
    INVALIDATED = "invalidated"
    EXPIRED = "expired"


class CandidateState(StrEnum):
    """Canonical candidate lifecycle after CONFIRMED_SETUP."""

    ACTIVE = "active"
    PLAN_CREATED = "plan_created"
    REJECTED = "rejected"
    SKIPPED = "skipped"
    EXPIRED = "expired"
    INVALIDATED = "invalidated"


class ActionEligibilityState(StrEnum):
    """Account/action permission. Never mutates setup truth."""

    ELIGIBLE = "eligible"
    BLOCKED = "blocked"
    EXPIRED = "expired"


class EvidenceRole(StrEnum):
    """Semantic roles inside a CanonicalEvidenceWindowV1."""

    TRIGGER_OHLCV = "trigger_ohlcv"
    CONTEXT_OHLCV = "context_ohlcv"
    TRIGGER = "trigger"
    SWING = "swing"
    CVD_WINDOW = "cvd_window"
    SIGNED_FLOW = "signed_flow"
    VOLUME = "volume"
    STRUCTURE = "structure"
    TRADE_EVENT = "trade_event"
    ORDER_BOOK = "order_book"
    PUBLIC_EXTERNAL_SIGNAL = "public_external_signal"


class EvidenceAdapterKind(StrEnum):
    """Transport adapters that must converge on one assessment command.

    Adapter identity is excluded from CanonicalEvidenceWindowV1.
    """

    WATCHER = "watcher"
    DETECTOR = "detector"
    TRADINGVIEW = "tradingview"


class AssertionSource(StrEnum):
    """Tenant-owned assertion sources. Never public market observations."""

    TRADINGVIEW = "tradingview"
    MANUAL_LEVEL = "manual_level"
    USER_ASSERTION = "user_assertion"
    PROPRIETARY_ALERT = "proprietary_alert"


class TenantAssertionRole(StrEnum):
    """Role-bound tenant assertion selection for CanonicalEvidenceWindowV1.

    ``PRESENTATION`` is never identity-forming. Only roles required or
    explicitly selected by FusionPolicy may enter the evidence-window hash.
    """

    TRADINGVIEW_ALERT = "tradingview_alert"
    MANUAL_LEVEL = "manual_level"
    USER_ASSERTION = "user_assertion"
    PROPRIETARY_ALERT = "proprietary_alert"
    PRESENTATION = "presentation"


class AssertionPrivacyClass(StrEnum):
    TENANT_CONFIDENTIAL = "tenant_confidential"


class AssessmentReasonCode(StrEnum):
    PRECONDITIONS_PASSED = "preconditions_passed"
    SEQUENCE_STEP_PASSED = "sequence_step_passed"
    ALL_MANDATORY_EVIDENCE_CONFIRMED = "all_mandatory_evidence_confirmed"
    PATTERN_INVALIDATED = "pattern_invalidated"
    MARKET_DISQUALIFIER = "market_disqualifier"
    REQUIRED_SOURCE_STALE = "required_source_stale"
    REQUIRED_SOURCE_GAPPED = "required_source_gapped"
    REQUIRED_SOURCE_FALLBACK = "required_source_fallback"
    WRONG_VENUE_OR_MARKET = "wrong_venue_or_market"
    DIRECTIONAL_MARKET_CONFLICT = "directional_market_conflict"
    POLICY_REPLACED = "policy_replaced"
    VALIDITY_INTERVAL_ELAPSED = "validity_interval_elapsed"
    DISTINCT_EVIDENCE_WINDOW = "distinct_evidence_window"


class CandidateReasonCode(StrEnum):
    CONFIRMED_SETUP = "confirmed_setup"
    PLAN_CREATED = "plan_created"
    REJECTED = "rejected"
    SKIPPED = "skipped"
    EXPIRED = "expired"
    INVALIDATED = "invalidated"


class EligibilityReasonCode(StrEnum):
    ELIGIBLE = "eligible"
    BLOCKED_KILL_SWITCH = "blocked_kill_switch"
    BLOCKED_DAILY_LOSS = "blocked_daily_loss"
    BLOCKED_COOLDOWN = "blocked_cooldown"
    BLOCKED_EXPOSURE = "blocked_exposure"
    BLOCKED_PORTFOLIO_CONFLICT = "blocked_portfolio_conflict"
    BLOCKED_ACCOUNT_STATE = "blocked_account_state"
    BLOCKED_VENUE_STATE = "blocked_venue_state"
    BLOCKED_DATA_QUALITY = "blocked_data_quality"
    BLOCKED_BASIS = "blocked_basis"
    BLOCKED_CANDIDATE_TTL = "blocked_candidate_ttl"
    EXPIRED = "expired"
