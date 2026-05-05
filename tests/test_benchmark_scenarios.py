from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import benchmark_public_web_scenarios as benchmark  # noqa: E402


def test_load_scenarios_from_file_supports_generic_verticals(tmp_path: Path) -> None:
    scenario_path = tmp_path / "scenarios.json"
    scenario_path.write_text(
        json.dumps(
            [
                {
                    "scenario_id": "dental_equipment_distributor",
                    "product": "Dental imaging distributor",
                    "buyer_type": "Dental clinics",
                    "query_terms": ["dental clinic"],
                    "translated_terms": {},
                    "include_keywords": ["dental", "clinic"],
                    "product_profile": {
                        "product_name": "Dental imaging distributor",
                        "industry_tags": ["healthcare", "dental"],
                        "feature_tags": ["imaging"],
                        "use_cases": ["sales_outreach"],
                        "target_roles": ["owner"],
                        "price_range": "distributor",
                        "exclude_tags": [],
                        "llm_provider": "mock",
                    },
                    "icp": {
                        "geography": ["US"],
                        "company_size": {"min": 1, "max": 1000},
                        "industry": ["healthcare", "dental"],
                        "role_titles": ["owner"],
                        "revenue_range": {"min": 0, "max": 1000000, "currency": "USD"},
                        "technology_stack": [],
                    },
                    "locations": ["Houston", "USA"],
                    "languages": ["en"],
                }
            ]
        ),
        encoding="utf-8",
    )

    scenarios = benchmark.load_scenarios(scenario_path)

    assert [scenario.scenario_id for scenario in scenarios] == ["dental_equipment_distributor"]
    assert scenarios[0].query_terms == ("dental clinic",)
    assert scenarios[0].include_keywords == ("dental", "clinic")


def test_normalize_title_prefers_keyword_rich_company_segment() -> None:
    title = "Top Software Review | Northwind Warehouse Systems"

    normalized = benchmark.normalize_title(title, "northwind.example", ("warehouse", "systems"))

    assert normalized == "Northwind Warehouse Systems"
