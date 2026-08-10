# Agent Researcher

Локальный хелпер продуктового аналитика: от brief до Quarto-отчёта (R + plotly) с визуальным design review.

Пайплайн в чате: **план → сверка данных → скелет → отчёт (`report.qmd` → HTML) → правки**.

## Требования

### Рекомендуемый путь — Docker

Нужно только:

- **Docker** + **Docker Compose** (v2)
- API-ключ(и) под провайдеров из `config.yaml`:
  - если агенты на OpenAI — `OPENAI_API_KEY`
  - если на Anthropic — `ANTHROPIC_API_KEY`
  - оба нужны только при смешанном конфиге (как в `config.example.yaml`); можно прописать всем агентам один `provider` и держать один ключ
- Свободный порт **8787**

R, Quarto, pandoc, Chromium и R-пакеты для knit уже внутри образа — отдельно ставить не нужно.

### Локально без Docker

Дополнительно к ключам:

| Что | Зачем |
|-----|--------|
| **Python ≥ 3.12** | приложение (FastAPI / uvicorn) |
| **R** (+ dev-заголовки под вашу ОС) | чанки в `report.qmd` |
| **R-пакеты** из `docker/install_r_packages.R` | `plotly`, `dplyr`, `readr`, `knitr`, `rmarkdown`, … |
| **[Quarto CLI](https://quarto.org/docs/get-started/)** | `quarto render` → HTML |
| **Chromium / Chrome** | скриншоты HTML для Designer |

Без R/Quarto UI и чат поднимутся, но сборка/рендер отчёта не заведутся. Без браузера design review со скриншотами не отработает.

## Быстрый старт (Docker)

```bash
git clone git@github.com:Paxdelph/agent-researcher.git
cd agent-researcher

cp .env.example .env          # вписать ключи
cp config.example.yaml config.yaml

# опционально: команда из любой research-папки
mkdir -p ~/.local/bin
ln -sfn "$PWD/scripts/agent-research" ~/.local/bin/agent-research

cd researches/example
agent-research --build
```

UI: http://127.0.0.1:8787

Флаги launcher’а: `--build`, `--reset`, `-d` / `--detach`.

Или без symlink:

```bash
RESEARCH_PATH=./researches/example docker compose up --build
```

Общий контекст компании: `researches/context.md` (для `researches/example`). Override: `CONTEXT_FILE=/path/to/context.md`.

## Как пользоваться

1. Brief в чате → «сделай план» (Lead → Analyst → Lead) → `analysis-plan.md`.
2. Положи CSV в `data/` → «проверь данные» → `data-review.md`.
3. «Сделай скелет» (Lead → Analyst → Storyteller → BI Analyst) → `skeleton.md`.
4. «Собери отчёт» — Coder пишет `report.qmd`, Quarto рендерит HTML, Designer один раунд визуального ревью.
5. Правки в чате правят `.qmd` точечно; полный пересбор — по явной просьбе («с нуля» / «переделай»).

Формат отчётов: Quarto extension **`researcher-html`** (тема и семантика `.finding` / `.kpi` / …).

## Локально без Docker

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# R-пакеты (нужен установленный R):
Rscript docker/install_r_packages.R

cp .env.example .env
cp config.example.yaml config.yaml

export WORKSPACE_PATH=./researches/example
export CONTEXT_PATH=./researches/context.md
export STATE_DIR=./.app-state
export AGENT_RESEARCHER_CONFIG=./config.yaml
# ключи уже в .env — подхватите через set -a; source .env; set +a

uvicorn app.main:app --host 0.0.0.0 --port 8787 --reload
```

## Структура

| Путь | Назначение |
|------|------------|
| `app/` | FastAPI UI, оркестрация, провайдеры LLM |
| `app/skills/` | инструкции агентам |
| `app/prompts/` | короткие роли (Lead, Analyst, Coder, …) |
| `quarto/_extensions/researcher/` | формат `researcher-html` |
| `researches/` | папки рисерчей + общий `context.md` |
| `scripts/agent-research` | запуск compose из папки анализа |
| `config.example.yaml` | шаблон конфига (локальный `config.yaml` в git не кладётся) |

## Папка рисерча

Любая директория (launcher создаст `data/` при необходимости). Рядом уровнем выше — общий `context.md`.

Типичные артефакты: `analysis-plan.md`, `data-review.md`, `skeleton.md`, `report.qmd`, `report.html`, `design-review.md`.
