# Source-of-truth documents

This folder holds the authoritative product/engineering references for AlphaTrade AI.
All scaffolding decisions are reconciled against these documents plus the master
build prompt.

| Document | Purpose |
| --- | --- |
| `Trading_AI_PRD.pdf` | Product requirements, MVP scope, definition of done |
| `Trading_AI_System_Architecture.pdf` | Layered architecture, data model, risk engine, RAG |
| `Trading_Playbook_Master.pdf` | Trading philosophy, risk discipline, psychology rules |

> The "engineering/cursor playbook" referenced in the build prompt is the master
> prompt itself; there is no separate `trading_ai_app_cursor_playbook.pdf` file.

If these documents change, re-run the reconciliation step before scaffolding new
slices.
