"""Deterministic client order ID derived from semantic execution identity."""

from __future__ import annotations

import hashlib
from uuid import UUID

from app.schemas.execution_protocol import CLIENT_ORDER_ID_NAMESPACE, SUBMIT_ENTRY_NAMESPACE

_HASH_HEX_LEN = 30


def derive_entry_client_order_id(
    *,
    account_id: UUID,
    revision_id: UUID,
    canonical_payload_hash: str,
) -> str:
    """Return a stable alphanumeric client order ID for one semantic entry.

    The preimage is operation namespace, account, immutable revision and
    CanonicalExecutionPayloadV1 hash. Transport retries cannot change it.
    """

    preimage = "\n".join(
        (
            CLIENT_ORDER_ID_NAMESPACE,
            SUBMIT_ENTRY_NAMESPACE,
            str(account_id),
            str(revision_id),
            canonical_payload_hash,
        )
    )
    digest = hashlib.sha256(preimage.encode("utf-8")).hexdigest()[:_HASH_HEX_LEN]
    return f"AT{digest}"
