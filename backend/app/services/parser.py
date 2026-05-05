from __future__ import annotations

import re

from app.models import ProductProfile
from app.services.text_utils import tokenize


INDUSTRY_KEYWORDS: dict[str, list[str]] = {
    "manufacturing": ["factory", "manufacturing", "industrial", "oem"],
    "saas": ["saas", "software", "cloud"],
    "ecommerce": ["ecommerce", "shop", "retail", "marketplace", "seller"],
    "healthcare": ["medical", "healthcare", "hospital", "pharma"],
    "finance": ["finance", "fintech", "bank", "payment"],
    "logistics": ["shipping", "logistics", "freight", "warehouse"],
}

FEATURE_KEYWORDS: dict[str, list[str]] = {
    "crm": ["crm", "customer relationship"],
    "automation": ["automation", "automate", "workflow"],
    "lead_generation": ["lead generation", "prospect", "b2b lead"],
    "analytics": ["dashboard", "analytics", "report", "insight"],
    "ai_assistant": ["ai", "llm", "agent", "assistant"],
    "multilingual": ["multilingual", "translation", "multi-language"],
}

USE_CASE_KEYWORDS: dict[str, list[str]] = {
    "sales_outreach": ["outreach", "cold email", "follow up", "prospecting"],
    "data_enrichment": ["enrichment", "data cleaning", "deduplicate"],
    "pipeline_management": ["pipeline", "crm sync", "lead scoring"],
    "market_expansion": ["global", "cross border", "export", "overseas"],
}

ROLE_KEYWORDS: dict[str, list[str]] = {
    "sales_manager": ["sales manager", "sales lead", "head of sales"],
    "founder": ["founder", "cofounder", "owner", "ceo"],
    "business_development": ["business development", "bdm", "partnership"],
    "operations": ["operations", "ops", "growth operations"],
    "marketing_manager": ["marketing manager", "demand gen", "growth marketer"],
}

EXCLUDE_HINTS: list[str] = [
    "student",
    "intern",
    "freelancer",
    "b2c",
]


def _extract_tags(description: str, tag_map: dict[str, list[str]]) -> list[str]:
    lower_text = description.lower()
    tags: list[str] = []
    for canonical, keywords in tag_map.items():
        if any(keyword in lower_text for keyword in keywords):
            tags.append(canonical)
    return sorted(set(tags))


def _extract_price_range(description: str) -> str:
    lower_text = description.lower()
    monthly = re.search(r"(\$?\d+)\s*-\s*(\$?\d+)\s*/?\s*month", lower_text)
    annual = re.search(r"(\$?\d+)\s*-\s*(\$?\d+)\s*/?\s*year", lower_text)
    if monthly:
        return f"{monthly.group(1)}-{monthly.group(2)}/month"
    if annual:
        return f"{annual.group(1)}-{annual.group(2)}/year"
    single = re.search(r"\$?\d+\s*/?\s*(month|year)", lower_text)
    if single:
        return single.group(0)
    if "enterprise" in lower_text:
        return "enterprise"
    if "free" in lower_text:
        return "free"
    return "unknown"


def _extract_product_name(description: str) -> str:
    lines = [line.strip() for line in description.splitlines() if line.strip()]
    if not lines:
        return "Unnamed Product"

    for line in lines[:3]:
        lowered = line.lower()
        if lowered.startswith("product:") or line.startswith("商品:"):
            return line.split(":", 1)[1].strip()
        if line.startswith("商品："):
            return line.split("：", 1)[1].strip()
    return lines[0][:80]


def parse_product_description(description: str) -> ProductProfile:
    tokens = tokenize(description)
    exclude_tags = sorted(set(token for token in tokens if token in EXCLUDE_HINTS))

    return ProductProfile(
        product_name=_extract_product_name(description),
        industry_tags=_extract_tags(description, INDUSTRY_KEYWORDS),
        feature_tags=_extract_tags(description, FEATURE_KEYWORDS),
        use_cases=_extract_tags(description, USE_CASE_KEYWORDS),
        target_roles=_extract_tags(description, ROLE_KEYWORDS),
        price_range=_extract_price_range(description),
        exclude_tags=exclude_tags,
    )
