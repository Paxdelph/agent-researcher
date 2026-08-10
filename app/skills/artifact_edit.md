# Skill: artifact_edit

Apply **incremental** edits to an existing research artifact.

## Hard rules

1. Change **only** what the user asked for.
2. Preserve all other sections, wording, numbers, and formatting **verbatim**.
3. Do **not** regenerate the document from the brief.
4. Do **not** "improve" unrelated sections, restyle headings, or reorder content unless asked.
5. If the request is unclear, ask a clarifying question instead of rewriting (action `clarify`).
6. Return the **complete** updated file contents (full markdown), not a diff — but the content must be a minimal edit of the previous version.

## Process

1. Read the current artifact carefully.
2. Locate the smallest span that must change.
3. Apply the change.
4. Re-read: unrelated paragraphs must match the previous version character-for-character where possible.

## Anti-patterns

- Rewriting the whole plan because one sentence changed.
- Expanding scope ("while we're here…").
- Dropping sections that were not mentioned in the request.
