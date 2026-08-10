# Skill: planning_pipeline

## Goal

Turn a managerial brief into an executable product-analytics analysis plan.

## Sequence (orchestrated in code)

1. Lead writes an independent design draft from the brief.
2. Analyst critiques that draft (sees brief + Lead draft).
3. Lead synthesizes the final `analysis-plan.md` incorporating useful critique.

## Output: analysis-plan.md sections (Russian headings and body)

1. Центральный исследовательский вопрос
2. Подвопросы
3. Гипотезы (фальсифицируемые, зависимые от данных)
4. Единица анализа
5. Метрики
6. Сегменты и разрезы
7. Необходимые данные (файлы)
8. Проверки качества
9. Ограничения
10. Что дизайн поддерживает / не поддерживает
11. Неразрешённые допущения (если есть)

## Section 7 — data as thematic files (important)

Do **not** dump one flat list of 10+ fields as if everything lives in a single table.

Describe data as **separate thematic files** under `data/`, each with a clear grain and purpose. Typical split:

- `data/events.csv` (or similar) — event / funnel / session stream
- `data/users.csv` — user attributes for joins and segments
- optional extras only if needed: `orders.csv`, `sessions.csv`, `experiments.csv`, etc.

For **each file** specify:

1. **Зачем файл** — one sentence (what it answers / joins to)
2. **Зерно строки** — one row = what (event, user, order…)
3. **Ключевые поля** — short list of columns needed for *this* design
4. **Ключ стыковки** — how it joins to other files (e.g. `user_id`)
5. **Обязательность** — must-have vs nice-to-have; mark uncertain availability
6. **Пример SQL** — short extract query that would produce this file (or the closest warehouse tables). Use realistic table/column placeholders (`analytics.events`, `dim.users`, …) and the analysis time window. Keep it copy-pasteable, not pseudo-code bullets. Dialect: generic ANSI-ish SQL unless the brief names a warehouse.

Anti-patterns:

- One mega-bullet list of fields with no file boundaries
- Inventing a warehouse schema or 20 optional columns «на всякий случай»
- Mixing user attributes into the events file when a users file is cleaner
- Data section without extract SQL («поля нужны» without how to pull them)

Prefer the smallest set of files that can test the hypotheses.

## Rules

- Prefer the simplest design that answers the question.
- Separate descriptive, comparative, and causal claims.
- Only keep hypotheses that could be tested with the stated files/fields.
- If shared company `context.md` is provided (one file for all researches of the analyst), treat it as ground truth about the product world: platforms, entities, metric definitions, known logging quirks. Do not invent a conflicting product model.
- End synthesis with a short note that the human can edit via chat or say to advance.
