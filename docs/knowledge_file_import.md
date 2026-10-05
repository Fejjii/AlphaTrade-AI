# Knowledge file preview and import (AT-096)

TXT, Markdown (`.md`), DOCX and PDFs containing selectable text can be previewed
and explicitly saved to the existing Knowledge library. Import uses the existing
`Document`, `Chunk`, embedding provider and vector store. It creates no second
document database and grants no trading, strategy, risk or execution authority.
Pasted ingestion remains available through the existing API and UI.

The actual Master Playbook is already stored in staging as 40 chunks and roughly
14,058 characters. Do not reimport it or request another upload. Its existing
Agent retrieval/context correction is a separate workstream.

## Review and save

1. Open Knowledge, select **Import a file**, choose a file, title and category
   (Trading Rules, Playbook or Market Observations), then select **Preview file**.
2. Review the full extracted text and any format warnings. Preview states that
   nothing has been saved or indexed. It calls no SQL, embedding or vector API.
3. Select **Save previewed file** to save. This is the explicit confirmation;
   choosing a file or generating a preview never saves it automatically.
4. Read the storage result and recorded index observation. Refreshing the library
   should show filename, provenance and chunks. Search provides document/chunk
   references and filename; relevance scores do not confer factual authority.

Changing file, title or category invalidates the UI preview. Save verifies a
signed ten-minute receipt bound to the exact authenticated organization/user,
normalized filename, raw-byte hash, extracted-text hash, title, category and
parser version. It performs a second bounded extraction and requires `confirm`.
An expired or mismatched preview must be generated again. The receipt is not a
stored document or an authorization to operate any strategy.

The JSON preview is read-only; it is not a text editor. Correct the source file
and preview it again when extraction omits or changes important content.

## API contract

Both routes require an authenticated principal with trader-level membership and
accept multipart form data. Organization/user identity always comes from auth.
The existing preview/ingest rate limits apply; save also uses the existing RAG
ingestion quota. Preview has its own rate limit and consumes no ingest quota.

| Route | Form fields | Result |
| --- | --- | --- |
| `POST /knowledge/files/preview` | `file`, `title`, `source_type` | Full extracted text, warnings, raw/extracted SHA-256, `saved=false`, `vector_index_status=not_started`, signed receipt and expiry. |
| `POST /knowledge/files/import` | Same file/title/category, `preview_receipt`, `confirm=true` | Canonical ingestion result: document ID, stored chunk count, duplicate flag, backend/fallback and recorded vector status. |

Allowed `source_type` values are `risk_policy`, `trading_playbook` and
`general_note`. A browser multipart request must let the browser generate its
Content-Type boundary; the shared API client preserves authentication and does
not add JSON headers to `FormData`.

## Format and resource limits

| Limit | Behavior |
| --- | --- |
| File | Nonempty, maximum 5 MiB; extension and declared MIME must agree. Empty/generic MIME is accepted for browser compatibility and the parser still validates the format. |
| Multipart request | Maximum file size plus 64 KiB of form overhead, counted before multipart parsing even without Content-Length; ten-second upload deadline. |
| Extracted text | Maximum 100,000 characters, nonempty readable text; unsupported control characters refused. |
| Parser process | Maximum two parsing children per API process; 256 MiB address-space cap, three seconds of CPU, eight seconds wall time, no core dumps. Busy parsing returns a retryable error. |
| TXT/Markdown | UTF-8 (optional BOM) or BOM-marked UTF-16. Binary and unsupported encoding errors are explicit. Markdown is stored as text. |
| DOCX | At most 2,000 unique ZIP entries, 16 MiB total declared expanded content, compression ratio at most 200, no encrypted entries or XML entities. No archive extraction to disk. |
| PDF | At most 100 pages and 2 MiB decoded content stream per page. Encrypted, malformed and unreadable files are refused. |

The child parser requires POSIX resource limits; an unsupported environment
fails rather than parsing without bounds. CPU/memory termination and wall time
failure return a clear parsing-limit error and never reach ingestion.

DOCX preview includes body paragraphs and table text. Headers, footers,
footnotes, embedded documents and image text are excluded. PDF text order and
layout can differ from the original. Pages without selectable text are omitted
with a warning; a PDF with no selectable text is refused with an explicit
scanned-PDF/OCR message. This implementation performs no OCR and makes no claim
to recover images or full document layout.

## Durable records, duplicates and indexing

Migration `a4knowledge001` (parent `a3release002`) adds nullable
`documents.ingestion_metadata` JSON. It stores:

- `file`: sanitized basename, media type, raw-content SHA-256, byte size,
  extracted-text SHA-256/character count, parser version and confirmation time.
- `indexing`: SQL chunk count, vector backend, `upsert_acknowledged`, fallback
  flag and observation time.

Only extracted text/chunks and provenance are stored. Raw file binaries and
preview receipts are not persisted. Existing documents remain compatible with
null ingestion metadata; their unrecorded indexing status is shown as unknown.
Filename is also carried in chunk metadata and search citations.

Identical raw bytes saved by the same user in the same organization/category
reuse the existing document, including when renamed or given another title.
The first saved title and provenance remain canonical. Different users,
organizations or categories get independent imports. New pasted hashes include
the user; old pasted hashes are reused only for the exact original owner.
Duplicate responses expose no foreign-principal document IDs or index status.
The existing SQL uniqueness constraint also protects simultaneous duplicate
inserts. SQL ownership is checked again when materializing vector search hits.

On successful save, SQL chunks have been committed and the vector upsert has
acknowledged. This is the latest recorded ingestion observation, not a live
availability or hosted-readiness guarantee. Local/fallback indexing is labeled
explicitly. Existing fail-closed provider requirements remain in force in
staging/production. A vector ingestion failure rolls back SQL ingestion and
returns an error. Vector operations remain the existing nontransactional
external operation; a subsequent SQL commit failure can leave orphan vectors,
which scoped retrieval will not present without matching SQL chunks.

## Migration, activation and rollback

No staging deployment, infrastructure change or actual document import has been
performed as part of this branch. Apply the additive `a4knowledge001` migration
before starting application code that reads the new column, using the normal
reviewed release procedure and the intended environment's database selector.
No additional service or parser binary is required; pinned `pypdf` and
`defusedxml` packages are included in the backend lockfile.

For an application rollback, retain the nullable metadata column and deploy the
previous application version; older code ignores the added column. This
preserves imported content and provenance. If a schema downgrade is separately
necessary, first back up ingestion metadata, then downgrade to `a3release002`
only after reverting the application. The downgrade drops provenance/index
observations but preserves existing document/chunk content. Do not delete
documents as an import rollback or reactivate unrelated execution workers.

## Focused acceptance and evidence

Use disposable local test selectors and mock providers. Never run these tests
against the default inherited/staging database URL. PostgreSQL validation owns
a random schema in explicitly named `alphatrade_knowledge_test` or CI's
`alphatrade_test`; it drops only that schema on completion.

```sh
# backend: activate the safe local test environment and set an explicit,
# disposable KNOWLEDGE_POSTGRES_URL before running this command.
PYTHONPATH=src .venv/bin/python -m pytest -o addopts='' -q --tb=short --show-capture=no \
  tests/test_knowledge_file_import.py tests/test_knowledge_file_migration.py \
  tests/test_rag.py tests/test_at013_provider_fail_closed.py

# frontend
npm run test -- src/components/knowledge/KnowledgeStorePanel.test.tsx \
  src/components/knowledge/KnowledgeSemanticSearch.test.tsx src/lib/api/client.test.ts
npm run typecheck
```

Results: **81 backend cases pass**, including the actual PostgreSQL nullable JSON
upgrade/round trip/downgrade; **18 frontend cases pass**. Changed-file Ruff
lint/format, strict mypy for nine changed modules, TypeScript and ESLint pass.
The shared models file retains 94 existing missing-generic type errors outside
the added typed metadata field. No full backend suite was
run in this workstream; combined CI and staging acceptance remain separate.

The synthetic API test previews `note.txt` containing a unique synthetic risk
statement, verifies zero documents/chunks before confirmation, saves it through
the real Knowledge route and canonical ingestion, checks durable filename and
hashes, then searches it with returned document/chunk citations and filename.
Same-organization foreign users cannot reuse its receipt, enumerate the document
or obtain its ID/status through duplicate handling. TXT/Markdown/DOCX/PDF parser
cases, malformed/scanned/encrypted documents, limits, duplicate rename behavior,
legacy owner compatibility and index rollback are covered. UI tests verify
explicit save, invalidated previews, parsing errors, fallback/unknown indexing
messages, expired receipts and retained pasted ingestion.

After the combined review/CI gate, staging acceptance should use a new small
synthetic file in an authenticated test principal. Preview all four supported
formats, inspect extracted text before save, confirm only the chosen synthetic
document, search its distinctive passage with source references, repeat import
to check same-owner duplicate behavior, then verify another principal cannot
see it. A separate Agent-owned integration checks that imported passages reach
read-only Agent context with filename/raw hash/document/chunk references; it
does not claim live responder quality. Do not use or reimport the existing
Master Playbook for this acceptance.
