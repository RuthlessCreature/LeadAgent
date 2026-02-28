from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.models import (
    AddProductRequest,
    ClassificationResult,
    ComplianceResult,
    CRMExportTarget,
    DeduplicateRequest,
    DeduplicateResponse,
    ICPDefinition,
    LeadCandidate,
    LeadCard,
    LeadsFetchRequest,
    Notification,
    OutreachEvent,
    OutreachEventType,
    OutreachStats,
    PermissionCheckRequest,
    PermissionCheckResponse,
    Platform,
    ProductParseRequest,
    ProductProfile,
    ScoreRequest,
    ScoreResponse,
    SearchRequest,
    StrategyDecision,
    TaskRecord,
    TaskStatus,
    TemplateRequest,
    TemplateSet,
)
from app.services.classifier import classify_lead
from app.services.compliance import scan_lead_compliance
from app.services.dashboard import build_dashboard
from app.services.dedup import deduplicate_leads
from app.services.exporters import export_cards_csv, export_cards_pdf, simulate_crm_sync
from app.services.icp import normalize_icp
from app.services.lead_card import to_lead_card
from app.services.parser import parse_product_description
from app.services.permissions import has_permission
from app.services.scoring import score_leads
from app.services.search import build_platform_query, extract_leads, search_platform
from app.services.strategy import decide_next_actions
from app.services.templates import generate_templates
from app.store import store


class StrategyRequest(BaseModel):
    query: str
    lead_ids: list[str] = Field(default_factory=list)


class ClassificationRequest(BaseModel):
    lead_ids: list[str] = Field(default_factory=list)


class ComplianceScanRequest(BaseModel):
    lead_ids: list[str] = Field(default_factory=list)


def _find_leads(lead_ids: list[str] | None = None) -> list[LeadCandidate]:
    if not lead_ids:
        return list(store.leads)
    id_set = set(lead_ids)
    return [lead for lead in store.leads if lead.lead_id in id_set]


def _replace_store_leads(updated: list[LeadCandidate]) -> None:
    by_id = {lead.lead_id: lead for lead in updated}
    replaced: list[LeadCandidate] = []
    for current in store.leads:
        replaced.append(by_id.get(current.lead_id, current))
    existing_ids = {lead.lead_id for lead in replaced}
    for lead in updated:
        if lead.lead_id not in existing_ids:
            replaced.append(lead)
    store.leads = replaced


def _build_notification(category: str, message: str) -> Notification:
    notification = Notification(
        notification_id=str(uuid4()),
        category=category,
        message=message,
    )
    store.notifications.append(notification)
    return notification


app = FastAPI(
    title="Lead Agent Fullstack API",
    version="0.1.0",
    description="Prompt-driven lead generation backend with scoring, tasking, and outreach support.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "time": datetime.now(timezone.utc).isoformat()}


@app.post("/api/v1/input/parse-product", response_model=ProductProfile)
def parse_product(request: ProductParseRequest) -> ProductProfile:
    profile = parse_product_description(request.description)
    profile.llm_provider = request.llm_provider
    store.product_profiles.append(profile)
    return profile


@app.post("/api/v1/input/icp/normalize", response_model=ICPDefinition)
def normalize_icp_endpoint(icp: ICPDefinition) -> ICPDefinition:
    return normalize_icp(icp)


@app.post("/api/v1/search/run")
def run_search(request: SearchRequest) -> dict:
    all_raw = []
    task_by_platform: dict[Platform, TaskRecord] = {}
    for platform in request.platforms:
        query = build_platform_query(request.query, request.icp, platform)
        task = TaskRecord(
            task_id=str(uuid4()),
            platform=platform,
            query=query,
            status=TaskStatus.running,
            results_count=0,
        )
        store.upsert_task(task)
        task_by_platform[platform] = task

    def _run_platform(platform: Platform) -> tuple[Platform, list]:
        raw = search_platform(request.query, request.icp, platform, request.limit_per_platform)
        return platform, raw

    with ThreadPoolExecutor(max_workers=max(1, min(6, len(request.platforms)))) as executor:
        future_map = {executor.submit(_run_platform, platform): platform for platform in request.platforms}
        for future in as_completed(future_map):
            platform = future_map[future]
            task = task_by_platform[platform]
            try:
                _, raw = future.result()
                all_raw.extend(raw)
                task.status = TaskStatus.completed
                task.results_count = len(raw)
            except Exception:
                task.status = TaskStatus.failed
                task.results_count = 0
            task.last_run = datetime.now(timezone.utc)
            store.upsert_task(task)

    tasks = [task_by_platform[platform] for platform in request.platforms]

    leads = extract_leads(all_raw)
    store.add_leads(leads)

    return {
        "tasks": tasks,
        "results_count": len(leads),
        "leads": leads,
    }


@app.post("/api/v1/scoring/score", response_model=ScoreResponse)
def score(request: ScoreRequest) -> ScoreResponse:
    scored = score_leads(request.leads, request.product_profile, request.icp, request.weights)
    _replace_store_leads(scored)

    high_score = [lead for lead in scored if lead.scores.overall >= 80]
    if high_score:
        _build_notification("high_score_lead", f"{len(high_score)} high-score leads detected.")

    return ScoreResponse(leads=scored)


@app.post("/api/v1/leads/deduplicate", response_model=DeduplicateResponse)
def dedup(request: DeduplicateRequest) -> DeduplicateResponse:
    deduped, removed = deduplicate_leads(request.leads)
    store.leads = list(deduped)
    return DeduplicateResponse(leads=deduped, removed_duplicates=removed)


@app.get("/api/v1/leads", response_model=list[LeadCandidate])
def list_leads(
    min_score: float = Query(default=0.0, ge=0.0, le=100.0),
    limit: int = Query(default=100, ge=1, le=500),
) -> list[LeadCandidate]:
    filtered = [lead for lead in store.leads if lead.scores.overall >= min_score]
    filtered.sort(key=lambda lead: lead.scores.overall, reverse=True)
    return filtered[:limit]


@app.get("/api/v1/leads/{lead_id}/card", response_model=LeadCard)
def get_lead_card(lead_id: str) -> LeadCard:
    lead = next((item for item in store.leads if item.lead_id == lead_id), None)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    latest_profile = store.product_profiles[-1] if store.product_profiles else None
    return to_lead_card(lead, latest_profile)


@app.get("/api/v1/leads/export")
def export_leads(format: str = Query(default="csv")) -> Response:
    cards = [to_lead_card(lead, store.product_profiles[-1] if store.product_profiles else None) for lead in store.leads]
    if format == "csv":
        data = export_cards_csv(cards)
        return Response(
            content=data,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=lead_cards.csv"},
        )
    if format == "pdf":
        data = export_cards_pdf(cards)
        return Response(
            content=data,
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=lead_cards.pdf"},
        )
    raise HTTPException(status_code=400, detail="Unsupported export format")


@app.get("/api/v1/tasks", response_model=list[TaskRecord])
def list_tasks() -> list[TaskRecord]:
    return sorted(store.tasks, key=lambda row: row.last_run, reverse=True)


@app.post("/api/v1/strategy/next", response_model=StrategyDecision)
def strategy(request: StrategyRequest) -> StrategyDecision:
    leads = _find_leads(request.lead_ids)
    return decide_next_actions(request.query, leads)


@app.post("/api/v1/classify", response_model=list[ClassificationResult])
def classify(request: ClassificationRequest) -> list[ClassificationResult]:
    leads = _find_leads(request.lead_ids)
    return [classify_lead(lead) for lead in leads]


@app.post("/api/v1/outreach/templates", response_model=TemplateSet)
def templates(request: TemplateRequest) -> TemplateSet:
    return generate_templates(request.lead_card, request.language)


@app.post("/api/v1/outreach/events", response_model=OutreachEvent)
def outreach_event(event: OutreachEvent) -> OutreachEvent:
    store.outreach_events.append(event)
    if event.event_type == OutreachEventType.opened:
        _build_notification("email_opened", f"Lead {event.lead_id} opened an email.")
    if event.event_type == OutreachEventType.replied:
        _build_notification("reply_received", f"Lead {event.lead_id} replied to outreach.")
    return event


@app.get("/api/v1/outreach/stats", response_model=OutreachStats)
def outreach_stats() -> OutreachStats:
    counter = Counter(event.event_type for event in store.outreach_events)
    return OutreachStats(
        sent=counter.get(OutreachEventType.sent, 0),
        opened=counter.get(OutreachEventType.opened, 0),
        clicked=counter.get(OutreachEventType.clicked, 0),
        replied=counter.get(OutreachEventType.replied, 0),
    )


@app.get("/api/v1/notifications", response_model=list[Notification])
def list_notifications(limit: int = Query(default=100, ge=1, le=500)) -> list[Notification]:
    return sorted(store.notifications, key=lambda row: row.created_at, reverse=True)[:limit]


@app.get("/api/v1/dashboard")
def dashboard() -> JSONResponse:
    metrics = build_dashboard(store.leads, store.outreach_events)
    return JSONResponse(content=metrics.model_dump())


@app.post("/api/v1/crm/export")
def crm_export(target: CRMExportTarget = Query(default=CRMExportTarget.csv)) -> dict:
    cards = [to_lead_card(lead, store.product_profiles[-1] if store.product_profiles else None) for lead in store.leads]
    if target in {CRMExportTarget.csv, CRMExportTarget.excel}:
        return {"target": target.value, "message": "Use /api/v1/leads/export for file downloads."}
    return simulate_crm_sync(target.value, cards)


@app.post("/api/v1/permissions/check", response_model=PermissionCheckResponse)
def permission_check(request: PermissionCheckRequest) -> PermissionCheckResponse:
    return PermissionCheckResponse(allowed=has_permission(request.role, request.action))


@app.post("/api/v1/compliance/scan", response_model=list[ComplianceResult])
def compliance_scan(request: ComplianceScanRequest) -> list[ComplianceResult]:
    leads = _find_leads(request.lead_ids)
    return [scan_lead_compliance(lead) for lead in leads]


@app.post("/api/v1/ext/add-product")
def ext_add_product(request: AddProductRequest) -> dict:
    store.product_profiles.append(request.product_profile)
    return {"status": "ok", "profiles": len(store.product_profiles)}


@app.post("/api/v1/ext/request-leads", response_model=list[LeadCandidate])
def ext_request_leads(request: LeadsFetchRequest) -> list[LeadCandidate]:
    query_tokens = request.query.lower().split()
    matched = [
        lead
        for lead in store.leads
        if any(token in lead.raw_text_snippet.lower() or token in lead.company.lower() for token in query_tokens)
    ]
    matched.sort(key=lambda row: row.scores.overall, reverse=True)
    return matched[: request.limit]


@app.get("/api/v1/ext/dashboard-data")
def ext_dashboard_data() -> JSONResponse:
    return dashboard()


BASE_DIR = Path(__file__).resolve().parents[2]
FRONTEND_DIR = BASE_DIR / "frontend"

if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/api/v1/demo/reset")
def demo_reset() -> dict:
    store.product_profiles.clear()
    store.tasks.clear()
    store.leads.clear()
    store.outreach_events.clear()
    store.notifications.clear()
    return {"status": "ok"}
