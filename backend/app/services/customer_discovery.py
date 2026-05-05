from __future__ import annotations

import re
from uuid import NAMESPACE_URL, uuid5

from app.models import BuyerHypothesis, CustomerDiscoveryPlanRequest, CustomerDiscoveryPlanResponse


DEFAULT_BUYER_TYPES = [
    {
        "buyer_type": "Importers and distributors",
        "buyer_roles": ["Importer", "Distributor", "Purchasing Manager", "Sourcing Manager"],
        "company_types": ["importer", "distributor", "wholesaler"],
        "source_plan": ["public_web", "licensed_database", "first_party_social"],
        "confidence": 0.78,
        "rationale": "Most exportable products have discoverable importers, distributors, or wholesalers.",
    },
    {
        "buyer_type": "Retail and ecommerce sellers",
        "buyer_roles": ["Owner", "Category Manager", "Marketplace Seller", "Buying Manager"],
        "company_types": ["retailer", "ecommerce seller", "marketplace store"],
        "source_plan": ["public_web", "customer_import", "licensed_database"],
        "confidence": 0.68,
        "rationale": "Retailers and ecommerce sellers are often publicly visible, but person-level data needs evidence.",
    },
    {
        "buyer_type": "Institutional procurement teams",
        "buyer_roles": ["Procurement Lead", "Operations Manager", "Facilities Manager"],
        "company_types": ["institution", "school", "clinic", "hotel", "event operator"],
        "source_plan": ["public_web", "licensed_database"],
        "confidence": 0.58,
        "rationale": "Institutions can be strong buyers when the product maps to operational use cases.",
    },
]


def build_customer_discovery_plan(request: CustomerDiscoveryPlanRequest) -> CustomerDiscoveryPlanResponse:
    product_name = _extract_product_name(request.product_description)
    geographies = request.geographies or ["global"]
    allowed_sources = set(request.allowed_sources)
    hypotheses: list[BuyerHypothesis] = []

    for template in DEFAULT_BUYER_TYPES:
        source_plan = [source for source in template["source_plan"] if source in allowed_sources]
        if not source_plan:
            continue
        buyer_type = str(template["buyer_type"])
        search_language = _search_language(product_name, buyer_type, geographies)
        hypothesis_id = str(uuid5(NAMESPACE_URL, f"{product_name}|{buyer_type}|{','.join(geographies)}"))
        hypotheses.append(
            BuyerHypothesis(
                hypothesis_id=hypothesis_id,
                buyer_type=buyer_type,
                buyer_roles=list(template["buyer_roles"]),
                company_types=list(template["company_types"]),
                geographies=geographies,
                search_language=search_language,
                source_plan=source_plan,
                confidence=float(template["confidence"]),
                rationale=str(template["rationale"]),
            )
        )

    if request.sales_motion:
        _boost_for_sales_motion(hypotheses, request.sales_motion)

    hypotheses.sort(key=lambda row: row.confidence, reverse=True)
    return CustomerDiscoveryPlanResponse(
        product_name=product_name,
        buyer_hypotheses=hypotheses,
        recommended_next_step=(
            "Run public-web discovery for the highest-confidence buyer type, then add authorized social "
            "or licensed sources for person-level coverage."
        ),
    )


def _extract_product_name(description: str) -> str:
    lines = [line.strip() for line in description.splitlines() if line.strip()]
    for line in lines[:3]:
        lowered = line.lower()
        if lowered.startswith("product:") or line.startswith("商品:"):
            return line.split(":", 1)[1].strip()[:120] or "Unnamed Product"
        if line.startswith("商品："):
            return line.split("：", 1)[1].strip()[:120] or "Unnamed Product"
    if lines:
        return lines[0][:120]
    return "Unnamed Product"


def _search_language(product_name: str, buyer_type: str, geographies: list[str]) -> list[str]:
    product = re.sub(r"\s+", " ", product_name).strip()
    buyer = buyer_type.lower()
    suffixes = ["buyer", "importer", "distributor", "wholesaler"]
    if "retail" in buyer or "ecommerce" in buyer:
        suffixes = ["retailer", "ecommerce seller", "online store", "category buyer"]
    if "institution" in buyer:
        suffixes = ["procurement", "purchasing department", "operations manager"]

    queries: list[str] = []
    for suffix in suffixes:
        queries.append(f"{product} {suffix}")
        for geo in geographies[:4]:
            queries.append(f"{product} {suffix} {geo}")
    return queries[:12]


def _boost_for_sales_motion(hypotheses: list[BuyerHypothesis], sales_motion: str) -> None:
    lowered = sales_motion.lower()
    for hypothesis in hypotheses:
        if any(token in lowered for token in ("wholesale", "distributor", "import")) and "distributor" in hypothesis.buyer_type.lower():
            hypothesis.confidence = min(1.0, hypothesis.confidence + 0.08)
        if any(token in lowered for token in ("retail", "ecommerce", "amazon")) and "retail" in hypothesis.buyer_type.lower():
            hypothesis.confidence = min(1.0, hypothesis.confidence + 0.08)
