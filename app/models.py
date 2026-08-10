"""Pydantic models for config, LLM I/O, and research state."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Stage(str, Enum):
    BRIEF = "brief"
    PLANNING = "planning"
    PLAN_READY = "plan_ready"
    PLAN_APPROVED = "plan_approved"
    WAITING_FOR_DATA = "waiting_for_data"
    DATA_REVIEW = "data_review"
    PLAN_ADJUSTED = "plan_adjusted"
    DATA_READY = "data_ready"
    SKELETON = "skeleton"
    SKELETON_READY = "skeleton_ready"
    SKELETON_APPROVED = "skeleton_approved"
    CODING = "coding"
    CODING_READY = "coding_ready"
    CODING_APPROVED = "coding_approved"


class Status(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    WAITING_FOR_USER = "waiting_for_user"
    FAILED = "failed"
    STOPPED = "stopped"


UI_STEPS: list[tuple[str, list[Stage]]] = [
    ("Brief", [Stage.BRIEF]),
    ("Analysis plan", [Stage.PLANNING, Stage.PLAN_READY, Stage.PLAN_APPROVED]),
    ("Data", [Stage.WAITING_FOR_DATA, Stage.DATA_REVIEW, Stage.PLAN_ADJUSTED, Stage.DATA_READY]),
    ("Skeleton", [Stage.SKELETON, Stage.SKELETON_READY, Stage.SKELETON_APPROVED]),
    ("Report", [Stage.CODING, Stage.CODING_READY, Stage.CODING_APPROVED]),
]


class AgentConfig(BaseModel):
    enabled: bool = True
    provider: str
    model: str
    prompt: str
    skills: list[str] = Field(default_factory=list)
    max_output_tokens: int = 0  # 0 = без лимита (потолок провайдера)


class AppConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8787
    state_dir: str = "/workspace/.agent-researcher"
    store_full_prompts: bool = False


class WorkspaceConfig(BaseModel):
    path: str = "/workspace"
    data_dir: str = "data"
    # Shared across all researches for one analyst (company / product background).
    context_path: str = "/company/context.md"


class ArtifactDefConfig(BaseModel):
    id: str
    file: str
    label: str
    editable: bool = True


class ResearchFilesConfig(BaseModel):
    plan_file: str = "analysis-plan.md"
    data_review_file: str = "data-review.md"
    skeleton_file: str = "skeleton.md"
    report_file: str = "report.qmd"
    report_html_file: str = "report.html"
    design_review_file: str = "design-review.md"
    artifact_language: str = "ru"
    artifacts: list[ArtifactDefConfig] = Field(default_factory=list)


class LimitsConfig(BaseModel):
    # 0 = без лимита
    max_total_tokens: int = 0
    max_single_call_input_tokens: int = 0
    default_timeout_seconds: int = 300


class AppSettings(BaseModel):
    app: AppConfig = Field(default_factory=AppConfig)
    workspace: WorkspaceConfig = Field(default_factory=WorkspaceConfig)
    research: ResearchFilesConfig = Field(default_factory=ResearchFilesConfig)
    agents: dict[str, AgentConfig]
    limits: LimitsConfig = Field(default_factory=LimitsConfig)


class UsageTotals(BaseModel):
    openai_input_tokens: int = 0
    openai_output_tokens: int = 0
    anthropic_input_tokens: int = 0
    anthropic_output_tokens: int = 0
    total_tokens: int = 0

    def add(self, provider: str, input_tokens: int, output_tokens: int) -> None:
        provider = provider.lower()
        if provider == "openai":
            self.openai_input_tokens += input_tokens
            self.openai_output_tokens += output_tokens
        elif provider == "anthropic":
            self.anthropic_input_tokens += input_tokens
            self.anthropic_output_tokens += output_tokens
        self.total_tokens += input_tokens + output_tokens


class Artifacts(BaseModel):
    analysis_plan: str | None = None
    data_review: str | None = None
    skeleton: str | None = None
    report: str | None = None
    report_html: str | None = None
    design_review: str | None = None


class CallLogEntry(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    run_id: str
    created_at: datetime
    stage: Stage
    role: str
    provider: str
    model: str
    status: str  # running | completed | failed
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int = 0
    error: str | None = None
    summary: str | None = None
    prompt_preview: str | None = None
    response_preview: str | None = None


class ImagePart(BaseModel):
    media_type: str = "image/png"
    data_base64: str


class LLMRequest(BaseModel):
    role: str
    stage: Stage
    system: str
    user: str
    model: str
    max_output_tokens: int
    temperature: float = 0.2
    json_mode: bool = False
    images: list[ImagePart] = Field(default_factory=list)


class LLMResult(BaseModel):
    text: str
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    latency_ms: int


class ChatMessage(BaseModel):
    role: str  # user | assistant | system
    content: str
    created_at: datetime = Field(default_factory=utcnow)


class ChatAction(str, Enum):
    EDIT = "edit"
    ADVANCE = "advance"
    CLARIFY = "clarify"
    START_PLANNING = "start_planning"
    REVIEW_DATA = "review_data"
    BUILD_SKELETON = "build_skeleton"
    BUILD_REPORT = "build_report"


class ChatDecision(BaseModel):
    action: ChatAction
    reply: str
    artifact: str | None = None


class ResearchState(BaseModel):
    run_id: str
    workspace: str
    stage: Stage = Stage.BRIEF
    status: Status = Status.IDLE
    research_question: str = ""
    business_context: str = ""
    status_text: str = "Введите задачу и начните планирование в чате"
    active_role: str | None = None
    error: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
    artifacts: Artifacts = Field(default_factory=Artifacts)
    usage: UsageTotals = Field(default_factory=UsageTotals)
    chat: list[ChatMessage] = Field(default_factory=list)
    lead_draft: str | None = None
    analyst_critique: str | None = None
    skeleton_draft: str | None = None
    skeleton_critique: str | None = None
    data_verdict: str | None = None  # ok | adjusted | blocked
    design_verdict: str | None = None  # approve | revise
    design_notes: str | None = None
    recovery_message: str | None = None

    def touch(self) -> None:
        self.updated_at = utcnow()
