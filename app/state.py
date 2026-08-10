"""Persistent research run state."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

from app.config import get_settings
from app.models import ResearchState, Stage, Status


class StateStore:
    def __init__(self, state_dir: str | Path | None = None) -> None:
        settings = get_settings()
        self.state_dir = Path(state_dir or settings.app.state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.state_path = self.state_dir / "state.json"
        self.log_path = self.state_dir / "calls.jsonl"

    def new_run(self, workspace: str) -> ResearchState:
        state = ResearchState(
            run_id=str(uuid.uuid4()),
            workspace=str(workspace),
            stage=Stage.BRIEF,
            status=Status.IDLE,
            status_text="Введите задачу и начните планирование в чате",
        )
        self.save(state)
        return state

    def load(self) -> ResearchState | None:
        if not self.state_path.exists():
            return None
        data = json.loads(self.state_path.read_text(encoding="utf-8"))
        return ResearchState.model_validate(data)

    def save(self, state: ResearchState) -> None:
        state.touch()
        self.state_dir.mkdir(parents=True, exist_ok=True)
        tmp = self.state_path.with_suffix(".tmp")
        tmp.write_text(state.model_dump_json(indent=2), encoding="utf-8")
        tmp.replace(self.state_path)

    def append_log(self, entry: dict) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, default=str) + "\n")

    def update_log(self, call_id: str, entry: dict) -> None:
        """Replace a log line by id (used to flip running → completed/failed)."""
        if not call_id:
            self.append_log(entry)
            return
        self.state_dir.mkdir(parents=True, exist_ok=True)
        if not self.log_path.exists():
            self.append_log(entry)
            return
        lines = self.log_path.read_text(encoding="utf-8").splitlines()
        out: list[str] = []
        found = False
        for line in lines:
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                out.append(line)
                continue
            if row.get("id") == call_id:
                out.append(json.dumps(entry, default=str))
                found = True
            else:
                out.append(line)
        if not found:
            out.append(json.dumps(entry, default=str))
        tmp = self.log_path.with_suffix(".tmp")
        tmp.write_text("\n".join(out) + ("\n" if out else ""), encoding="utf-8")
        tmp.replace(self.log_path)

    def read_logs(self, limit: int = 80) -> list[dict]:
        if not self.log_path.exists():
            return []
        lines = self.log_path.read_text(encoding="utf-8").splitlines()
        entries = [json.loads(line) for line in lines if line.strip()]
        return entries[-limit:]

    def ensure_for_workspace(self, workspace: str) -> ResearchState:
        state = self.load()
        workspace = str(Path(workspace).resolve())
        if state is None:
            return self.new_run(workspace)
        if Path(state.workspace).resolve() != Path(workspace).resolve():
            state.recovery_message = (
                f"Сохранённый прогон был для {state.workspace}, "
                f"сейчас смонтирован {workspace}. Начинаем новый прогон."
            )
            return self.new_run(workspace)
        state.recovery_message = None
        return state


_store: StateStore | None = None


def get_store() -> StateStore:
    global _store
    if _store is None:
        _store = StateStore()
    return _store


def reset_store(state_dir: str | Path | None = None) -> StateStore:
    global _store
    _store = StateStore(state_dir=state_dir)
    return _store
