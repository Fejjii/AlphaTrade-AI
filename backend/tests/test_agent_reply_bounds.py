"""Bounded conversational prose ends at complete, cited statements."""

import json

import pytest

from app.interactive_agent.conversation import _prose, compose_visible_reply


def _lead(reply):
    return reply.split("\n\nRecorded facts (not a confirmation):", 1)[0]


@pytest.mark.parametrize("structured", [False, True])
def test_model_and_visible_bounds_keep_complete_cited_playbook_sentences(structured):
    sentence = "The Master Playbook proposes discipline guidance, not approved settings [K1]. "
    complete = sentence * 23
    prose = complete + "An unresolved decision needs explicit approval " * 20 + "."
    assert len(complete) < 1900 < 2000 < len(prose)
    content = json.dumps({"summary": prose}) if structured else prose
    model = _prose(content)
    assert model == complete.rstrip() + "\n\nReply shortened to fit the display limit."
    assert len(model) <= 2000
    assert _lead(compose_visible_reply(model, "Source [K1]: Master Playbook v1, chunk 9.")) == model


@pytest.mark.parametrize(
    "citation",
    [
        "[K1, K2]",
        "【Master Playbook v1, chunk 9】",
        "[Master Playbook](https://example.com/source_(v1))",
    ],
)
def test_sentence_with_attached_citation_is_omitted_if_source_crosses_limit(citation):
    previous = "Earlier discipline guidance is proposed [K1]. " * 10
    # A period before the source is not a safe cut: the claim and source stay together.
    budget = 2000 - len("\n\nReply shortened to fit the display limit.")
    claim = (
        "Pending decision: " + "x" * (budget - 2 - len(previous) - len("Pending decision: ")) + ". "
    )
    prose = previous + claim + citation + " More guidance remains unresolved." * 10
    lead = _lead(compose_visible_reply(prose, "Stored document references remain available."))
    assert lead == previous.rstrip() + "\n\nReply shortened to fit the display limit."
    assert "Pending decision" not in lead
    assert citation not in lead
    assert len(lead) <= 2000


def test_periods_inside_source_titles_are_not_sentence_boundaries():
    previous = "Only this complete sentence fits [K1]. " * 10
    citation = "[" + "Source title. " * 200 + "]"
    lead = _lead(compose_visible_reply(previous + "A cited claim " + citation + ".", "Facts."))
    assert lead == previous.rstrip() + "\n\nReply shortened to fit the display limit."
    assert "Source title" not in lead


def test_overlong_single_sentence_has_a_clean_notice_instead_of_a_fragment():
    prose = "An unresolved decision " * 200 + "[K1]."
    assert _prose(prose) == "Reply shortened to fit the display limit."
    reply = compose_visible_reply(prose, "Document guidance is reference data [K1].")
    assert "do not establish approved settings" in _lead(reply)
    assert len(reply) <= 4000


def test_common_abbreviation_is_not_used_as_a_cut_inside_a_sentence():
    previous = "Discipline guidance remains proposed [K1]. " * 45
    prose = previous + "For example, e.g. " + "an unresolved decision " * 40 + "."
    assert _prose(prose) == previous.rstrip() + "\n\nReply shortened to fit the display limit."


@pytest.mark.parametrize(
    "prose", ["", "A short response [K1].", "A short bullet without punctuation"]
)
def test_short_model_content_remains_unchanged(prose):
    assert _prose(prose) == prose
