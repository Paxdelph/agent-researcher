"""FastAPI application entrypoint."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.artifacts import editable_filenames, load_preview
from app.config import get_settings
from app.models import Status, UI_STEPS, Stage
from app.orchestration.engine import get_engine
from app.state import get_store

APP_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(APP_DIR / "templates"))

app = FastAPI(title="Agent Researcher", version="0.1.0")
app.mount("/static", StaticFiles(directory=str(APP_DIR / "static")), name="static")


def _progress_rows(stage: Stage) -> list[dict]:
    stage_order = [s for _, stages in UI_STEPS for s in stages]
    try:
        idx = stage_order.index(stage)
    except ValueError:
        idx = 0
    out = []
    cursor = 0
    for label, stages in UI_STEPS:
        end = cursor + len(stages) - 1
        if end < idx:
            st = "done"
        elif cursor <= idx <= end:
            st = "current"
        else:
            st = "todo"
        out.append({"label": label, "status": st})
        cursor += len(stages)
    return out


def _ctx(
    request: Request,
    *,
    artifact: str | None = None,
    edit_mode: bool = False,
    preview_saved: bool = False,
    render_message: str | None = None,
    render_ok: bool = False,
) -> dict:
    engine = get_engine()
    state = engine.get_state()
    settings = get_settings()
    artifact_id = artifact or request.query_params.get("artifact")
    loaded = load_preview(state, artifact_id)
    usage = state.usage
    openai_total = usage.openai_input_tokens + usage.openai_output_tokens
    anthropic_total = usage.anthropic_input_tokens + usage.anthropic_output_tokens
    report_path = Path(settings.workspace.path) / settings.research.report_file
    return {
        "request": request,
        "state": state,
        "workspace": settings.workspace.path,
        "progress": _progress_rows(state.stage),
        "preview": loaded["preview"],
        "tabs": loaded["tabs"],
        "artifact_id": loaded["artifact_id"],
        "running": state.status == Status.RUNNING,
        "edit_mode": edit_mode,
        "preview_saved": preview_saved,
        "can_render_report": report_path.is_file(),
        "render_message": render_message,
        "render_ok": render_ok,
        "token_limit": settings.limits.max_total_tokens,
        "tokens": {
            "openai": openai_total,
            "openai_in": usage.openai_input_tokens,
            "openai_out": usage.openai_output_tokens,
            "anthropic": anthropic_total,
            "anthropic_in": usage.anthropic_input_tokens,
            "anthropic_out": usage.anthropic_output_tokens,
            "total": usage.total_tokens,
            "limit": settings.limits.max_total_tokens,
            "pct": min(
                100,
                int(100 * usage.total_tokens / settings.limits.max_total_tokens)
                if settings.limits.max_total_tokens
                else 0,
            ),
        },
        "call_log": list(reversed(get_store().read_logs(60))),
    }


@app.get("/", response_class=HTMLResponse)
async def index(request: Request, artifact: str | None = None):
    return templates.TemplateResponse(request, "index.html", _ctx(request, artifact=artifact))


@app.get("/partials/app", response_class=HTMLResponse)
async def partial_app(request: Request, artifact: str | None = None):
    return templates.TemplateResponse(
        request, "partials/app_body.html", _ctx(request, artifact=artifact)
    )


@app.get("/partials/chat", response_class=HTMLResponse)
async def partial_chat(request: Request):
    return templates.TemplateResponse(request, "partials/chat.html", _ctx(request))


@app.get("/partials/preview", response_class=HTMLResponse)
async def partial_preview(
    request: Request,
    artifact: str | None = None,
    edit: int = 0,
):
    return templates.TemplateResponse(
        request,
        "partials/preview.html",
        _ctx(request, artifact=artifact, edit_mode=bool(edit)),
    )


@app.get("/partials/call_log", response_class=HTMLResponse)
async def partial_call_log(request: Request):
    return templates.TemplateResponse(request, "partials/call_log.html", _ctx(request))


@app.get("/partials/status", response_class=HTMLResponse)
async def partial_status(request: Request):
    return templates.TemplateResponse(request, "partials/status.html", _ctx(request))


@app.post("/brief")
async def save_brief(
    research_question: str = Form(""),
    business_context: str = Form(""),
):
    engine = get_engine()
    engine.save_brief(research_question, business_context)
    return RedirectResponse("/", status_code=303)


@app.post("/artifact", response_class=HTMLResponse)
async def save_artifact(
    request: Request,
    name: str = Form(...),
    content: str = Form(""),
    artifact: str = Form(""),
):
    engine = get_engine()
    artifact_id = artifact or None
    try:
        if name not in editable_filenames():
            raise ValueError(f"Артефакт нельзя править вручную: {name}")
        engine.save_artifact(name, content, artifact_id=artifact_id)
    except (RuntimeError, ValueError) as exc:
        ctx = _ctx(request, artifact=artifact_id or name, edit_mode=True)
        ctx["preview"]["error"] = str(exc)
        return templates.TemplateResponse(request, "partials/preview.html", ctx)
    response = templates.TemplateResponse(
        request,
        "partials/preview.html",
        _ctx(request, artifact=artifact_id or name, preview_saved=True),
    )
    response.headers["HX-Trigger"] = json.dumps({"refreshChat": True, "refreshStatus": True})
    return response


@app.post("/render-report", response_class=HTMLResponse)
async def render_report(request: Request, artifact: str = Form("")):
    """Local Quarto → HTML render without LLM."""
    import asyncio

    from app.orchestration.render import RenderError

    engine = get_engine()
    settings = get_settings()
    artifact_id = artifact or "report_html"
    if artifact_id not in {"report", "report_html"}:
        artifact_id = "report_html"

    try:
        await asyncio.to_thread(engine.render_report_local)
        ctx = _ctx(
            request,
            artifact=artifact_id,
            render_message=f"Готово: `{settings.research.report_html_file}` обновлён (без LLM).",
            render_ok=True,
        )
    except (RuntimeError, RenderError) as exc:
        ctx = _ctx(
            request,
            artifact=artifact_id if artifact_id != "report_html" else "report",
            render_message=str(exc),
            render_ok=False,
        )
    response = templates.TemplateResponse(request, "partials/preview.html", ctx)
    response.headers["HX-Trigger"] = json.dumps(
        {"refreshChat": True, "refreshStatus": True}
    )
    return response


@app.post("/chat", response_class=HTMLResponse)
async def post_chat(request: Request, message: str = Form("")):
    engine = get_engine()
    if message.strip():
        await engine.handle_chat(message)
    state = engine.get_state()
    response = templates.TemplateResponse(request, "partials/chat.html", _ctx(request))
    if state.status == Status.RUNNING:
        response.headers["HX-Trigger"] = json.dumps({"jobWatch": True})
    else:
        response.headers["HX-Trigger"] = json.dumps({"jobDone": True})
    return response


@app.get("/files/{file_path:path}")
async def workspace_file(file_path: str):
    """Serve a file from the research workspace (for HTML iframe preview)."""
    settings = get_settings()
    root = Path(settings.workspace.path).resolve()
    target = (root / file_path).resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Not found") from exc
    if not target.is_file():
        raise HTTPException(status_code=404, detail="Not found")
    return FileResponse(target)


@app.get("/health")
async def health():
    state = get_engine().get_state()
    return {
        "ok": True,
        "stage": state.stage.value,
        "status": state.status.value,
        "active_role": state.active_role,
        "status_text": state.status_text,
    }
