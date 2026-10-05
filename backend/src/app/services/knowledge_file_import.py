"""Bounded extraction and signed preview approval for existing Knowledge ingestion."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import threading
from datetime import UTC, datetime, timedelta
from pathlib import PurePosixPath
from typing import Any
from uuid import UUID

import jwt

from app.core.config import Settings
from app.core.errors import ServiceUnavailableError, ValidationAppError
from app.rag.file_import_worker import MAX_FILE_BYTES, MAX_TEXT_CHARACTERS, PARSER_VERSION
from app.schemas.common import DocumentSourceType
from app.schemas.rag import FileImportPreview, FileProvenance

_ALLOWED_CATEGORIES = {
    DocumentSourceType.RISK_POLICY,
    DocumentSourceType.TRADING_PLAYBOOK,
    DocumentSourceType.GENERAL_NOTE,
}
_MEDIA_TYPES = {
    "txt": "text/plain",
    "md": "text/markdown",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pdf": "application/pdf",
}
PREVIEW_TTL = timedelta(minutes=10)
_PARSER_SLOTS = threading.BoundedSemaphore(2)


def normalize_filename(filename: str) -> tuple[str, str]:
    basename = filename.replace("\\", "/").rsplit("/", 1)[-1].strip()
    if not basename or len(basename) > 255 or any(ord(char) < 32 for char in basename):
        raise ValidationAppError("A valid file name of at most 255 characters is required.")
    extension = PurePosixPath(basename).suffix.lower().removeprefix(".")
    if extension not in _MEDIA_TYPES:
        raise ValidationAppError("Choose a TXT, Markdown (.md), DOCX or text PDF file.")
    return basename, extension


def extract_file(content: bytes, *, filename: str, media_type: str | None) -> dict[str, Any]:
    basename, extension = normalize_filename(filename)
    if not content or len(content) > MAX_FILE_BYTES:
        raise ValidationAppError("Choose a nonempty file no larger than 5 MiB.")
    allowed_types = {_MEDIA_TYPES[extension], "application/octet-stream", ""}
    if extension == "md":
        allowed_types.add("text/plain")
    if (media_type or "").split(";", 1)[0].lower() not in allowed_types:
        raise ValidationAppError("The file type does not match its extension.")
    if not _PARSER_SLOTS.acquire(blocking=False):
        raise ServiceUnavailableError("File parsing is busy. Try the preview again shortly.")
    try:
        parsed = subprocess.run(
            [sys.executable, "-m", "app.rag.file_import_worker", extension],
            input=content,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=8,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise ValidationAppError("File parsing exceeded the eight-second time limit.") from exc
    finally:
        _PARSER_SLOTS.release()
    if parsed.returncode != 0 or len(parsed.stdout) > MAX_TEXT_CHARACTERS * 6 + 4096:
        raise ValidationAppError("File parsing exceeded a resource limit or is unsupported.")
    try:
        result = json.loads(parsed.stdout)
        if "error" in result:
            raise ValidationAppError(result["error"])
        text = result["text"]
        if not isinstance(text, str) or not 0 < len(text) <= MAX_TEXT_CHARACTERS:
            raise ValueError("Invalid extracted text.")
    except (ValueError, TypeError, KeyError) as exc:
        raise ValidationAppError("The file could not be parsed safely.") from exc
    return {
        "filename": basename,
        "media_type": _MEDIA_TYPES[extension],
        "byte_size": len(content),
        "raw_content_hash": hashlib.sha256(content).hexdigest(),
        "extracted_text_hash": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "extracted_text": text,
        "extracted_characters": len(text),
        "warnings": result.get("warnings", []),
    }


def _binding(
    extracted: dict[str, Any],
    *,
    title: str,
    source_type: DocumentSourceType,
    organization_id: UUID,
    user_id: UUID,
) -> dict[str, str]:
    return {
        "organization_id": str(organization_id),
        "user_id": str(user_id),
        "title": title,
        "source_type": source_type.value,
        "filename": extracted["filename"],
        "raw_content_hash": extracted["raw_content_hash"],
        "extracted_text_hash": extracted["extracted_text_hash"],
        "parser_version": PARSER_VERSION,
    }


def preview_file(
    content: bytes,
    *,
    filename: str,
    media_type: str | None,
    title: str,
    source_type: DocumentSourceType,
    organization_id: UUID,
    user_id: UUID,
    settings: Settings,
) -> FileImportPreview:
    title = title.strip()
    if not 1 <= len(title) <= 255 or source_type not in _ALLOWED_CATEGORIES:
        raise ValidationAppError(
            "Choose a title and a Trading Rules, Playbook or Market Observations category."
        )
    extracted = extract_file(content, filename=filename, media_type=media_type)
    expires = datetime.now(UTC) + PREVIEW_TTL
    token = jwt.encode(
        {
            **_binding(
                extracted,
                title=title,
                source_type=source_type,
                organization_id=organization_id,
                user_id=user_id,
            ),
            "exp": expires,
            "aud": "knowledge-file-preview",
        },
        settings.jwt_secret,
        algorithm="HS256",
    )
    return FileImportPreview(
        **extracted, title=title, source_type=source_type, preview_receipt=token, expires_at=expires
    )


def verify_file_save(
    content: bytes,
    *,
    filename: str,
    media_type: str | None,
    title: str,
    source_type: DocumentSourceType,
    organization_id: UUID,
    user_id: UUID,
    settings: Settings,
    preview_receipt: str,
    confirm: bool,
) -> tuple[str, FileProvenance]:
    if not confirm:
        raise ValidationAppError(
            "Review the extracted text and explicitly confirm saving the file."
        )
    try:
        receipt = jwt.decode(
            preview_receipt,
            settings.jwt_secret,
            algorithms=["HS256"],
            audience="knowledge-file-preview",
            options={"require": ["exp", "aud"]},
        )
    except jwt.InvalidTokenError as exc:
        raise ValidationAppError(
            "File preview expired or is invalid. Preview the file again."
        ) from exc
    # Validate cheap byte/principal bindings before a second bounded parse.
    basename, _ = normalize_filename(filename)
    if (
        receipt.get("organization_id"),
        receipt.get("user_id"),
        receipt.get("title"),
        receipt.get("source_type"),
        receipt.get("filename"),
        receipt.get("raw_content_hash"),
        receipt.get("parser_version"),
    ) != (
        str(organization_id),
        str(user_id),
        title.strip(),
        source_type.value,
        basename,
        hashlib.sha256(content).hexdigest(),
        PARSER_VERSION,
    ):
        raise ValidationAppError(
            "File, title, category or account changed. Preview the file again."
        )
    extracted = extract_file(content, filename=filename, media_type=media_type)
    if receipt.get("extracted_text_hash") != extracted["extracted_text_hash"]:
        raise ValidationAppError("Extracted content changed. Preview the file again.")
    provenance = FileProvenance(
        **{
            key: value
            for key, value in extracted.items()
            if key not in {"extracted_text", "warnings"}
        },
        parser_version=PARSER_VERSION,
        confirmed_at=datetime.now(UTC),
    )
    return extracted["extracted_text"], provenance
