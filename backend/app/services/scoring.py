from __future__ import annotations

import re

from app.models import ICPDefinition, LeadCandidate, ProductProfile, ScoreWeights
from app.services.icp import icp_match_score
from app.services.text_utils import jaccard_similarity, tokenize


INTENT_KEYWORDS = {
    "looking for suppliers": 25,
    "request for quotation": 25,
    "rfq": 20,
    "comparing": 15,
    "hiring procurement": 20,
    "evaluating vendors": 20,
    "buying intent": 25,
    "pricing": 15,
    "outbound campaigns": 10,
}


ROLE_BONUS = {
    "head of procurement": 15,
    "purchasing manager": 15,
    "director of strategic sourcing": 15,
    "vp growth": 10,
    "sales operations manager": 10,
}


EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _clamp_score(value: float) -> float:
    return round(max(0.0, min(100.0, value)), 2)


def industry_score(lead: LeadCandidate, product_profile: ProductProfile, icp: ICPDefinition) -> float:
    lead_tokens = tokenize(" ".join(lead.industry + [lead.company, lead.raw_text_snippet]))
    product_tokens = tokenize(" ".join(product_profile.industry_tags + product_profile.feature_tags))
    icp_tokens = tokenize(" ".join(icp.industry))
    content_similarity = jaccard_similarity(lead_tokens, product_tokens) * 100.0
    icp_similarity = jaccard_similarity(lead_tokens, icp_tokens) * 100.0
    blended = (content_similarity * 0.65) + (icp_similarity * 0.35)
    return _clamp_score(blended)


def intent_score(lead: LeadCandidate) -> float:
    text = f"{lead.raw_text_snippet} {lead.role}".lower()
    score = 0
    for keyword, weight in INTENT_KEYWORDS.items():
        if keyword in text:
            score += weight
    for role, bonus in ROLE_BONUS.items():
        if role in text:
            score += bonus
    if "supplier" in text and "looking" in text:
        score += 10
    return _clamp_score(score)


def contact_score(lead: LeadCandidate) -> float:
    score = 0
    if lead.email and EMAIL_REGEX.match(lead.email):
        score += 45
    if lead.linkedin:
        score += 25
    if lead.phone:
        score += 20
    if lead.domain:
        score += 10
    return _clamp_score(score)


def overall_score(industry: float, intent: float, contact: float, weights: ScoreWeights) -> float:
    total_weight = weights.industry + weights.intent + weights.contact
    if total_weight <= 0:
        total_weight = 1.0
    weighted = (
        weights.industry * industry + weights.intent * intent + weights.contact * contact
    ) / total_weight
    return _clamp_score(weighted)


def score_leads(
    leads: list[LeadCandidate], product_profile: ProductProfile, icp: ICPDefinition, weights: ScoreWeights
) -> list[LeadCandidate]:
    scored: list[LeadCandidate] = []
    for lead in leads:
        ind_score = (industry_score(lead, product_profile, icp) + icp_match_score(icp, lead) * 0.25) / 1.25
        int_score = intent_score(lead)
        con_score = contact_score(lead)
        lead.scores.industry = _clamp_score(ind_score)
        lead.scores.intent = int_score
        lead.scores.contact = con_score
        lead.scores.overall = overall_score(lead.scores.industry, int_score, con_score, weights)
        scored.append(lead)
    scored.sort(key=lambda item: item.scores.overall, reverse=True)
    return scored
