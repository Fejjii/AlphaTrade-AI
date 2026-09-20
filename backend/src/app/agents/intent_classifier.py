"""Deterministic IntentDecision classifier (Phase 1; no Tier B model routing).

Ambiguity and analysis default to READ_ONLY. EXECUTE_PAPER_PLAN is never
inferred from analysis. APPROVE never executes. REJECT/SKIP never authorize.
"""

from __future__ import annotations

import re
from uuid import UUID

from app.agents.mutation_policy import has_explicit_confirmation, is_question_message
from app.agents.strategy_intent import classify_strategy_workflow
from app.core.operation_policy import most_restrictive_class
from app.schemas.agent import (
    AgentChannel,
    ClassifierSource,
    ExtractedParameters,
    Intent,
    IntentDecision,
    MessageClass,
    OperationClass,
    PrincipalRef,
    RequestedAction,
)
from app.schemas.common import Timeframe

_UUID_RE = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)

_AMBIGUOUS_MUTATION = (
    r"\b(close it|do it|just (do|trade|execute)|go ahead|take the trade|"
    r"enter now|flatten|market order)\b"
)

_EXECUTE_PAPER_PLAN = re.compile(
    r"\bexecute\s+(?:the\s+)?approved\s+paper\s+plan\b|"
    r"\bexecute\s+paper\s+plan\b|"
    r"\bexecute\s+approved\s+plan\b",
    re.IGNORECASE,
)

_PLAN_TRADE = re.compile(
    r"\b(build|create|draft|make)\s+(?:a\s+|me\s+a\s+)?(?:paper\s+)?plan\b|"
    r"\bplan\s+(?:a\s+)?(?:paper\s+)?trade\b|"
    r"\bbuild a paper plan\b|"
    r"\bpaper plan\b",
    re.IGNORECASE,
)

_SETUP_ANALYSIS = re.compile(
    r"\bmatch(?:es)?\s+my\s+(?:pattern|setup|exhaustion)\b|"
    r"\bdoes (?:this|btc|eth|sol).{0,40}match\b|"
    r"\bsetup analysis\b|"
    r"\bexhaustion pattern\b",
    re.IGNORECASE,
)

_MARKET_ANALYSIS = re.compile(
    r"\b(analy[sz]e|analysis|watch|monitor|look at|review the chart)\b",
    re.IGNORECASE,
)

_APPROVE_PLAN = re.compile(
    r"\bapprov(?:e|al)\b",
    re.IGNORECASE,
)
_REJECT = re.compile(r"\breject\b", re.IGNORECASE)
_SKIP = re.compile(r"\bskip\b", re.IGNORECASE)

_LESSON_HINT = re.compile(r"\blesson\b", re.IGNORECASE)

_SYMBOL_RE = re.compile(r"\b(btc|eth|sol|btcUSDT|ethUSDT|solUSDT)\b", re.IGNORECASE)
_TF_RE = re.compile(r"\b(1m|3m|5m|15m|30m|1h|2h|4h|6h|12h|1d|1w)\b", re.IGNORECASE)

_MUTATION_WITHOUT_TARGET = re.compile(
    r"\b(close|flatten|cancel|execute|enter|exit)\b",
    re.IGNORECASE,
)

_STRATEGY_READ_INTENTS = frozenset(
    {
        Intent.PRE_TRADE,
        Intent.POSITION_SIZE,
        Intent.INVALIDATION_QUERY,
        Intent.LOSS_ACCEPTANCE,
        Intent.HUMAN_VS_SYSTEM,
        Intent.MANUAL_LEVELS,
        Intent.STRATEGY_STATUS,
        Intent.BACKTEST_QUEUE,
        Intent.BACKTEST_RESULTS,
        Intent.BACKTEST_ELIGIBILITY,
        Intent.EARLY_EXIT_QUERY,
        Intent.STOP_DISCIPLINE_QUERY,
        Intent.STRATEGY_TESTABILITY,
        Intent.STRUCTURE_STRATEGY,
        Intent.LESSON_PENDING_QUERY,
        Intent.LESSON_ACCEPTED_QUERY,
        Intent.LESSON_RULE_SUGGEST,
        Intent.ADD_RUNNER_RULE,
        Intent.PAPER_ELIGIBILITY_BLOCKERS,
        Intent.LESSON_STRATEGY_UPDATE,
        Intent.LESSON_STRATEGY_LINKED,
        Intent.LESSON_UNRESOLVED_BLOCKERS,
        Intent.BACKTEST_PREP,
        Intent.PAPER_VALIDATION_QUERY,
        Intent.PAPER_VALIDATION_RECOMMEND,
        Intent.PAPER_SCHEDULER_QUERY,
        Intent.PAPER_ALERTS_QUERY,
        Intent.ALERT_DELIVERY_QUERY,
        Intent.MARKET_WATCHER_QUERY,
        Intent.MARKET_WATCHER_BRIDGE_QUERY,
        Intent.STRATEGY_DISCUSSION,
    }
)

_STRATEGY_MUTATION_INTENTS = frozenset(
    {
        Intent.STRATEGY_CARD,
        Intent.BACKTEST_RUN,
        Intent.LESSON_ACCEPT,
        Intent.LESSON_REJECT,
        Intent.LESSON_CREATE_VERSION,
        Intent.PAPER_VALIDATION_START,
        Intent.PAPER_VALIDATION_SCAN,
        Intent.STRATEGY_PROPOSAL_CONFIRM,
        Intent.STRATEGY_PROPOSAL_REJECT,
    }
)


def _extract_symbol(message: str) -> str | None:
    match = _SYMBOL_RE.search(message)
    if match is None:
        return None
    token = match.group(1).upper()
    if token in {"BTC", "ETH", "SOL"}:
        return f"{token}USDT"
    return token


def _extract_timeframe(message: str) -> str | None:
    match = _TF_RE.search(message)
    if match is None:
        return None
    raw = match.group(1).lower()
    try:
        return Timeframe(raw).value
    except ValueError:
        return raw


def _first_uuid(message: str) -> UUID | None:
    match = _UUID_RE.search(message)
    if match is None:
        return None
    return UUID(match.group(0))


def _clarifying(
    *,
    intent: Intent,
    operation_class: OperationClass,
    reasons: list[str],
    organization_id: UUID | None,
    user_id: UUID | None,
    channel: AgentChannel,
    message: str,
    requested_action: RequestedAction = RequestedAction.CLARIFY,
    explicit_confirmation: bool = False,
) -> IntentDecision:
    return IntentDecision(
        intent=intent,
        operation_class=OperationClass.READ_ONLY,
        organization_id=organization_id,
        principal=PrincipalRef(user_id=user_id),
        channel=channel,
        requested_action=requested_action,
        extracted_parameters=ExtractedParameters(
            symbol=_extract_symbol(message),
            timeframe=_extract_timeframe(message),
        ),
        explicit_confirmation=explicit_confirmation,
        confidence=0.2,
        ambiguity_reasons=tuple(reasons),
        requires_clarification=True,
        classifier_source=ClassifierSource.DETERMINISTIC,
    )


def _decision(
    *,
    intent: Intent,
    operation_class: OperationClass,
    organization_id: UUID | None,
    user_id: UUID | None,
    channel: AgentChannel,
    message: str,
    requested_action: RequestedAction = RequestedAction.NONE,
    explicit_confirmation: bool = False,
    confidence: float = 0.9,
    target_type: str | None = None,
    target_id: UUID | None = None,
    target_revision_id: UUID | None = None,
    target_content_hash: str | None = None,
    ambiguity_reasons: tuple[str, ...] = (),
    requires_clarification: bool = False,
) -> IntentDecision:
    effective = operation_class
    if requires_clarification:
        effective = most_restrictive_class(operation_class, OperationClass.READ_ONLY)
    return IntentDecision(
        intent=intent,
        operation_class=effective,
        organization_id=organization_id,
        principal=PrincipalRef(user_id=user_id),
        channel=channel,
        target_type=target_type,
        target_id=target_id,
        target_revision_id=target_revision_id,
        target_content_hash=target_content_hash,
        requested_action=requested_action,
        extracted_parameters=ExtractedParameters(
            symbol=_extract_symbol(message),
            timeframe=_extract_timeframe(message),
            plan_id=target_id if target_type == "trade_plan" else None,
            revision_id=target_revision_id,
            target_id=target_id,
        ),
        explicit_confirmation=explicit_confirmation,
        confidence=confidence,
        ambiguity_reasons=ambiguity_reasons,
        requires_clarification=requires_clarification,
        classifier_source=ClassifierSource.DETERMINISTIC,
    )


def classify_message_class(message: str) -> MessageClass:
    """Classify surface form. Never emits MessageClass.COMMAND."""
    lowered = message.strip().lower()
    if "approve" in lowered or "reject" in lowered or "skip" in lowered:
        return MessageClass.APPROVAL_RESPONSE
    if any(w in lowered for w in ("journal", "mistake", "lesson")):
        return MessageClass.JOURNAL_ENTRY
    if any(w in lowered for w in ("analyze", "analysis", "setup", "plan", "btc", "eth")):
        return MessageClass.ANALYSIS_REQUEST
    if lowered.endswith("?"):
        return MessageClass.QUESTION
    return MessageClass.UNKNOWN


def classify_intent_decision(
    message: str,
    *,
    organization_id: UUID | None,
    user_id: UUID | None,
    channel: AgentChannel = AgentChannel.WEB,
) -> IntentDecision:
    """Return the immutable IntentDecision for one request."""
    explicit = has_explicit_confirmation(message)
    question = is_question_message(message)
    lowered = message.lower()

    ambiguous = re.search(_AMBIGUOUS_MUTATION, message) or (
        _MUTATION_WITHOUT_TARGET.search(message)
        and _first_uuid(message) is None
        and "plan" not in lowered
        and "analy" not in lowered
        and "paper plan" not in lowered
        and not _EXECUTE_PAPER_PLAN.search(message)
        and not _PLAN_TRADE.search(message)
        and not _APPROVE_PLAN.search(message)
    )
    # Generic execute/close without an exact target fails closed.
    if ambiguous and ("execute" in lowered or "close it" in lowered or "do it" in lowered):
        return _clarifying(
            intent=Intent.UNKNOWN,
            operation_class=OperationClass.READ_ONLY,
            reasons=["ambiguous_mutation_missing_target"],
            organization_id=organization_id,
            user_id=user_id,
            channel=channel,
            message=message,
            explicit_confirmation=explicit,
        )

    if _EXECUTE_PAPER_PLAN.search(message):
        if "analy" in lowered:
            return _clarifying(
                intent=Intent.MARKET_ANALYSIS,
                operation_class=OperationClass.READ_ONLY,
                reasons=["analysis_cannot_infer_execute_paper_plan"],
                organization_id=organization_id,
                user_id=user_id,
                channel=channel,
                message=message,
                explicit_confirmation=explicit,
            )
        return _decision(
            intent=Intent.EXECUTE_PAPER_PLAN,
            operation_class=OperationClass.EXECUTION,
            organization_id=organization_id,
            user_id=user_id,
            channel=channel,
            message=message,
            requested_action=RequestedAction.EXECUTE_PAPER_PLAN,
            explicit_confirmation=explicit,
            target_type="trade_plan",
            target_id=_first_uuid(message),
        )

    # Generic "execute" (including legacy [test_execute] + paper) is not execution.
    if "execute" in lowered and "analy" not in lowered:
        return _clarifying(
            intent=Intent.UNKNOWN,
            operation_class=OperationClass.READ_ONLY,
            reasons=["generic_execute_is_not_execute_paper_plan"],
            organization_id=organization_id,
            user_id=user_id,
            channel=channel,
            message=message,
            explicit_confirmation=explicit,
        )

    lesson = bool(_LESSON_HINT.search(message))

    if _APPROVE_PLAN.search(message) and not lesson:
        return _decision(
            intent=Intent.APPROVE,
            operation_class=OperationClass.APPROVAL,
            organization_id=organization_id,
            user_id=user_id,
            channel=channel,
            message=message,
            requested_action=RequestedAction.APPROVE,
            explicit_confirmation=explicit,
            target_type="trade_plan",
            target_id=_first_uuid(message),
        )

    if _REJECT.search(message) and not lesson:
        return _decision(
            intent=Intent.REJECT,
            operation_class=OperationClass.APPROVAL,
            organization_id=organization_id,
            user_id=user_id,
            channel=channel,
            message=message,
            requested_action=RequestedAction.REJECT,
            explicit_confirmation=explicit,
            target_type="trade_plan",
            target_id=_first_uuid(message),
        )

    if _SKIP.search(message) and not lesson:
        return _decision(
            intent=Intent.SKIP,
            operation_class=OperationClass.APPROVAL,
            organization_id=organization_id,
            user_id=user_id,
            channel=channel,
            message=message,
            requested_action=RequestedAction.SKIP,
            explicit_confirmation=explicit,
            target_type="candidate",
            target_id=_first_uuid(message),
        )

    if _PLAN_TRADE.search(message) or re.search(r"\bplan trade\b", message, re.I):
        return _decision(
            intent=Intent.PLAN_TRADE,
            operation_class=OperationClass.PLAN,
            organization_id=organization_id,
            user_id=user_id,
            channel=channel,
            message=message,
            requested_action=RequestedAction.CREATE_PLAN,
            explicit_confirmation=explicit,
        )

    if _SETUP_ANALYSIS.search(message):
        return _decision(
            intent=Intent.SETUP_ANALYSIS,
            operation_class=OperationClass.READ_ONLY,
            organization_id=organization_id,
            user_id=user_id,
            channel=channel,
            message=message,
        )

    workflow = classify_strategy_workflow(message)
    if workflow is not None:
        if workflow in _STRATEGY_MUTATION_INTENTS:
            op = OperationClass.MUTATION
            if question:
                op = OperationClass.READ_ONLY
            return _decision(
                intent=workflow,
                operation_class=op,
                organization_id=organization_id,
                user_id=user_id,
                channel=channel,
                message=message,
                requested_action=(
                    RequestedAction.CONFIRM_WRITE
                    if op is OperationClass.MUTATION
                    else RequestedAction.NONE
                ),
                explicit_confirmation=explicit,
                requires_clarification=question and workflow in _STRATEGY_MUTATION_INTENTS,
            )
        if workflow in _STRATEGY_READ_INTENTS:
            op = OperationClass.READ_ONLY
            if workflow in {Intent.LESSON_PENDING_QUERY, Intent.LESSON_ACCEPTED_QUERY}:
                op = OperationClass.JOURNAL
            return _decision(
                intent=workflow,
                operation_class=op,
                organization_id=organization_id,
                user_id=user_id,
                channel=channel,
                message=message,
            )

    if _MARKET_ANALYSIS.search(message) or "analy" in lowered:
        return _decision(
            intent=Intent.MARKET_ANALYSIS,
            operation_class=OperationClass.READ_ONLY,
            organization_id=organization_id,
            user_id=user_id,
            channel=channel,
            message=message,
        )

    if "watch" in lowered or "monitor" in lowered:
        return _decision(
            intent=Intent.MARKET_ANALYSIS,
            operation_class=OperationClass.READ_ONLY,
            organization_id=organization_id,
            user_id=user_id,
            channel=channel,
            message=message,
        )

    if "review" in lowered or "journal" in lowered:
        return _decision(
            intent=Intent.REVIEW_TRADE,
            operation_class=OperationClass.READ_ONLY,
            organization_id=organization_id,
            user_id=user_id,
            channel=channel,
            message=message,
        )

    if "rule" in lowered and "update" in lowered:
        return _decision(
            intent=Intent.UPDATE_RULE,
            operation_class=OperationClass.CONFIGURATION,
            organization_id=organization_id,
            user_id=user_id,
            channel=channel,
            message=message,
            requested_action=RequestedAction.PREVIEW,
            requires_clarification=not explicit,
        )

    if question:
        return _decision(
            intent=Intent.EXPLAIN,
            operation_class=OperationClass.READ_ONLY,
            organization_id=organization_id,
            user_id=user_id,
            channel=channel,
            message=message,
        )

    return _decision(
        intent=Intent.UNKNOWN,
        operation_class=OperationClass.READ_ONLY,
        organization_id=organization_id,
        user_id=user_id,
        channel=channel,
        message=message,
        confidence=0.4,
    )
