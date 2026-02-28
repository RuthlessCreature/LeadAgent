from __future__ import annotations

from app.models import ICPDefinition, LeadCandidate
from app.services.text_utils import normalize_text


def _normalize_list(values: list[str]) -> list[str]:
    cleaned = []
    seen = set()
    for value in values:
        text = normalize_text(value)
        if not text or text in seen:
            continue
        seen.add(text)
        cleaned.append(text)
    return cleaned


def normalize_icp(icp: ICPDefinition) -> ICPDefinition:
    return ICPDefinition(
        geography=_normalize_list(icp.geography),
        company_size=icp.company_size,
        industry=_normalize_list(icp.industry),
        role_titles=_normalize_list(icp.role_titles),
        revenue_range=icp.revenue_range,
        technology_stack=_normalize_list(icp.technology_stack),
    )


def icp_match_score(icp: ICPDefinition, lead: LeadCandidate) -> float:
    score = 0.0
    max_score = 3.0

    lead_blob = normalize_text(
        " ".join([lead.company, lead.role, lead.raw_text_snippet, " ".join(lead.industry)])
    )
    if any(item in lead_blob for item in icp.industry):
        score += 1
    if any(item in lead_blob for item in icp.role_titles):
        score += 1
    if any(item in lead_blob for item in icp.technology_stack):
        score += 1

    return round((score / max_score) * 100.0, 2)
