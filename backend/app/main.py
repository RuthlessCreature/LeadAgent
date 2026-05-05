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
    ConsentStatus,
    CustomerDiscoveryPlanRequest,
    CustomerDiscoveryPlanResponse,
    CRMExportTarget,
    DeduplicateRequest,
    DeduplicateResponse,
    ICPDefinition,
    LeadImportRequest,
    LeadImportResponse,
    LeadCandidate,
    LeadCard,
    LeadSourceType,
    LeadsFetchRequest,
    LLMModelCatalog,
    Notification,
    OutreachEvent,
    OutreachEventType,
    OutreachStats,
    PermissionCheckRequest,
    PermissionCheckResponse,
    Platform,
    ProductParseRequest,
    ProductProfile,
    SocialConnection,
    SocialConnectionCreateRequest,
    SocialConnectorDefinition,
    SocialConnectorKey,
    SocialConnectionStatus,
    SocialConnectionSyncRequest,
    SocialConnectionSyncResponse,
    SocialOverview,
    SocialSyncRun,
    SourcingPlan,
    SourcingPlanRequest,
    SourcingReport,
    SourcingReportRequest,
    SourcingSearchRequest,
    SourcingSearchResponse,
    PublicWebCrawlRequest,
    PublicWebCrawlResponse,
    PublicWebDiscoverRequest,
    PublicWebDiscoverResponse,
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
from app.services.customer_discovery import build_customer_discovery_plan
from app.services.dashboard import build_dashboard
from app.services.dedup import deduplicate_leads
from app.services.discovery import discover_public_urls
from app.services.exporters import export_cards_csv, export_cards_pdf, simulate_crm_sync
from app.services.icp import normalize_icp
from app.services.lead_card import to_lead_card
from app.services.llm import LLMClient
from app.services.parser import parse_product_description
from app.services.permissions import has_permission
from app.services.public_web import crawl_public_web
from app.services.query_expansion import expand_public_web_queries
from app.services.scoring import score_leads
from app.services.search import build_platform_query, extract_leads, search_platform
from app.services.social_connectors import (
    default_connector_key_for_platform,
    get_social_connector,
    list_social_connectors,
    validate_connector_platform,
)
from app.services.sourcing import build_sourcing_plan, generate_sourcing_report, search_sourcing_plan
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


class LLMTestRequest(BaseModel):
    provider: str = "deepseek"
    api_key: str = ""
    model: str = ""


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
    store.set_leads(replaced)


def _append_unique_leads(new_leads: list[LeadCandidate], deduplicate: bool = True) -> tuple[list[LeadCandidate], int]:
    if not deduplicate:
        store.add_leads(new_leads)
        return new_leads, 0

    existing_ids = {lead.lead_id for lead in store.leads}
    unique: list[LeadCandidate] = []
    skipped_duplicates = 0
    for lead in new_leads:
        if lead.lead_id in existing_ids:
            skipped_duplicates += 1
            continue
        existing_ids.add(lead.lead_id)
        unique.append(lead)
    store.add_leads(unique)
    return unique, skipped_duplicates


def _build_notification(category: str, message: str) -> Notification:
    notification = Notification(
        notification_id=str(uuid4()),
        category=category,
        message=message,
    )
    store.add_notification(notification)
    return notification


def _find_social_connection(connection_id: str) -> SocialConnection:
    connection = next((item for item in store.social_connections if item.connection_id == connection_id), None)
    if connection is None:
        raise HTTPException(status_code=404, detail="Social connection not found")
    return connection


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


@app.get("/api/v1/llm/models", response_model=LLMModelCatalog)
def llm_models() -> LLMModelCatalog:
    client = LLMClient()
    metadata = client.metadata()
    return LLMModelCatalog(
        provider=metadata["provider"],
        model=metadata["model"],
        has_api_key=metadata["has_api_key"],
        deepseek_defaults=metadata["deepseek_defaults"],
    )


@app.post("/api/v1/llm/test")
def llm_test(request: LLMTestRequest) -> dict:
    api_key = request.api_key.strip() or None
    model = request.model.strip() or None
    try:
        client = LLMClient(provider=request.provider, api_key=api_key, model=model)
        result = client.chat(
            [{"role": "user", "content": "Reply with exactly OK."}],
            temperature=0,
            max_tokens=16,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"status": "ok", "provider": client.provider, "model": client.model, "result": result}


@app.post("/api/v1/input/parse-product", response_model=ProductProfile)
def parse_product(request: ProductParseRequest) -> ProductProfile:
    profile = parse_product_description(request.description)
    profile.llm_provider = request.llm_provider
    store.add_product_profile(profile)
    return profile


@app.post("/api/v1/input/icp/normalize", response_model=ICPDefinition)
def normalize_icp_endpoint(icp: ICPDefinition) -> ICPDefinition:
    return normalize_icp(icp)


@app.post("/api/v1/customer-discovery/plan", response_model=CustomerDiscoveryPlanResponse)
def customer_discovery_plan(request: CustomerDiscoveryPlanRequest) -> CustomerDiscoveryPlanResponse:
    return build_customer_discovery_plan(request)


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
    store.set_leads(list(deduped))
    return DeduplicateResponse(leads=deduped, removed_duplicates=removed)


@app.get("/api/v1/leads", response_model=list[LeadCandidate])
def list_leads(
    min_score: float = Query(default=0.0, ge=0.0, le=100.0),
    limit: int = Query(default=100, ge=1, le=500),
    platform: Platform | None = Query(default=None),
    source_type: LeadSourceType | None = Query(default=None),
) -> list[LeadCandidate]:
    filtered = [lead for lead in store.leads if lead.scores.overall >= min_score]
    if platform is not None:
        filtered = [lead for lead in filtered if lead.platform == platform]
    if source_type is not None:
        filtered = [lead for lead in filtered if lead.source_type == source_type]
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
    store.add_outreach_event(event)
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


@app.post("/api/v1/public-web/discover", response_model=PublicWebDiscoverResponse)
def public_web_discover(request: PublicWebDiscoverRequest) -> PublicWebDiscoverResponse:
    executed_queries = expand_public_web_queries(
        queries=request.queries,
        query_preset=request.query_preset,
        languages=request.languages,
        locations=request.locations,
        query_terms=request.query_terms,
        translated_terms=request.translated_terms,
        include_global_queries=request.include_global_queries,
        use_location_aliases=request.use_location_aliases,
        location_aliases=request.location_aliases,
        max_queries=request.max_expanded_queries,
    )
    results = discover_public_urls(
        queries=executed_queries,
        limit_per_query=request.limit_per_query,
        exclude_social=request.exclude_social,
        engines=request.engines,
    )
    return PublicWebDiscoverResponse(
        results=results,
        discovered_urls=[row.url for row in results],
        executed_queries=executed_queries,
    )


@app.post("/api/v1/public-web/crawl", response_model=PublicWebCrawlResponse)
def public_web_crawl(request: PublicWebCrawlRequest) -> PublicWebCrawlResponse:
    outcome = crawl_public_web(
        seed_urls=request.seed_urls,
        max_pages_per_domain=request.max_pages_per_domain,
        respect_robots=request.respect_robots,
    )
    crawled_leads = extract_leads(outcome.raw_results)

    if request.product_profile and request.icp and crawled_leads:
        crawled_leads = score_leads(crawled_leads, request.product_profile, request.icp, request.weights)

    accepted, skipped_duplicates = _append_unique_leads(crawled_leads, deduplicate=True)
    if accepted:
        _build_notification("public_web_crawl", f"Imported {len(accepted)} public-web leads for review.")

    return PublicWebCrawlResponse(
        imported=len(accepted),
        skipped_duplicates=skipped_duplicates,
        visited_urls=outcome.visited_urls,
        blocked_urls=outcome.blocked_urls,
        leads=accepted,
    )


@app.post("/api/v1/sourcing/plan", response_model=SourcingPlan)
def sourcing_plan(request: SourcingPlanRequest) -> SourcingPlan:
    return build_sourcing_plan(request)


@app.post("/api/v1/sourcing/search", response_model=SourcingSearchResponse)
def sourcing_search(request: SourcingSearchRequest) -> SourcingSearchResponse:
    offers, suppliers = search_sourcing_plan(request.plan, limit_per_platform=request.limit_per_platform)
    return SourcingSearchResponse(plan=request.plan, offers=offers, suppliers=suppliers)


@app.post("/api/v1/sourcing/report", response_model=SourcingReport)
def sourcing_report(request: SourcingReportRequest) -> SourcingReport:
    report = generate_sourcing_report(request)
    store.add_sourcing_report(report)
    _build_notification("sourcing_report", f"Generated sourcing report for {report.product_name}.")
    return report


@app.get("/api/v1/sourcing/reports", response_model=list[SourcingReport])
def list_sourcing_reports(limit: int = Query(default=50, ge=1, le=200)) -> list[SourcingReport]:
    reports = sorted(store.sourcing_reports, key=lambda row: row.generated_at, reverse=True)
    return reports[:limit]


@app.get("/api/v1/sourcing/reports/{report_id}", response_model=SourcingReport)
def get_sourcing_report(report_id: str) -> SourcingReport:
    report = next((item for item in store.sourcing_reports if item.report_id == report_id), None)
    if report is None:
        raise HTTPException(status_code=404, detail="Sourcing report not found")
    return report


@app.get("/api/v1/compliance/data-policy")
def compliance_data_policy() -> JSONResponse:
    policy = {
        "allowed_sources": [
            {
                "key": LeadSourceType.first_party.value,
                "label": "第一方入站",
                "description": "官网表单、演示预约、订阅注册或用户明确选择加入的来源。",
            },
            {
                "key": LeadSourceType.first_party_social.value,
                "label": "自有社媒线索",
                "description": "通过官方流程连接的 LinkedIn Lead Gen Forms、Meta lead ads 或其他客户授权社媒线索。",
            },
            {
                "key": LeadSourceType.customer_import.value,
                "label": "客户自有导入",
                "description": "客户提供且有权处理的 CRM 导出或自有潜客名单。",
            },
            {
                "key": LeadSourceType.public_web.value,
                "label": "公开网页证据",
                "description": "带有明确商业上下文的公司官网、公开联系页、团队页或职位页。",
            },
            {
                "key": LeadSourceType.licensed_database.value,
                "label": "授权 B2B 数据",
                "description": "具备合同、来源说明、删除和退订流程的数据供应商。",
            },
        ],
        "prohibited_sources": [
            {
                "key": "leak_database",
                "label": "泄露或被盗数据库",
                "description": "不要把被盗、泄露或违规获得的数据导入 LeadAgent。",
            },
            {
                "key": "stolen_credentials",
                "label": "未授权账号访问",
                "description": "不要使用依赖被盗 cookie、密码或绕过访问控制的抓取/提取方式。",
            },
            {
                "key": "do_not_contact",
                "label": "已退订或要求删除的联系人",
                "description": "不要重新激活已经退订或要求删除的人。",
            },
        ],
        "notes": [
            "LeadAgent 演示数据是合成数据，真实触达前必须替换成可用数据。",
            "外呼或邮件触达时，每条线索都应保留来源 URL、法律依据和数据保留设置。",
            "不同市场的法律要求不同，正式上线前建议让当地法律顾问确认。",
        ],
    }
    return JSONResponse(content=policy)


@app.post("/api/v1/leads/import", response_model=LeadImportResponse)
def import_leads(request: LeadImportRequest) -> LeadImportResponse:
    raw_rows = [row.model_dump(mode="json") for row in request.leads]
    imported_candidates = extract_leads(raw_rows)
    skipped_in_batch = max(0, len(raw_rows) - len(imported_candidates))
    accepted, skipped_duplicates = _append_unique_leads(imported_candidates, deduplicate=request.deduplicate)
    total_skipped = skipped_in_batch + skipped_duplicates

    if accepted:
        consented = len([lead for lead in accepted if lead.consent_status in {ConsentStatus.consented, ConsentStatus.legitimate_interest}])
        _build_notification("lead_import", f"Imported {len(accepted)} leads ({consented} with outreach-ready legal basis).")

    return LeadImportResponse(
        imported=len(accepted),
        skipped_duplicates=total_skipped,
        leads=accepted,
    )


@app.get("/api/v1/social/connectors", response_model=list[SocialConnectorDefinition])
def social_connectors() -> list[SocialConnectorDefinition]:
    return list_social_connectors()


@app.get("/api/v1/social/connectors/{connector_key}", response_model=SocialConnectorDefinition)
def social_connector_detail(connector_key: SocialConnectorKey) -> SocialConnectorDefinition:
    connector = get_social_connector(connector_key)
    if connector is None:
        raise HTTPException(status_code=404, detail="Social connector not found")
    return connector


@app.get("/api/v1/social/connections", response_model=list[SocialConnection])
def list_social_connections() -> list[SocialConnection]:
    return sorted(store.social_connections, key=lambda row: row.updated_at, reverse=True)


@app.post("/api/v1/social/connections", response_model=SocialConnection)
def create_social_connection(request: SocialConnectionCreateRequest) -> SocialConnection:
    try:
        connector_key = request.connector_key or default_connector_key_for_platform(request.platform)
        validate_connector_platform(connector_key, request.platform)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    connection = SocialConnection(
        connection_id=str(uuid4()),
        connector_key=connector_key,
        platform=request.platform,
        display_name=request.display_name,
        auth_type=request.auth_type,
        owner_email=request.owner_email,
        sync_mode=request.sync_mode,
        scopes=request.scopes,
        selected_assets=request.selected_assets,
        status=SocialConnectionStatus.connected,
    )
    store.upsert_social_connection(connection)
    _build_notification(
        "social_connection",
        f"Connected {connection.platform.value} asset set '{connection.display_name}' via {connection.connector_key.value}.",
    )
    return connection


@app.post("/api/v1/social/connections/{connection_id}/sync", response_model=SocialConnectionSyncResponse)
def sync_social_connection(connection_id: str, request: SocialConnectionSyncRequest) -> SocialConnectionSyncResponse:
    connection = _find_social_connection(connection_id)
    raw_rows = [row.model_dump(mode="json") for row in request.leads]
    imported_candidates = extract_leads(raw_rows)
    skipped_in_batch = max(0, len(raw_rows) - len(imported_candidates))
    accepted, skipped_duplicates = _append_unique_leads(imported_candidates, deduplicate=True)
    total_skipped = skipped_in_batch + skipped_duplicates

    now = datetime.now(timezone.utc)
    updated_connection = connection.model_copy(
        update={
            "status": request.status,
            "last_synced_at": now,
            "last_error": request.error_message,
            "updated_at": now,
        }
    )
    store.upsert_social_connection(updated_connection)

    sync_run = SocialSyncRun(
        run_id=str(uuid4()),
        connection_id=updated_connection.connection_id,
        platform=updated_connection.platform,
        imported=len(accepted),
        skipped_duplicates=total_skipped,
        submitted_leads=len(request.leads),
        asset_count=len(updated_connection.selected_assets),
    )
    store.add_social_sync_run(sync_run)

    if accepted:
        _build_notification(
            "social_sync",
            f"Synced {len(accepted)} leads from {updated_connection.platform.value} connection '{updated_connection.display_name}'.",
        )

    return SocialConnectionSyncResponse(
        connection=updated_connection,
        sync_run=sync_run,
        imported=len(accepted),
        skipped_duplicates=total_skipped,
        leads=accepted,
    )


@app.get("/api/v1/social/overview", response_model=SocialOverview)
def social_overview() -> SocialOverview:
    platform_breakdown = Counter(connection.platform.value for connection in store.social_connections)
    source_breakdown = Counter(
        lead.platform.value for lead in store.leads if lead.source_type == LeadSourceType.first_party_social
    )
    last_sync_at = max(
        (connection.last_synced_at for connection in store.social_connections if connection.last_synced_at is not None),
        default=None,
    )
    total_synced_leads = len([lead for lead in store.leads if lead.source_type == LeadSourceType.first_party_social])

    return SocialOverview(
        connections=len(store.social_connections),
        connected_connections=len(
            [connection for connection in store.social_connections if connection.status == SocialConnectionStatus.connected]
        ),
        synced_connections=len([connection for connection in store.social_connections if connection.last_synced_at is not None]),
        total_synced_leads=total_synced_leads,
        platform_breakdown=dict(platform_breakdown),
        source_breakdown=dict(source_breakdown),
        last_sync_at=last_sync_at,
    )


@app.post("/api/v1/ext/add-product")
def ext_add_product(request: AddProductRequest) -> dict:
    store.add_product_profile(request.product_profile)
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
    store.clear_all()
    return {"status": "ok"}
