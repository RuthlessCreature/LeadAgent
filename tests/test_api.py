from __future__ import annotations

import json
import os
from pathlib import Path
import sys

from bs4 import BeautifulSoup
from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Keep tests deterministic; live mode is covered by a separate smoke run.
os.environ["SEARCH_MODE"] = "mock"

import app.main as main_module  # noqa: E402
from app.main import app  # noqa: E402
from app.services import discovery as discovery_service  # noqa: E402
from app.services import public_web as public_web_service  # noqa: E402
from app.services.llm import parse_json_object  # noqa: E402
from app.store import store  # noqa: E402


client = TestClient(app)


class DummyResponse:
    def __init__(self, url: str, text: str, content_type: str = "text/html; charset=utf-8", status_code: int = 200):
        self.url = url
        self.text = text
        self.headers = {"content-type": content_type}
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def reset_demo() -> None:
    response = client.get("/api/v1/demo/reset")
    assert response.status_code == 200


def test_parse_search_score_pipeline() -> None:
    reset_demo()

    parse_response = client.post(
        "/api/v1/input/parse-product",
        json={
            "description": "Product: LeadPilot\nAI outreach and lead scoring for B2B manufacturing buyers. $99/month",
            "llm_provider": "openai",
        },
    )
    assert parse_response.status_code == 200
    profile = parse_response.json()
    assert profile["product_name"] == "LeadPilot"

    icp_response = client.post(
        "/api/v1/input/icp/normalize",
        json={
            "geography": ["US", "Germany"],
            "company_size": {"min": 20, "max": 500},
            "industry": ["Manufacturing", "Logistics"],
            "role_titles": ["Head of Procurement", "Sales Operations Manager"],
            "revenue_range": {"min": 1000000, "max": 50000000, "currency": "USD"},
            "technology_stack": ["Salesforce", "HubSpot"],
        },
    )
    assert icp_response.status_code == 200
    icp = icp_response.json()
    assert "manufacturing" in icp["industry"]

    search_response = client.post(
        "/api/v1/search/run",
        json={
            "query": "supplier sourcing automation",
            "icp": icp,
            "platforms": ["linkedin", "google", "b2b_db"],
            "limit_per_platform": 3,
        },
    )
    assert search_response.status_code == 200
    leads = search_response.json()["leads"]
    assert len(leads) > 0

    score_response = client.post(
        "/api/v1/scoring/score",
        json={
            "product_profile": profile,
            "icp": icp,
            "leads": leads,
            "weights": {"industry": 0.4, "intent": 0.35, "contact": 0.25},
        },
    )
    assert score_response.status_code == 200
    scored = score_response.json()["leads"]
    assert scored[0]["scores"]["overall"] >= scored[-1]["scores"]["overall"]

    dedup_response = client.post("/api/v1/leads/deduplicate", json={"leads": scored})
    assert dedup_response.status_code == 200
    assert "removed_duplicates" in dedup_response.json()


def test_llm_model_catalog_defaults(monkeypatch) -> None:
    monkeypatch.delenv("DEEPSEEK_MODEL", raising=False)
    monkeypatch.delenv("DEEPSEEK_REASONING_MODEL", raising=False)
    monkeypatch.delenv("DEEPSEEK_REPORT_MODEL", raising=False)
    monkeypatch.delenv("DEEPSEEK_REPORT_REASONING_MODEL", raising=False)

    response = client.get("/api/v1/llm/models")

    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "deepseek"
    assert payload["model"] == "deepseek-v4-flash"
    assert payload["deepseek_defaults"]["reasoning"] == "deepseek-v4-flash-thinking"
    assert payload["deepseek_defaults"]["report"] == "deepseek-v4-pro"
    assert payload["deepseek_defaults"]["legacy_retirement_date"] == "2026-07-24"
    assert parse_json_object('```json\n{"ok": true}\n```') == {"ok": True}


def test_customer_discovery_plan_generates_buyer_hypotheses() -> None:
    response = client.post(
        "/api/v1/customer-discovery/plan",
        json={
            "product_description": "Product: LED camping light\nRechargeable lamp for outdoor retailers.",
            "geographies": ["UAE", "Saudi Arabia"],
            "sales_motion": "wholesale distributor",
            "allowed_sources": ["public_web", "licensed_database"],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["product_name"] == "LED camping light"
    assert len(payload["buyer_hypotheses"]) >= 1
    first = payload["buyer_hypotheses"][0]
    assert "distributor" in " ".join(first["company_types"])
    assert any("UAE" in query for query in first["search_language"])
    assert set(first["source_plan"]) <= {"public_web", "licensed_database"}


def test_sourcing_plan_search_and_report_workflow() -> None:
    reset_demo()

    plan_response = client.post(
        "/api/v1/sourcing/plan",
        json={
            "product_description": "Product: LED camping light\nRechargeable waterproof lamp with custom packaging.",
            "target_platforms": ["1688", "alibaba"],
            "supplier_regions": ["China", "Guangdong"],
            "moq": "500 pcs",
            "certifications": ["CE"],
            "report_language": "EN",
        },
    )
    assert plan_response.status_code == 200
    plan = plan_response.json()
    assert plan["product_name"] == "LED camping light"
    assert "1688" in plan["target_platforms"]
    assert any(query["platform"] == "1688" for query in plan["queries"])
    assert any("灯" in term or "LED" in term for term in plan["query_terms"])

    search_response = client.post(
        "/api/v1/sourcing/search",
        json={
            "plan": plan,
            "limit_per_platform": 3,
        },
    )
    assert search_response.status_code == 200
    search_payload = search_response.json()
    assert len(search_payload["offers"]) >= 1
    assert len(search_payload["suppliers"]) >= 1
    assert search_payload["offers"][0]["source_evidence"]

    report_response = client.post(
        "/api/v1/sourcing/report",
        json={
            "product_name": plan["product_name"],
            "offers": search_payload["offers"],
            "suppliers": search_payload["suppliers"],
            "report_language": "EN",
        },
    )
    assert report_response.status_code == 200
    report = report_response.json()
    assert report["product_name"] == "LED camping light"
    assert "Sourcing Report" in report["report_markdown"]
    assert report["recommendations"]

    saved_response = client.get(f"/api/v1/sourcing/reports/{report['report_id']}")
    assert saved_response.status_code == 200
    assert saved_response.json()["report_id"] == report["report_id"]


def test_lead_card_export_and_dashboard() -> None:
    reset_demo()
    pipeline = client.post(
        "/api/v1/search/run",
        json={
            "query": "b2b lead generation",
            "icp": {
                "geography": ["US"],
                "company_size": {"min": 10, "max": 500},
                "industry": ["saas"],
                "role_titles": ["vp growth"],
                "revenue_range": {"min": 0, "max": 100000000, "currency": "USD"},
                "technology_stack": ["crm"],
            },
            "platforms": ["linkedin"],
            "limit_per_platform": 2,
        },
    )
    assert pipeline.status_code == 200
    leads = pipeline.json()["leads"]
    lead_id = leads[0]["lead_id"]

    card_response = client.get(f"/api/v1/leads/{lead_id}/card")
    assert card_response.status_code == 200
    card = card_response.json()
    assert card["lead_id"] == lead_id

    template_response = client.post(
        "/api/v1/outreach/templates",
        json={"lead_card": card, "language": "EN"},
    )
    assert template_response.status_code == 200
    assert "first_touch" in template_response.json()

    csv_response = client.get("/api/v1/leads/export?format=csv")
    assert csv_response.status_code == 200
    assert "text/csv" in csv_response.headers["content-type"]

    pdf_response = client.get("/api/v1/leads/export?format=pdf")
    assert pdf_response.status_code == 200
    assert "application/pdf" in pdf_response.headers["content-type"]

    dashboard = client.get("/api/v1/dashboard")
    assert dashboard.status_code == 200
    assert "new_leads" in dashboard.json()


def test_owned_import_and_policy_routes() -> None:
    reset_demo()

    policy = client.get("/api/v1/compliance/data-policy")
    assert policy.status_code == 200
    assert any(item["key"] == "first_party_social" for item in policy.json()["allowed_sources"])
    assert any(item["key"] == "customer_import" for item in policy.json()["allowed_sources"])
    assert any(item["key"] == "leak_database" for item in policy.json()["prohibited_sources"])

    import_response = client.post(
        "/api/v1/leads/import",
        json={
            "deduplicate": True,
            "leads": [
                {
                    "company": "Northwind Systems",
                    "platform": "b2b_db",
                    "contact_name": "Ivy Brooks",
                    "role": "Revenue Operations Lead",
                    "email": "ivy@northwind-systems.example",
                    "domain": "northwind-systems.example",
                    "raw_text_snippet": "Customer-owned export from CRM for outbound review.",
                    "source_type": "customer_import",
                    "source_label": "Customer CRM export",
                    "consent_status": "consented",
                    "verification_status": "email_verified",
                },
                {
                    "company": "Northwind Systems",
                    "platform": "b2b_db",
                    "contact_name": "Ivy Brooks",
                    "role": "Revenue Operations Lead",
                    "email": "ivy@northwind-systems.example",
                    "domain": "northwind-systems.example",
                    "raw_text_snippet": "Customer-owned export from CRM for outbound review.",
                    "source_type": "customer_import",
                    "source_label": "Customer CRM export",
                    "consent_status": "consented",
                    "verification_status": "email_verified",
                },
            ],
        },
    )
    assert import_response.status_code == 200
    import_payload = import_response.json()
    assert import_payload["imported"] == 1
    assert import_payload["skipped_duplicates"] == 1

    leads_response = client.get("/api/v1/leads?source_type=customer_import")
    assert leads_response.status_code == 200
    leads = leads_response.json()
    assert len(leads) == 1
    assert leads[0]["source_type"] == "customer_import"

    compliance = client.post(
        "/api/v1/compliance/scan",
        json={"lead_ids": [import_payload["leads"][0]["lead_id"]]},
    )
    assert compliance.status_code == 200
    row = compliance.json()[0]
    assert row["source_risk_level"] in {"low", "medium"}


def test_public_web_crawl_route(monkeypatch) -> None:
    reset_demo()

    pages = {
        "https://acme.example/robots.txt": DummyResponse(
            "https://acme.example/robots.txt",
            "User-agent: *\nAllow: /\n",
            content_type="text/plain",
        ),
        "https://acme.example": DummyResponse(
            "https://acme.example",
            """
            <html>
              <head>
                <title>Acme Industrial</title>
                <meta name="description" content="Industrial supplier serving distributors." />
              </head>
              <body>
                <a href="/contact">Contact</a>
              </body>
            </html>
            """,
        ),
        "https://acme.example/contact": DummyResponse(
            "https://acme.example/contact",
            """
            <html>
              <head><title>Contact | Acme Industrial</title></head>
              <body>
                <h1>Contact Acme Industrial</h1>
                <p>Email our sales desk at sales@acme.example or call +1 415 555 9988.</p>
                <a href="mailto:sales@acme.example">sales@acme.example</a>
              </body>
            </html>
            """,
        ),
    }

    def fake_get(self, url, timeout=10, allow_redirects=True):  # noqa: ANN001
        key = url.rstrip("/")
        if key in pages:
            return pages[key]
        raise RuntimeError(f"Unexpected URL {url}")

    monkeypatch.setattr(public_web_service.requests.Session, "get", fake_get)

    response = client.post(
        "/api/v1/public-web/crawl",
        json={
            "seed_urls": ["https://acme.example"],
            "max_pages_per_domain": 3,
            "respect_robots": True,
            "product_profile": {
                "product_name": "LeadAgent",
                "industry_tags": ["manufacturing"],
                "feature_tags": ["automation"],
                "use_cases": ["sales_outreach"],
                "target_roles": ["operations"],
                "price_range": "unknown",
                "exclude_tags": [],
                "llm_provider": "mock",
            },
            "icp": {
                "geography": ["US"],
                "company_size": {"min": 10, "max": 1000},
                "industry": ["manufacturing"],
                "role_titles": ["sales manager"],
                "revenue_range": {"min": 0, "max": 100000000, "currency": "USD"},
                "technology_stack": [],
            },
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["imported"] == 1
    assert payload["visited_urls"] == ["https://acme.example", "https://acme.example/contact"]
    assert payload["leads"][0]["email"] == "sales@acme.example"
    assert payload["leads"][0]["source_type"] == "public_web"


def test_public_web_crawl_route_extracts_named_people(monkeypatch) -> None:
    reset_demo()

    pages = {
        "https://safar.example/robots.txt": DummyResponse(
            "https://safar.example/robots.txt",
            "User-agent: *\nAllow: /\n",
            content_type="text/plain",
        ),
        "https://safar.example": DummyResponse(
            "https://safar.example",
            """
            <html>
              <head><title>Safar Travels</title></head>
              <body>
                <a href="/team">Our Team</a>
              </body>
            </html>
            """,
        ),
        "https://safar.example/team": DummyResponse(
            "https://safar.example/team",
            """
            <html>
              <head><title>Team | Safar Travels</title></head>
              <body>
                <section class="team-member">
                  <h3>Sarah Khan</h3>
                  <p>Sales Manager</p>
                  <a href="mailto:sarah@safar.example">sarah@safar.example</a>
                  <a href="tel:+44 20 1234 5678">+44 20 1234 5678</a>
                </section>
                <section class="team-member">
                  <h3>Ahmed Ali</h3>
                  <p>Travel Consultant</p>
                  <a href="mailto:ahmed@safar.example">ahmed@safar.example</a>
                </section>
              </body>
            </html>
            """,
        ),
    }

    def fake_get(self, url, timeout=10, allow_redirects=True):  # noqa: ANN001
        key = url.rstrip("/")
        if key in pages:
            return pages[key]
        raise RuntimeError(f"Unexpected URL {url}")

    monkeypatch.setattr(public_web_service.requests.Session, "get", fake_get)

    response = client.post(
        "/api/v1/public-web/crawl",
        json={
            "seed_urls": ["https://safar.example"],
            "max_pages_per_domain": 3,
            "respect_robots": True,
            "product_profile": {
                "product_name": "LeadAgent",
                "industry_tags": ["travel"],
                "feature_tags": ["outbound"],
                "use_cases": ["sales_outreach"],
                "target_roles": ["sales", "operations"],
                "price_range": "unknown",
                "exclude_tags": [],
                "llm_provider": "mock",
            },
            "icp": {
                "geography": ["UK"],
                "company_size": {"min": 1, "max": 1000},
                "industry": ["travel"],
                "role_titles": ["sales manager", "travel consultant"],
                "revenue_range": {"min": 0, "max": 100000000, "currency": "USD"},
                "technology_stack": [],
            },
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["imported"] == 2
    leads = sorted(payload["leads"], key=lambda item: item["contact_name"])
    assert [lead["contact_name"] for lead in leads] == ["Ahmed Ali", "Sarah Khan"]
    assert [lead["role"] for lead in leads] == ["Travel Consultant", "Sales Manager"]
    assert leads[0]["email"] == "ahmed@safar.example"
    assert leads[1]["phone"] == "+44 20 1234 5678"


def test_public_web_discover_route_filters_social(monkeypatch) -> None:
    html = """
    <html>
      <body>
        <div class="result">
          <div class="result__title">
            <a href="//duckduckgo.com/l/?uddg=https%3A%2F%2Facme.example%2Fcontact">Acme Hajj Supplies</a>
          </div>
          <div class="result__snippet">Pilgrim kits and wholesale distribution.</div>
        </div>
        <div class="result">
          <div class="result__title">
            <a href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fwww.facebook.com%2Facmehajj">Acme Facebook</a>
          </div>
          <div class="result__snippet">Social profile.</div>
        </div>
      </body>
    </html>
    """

    def fake_get(self, url, timeout=10, allow_redirects=True):  # noqa: ANN001
        return DummyResponse(url, html)

    monkeypatch.setattr(discovery_service.requests.Session, "get", fake_get)

    response = client.post(
        "/api/v1/public-web/discover",
        json={
            "queries": ["hajj supplies distributor"],
            "limit_per_query": 5,
            "exclude_social": True,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["discovered_urls"] == ["https://acme.example/contact"]
    assert payload["results"][0]["domain"] == "acme.example"
    assert payload["executed_queries"] == ["hajj supplies distributor"]


def test_public_web_discover_route_expands_multilingual_queries(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_discover_public_urls(queries, limit_per_query=10, exclude_social=True, engines=None):  # noqa: ANN001
        captured["queries"] = list(queries)
        captured["engines"] = list(engines or [])
        return []

    monkeypatch.setattr(main_module, "discover_public_urls", fake_discover_public_urls)

    response = client.post(
        "/api/v1/public-web/discover",
        json={
            "query_preset": "hajj_umrah",
            "languages": ["en", "ar", "ur"],
            "locations": ["London"],
            "engines": ["yahoo"],
            "limit_per_query": 5,
            "use_location_aliases": True,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    executed_queries = payload["executed_queries"]
    assert "umrah packages" in executed_queries
    assert "umrah packages London" in executed_queries
    assert any("باقات العمرة" in query for query in executed_queries)
    assert any("عمرہ پیکج" in query for query in executed_queries)
    assert any("باقات العمرة لندن" in query for query in executed_queries)
    assert any("عمرہ پیکج لندن" in query for query in executed_queries)
    assert captured["engines"] == ["yahoo"]


def test_public_web_contact_cleanup_helpers() -> None:
    html = """
    <html>
      <body>
        <a href="mailto:info@acme.example%20">Email</a>
        <p>Placeholder phone 1 2 3 4 5 6 7 8 9 and real phone +1 415 555 9988.</p>
      </body>
    </html>
    """
    soup = BeautifulSoup(html, "html.parser")
    page_text = soup.get_text(" ", strip=True)

    emails = public_web_service._emails_from_page(soup, page_text)
    phones = public_web_service._phones_from_text(page_text)

    assert emails == ["info@acme.example"]
    assert "+1 415 555 9988" in phones
    assert "1 2 3 4 5 6 7 8 9" not in phones


def test_social_connection_sync_workflow() -> None:
    reset_demo()

    create_response = client.post(
        "/api/v1/social/connections",
        json={
            "connector_key": "linkedin_lead_sync",
            "platform": "linkedin",
            "display_name": "Acme LinkedIn Lead Sync",
            "owner_email": "ops@acme.example",
            "sync_mode": "hybrid",
            "scopes": ["r_organization_social", "rw_ads"],
            "selected_assets": [
                {
                    "asset_id": "urn:li:sponsoredAccount:123",
                    "asset_type": "ad_account",
                    "name": "Acme Sponsored Account",
                    "selected": True,
                },
                {
                    "asset_id": "urn:li:leadForm:456",
                    "asset_type": "form",
                    "name": "Q2 Demo Form",
                    "selected": True,
                },
            ],
        },
    )
    assert create_response.status_code == 200
    connection = create_response.json()
    assert connection["platform"] == "linkedin"
    assert len(connection["selected_assets"]) == 2

    sync_response = client.post(
        f"/api/v1/social/connections/{connection['connection_id']}/sync",
        json={
            "status": "connected",
            "leads": [
                {
                    "company": "Northwind Systems",
                    "platform": "linkedin",
                    "contact_name": "Ivy Brooks",
                    "role": "Revenue Operations Lead",
                    "email": "ivy@northwind.example",
                    "source_type": "first_party_social",
                    "source_label": "LinkedIn Lead Gen Form",
                    "source_external_lead_id": "lead-001",
                    "source_asset_owner_type": "organization",
                    "source_asset_owner_id": "urn:li:organization:999",
                    "source_form_id": "urn:li:leadForm:456",
                    "source_campaign_id": "urn:li:sponsoredCampaign:789",
                    "source_ad_account_id": "urn:li:sponsoredAccount:123",
                    "source_consent_text": "Yes, I want product updates and a demo.",
                    "source_privacy_policy_url": "https://acme.example/privacy",
                    "source_submission_timestamp": "2026-04-06T10:30:00Z",
                    "source_payload_version": "li-v2026-03",
                    "source_raw_payload_hash": "abc123",
                    "consent_status": "consented",
                    "verification_status": "company_verified",
                    "raw_text_snippet": "Inbound LinkedIn lead form submission from Acme campaign.",
                },
                {
                    "company": "Northwind Systems",
                    "platform": "linkedin",
                    "contact_name": "Ivy Brooks",
                    "role": "Revenue Operations Lead",
                    "email": "ivy@northwind.example",
                    "source_type": "first_party_social",
                    "source_label": "LinkedIn Lead Gen Form",
                    "source_external_lead_id": "lead-001",
                    "source_asset_owner_type": "organization",
                    "source_asset_owner_id": "urn:li:organization:999",
                    "source_form_id": "urn:li:leadForm:456",
                    "source_campaign_id": "urn:li:sponsoredCampaign:789",
                    "source_ad_account_id": "urn:li:sponsoredAccount:123",
                    "source_submission_timestamp": "2026-04-06T10:30:00Z",
                    "source_payload_version": "li-v2026-03",
                    "source_raw_payload_hash": "abc123",
                    "consent_status": "consented",
                    "verification_status": "company_verified",
                    "raw_text_snippet": "Inbound LinkedIn lead form submission from Acme campaign.",
                },
            ],
        },
    )
    assert sync_response.status_code == 200
    sync_payload = sync_response.json()
    assert sync_payload["imported"] == 1
    assert sync_payload["skipped_duplicates"] == 1
    assert sync_payload["connection"]["last_synced_at"] is not None
    assert sync_payload["leads"][0]["source_type"] == "first_party_social"
    assert sync_payload["leads"][0]["source_form_id"] == "urn:li:leadForm:456"

    overview_response = client.get("/api/v1/social/overview")
    assert overview_response.status_code == 200
    overview = overview_response.json()
    assert overview["connections"] == 1
    assert overview["connected_connections"] == 1
    assert overview["synced_connections"] == 1
    assert overview["total_synced_leads"] == 1
    assert overview["platform_breakdown"]["linkedin"] == 1
    assert overview["source_breakdown"]["linkedin"] == 1

    leads_response = client.get("/api/v1/leads?source_type=first_party_social")
    assert leads_response.status_code == 200
    leads = leads_response.json()
    assert len(leads) == 1
    assert leads[0]["source_asset_owner_id"] == "urn:li:organization:999"

    notifications = client.get("/api/v1/notifications")
    assert notifications.status_code == 200
    categories = [item["category"] for item in notifications.json()]
    assert "social_connection" in categories
    assert "social_sync" in categories


def test_social_connector_catalog_and_persistence(monkeypatch, tmp_path: Path) -> None:
    state_path = tmp_path / "leadagent_store.json"
    monkeypatch.setattr(store, "state_path", state_path)
    store.clear_all()

    connectors_response = client.get("/api/v1/social/connectors")
    assert connectors_response.status_code == 200
    connectors = connectors_response.json()
    keys = {item["connector_key"] for item in connectors}
    assert {"linkedin_lead_sync", "meta_lead_ads"} <= keys

    linkedin_detail = client.get("/api/v1/social/connectors/linkedin_lead_sync")
    assert linkedin_detail.status_code == 200
    payload = linkedin_detail.json()
    assert payload["platform"] == "linkedin"
    assert payload["expected_lead_fields"][0]["key"] == "company"

    create_response = client.post(
        "/api/v1/social/connections",
        json={
            "platform": "linkedin",
            "display_name": "Persistent LinkedIn",
            "owner_email": "growth@example.com",
            "selected_assets": [
                {
                    "asset_id": "urn:li:leadForm:999",
                    "asset_type": "form",
                    "name": "Persistent Form",
                    "selected": True,
                }
            ],
        },
    )
    assert create_response.status_code == 200
    connection_id = create_response.json()["connection_id"]
    assert state_path.exists()

    sync_response = client.post(
        f"/api/v1/social/connections/{connection_id}/sync",
        json={
            "leads": [
                {
                    "company": "Contoso",
                    "platform": "linkedin",
                    "contact_name": "Mia Chen",
                    "email": "mia@contoso.example",
                    "source_type": "first_party_social",
                    "source_label": "LinkedIn Lead Gen Form",
                    "source_external_lead_id": "lead-xyz",
                    "source_form_id": "urn:li:leadForm:999",
                    "source_submission_timestamp": "2026-04-07T09:00:00Z",
                    "consent_status": "consented",
                    "verification_status": "company_verified",
                    "raw_text_snippet": "Persistent LinkedIn lead sync.",
                }
            ]
        },
    )
    assert sync_response.status_code == 200

    persisted = json.loads(state_path.read_text(encoding="utf-8"))
    assert len(persisted["social_connections"]) == 1
    assert len(persisted["social_sync_runs"]) == 1
    assert len(persisted["leads"]) == 1
    assert persisted["social_connections"][0]["connector_key"] == "linkedin_lead_sync"
    assert persisted["leads"][0]["source_external_lead_id"] == "lead-xyz"

    store.social_connections.clear()
    store.social_sync_runs.clear()
    store.leads.clear()
    store.load()

    assert len(store.social_connections) == 1
    assert len(store.social_sync_runs) == 1
    assert len(store.leads) == 1
    assert store.social_connections[0].connector_key.value == "linkedin_lead_sync"

    reset_demo()
