"""Persisted rolling SFP scans distinguish decimal encoding from true conflicts."""

from copy import deepcopy
from datetime import timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from structlog.testing import capture_logs

from app.db.public_market_observations import PublicMarketObservationRow
from app.evidence_pipeline.assembler import FirstSliceEvidenceAssembler
from app.evidence_pipeline.watcher_port import AssemblingWatcherScanEvidence
from app.market_contracts.errors import DuplicateDataError, MarketContractError
from app.market_contracts.hashing import with_content_hash
from app.watcher.errors import WatcherEvidenceUnavailableError
from tests.support.live_market_monitor import ScriptedPerpetualSource
from tests.test_live_evidence_pipeline import _evaluation_command
from tests.test_sfp_detector import BULL, spec
from tests.test_sfp_strategy_brain_runtime import approve, padded_evidence
from tests.test_sfp_strategy_brain_runtime import postgres_store as postgres_store
from tests.test_sfp_strategy_brain_runtime import store as store

DECIMAL_FIELDS = ("open", "high", "low", "close", "base_volume", "quote_volume")


@pytest.fixture(params=("sqlite", "postgres"))
def receipt_store(request):
    if request.param == "sqlite":
        return request.getfixturevalue("store")
    session, org, user, _factory = request.getfixturevalue("postgres_store")
    url = session.get_bind().url.render_as_string(hide_password=False)
    return session, org, user, url


def encoded(bars):
    return tuple(
        with_content_hash(
            bar.model_copy(
                update={name: Decimal(f"{getattr(bar, name):.8f}") for name in DECIMAL_FIELDS}
            )
        )
        for bar in bars
    )


def load(session, policy, bars, *, now):
    source = ScriptedPerpetualSource(replay=False, bars_15m=list(bars))
    port = AssemblingWatcherScanEvidence(
        FirstSliceEvidenceAssembler(source, replay=False, clock=lambda: now),
        session=session,
        executable_resolver=lambda _: policy,
    )
    result = port.load(_evaluation_command(policy.organization_id))
    assert result is not None
    return result


def receipts(session):
    return {
        row.observation_id: deepcopy((row.payload, row.ohlcv))
        for row in session.scalars(select(PublicMarketObservationRow))
    }


def test_rolling_encoding_reuse_preserves_original_receipts_for_both_scopes_and_restart(
    receipt_store,
):
    session, org, user, url = receipt_store
    policies = [approve(session, org, user, spec(bearish=bearish)) for bearish in (False, True)]
    bars, _ = padded_evidence([*BULL, (104, 106, 103, 105)])
    assert [bar.content_hash for bar in encoded(bars)] == [bar.content_hash for bar in bars]
    initial = bars[:260]
    first_at = initial[-1].interval_end + timedelta(seconds=5)
    for policy in policies:
        load(session, policy, initial[-256:], now=first_at)
        session.commit()
    original = receipts(session)
    assert len(original) == 256

    engine = create_engine(url)
    with Session(engine) as restarted:
        for size in (261, 262, 263):
            selected = encoded(bars[size - 256 : size])
            now = selected[-1].interval_end + timedelta(seconds=5)
            for policy in policies:
                for _repeat in range(2):
                    result = load(restarted, policy, selected, now=now)
                    restarted.commit()
                    assert result.assessment_command.trigger.revision == 1
                    assert (
                        result.assessment_command.public_observations[0].interval_end
                        == selected[-1].interval_end
                    )
            current = receipts(restarted)
            assert all(current[key] == payload for key, payload in original.items())
            assert len(current) == 256 + size - 260
    engine.dispose()


def test_true_payload_change_keeps_original_evidence_and_strict_refusal(receipt_store):
    session, org, user, _ = receipt_store
    policy = approve(session, org, user)
    bars, _ = padded_evidence()
    now = bars[-1].interval_end + timedelta(seconds=5)
    load(session, policy, bars, now=now)
    session.commit()
    original = receipts(session)
    changed = (
        *bars[:-1],
        with_content_hash(bars[-1].model_copy(update={"high": bars[-1].high + Decimal("0.01")})),
    )
    with capture_logs() as logs, pytest.raises(WatcherEvidenceUnavailableError) as failure:
        load(session, policy, changed, now=now + timedelta(seconds=1))
    assert isinstance(failure.value.__cause__, DuplicateDataError)
    assert failure.value.reason_code == "canonical_contract_invalid_contract"
    assert receipts(session) == original
    conflict = next(item for item in logs if item["event"] == "canonical_ohlcv_receipt_conflict")
    assert conflict["conflicting_fields"] == ["content_hash", "high"]
    assert "high" not in conflict and "ohlcv" not in conflict and "payload" not in conflict


def test_explicit_revision_appends_and_provider_revision_regression_is_refused(receipt_store):
    session, org, user, _ = receipt_store
    policy = approve(session, org, user)
    bars, _ = padded_evidence()
    now = bars[-1].interval_end + timedelta(seconds=5)
    load(session, policy, bars, now=now)
    session.commit()
    original = receipts(session)
    revised = (
        *bars[:-1],
        with_content_hash(
            bars[-1].model_copy(
                update={
                    "revision": 2,
                    "high": bars[-1].high + Decimal("0.01"),
                }
            )
        ),
    )
    result = load(session, policy, revised, now=now + timedelta(seconds=1))
    session.commit()
    current = receipts(session)
    assert len(current) == len(original) + 1
    assert all(current[key] == payload for key, payload in original.items())
    assert result.assessment_command.trigger.revision == 2
    with capture_logs() as logs, pytest.raises(WatcherEvidenceUnavailableError) as failure:
        load(session, policy, bars, now=now + timedelta(seconds=2))
    assert isinstance(failure.value.__cause__, DuplicateDataError)
    assert "older canonical candle revision" in str(failure.value.__cause__)
    assert any(item["event"] == "canonical_ohlcv_revision_regressed" for item in logs)
    assert receipts(session) == current


def test_wrapper_logs_only_allowlisted_failure_category():
    secret = "https://provider.example/?api_key=DO_NOT_LOG payload=PRIVATE_DATA"
    with capture_logs() as logs, pytest.raises(WatcherEvidenceUnavailableError):
        AssemblingWatcherScanEvidence._raise_undiagnosed(MarketContractError(secret))
    assert logs == [
        {
            "event": "canonical_evidence_contract_rejected",
            "failure_reason": "invalid_contract",
            "log_level": "warning",
        }
    ]
    assert secret not in repr(logs)
