from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class LLMProvider(str, Enum):
    deepseek = "deepseek"
    openai = "openai"
    claude = "claude"


class Platform(str, Enum):
    linkedin = "linkedin"
    facebook = "facebook"
    tiktok = "tiktok"
    youtube = "youtube"
    google = "google"
    b2b_db = "b2b_db"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ProductProfile(BaseModel):
    product_name: str = ""
    industry_tags: list[str] = Field(default_factory=list)
    feature_tags: list[str] = Field(default_factory=list)
    use_cases: list[str] = Field(default_factory=list)
    target_roles: list[str] = Field(default_factory=list)
    price_range: str = ""
    exclude_tags: list[str] = Field(default_factory=list)
    llm_provider: LLMProvider = LLMProvider.openai


class ProductParseRequest(BaseModel):
    description: str
    llm_provider: LLMProvider = LLMProvider.openai


class IntRange(BaseModel):
    min: int | None = None
    max: int | None = None


class RevenueRange(BaseModel):
    min: float | None = None
    max: float | None = None
    currency: str = "USD"


class ICPDefinition(BaseModel):
    geography: list[str] = Field(default_factory=list)
    company_size: IntRange = Field(default_factory=IntRange)
    industry: list[str] = Field(default_factory=list)
    role_titles: list[str] = Field(default_factory=list)
    revenue_range: RevenueRange = Field(default_factory=RevenueRange)
    technology_stack: list[str] = Field(default_factory=list)


class SearchRequest(BaseModel):
    query: str
    icp: ICPDefinition
    platforms: list[Platform] = Field(
        default_factory=lambda: [
            Platform.linkedin,
            Platform.facebook,
            Platform.tiktok,
            Platform.youtube,
            Platform.google,
            Platform.b2b_db,
        ]
    )
    limit_per_platform: int = Field(default=5, ge=1, le=25)


class RawSearchResult(BaseModel):
    platform: Platform
    title: str
    snippet: str
    payload: dict = Field(default_factory=dict)


class LeadContact(BaseModel):
    name: str = ""
    role: str = ""
    email: str = ""
    linkedin: str = ""
    phone: str = ""


class LeadScores(BaseModel):
    industry: float = 0.0
    intent: float = 0.0
    contact: float = 0.0
    overall: float = 0.0


class LeadCandidate(BaseModel):
    lead_id: str
    company: str
    contact_name: str = ""
    role: str = ""
    platform: Platform
    raw_text_snippet: str
    email: str = ""
    linkedin: str = ""
    phone: str = ""
    domain: str = ""
    source_url: str = ""
    industry: list[str] = Field(default_factory=list)
    scores: LeadScores = Field(default_factory=LeadScores)


class LeadCard(BaseModel):
    lead_id: str
    company: str
    contacts: list[LeadContact] = Field(default_factory=list)
    product_fit_summary: str = ""
    scores: LeadScores = Field(default_factory=LeadScores)
    snippets: list[str] = Field(default_factory=list)
    source_platform: Platform


class ScoreWeights(BaseModel):
    industry: float = 0.4
    intent: float = 0.35
    contact: float = 0.25


class ScoreRequest(BaseModel):
    product_profile: ProductProfile
    icp: ICPDefinition
    leads: list[LeadCandidate]
    weights: ScoreWeights = Field(default_factory=ScoreWeights)


class ScoreResponse(BaseModel):
    leads: list[LeadCandidate]


class DeduplicateRequest(BaseModel):
    leads: list[LeadCandidate]


class DeduplicateResponse(BaseModel):
    leads: list[LeadCandidate]
    removed_duplicates: int


class TaskStatus(str, Enum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"


class TaskRecord(BaseModel):
    task_id: str
    platform: Platform
    query: str
    status: TaskStatus
    results_count: int = 0
    last_run: datetime = Field(default_factory=utc_now)


class StrategyDecision(BaseModel):
    continue_search: bool
    next_queries: list[str] = Field(default_factory=list)
    next_platforms: list[Platform] = Field(default_factory=list)
    reason: str = ""


class ClassificationResult(BaseModel):
    lead_id: str
    industry_labels: list[str] = Field(default_factory=list)
    intent_signals: list[str] = Field(default_factory=list)
    role_labels: list[str] = Field(default_factory=list)


class TemplateRequest(BaseModel):
    lead_card: LeadCard
    language: Literal["EN", "ES", "FR", "DE", "CN"] = "EN"


class TemplateSet(BaseModel):
    first_touch: str
    follow_up: str
    restart: str
    language: str


class OutreachEventType(str, Enum):
    sent = "sent"
    opened = "opened"
    clicked = "clicked"
    replied = "replied"


class OutreachEvent(BaseModel):
    event_id: str
    lead_id: str
    event_type: OutreachEventType
    timestamp: datetime = Field(default_factory=utc_now)


class OutreachStats(BaseModel):
    sent: int = 0
    opened: int = 0
    clicked: int = 0
    replied: int = 0


class Notification(BaseModel):
    notification_id: str
    category: str
    message: str
    created_at: datetime = Field(default_factory=utc_now)


class CRMExportTarget(str, Enum):
    csv = "csv"
    excel = "excel"
    hubspot = "hubspot"
    zoho = "zoho"
    salesforce = "salesforce"


class DashboardMetrics(BaseModel):
    new_leads: int
    high_score_ratio: float
    email_open_rate: float
    email_reply_rate: float
    platform_contribution: dict[str, int]


class Role(str, Enum):
    admin = "admin"
    sales_rep = "sales_rep"
    reviewer = "reviewer"
    data_engineer = "data_engineer"


class PermissionAction(str, Enum):
    read_data = "read_data"
    edit_data = "edit_data"
    approve = "approve"
    export = "export"


class PermissionCheckRequest(BaseModel):
    role: Role
    action: PermissionAction


class PermissionCheckResponse(BaseModel):
    allowed: bool


class ComplianceResult(BaseModel):
    lead_id: str
    contains_sensitive: bool
    sensitive_fields: list[str] = Field(default_factory=list)
    unsubscribe_detected: bool = False
    retention_days: int = 365


class AddProductRequest(BaseModel):
    product_profile: ProductProfile


class LeadsFetchRequest(BaseModel):
    query: str
    limit: int = Field(default=20, ge=1, le=200)
