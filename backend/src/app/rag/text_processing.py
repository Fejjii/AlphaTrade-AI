"""Deterministic text normalization, chunking, and hashing for RAG ingestion."""

from __future__ import annotations

import hashlib
import re
import uuid
from uuid import UUID

_WHITESPACE_RE = re.compile(r"[ \t]+")

_WHITESPACE_RE = re.compile(r"[ \t]+")


def normalize_text(text: str) -> str:
    """Collapse whitespace and normalize line endings for stable hashing."""
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    paragraphs = [
        _WHITESPACE_RE.sub(" ", paragraph.replace("\n", " ").strip())
        for paragraph in normalized.split("\n\n")
    ]
    paragraphs = [paragraph for paragraph in paragraphs if paragraph]
    return "\n\n".join(paragraphs)


def compute_text_hash(text: str) -> str:
    """Stable SHA-256 hash of normalized chunk text."""
    return hashlib.sha256(normalize_text(text).encode()).hexdigest()


def compute_source_hash(
    *,
    title: str,
    text: str,
    source_type: str,
    organization_id: UUID | None,
) -> str:
    """Stable hash for duplicate document detection."""
    payload = "|".join(
        [
            title.strip(),
            source_type,
            str(organization_id) if organization_id else "",
            normalize_text(text),
        ]
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def stable_chunk_id(document_id: UUID, ordinal: int, text_hash: str) -> UUID:
    """Deterministic chunk id derived from document, ordinal, and content hash."""
    name = f"{document_id}:{ordinal}:{text_hash}"
    return uuid.uuid5(uuid.NAMESPACE_URL, name)


def chunk_text(text: str, *, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    """Split normalized text into overlapping chunks."""
    normalized = normalize_text(text)
    if not normalized:
        return []

    paragraphs = [p.strip() for p in normalized.split("\n\n") if p.strip()]
    chunks: list[str] = []
    buffer = ""

    def flush_buffer() -> None:
        nonlocal buffer
        if buffer.strip():
            chunks.append(buffer.strip())
        buffer = ""

    for paragraph in paragraphs:
        if len(paragraph) <= chunk_size:
            candidate = f"{buffer}\n\n{paragraph}".strip() if buffer else paragraph
            if len(candidate) <= chunk_size:
                buffer = candidate
            else:
                flush_buffer()
                buffer = paragraph
            continue

        start = 0
        while start < len(paragraph):
            end = min(start + chunk_size, len(paragraph))
            piece = paragraph[start:end].strip()
            if piece:
                if buffer:
                    flush_buffer()
                chunks.append(piece)
            if end >= len(paragraph):
                break
            start = max(end - overlap, start + 1)

    flush_buffer()
    return chunks


def estimate_token_count(text: str) -> int:
    """Rough token estimate for metadata (deterministic, no external tokenizer)."""
    return max(len(text.split()), 1)
