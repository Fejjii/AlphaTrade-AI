"""Deterministic fake venue used by Phase 1 dispatch tests.

No network I/O. Production and demo adapters are never constructed here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from threading import Lock


class FakeVenueBehavior(StrEnum):
    ACCEPT = "ACCEPT"
    REJECT = "REJECT"
    AMBIGUOUS = "AMBIGUOUS"
    RAISE = "RAISE"


@dataclass(frozen=True)
class FakeVenueOrder:
    client_order_id: str
    status: str


@dataclass
class FakeVenueSubmitProvider:
    """In-process venue fake. At most one semantic order per client order ID."""

    behavior: FakeVenueBehavior = FakeVenueBehavior.ACCEPT
    name: str = "phase1-fake-venue"
    _lock: Lock = field(default_factory=Lock)
    submitted: list[str] = field(default_factory=list)
    orders: dict[str, FakeVenueOrder] = field(default_factory=dict)

    def submit(self, *, client_order_id: str) -> FakeVenueOrder | None:
        with self._lock:
            if self.behavior is FakeVenueBehavior.RAISE:
                raise RuntimeError("fake_venue_send_interrupted")
            if self.behavior is FakeVenueBehavior.AMBIGUOUS:
                self.submitted.append(client_order_id)
                return None
            if client_order_id in self.orders:
                return self.orders[client_order_id]
            status = "accepted" if self.behavior is FakeVenueBehavior.ACCEPT else "rejected"
            order = FakeVenueOrder(client_order_id=client_order_id, status=status)
            self.orders[client_order_id] = order
            self.submitted.append(client_order_id)
            return order

    def lookup(self, *, client_order_id: str) -> FakeVenueOrder | None:
        with self._lock:
            return self.orders.get(client_order_id)

    @property
    def submit_count(self) -> int:
        with self._lock:
            return len(self.submitted)
