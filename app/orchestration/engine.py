"""Research orchestration engine with background tasks."""

from __future__ import annotations

import asyncio
import threading
from pathlib import Path

from app.config import get_settings
from app.models import ChatMessage, ResearchState, Status
from app.orchestration.chat import handle_user_message
from app.state import get_store

_task: asyncio.Task | None = None


class Engine:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.workspace = Path(self.settings.workspace.path)
        self.workspace.mkdir(parents=True, exist_ok=True)
        (self.workspace / self.settings.workspace.data_dir).mkdir(parents=True, exist_ok=True)
        self.store = get_store()
        self.state = self.store.ensure_for_workspace(str(self.workspace))
        self._render_lock = threading.Lock()

    def get_state(self) -> ResearchState:
        loaded = self.store.load()
        if loaded is not None:
            self.state = loaded
        return self.state

    def save_brief(self, research_question: str, business_context: str) -> ResearchState:
        self.get_state()
        if self.state.status == Status.RUNNING:
            return self.state
        self.state.research_question = research_question.strip()
        self.state.business_context = business_context.strip()
        if self.state.research_question:
            self.state.status_text = (
                "Brief сохранён — в чате напишите «сделай план» или опишите задачу"
            )
            if self.state.status == Status.IDLE:
                self.state.status = Status.WAITING_FOR_USER
        self.store.save(self.state)
        return self.state

    def _spawn(self, coro) -> None:
        global _task
        if _task and not _task.done():
            return

        async def runner() -> None:
            try:
                await coro
            except Exception as exc:  # noqa: BLE001
                self.get_state()
                self.state.status = Status.FAILED
                self.state.error = str(exc)
                self.state.active_role = None
                self.state.status_text = "Ошибка"
                self.state.chat.append(
                    ChatMessage(role="assistant", content=f"Ошибка: {exc}")
                )
                self.store.save(self.state)

        _task = asyncio.create_task(runner())

    async def handle_chat(self, message: str) -> ResearchState:
        self.get_state()
        message = message.strip()
        if not message:
            return self.state

        if self.state.status == Status.RUNNING:
            self.state.chat.append(
                ChatMessage(
                    role="assistant",
                    content="Сейчас выполняется шаг — дождитесь завершения.",
                )
            )
            self.store.save(self.state)
            return self.state

        self.state.status = Status.RUNNING
        self.state.status_text = "Обрабатываю сообщение…"
        self.state.error = None
        self.state.chat.append(ChatMessage(role="user", content=message))
        self.store.save(self.state)

        async def work() -> None:
            self.get_state()
            self.state = await handle_user_message(
                self.state, self.workspace, message, already_logged=True
            )
            if self.state.status == Status.RUNNING:
                self.state.status = Status.WAITING_FOR_USER
            self.store.save(self.state)

        self._spawn(work())
        return self.get_state()

    def save_artifact(
        self,
        name: str,
        content: str,
        artifact_id: str | None = None,
    ) -> ResearchState:
        """Write an allowed workspace artifact without calling an LLM."""
        from app.artifacts import configured_artifacts, editable_filenames, resolve_artifact
        from app.models import Stage
        from app.workspace_paths import artifact_disk_path, company_context_path

        self.get_state()
        if self.state.status == Status.RUNNING:
            raise RuntimeError("Нельзя править артефакт, пока агент работает")

        allowed = editable_filenames()
        if name not in allowed:
            raise ValueError(f"Артефакт нельзя править вручную: {name}")

        art = resolve_artifact(artifact_id) if artifact_id else None
        if art is None:
            for candidate in configured_artifacts():
                if candidate.file == name:
                    art = candidate
                    break

        if art is not None and art.id == "context":
            path = company_context_path(self.settings)
        elif art is not None and artifact_id:
            path = artifact_disk_path(art, self.settings)
        else:
            path = self.workspace / name

        path.parent.mkdir(parents=True, exist_ok=True)
        text = content if content.endswith("\n") else content + "\n"
        path.write_text(text, encoding="utf-8")

        research = self.settings.research
        plan_file = getattr(research, "plan_file", "analysis-plan.md")
        skeleton_file = getattr(research, "skeleton_file", "skeleton.md")
        report_file = getattr(research, "report_file", "report.qmd")

        if name == plan_file:
            self.state.artifacts.analysis_plan = str(path)
            if self.state.stage in {Stage.BRIEF, Stage.PLANNING}:
                self.state.stage = Stage.PLAN_READY
        elif name == skeleton_file:
            self.state.artifacts.skeleton = str(path)
        elif name == report_file:
            self.state.artifacts.report = str(path)
            if self.state.stage in {Stage.CODING_READY, Stage.CODING_APPROVED}:
                self.state.stage = Stage.CODING_READY

        hint = ""
        if name == report_file:
            hint = " Можно нажать «Перерендерить HTML» на вкладке Quarto — без моделей."

        self.state.status_text = f"Сохранено вручную: {name}"
        self.state.chat.append(
            ChatMessage(
                role="system",
                content=f"Вы вручную сохранили `{name}` (без вызова модели).{hint}",
            )
        )
        self.state.error = None
        if self.state.status == Status.IDLE:
            self.state.status = Status.WAITING_FOR_USER
        self.store.save(self.state)
        return self.state

    def render_report_local(self) -> ResearchState:
        """Quarto → HTML without LLM / design review."""
        self.get_state()
        if self.state.status == Status.RUNNING:
            raise RuntimeError("Нельзя рендерить, пока агент работает")

        if not self._render_lock.acquire(blocking=False):
            raise RuntimeError("Уже идёт рендер HTML — дождись окончания")
        try:
            return self._render_report_unlocked()
        finally:
            self._render_lock.release()

    def _render_report_unlocked(self) -> ResearchState:
        from app.orchestration.render import RenderError, render_quarto

        settings = self.settings
        qmd = settings.research.report_file
        html = settings.research.report_html_file
        if not (self.workspace / qmd).exists():
            raise RuntimeError(f"Нет файла `{qmd}` для рендера")

        self.state.status_text = f"Рендер {qmd} → {html}…"
        self.store.save(self.state)
        try:
            html_path = render_quarto(self.workspace, qmd, html)
        except RenderError:
            self.state.status_text = "Ошибка рендера Quarto"
            self.store.save(self.state)
            raise

        self.state.artifacts.report = str(self.workspace / qmd)
        self.state.artifacts.report_html = str(html_path)
        self.state.error = None
        self.state.status_text = f"Срендерено: {html} (без моделей)"
        if self.state.status == Status.IDLE:
            self.state.status = Status.WAITING_FOR_USER
        self.state.chat.append(
            ChatMessage(
                role="system",
                content=f"Локальный рендер: `{qmd}` → `{html}` (без LLM, без Designer).",
            )
        )
        self.store.save(self.state)
        return self.state


_engine: Engine | None = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = Engine()
    return _engine


def reset_engine() -> Engine:
    global _engine
    _engine = Engine()
    return _engine
