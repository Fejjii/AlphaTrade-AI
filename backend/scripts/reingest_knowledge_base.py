#!/usr/bin/env python3
"""Reingest playbook / knowledge fixtures into the RAG collection.

Modes:
  --local  Use DATABASE_URL + RagService (writes DB + vector store).
  --api    POST /knowledge/ingest against a running backend (staging-safe).

Never prints secrets. Does not enable trading or automation.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

BACKEND_ROOT = Path(__file__).resolve().parents[1]
SRC = BACKEND_ROOT / "src"
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "knowledge_seed.json"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Reingest AlphaTrade knowledge fixtures.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--local", action="store_true", help="Ingest via local RagService + DB.")
    mode.add_argument("--api", action="store_true", help="Ingest via HTTP /knowledge/ingest.")
    parser.add_argument(
        "--fixture",
        type=Path,
        default=FIXTURE,
        help="Path to knowledge fixture JSON.",
    )
    parser.add_argument(
        "--base-url",
        default=os.environ.get("BASE_URL", "http://127.0.0.1:8000"),
        help="API base URL for --api mode.",
    )
    parser.add_argument(
        "--access-token",
        default=os.environ.get("ACCESS_TOKEN", ""),
        help="Bearer token for --api mode (or set ACCESS_TOKEN).",
    )
    parser.add_argument(
        "--organization-id",
        default=os.environ.get("ORGANIZATION_ID", ""),
        help="Organization UUID for --local mode (required).",
    )
    parser.add_argument(
        "--user-id",
        default=os.environ.get("USER_ID", ""),
        help="Optional user UUID for --local mode.",
    )
    return parser.parse_args()


def _load_fixture(path: Path) -> list[dict[str, Any]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list) or not raw:
        raise ValueError("fixture must be a non-empty JSON array")
    return raw


def _run_local(docs: list[dict[str, Any]], organization_id: str, user_id: str) -> int:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.core.config import Settings, get_settings
    from app.schemas.common import DocumentSourceType
    from app.schemas.rag import IngestDocumentRequest
    from app.services.rag_service import build_rag_service

    if not organization_id.strip():
        print(
            "Refusing: --organization-id / ORGANIZATION_ID required for --local.",
            file=sys.stderr,
        )
        return 2

    get_settings.cache_clear()
    settings = Settings()
    if settings.real_trading_enabled or settings.execution_mode.value != "paper":
        print("Refusing: trading posture is not paper-only.", file=sys.stderr)
        return 3

    org = uuid.UUID(organization_id)
    user = uuid.UUID(user_id) if user_id.strip() else None
    engine = create_engine(settings.database_url, pool_pre_ping=True)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    ingested = 0
    try:
        with factory() as session:
            service = build_rag_service(settings, session)
            for row in docs:
                payload = IngestDocumentRequest(
                    organization_id=org,
                    user_id=user,
                    source_type=DocumentSourceType(row["source_type"]),
                    title=row["title"],
                    text=row["text"],
                    source_uri=row.get("source_uri"),
                    strategy_tag=row.get("strategy_tag"),
                    symbol_tag=row.get("symbol_tag"),
                    timeframe_tag=row.get("timeframe_tag"),
                    risk_tag=row.get("risk_tag"),
                )
                result = service.ingest(payload)
                print(
                    f"  ingested title={row['title']!r} "
                    f"chunks={result.chunk_count} duplicate={result.duplicate}"
                )
                ingested += 1
    finally:
        engine.dispose()
    print(f"OK: local reingest complete ({ingested} documents)")
    return 0


def _api_post(base_url: str, token: str, body: dict[str, Any]) -> dict[str, Any]:
    data = json.dumps(body).encode("utf-8")
    req = Request(
        f"{base_url.rstrip('/')}/knowledge/ingest",
        data=data,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    with urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _run_api(docs: list[dict[str, Any]], base_url: str, token: str) -> int:
    if not token.strip():
        print("Refusing: ACCESS_TOKEN / --access-token required for --api mode.", file=sys.stderr)
        return 2
    ingested = 0
    for row in docs:
        body: dict[str, Any] = {
            "source_type": row["source_type"],
            "title": row["title"],
            "text": row["text"],
        }
        for key in ("source_uri", "strategy_tag", "symbol_tag", "timeframe_tag", "risk_tag"):
            if row.get(key):
                body[key] = row[key]
        try:
            result = _api_post(base_url, token, body)
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            print(f"FAIL ingest {row.get('title')!r}: HTTP {exc.code} {detail}", file=sys.stderr)
            return 1
        except URLError as exc:
            print(f"FAIL: cannot reach API: {exc}", file=sys.stderr)
            return 1
        print(
            f"  ingested title={row['title']!r} "
            f"chunks={result.get('chunk_count')} duplicate={result.get('duplicate')}"
        )
        ingested += 1
    print(f"OK: API reingest complete ({ingested} documents) base_url={base_url}")
    return 0


def main() -> int:
    args = _parse_args()
    docs = _load_fixture(args.fixture)
    print(f"Loaded {len(docs)} knowledge fixtures from {args.fixture}")
    if args.local:
        return _run_local(docs, args.organization_id, args.user_id)
    return _run_api(docs, args.base_url, args.access_token)


if __name__ == "__main__":
    raise SystemExit(main())
