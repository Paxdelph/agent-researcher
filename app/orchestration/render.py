"""Quarto render and HTML screenshots for design review."""

from __future__ import annotations

import base64
import shutil
import subprocess
from pathlib import Path


class RenderError(RuntimeError):
    pass


def _which(names: list[str]) -> str | None:
    for name in names:
        path = shutil.which(name)
        if path:
            return path
    return None


def quarto_bin() -> str:
    found = _which(["quarto"])
    if not found:
        raise RenderError(
            "quarto не найден в PATH. Установите Quarto в образ/окружение."
        )
    return found


def chromium_bin() -> str | None:
    return _which(["chromium", "chromium-browser", "google-chrome", "chrome"])


def render_quarto(workspace: Path, qmd_file: str, html_file: str) -> Path:
    """Render report.qmd → report.html inside workspace.

    Always pass *relative* input/output names with cwd=workspace. Absolute
    paths make Quarto/knitr lose the source file mid-render («report.qmd:
    No such file or directory»).
    """
    from app.orchestration.quarto_ext import ensure_researcher_extension

    workspace = workspace.resolve()
    qmd = workspace / qmd_file
    if not qmd.is_file():
        raise RenderError(f"Нет файла для рендера: {qmd_file}")

    ensure_researcher_extension(workspace)

    out = workspace / html_file
    cmd = [
        quarto_bin(),
        "render",
        qmd_file,
        "--to",
        "researcher-html",
        "--output",
        html_file,
        "--execute",
    ]
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(workspace),
            capture_output=True,
            text=True,
            timeout=600,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise RenderError("Таймаут quarto render (600s)") from exc
    except FileNotFoundError as exc:
        raise RenderError(str(exc)) from exc

    if proc.returncode != 0 or not out.is_file():
        tail = (proc.stderr or proc.stdout or "").strip()[-4000:]
        raise RenderError(f"quarto render failed (code {proc.returncode}):\n{tail}")
    return out


def screenshot_html(
    html_path: Path,
    out_dir: Path,
    *,
    width: int = 1280,
    heights: tuple[int, ...] = (1600, 3200),
) -> list[Path]:
    """Capture one or more viewport screenshots of a local HTML file."""
    browser = chromium_bin()
    if not browser:
        return []

    out_dir.mkdir(parents=True, exist_ok=True)
    uri = html_path.resolve().as_uri()
    shots: list[Path] = []
    for i, height in enumerate(heights, start=1):
        target = out_dir / f"report-shot-{i}.png"
        cmd = [
            browser,
            "--headless=new",
            "--disable-gpu",
            "--no-sandbox",
            "--disable-dev-shm-usage",
            f"--window-size={width},{height}",
            f"--screenshot={target}",
            uri,
        ]
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
        except (subprocess.TimeoutExpired, FileNotFoundError):
            continue
        if proc.returncode == 0 and target.exists() and target.stat().st_size > 0:
            shots.append(target)
    return shots


def images_as_base64(paths: list[Path]) -> list[tuple[str, str]]:
    """Return list of (media_type, base64) for PNG screenshots."""
    out: list[tuple[str, str]] = []
    for path in paths:
        data = path.read_bytes()
        out.append(("image/png", base64.b64encode(data).decode("ascii")))
    return out


def html_excerpt(html_path: Path, limit: int = 12000) -> str:
    text = html_path.read_text(encoding="utf-8", errors="replace")
    if len(text) <= limit:
        return text
    return text[:limit] + "\n\n<!-- truncated -->\n"
