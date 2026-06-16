# Journal Learning (Slice 36)

Discipline analysis connects journal entries to human-vs-system comparison and lesson candidates.

## Discipline analysis

`GET /journal/entries/{id}/discipline-analysis`

Returns plan adherence, early exit analysis, stop loss discipline, and generated lessons.

## Lesson candidates

When early exit or stop violation is detected, a `lesson_candidate` row is created with status `needs_review`. Lessons are not auto-promoted to permanent trading rules.

## Limitations

- Estimates are conservative and labeled
- Missing proposal/position linkage reduces accuracy
- Real trading remains disabled
