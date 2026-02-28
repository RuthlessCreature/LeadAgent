from __future__ import annotations

from app.models import ClassificationResult, LeadCandidate


INDUSTRY_LABELS = {
    "manufacturing": ["factory", "industrial", "oem", "components"],
    "logistics": ["shipping", "freight", "warehouse", "cross-border"],
    "saas": ["saas", "software", "crm", "automation"],
    "finance": ["payment", "bank", "fintech", "finance"],
    "healthcare": ["medical", "healthcare", "hospital", "pharma"],
    "ecommerce": ["seller", "marketplace", "retail", "shop"],
}

INTENT_SIGNALS = {
    "hiring_procurement": ["hiring procurement", "procurement analyst"],
    "looking_for_suppliers": ["looking for suppliers", "supplier"],
    "rfq": ["request for quotation", "rfq", "quote"],
    "pricing_interest": ["pricing", "compare", "cost"],
}

ROLE_LABELS = {
    "decision_maker": ["head", "director", "vp", "chief"],
    "influencer": ["manager", "consultant", "lead"],
    "practitioner": ["analyst", "specialist", "coordinator"],
}


def _match_keywords(text: str, keyword_map: dict[str, list[str]]) -> list[str]:
    matches = []
    lowered = text.lower()
    for label, keywords in keyword_map.items():
        if any(keyword in lowered for keyword in keywords):
            matches.append(label)
    return matches


def classify_lead(lead: LeadCandidate) -> ClassificationResult:
    text = " ".join([lead.company, lead.role, lead.raw_text_snippet, " ".join(lead.industry)])
    return ClassificationResult(
        lead_id=lead.lead_id,
        industry_labels=_match_keywords(text, INDUSTRY_LABELS),
        intent_signals=_match_keywords(text, INTENT_SIGNALS),
        role_labels=_match_keywords(lead.role, ROLE_LABELS),
    )
