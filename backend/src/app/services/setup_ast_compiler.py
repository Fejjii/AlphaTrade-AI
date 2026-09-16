"""Deterministic setup AST compiler (Phase 3)."""

from __future__ import annotations

from typing import Any

from app.core.errors import ValidationAppError
from app.schemas.common import EntryTriggerType, SetupCompileStatus, Timeframe, TradeDirection
from app.schemas.setup_ast import (
    ALLOWED_ARITHMETIC_OPS,
    ALLOWED_BOOLEAN_OPS,
    ALLOWED_COMPARE_OPS,
    ALLOWED_CROSSES_OPS,
    ALLOWED_FIELD_SPECS,
    ALLOWED_UNARY_OPS,
    ALLOWED_WINDOW_OPS,
    WILDER_ATR_FEATURE_TYPE,
    WILDER_ATR_FEATURE_VERSION,
    ArithmeticOp,
    AstExpr,
    AstNodeKind,
    AstUnit,
    CompareOp,
    CompiledAstDocument,
    CompileFailure,
    CompileResult,
    FeatureRef,
    FeatureRole,
    FinalityRequirement,
    OverlapPolicy,
    PatternAst,
    PatternStep,
    UnaryOp,
    WindowAggOp,
    abs_expr,
    arith,
    boolean,
    cmp,
    fld,
    is_missing,
    lit_bool,
    lit_decimal,
    result_unit,
    unary,
    window,
)
from app.schemas.strategy_library import StrategyCard
from app.schemas.structured_rules import StructuredRules
from app.services.canonical_serialization import canonical_sha256

FIRST_SLICE_SYMBOL = "BTCUSDT"
FIRST_SLICE_TRIGGER_TF = Timeframe.M15.value
FIRST_SLICE_CONTEXT_TF = Timeframe.H4.value
FIRST_SLICE_NAME = "Bearish Liquidity Sweep Exhaustion at 4h Resistance"


class SetupAstCompileError(ValidationAppError):
    code = "setup_ast_rejected"


def _fail(code: str, message: str, path: str | None = None) -> CompileFailure:
    return CompileFailure(code=code, message=message, path=path)


def _node_unit(expr: AstExpr) -> AstUnit | None:
    if expr.unit is not None:
        return expr.unit
    if expr.kind is AstNodeKind.FIELD and expr.path is not None:
        spec = ALLOWED_FIELD_SPECS.get(expr.path)
        return spec[1] if spec else None
    if expr.kind is AstNodeKind.UNARY and expr.args:
        return _node_unit(expr.args[0])
    if expr.kind is AstNodeKind.WINDOW_AGGREGATE and expr.args:
        return _node_unit(expr.args[0])
    if expr.kind is AstNodeKind.ARITHMETIC and len(expr.args) >= 2:
        left = _node_unit(expr.args[0])
        if left is None or expr.op not in ALLOWED_ARITHMETIC_OPS:
            return None
        acc = left
        op = ArithmeticOp(expr.op)
        for arg in expr.args[1:]:
            right = _node_unit(arg)
            if right is None:
                return None
            derived = result_unit(acc, op, right)
            if derived is None:
                return None
            acc = derived
        return acc
    if expr.kind in {AstNodeKind.COMPARE, AstNodeKind.BOOLEAN, AstNodeKind.IS_MISSING}:
        return AstUnit.BOOLEAN
    return None


def validate_expr(expr: AstExpr, *, path: str, failures: list[CompileFailure]) -> None:
    if expr.kind is AstNodeKind.LITERAL:
        if expr.value is None or expr.value_type is None or expr.unit is None:
            failures.append(
                _fail("invalid_literal", "Literal requires value, type, and unit.", path)
            )
        return
    if expr.kind is AstNodeKind.FIELD:
        if expr.path is None or expr.path not in ALLOWED_FIELD_SPECS:
            failures.append(
                _fail("unsupported_field", f"Field {expr.path!r} is not in the V1 allowlist.", path)
            )
            return
        expected_type, expected_unit = ALLOWED_FIELD_SPECS[expr.path]
        if expr.value_type not in {None, expected_type} or expr.unit not in {None, expected_unit}:
            failures.append(
                _fail("field_type_mismatch", "Field type/unit does not match allowlist.", path)
            )
        return
    if expr.kind is AstNodeKind.UNARY:
        if expr.op not in ALLOWED_UNARY_OPS:
            failures.append(
                _fail("unsupported_operator", f"Unary operator {expr.op!r} rejected.", path)
            )
        if len(expr.args) != 1:
            failures.append(_fail("invalid_arity", "Unary requires one argument.", path))
        else:
            validate_expr(expr.args[0], path=f"{path}.args[0]", failures=failures)
        return
    if expr.kind is AstNodeKind.ARITHMETIC:
        if expr.op not in ALLOWED_ARITHMETIC_OPS:
            failures.append(
                _fail("unsupported_operator", f"Arithmetic operator {expr.op!r} rejected.", path)
            )
            return
        if len(expr.args) < 2:
            failures.append(
                _fail("invalid_arity", "Arithmetic requires at least two arguments.", path)
            )
            return
        units: list[AstUnit] = []
        for index, arg in enumerate(expr.args):
            validate_expr(arg, path=f"{path}.args[{index}]", failures=failures)
            unit = _node_unit(arg)
            if unit is None:
                failures.append(_fail("missing_unit", "Arithmetic operand missing unit.", path))
            else:
                units.append(unit)
        if len(units) >= 2:
            acc = units[0]
            op = ArithmeticOp(expr.op)
            for unit in units[1:]:
                derived = result_unit(acc, op, unit)
                if derived is None:
                    failures.append(
                        _fail("incompatible_units", "Arithmetic units are incompatible.", path)
                    )
                    break
                acc = derived
        return
    if expr.kind is AstNodeKind.COMPARE:
        if expr.op not in ALLOWED_COMPARE_OPS:
            failures.append(
                _fail("unsupported_operator", f"Compare operator {expr.op!r} rejected.", path)
            )
            return
        if len(expr.args) != 2:
            failures.append(_fail("invalid_arity", "Compare requires two arguments.", path))
            return
        validate_expr(expr.args[0], path=f"{path}.left", failures=failures)
        validate_expr(expr.args[1], path=f"{path}.right", failures=failures)
        left_unit = _node_unit(expr.args[0])
        right_unit = _node_unit(expr.args[1])
        if left_unit is not None and right_unit is not None and left_unit != right_unit:
            failures.append(
                _fail("incompatible_units", "Compare operands require compatible units.", path)
            )
        return
    if expr.kind is AstNodeKind.BOOLEAN:
        if expr.op not in ALLOWED_BOOLEAN_OPS:
            failures.append(
                _fail("unsupported_operator", f"Boolean operator {expr.op!r} rejected.", path)
            )
        if len(expr.args) < 2:
            failures.append(
                _fail("invalid_arity", "Boolean requires at least two arguments.", path)
            )
            return
        for index, arg in enumerate(expr.args):
            validate_expr(arg, path=f"{path}.args[{index}]", failures=failures)
        return
    if expr.kind is AstNodeKind.WINDOW_AGGREGATE:
        if expr.op not in ALLOWED_WINDOW_OPS:
            failures.append(
                _fail("unsupported_operator", f"Window operator {expr.op!r} rejected.", path)
            )
        if expr.window_bars is None:
            failures.append(_fail("invalid_window", "WindowAggregate requires window_bars.", path))
        if len(expr.args) != 1:
            failures.append(_fail("invalid_arity", "WindowAggregate requires one series.", path))
        else:
            validate_expr(expr.args[0], path=f"{path}.series", failures=failures)
        return
    if expr.kind is AstNodeKind.CROSSES:
        if expr.op not in ALLOWED_CROSSES_OPS:
            failures.append(
                _fail("unsupported_operator", f"Crosses operator {expr.op!r} rejected.", path)
            )
        if len(expr.args) != 2:
            failures.append(_fail("invalid_arity", "Crosses requires left and right.", path))
            return
        validate_expr(expr.args[0], path=f"{path}.left", failures=failures)
        validate_expr(expr.args[1], path=f"{path}.right", failures=failures)
        return
    if expr.kind is AstNodeKind.IS_MISSING:
        if len(expr.args) != 1:
            failures.append(_fail("invalid_arity", "IsMissing requires one argument.", path))
        else:
            validate_expr(expr.args[0], path=f"{path}.args[0]", failures=failures)
        return
    failures.append(_fail("unsupported_operator", f"AST kind {expr.kind} is not supported.", path))


def _required_feature_paths(expr: AstExpr) -> set[str]:
    found: set[str] = set()
    if expr.kind is AstNodeKind.FIELD and expr.path and expr.path.startswith("feature."):
        found.add(expr.path)
    for arg in expr.args:
        found.update(_required_feature_paths(arg))
    return found


def _walk_pattern_exprs(pattern: PatternAst) -> list[tuple[str, AstExpr]]:
    nodes: list[tuple[str, AstExpr]] = [
        ("preconditions", pattern.preconditions),
        ("trigger", pattern.trigger),
    ]
    for index, item in enumerate(pattern.invalidation):
        nodes.append((f"invalidation[{index}]", item))
    for index, step in enumerate(pattern.sequence):
        nodes.append((f"sequence[{index}].predicate", step.predicate))
        if step.reset_on is not None:
            nodes.append((f"sequence[{index}].reset_on", step.reset_on))
        if step.invalidate_on is not None:
            nodes.append((f"sequence[{index}].invalidate_on", step.invalidate_on))
    return nodes


def compile_pattern(pattern: PatternAst) -> CompileResult:
    failures: list[CompileFailure] = []
    for path, expr in _walk_pattern_exprs(pattern):
        validate_expr(expr, path=path, failures=failures)

    declared_roles = {feature.role for feature in pattern.features}
    for feature in pattern.features:
        if feature.feature_type != WILDER_ATR_FEATURE_TYPE:
            failures.append(
                _fail(
                    "missing_feature",
                    f"Feature type {feature.feature_type!r} is not supported in V1.",
                    "features",
                )
            )
        if feature.feature_version != WILDER_ATR_FEATURE_VERSION:
            failures.append(
                _fail(
                    "missing_feature",
                    f"Feature version {feature.feature_version!r} is not supported.",
                    "features",
                )
            )

    feature_paths: set[str] = set()
    for _, expr in _walk_pattern_exprs(pattern):
        feature_paths.update(_required_feature_paths(expr))
    if "feature.wilder_atr_v1.value" in feature_paths and FeatureRole.TRIGGER not in declared_roles:
        failures.append(
            _fail("missing_feature", "WilderAtrFeatureV1 trigger feature is required.", "features")
        )
    if (
        "feature.wilder_atr_v1.context.value" in feature_paths
        and FeatureRole.CONTEXT not in declared_roles
    ):
        failures.append(
            _fail("missing_feature", "WilderAtrFeatureV1 context feature is required.", "features")
        )

    if failures:
        return CompileResult(status=SetupCompileStatus.NON_EXECUTABLE.value, failures=failures)

    document = CompiledAstDocument(
        compiler_version=pattern.compiler_version,
        grammar_version=pattern.grammar_version,
        pattern=pattern,
        content_hash=canonical_sha256(pattern.model_dump(mode="python")),
    )
    return CompileResult(status=SetupCompileStatus.EXECUTABLE.value, document=document)


def first_slice_bearish_sweep_pattern() -> PatternAst:
    """AST for the first vertical slice. Market evaluation is not wired."""

    atr = fld("feature.wilder_atr_v1.value")
    atr_htf = fld("feature.wilder_atr_v1.context.value")
    swing = fld("swing.S")
    resistance = fld("manual_level.R")
    high = fld("ohlcv.high")
    close = fld("ohlcv.close")
    open_px = fld("ohlcv.open")
    volume = fld("ohlcv.volume")
    tick = fld("evidence.tick_size")
    cvd_t = fld("cvd.at_bar_close")
    cvd_s = fld("cvd.at_swing_close")
    signed_flow = fld("flow.signed_quote_delta_T")
    total_flow = fld("flow.total_quote_volume_T")
    trigger_high = fld("trigger.ohlcv.high")

    atr_present = boolean(
        "and",
        unary(UnaryOp.NOT, is_missing(atr)),
        unary(UnaryOp.NOT, is_missing(atr_htf)),
    )
    data_quality = boolean(
        "and",
        cmp(CompareOp.EQ, fld("predicate.finality"), lit_bool(True)),
        cmp(CompareOp.EQ, fld("predicate.freshness"), lit_bool(True)),
        cmp(CompareOp.EQ, fld("predicate.gap"), lit_bool(False)),
        atr_present,
    )
    near_resistance = cmp(
        CompareOp.LTE,
        abs_expr(arith(ArithmeticOp.SUBTRACT, swing, resistance)),
        arith(ArithmeticOp.MULTIPLY, lit_decimal("0.50", AstUnit.RATIO), atr_htf),
    )
    sweep = cmp(
        CompareOp.GTE,
        high,
        arith(
            ArithmeticOp.ADD,
            swing,
            arith(ArithmeticOp.MULTIPLY, lit_decimal("0.25", AstUnit.RATIO), atr),
        ),
    )
    close_back = boolean(
        "and",
        cmp(CompareOp.LT, close, swing),
        cmp(CompareOp.LT, close, open_px),
    )
    volume_spike = cmp(
        CompareOp.GTE,
        arith(ArithmeticOp.DIVIDE, volume, window(WindowAggOp.MEAN, volume, bars=20)),
        lit_decimal("1.50", AstUnit.RATIO),
    )
    cvd_bearish = boolean(
        "and",
        cmp(CompareOp.GT, high, swing),
        cmp(CompareOp.LT, cvd_t, cvd_s),
    )
    sell_imbalance = cmp(
        CompareOp.LTE,
        arith(ArithmeticOp.DIVIDE, signed_flow, total_flow),
        lit_decimal("-0.10", AstUnit.RATIO),
    )

    trigger = boolean(
        "and",
        near_resistance,
        sweep,
        close_back,
        volume_spike,
        cvd_bearish,
        sell_imbalance,
    )
    invalidation_buffer = arith(
        ArithmeticOp.MAX,
        arith(ArithmeticOp.MULTIPLY, lit_decimal("0.10", AstUnit.RATIO), atr),
        arith(ArithmeticOp.MULTIPLY, lit_decimal("2", AstUnit.RATIO), tick),
    )
    invalidation = cmp(
        CompareOp.GT,
        high,
        arith(ArithmeticOp.ADD, trigger_high, invalidation_buffer),
    )
    return PatternAst(
        symbols=[FIRST_SLICE_SYMBOL],
        trigger_timeframe=FIRST_SLICE_TRIGGER_TF,
        context_timeframe=FIRST_SLICE_CONTEXT_TF,
        direction=TradeDirection.SHORT,
        features=[
            FeatureRef(
                feature_type=WILDER_ATR_FEATURE_TYPE,
                feature_version=WILDER_ATR_FEATURE_VERSION,
                role=FeatureRole.TRIGGER,
                period=14,
                timeframe=FIRST_SLICE_TRIGGER_TF,
            ),
            FeatureRef(
                feature_type=WILDER_ATR_FEATURE_TYPE,
                feature_version=WILDER_ATR_FEATURE_VERSION,
                role=FeatureRole.CONTEXT,
                period=14,
                timeframe=FIRST_SLICE_CONTEXT_TF,
            ),
        ],
        preconditions=data_quality,
        sequence=[
            PatternStep(
                step_id="htf_resistance_context",
                predicate=near_resistance,
                min_offset=0,
                max_offset=0,
                finality_requirement=FinalityRequirement.FINAL_ONLY,
                overlap_policy=OverlapPolicy.DISALLOW,
            ),
            PatternStep(
                step_id="ltf_liquidity_sweep",
                predicate=boolean("and", sweep, close_back),
                min_offset=0,
                max_offset=2,
                finality_requirement=FinalityRequirement.FINAL_ONLY,
                overlap_policy=OverlapPolicy.DISALLOW,
            ),
        ],
        trigger=trigger,
        invalidation=[invalidation],
        expiration_final_bars=2,
    )


def _timeframe_values(card: StrategyCard) -> set[str]:
    return {item.value for item in card.timeframes}


def _assets(card: StrategyCard) -> set[str]:
    return {item.upper() for item in card.asset_universe}


def first_slice_mapping_possible(card: StrategyCard, rules: StructuredRules | None) -> bool:
    if rules is None or not rules.entry_rules:
        return False
    assets = _assets(card)
    timeframes = _timeframe_values(card)
    if FIRST_SLICE_SYMBOL not in assets:
        return False
    if FIRST_SLICE_TRIGGER_TF not in timeframes or FIRST_SLICE_CONTEXT_TF not in timeframes:
        return False
    entry = rules.entry_rules[0]
    if entry.trigger_type is not EntryTriggerType.LIQUIDITY_SWEEP:
        return False
    return entry.direction is TradeDirection.SHORT


def compile_from_authored(
    *,
    card: StrategyCard,
    rules: StructuredRules | None,
    strategy_version_id: Any | None = None,
    organization_id: Any | None = None,
    alias: str | None = None,
) -> CompileResult:
    if alias is not None:
        allowed = {card.strategy_name, FIRST_SLICE_NAME}
        if alias not in allowed:
            return CompileResult(
                status=SetupCompileStatus.NON_EXECUTABLE.value,
                failures=[
                    _fail(
                        "alias_mismatch",
                        "Compatibility alias does not match the canonical strategy identity.",
                        "alias",
                    )
                ],
                strategy_version_id=strategy_version_id,
                organization_id=organization_id,
            )
    if not first_slice_mapping_possible(card, rules):
        return CompileResult(
            status=SetupCompileStatus.NON_EXECUTABLE.value,
            failures=[
                _fail(
                    "ambiguous_mapping",
                    "Legacy structured rules do not map deterministically to AST V1.",
                    "structured_rules",
                )
            ],
            strategy_version_id=strategy_version_id,
            organization_id=organization_id,
        )
    result = compile_pattern(first_slice_bearish_sweep_pattern())
    return result.model_copy(
        update={
            "strategy_version_id": strategy_version_id,
            "organization_id": organization_id,
        }
    )


def assert_canonical_alias(
    *, strategy_version_id: Any, alias: str | None, strategy_name: str
) -> None:
    if alias is None:
        return
    allowed = {str(strategy_version_id), strategy_name, FIRST_SLICE_NAME}
    if alias not in allowed:
        raise SetupAstCompileError(
            "Strategy alias mismatch rejected.",
            details={"alias": alias, "strategy_version_id": str(strategy_version_id)},
            code="strategy_alias_mismatch",
        )
