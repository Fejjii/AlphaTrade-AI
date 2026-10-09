"""BloFin's documented ID cursors must prove complete native history."""

import pytest

from app.providers.exchange.demo_reconciliation import NativeEvidenceError, history_rows


class Client:
    def __init__(self, pages):
        self.pages = iter(pages)
        self.calls = []

    def request(self, method, endpoint, *, params, signed):
        assert method == "GET" and signed
        self.calls.append(dict(params))
        return next(self.pages)


@pytest.mark.parametrize("field", ["orderId", "tpslId", "tradeId"])
def test_history_full_page_uses_native_id_after_and_requires_terminal_page(field):
    client = Client([[{field: str(n)} for n in range(200, 100, -1)], [{field: "100"}]])
    found = history_rows(
        client, endpoint="GET /history", cursor_field=field, params={"begin": "123"}
    )
    assert len(found) == 101
    assert client.calls == [
        {"begin": "123", "limit": "100"},
        {"begin": "123", "limit": "100", "after": "101"},
    ]


@pytest.mark.parametrize("case", ["overlap", "budget"])
def test_history_overlap_and_budget_refuse_completeness(case):
    page = [{"orderId": str(n)} for n in range(200, 100, -1)]
    client = Client([page, page])
    with pytest.raises(NativeEvidenceError) as caught:
        history_rows(
            client,
            endpoint="GET /history",
            cursor_field="orderId",
            params={},
            max_pages=1 if case == "budget" else 2,
        )
    assert caught.value.reason == (
        "history_page_budget_exhausted" if case == "budget" else "history_cursor_overlap"
    )
