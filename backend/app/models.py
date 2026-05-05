from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field

from app import db


# -----------------------------
# FastAPI/Pydantic schema layer
# -----------------------------


class Platform(str, Enum):
    public_web = "public_web"
    linkedin = "linkedin"
    google = "google"
    b2b_db = "b2b_db"
    facebook = "facebook"
    youtube = "youtube"
    tiktok = "tiktok"
    instagram = "instagram"


class LeadSourceType(str, Enum):
    demo = "demo"
    public_web = "public_web"
    first_party_social = "first_party_social"
    licensed_database = "licensed_database"
    first_party = "first_party"
    customer_import = "customer_import"
    partner_referral = "partner_referral"


class ConsentStatus(str, Enum):
    unknown = "unknown"
    legitimate_interest = "legitimate_interest"
    consented = "consented"
    not_applicable = "not_applicable"
    do_not_contact = "do_not_contact"


class VerificationStatus(str, Enum):
    unverified = "unverified"
    company_verified = "company_verified"
    email_verified = "email_verified"
    phone_verified = "phone_verified"
    fully_verified = "fully_verified"


class TaskStatus(str, Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class OutreachEventType(str, Enum):
    sent = "sent"
    opened = "opened"
    clicked = "clicked"
    replied = "replied"


class CRMExportTarget(str, Enum):
    csv = "csv"
    excel = "excel"
    hubspot = "hubspot"
    salesforce = "salesforce"


class SocialConnectionStatus(str, Enum):
    connected = "connected"
    attention_required = "attention_required"
    disconnected = "disconnected"


class SocialSyncMode(str, Enum):
    webhook = "webhook"
    pull = "pull"
    hybrid = "hybrid"


class SocialConnectorKey(str, Enum):
    linkedin_lead_sync = "linkedin_lead_sync"
    meta_lead_ads = "meta_lead_ads"


class SocialAssetType(str, Enum):
    organization = "organization"
    page = "page"
    ad_account = "ad_account"
    form = "form"
    campaign = "campaign"
    business_account = "business_account"
    event = "event"
    product_page = "product_page"


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


class CompanySizeRange(BaseModel):
    min: int = 0
    max: int = 1_000_000


class RevenueRange(BaseModel):
    min: float = 0.0
    max: float = 1_000_000_000_000.0
    currency: str = "USD"


class ProductParseRequest(BaseModel):
    description: str
    llm_provider: str = "mock"


class ProductProfile(BaseModel):
    product_name: str
    industry_tags: list[str] = Field(default_factory=list)
    feature_tags: list[str] = Field(default_factory=list)
    use_cases: list[str] = Field(default_factory=list)
    target_roles: list[str] = Field(default_factory=list)
    price_range: str = "unknown"
    exclude_tags: list[str] = Field(default_factory=list)
    llm_provider: str = "mock"


class ICPDefinition(BaseModel):
    geography: list[str] = Field(default_factory=list)
    company_size: CompanySizeRange = Field(default_factory=CompanySizeRange)
    industry: list[str] = Field(default_factory=list)
    role_titles: list[str] = Field(default_factory=list)
    revenue_range: RevenueRange = Field(default_factory=RevenueRange)
    technology_stack: list[str] = Field(default_factory=list)


class SearchRequest(BaseModel):
    query: str
    icp: ICPDefinition
    platforms: list[Platform] = Field(default_factory=lambda: [Platform.linkedin])
    limit_per_platform: int = Field(default=5, ge=1, le=50)


class LeadScores(BaseModel):
    industry: float = 0.0
    intent: float = 0.0
    contact: float = 0.0
    overall: float = 0.0


class LeadCandidate(BaseModel):
    lead_id: str
    platform: Platform
    company: str
    contact_name: str = ""
    role: str = ""
    email: str = ""
    phone: str = ""
    linkedin: str = ""
    domain: str = ""
    industry: list[str] = Field(default_factory=list)
    raw_text_snippet: str = ""
    source_type: LeadSourceType = LeadSourceType.demo
    source_label: str = ""
    source_url: str = ""
    source_external_lead_id: str = ""
    source_asset_owner_type: str = ""
    source_asset_owner_id: str = ""
    source_form_id: str = ""
    source_campaign_id: str = ""
    source_ad_account_id: str = ""
    source_page_id: str = ""
    source_privacy_policy_url: str = ""
    source_consent_text: str = ""
    source_submission_timestamp: datetime | None = None
    source_payload_version: str = ""
    source_raw_payload_hash: str = ""
    deletion_requested_at: datetime | None = None
    retention_expires_at: datetime | None = None
    consent_status: ConsentStatus = ConsentStatus.unknown
    verification_status: VerificationStatus = VerificationStatus.unverified
    scores: LeadScores = Field(default_factory=LeadScores)


class ScoreWeights(BaseModel):
    industry: float = 0.4
    intent: float = 0.35
    contact: float = 0.25


class ScoreRequest(BaseModel):
    leads: list[LeadCandidate] = Field(default_factory=list)
    product_profile: ProductProfile
    icp: ICPDefinition
    weights: ScoreWeights = Field(default_factory=ScoreWeights)


class ScoreResponse(BaseModel):
    leads: list[LeadCandidate] = Field(default_factory=list)


class PublicWebCrawlRequest(BaseModel):
    seed_urls: list[str] = Field(default_factory=list)
    max_pages_per_domain: int = Field(default=4, ge=1, le=20)
    respect_robots: bool = True
    product_profile: ProductProfile | None = None
    icp: ICPDefinition | None = None
    weights: ScoreWeights = Field(default_factory=ScoreWeights)


class PublicWebCrawlResponse(BaseModel):
    imported: int = 0
    skipped_duplicates: int = 0
    visited_urls: list[str] = Field(default_factory=list)
    blocked_urls: list[str] = Field(default_factory=list)
    leads: list[LeadCandidate] = Field(default_factory=list)


class DiscoveredUrl(BaseModel):
    query: str
    title: str
    url: str
    snippet: str = ""
    domain: str = ""


class PublicWebDiscoverRequest(BaseModel):
    queries: list[str] = Field(default_factory=list)
    limit_per_query: int = Field(default=10, ge=1, le=50)
    exclude_social: bool = True
    engines: list[str] = Field(default_factory=list)
    query_preset: str = ""
    languages: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)
    query_terms: list[str] = Field(default_factory=list)
    translated_terms: dict[str, list[str]] = Field(default_factory=dict)
    include_global_queries: bool = True
    use_location_aliases: bool = True
    location_aliases: dict[str, list[str]] = Field(default_factory=dict)
    max_expanded_queries: int = Field(default=1500, ge=1, le=5000)


class PublicWebDiscoverResponse(BaseModel):
    results: list[DiscoveredUrl] = Field(default_factory=list)
    discovered_urls: list[str] = Field(default_factory=list)
    executed_queries: list[str] = Field(default_factory=list)


class BuyerHypothesis(BaseModel):
    hypothesis_id: str
    buyer_type: str
    buyer_roles: list[str] = Field(default_factory=list)
    company_types: list[str] = Field(default_factory=list)
    geographies: list[str] = Field(default_factory=list)
    search_language: list[str] = Field(default_factory=list)
    source_plan: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    rationale: str = ""


class PersonEvidence(BaseModel):
    evidence_id: str
    lead_id: str
    source_url: str
    source_platform: str
    evidence_type: str
    observed_name: str = ""
    observed_role: str = ""
    observed_company: str = ""
    observed_contact: str = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    collected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CustomerDiscoveryPlanRequest(BaseModel):
    product_description: str
    geographies: list[str] = Field(default_factory=list)
    sales_motion: str = ""
    allowed_sources: list[str] = Field(default_factory=lambda: ["public_web", "first_party_social", "licensed_database"])


class CustomerDiscoveryPlanResponse(BaseModel):
    product_name: str
    buyer_hypotheses: list[BuyerHypothesis] = Field(default_factory=list)
    recommended_next_step: str = ""


class SourcingPlanRequest(BaseModel):
    product_description: str
    target_platforms: list[str] = Field(default_factory=lambda: ["1688"])
    supplier_regions: list[str] = Field(default_factory=list)
    price_min: float | None = None
    price_max: float | None = None
    moq: str = ""
    certifications: list[str] = Field(default_factory=list)
    report_language: str = "EN"


class SourcingQuery(BaseModel):
    platform: str
    query: str
    language: str = "en"
    intent: str = "product_search"


class SourcingPlan(BaseModel):
    plan_id: str
    product_name: str
    product_summary: str = ""
    target_platforms: list[str] = Field(default_factory=list)
    supplier_regions: list[str] = Field(default_factory=list)
    query_terms: list[str] = Field(default_factory=list)
    queries: list[SourcingQuery] = Field(default_factory=list)
    constraints: dict[str, str] = Field(default_factory=dict)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    notes: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SupplierCandidate(BaseModel):
    supplier_id: str
    platform: str
    supplier_name: str
    supplier_url: str
    location: str = ""
    years_active: int | None = None
    verification_badges: list[str] = Field(default_factory=list)
    response_rate: str = ""
    transaction_signals: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    score: float = Field(default=0.0, ge=0.0, le=100.0)


class ProductOffer(BaseModel):
    offer_id: str
    supplier_id: str
    platform: str
    title: str
    product_url: str
    image_url: str = ""
    price_min: float | None = None
    price_max: float | None = None
    currency: str = "CNY"
    moq: str = ""
    attributes: dict[str, str] = Field(default_factory=dict)
    source_evidence: list[str] = Field(default_factory=list)
    score: float = Field(default=0.0, ge=0.0, le=100.0)


class SourcingSearchRequest(BaseModel):
    plan: SourcingPlan
    limit_per_platform: int = Field(default=8, ge=1, le=50)


class SourcingSearchResponse(BaseModel):
    plan: SourcingPlan
    offers: list[ProductOffer] = Field(default_factory=list)
    suppliers: list[SupplierCandidate] = Field(default_factory=list)
    searched_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SourcingReportRequest(BaseModel):
    product_name: str = ""
    offers: list[ProductOffer] = Field(default_factory=list)
    suppliers: list[SupplierCandidate] = Field(default_factory=list)
    report_language: str = "EN"


class SourcingReport(BaseModel):
    report_id: str
    product_name: str
    query_terms: list[str] = Field(default_factory=list)
    offers: list[ProductOffer] = Field(default_factory=list)
    suppliers: list[SupplierCandidate] = Field(default_factory=list)
    summary: str = ""
    recommendations: list[str] = Field(default_factory=list)
    report_markdown: str = ""
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class LLMModelCatalog(BaseModel):
    provider: str
    model: str
    has_api_key: bool = False
    deepseek_defaults: dict[str, str] = Field(default_factory=dict)


class DeduplicateRequest(BaseModel):
    leads: list[LeadCandidate] = Field(default_factory=list)


class DeduplicateResponse(BaseModel):
    leads: list[LeadCandidate] = Field(default_factory=list)
    removed_duplicates: int = 0


class LeadContact(BaseModel):
    name: str = ""
    role: str = ""
    email: str = ""
    linkedin: str = ""
    phone: str = ""


class LeadCard(BaseModel):
    lead_id: str
    company: str
    contacts: list[LeadContact] = Field(default_factory=list)
    product_fit_summary: str = ""
    scores: LeadScores = Field(default_factory=LeadScores)
    snippets: list[str] = Field(default_factory=list)
    source_platform: Platform = Platform.linkedin
    source_summary: str = ""
    consent_status: ConsentStatus = ConsentStatus.unknown
    verification_status: VerificationStatus = VerificationStatus.unverified


class TemplateRequest(BaseModel):
    lead_card: LeadCard
    language: str = "EN"


class TemplateSet(BaseModel):
    first_touch: str
    follow_up: str
    restart: str
    language: str = "EN"


class TaskRecord(BaseModel):
    task_id: str
    platform: Platform
    query: str
    status: TaskStatus = TaskStatus.pending
    results_count: int = 0
    last_run: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


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


class OutreachEvent(BaseModel):
    event_id: str = ""
    lead_id: str
    event_type: OutreachEventType
    message_id: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class OutreachStats(BaseModel):
    sent: int = 0
    opened: int = 0
    clicked: int = 0
    replied: int = 0


class Notification(BaseModel):
    notification_id: str
    category: str
    message: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DashboardMetrics(BaseModel):
    new_leads: int = 0
    high_score_ratio: float = 0.0
    email_open_rate: float = 0.0
    email_reply_rate: float = 0.0
    platform_contribution: dict[str, int] = Field(default_factory=dict)
    source_contribution: dict[str, int] = Field(default_factory=dict)
    compliant_leads: int = 0


class PermissionCheckRequest(BaseModel):
    role: Role
    action: PermissionAction


class PermissionCheckResponse(BaseModel):
    allowed: bool


class ComplianceResult(BaseModel):
    lead_id: str
    contains_sensitive: bool = False
    sensitive_fields: list[str] = Field(default_factory=list)
    unsubscribe_detected: bool = False
    retention_days: int = 365
    source_risk_level: str = "low"
    recommended_action: str = ""


class LeadsFetchRequest(BaseModel):
    query: str
    limit: int = Field(default=20, ge=1, le=200)


class AddProductRequest(BaseModel):
    product_profile: ProductProfile


class LeadImportItem(BaseModel):
    company: str
    platform: Platform = Platform.b2b_db
    contact_name: str = ""
    role: str = ""
    email: str = ""
    phone: str = ""
    linkedin: str = ""
    domain: str = ""
    industry: list[str] = Field(default_factory=list)
    raw_text_snippet: str = ""
    source_type: LeadSourceType = LeadSourceType.customer_import
    source_label: str = "Customer-owned import"
    source_url: str = ""
    source_external_lead_id: str = ""
    source_asset_owner_type: str = ""
    source_asset_owner_id: str = ""
    source_form_id: str = ""
    source_campaign_id: str = ""
    source_ad_account_id: str = ""
    source_page_id: str = ""
    source_privacy_policy_url: str = ""
    source_consent_text: str = ""
    source_submission_timestamp: datetime | None = None
    source_payload_version: str = ""
    source_raw_payload_hash: str = ""
    deletion_requested_at: datetime | None = None
    retention_expires_at: datetime | None = None
    consent_status: ConsentStatus = ConsentStatus.consented
    verification_status: VerificationStatus = VerificationStatus.company_verified


class LeadImportRequest(BaseModel):
    leads: list[LeadImportItem] = Field(default_factory=list)
    deduplicate: bool = True


class LeadImportResponse(BaseModel):
    imported: int = 0
    skipped_duplicates: int = 0
    leads: list[LeadCandidate] = Field(default_factory=list)


class SocialAsset(BaseModel):
    asset_id: str
    asset_type: SocialAssetType
    name: str
    selected: bool = True


class SocialConnection(BaseModel):
    connection_id: str
    connector_key: SocialConnectorKey
    platform: Platform
    display_name: str
    status: SocialConnectionStatus = SocialConnectionStatus.connected
    auth_type: str = "oauth"
    owner_email: str = ""
    sync_mode: SocialSyncMode = SocialSyncMode.hybrid
    scopes: list[str] = Field(default_factory=list)
    selected_assets: list[SocialAsset] = Field(default_factory=list)
    last_synced_at: datetime | None = None
    last_error: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SocialConnectionCreateRequest(BaseModel):
    connector_key: SocialConnectorKey | None = None
    platform: Platform
    display_name: str
    auth_type: str = "oauth"
    owner_email: str = ""
    sync_mode: SocialSyncMode = SocialSyncMode.hybrid
    scopes: list[str] = Field(default_factory=list)
    selected_assets: list[SocialAsset] = Field(default_factory=list)


class SocialSyncLeadItem(BaseModel):
    company: str
    platform: Platform
    contact_name: str = ""
    role: str = ""
    email: str = ""
    phone: str = ""
    linkedin: str = ""
    domain: str = ""
    industry: list[str] = Field(default_factory=list)
    raw_text_snippet: str = ""
    source_type: LeadSourceType = LeadSourceType.first_party_social
    source_label: str = "Owned social lead sync"
    source_url: str = ""
    source_external_lead_id: str = ""
    source_asset_owner_type: str = ""
    source_asset_owner_id: str = ""
    source_form_id: str = ""
    source_campaign_id: str = ""
    source_ad_account_id: str = ""
    source_page_id: str = ""
    source_privacy_policy_url: str = ""
    source_consent_text: str = ""
    source_submission_timestamp: datetime | None = None
    source_payload_version: str = "v1"
    source_raw_payload_hash: str = ""
    deletion_requested_at: datetime | None = None
    retention_expires_at: datetime | None = None
    consent_status: ConsentStatus = ConsentStatus.consented
    verification_status: VerificationStatus = VerificationStatus.company_verified


class SocialConnectionSyncRequest(BaseModel):
    leads: list[SocialSyncLeadItem] = Field(default_factory=list)
    status: SocialConnectionStatus = SocialConnectionStatus.connected
    error_message: str = ""


class SocialSyncRun(BaseModel):
    run_id: str
    connection_id: str
    platform: Platform
    imported: int = 0
    skipped_duplicates: int = 0
    submitted_leads: int = 0
    asset_count: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SocialConnectionSyncResponse(BaseModel):
    connection: SocialConnection
    sync_run: SocialSyncRun
    imported: int = 0
    skipped_duplicates: int = 0
    leads: list[LeadCandidate] = Field(default_factory=list)


class SocialOverview(BaseModel):
    connections: int = 0
    connected_connections: int = 0
    synced_connections: int = 0
    total_synced_leads: int = 0
    platform_breakdown: dict[str, int] = Field(default_factory=dict)
    source_breakdown: dict[str, int] = Field(default_factory=dict)
    last_sync_at: datetime | None = None


class SocialConnectorField(BaseModel):
    key: str
    label: str
    required: bool = False
    description: str = ""


class SocialConnectorDefinition(BaseModel):
    connector_key: SocialConnectorKey
    platform: Platform
    display_name: str
    official_only: bool = True
    auth_type: str = "oauth2"
    required_scopes: list[str] = Field(default_factory=list)
    supported_sync_modes: list[SocialSyncMode] = Field(default_factory=list)
    supported_asset_types: list[SocialAssetType] = Field(default_factory=list)
    supported_source_type: LeadSourceType = LeadSourceType.first_party_social
    webhook_supported: bool = True
    backfill_supported: bool = True
    audience_sync_supported: bool = False
    onboarding_steps: list[str] = Field(default_factory=list)
    expected_lead_fields: list[SocialConnectorField] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


# -----------------------------
# Flask/SQLAlchemy model layer
# -----------------------------


class Lead(db.Model):
    __tablename__ = "leads"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200))
    company = db.Column(db.String(200))
    job_title = db.Column(db.String(200))

    email = db.Column(db.String(200))
    phone = db.Column(db.String(50))
    wechat = db.Column(db.String(100))
    whatsapp = db.Column(db.String(50))

    url = db.Column(db.String(500))
    platform = db.Column(db.String(50))

    tags = db.Column(db.Text)
    notes = db.Column(db.Text)

    score = db.Column(db.Integer, default=0)
    is_target = db.Column(db.Boolean, default=None)

    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "company": self.company,
            "job_title": self.job_title,
            "email": self.email,
            "phone": self.phone,
            "wechat": self.wechat,
            "whatsapp": self.whatsapp,
            "url": self.url,
            "platform": self.platform,
            "tags": self.tags,
            "notes": self.notes,
            "score": self.score,
            "is_target": self.is_target,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class Config(db.Model):
    __tablename__ = "config"

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(db.Text)

    @staticmethod
    def get(key, default=None):
        cfg = Config.query.filter_by(key=key).first()
        return cfg.value if cfg else default

    @staticmethod
    def set(key, value):
        cfg = Config.query.filter_by(key=key).first()
        if cfg:
            cfg.value = value
        else:
            cfg = Config(key=key, value=value)
            db.session.add(cfg)
        db.session.commit()


class SearchTask(db.Model):
    __tablename__ = "search_tasks"

    id = db.Column(db.Integer, primary_key=True)
    keyword = db.Column(db.String(500))
    product_desc = db.Column(db.Text)
    status = db.Column(db.String(20), default="pending")
    total_results = db.Column(db.Integer, default=0)
    found_results = db.Column(db.Integer, default=0)

    created_at = db.Column(db.DateTime, default=datetime.now)
    completed_at = db.Column(db.DateTime)

    def to_dict(self):
        return {
            "id": self.id,
            "keyword": self.keyword,
            "product_desc": self.product_desc,
            "status": self.status,
            "total_results": self.total_results,
            "found_results": self.found_results,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }
