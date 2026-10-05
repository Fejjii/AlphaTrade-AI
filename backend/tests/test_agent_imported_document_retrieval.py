"""File preview/save to Agent passages; captured inputs are not live model quality."""

import hashlib
import json

import pytest
from sqlalchemy import func, select

from app.db.models import Document, Order, UserRiskSettings, UserStrategy
from app.interactive_agent.contracts import AgentTurnRequest
from app.interactive_agent.service import InteractiveAgentService
from tests.test_knowledge_file_import import (
    ORG_A,
    ORG_B,
    SETTINGS,
    USER_A,
    USER_A2,
    USER_B,
    docx_bytes,
    pdf_bytes,
)
from tests.test_knowledge_file_import import knowledge_api as knowledge_api
from tests.test_knowledge_file_import import knowledge_db as knowledge_db

QUERY = (
    "Using my Uploaded Playbook v1, summarize my discipline rules and unresolved decisions. "
    "Cite sources and distinguish proposed guidance from approved settings."
)
TEXT = (
    "Background information. "
    * 50
    + "\n\nProposed discipline rules: never widen stops and pause after two losses. "
    "These are document proposals requiring application confirmation.\n\n"
    "Unresolved decisions: daily loss percentage and runner size remain undecided. "
    "No values have been approved in application settings."
)


def _save(client, content, filename, media_type):
    form = {"title": "Uploaded Playbook v1", "source_type": "trading_playbook"}
    upload = {"file": (filename, content, media_type)}
    preview = client.post(
        "/knowledge/files/preview", data=form, files=upload, headers={"Authorization": "first"}
    )
    assert preview.status_code == 200, preview.text
    saved = client.post(
        "/knowledge/files/import",
        data={**form, "preview_receipt": preview.json()["preview_receipt"], "confirm": "true"},
        files=upload,
        headers={"Authorization": "first"},
    )
    assert saved.status_code == 200, saved.text
    return saved.json()["document_id"]


@pytest.mark.parametrize(
    "filename,content,media_type",
    [
        ("playbook.txt", TEXT.encode(), "text/plain"),
        ("playbook.md", TEXT.encode(), "text/markdown"),
        (
            "playbook.docx",
            docx_bytes(TEXT),
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ),
        ("playbook.pdf", pdf_bytes(text=TEXT), "application/pdf"),
    ],
)
def test_imported_formats_reach_agent_with_substantive_passages_and_source_refs(
    knowledge_api, filename, content, media_type
):
    client, session = knowledge_api
    document_id = _save(client, content, filename, media_type)
    session.expire_all()
    captured = []

    class Responder:
        def compose(self, **kwargs):
            captured.append(kwargs["factual_context"])
            return "The document proposes discipline guidance and records unresolved choices [K1]."

    result = InteractiveAgentService(session, settings=SETTINGS, responder=Responder()).handle_turn(
        AgentTurnRequest(message=QUERY), organization_id=ORG_A, user_id=USER_A
    )
    assert captured and "never widen stops" in captured[0]
    assert "daily loss percentage" in captured[0]
    references = [
        json.loads(line) for line in captured[0].splitlines() if line.startswith('{"reference"')
    ]
    assert references and all(source["document_id"] == document_id for source in references)
    assert all(source["filename"] == filename for source in references)
    assert all(
        source["raw_content_hash"] == hashlib.sha256(content).hexdigest() for source in references
    )
    assert all(source["chunk_id"] and isinstance(source["ordinal"], int) for source in references)
    assert all(source["provenance"] == "user_supplied" for source in references)
    assert result.recorded_evidence == captured[0].strip()
    assert {str(hit.document_id) for hit in result.knowledge} == {document_id}
    assert not result.authority_mutated and result.proposals == []
    for model in (Order, UserRiskSettings, UserStrategy):
        assert session.scalar(select(func.count()).select_from(model)) == 0
    assert session.scalar(select(func.count()).select_from(Document)) == 1


@pytest.mark.parametrize("organization,user", [(ORG_A, USER_A2), (ORG_B, USER_B)])
def test_uploaded_source_is_unavailable_to_other_agent_principals(
    knowledge_api, organization, user
):
    client, session = knowledge_api
    _save(client, TEXT.encode(), "private.txt", "text/plain")
    captured = []

    class Responder:
        def compose(self, **kwargs):
            captured.append(kwargs["factual_context"])
            return "No source passages are available in this account scope."

    result = InteractiveAgentService(session, settings=SETTINGS, responder=Responder()).handle_turn(
        AgentTurnRequest(message=QUERY), organization_id=organization, user_id=user
    )
    assert result.knowledge == []
    assert "never widen stops" not in " ".join(captured)
    assert "private.txt" not in (result.recorded_evidence or "")
    assert not result.authority_mutated
