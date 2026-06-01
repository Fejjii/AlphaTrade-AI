"""Test-only fixtures — not used by production guardrail paths.

Deterministic agent workflow tests may still use markers in *nodes* for risk and
proposal scaffolding (e.g. ``[test_high_risk]``). Guardrail tests should prefer
realistic attack strings or the helpers below rather than production marker checks.
"""

from __future__ import annotations

# Explicitly test-only strings for unit tests that need forced outcomes.
FORCE_INVALID_OUTPUT = "[test_force_invalid_output]"
TEST_INVALID_NARRATIVE = "[test_invalid_narrative]"
TEST_UNSAFE_NARRATIVE = "[test_unsafe_narrative]"
