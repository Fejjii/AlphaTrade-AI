# Agent trade continuity and document import acceptance

A recorded-trade read stores a server-created Journal/account reference in its
assistant transcript payload. “Explain that trade” revalidates conversation,
tenant, owner and account, then reads current Journal and exact immutable lineage.
Explicit trade/account/market/direction/latest selections override that reference.
A failed or ambiguous selection clears it; absent context asks which trade is meant.
New chats remain separate even when they use the same strategy. Equal-clock,
conflicting references refuse selection. Conversation prose never authorizes actions.

Bare market names such as BTC resolve through scoped immutable plan instrument
metadata. Unknown names are unavailable; no quote currency or other market is
substituted. Journal records without that metadata need their explicit symbol.

The model receives at most eight prior user/assistant turns, 1,600 characters per
turn and 8,000 total, as conversational messages. Old raw evidence excerpts are
excluded; freshly read facts remain separate. Visible prose has up to 3,500
characters within the existing 4,000-character response budget, ending at complete
sentences with attached citations. Required missing-evidence warnings reserve
space. The complete model explanation is retained up to 16,000 characters; an
explicit notice identifies any further storage truncation. Full retrieved evidence
and source references remain separately available in collapsed **Stored evidence**.
Exact decimal values/hashes remain in evidence; display-only rounding uses an
approximation marker. Prices use stored tick precision (up to eight decimal places)
and target allocation uses percentages. Internal paper and actual demo fills remain
distinct; plans, acknowledgments and previous assistant prose never establish fills.

**Import document** in Agent opens the existing Knowledge file flow in file mode.
It saves to Knowledge. Select TXT, Markdown, DOCX or text-based PDF, set title and
category, preview extracted text, then explicitly **Save previewed file**. Preview
alone never saves. The existing validation, tenant scope, preview receipt, duplicate
handling and accurate indexing status remain authoritative. Paste ingestion remains
available. Scanned PDFs have no OCR support. Import creates no Journal entry and
approves no strategy. Unsupported screenshot controls are hidden.

## Supervising acceptance after review and deployment

1. Leave execution settings unchanged. Complete the supervising release gate on the
   reviewed SHA; this coding task does not dispatch full CI or alter its running run.
2. In a new Agent conversation ask: “Explain my latest BTC short paper trade:
   strategy, entry, stop, target, authorization and execution venue.” Check the selected
   Journal and linked plan/fill/authorization references in Stored evidence.
3. Ask “Explain that trade”. It must explain the same record without asking for a
   Journal UUID. Refresh/reopen the conversation and repeat. Verify current records,
   planned versus filled prices, venue and material missing evidence. Repeat an
   explicit latest or different-market selection and verify precedence.
4. Start another chat, ask “Explain that trade”, and verify a targeted selection
   question. Test an account ambiguity: account/trade references may be expanded,
   but the Agent must not pick one or infer approval from a playbook.
5. Verify readable prices/percentages, clean explanation endings and complete stored
   explanation/evidence. Expand Stored evidence to inspect technical references.
6. Open Import document. Confirm Knowledge destination; preview a disposable text
   document without saving and verify it is absent from Knowledge. Explicitly save,
   verify truthful storage/indexing status and duplicate behavior. Verify malformed
   or scanned PDF errors. No Journal/strategy/risk authority may change.

Old transcripts written before this change have no server-created selection. Run
one explicit recorded-trade lookup in that chat to establish the reference; prior
prose and UUID-looking text are deliberately not reconstructed as authority.
Focused PostgreSQL, API, model-router and UI fixtures establish implementation
behavior; deployed conversation quality, browser behavior and hosted search remain
supervised acceptance, not claims from mocked tests. No migration is required.
