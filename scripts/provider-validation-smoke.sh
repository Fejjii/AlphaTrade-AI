#!/usr/bin/env bash
# Provider validation smoke for OpenAI + embeddings + Qdrant compatibility.
#
# Default (local): no real provider network calls — offline checks + pytest.
#
# Remote (optional):
#   BASE_URL=https://<staging-api> ./scripts/provider-validation-smoke.sh --remote
#   ACCESS_TOKEN=... BASE_URL=... ./scripts/provider-validation-smoke.sh --remote --ingest
#
# Never prints secrets. Does not place orders or enable automation.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODE="${1:-local}"

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

ok() {
  echo "OK: $*"
}

if [[ "$MODE" == "local" || "$MODE" == "--local" ]]; then
  echo "=== Local provider validation (no live OpenAI/Qdrant required) ==="
  cd "$ROOT_DIR/backend"
  PYTHONPATH=src uv run python - <<'PY'
from __future__ import annotations

from unittest.mock import MagicMock

from app.core.config import Settings
from app.providers.embedding_dimensions import (
    MOCK_EMBEDDINGS_DIMENSIONS,
    resolve_embeddings_dimensions,
)
from app.providers.embeddings import MockEmbeddingsProvider, OpenAIEmbeddingsProvider
from app.providers.factory import resolve_providers
from app.providers.qdrant import (
    InMemoryVectorStore,
    QdrantVectorStore,
    VectorDimensionMismatchError,
    VectorPoint,
    VectorSearchFilters,
)

settings = Settings(openai_api_key="", log_json=False, provider_mode="mock")
assert resolve_embeddings_dimensions(settings) == MOCK_EMBEDDINGS_DIMENSIONS
resolved = resolve_providers(settings)
assert resolved.embeddings.name == "mock-embeddings"
assert len(resolved.embeddings.embed(["hello"])[0]) == MOCK_EMBEDDINGS_DIMENSIONS

settings_oai = Settings(
    openai_api_key="sk-test-not-used",
    embeddings_model="text-embedding-3-small",
    log_json=False,
    provider_mode="fallback",
    qdrant_url="",
)
assert resolve_embeddings_dimensions(settings_oai) == 1536
resolved_oai = resolve_providers(settings_oai)
assert resolved_oai.embeddings.name == "openai-embeddings"
assert isinstance(resolved_oai.embeddings, OpenAIEmbeddingsProvider)
assert resolved_oai.embeddings.dimensions == 1536
assert len(MockEmbeddingsProvider(dimensions=1536).embed(["a"])[0]) == 1536

settings_override = Settings(
    openai_api_key="sk-test",
    embeddings_dimensions=384,
    embeddings_model="text-embedding-3-small",
    log_json=False,
)
assert resolve_embeddings_dimensions(settings_override) == 384

store = QdrantVectorStore("http://127.0.0.1:1", vector_size=1536, fallback=InMemoryVectorStore())
assert store.using_qdrant is False

fake = QdrantVectorStore.__new__(QdrantVectorStore)
fake._url = "http://example.invalid"
fake._api_key = None
fake._fallback = InMemoryVectorStore()
fake._vector_size = 1536
fake._client = MagicMock()
fake._using_qdrant = True
fake._dimension_mismatch = None
collection_info = MagicMock()
collection_info.config.params.vectors.size = 384
fake._client.get_collection.return_value = collection_info

try:
    fake.assert_compatible("alphatrade_knowledge", 1536)
except VectorDimensionMismatchError:
    pass
else:
    raise SystemExit("expected VectorDimensionMismatchError")

fake.upsert(
    "alphatrade_knowledge",
    [VectorPoint(point_id="p2", vector=[0.2] * 1536, payload={"k": 1})],
)
hits = fake._fallback.search(
    "alphatrade_knowledge",
    [0.2] * 1536,
    filters=VectorSearchFilters(),
    top_k=1,
)
assert hits
status = fake.status()
assert status.using_fallback is True
assert "384" in (status.detail or "")

keyed = QdrantVectorStore(
    "http://127.0.0.1:1",
    api_key="test-key-not-printed",
    vector_size=1536,
    fallback=InMemoryVectorStore(),
)
assert keyed._api_key == "test-key-not-printed"
print("local provider validation checks passed")
PY
  ok "offline dimension + Qdrant compatibility checks"
  echo "Running provider/RAG/safety pytest suite..."
  PYTHONPATH=src uv run pytest \
    tests/test_provider_integration.py \
    tests/test_providers_status.py \
    tests/test_rag.py \
    tests/test_deployment_safety.py \
    tests/test_embedding_dimensions.py \
    tests/test_qdrant_dimensions.py \
    -q
  ok "pytest provider/RAG/safety suite"
  exit 0
fi

if [[ "$MODE" != "--remote" && "$MODE" != "remote" ]]; then
  fail "unknown mode '$MODE' (use local or --remote)"
fi

BASE_URL="${BASE_URL:-}"
[[ -n "$BASE_URL" ]] || fail "BASE_URL required for --remote"
BASE_URL="${BASE_URL%/}"
shift || true

echo "=== Remote provider validation against ${BASE_URL} ==="
echo "Checking safety posture..."
"$ROOT_DIR/scripts/verify-safety.sh" || fail "verify-safety failed"

echo "Checking /providers/status..."
STATUS_JSON="$(curl -fsS "${BASE_URL}/providers/status")"
STATUS_JSON="$STATUS_JSON" python3 - <<'PY'
import json
import os
import sys

body = json.loads(os.environ["STATUS_JSON"])
providers = {p["kind"]: p for p in body.get("providers", [])}
for kind in ("llm", "embeddings", "vector", "market_data"):
    if kind not in providers:
        print(f"FAIL: missing provider kind {kind}", file=sys.stderr)
        sys.exit(1)
llm = providers["llm"]
emb = providers["embeddings"]
vec = providers["vector"]
print(f"  llm={llm['name']} health={llm['health']} mock={llm['is_mock']}")
print(f"  embeddings={emb['name']} health={emb['health']} mock={emb['is_mock']}")
print(f"  vector={vec['name']} health={vec['health']} fallback={vec.get('using_fallback')}")
detail = f"{vec.get('detail') or ''} {emb.get('detail') or ''}".lower()
if "dimension mismatch" in detail or "incompatible" in detail:
    print(
        "FAIL: dimension incompatibility reported — recreate collection + reingest",
        file=sys.stderr,
    )
    sys.exit(1)
print("OK: provider status looks coherent")
PY

INGEST=false
for arg in "$@"; do
  if [[ "$arg" == "--ingest" ]]; then
    INGEST=true
  fi
done

if [[ "$INGEST" == "true" ]]; then
  [[ -n "${ACCESS_TOKEN:-}" ]] || fail "ACCESS_TOKEN required with --ingest"
  echo "Light ingest + search..."
  INGEST_JSON="$(curl -fsS -X POST "${BASE_URL}/knowledge/ingest" \
    -H "Authorization: Bearer ${ACCESS_TOKEN}" \
    -H "Content-Type: application/json" \
    -d '{"source_type":"trading_playbook","title":"Provider Smoke Playbook","text":"Human approval is required before any executable order. Paper mode remains active."}')"
  INGEST_JSON="$INGEST_JSON" python3 - <<'PY'
import json, os
print(f"  ingest chunk_count={json.loads(os.environ['INGEST_JSON'])['chunk_count']}")
PY
  SEARCH_JSON="$(curl -fsS -X POST "${BASE_URL}/knowledge/search" \
    -H "Authorization: Bearer ${ACCESS_TOKEN}" \
    -H "Content-Type: application/json" \
    -d '{"query":"approval required before executable order","top_k":3}')"
  SEARCH_JSON="$SEARCH_JSON" python3 - <<'PY'
import json
import os
import sys

body = json.loads(os.environ["SEARCH_JSON"])
chunks = body.get("chunks") or []
if not chunks:
    print("FAIL: search returned no chunks", file=sys.stderr)
    sys.exit(1)
print(f"OK: retrieval returned {len(chunks)} chunk(s)")
PY
fi

ok "remote provider validation complete"
