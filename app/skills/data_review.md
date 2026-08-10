# Skill: data_review

Compare the approved analysis plan with what is actually present in `data/*.csv`.

## Inputs you receive

- Current `analysis-plan.md`
- Deterministic **data profile** (files, columns, row counts, nulls, sample rows)
- Brief + product context

## Goals

1. Say clearly what is **Ready / Missing / Ambiguous** vs the plan's required files & fields.
2. If missing fields break planned cuts (e.g. no `platform`), **adjust the plan** to what the data can support — do not invent columns.
3. Keep changes incremental: only rewrite sections that must change (metrics, segments, required data, limitations, what design supports).

## Verdict

- `ok` — data covers the plan well enough; `plan_artifact` = null
- `adjusted` — plan must change; return full updated markdown in `plan_artifact`
- `blocked` — too little data to proceed meaningfully; explain what to collect; `plan_artifact` = null

## Rules

- Never claim a column exists if it is absent from the profile.
- Prefer narrowing scope (drop mobile vs web cut) over fake proxies.
- If a proxy is possible and honest (e.g. period via `app_version` / dates only), document it as a limitation.
- Reply to the user in Russian, concrete and short.
