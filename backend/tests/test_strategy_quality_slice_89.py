"""Tests for strategy quality and detector performance (Slice 89 — read-only).

Covers pure scoring (confidence normalization, shrinkage, trust tiers, verdicts,
calibration labels, warnings), the service/endpoints over seeded validation
sessions, RBAC, tenant isolation, the optional user filter, and empty/
small-sample safety. No order/execution/proposal/approval/rule-mutation/
automation paths are exercised.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import Settings, get_settings
from app.core.errors import ForbiddenError
from app.db.base import Base
from app.db.models import (
    PaperValidationAlert,
    PaperValidationCandidate,
    PaperValidationDraft,
    PaperValidationRunPlan,
    PaperValidationRunSession,
    PaperValidationSessionResult,
)
from app.db.session import get_session
from app.main import create_app
from app.schemas.common import MembershipRole, PaperAlertType
from app.security.rate_limit import reset_rate_limiter
from app.security.rbac import require_membership_roles
from app.services.strategy_quality.scoring import (
    CALIB_INSUFFICIENT,
    CALIB_OVERCONFIDENT,
    CALIB_UNDERCONFIDENT,
    CALIB_WELL,
    TRUST_HIGH,
    TRUST_LOW,
    TRUST_MEDIUM,
    TRUST_NONE,
    VERDICT_AVOID_FOR_NOW,
    VERDICT_IMPROVE,
    VERDICT_NEEDS_MORE_VALIDATION,
    VERDICT_TRUSTED,
    calibration_label,
    decide_verdict,
    mean_confidence,
    normalize_confidence,
    score_detector,
    shrink_toward_prior,
)

_BASE = {
    "environment": "local",
    "log_json": False,
    "execution_mode": "paper",
    "enable_real_trading": False,
    "database_url": "sqlite+pysqlite:///:memory:",
    "jwt_secret": "strategy-quality-test-secret-min-32-chars",
    "rate_limit_use_redis": False,
    "access_token_denylist_use_redis": False,
    "provider_mode": "mock",
    "market_data_provider": "mock",
    "worker_enabled": False,
    "market_watcher_enabled": False,
    "market_watcher_bridge_enabled": False,
}


# --------------------------------------------------------------------------- #
# Pure scoring unit tests                                                      #
# --------------------------------------------------------------------------- #


def test_normalize_confidence_handles_both_scales() -> None:
    assert normalize_confidence(None) is None
    assert normalize_confidence(0.8) == 0.8
    assert normalize_confidence(80.0) == 0.8  # 0-100 scale normalized to 0-1
    assert normalize_confidence(150.0) == 1.0  # clamped
    assert normalize_confidence(-5.0) == 0.0  # clamped


def test_mean_confidence_ignores_nulls_and_normalizes() -> None:
    assert mean_confidence([]) is None
    assert mean_confidence([None, None]) is None
    assert mean_confidence([80.0, 0.6]) == round((0.8 + 0.6) / 2, 4)


def test_shrink_toward_prior_pulls_thin_samples() -> None:
    assert shrink_toward_prior(None, 0, 5) is None
    assert shrink_toward_prior(100.0, 0, 5) is None
    # n == min_sample -> r = 0.5, midway between raw and prior.
    assert shrink_toward_prior(100.0, 5, 5) == 75.0
    # Large sample barely shrinks: r = 95/100 = 0.95 -> 0.95*100 + 0.05*50.
    assert shrink_toward_prior(100.0, 95, 5) == 97.5


def test_calibration_label_bands() -> None:
    assert calibration_label(None, 0.5, 10, 5) == CALIB_INSUFFICIENT
    assert calibration_label(0.9, 0.5, 3, 5) == CALIB_INSUFFICIENT  # below min_sample
    assert calibration_label(0.9, 0.5, 10, 5) == CALIB_OVERCONFIDENT
    assert calibration_label(0.4, 0.8, 10, 5) == CALIB_UNDERCONFIDENT
    assert calibration_label(0.6, 0.6, 10, 5) == CALIB_WELL


def test_decide_verdict_thin_evidence_never_condemns_or_trusts() -> None:
    assert (
        decide_verdict(
            trust_tier=TRUST_LOW, shrunk_quality=95.0, invalidation_rate=0.0, avoided_rate=0.0
        )
        == VERDICT_NEEDS_MORE_VALIDATION
    )
    assert (
        decide_verdict(
            trust_tier=TRUST_NONE, shrunk_quality=None, invalidation_rate=0.9, avoided_rate=0.9
        )
        == VERDICT_NEEDS_MORE_VALIDATION
    )


def test_decide_verdict_medium_high_bands() -> None:
    assert (
        decide_verdict(
            trust_tier=TRUST_HIGH, shrunk_quality=85.0, invalidation_rate=0.1, avoided_rate=0.0
        )
        == VERDICT_TRUSTED
    )
    assert (
        decide_verdict(
            trust_tier=TRUST_MEDIUM, shrunk_quality=85.0, invalidation_rate=0.6, avoided_rate=0.0
        )
        == VERDICT_AVOID_FOR_NOW
    )
    assert (
        decide_verdict(
            trust_tier=TRUST_MEDIUM, shrunk_quality=85.0, invalidation_rate=0.0, avoided_rate=0.4
        )
        == VERDICT_AVOID_FOR_NOW
    )
    assert (
        decide_verdict(
            trust_tier=TRUST_HIGH, shrunk_quality=45.0, invalidation_rate=0.0, avoided_rate=0.0
        )
        == VERDICT_IMPROVE
    )


def test_score_detector_trusted_all_success() -> None:
    score = score_detector(
        condition="liquidity_sweep",
        sample_size=5,
        success_rate=1.0,
        behaved_rate=1.0,
        invalidation_hit_rate=0.0,
        avoided_rate=0.0,
        missed_entry_rate=0.0,
        mean_conf=0.8,
        calibration=CALIB_WELL,
        min_sample=5,
    )
    assert score.trust_tier == TRUST_MEDIUM
    assert score.raw_quality == 100.0
    assert score.shrunk_quality == 75.0
    assert score.verdict == VERDICT_TRUSTED
    assert {f.code for f in score.factors} >= {"success_rate", "expected_behavior"}


def test_score_detector_noisy_detector_flagged() -> None:
    score = score_detector(
        condition="sfp",
        sample_size=6,
        success_rate=0.1,
        behaved_rate=0.2,
        invalidation_hit_rate=0.8,
        avoided_rate=0.4,
        missed_entry_rate=0.0,
        mean_conf=0.5,
        calibration=CALIB_WELL,
        min_sample=5,
    )
    assert score.verdict == VERDICT_AVOID_FOR_NOW
    codes = {w.code for w in score.warnings}
    assert "noisy_high_invalidation" in codes
    assert "frequently_should_have_avoided" in codes


def test_score_detector_zero_sample_is_insufficient() -> None:
    score = score_detector(
        condition="order_block",
        sample_size=0,
        success_rate=None,
        behaved_rate=None,
        invalidation_hit_rate=None,
        avoided_rate=None,
        missed_entry_rate=None,
        mean_conf=None,
        calibration=CALIB_INSUFFICIENT,
        min_sample=5,
    )
    assert score.trust_tier == TRUST_NONE
    assert score.shrunk_quality is None
    assert score.verdict == VERDICT_NEEDS_MORE_VALIDATION
    assert {w.code for w in score.warnings} == {"insufficient_data"}


# --------------------------------------------------------------------------- #
# Service / endpoint harness                                                   #
# --------------------------------------------------------------------------- #


@dataclass
class Harness:
    client: TestClient
    factory: sessionmaker[Session]


@pytest.fixture(autouse=True)
def _reset_limiter() -> None:
    reset_rate_limiter()


@pytest.fixture
def harness() -> Iterator[Harness]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _fk(dbapi_conn: object, _record: object) -> None:
        cursor = dbapi_conn.cursor()  # type: ignore[attr-defined]
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    def _override_session() -> Iterator[Session]:
        with factory() as session:
            yield session

    get_settings.cache_clear()
    app = create_app(settings=Settings(**_BASE))
    app.dependency_overrides[get_session] = _override_session

    with TestClient(app) as client:
        yield Harness(client=client, factory=factory)

    app.dependency_overrides.clear()
    get_settings.cache_clear()
    engine.dispose()


def _register_owner(
    client: TestClient,
    email: str = "owner@example.com",
    organization_name: str = "Quality Org",
) -> tuple[dict[str, str], uuid.UUID, uuid.UUID]:
    reg = client.post(
        "/auth/register",
        json={
            "email": email,
            "password": "SecurePass123!",
            "organization_name": organization_name,
        },
    )
    assert reg.status_code == 201, reg.text
    login = client.post(
        "/auth/login",
        json={"email": email, "password": "SecurePass123!"},
    )
    assert login.status_code == 200, login.text
    token = login.json()["tokens"]["access_token"]
    org_id = uuid.UUID(reg.json()["organization"]["id"])
    user_id = uuid.UUID(reg.json()["user"]["id"])
    return {"Authorization": f"Bearer {token}"}, org_id, user_id


def _seed_session(
    factory: sessionmaker[Session],
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID | None = None,
    outcome: str = "success",
    condition: str = "liquidity_sweep",
    timeframe: str = "1h",
    symbol: str = "BTCUSDT",
    direction: str = "long",
    confidence: float | None = 0.8,
    entry_assessment: str = "entered_as_planned",
    discipline_assessment: str = "disciplined",
    invalidation_hit: bool = False,
    behaved_as_expected: bool | None = True,
    recorded_at: datetime | None = None,
) -> uuid.UUID:
    """Insert a full alert -> ... -> result chain and return the session id."""
    recorded = recorded_at or datetime(2026, 1, 10, 12, 0, tzinfo=UTC)
    started = recorded - timedelta(minutes=30)
    with factory() as session:
        alert = PaperValidationAlert(
            organization_id=organization_id,
            user_id=user_id,
            alert_type=PaperAlertType.SETUP_SIGNAL_DETECTED,
            message="seeded setup",
        )
        session.add(alert)
        session.flush()

        draft = PaperValidationDraft(
            organization_id=organization_id,
            source_alert_id=alert.id,
            review_status="important",
            created_by=user_id,
        )
        session.add(draft)
        session.flush()

        candidate = PaperValidationCandidate(
            organization_id=organization_id,
            draft_id=draft.id,
            source_alert_id=alert.id,
            created_by=user_id,
        )
        session.add(candidate)
        session.flush()

        plan = PaperValidationRunPlan(
            organization_id=organization_id,
            candidate_id=candidate.id,
            draft_id=draft.id,
            source_alert_id=alert.id,
            symbol=symbol,
            timeframe=timeframe,
            condition=condition,
            direction=direction,
            confidence=confidence,
            created_by=user_id,
        )
        session.add(plan)
        session.flush()

        run_session = PaperValidationRunSession(
            organization_id=organization_id,
            run_plan_id=plan.id,
            candidate_id=candidate.id,
            draft_id=draft.id,
            source_alert_id=alert.id,
            symbol=symbol,
            timeframe=timeframe,
            condition=condition,
            direction=direction,
            session_status="completed",
            started_by=user_id,
            started_at=started,
            ended_at=recorded,
        )
        session.add(run_session)
        session.flush()

        result = PaperValidationSessionResult(
            organization_id=organization_id,
            run_session_id=run_session.id,
            run_plan_id=plan.id,
            outcome=outcome,
            success_criteria_met="met" if outcome == "success" else "not_met",
            failure_criteria_met="not_met",
            invalidation_hit=invalidation_hit,
            entry_assessment=entry_assessment,
            discipline_assessment=discipline_assessment,
            behaved_as_expected=behaved_as_expected,
            recorded_by=user_id,
            recorded_at=recorded,
        )
        session.add(result)
        session.commit()
        return run_session.id


_ENDPOINTS = (
    "/strategy-quality/detectors",
    "/strategy-quality/summary",
    "/strategy-quality/detectors/liquidity_sweep/explain",
)


def test_endpoints_require_auth(harness: Harness) -> None:
    for path in _ENDPOINTS:
        assert harness.client.get(path).status_code == 401, path


def test_reader_dependency_allows_viewer_and_blocks_unknown() -> None:
    reader = require_membership_roles(
        MembershipRole.OWNER, MembershipRole.TRADER, MembershipRole.VIEWER
    )
    viewer = SimpleNamespace(membership_role=MembershipRole.VIEWER)
    assert reader(viewer) is viewer

    owner_only = require_membership_roles(MembershipRole.OWNER)
    with pytest.raises(ForbiddenError):
        owner_only(SimpleNamespace(membership_role=MembershipRole.VIEWER))


def test_empty_tenant_lists_known_detectors_as_insufficient(harness: Harness) -> None:
    headers, _org, _user = _register_owner(harness.client)
    resp = harness.client.get("/strategy-quality/detectors", headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    conditions = {d["condition"]: d for d in body["detectors"]}
    # All five known detectors appear even with no data.
    for known in ("liquidity_sweep", "sfp", "trend_pullback", "order_block", "breakout_retest"):
        assert known in conditions
        assert conditions[known]["sample_size"] == 0
        assert conditions[known]["insufficient_data"] is True
        assert conditions[known]["trust_tier"] == "none"
        assert conditions[known]["verdict"] == "needs_more_validation"
        assert conditions[known]["quality_score"] is None
    assert "does not" in body["note"] or "read-only" in body["note"].lower()


def test_trusted_detector_scored_from_outcomes(harness: Harness) -> None:
    headers, org, _user = _register_owner(harness.client)
    for _ in range(5):
        _seed_session(harness.factory, organization_id=org, condition="liquidity_sweep")

    resp = harness.client.get("/strategy-quality/detectors", headers=headers)
    assert resp.status_code == 200, resp.text
    detectors = {d["condition"]: d for d in resp.json()["detectors"]}
    sweep = detectors["liquidity_sweep"]
    assert sweep["sample_size"] == 5
    assert sweep["insufficient_data"] is False
    assert sweep["trust_tier"] == "medium"
    assert sweep["verdict"] == "trusted"
    assert sweep["quality_score"] == 75.0
    assert sweep["success_rate"] == 1.0
    # Most-evidenced sufficient detector ranks first.
    assert resp.json()["detectors"][0]["condition"] == "liquidity_sweep"


def test_noisy_detector_flagged_avoid_for_now(harness: Harness) -> None:
    headers, org, _user = _register_owner(harness.client)
    for _ in range(6):
        _seed_session(
            harness.factory,
            organization_id=org,
            condition="sfp",
            outcome="invalidated",
            invalidation_hit=True,
            discipline_assessment="should_have_avoided",
            behaved_as_expected=False,
        )

    resp = harness.client.get(
        "/strategy-quality/detectors", headers=headers, params={"condition": "sfp"}
    )
    assert resp.status_code == 200, resp.text
    detectors = resp.json()["detectors"]
    assert len(detectors) == 1
    sfp = detectors[0]
    assert sfp["verdict"] == "avoid_for_now"
    codes = {w["code"] for w in sfp["warnings"]}
    assert "noisy_high_invalidation" in codes
    assert "frequently_should_have_avoided" in codes


def test_confidence_normalized_before_bucketing(harness: Harness) -> None:
    headers, org, _user = _register_owner(harness.client)
    for _ in range(5):
        # Stored on the 0-100 scale as real detector confidence is.
        _seed_session(
            harness.factory, organization_id=org, condition="order_block", confidence=80.0
        )

    resp = harness.client.get("/strategy-quality/detectors/order_block/explain", headers=headers)
    assert resp.status_code == 200, resp.text
    calibration = resp.json()["report"]["confidence_calibration"]
    assert calibration["mean_confidence"] == 0.8
    high_bucket = next(b for b in calibration["buckets"] if b["bucket"] == "high")
    assert high_bucket["sample_size"] == 5


def test_overconfident_detector_calibration(harness: Harness) -> None:
    headers, org, _user = _register_owner(harness.client)
    for _ in range(5):
        _seed_session(
            harness.factory,
            organization_id=org,
            condition="breakout_retest",
            outcome="failure",
            confidence=0.9,
            behaved_as_expected=False,
        )

    resp = harness.client.get(
        "/strategy-quality/detectors/breakout_retest/explain", headers=headers
    )
    assert resp.status_code == 200, resp.text
    report = resp.json()["report"]
    assert report["confidence_calibration"]["calibration_label"] == "overconfident"
    assert "overconfident_detector" in {w["code"] for w in report["warnings"]}


def test_summary_counts_and_ranking(harness: Harness) -> None:
    headers, org, _user = _register_owner(harness.client)
    for _ in range(5):
        _seed_session(harness.factory, organization_id=org, condition="liquidity_sweep")
    for _ in range(6):
        _seed_session(
            harness.factory,
            organization_id=org,
            condition="sfp",
            outcome="invalidated",
            invalidation_hit=True,
        )

    resp = harness.client.get("/strategy-quality/summary", headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["detectors_with_data"] == 2
    assert body["total_results"] == 11
    trusted = next(v["count"] for v in body["by_verdict"] if v["verdict"] == "trusted")
    assert trusted == 1
    # Ranking only contains sufficient-sample detectors, best first.
    assert body["ranked"][0]["condition"] == "liquidity_sweep"
    assert all(item["sample_size"] >= 5 for item in body["ranked"])


def test_explain_timeframe_breakdown_and_not_found(harness: Harness) -> None:
    headers, org, _user = _register_owner(harness.client)
    _seed_session(harness.factory, organization_id=org, condition="trend_pullback", timeframe="1h")
    _seed_session(harness.factory, organization_id=org, condition="trend_pullback", timeframe="4h")

    resp = harness.client.get("/strategy-quality/detectors/trend_pullback/explain", headers=headers)
    assert resp.status_code == 200, resp.text
    timeframes = {t["timeframe"]: t for t in resp.json()["timeframes"]}
    assert set(timeframes) == {"1h", "4h"}
    assert timeframes["1h"]["sample_size"] == 1

    missing = harness.client.get(
        "/strategy-quality/detectors/not_a_real_detector/explain", headers=headers
    )
    assert missing.status_code == 404


def test_tenant_isolation(harness: Harness) -> None:
    headers_a, org_a, _user_a = _register_owner(harness.client, "a@example.com", "Org A")
    headers_b, _org_b, _user_b = _register_owner(harness.client, "b@example.com", "Org B")
    for _ in range(5):
        _seed_session(harness.factory, organization_id=org_a, condition="liquidity_sweep")

    body_a = harness.client.get("/strategy-quality/summary", headers=headers_a).json()
    body_b = harness.client.get("/strategy-quality/summary", headers=headers_b).json()
    assert body_a["total_results"] == 5
    assert body_b["total_results"] == 0
    assert body_a["organization_id"] != body_b["organization_id"]


def test_user_filter_scopes_history(harness: Harness) -> None:
    headers, org, user = _register_owner(harness.client)
    for _ in range(5):
        _seed_session(
            harness.factory, organization_id=org, user_id=user, condition="liquidity_sweep"
        )
    # Org-wide sessions not attributed to the calling user (started_by is null).
    for _ in range(3):
        _seed_session(harness.factory, organization_id=org, user_id=None, condition="sfp")

    scoped = harness.client.get(
        "/strategy-quality/summary", headers=headers, params={"user_id": str(user)}
    ).json()
    assert scoped["total_results"] == 5

    org_wide = harness.client.get("/strategy-quality/summary", headers=headers).json()
    assert org_wide["total_results"] == 8
