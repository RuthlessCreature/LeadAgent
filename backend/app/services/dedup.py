from __future__ import annotations

from urllib.parse import urlparse

from app.models import LeadCandidate
from app.services.text_utils import normalize_text, similarity


def _normalize_domain(domain: str) -> str:
    if not domain:
        return ""
    if "://" in domain:
        parsed = urlparse(domain)
        domain = parsed.netloc or parsed.path
    domain = domain.lower().strip()
    if domain.startswith("www."):
        domain = domain[4:]
    return domain


def _company_match(left: str, right: str) -> bool:
    if not left or not right:
        return False
    return similarity(left, right) >= 0.88


def deduplicate_leads(leads: list[LeadCandidate]) -> tuple[list[LeadCandidate], int]:
    deduped: list[LeadCandidate] = []
    removed = 0

    seen_domains: set[str] = set()
    seen_emails: set[str] = set()

    for lead in sorted(leads, key=lambda row: row.scores.overall, reverse=True):
        domain = _normalize_domain(lead.domain)
        email = normalize_text(lead.email)

        is_duplicate = False
        if domain and domain in seen_domains:
            is_duplicate = True
        if email and email in seen_emails:
            is_duplicate = True

        if not is_duplicate:
            for existing in deduped:
                if _company_match(existing.company, lead.company):
                    is_duplicate = True
                    break

        if is_duplicate:
            removed += 1
            continue

        deduped.append(lead)
        if domain:
            seen_domains.add(domain)
        if email:
            seen_emails.add(email)

    return deduped, removed
