"""Phase 3 — strategy immutability, AST compiler, Wilder ATR, migrations."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.analysis.wilder_atr_v1 import (
    FinalOhlcvBar,
    OhlcvFinality,
    WilderAtrStatus,
    compute_wilder_atr_v1,
)
from app.core.errors import PersistencePolicyError
from app.core.operation_policy import operation_scope
from app.core.persistence_firewall import install_persistence_firewall
from app.db.base import Base
from app.db.models import (
    CompiledSetupDefinition,
    GlobalSetupTemplate,
    Membership,
    Organization,
    SetupDefinition,
    SetupMigrationRun,
    User,
    UserStrategy,
    UserStrategyVersion,
)
from app.db.strategy_immutability import (
    ImmutableHistoryError,
    StrategyVersionImmutabilityError,
)
from app.schemas.agent import Intent, IntentDecision, OperationClass, PrincipalRef, RequestedAction
from app.schemas.common import (
    EntryTriggerType,
    ExitRuleType,
    ManualLevelType,
    MembershipRole,
    SetupCategory,
    SetupCompileStatus,
    StrategyId,
    Timeframe,
    TradeDirection,
)
from app.schemas.manual_levels import ManualChartLevelCreate, ManualChartLevelUpdate
from app.schemas.setup_ast import (
    ALLOWED_FIELD_SPECS,
    AstExpr,
    AstNodeKind,
    AstUnit,
    fld,
    lit_decimal,
)
from app.schemas.strategy_library import StrategyCard, UserStrategyCreate, UserStrategyUpdate
from app.schemas.structured_rules import (
    EntryRuleBlock,
    ExitRuleBlock,
    StructuredRules,
    StructuredRulesPatch,
)
from app.services.canonical_serialization import canonical_sha256
from app.services.compiled_setup_service import CompiledSetupService
from app.services.manual_level_service import ManualLevelService
from app.services.setup_ast_compiler import (
    SetupAstCompileError,
    compile_from_authored,
    compile_pattern,
)
from app.services.setup_ast_compiler import (
    first_slice_bearish_sweep_pattern as compiler_first_slice,
)
from app.services.setup_migration_service import SetupMigrationService
from app.services.strategy_library_service import StrategyLibraryService
from app.services.strategy_versioning import CrossTenantStrategyError, StrategyVersioningService
from app.services.structured_rules_service import StructuredRulesService

ORG_A = uuid.UUID("00000000-0000-0000-0000-00000000c001")
ORG_B = uuid.UUID("00000000-0000-0000-0000-00000000c002")
USER_A = uuid.UUID("00000000-0000-0000-0000-00000000c011")
USER_B = uuid.UUID("00000000-0000-0000-0000-00000000c012")


def _engine() -> sessionmaker[Session]:
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
    install_persistence_firewall()
    return sessionmaker(bind=engine, expire_on_commit=False)


@pytest.fixture
def session() -> Iterator[Session]:
    factory = _engine()
    with factory() as db:
        db.add_all(
            [
                Organization(id=ORG_A, name="Phase3 Org A"),
                Organization(id=ORG_B, name="Phase3 Org B"),
                User(
                    id=USER_A,
                    email="phase3-a@test.example",
                    hashed_password="not-a-real-hash",
                ),
                User(
                    id=USER_B,
                    email="phase3-b@test.example",
                    hashed_password="not-a-real-hash",
                ),
            ]
        )
        db.flush()
        db.add_all(
            [
                Membership(
                    organization_id=ORG_A,
                    user_id=USER_A,
                    role=MembershipRole.TRADER,
                ),
                Membership(
                    organization_id=ORG_B,
                    user_id=USER_B,
                    role=MembershipRole.TRADER,
                ),
            ]
        )
        db.commit()
        yield db


def _card(**overrides: object) -> StrategyCard:
    payload: dict[str, object] = {
        "strategy_name": "Bearish Liquidity Sweep Exhaustion at 4h Resistance",
        "market_type": "crypto_perp",
        "asset_universe": ["BTCUSDT"],
        "timeframes": ["15m", "4h"],
        "entry_conditions": ["Bearish liquidity sweep at 4h resistance"],
        "confirmation_conditions": ["CVD divergence"],
        "invalidation": ["Close back above sweep high"],
        "stop_loss": ["Above sweep high"],
        "take_profit_plan": ["TP1 at 1R"],
        "runner_plan": [],
        "position_sizing": ["1%"],
        "add_rules": [],
        "no_trade_rules": [],
        "backtest_rules": [],
        "success_criteria": [],
        "validation_status": "draft",
    }
    payload.update(overrides)
    return StrategyCard.model_validate(payload)


def _first_slice_rules() -> StructuredRules:
    return StructuredRules(
        primary_timeframe=Timeframe.M15,
        entry_rules=[
            EntryRuleBlock(
                trigger_type=EntryTriggerType.LIQUIDITY_SWEEP,
                direction=TradeDirection.SHORT,
            )
        ],
        exit_rules=[
            ExitRuleBlock(rule_type=ExitRuleType.FIXED_STOP, value=Decimal("1")),
            ExitRuleBlock(rule_type=ExitRuleType.TP_MULTIPLE, r_multiple=Decimal("1")),
        ],
    )


def _create_strategy(
    session: Session, *, org: uuid.UUID = ORG_A, user: uuid.UUID = USER_A
) -> UserStrategy:
    service = StrategyLibraryService(session)
    return service.create(
        UserStrategyCreate(
            organization_id=org,
            user_id=user,
            name="Phase3 Sweep",
            setup_type=StrategyId.LIQUIDITY_SWEEP_REVERSAL,
            card=_card(),
        )
    )


def _readonly_decision(org: uuid.UUID, user: uuid.UUID) -> IntentDecision:
    return IntentDecision(
        intent=Intent.MARKET_ANALYSIS,
        operation_class=OperationClass.READ_ONLY,
        organization_id=org,
        principal=PrincipalRef(user_id=user),
        requested_action=RequestedAction.NONE,
    )


def test_semantic_update_creates_new_draft_and_preserves_old(session: Session) -> None:
    created = _create_strategy(session)
    versioning = StrategyVersioningService(session)
    parent = versioning.selected_version(session.get(UserStrategy, created.id))  # type: ignore[arg-type]
    assert parent is not None
    parent_id = parent.id
    parent_hash = parent.content_hash
    parent_card = dict(parent.card)

    rules = StructuredRulesService(session)
    rules.patch(
        created.id,
        StructuredRulesPatch(
            primary_timeframe=Timeframe.M15,
            entry_rules=_first_slice_rules().entry_rules,
            exit_rules=_first_slice_rules().exit_rules,
        ),
        organization_id=ORG_A,
        user_id=USER_A,
    )
    session.flush()

    old = session.get(UserStrategyVersion, parent_id)
    assert old is not None
    assert old.content_hash == parent_hash
    assert old.card == parent_card
    assert old.structured_rules is None

    strategy = session.get(UserStrategy, created.id)
    assert strategy is not None
    assert strategy.current_version == 2
    selected = versioning.selected_version(strategy)
    assert selected is not None
    assert selected.id != parent_id
    assert selected.parent_version_id == parent_id
    assert selected.structured_rules is not None


def test_in_place_semantic_mutation_rejected(session: Session) -> None:
    created = _create_strategy(session)
    version = StrategyVersioningService(session).selected_version(
        session.get(UserStrategy, created.id)  # type: ignore[arg-type]
    )
    assert version is not None
    version.structured_rules = {"entry_rules": []}
    with pytest.raises(StrategyVersionImmutabilityError):
        session.flush()


def test_alias_mismatch_rejected(session: Session) -> None:
    created = _create_strategy(session)
    version = StrategyVersioningService(session).selected_version(
        session.get(UserStrategy, created.id)  # type: ignore[arg-type]
    )
    assert version is not None
    with pytest.raises(SetupAstCompileError):
        StrategyVersioningService(session).assert_tenant_version(
            version, organization_id=ORG_A, alias="some-other-name"
        )


def test_one_canonical_persisted_identity(session: Session) -> None:
    created = _create_strategy(session)
    version = StrategyVersioningService(session).selected_version(
        session.get(UserStrategy, created.id)  # type: ignore[arg-type]
    )
    assert version is not None
    compiler = CompiledSetupService(session)
    rules = StructuredRulesService(session)
    rules.patch(
        created.id,
        StructuredRulesPatch(
            primary_timeframe=Timeframe.M15,
            entry_rules=_first_slice_rules().entry_rules,
            exit_rules=_first_slice_rules().exit_rules,
        ),
        organization_id=ORG_A,
        user_id=USER_A,
    )
    session.flush()
    selected = StrategyVersioningService(session).selected_version(
        session.get(UserStrategy, created.id)  # type: ignore[arg-type]
    )
    assert selected is not None
    first = compiler.compile_version(selected.id, organization_id=ORG_A, user_id=USER_A)
    second = compiler.compile_version(selected.id, organization_id=ORG_A, user_id=USER_A)
    assert first.status is SetupCompileStatus.EXECUTABLE
    assert first.compiled is not None
    assert second.compiled is not None
    assert first.compiled.id == second.compiled.id
    rows = list(session.scalars(select(CompiledSetupDefinition)).all())
    assert len(rows) == 1
    assert rows[0].strategy_version_id == selected.id


def test_global_template_remains_global(session: Session) -> None:
    setup = SetupDefinition(
        name="Legacy Sweep",
        strategy_id=StrategyId.LIQUIDITY_SWEEP_REVERSAL,
        category=SetupCategory.REVERSAL,
        version=1,
    )
    session.add(setup)
    session.flush()
    report = SetupMigrationService(session).run(dry_run=False, organization_id=ORG_A)
    assert report.templates_created == 1
    template = session.scalar(select(GlobalSetupTemplate))
    assert template is not None
    assert template.is_global is True
    assert template.organization_id is None
    assert template.setup_definition_id == setup.id


def test_tenant_compiled_definition_is_tenant_scoped(session: Session) -> None:
    created = _create_strategy(session)
    StructuredRulesService(session).patch(
        created.id,
        StructuredRulesPatch(
            primary_timeframe=Timeframe.M15,
            entry_rules=_first_slice_rules().entry_rules,
            exit_rules=_first_slice_rules().exit_rules,
        ),
        organization_id=ORG_A,
        user_id=USER_A,
    )
    session.flush()
    selected = StrategyVersioningService(session).selected_version(
        session.get(UserStrategy, created.id)  # type: ignore[arg-type]
    )
    assert selected is not None
    outcome = CompiledSetupService(session).compile_version(
        selected.id, organization_id=ORG_A, user_id=USER_A
    )
    assert outcome.compiled is not None
    assert outcome.compiled.organization_id == ORG_A
    with pytest.raises(CrossTenantStrategyError):
        CompiledSetupService(session).compile_version(
            selected.id, organization_id=ORG_B, user_id=USER_B
        )


def test_ast_golden_serialization_and_hash_stability() -> None:
    first = compile_pattern(compiler_first_slice())
    second = compile_pattern(compiler_first_slice())
    assert first.document is not None
    assert second.document is not None
    assert first.document.content_hash == second.document.content_hash
    assert first.document.content_hash == canonical_sha256(
        first.document.pattern.model_dump(mode="python")
    )
    dumped = first.document.pattern.model_dump(mode="json")
    assert dumped["symbols"] == ["BTCUSDT"]
    assert dumped["trigger_timeframe"] == "15m"
    assert dumped["context_timeframe"] == "4h"


def test_unsupported_field_rejected() -> None:
    pattern = compiler_first_slice()
    pattern = pattern.model_copy(
        update={"trigger": AstExpr(kind=AstNodeKind.FIELD, path="foo.unknown", unit=AstUnit.PRICE)}
    )
    result = compile_pattern(pattern)
    assert result.status == SetupCompileStatus.NON_EXECUTABLE.value
    assert any(item.code == "unsupported_field" for item in result.failures)


def test_unsupported_operator_rejected() -> None:
    pattern = compiler_first_slice()
    pattern = pattern.model_copy(
        update={
            "trigger": AstExpr(
                kind=AstNodeKind.COMPARE,
                op="approx",
                args=[fld("ohlcv.close"), lit_decimal("1", AstUnit.PRICE)],
            )
        }
    )
    result = compile_pattern(pattern)
    assert any(item.code == "unsupported_operator" for item in result.failures)


def test_missing_feature_rejected() -> None:
    pattern = compiler_first_slice().model_copy(update={"features": []})
    result = compile_pattern(pattern)
    assert any(item.code == "missing_feature" for item in result.failures)


def test_ambiguous_legacy_mapping_fail_closed() -> None:
    card = _card()
    rules = StructuredRules(
        primary_timeframe=Timeframe.H4,
        entry_rules=[EntryRuleBlock(trigger_type=EntryTriggerType.EMA_PULLBACK)],
        exit_rules=[ExitRuleBlock(rule_type=ExitRuleType.FIXED_STOP, value=Decimal("1"))],
    )
    result = compile_from_authored(card=card, rules=rules)
    assert result.status == SetupCompileStatus.NON_EXECUTABLE.value
    assert any(item.code == "ambiguous_mapping" for item in result.failures)


def _atr_bar(
    index: int,
    *,
    high: str,
    low: str,
    close: str,
    finality: OhlcvFinality = OhlcvFinality.FINAL,
    revision: uuid.UUID | None = None,
    instrument: str = "BTCUSDT",
    timeframe: str = "15m",
) -> FinalOhlcvBar:
    open_time = datetime(2026, 1, 1, tzinfo=UTC) + timedelta(minutes=15 * index)
    close_time = open_time + timedelta(minutes=15)
    payload = {
        "instrument": instrument,
        "timeframe": timeframe,
        "open_time": open_time,
        "high": Decimal(high),
        "low": Decimal(low),
        "close": Decimal(close),
        "index": index,
    }
    return FinalOhlcvBar(
        revision_id=revision or uuid.uuid4(),
        content_hash=canonical_sha256(payload),
        venue="binance",
        market="usdm_perp",
        instrument=instrument,
        timeframe=timeframe,
        open_time=open_time,
        close_time=close_time,
        open=Decimal(close),
        high=Decimal(high),
        low=Decimal(low),
        close=Decimal(close),
        volume=Decimal("10"),
        finality=finality,
    )


def test_wilder_atr_warmup_and_value() -> None:
    bars = [_atr_bar(i, high="2", low="0", close="1") for i in range(14)]
    feature = compute_wilder_atr_v1(bars)
    assert feature.status is WilderAtrStatus.VALUE
    assert feature.value == Decimal("2").quantize(Decimal("1E-16"))
    incomplete = compute_wilder_atr_v1(bars[:13])
    assert incomplete.status is WilderAtrStatus.MISSING
    assert incomplete.missing_reason == "warmup_incomplete"


def test_wilder_atr_final_candle_and_missing() -> None:
    bars = [_atr_bar(i, high="2", low="0", close="1") for i in range(13)]
    bars.append(_atr_bar(13, high="2", low="0", close="1", finality=OhlcvFinality.FORMING))
    feature = compute_wilder_atr_v1(bars)
    assert feature.status is WilderAtrStatus.MISSING
    assert feature.missing_reason == "forming_candle"


def test_wilder_atr_correction_determinism() -> None:
    bars = [_atr_bar(i, high="2", low="0", close="1") for i in range(14)]
    first = compute_wilder_atr_v1(bars)
    second = compute_wilder_atr_v1(bars)
    assert first.content_hash == second.content_hash
    corrected = list(bars)
    corrected[-1] = _atr_bar(13, high="4", low="0", close="2")
    changed = compute_wilder_atr_v1(corrected)
    assert changed.content_hash != first.content_hash
    assert changed.value != first.value


def test_manual_level_revision_immutability(session: Session) -> None:
    service = ManualLevelService(session)
    created = service.create(
        ManualChartLevelCreate(
            organization_id=ORG_A,
            user_id=USER_A,
            symbol="BTCUSDT",
            exchange="binance",
            timeframe=Timeframe.H4,
            level_type=ManualLevelType.RESISTANCE,
            price=Decimal("68000"),
        )
    )
    first = service.current_revision(created.id, organization_id=ORG_A)
    assert first is not None
    first_id = first.id
    first_hash = first.content_hash
    first_value = first.value
    service.update(
        created.id,
        ManualChartLevelUpdate(price=Decimal("69000")),
        organization_id=ORG_A,
        user_id=USER_A,
    )
    session.flush()
    historical = service.get_revision(first_id, organization_id=ORG_A)
    assert historical.content_hash == first_hash
    assert historical.value == first_value
    current = service.current_revision(created.id, organization_id=ORG_A)
    assert current is not None
    assert current.id != first_id
    assert current.supersedes_revision_id == first_id
    assert current.value == Decimal("69000")
    with pytest.raises(ImmutableHistoryError):
        first.value = Decimal("1")
        session.flush()
    session.rollback()


def test_manual_level_cross_tenant_rejected(session: Session) -> None:
    service = ManualLevelService(session)
    created = service.create(
        ManualChartLevelCreate(
            organization_id=ORG_A,
            user_id=USER_A,
            symbol="BTCUSDT",
            exchange="binance",
            timeframe=Timeframe.H4,
            level_type=ManualLevelType.RESISTANCE,
            price=Decimal("68000"),
        )
    )
    revision = service.current_revision(created.id, organization_id=ORG_A)
    assert revision is not None
    from app.services.manual_level_service import CrossTenantLevelError

    with pytest.raises(CrossTenantLevelError):
        service.get_revision(revision.id, organization_id=ORG_B)


def test_migration_dry_run_apply_idempotency_and_rollback(session: Session) -> None:
    session.add(
        SetupDefinition(
            name="Legacy Global",
            strategy_id=StrategyId.LIQUIDITY_SWEEP_REVERSAL,
            category=SetupCategory.REVERSAL,
            version=1,
        )
    )
    created = _create_strategy(session)
    StructuredRulesService(session).patch(
        created.id,
        StructuredRulesPatch(
            primary_timeframe=Timeframe.M15,
            entry_rules=_first_slice_rules().entry_rules,
            exit_rules=_first_slice_rules().exit_rules,
        ),
        organization_id=ORG_A,
        user_id=USER_A,
    )
    session.flush()
    migrator = SetupMigrationService(session)
    dry = migrator.run(dry_run=True, organization_id=ORG_A)
    assert dry.templates_created == 1
    assert session.scalar(select(GlobalSetupTemplate)) is None
    applied = migrator.run(dry_run=False, organization_id=ORG_A)
    assert applied.templates_created == 1
    assert applied.compiled_created == 1
    template = session.scalar(select(GlobalSetupTemplate))
    assert template is not None
    assert template.organization_id is None
    again = migrator.run(dry_run=False, organization_id=ORG_A)
    assert again.templates_skipped >= 1
    assert again.compiled_skipped >= 1
    assert again.compiled_created == 0
    retained = migrator.rollback_run(applied.run_id)  # type: ignore[arg-type]
    assert retained == 0
    remaining = list(session.scalars(select(CompiledSetupDefinition)).all())
    assert len(remaining) == 1
    assert session.scalar(select(GlobalSetupTemplate)) is not None
    rollback_rows = list(
        session.scalars(select(SetupMigrationRun).where(SetupMigrationRun.mode == "rollback")).all()
    )
    assert len(rollback_rows) == 1


def test_readonly_cannot_write_compiled_setup(session: Session) -> None:
    created = _create_strategy(session)
    version = StrategyVersioningService(session).selected_version(
        session.get(UserStrategy, created.id)  # type: ignore[arg-type]
    )
    assert version is not None
    with (
        operation_scope(_readonly_decision(ORG_A, USER_A)),
        pytest.raises(PersistencePolicyError),
    ):
        session.add(
            CompiledSetupDefinition(
                organization_id=ORG_A,
                user_id=USER_A,
                strategy_id=created.id,
                strategy_version_id=version.id,
                compiler_version="setup-ast/v1",
                grammar_version="setup-ast-grammar/v1",
                compiled_ast={"pattern": {}},
                content_hash="a" * 64,
            )
        )
        session.flush()


def test_card_update_does_not_rewrite_parent(session: Session) -> None:
    created = _create_strategy(session)
    parent = StrategyVersioningService(session).selected_version(
        session.get(UserStrategy, created.id)  # type: ignore[arg-type]
    )
    assert parent is not None
    parent_id = parent.id
    StrategyLibraryService(session).update(
        created.id,
        UserStrategyUpdate(card=_card(strategy_name="Renamed Sweep")),
        organization_id=ORG_A,
        user_id=USER_A,
    )
    session.flush()
    old = session.get(UserStrategyVersion, parent_id)
    assert old is not None
    assert old.card["strategy_name"] == "Bearish Liquidity Sweep Exhaustion at 4h Resistance"


def test_allowlist_contains_first_slice_fields() -> None:
    required = {
        "ohlcv.open",
        "ohlcv.high",
        "ohlcv.low",
        "ohlcv.close",
        "ohlcv.volume",
        "feature.wilder_atr_v1.value",
        "swing.S",
        "manual_level.R",
        "cvd.at_bar_close",
        "flow.signed_quote_delta_T",
        "flow.total_quote_volume_T",
        "evidence.tick_size",
    }
    assert required.issubset(ALLOWED_FIELD_SPECS)
