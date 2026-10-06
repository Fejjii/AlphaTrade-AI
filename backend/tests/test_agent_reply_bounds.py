"""Visible bounds preserve clean citations and the separate complete explanation."""

import json
from decimal import Decimal

import pytest

from app.interactive_agent.conversation import (
    _bounded_prose,
    _prose,
    compose_visible_reply,
    present_prose,
)
from app.interactive_agent.presentation import readable_percentage, readable_price

NOTICE = "Further explanation is available in Stored evidence."


def _lead(reply):
    return reply.split("\n\nRecorded facts (not a confirmation):", 1)[0]


@pytest.mark.parametrize("structured", [False, True])
def test_explanation_past_previous_limit_is_preserved(structured):
    text = "The Playbook proposes discipline guidance; approval needs stored settings [K1]. " * 34
    assert 2000 < len(text) < 3500
    model = _prose(json.dumps({"summary": text}) if structured else text)
    assert model == text.strip()
    assert _lead(compose_visible_reply(model, "Facts.")) == model.replace(" [K1]", "")


@pytest.mark.parametrize(
    "citation", ["[K1, K2]", "【Source, chunk 9】", "[Source](https://example.com/v1)"]
)
def test_claim_and_attached_citation_are_kept_as_one_unit(citation):
    previous = "Earlier discipline remains proposed [K1]. " * 10
    budget = 3500 - len("\n\n" + NOTICE)
    claim = "Pending decision: " + "x" * (budget - 2 - len(previous) - 18) + ". "
    text = previous + claim + citation + " More unresolved guidance." * 10
    lead = _lead(compose_visible_reply(text, "Facts."))
    assert lead == previous.rstrip().replace(" [K1]", "") + "\n\n" + NOTICE
    assert citation not in lead and "Pending decision" not in lead
    assert len(lead) <= 3500


def test_periods_inside_source_titles_and_abbreviations_are_not_cuts():
    previous = "Complete sentence [K1]. " * 10
    for tail in (
        "A claim [" + "Source title. " * 300 + "]",
        "For example, e.g. " + "pending " * 500,
    ):
        assert _bounded_prose(previous + tail) == previous.rstrip() + "\n\n" + NOTICE


def test_single_overlong_sentence_and_material_warnings_remain_clean():
    text = "An unresolved decision " * 230 + "[K1]."
    assert _prose(text) == text
    result = compose_visible_reply(
        text, "Facts.", required_warnings=("Actual fills are unavailable.",)
    )
    assert _lead(result) == NOTICE + "\n\nActual fills are unavailable."
    assert len(result) <= 4000


def test_full_reply_has_a_deliberate_bound_and_visible_reply_does_not_cut_a_claim():
    text = "A complete explanation with a source [K1]. " * 700
    model = _prose(text)
    assert len(model) <= 16000 and model.endswith("further model prose was not retained.")
    visible = compose_visible_reply(model, "Evidence " * 1700)
    assert len(visible) <= 4000
    assert _lead(visible).split("\n\n", 1)[0].endswith("source.")


def test_identifiers_and_precision_are_display_only():
    identity = "9c8c5c4f-3a8c-5301-bb63-b6b6a9bdc1b2"
    original = f"Trade {identity}; hash {'a' * 64}; fill 84714.100000000001."
    shown = present_prose(original)
    assert identity not in shown and "a" * 64 not in shown
    assert "≈84,714.1" in shown and identity in original
    assert readable_price(Decimal("84714.10000000"), Decimal("0.1")) == "84,714.1"
    assert readable_percentage(Decimal("0.25000000")) == "25%"


@pytest.mark.parametrize("text", ["", "A short reply [K1].", "A short bullet"])
def test_short_model_content_is_unchanged(text):
    assert _prose(text) == text
