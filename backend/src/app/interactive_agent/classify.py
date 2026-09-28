"""Deterministic capability and artifact classification.

Keyword routing chooses a read, a proposal, or a refusal. It never treats
chat text as confirmation of a stored proposal.
"""

from __future__ import annotations

import re

from pydantic import Field

from app.interactive_agent.contracts import (
    AgentCapability,
    ArtifactKind,
    StructuredActionKind,
    TurnOperation,
)
from app.schemas.common import StrictModel

_LIVE_TRADING = re.compile(
    r"("
    r"enable real trading|enable live trading|enable live orders|"
    r"enable_real_trading|real_trading_enabled|"
    r"execution_mode\s*=\s*trade|exchange_mode\s*=\s*trade_live|"
    r"\btrade live\b|\btrade_live\b|\bgo live\b|\bswitch to live\b|"
    r"\blive account\b|\breal money\b|\bwithdraw(?:al)?\b|"
    r"\breal trading\b"
    r")",
    re.IGNORECASE,
)
_LIVE_PRICE = re.compile(r"\blive (?:price|quote|market|ticker)\b", re.IGNORECASE)
_SCREENSHOT = re.compile(
    r"\b(?:screenshot|chart image|image upload|analyze this image)\b",
    re.IGNORECASE,
)
_VOICE = re.compile(
    r"\b(?:voice note|transcribe|text to speech|speak this|audio message)\b",
    re.IGNORECASE,
)
_JOURNAL_CAPTURE = re.compile(
    r"\b(?:journal this|add to (?:my )?journal|log this trade|write (?:a )?journal)\b",
    re.IGNORECASE,
)
_STRATEGY_AUTHOR = re.compile(
    r"\b(?:create|draft|refine|update|change|build)\b[\w\s]{0,40}\bstrateg",
    re.IGNORECASE,
)
_RULE_CAPTURE = re.compile(
    r"\b(?:capture|add|record)\b[\w\s]{0,24}\b(?:rule|pattern)\b|\bmy rule is\b|\brule:",
    re.IGNORECASE,
)
_PRE_TRADE = re.compile(
    r"\b(?:pre-trade|pretrade|before i enter|invalidation|should i take)\b",
    re.IGNORECASE,
)
_POST_TRADE = re.compile(
    r"\b(?:reflect|lesson|after the trade|what did i do wrong|post-trade|post trade)\b",
    re.IGNORECASE,
)
_PLACE_ORDER = re.compile(
    r"\b(?:place\b.{0,24}\b(?:order|trade)|execute\b.{0,24}\b(?:plan|order|trade)|"
    r"submit\b.{0,16}\border)\b",
    re.IGNORECASE,
)
_STRATEGY_READ = re.compile(
    r"\bstrateg(?:y|ies)\b",
    re.IGNORECASE,
)
_STRATEGY_LIST = re.compile(
    r"\b(?:list|show|what|which|retrieve|find)\b",
    re.IGNORECASE,
)
_STATISTICS = re.compile(
    r"\b(?:win rate|pnl|p&l|performance|drawdown|expectancy|statistics)\b",
    re.IGNORECASE,
)
_MARKET = re.compile(
    r"\b(?:price|ticker|portfolio|positions?|balance|open trades|market)\b",
    re.IGNORECASE,
)
_KNOWLEDGE = re.compile(
    r"\b(?:playbook|knowledge|notes|what do i know|search my|remember)\b",
    re.IGNORECASE,
)
_TRADE = re.compile(r"\btrades?\b", re.IGNORECASE)
_OBSERVATION = re.compile(
    r"\bobservation:|\bi notice\b|\bi noticed\b|\bi see\b",
    re.IGNORECASE,
)
_HYPOTHESIS = re.compile(r"\bhypothesis:|\bi think\b|\bmight be\b", re.IGNORECASE)
_LESSON = re.compile(r"\blesson\b|\bmistake\b|\bnext time\b", re.IGNORECASE)
_RULE = re.compile(r"\brules?\b|\bpattern\b", re.IGNORECASE)
_JOURNAL_WORD = re.compile(r"\bjournal\b", re.IGNORECASE)
_DECISION = re.compile(r"\bdecision\b|\benter\b|\btake the trade\b", re.IGNORECASE)


class TurnClassification(StrictModel):
    capability: AgentCapability
    operation: TurnOperation
    artifact_kinds: list[ArtifactKind]
    action_kind: StructuredActionKind = StructuredActionKind.NONE
    screenshot_requested: bool = False
    voice_requested: bool = False
    refusal_reason: str | None = Field(default=None, max_length=300)


def _with_kind(kinds: list[ArtifactKind], kind: ArtifactKind) -> None:
    if kind not in kinds:
        kinds.append(kind)


def artifact_kinds_for(message: str, capability: AgentCapability) -> list[ArtifactKind]:
    """Label every artifact kind the message explicitly or primarily expresses."""
    kinds: list[ArtifactKind] = []
    primary = {
        AgentCapability.STRATEGY_RETRIEVAL: ArtifactKind.STRATEGY,
        AgentCapability.STRATEGY_AUTHORING: ArtifactKind.STRATEGY,
        AgentCapability.PATTERN_AND_RULE_CAPTURE: ArtifactKind.RULE,
        AgentCapability.JOURNAL_CAPTURE: ArtifactKind.JOURNAL_ENTRY,
        AgentCapability.PRE_TRADE_REASONING: ArtifactKind.TRADE_DECISION,
        AgentCapability.POST_TRADE_REFLECTION: ArtifactKind.LESSON,
    }.get(capability)
    if primary is not None:
        _with_kind(kinds, primary)
    if _OBSERVATION.search(message):
        _with_kind(kinds, ArtifactKind.OBSERVATION)
    if _HYPOTHESIS.search(message):
        _with_kind(kinds, ArtifactKind.HYPOTHESIS)
    if _RULE.search(message):
        _with_kind(kinds, ArtifactKind.RULE)
        if re.search(r"\bpattern\b", message, re.IGNORECASE):
            _with_kind(kinds, ArtifactKind.STRATEGY)
    if _JOURNAL_WORD.search(message):
        _with_kind(kinds, ArtifactKind.JOURNAL_ENTRY)
    if _DECISION.search(message) or capability is AgentCapability.PRE_TRADE_REASONING:
        _with_kind(kinds, ArtifactKind.TRADE_DECISION)
    if _LESSON.search(message):
        _with_kind(kinds, ArtifactKind.LESSON)
    if capability is AgentCapability.STRATEGY_AUTHORING:
        _with_kind(kinds, ArtifactKind.STRATEGY)
    return kinds


def _is_real_trading_request(message: str) -> bool:
    if not _LIVE_TRADING.search(message):
        return False
    # A live quote question is market data, unless another live-trading phrase remains.
    stripped = _LIVE_PRICE.sub(" ", message)
    return _LIVE_TRADING.search(stripped) is not None


def classify_turn(message: str) -> TurnClassification:
    """Choose one primary capability. Confirmation text in the same message is not applied."""
    screenshot = _SCREENSHOT.search(message) is not None
    voice = _VOICE.search(message) is not None
    if _is_real_trading_request(message):
        capability = AgentCapability.GENERAL_CONVERSATION
        return TurnClassification(
            capability=capability,
            operation=TurnOperation.REFUSE,
            artifact_kinds=artifact_kinds_for(message, capability),
            action_kind=StructuredActionKind.ENABLE_REAL_TRADING,
            screenshot_requested=screenshot,
            voice_requested=voice,
            refusal_reason=(
                "The interactive agent cannot enable real trading or submit a live order."
            ),
        )

    capability = AgentCapability.GENERAL_CONVERSATION
    operation = TurnOperation.READ
    action = StructuredActionKind.NONE
    if re.match(r"\s*observation:", message, re.IGNORECASE):
        action = StructuredActionKind.PROPOSE_OBSERVATION
        operation = TurnOperation.PROPOSE
    elif re.match(r"\s*hypothesis:", message, re.IGNORECASE):
        action = StructuredActionKind.PROPOSE_HYPOTHESIS
        operation = TurnOperation.PROPOSE
    elif _JOURNAL_CAPTURE.search(message):
        capability = AgentCapability.JOURNAL_CAPTURE
        operation = TurnOperation.PROPOSE
        action = StructuredActionKind.PROPOSE_JOURNAL_ENTRY
    elif _STRATEGY_AUTHOR.search(message):
        capability = AgentCapability.STRATEGY_AUTHORING
        operation = TurnOperation.PROPOSE
        action = StructuredActionKind.PROPOSE_STRATEGY
    elif _RULE_CAPTURE.search(message):
        capability = AgentCapability.PATTERN_AND_RULE_CAPTURE
        operation = TurnOperation.PROPOSE
        action = StructuredActionKind.PROPOSE_RULE
    elif _PRE_TRADE.search(message):
        capability = AgentCapability.PRE_TRADE_REASONING
        operation = TurnOperation.PROPOSE
        action = StructuredActionKind.PROPOSE_TRADE_DECISION
    elif _POST_TRADE.search(message):
        capability = AgentCapability.POST_TRADE_REFLECTION
        operation = TurnOperation.PROPOSE
        action = StructuredActionKind.PROPOSE_LESSON
    elif _PLACE_ORDER.search(message):
        capability = AgentCapability.TRADE_DISCUSSION
        operation = TurnOperation.PROPOSE
        action = StructuredActionKind.PROPOSE_TRADE_DECISION
    elif _STRATEGY_READ.search(message) and _STRATEGY_LIST.search(message):
        capability = AgentCapability.STRATEGY_RETRIEVAL
    elif _STATISTICS.search(message):
        capability = AgentCapability.STATISTICS_AND_PERFORMANCE
    elif _MARKET.search(message):
        capability = AgentCapability.MARKET_AND_PORTFOLIO
    elif _KNOWLEDGE.search(message):
        capability = AgentCapability.KNOWLEDGE_RETRIEVAL
    elif _TRADE.search(message):
        capability = AgentCapability.TRADE_DISCUSSION
    elif screenshot:
        capability = AgentCapability.SCREENSHOT_ANALYSIS
    elif voice:
        capability = AgentCapability.VOICE_IO
    elif message.strip():
        capability = AgentCapability.GENERAL_CONVERSATION

    return TurnClassification(
        capability=capability,
        operation=operation,
        artifact_kinds=artifact_kinds_for(message, capability),
        action_kind=action,
        screenshot_requested=screenshot,
        voice_requested=voice,
    )
