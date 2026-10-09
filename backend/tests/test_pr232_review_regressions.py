"""Review regressions using native-shaped fixtures; no external account IO."""

from decimal import Decimal

import pytest

from app.services.manual_demo_history import ManualDemoHistoryService
from tests.test_manual_blofin_demo import world as world
from tests.test_manual_demo_lifecycle_workflow import set_exit
from tests.test_manual_demo_reconciliation import _service, _submit
from tests.test_manual_demo_reconciliation import native as native

__all__ = ["native", "world"]


@pytest.mark.parametrize("protection_history", ["missing", "unavailable"])
def test_closed_refresh_response_agrees_with_stored_protection_confidence(
    native, protection_history
):
    world, changes = native
    _, first = _submit(native)
    set_exit(native, first)
    if protection_history == "missing":
        changes["response"]["/api/v1/trade/orders-tpsl-history"] = []
    else:
        changes["failure"] = "/api/v1/trade/orders-tpsl-history"
    with world[0]() as session:
        refreshed = _service(world, session).reconcile(world[1], first.command_id)
        stored = ManualDemoHistoryService(session).get(world[1], first.command_id).evidence
        assert refreshed.execution_status == stored.execution_status == "closed"
        assert refreshed.exit_quantity == stored.exit_quantity == Decimal("0.1")
        assert refreshed.protection == stored.protection == "not_required_closed"
        assert not any(
            "Stop and target protection are not verified" in note
            for note in refreshed.missing_evidence
        )
        assert world[3].post_count == 1


def test_open_refresh_keeps_missing_protection_warning(native):
    world, changes = native
    _, first = _submit(native)
    world[3].open_position = True
    changes["response"]["/api/v1/trade/orders-tpsl-pending"] = []
    with world[0]() as session:
        refreshed = _service(world, session).reconcile(world[1], first.command_id)
        assert refreshed.execution_status == "filled"
        assert refreshed.position_status == "account_position_present"
        assert refreshed.protection not in {"verified", "not_required_closed"}
        assert "Stop and target protection are not verified." in refreshed.missing_evidence
        assert not refreshed.can_resolve
        assert world[3].post_count == 1
