from __future__ import annotations

import os
from pathlib import Path
import sys

from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Keep tests deterministic; live mode is covered by a separate smoke run.
os.environ["SEARCH_MODE"] = "mock"

from app.main import app  # noqa: E402


client = TestClient(app)


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
