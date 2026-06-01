"""Shared deterministic pattern rules for guardrails."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class PatternRule:
    """A named regex rule evaluated case-insensitively against text."""

    rule_id: str
    pattern: re.Pattern[str]
    description: str


def compile_rules(specs: Sequence[tuple[str, str, str]]) -> list[PatternRule]:
    """Compile ``(rule_id, regex, description)`` tuples into pattern rules."""
    return [
        PatternRule(
            rule_id=rule_id,
            pattern=re.compile(regex, re.IGNORECASE),
            description=description,
        )
        for rule_id, regex, description in specs
    ]


def match_rules(text: str, rules: Sequence[PatternRule]) -> list[str]:
    """Return rule ids that matched the given text."""
    return [rule.rule_id for rule in rules if rule.pattern.search(text)]
