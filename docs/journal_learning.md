# Journal Learning (Slice 36–37)

Discipline analysis connects journal entries to human-vs-system comparison and lesson candidates.

## Discipline analysis

`GET /journal/entries/{id}/discipline-analysis`

Returns plan adherence, early exit analysis, stop loss discipline, generated lessons, and `lesson_candidate_ids` when auto-created.

## Lesson review (Slice 37)

- Journal discipline panel links to `/lessons` or offers **Create lesson candidate**
- Accepted lessons may ingest to RAG as reviewed memory (not pending observations)
- See [lesson_workflow.md](lesson_workflow.md)

## Limitations

- Estimates are conservative and labeled
- Missing proposal/position linkage reduces accuracy
- Post-exit runner analysis requires historical candles — otherwise returns limitations
- Real trading remains disabled
