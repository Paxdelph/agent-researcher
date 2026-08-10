# Agent Researcher

Локальный хелпер продуктового аналитика. **Шаг 1:** brief → план исследования (`analysis-plan.md`) через Lead → Analyst → Lead. Правки и утверждение — только в чате.

## Быстрый старт (Docker)

```bash
cd ~/Work/my-projects/agent-researcher
cp .env.example .env   # OPENAI_API_KEY / ANTHROPIC_API_KEY
cp config.example.yaml config.yaml

# опционально: symlink launcher
ln -sfn "$PWD/scripts/agent-research" ~/.local/bin/agent-research

cd researches/example
agent-research --build
```

UI: http://127.0.0.1:8787

Флаги: `--build`, `--reset`, `-d`.

## Как пользоваться

1. Brief → «сделай план» (Lead → Analyst → Lead).
2. «Едем дальше» → данные в `data/` → «проверь данные».
3. «Сделай скелет» (Lead → Analyst → Storyteller → **BI Analyst** viz-pass).
4. «Собери отчёт» — **Coder** пишет `report.qmd` (R + plotly), рендер HTML, **Designer** визуально ревьюит (один раунд фикса).
5. Правки кода в чате снова гоняют design review.

UI: http://127.0.0.1:8787

## Локально без Docker

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

export WORKSPACE_PATH=./researches/example
export STATE_DIR=./.app-state
export AGENT_RESEARCHER_CONFIG=./config.yaml
# + API keys in env

uvicorn app.main:app --host 0.0.0.0 --port 8787 --reload
```

## Структура

- `app/orchestration/planning.py` — Lead → Analyst → Lead
- `app/orchestration/chat.py` — interpret / edit / advance
- `app/skills/` — инструкции (не stage-промпты)
- `app/prompts/` — короткие роли Lead / Analyst
- `scripts/agent-research` — запуск из папки анализа

## Папка анализа

Любая директория с `data/` (создаётся launcher'ом при необходимости). Артефакт шага 1: `analysis-plan.md` в корне workspace.
