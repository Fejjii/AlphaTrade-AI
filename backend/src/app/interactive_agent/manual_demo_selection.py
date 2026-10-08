"""Bounded manual time/quantity/status selectors. Unsupported precision is explicit."""

import re
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

MONTHS = {
    name.lower(): i
    for i, name in enumerate(
        (
            "January",
            "February",
            "March",
            "April",
            "May",
            "June",
            "July",
            "August",
            "September",
            "October",
            "November",
            "December",
        ),
        1,
    )
}
UUID_PATTERN = r"[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}"


def manual_selectors(message: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    command = re.search(
        rf"\b(?:command|attempt|order)\s*(?:id\s*)?[=:]?\s*({UUID_PATTERN})\b", message, re.I
    )
    if command:
        result.update(
            command_id=command.group(1),
            execution_venue="BLOFIN_DEMO",
            trade_origin="manual_demo_test",
        )
    quantity = re.search(r"\b(\d+(?:\.\d+)?)\s*contracts?\b", message, re.I)
    if quantity:
        value = Decimal(quantity.group(1))
        if value > 0 and len(quantity.group(1)) <= 24:
            result["requested_quantity"] = str(value)
        else:
            result["unsupported_filters"] = [
                "Requested contract quantity exceeds supported precision."
            ]
    if re.search(r"\b(?:blocked|unsent)\b", message, re.I):
        result["submission_status"] = "blocked"
    elif re.search(r"\buncertain\b", message, re.I):
        result["submission_status"] = "uncertain"
    elif re.search(r"\bfilled\b", message, re.I):
        result["submission_status"] = "filled"
    elif re.search(r"\bsubmitted\b", message, re.I):
        result["submission_status"] = "submitted"
    iso = re.search(r"\b(20\d{2})-(\d{2})-(\d{2})\b", message)
    english = re.search(r"\b(\d{1,2})\s+(" + "|".join(MONTHS) + r")\s+(20\d{2})\b", message, re.I)
    time = re.search(r"\b(\d{1,2}):(\d{2})(?::(\d{2}))?\s*(UTC|Z)\b", message, re.I)
    if iso or english:
        try:
            if iso:
                day = datetime(int(iso[1]), int(iso[2]), int(iso[3]), tzinfo=UTC)
            else:
                assert english is not None
                day = datetime(
                    int(english[3]), MONTHS[english[2].lower()], int(english[1]), tzinfo=UTC
                )
            if time:
                instant = day.replace(
                    hour=int(time[1]), minute=int(time[2]), second=int(time[3] or 0)
                )
                around = bool(re.search(r"\b(?:around|about|approximately)\b", message, re.I))
                result.update(
                    since=(instant - timedelta(minutes=5) if around else instant).isoformat(),
                    until=(
                        instant + timedelta(minutes=5) if around else instant + timedelta(minutes=1)
                    ).isoformat(),
                )
            elif re.search(r"\b\d{1,2}:\d{2}", message):
                result.setdefault("unsupported_filters", []).append(
                    "Submission time requires UTC or an explicit structured "
                    "timezone-aware range; no time filter was guessed."
                )
            else:
                result.update(
                    since=day.isoformat(),
                    until=(day + timedelta(days=1) - timedelta(microseconds=1)).isoformat(),
                )
        except (ValueError, TypeError):
            result.setdefault("unsupported_filters", []).append(
                "Submission date/time is invalid; use an ISO date and UTC time."
            )
    elif time or re.search(
        r"\b(?:today|yesterday|" + "|".join(MONTHS) + r"|\d{1,2}:\d{2})\b", message, re.I
    ):
        result.setdefault("unsupported_filters", []).append(
            "Submission time requires an explicit date including year and UTC "
            "time; no date was guessed."
        )
    if re.search(r"\b(?:stop|target|entry price|pnl)\s*[=:]?\s*\d", message, re.I):
        result.setdefault("unsupported_filters", []).append(
            "Stop/target/price/PnL selection filters are unsupported; use "
            "command ID, submission time, contracts and status."
        )
    return result
